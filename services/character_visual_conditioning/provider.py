#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Visual Reference Conditioning v0 (C3) -- provider-adjacent transport.

A single-call, no-retry, no-fallback image-edit transport for
reference-conditioned image generation. It is SEPARATE from the C1 text-only
``services/image_provider_boundary`` path (which remains untouched and
backward-compatible).

Target (owner-ratified for the future C3 live smoke):

    POST /v1/images/edits   (multipart/form-data)

Safety contract (same discipline as C1):
- model + credential + explicit image inputs required BEFORE network; missing
  inputs raise before any network I/O.
- prompt text is sent verbatim (NEVER rewritten).
- n=1, size=1024x1024, quality=low, non-streaming.
- exactly one request; no retry; no fallback; no second fetch.
- in-band base64 image result only; URL-only results are REFUSED.

Stdlib-only (``urllib`` + manual multipart). No new dependency.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .errors import (
    ProviderInputConfigurationError,
    ProviderInputResultError,
    ProviderInputTransportError,
)
from .model import ConditionedImage, VisualReferenceSet

DEFAULT_BASE_URL = "https://api.openai.com"
DEFAULT_TIMEOUT_S = 300.0
EDIT_ENDPOINT_PATH = "/v1/images/edits"

_FORMAT_TO_CONTENT_TYPE = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class ReferenceImageInput:
    """One explicit reference image for a conditioned provider request."""

    filename: str
    content_type: str
    payload: bytes


def _get_ssl_context() -> ssl.SSLContext:
    """Verified SSL context using certifi CA bundle (CERT_REQUIRED)."""
    try:
        import certifi
    except ImportError as exc:  # pragma: no cover - defensive
        raise ProviderInputConfigurationError(
            "certifi is required for verified image provider TLS"
        ) from exc
    return ssl.create_default_context(cafile=certifi.where())


def _coerce_timeout(timeout_s: float) -> float:
    try:
        value = float(timeout_s)
    except (TypeError, ValueError) as exc:
        raise ProviderInputConfigurationError(
            f"invalid image provider timeout: {timeout_s!r}"
        ) from exc
    if value <= 0:
        raise ProviderInputConfigurationError(
            f"image provider timeout must be > 0: {timeout_s!r}"
        )
    return value


def _build_multipart(
    boundary: str,
    *,
    model: str,
    prompt: str,
    n: int,
    size: str,
    quality: str,
    images: Sequence[ReferenceImageInput],
) -> bytes:
    """Build a multipart/form-data body with repeated ``image[]`` file parts."""
    lines: list[bytes] = []
    crlf = b"\r\n"

    def field(name: str, value: str) -> None:
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        )
        lines.append(b"")
        lines.append(value.encode("utf-8"))

    field("model", model)
    field("prompt", prompt)
    field("n", str(n))
    field("size", size)
    field("quality", quality)

    for img in images:
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="image[]"; '
            f'filename="{img.filename}"'.encode("utf-8")
        )
        lines.append(f"Content-Type: {img.content_type}".encode("utf-8"))
        lines.append(b"")
        lines.append(img.payload)

    lines.append(f"--{boundary}--".encode("utf-8"))
    return crlf.join(lines) + crlf


def _decode_image_result(data: dict[str, Any], *, model: str) -> ConditionedImage:
    items = data.get("data")
    if not isinstance(items, list) or len(items) != 1:
        raise ProviderInputResultError(
            "image provider returned no single image result"
        )
    item = items[0]
    if not isinstance(item, dict):
        raise ProviderInputResultError("image provider result entry is invalid")

    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        try:
            payload = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ProviderInputResultError(
                "image provider returned invalid base64 image data"
            ) from exc
        if not payload:
            raise ProviderInputResultError("image provider returned empty image data")
        return ConditionedImage(
            payload=payload,
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            content_type="image/png",
            model=model,
        )

    if item.get("url"):
        raise ProviderInputResultError(
            "image provider returned a URL result; the C3 boundary refuses to "
            "perform the required second fetch"
        )

    raise ProviderInputResultError(
        "image provider returned no decodable image payload"
    )


def generate_conditioned_image(
    prompt: str,
    *,
    model: str,
    reference_images: Sequence[ReferenceImageInput],
    api_key: str | None = None,
    base_url: str | None = None,
    size: str = "1024x1024",
    quality: str = "low",
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ConditionedImage:
    """Perform exactly one reference-conditioned image edit call.

    Never retries; never performs a second fetch; prompt is sent verbatim.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ProviderInputConfigurationError("prompt must be a non-empty string")

    selected_model = (model or "").strip()
    if not selected_model:
        raise ProviderInputConfigurationError(
            "model is required; the conditioned provider boundary must be given "
            "an explicit runtime model identifier"
        )

    selected_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if not selected_key or not selected_key.strip():
        raise ProviderInputConfigurationError(
            "OPENAI_API_KEY is required for reference-conditioned image generation"
        )

    images = list(reference_images)
    if not images:
        raise ProviderInputConfigurationError(
            "at least one reference image is required for reference conditioning"
        )
    for img in images:
        if not isinstance(img.payload, bytes) or len(img.payload) == 0:
            raise ProviderInputConfigurationError(
                "reference image payload must be non-empty bytes"
            )

    selected_base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    timeout_value = _coerce_timeout(timeout_s)

    boundary = "----vne-c3-" + hashlib.sha256(
        json.dumps(
            {
                "model": selected_model,
                "prompt": prompt,
                "n": len(images),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    body = _build_multipart(
        boundary,
        model=selected_model,
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
        images=images,
    )

    request = urllib.request.Request(
        f"{selected_base}{EDIT_ENDPOINT_PATH}",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "Authorization": f"Bearer {selected_key.strip()}",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_value,
            context=_get_ssl_context(),
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderInputTransportError(
            f"image provider HTTP {exc.code}: {detail[:300]}"
        ) from None
    except urllib.error.URLError as exc:
        raise ProviderInputTransportError(
            f"image provider connection failed: {exc.reason}"
        ) from None
    except TimeoutError as exc:
        raise ProviderInputTransportError("image provider connection timed out") from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderInputTransportError(
            f"image provider returned invalid JSON: {exc}"
        ) from None

    if not isinstance(data, dict):
        raise ProviderInputTransportError(
            "image provider response must be a JSON object"
        )

    return _decode_image_result(data, model=selected_model)


def reference_inputs_from_set(
    reference_set: VisualReferenceSet,
) -> list[ReferenceImageInput]:
    """Read the selected reference bytes (READ ONLY) into provider inputs.

    Uses the operational ``source_path`` stored on each reference. The files
    are never modified, copied into the repo, or re-encoded.
    """
    inputs: list[ReferenceImageInput] = []
    for ref in reference_set.references:
        source_path = ref.source_path
        if not source_path:
            raise ProviderInputConfigurationError(
                f"reference {ref.reference_id!r} has no operational source path"
            )
        full = Path(source_path)
        if not full.exists():
            raise ProviderInputConfigurationError(
                f"reference file missing: {source_path}"
            )
        payload = full.read_bytes()
        content_type = _FORMAT_TO_CONTENT_TYPE.get(
            ref.image_format, "image/png"
        )
        inputs.append(
            ReferenceImageInput(
                filename=full.name,
                content_type=content_type,
                payload=payload,
            )
        )
    return inputs