#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI-shaped single-call image transports (text + reference-conditioned).

Adapted from the VNE repo:

* ``services/image_provider_boundary/client.py``      -> the text path
  (``POST <base>/v1/images/generations``, JSON, ``n=1``)
* ``services/character_visual_conditioning/provider.py`` -> the conditioned
  path (``POST <base>/v1/images/edits``, ``multipart/form-data`` with repeated
  ``image[]`` parts, ``n=1``)

Adaptation (both paths):

* NO ``os.environ["OPENAI_API_KEY"]`` fallback -- the credential is an explicit
  argument or the call raises before any network I/O.
* Base URL is an explicit argument (resolved from Companion provider config by
  the caller); no hard-coded ``api.openai.com`` default is used at runtime.
* The single HTTP request goes through an INJECTABLE callable seam
  (:data:`ImageHttpPost`) so tests never open a socket. The default seam is a
  plain ``urllib`` POST, matching :mod:`services.character_companion.cloud_provider`.
* Exactly one request per call. No retry. No fallback. No second URL fetch.
* Reference bytes come only from the already-validated ``ReferenceBundle``
  entries -- never a file reopen, never Character Canon.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from ..character_import.reference_importer import sniff_image_format
from .provider_errors import (
    ImageHTTPFailureDiagnostic,
    ImageGenerationConfigurationError,
    ImageGenerationResultError,
    ImageGenerationTransportError,
)
from .provider_model import (
    CONTENT_TYPE_TO_EXTENSION,
    DEFAULT_SIZE,
    IMAGE_FORMAT_KEY_TO_CONTENT_TYPE,
    GeneratedImage,
)
from .reference_model import ReferenceBundle

DEFAULT_TIMEOUT_S = 300.0
TEXT_ENDPOINT_PATH = "/v1/images/generations"
EDIT_ENDPOINT_PATH = "/v1/images/edits"

#: Injectable transport seam: (url, body_bytes, headers, timeout_s) -> JSON dict.
ImageHttpPost = Callable[[str, bytes, dict, float], Any]


def _http_failure_diagnostic(exc: urllib.error.HTTPError, headers: dict) -> ImageHTTPFailureDiagnostic:
    # Ограничиваем чтение; HTML, обрезанный JSON и лишние поля не сохраняются.
    error = {}
    try:
        raw = exc.read(16_384 + 1)
        if len(raw) <= 16_384:
            data = json.loads(raw)
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                error = data["error"]
    except (OSError, ValueError, RecursionError):
        pass
    finally:
        exc.close()
    authorization = next((v for k, v in headers.items() if k.lower() == "authorization"), "")
    credential = authorization.partition(" ")[2]
    return ImageHTTPFailureDiagnostic(
        http_status=exc.code,
        provider_error_code=error.get("code"),
        provider_error_type=error.get("type"),
        provider_message=error.get("message"),
        secrets=(authorization, credential),
    )


def _default_image_http_post(url: str, body: bytes, headers: dict, timeout_s: float) -> Any:
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Accept": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ImageGenerationTransportError(
            "image provider HTTP request failed", diagnostic=_http_failure_diagnostic(exc, headers)
        ) from None
    except urllib.error.URLError:
        raise ImageGenerationTransportError("image provider unreachable") from None
    except TimeoutError:
        raise ImageGenerationTransportError("image provider timed out") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ImageGenerationTransportError("image provider returned invalid JSON") from None
    if not isinstance(data, dict):
        raise ImageGenerationTransportError("image provider response must be a JSON object")
    return data


# ---------------------------------------------------------------------------
# shared validation + result decode
# ---------------------------------------------------------------------------
def _require(value: Optional[str], what: str) -> str:
    s = (value or "").strip()
    if not s:
        raise ImageGenerationConfigurationError(f"{what} is required before any network call")
    return s


def _decode_single_image(data: dict, *, model: str) -> GeneratedImage:
    items = data.get("data")
    if not isinstance(items, list) or len(items) != 1:
        raise ImageGenerationResultError("image provider did not return exactly one image result")
    item = items[0]
    if not isinstance(item, dict):
        raise ImageGenerationResultError("image provider result entry is not an object")

    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        try:
            payload = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageGenerationResultError("image provider returned invalid base64 image data") from exc
        if not payload:
            raise ImageGenerationResultError("image provider returned empty image data")
        fmt = sniff_image_format(payload)
        content_type = IMAGE_FORMAT_KEY_TO_CONTENT_TYPE.get(fmt or "")
        if content_type is None:
            raise ImageGenerationResultError("image provider returned an unrecognised image format")
        return GeneratedImage.from_bytes(payload=payload, content_type=content_type, model=model)

    if item.get("url"):
        raise ImageGenerationResultError(
            "image provider returned a URL-only result; this boundary refuses the required second fetch"
        )
    raise ImageGenerationResultError("image provider returned no decodable image payload")


