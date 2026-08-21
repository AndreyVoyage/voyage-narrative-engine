#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-call image generation transport for Image Provider Boundary v0 (C1).

This module performs EXACTLY ONE HTTP request per ``generate_image`` call and
never retries, never falls back, and never issues a second generation. The
target is the OpenAI-compatible Images endpoint (provider ratified for C1).

Safety contract implemented here:
- The credential (OPENAI_API_KEY) and model are required BEFORE any network
  access; their absence raises ImageProviderConfigurationError with zero
  network I/O.
- The single request is a POST to {base_url}/v1/images/generations with
  ``n=1`` and the explicit model identifier.
- The response must be a single object with either a base64 ``b64_json``
  (decoded ONCE) or a ``url``. A URL result is REFUSED, because following it
  would require a SECOND explicit provider/network fetch, which C1 forbids.
- No retry loop exists anywhere in the call path.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

from .errors import (
    ImageProviderConfigurationError,
    ImageProviderResultError,
    ImageProviderTransportError,
)
from .model import GeneratedImage

DEFAULT_BASE_URL = "https://api.openai.com"
DEFAULT_TIMEOUT_S = 300.0
API_ENDPOINT_PATH = "/v1/images/generations"


def _get_ssl_context() -> ssl.SSLContext:
    """Verified SSL context using certifi CA bundle.

    Mirrors the established tools/llm_provider.py convention: certifi-backed
    CERT_REQUIRED context so embedded runtimes never silently downgrade TLS.
    If certifi is unavailable, raise (do not fall back to insecure).
    """
    try:
        import certifi
    except ImportError as exc:  # pragma: no cover - defensive
        raise ImageProviderConfigurationError(
            "certifi is required for verified image provider TLS"
        ) from exc
    return ssl.create_default_context(cafile=certifi.where())


def _coerce_timeout(timeout_s: float) -> float:
    try:
        value = float(timeout_s)
    except (TypeError, ValueError) as exc:
        raise ImageProviderConfigurationError(
            f"Invalid image provider timeout: {timeout_s!r}"
        ) from exc
    if value <= 0:
        raise ImageProviderConfigurationError(
            f"Image provider timeout must be > 0: {timeout_s!r}"
        )
    return value


def generate_image(
    prompt: str,
    *,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    size: str = "1024x1024",
    quality: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> GeneratedImage:
    """Perform exactly one image-generation call and return its bytes.

    Returns the single generated image. Never retries; never requests a
    second image; never performs a follow-up download.

    Raises:
      ImageProviderConfigurationError: missing model/credential BEFORE network.
      ImageProviderTransportError: HTTP/connection/JSON failure (terminal).
      ImageProviderResultError: response has no single decodable image.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ImageProviderConfigurationError("prompt must be a non-empty string")

    selected_model = (model or "").strip()
    if not selected_model:
        raise ImageProviderConfigurationError(
            "model is required; the image provider boundary must be given an "
            "explicit runtime model identifier"
        )

    selected_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if not selected_key or not selected_key.strip():
        raise ImageProviderConfigurationError(
            "OPENAI_API_KEY is required for image generation"
        )

    selected_base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    timeout_value = _coerce_timeout(timeout_s)

    payload: dict[str, Any] = {
        "model": selected_model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if quality:
        payload["quality"] = quality

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{selected_base}{API_ENDPOINT_PATH}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {selected_key.strip()}",
        },
    )

    # EXACTLY ONE network call. There is no retry loop anywhere here.
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_value,
            context=_get_ssl_context(),
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ImageProviderTransportError(
            f"image provider HTTP {exc.code}: {detail[:300]}"
        ) from None
    except urllib.error.URLError as exc:
        raise ImageProviderTransportError(
            f"image provider connection failed: {exc.reason}"
        ) from None
    except TimeoutError as exc:
        raise ImageProviderTransportError("image provider connection timed out") from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImageProviderTransportError(
            f"image provider returned invalid JSON: {exc}"
        ) from None

    if not isinstance(data, dict):
        raise ImageProviderTransportError(
            "image provider response must be a JSON object"
        )

    # C1 requires a single, in-band image result. A base64 payload is decoded
    # once. A URL result is REFUSED (would require a second fetch). A missing
    # result is a terminal result error.
    return _decode_image_result(data, model=selected_model)


def _decode_image_result(data: dict[str, Any], *, model: str) -> GeneratedImage:
    items = data.get("data")
    if not isinstance(items, list) or len(items) != 1:
        raise ImageProviderResultError(
            "image provider returned no single image result"
        )

    item = items[0]
    if not isinstance(item, dict):
        raise ImageProviderResultError("image provider result entry is invalid")

    b64 = item.get("b64_json")
    if isinstance(b64, str) and b64:
        try:
            payload = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageProviderResultError(
                "image provider returned invalid base64 image data"
            ) from exc
        if not payload:
            raise ImageProviderResultError("image provider returned empty image data")
        return GeneratedImage.from_bytes(
            payload=payload,
            content_type="image/png",
            model=model,
        )

    if item.get("url"):
        raise ImageProviderResultError(
            "image provider returned a URL result; the C1 boundary refuses to "
            "perform the required second fetch"
        )

    raise ImageProviderResultError(
        "image provider returned no decodable image payload"
    )