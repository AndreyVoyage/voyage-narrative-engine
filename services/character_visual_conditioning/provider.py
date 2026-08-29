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

from .bundle import validate_reference_bundle_integrity
from .errors import (
    ProviderInputConfigurationError,
    ProviderInputResultError,
    ProviderInputTransportError,
)
from .model import ConditionedImage, ReferenceBundle, VisualReferenceSet

DEFAULT_BASE_URL = "https://api.openai.com"
DEFAULT_TIMEOUT_S = 300.0
EDIT_ENDPOINT_PATH = "/v1/images/edits"

_FORMAT_TO_CONTENT_TYPE = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

_CONTENT_TYPE_TO_EXTENSION = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
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


# ---------------------------------------------------------------------------
# Generic bundle attachment (RC3): consume ReferenceBundle directly.
# ---------------------------------------------------------------------------

REFERENCE_MAP_HEADER = "[REFERENCE MAP]"


def _sanitize_filename_token(value: str) -> str:
    """Return a deterministic, filename-safe token for a character id."""
    chars: list[str] = []
    for ch in value:
        if ch.isascii() and (ch.isalnum() or ch in "_-"):
            chars.append(ch)
        else:
            chars.append("_")
    token = "".join(chars)
    return token or "char"


def _content_type_to_extension(content_type: str) -> str:
    return _CONTENT_TYPE_TO_EXTENSION.get(content_type, "bin")


def _build_provider_filename(index: int, character_id: str, content_type: str) -> str:
    """Deterministic, generic multipart filename bound to index + character."""
    ext = _content_type_to_extension(content_type)
    return f"ref_{index:03d}_{_sanitize_filename_token(character_id)}.{ext}"


def _iter_bundle_attachments(reference_bundle: ReferenceBundle):
    """Yield ``(attachment_index, group, entry)`` in bundle order."""
    index = 0
    for group in reference_bundle.character_groups:
        for entry in group.references:
            yield index, group, entry
            index += 1


def _validate_bundle_has_attachments(reference_bundle: ReferenceBundle) -> None:
    """Fail closed before any request construction on an unusable bundle."""
    validate_reference_bundle_integrity(reference_bundle)
    groups = list(reference_bundle.character_groups)
    if not groups:
        raise ProviderInputConfigurationError(
            "reference bundle has no character groups"
        )
    for group in groups:
        if not group.references:
            raise ProviderInputConfigurationError(
                f"character group {group.character_id!r} has no reference entries"
            )


def _flatten_bundle(
    reference_bundle: ReferenceBundle,
) -> tuple[list[ReferenceImageInput], str]:
    """Flatten a ReferenceBundle into ordered inputs + a deterministic reference map.

    Returns ``(inputs, reference_map_text)``. Flattening is transport-only; it
    never loses character ownership or role metadata.
    """
    _validate_bundle_has_attachments(reference_bundle)

    inputs: list[ReferenceImageInput] = []
    map_lines: list[str] = [REFERENCE_MAP_HEADER]

    for index, group, entry in _iter_bundle_attachments(reference_bundle):
        label = (
            group.prompt_alias
            if group.prompt_alias is not None
            else group.character_id
        )
        filename = _build_provider_filename(index, label, entry.content_type)
        inputs.append(
            ReferenceImageInput(
                filename=filename,
                content_type=entry.content_type,
                payload=entry.payload,
            )
        )
        map_lines.append(f"image[{index}]:")
        map_lines.append(f"character_id={label}")
        map_lines.append(f"roles={','.join(entry.roles)}")
        if group.prompt_alias is not None:
            # Alias-safe source: expose the already-generated safe multipart
            # attachment filename only. Never the asset basename (which may
            # embed the raw internal character id) and never the internal
            # character directory.
            map_lines.append(f"source={filename}")
        else:
            map_lines.append(f"source={entry.path}")
        map_lines.append("")

    reference_map = "\n".join(map_lines).rstrip("\n")
    return inputs, reference_map


def reference_inputs_from_bundle(
    reference_bundle: ReferenceBundle,
) -> list[ReferenceImageInput]:
    """Return ordered provider image inputs from a ReferenceBundle.

    Uses ``entry.payload`` bytes directly; never reopens Canon files.
    """
    inputs, _ = _flatten_bundle(reference_bundle)
    return inputs


def build_reference_map(reference_bundle: ReferenceBundle) -> str:
    """Return the deterministic reference map for a ReferenceBundle."""
    _, reference_map = _flatten_bundle(reference_bundle)
    return reference_map


def _compose_effective_prompt(original_prompt: str, reference_map: str) -> str:
    """Append the provider reference map to the original prompt.

    The original prompt is never mutated (Python strings are immutable).
    """
    return f"{original_prompt}\n\n{reference_map}"


def generate_conditioned_image_from_bundle(
    *,
    prompt: str,
    reference_bundle: ReferenceBundle,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    size: str = "1024x1024",
    quality: str = "low",
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ConditionedImage:
    """Perform one reference-conditioned image edit from a ReferenceBundle.

    The ReferenceBundle is authoritative for all attached character refs.
    Actual bundle payload bytes are attached (no file reopen, no Canon reread).
    A deterministic reference map is appended to the provider-bound effective
    prompt only; the upstream prompt is untouched.
    """
    if not prompt or not prompt.strip():
        raise ProviderInputConfigurationError("prompt must be a non-empty string")

    inputs, reference_map = _flatten_bundle(reference_bundle)
    effective_prompt = _compose_effective_prompt(prompt, reference_map)

    return generate_conditioned_image(
        effective_prompt,
        model=model,
        reference_images=inputs,
        api_key=api_key,
        base_url=base_url,
        size=size,
        quality=quality,
        timeout_s=timeout_s,
    )