def _auth_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


# ---------------------------------------------------------------------------
# text -> image
# ---------------------------------------------------------------------------
def generate_text_to_image(
    *,
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    size: str = DEFAULT_SIZE,
    quality: Optional[str] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    http_post: Optional[ImageHttpPost] = None,
) -> GeneratedImage:
    """One ``POST <base>/v1/images/generations`` call. No multipart, no retry."""
    prompt = _require(prompt, "prompt")
    model = _require(model, "model")
    key = _require(api_key, "credential")
    base = _require(base_url, "base_url")

    payload: dict[str, Any] = {"model": model, "prompt": prompt, "n": 1, "size": size}
    if quality:
        payload["quality"] = quality
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", **_auth_headers(key)}
    url = base.rstrip("/") + TEXT_ENDPOINT_PATH

    post = http_post or _default_image_http_post
    data = post(url, body, headers, timeout_s)
    if not isinstance(data, dict):
        raise ImageGenerationTransportError("image provider response must be a JSON object")
    return _decode_single_image(data, model=model)


# ---------------------------------------------------------------------------
# reference-conditioned -> image
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReferenceImageInput:
    filename: str
    content_type: str
    payload: bytes


def _sanitize_token(value: str) -> str:
    out = "".join(ch if (ch.isascii() and (ch.isalnum() or ch in "_-")) else "_" for ch in value)
    return out or "char"


def reference_inputs_from_bundle(bundle: ReferenceBundle) -> list[ReferenceImageInput]:
    """Ordered provider image inputs from a validated ReferenceBundle.

    Order == bundle order (already deterministic from Slice B selection). Uses
    ``entry.payload`` bytes directly; never reopens a snapshot or Canon file.
    Filenames are index + character-id derived and carry no absolute path.
    """
    inputs: list[ReferenceImageInput] = []
    for index, entry in enumerate(bundle.references):
        ext = CONTENT_TYPE_TO_EXTENSION.get(entry.content_type)
        if ext is None:
            raise ImageGenerationConfigurationError(
                f"reference {entry.asset_id!r} has unsupported content type {entry.content_type!r}"
            )
        if not isinstance(entry.payload, bytes) or not entry.payload:
            raise ImageGenerationConfigurationError(
                f"reference {entry.asset_id!r} payload is empty"
            )
        inputs.append(
            ReferenceImageInput(
                filename=f"ref_{index:03d}_{_sanitize_token(entry.character_id)}.{ext}",
                content_type=entry.content_type,
                payload=entry.payload,
            )
        )
    return inputs


def _build_multipart(
    boundary: str,
    *,
    model: str,
    prompt: str,
    size: str,
    quality: str,
    images: Sequence[ReferenceImageInput],
) -> bytes:
    crlf = b"\r\n"
    lines: list[bytes] = []

    def field(name: str, value: str) -> None:
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(value.encode("utf-8"))

    field("model", model)
    field("prompt", prompt)
    field("n", "1")
    field("size", size)
    field("quality", quality)
    for img in images:
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="image[]"; filename="{img.filename}"'.encode("utf-8")
        )
        lines.append(f"Content-Type: {img.content_type}".encode("utf-8"))
        lines.append(b"")
        lines.append(img.payload)
    lines.append(f"--{boundary}--".encode("utf-8"))
    return crlf.join(lines) + crlf


def generate_conditioned_image(
    *,
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    references: Sequence[ReferenceImageInput],
    size: str = DEFAULT_SIZE,
    quality: str = "low",
    timeout_s: float = DEFAULT_TIMEOUT_S,
    http_post: Optional[ImageHttpPost] = None,
) -> GeneratedImage:
    """One ``POST <base>/v1/images/edits`` multipart call. Prompt sent verbatim."""
    prompt = _require(prompt, "prompt")
    model = _require(model, "model")
    key = _require(api_key, "credential")
    base = _require(base_url, "base_url")

    images = list(references)
    if not images:
        raise ImageGenerationConfigurationError(
            "at least one reference image is required for a conditioned request"
        )
    for img in images:
        if not isinstance(img.payload, bytes) or not img.payload:
            raise ImageGenerationConfigurationError("reference image payload must be non-empty bytes")

    boundary = "----companion-c-" + hashlib.sha256(
        json.dumps({"model": model, "prompt": prompt, "n": len(images)}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    body = _build_multipart(boundary, model=model, prompt=prompt, size=size, quality=quality, images=images)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", **_auth_headers(key)}
    url = base.rstrip("/") + EDIT_ENDPOINT_PATH

    post = http_post or _default_image_http_post
    data = post(url, body, headers, timeout_s)
    if not isinstance(data, dict):
        raise ImageGenerationTransportError("image provider response must be a JSON object")
    return _decode_single_image(data, model=model)
