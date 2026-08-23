#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for Image Provider Boundary v0 (C1).

Deterministic, hermetic, and fully offline:

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0

All HTTP behavior is exercised by monkeypatching ``urllib.request.urlopen``
with an in-memory fake. No TLS handshake, no credential value read, no media
generation. These tests verify the single-call / no-retry / no-fallback
contract and the binary decode path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.error
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.image_provider_boundary import (  # noqa: E402
    ImageProviderConfigurationError,
    ImageProviderResultError,
    ImageProviderTransportError,
    SUPPORTED_IMAGE_CONTENT_TYPES,
    GeneratedImage,
    generate_image,
)

_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures" / "image_provider_boundary"
if str(_FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIXTURES_DIR))

from png_fixtures import MINIMAL_PNG_BYTES  # noqa: E402

_MODEL = "gpt-image-test-model"
_PROMPT = "KIRA находится в yoga_hall и разминается на беговой дорожке."


class _FakeResponse:
    def __init__(self, raw: bytes):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._raw


def _b64_success(byte_payload: bytes = MINIMAL_PNG_BYTES) -> bytes:
    return json.dumps(
        {"data": [{"b64_json": base64.b64encode(byte_payload).decode("ascii")}]}
    ).encode("utf-8")


def _patch_transport(monkeypatch, raw: bytes):
    """Replace TLS + HTTP with fully offline fakes. Returns a calls counter."""
    calls: list[object] = []

    monkeypatch.setattr(
        "services.image_provider_boundary.client._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request)
        return _FakeResponse(raw)

    monkeypatch.setattr(
        "services.image_provider_boundary.client.urllib.request.urlopen",
        fake_urlopen,
    )
    return calls


@pytest.fixture
def no_env_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_missing_model_raises_before_network(monkeypatch):
    """A missing model is a configuration error with zero network I/O."""
    calls: list[object] = []

    monkeypatch.setattr(
        "services.image_provider_boundary.client._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(*a, **k):
        calls.append(a)
        raise AssertionError("urlopen must not be called when model is missing")

    monkeypatch.setattr(
        "services.image_provider_boundary.client.urllib.request.urlopen",
        fake_urlopen,
    )

    with pytest.raises(ImageProviderConfigurationError):
        generate_image(_PROMPT, model="   ", api_key="sk-test")
    assert calls == []


def test_missing_api_key_raises_before_network(monkeypatch, no_env_key):
    """A missing credential raises before any network I/O."""
    calls: list[object] = []

    monkeypatch.setattr(
        "services.image_provider_boundary.client._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(*a, **k):
        calls.append(a)
        raise AssertionError("urlopen must not be called when key is missing")

    monkeypatch.setattr(
        "services.image_provider_boundary.client.urllib.request.urlopen",
        fake_urlopen,
    )

    with pytest.raises(ImageProviderConfigurationError):
        generate_image(_PROMPT, model=_MODEL)
    assert calls == []


def test_successful_decode_and_hash(monkeypatch):
    calls = _patch_transport(monkeypatch, _b64_success())

    result = generate_image(
        _PROMPT,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )

    assert len(calls) == 1
    assert isinstance(result, GeneratedImage)
    assert result.payload == MINIMAL_PNG_BYTES
    assert result.payload_sha256 == hashlib.sha256(MINIMAL_PNG_BYTES).hexdigest()
    assert result.model == _MODEL
    assert result.content_type == "image/png"


def test_single_call_and_request_shape(monkeypatch):
    """Prove exactly ONE call with n=1 and the explicit model, correct endpoint."""
    calls = _patch_transport(monkeypatch, _b64_success())

    generate_image(
        _PROMPT,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )

    assert len(calls) == 1
    request = calls[0]
    assert request.method == "POST"
    assert request.full_url == "https://api.example.invalid/v1/images/generations"

    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == _MODEL
    assert body["prompt"] == _PROMPT
    assert body["n"] == 1

    # Authorization present but the value is never echoed back by this test.
    auth = request.get_header("Authorization")
    assert auth is not None and auth.startswith("Bearer ")


def test_live_smoke_request_forces_explicit_low_quality(monkeypatch):
    """The owner-ratified C1 smoke request must send quality == 'low' exactly."""
    calls = _patch_transport(monkeypatch, _b64_success())

    generate_image(
        _PROMPT,
        model=_MODEL,
        api_key="sk-test",
        base_url="https://api.example.invalid",
        quality="low",
    )

    assert len(calls) == 1
    body = json.loads(calls[0].data.decode("utf-8"))
    assert body["quality"] == "low"
    assert body["size"] == "1024x1024"
    assert body["n"] == 1
    assert body["model"] == _MODEL
    assert body["prompt"] == _PROMPT


def test_url_result_is_refused_no_second_fetch(monkeypatch):
    """A URL result would require a second fetch; the boundary refuses it."""
    raw = json.dumps({"data": [{"url": "https://example.invalid/image.png"}]}).encode("utf-8")
    calls = _patch_transport(monkeypatch, raw)

    with pytest.raises(ImageProviderResultError):
        generate_image(_PROMPT, model=_MODEL, api_key="sk-test")

    # Exactly one transport call; no follow-up download was attempted.
    assert len(calls) == 1


def test_invalid_base64_raises_result_error(monkeypatch):
    raw = json.dumps({"data": [{"b64_json": "!!!not-base64!!!"}]}).encode("utf-8")
    calls = _patch_transport(monkeypatch, raw)

    with pytest.raises(ImageProviderResultError):
        generate_image(_PROMPT, model=_MODEL, api_key="sk-test")
    assert len(calls) == 1


def test_missing_data_field_raises_result_error(monkeypatch):
    raw = json.dumps({"data": []}).encode("utf-8")
    calls = _patch_transport(monkeypatch, raw)

    with pytest.raises(ImageProviderResultError):
        generate_image(_PROMPT, model=_MODEL, api_key="sk-test")
    assert len(calls) == 1


def test_http_error_is_terminal_no_retry(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(
        "services.image_provider_boundary.client._get_ssl_context",
        lambda: None,
    )

    def raise_http(request, timeout=None, context=None):
        calls.append(request)
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", {}, io_bytes()
        )

    monkeypatch.setattr(
        "services.image_provider_boundary.client.urllib.request.urlopen",
        raise_http,
    )

    with pytest.raises(ImageProviderTransportError):
        generate_image(_PROMPT, model=_MODEL, api_key="sk-test")

    # Terminal: exactly one attempt, no retry.
    assert len(calls) == 1


def test_invalid_json_is_transport_error(monkeypatch):
    calls = _patch_transport(monkeypatch, b"{not json")
    with pytest.raises(ImageProviderTransportError):
        generate_image(_PROMPT, model=_MODEL, api_key="sk-test")
    assert len(calls) == 1


def test_model_result_is_immutable_and_does_not_leak_bytes():
    image = GeneratedImage.from_bytes(
        payload=MINIMAL_PNG_BYTES,
        content_type="image/png",
        model=_MODEL,
    )
    with pytest.raises(Exception):
        image.payload = b"mutate"  # frozen dataclass rejects assignment

    summary = image.to_dict()
    assert "payload" not in summary
    assert summary["payload_byte_length"] == len(MINIMAL_PNG_BYTES)
    assert "payload_sha256" in summary


def test_supported_content_types_include_png_jpeg_webp():
    assert SUPPORTED_IMAGE_CONTENT_TYPES == ("image/png", "image/jpeg", "image/webp")


def io_bytes() -> "object":
    import io

    return io.BytesIO(b'{"error":{"message":"unauthorized"}}')