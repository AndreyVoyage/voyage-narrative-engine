#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMAGE_GENERATION provider adapter + existing ImageJobService integration (Slice C).

Offline. No socket, no live provider, no real DPAPI vault, no real API key, no
real Companion data root, no Character Canon. The single provider transport is
an injected in-process callable that captures the request and returns a
deterministic fake response.

HARD SAFETY GATES proved here:
  * one job generation attempt -> at most ONE provider transport call
  * no retry, no fallback, no URL second-fetch
  * config / capability failures raise BEFORE any transport call (0 calls)
"""

from __future__ import annotations

import base64
import io
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import pytest

from services.character_companion.character_import import CharacterImportService
from services.character_companion.credentials import InMemoryCredentialVault
from services.character_companion.image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    ImageJob,
    ImageJobService,
)
from services.character_companion.provider_registry import ROLE_IMAGE_GENERATION
from services.character_companion.settings import CompanionSettings, RoleAssignment
from services.character_companion.visual import (
    GeneratedImage,
    ImageGenerationConfigurationError,
    ImageGenerationRequest,
    ImageGenerationResultError,
    ImageGenerationTransportError,
    ImageGenerationUnsupportedProviderError,
    ImageProviderAdapter,
    RealCompanionImageGenerator,
    ReferenceImageInput,
    build_reference_bundle,
    generate_conditioned_image,
    generate_text_to_image,
)
from services.character_companion.provider_resolution import resolve_role_config


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("network access is forbidden in image provider tests")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


# ============================================================ fixtures
def _png(pad: int = 32) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * pad


def _jpeg(pad: int = 32) -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * pad


def _webp(pad: int = 24) -> bytes:
    return b"RIFF" + b"\x2c\x00\x00\x00" + b"WEBP" + b"\x00" * pad


_RESULT_PNG = _png(64)


def _fake_ok_response(payload: bytes = _RESULT_PNG) -> dict:
    return {"data": [{"b64_json": base64.b64encode(payload).decode("ascii")}]}


class FakeImageHttp:
    """Injected transport seam. Captures every call; never opens a socket."""

    def __init__(self, response=None, raises: Optional[BaseException] = None) -> None:
        self.calls: list[dict] = []
        self._response = response if response is not None else _fake_ok_response()
        self._raises = raises

    def __call__(self, url: str, body: bytes, headers: dict, timeout_s: float):
        self.calls.append(
            {"url": url, "body": body, "headers": dict(headers), "timeout_s": timeout_s}
        )
        if self._raises is not None:
            raise self._raises
        return self._response


class StubSettingsStore:
    def __init__(self, settings: CompanionSettings) -> None:
        self._settings = settings

    def load(self) -> CompanionSettings:
        return self._settings


def _image_settings(
    *, provider="openai", model="gpt-image-1", base_url="https://images.test.invalid"
) -> CompanionSettings:
    s = CompanionSettings(roles={ROLE_IMAGE_GENERATION: RoleAssignment(provider, model)})
    s.base_urls[provider] = base_url
    return s


def _vault_with_key(provider="openai", key="test-key-not-real") -> InMemoryCredentialVault:
    v = InMemoryCredentialVault()
    v.store(provider, key)
    return v


def _make_canon(tmp_path: Path, character_id: str = "kira") -> Path:
    root = tmp_path / "fake-canon"
    gen_rel = f"AI_CHARACTERS/{character_id}/07_generated"
    preset = {
        "character": character_id,
        "status": "APPROVED_AS_CANON",
        "active_canon": {
            "primary_face_reference": f"{gen_rel}/face.png",
            "body_canon_a": f"{gen_rel}/body_a.jpg",
            "body_canon_b": f"{gen_rel}/body_b.jpg",
            "expression_canon": f"{gen_rel}/expr.webp",
        },
        "identity_summary": {
            "role": "female",
            "height_cm": 168,
            "height_direction": "athletic and slender",
            "body_direction": "athletic build",
            "face_direction": "oval face",
            "hair_direction": "shoulder-length wavy hair",
            "style_direction": "casual modern",
        },
        "identity_confirmed_traits": ["green eyes"],
        "safety_rules": ["adults only; no minors"],
    }
    notes = root / "AI_CHARACTERS" / character_id / "10_notes"
    notes.mkdir(parents=True)
    (notes / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    gen = root / "AI_CHARACTERS" / character_id / "07_generated"
    gen.mkdir(parents=True)
    (gen / "face.png").write_bytes(_png(10))
    (gen / "body_a.jpg").write_bytes(_jpeg(20))
    (gen / "body_b.jpg").write_bytes(_jpeg(30))
    (gen / "expr.webp").write_bytes(_webp(16))
    return root


def _seed_snapshot(data_root: Path, tmp_path: Path, character_id: str = "kira") -> None:
    CharacterImportService(data_root).import_character(_make_canon(tmp_path, character_id), character_id, "add")


def _bundle(data_root: Path, character_id: str = "kira"):
    from services.character_companion.character_import.local_snapshot import SnapshotStore

    store = SnapshotStore(data_root)
    snap = store.load_active_snapshot(character_id)
    sdir = store.version_dir(character_id, snap.snapshot_version)
    return build_reference_bundle(snapshot=snap, snapshot_dir=sdir)


def _role_config(settings: CompanionSettings, vault) -> dict:
    return resolve_role_config(ROLE_IMAGE_GENERATION, settings, vault)


def _request(*, provider="openai", model="gpt-image-1", kind="conditioned", prompt="PROMPT TEXT") -> ImageGenerationRequest:
    return ImageGenerationRequest(
        character_id="kira",
        character_snapshot_version="v1",
        prompt_text=prompt,
        provider_id=provider,
        model_id=model,
        endpoint_kind=kind,
    )


# ============================================ low-level transport (32, 25/26/27)
def test_pure_text_transport_one_call_correct_shape():
    http = FakeImageHttp()
    img = generate_text_to_image(
        prompt="a quiet evening portrait",
        model="gpt-image-1",
        api_key="test-key-not-real",
        base_url="https://images.test.invalid",
        size="1024x1024",
        http_post=http,
    )
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == "https://images.test.invalid/v1/images/generations"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["Authorization"] == "Bearer test-key-not-real"
    payload = json.loads(call["body"].decode("utf-8"))
    assert payload == {"model": "gpt-image-1", "prompt": "a quiet evening portrait", "n": 1, "size": "1024x1024"}
    assert isinstance(img, GeneratedImage)
    assert img.payload == _RESULT_PNG
    assert img.payload_sha256 == GeneratedImage.from_bytes(
        payload=_RESULT_PNG, content_type="image/png", model="x"
    ).payload_sha256
    assert img.content_type == "image/png"


def test_pure_text_transport_requires_credential_before_network():
    http = FakeImageHttp()
    with pytest.raises(ImageGenerationConfigurationError):
        generate_text_to_image(
            prompt="p", model="gpt-image-1", api_key="  ", base_url="https://x.invalid", http_post=http
        )
    assert http.calls == []


def test_conditioned_transport_multipart_semantic_parts(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    bundle = _bundle(data_root)
    inputs = [
        ReferenceImageInput(filename=f"ref_{i:03d}_kira.png", content_type=e.content_type, payload=e.payload)
        for i, e in enumerate(bundle.references)
    ]
    http = FakeImageHttp()
    generate_conditioned_image(
        prompt="PROMPT VERBATIM",
        model="gpt-image-1",
        api_key="test-key-not-real",
        base_url="https://images.test.invalid",
        references=inputs,
        http_post=http,
    )
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == "https://images.test.invalid/v1/images/edits"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert call["headers"]["Authorization"] == "Bearer test-key-not-real"
    body = call["body"]
    assert body.count(b'name="prompt"') == 1
    assert b"PROMPT VERBATIM" in body
    assert body.count(b'name="image[]"') == len(inputs)
    assert body.count(b'name="n"') == 1 and b"\r\n1\r\n" in body
    # every reference's exact bytes are attached, in bundle order
    last = -1
    for e in bundle.references:
        idx = body.find(e.payload)
        assert idx != -1 and idx > last
        last = idx


def test_url_only_result_is_refused_no_second_fetch():
    http = FakeImageHttp(response={"data": [{"url": "https://example.invalid/image.png"}]})
    with pytest.raises(ImageGenerationResultError):
        generate_text_to_image(
            prompt="p", model="gpt-image-1", api_key="k-not-real", base_url="https://x.invalid", http_post=http
        )
    assert len(http.calls) == 1  # the one attempt only; no follow-up fetch


def test_zero_and_many_results_rejected():
    for resp in ({"data": []}, {"data": [{"b64_json": "a"}, {"b64_json": "b"}]}, {"data": "nope"}):
        http = FakeImageHttp(response=resp)
        with pytest.raises(ImageGenerationResultError):
            generate_text_to_image(
                prompt="p", model="m", api_key="k-not-real", base_url="https://x.invalid", http_post=http
            )
        assert len(http.calls) == 1


def test_malformed_base64_rejected():
    http = FakeImageHttp(response={"data": [{"b64_json": "not!valid!base64!"}]})
    with pytest.raises(ImageGenerationResultError):
        generate_text_to_image(
            prompt="p", model="m", api_key="k-not-real", base_url="https://x.invalid", http_post=http
        )


def test_unrecognised_image_bytes_rejected():
    http = FakeImageHttp(response=_fake_ok_response(b"GIF89a not a supported format"))
    with pytest.raises(ImageGenerationResultError):
        generate_text_to_image(
            prompt="p", model="m", api_key="k-not-real", base_url="https://x.invalid", http_post=http
        )


def test_transport_http_failure_is_terminal_no_retry():
    http = FakeImageHttp(raises=ImageGenerationTransportError("boom"))
    with pytest.raises(ImageGenerationTransportError):
        generate_text_to_image(
            prompt="p", model="m", api_key="k-not-real", base_url="https://x.invalid", http_post=http
        )
    assert len(http.calls) == 1


def _http_error_response(monkeypatch, raw, *, status=400):
    calls = []
    reads = []

    class BoundedBody(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            assert 0 < size <= 16_385
            return super().read(size)

    def urlopen(request, *, timeout):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(
            request.full_url, status, "untrusted HTTP reason", {}, BoundedBody(raw)
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls, reads


def _capture_http_failure():
    with pytest.raises(ImageGenerationTransportError) as caught:
        generate_text_to_image(
            prompt="private request prompt", model="gpt-image-1", api_key="test-key-not-real",
            base_url="https://images.test.invalid",
        )
    return caught.value


def test_http_json_error_preserves_allowlisted_diagnostic(monkeypatch):
    raw = json.dumps({"error": {
        "message": "Organization verification required.\n Try the dashboard.",
        "type": "invalid_request_error", "code": "organization_unverified",
        "request": "private request body", "headers": {"Authorization": "Bearer test-key-not-real"},
    }, "debug": "must never be retained"}).encode()
    calls, reads = _http_error_response(monkeypatch, raw)
    exc = _capture_http_failure()
    assert exc.code == "image_generation_transport_failed"
    assert exc.diagnostic.to_dict() == {
        "httpStatus": 400, "providerErrorCode": "organization_unverified",
        "providerErrorType": "invalid_request_error",
        "providerMessage": "Organization verification required. Try the dashboard.",
    }
    assert len(calls) == 1 and reads == [16_385]
    exposed = repr(exc) + str(exc) + repr(exc.diagnostic) + json.dumps(exc.diagnostic.to_dict())
    for forbidden in ("test-key-not-real", "Authorization", "private request body", "debug"):
        assert forbidden not in exposed


@pytest.mark.parametrize("raw", [
    b"<html>Authorization: Bearer test-key-not-real</html>" * 1000,
    b'{"error":', b'[]', b'{"error":"not an object"}',
    b'{"error":{"message":"' + b"x" * 20_000 + b'"}}',
    b'{"error":{"message":"\xff"}}',
], ids=["html", "truncated-json", "array", "scalar-error", "oversized-json", "invalid-utf8"])
def test_http_unparseable_error_retains_status_only(monkeypatch, raw):
    calls, _ = _http_error_response(monkeypatch, raw, status=502)
    exc = _capture_http_failure()
    assert exc.diagnostic.to_dict() == {"httpStatus": 502}
    assert str(exc) == "image provider HTTP request failed"
    assert len(calls) == 1


@pytest.mark.parametrize("unsafe", [
    "test-key-not-real", "Authorization: Bearer test-key-not-real",
    "sk-other-credential-value", "API_KEY=another-value",
    r"Cannot read C:\Users\owner\private.png", "/home/owner/private.png",
    r"\\server\share\private.png", "data:image/png;base64,aGVsbG8=",
    base64.b64encode(_RESULT_PNG).decode(),
    base64.b64encode(_png(0)).decode(),
    'Content-Disposition: form-data; name="image[]"',
    "invalid\x00binary", "prompt: private request prompt",
], ids=["credential", "authorization", "key-token", "key-label", "windows-path", "unix-path",
        "unc-path", "data-url", "base64", "short-base64", "multipart", "binary", "request-echo"])
def test_http_diagnostic_withholds_sensitive_fields(monkeypatch, unsafe):
    raw = json.dumps({"error": {"message": unsafe, "code": unsafe, "type": unsafe}}).encode()
    _http_error_response(monkeypatch, raw)
    exc = _capture_http_failure()
    assert exc.diagnostic.to_dict() == {
        "httpStatus": 400, "providerMessage": "Provider error details withheld."
    }
    assert unsafe not in repr(exc) + str(exc) + repr(exc.diagnostic)


def test_http_diagnostic_bounds_message_and_ignores_nonstring_fields(monkeypatch):
    _http_error_response(monkeypatch, json.dumps({"error": {
        "message": "Temporary provider failure. " * 50,
        "code": {"secret": "test-key-not-real"}, "type": ["arbitrary", "data"],
    }}).encode())
    failure = _capture_http_failure().diagnostic.to_dict()
    assert set(failure) == {"httpStatus", "providerMessage"}
    assert len(failure["providerMessage"]) == 400


def test_http_authentication_error_keeps_code_but_withholds_key(monkeypatch):
    _http_error_response(monkeypatch, json.dumps({"error": {
        "code": "invalid_api_key", "type": "authentication_error",
        "message": "Incorrect API key provided: test-key-not-real",
    }}).encode(), status=401)
    assert _capture_http_failure().diagnostic.to_dict() == {
        "httpStatus": 401, "providerErrorCode": "invalid_api_key",
        "providerErrorType": "authentication_error", "providerMessage": "Provider error details withheld.",
    }


def test_non_http_transport_error_does_not_echo_reason(monkeypatch):
    def urlopen(*args, **kwargs):
        raise urllib.error.URLError("Authorization: Bearer test-key-not-real /private/path")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    exc = _capture_http_failure()
    assert str(exc) == "image provider unreachable"
    assert exc.diagnostic is None


# ============================================ adapter routing + capability gate
def test_adapter_routes_conditioned_when_bundle_present(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    bundle = _bundle(data_root)
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings, vault = _image_settings(), _vault_with_key()
    img = adapter.generate(
        request=_request(kind="conditioned"),
        reference_bundle=bundle,
        role_config=_role_config(settings, vault),
        base_url="https://images.test.invalid",
        api_key="test-key-not-real",
    )
    assert len(http.calls) == 1
    assert http.calls[0]["url"].endswith("/v1/images/edits")
    assert isinstance(img, GeneratedImage)


def test_adapter_routes_text_when_no_references(tmp_path):
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings, vault = _image_settings(), _vault_with_key()
    adapter.generate(
        request=_request(kind="text", prompt="freeform text prompt"),
        reference_bundle=None,
        role_config=_role_config(settings, vault),
        base_url="https://images.test.invalid",
        api_key="test-key-not-real",
    )
    assert len(http.calls) == 1
    assert http.calls[0]["url"].endswith("/v1/images/generations")


def test_adapter_prompt_is_request_prompt_text_exactly(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    bundle = _bundle(data_root)
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings, vault = _image_settings(), _vault_with_key()
    adapter.generate(
        request=_request(kind="conditioned", prompt="EXACT-PROMPT-marker-123"),
        reference_bundle=bundle,
        role_config=_role_config(settings, vault),
        base_url="https://images.test.invalid",
        api_key="test-key-not-real",
    )
    body = http.calls[0]["body"]
    assert b"EXACT-PROMPT-marker-123" in body


def test_adapter_rejects_unassigned_role_before_transport():
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings = CompanionSettings(roles={})  # nothing assigned
    vault = _vault_with_key()
    with pytest.raises(ImageGenerationConfigurationError):
        adapter.generate(
            request=_request(),
            reference_bundle=None,
            role_config=_role_config(settings, vault),
            base_url="https://x.invalid",
            api_key="test-key-not-real",
        )
    assert http.calls == []


def test_adapter_rejects_missing_credential_before_transport():
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings = _image_settings()
    vault = InMemoryCredentialVault()  # no key stored
    with pytest.raises(ImageGenerationConfigurationError):
        adapter.generate(
            request=_request(),
            reference_bundle=None,
            role_config=_role_config(settings, vault),
            base_url="https://x.invalid",
            api_key="",
        )
    assert http.calls == []


def test_adapter_rejects_model_without_image_generation_capability():
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings = _image_settings(model="gpt-4o-mini")  # DIALOGUE/VISION only
    vault = _vault_with_key()
    with pytest.raises(ImageGenerationUnsupportedProviderError):
        adapter.generate(
            request=_request(model="gpt-4o-mini"),
            reference_bundle=None,
            role_config=_role_config(settings, vault),
            base_url="https://x.invalid",
            api_key="test-key-not-real",
        )
    assert http.calls == []


def test_adapter_rejects_request_role_mismatch():
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings, vault = _image_settings(), _vault_with_key()
    with pytest.raises(ImageGenerationConfigurationError):
        adapter.generate(
            request=_request(model="some-other-model"),
            reference_bundle=None,
            role_config=_role_config(settings, vault),
            base_url="https://x.invalid",
            api_key="test-key-not-real",
        )
    assert http.calls == []


def test_adapter_conditioned_rejected_when_reference_capability_unsupported(tmp_path):
    """A CHARACTER_REFERENCE / IMAGE_TO_IMAGE-less IMAGE_GENERATION model must not
    receive image attachments. Uses a synthetic registry model via monkeypatch."""
    import services.character_companion.visual.image_provider_adapter as mod

    class _M:
        capabilities = ("IMAGE_GENERATION", "CLOUD")
        supports_reference_image = False
        supports_image_to_image = None

    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    bundle = _bundle(data_root)
    http = FakeImageHttp()
    adapter = ImageProviderAdapter(http_post=http)
    settings, vault = _image_settings(), _vault_with_key()
    rc = _role_config(settings, vault)

    orig = mod.require_model_supported
    mod.require_model_supported = lambda p, m, r: (object(), _M())
    try:
        with pytest.raises(ImageGenerationUnsupportedProviderError):
            adapter.generate(
                request=_request(kind="conditioned"),
                reference_bundle=bundle,
                role_config=rc,
                base_url="https://x.invalid",
                api_key="test-key-not-real",
            )
    finally:
        mod.require_model_supported = orig
    assert http.calls == []


# ============================================ RealCompanionImageGenerator + ImageJobService
def _generator(data_root: Path, http, *, settings=None, vault=None) -> RealCompanionImageGenerator:
    return RealCompanionImageGenerator(
        data_root=data_root,
        settings_store=StubSettingsStore(settings or _image_settings()),
        credential_vault=vault or _vault_with_key(),
        adapter=ImageProviderAdapter(http_post=http),
    )


def _job(data_root: Path, gen, *, kind=KIND_CUSTOM, prompt="Kira by a window in the evening", context=None):
    svc = ImageJobService(data_root, gen)
    job = svc.create_job(session_id="s1", character_id="kira", kind=kind, prompt=prompt, context=context)
    return svc, job


def test_job_queued_then_generating_no_provider_call_first_tick(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    assert job.state == STATE_QUEUED
    svc.tick()
    assert svc.get_job(job.job_id).state == STATE_GENERATING
    assert http.calls == []


def test_job_generating_to_ready_exactly_one_provider_call(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    svc.tick()  # -> GENERATING
    svc.tick()  # -> READY
    done = svc.get_job(job.job_id)
    assert done.state == STATE_READY
    assert len(http.calls) == 1
    assert http.calls[0]["url"].endswith("/v1/images/edits")  # KIRA has references
    assert done.result_ref == f"images/{job.job_id}.png"
    out = data_root / done.result_ref
    assert out.is_file() and out.read_bytes() == _RESULT_PNG
    assert svc.ready_results("s1") == (done.result_ref,)
    prov = done.context["result"]
    assert prov["provider"] == "openai" and prov["model"] == "gpt-image-1"
    assert prov["snapshotVersion"] == "v1"
    assert prov["payloadSha256"] == GeneratedImage.from_bytes(
        payload=_RESULT_PNG, content_type="image/png", model="x"
    ).payload_sha256


def test_job_ready_is_not_regenerated_on_further_ticks(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    assert svc.get_job(job.job_id).state == STATE_READY
    for _ in range(3):
        svc.tick()
    assert len(http.calls) == 1


def test_job_context_kind_uses_scene_and_recent_messages(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    context = {
        "characterId": "kira",
        "sessionId": "s1",
        "scene": {"place": "small kitchen", "time": "late evening", "mood": "quiet"},
        "recentMessages": [
            {"role": "user", "text": "тяжёлый день"},
            {"role": "character", "text": "я рядом"},
        ],
        "excerptLimit": 8,
    }
    svc, job = _job(data_root, _generator(data_root, http), kind=KIND_CONTEXT, prompt=None, context=context)
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_READY
    assert len(http.calls) == 1
    body = http.calls[0]["body"]
    assert "small kitchen".encode("utf-8") in body
    assert "тяжёлый день".encode("utf-8") in body


def test_job_failed_when_transport_raises_exactly_one_call_no_retry(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp(raises=ImageGenerationTransportError("provider exploded"))
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_transport_failed"
    assert done.result_ref is None
    assert not (data_root / "images" / f"{job.job_id}.png").exists()
    for _ in range(3):
        svc.tick()
    assert len(http.calls) == 1  # no automatic retry


@pytest.mark.parametrize("message, expected_message", [
    ("Organization verification required.", "Organization verification required."),
    ("Authorization: Bearer test-key-not-real", "Provider error details withheld."),
    ("Rejected: Kira by a window in the evening", "Provider error details withheld."),
], ids=["safe", "credential", "request-echo"])
def test_http_failure_is_persisted_without_mutating_source_context(tmp_path, monkeypatch, message, expected_message):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    calls, _ = _http_error_response(monkeypatch, json.dumps({"error": {
        "message": message, "type": "invalid_request_error", "code": "organization_unverified",
    }}).encode())
    source_context = {"scene": {"place": "quiet room"}, "marker": "preserve me"}
    original = json.loads(json.dumps(source_context))
    generator = _generator(data_root, None)
    svc, job = _job(data_root, generator, context=source_context)
    advance = generator.advance
    observed = []

    def observe_advance(job, **kwargs):
        updated = advance(job, **kwargs)
        if updated.state == STATE_FAILED:
            observed.append(updated)
            assert updated.context is not job.context
            assert job.context == original
        return updated

    monkeypatch.setattr(generator, "advance", observe_advance)
    svc.run_to_completion(job.job_id)
    failed = observed[0]
    assert source_context == original
    assert failed.state == STATE_FAILED
    assert failed.error == "image_generation_transport_failed"
    assert failed.context["scene"] == original["scene"]
    assert failed.context["marker"] == "preserve me"
    assert failed.context["failure"] == {
        "provider": "openai", "model": "gpt-image-1", "httpStatus": 400,
        "providerErrorCode": "organization_unverified", "providerErrorType": "invalid_request_error",
        "providerMessage": expected_message,
    }
    persisted = svc.get_job(job.job_id)
    assert persisted.to_row() == failed.to_row()
    serialized = (data_root / "companion_image_jobs.json").read_text(encoding="utf-8")
    for forbidden in ("test-key-not-real", "Authorization", "Bearer", "multipart", "base64"):
        assert forbidden not in serialized
    assert persisted.result_ref is None
    assert not (data_root / "images").exists()
    svc.tick()
    assert len(calls) == 1


def test_job_failed_when_result_is_url_only(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp(response={"data": [{"url": "https://example.invalid/x.png"}]})
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_result_invalid"
    assert len(http.calls) == 1


def test_job_failed_when_no_active_snapshot_before_provider(tmp_path):
    data_root = tmp_path / "data"       # nothing seeded -> no snapshot
    (data_root).mkdir(parents=True)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_active_snapshot_missing"
    assert http.calls == []


def test_job_failed_when_role_unassigned_before_provider(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    gen = _generator(data_root, http, settings=CompanionSettings(roles={}))
    svc, job = _job(data_root, gen)
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_role_unassigned"
    assert http.calls == []


def test_job_failed_when_credential_missing_before_provider(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    gen = _generator(data_root, http, vault=InMemoryCredentialVault())
    svc, job = _job(data_root, gen)
    svc.run_to_completion(job.job_id)
    done = svc.get_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_credential_missing"
    assert http.calls == []


def test_default_image_job_service_generator_is_unavailable(tmp_path):
    """Slice C must NOT change the safe release default."""
    from services.character_companion.image_jobs import UnavailableImageGenerator

    svc = ImageJobService(tmp_path / "data")
    assert isinstance(svc._generator, UnavailableImageGenerator)
    assert svc.generator_name == "unavailable"


def test_generated_prompt_and_multipart_carry_no_local_paths(tmp_path):
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    body = http.calls[0]["body"]
    assert str(data_root).encode("utf-8") not in body
    assert b"references/" not in body
    assert b"AI_CHARACTERS" not in body
    assert b"07_generated" not in body


def test_no_socket_module_used_by_fake_path(tmp_path):
    """The injected seam means urllib is never touched; assert our fake got every call."""
    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    http = FakeImageHttp()
    svc, job = _job(data_root, _generator(data_root, http))
    svc.run_to_completion(job.job_id)
    assert len(http.calls) == 1
    assert http.calls[0]["timeout_s"] > 0
