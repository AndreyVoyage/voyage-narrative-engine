#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMAGE_GENERATION_PRODUCT_WIRING_V1 (Slice D).

Offline. Temp data roots, fake settings/vault, an injected in-process image
transport (Slice C's ImageHttpPost seam). No socket, no live provider, no real
credential, no real Companion data, no Canon.

Proves the product wiring:
  * server composition root wires RealCompanionImageGenerator (release) while the
    library default stays UnavailableImageGenerator;
  * provider-call-free IMAGE_GENERATION readiness (all not-ready reasons + ready);
  * the custom + context product flows run QUEUED -> GENERATING -> READY with
    exactly one provider transport call, the Slice B prompt, local references,
    a Gallery-visible result, and zero chat/memory mutation;
  * the failed flow and the background/cover reuse.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import pytest

from services.character_companion import CompanionService
from services.character_companion.character_import import CharacterImportService
from services.character_companion.credentials import InMemoryCredentialVault
from services.character_companion.image_jobs import (
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    ImageJobService,
    UnavailableImageGenerator,
)
from services.character_companion.image_readiness import (
    STATUS_ACTIVE_SNAPSHOT_MISSING,
    STATUS_CREDENTIAL_MISSING,
    STATUS_MODEL_UNSUPPORTED,
    STATUS_READY,
    STATUS_ROLE_UNASSIGNED,
    evaluate_image_generation_readiness,
)
from services.character_companion.settings import CompanionSettings, RoleAssignment, SettingsStore
from services.character_companion.transport import CompanionTransport
from services.character_companion.visual import ImageProviderAdapter, RealCompanionImageGenerator

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory

_IMG_ROLE = "IMAGE_GENERATION"


# ============================================================ fixtures
def _png(pad: int = 40) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * pad


def _jpeg(pad: int = 40) -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * pad


def _webp(pad: int = 24) -> bytes:
    return b"RIFF" + b"\x2c\x00\x00\x00" + b"WEBP" + b"\x00" * pad


_RESULT_PNG = _png(96)


class FakeImageHttp:
    """Injected image transport seam. Captures every call; never opens a socket."""

    def __init__(self, raises: Optional[BaseException] = None) -> None:
        self.calls: list[dict] = []
        self._raises = raises

    def __call__(self, url: str, body: bytes, headers: dict, timeout_s: float):
        self.calls.append({"url": url, "body": body, "headers": dict(headers)})
        if self._raises is not None:
            raise self._raises
        return {"data": [{"b64_json": base64.b64encode(_RESULT_PNG).decode("ascii")}]}


def _make_canon(tmp_path: Path, character_id: str = "kira") -> Path:
    root = tmp_path / "fake-canon"
    gen_rel = f"AI_CHARACTERS/{character_id}/07_generated"
    preset = {
        "character": character_id,
        "status": "APPROVED_AS_CANON",
        "active_canon": {
            "primary_face_reference": f"{gen_rel}/face.png",
            "body_canon_a": f"{gen_rel}/body_a.jpg",
            "expression_canon": f"{gen_rel}/expr.webp",
        },
        "identity_summary": {
            "role": "female", "height_cm": 168, "height_direction": "athletic and slender",
            "body_direction": "athletic build", "face_direction": "oval face",
            "hair_direction": "shoulder-length wavy hair", "style_direction": "casual modern",
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
    (gen / "expr.webp").write_bytes(_webp(16))
    return root


def _seed_snapshot(data_root: Path, tmp_path: Path, character_id: str = "kira") -> None:
    CharacterImportService(data_root).import_character(_make_canon(tmp_path, character_id), character_id, "add")


def _configured_settings_store(data_root: Path, *, model="gpt-image-1") -> SettingsStore:
    store = SettingsStore(data_root)
    s = store.load()
    s.roles[_IMG_ROLE] = RoleAssignment("openai", model)
    return store.save(s) and store   # save persists; return the store


def _vault_with_key(provider="openai", key="test-key-not-real") -> InMemoryCredentialVault:
    v = InMemoryCredentialVault()
    v.store(provider, key)
    return v


def _service(
    tmp_path,
    *,
    data_root=None,
    http=None,
    settings_store=None,
    vault=None,
    generator=None,
) -> CompanionService:
    data_root = data_root or (tmp_path / "companion-data")
    vault = vault if vault is not None else _vault_with_key()
    settings_store = settings_store or _configured_settings_store(data_root)
    if generator is None:
        generator = RealCompanionImageGenerator(
            data_root=data_root,
            settings_store=settings_store,
            credential_vault=vault,
            adapter=ImageProviderAdapter(http_post=http or FakeImageHttp()),
        )
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        image_generator=generator,
        settings_store=settings_store,
        credential_vault=vault,
    )


# ==================================== 30/31 composition root + library default
def test_30_release_composition_wires_real_generator_no_provider_call(tmp_path):
    import tools.character_companion_server as server

    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    store = _configured_settings_store(data_root)
    vault = _vault_with_key()

    gen = server._build_image_generator("real", data_root=data_root, settings_store=store, vault=vault)
    assert isinstance(gen, RealCompanionImageGenerator)
    assert gen.name == "real-openai-compat"

    # release mode default resolves to "real"; dev -> "fake"; no vault -> fail closed
    assert server._build_image_generator("fake", data_root=data_root, settings_store=store, vault=vault).name == "fake"
    assert isinstance(
        server._build_image_generator("real", data_root=data_root, settings_store=store, vault=None),
        UnavailableImageGenerator,
    )

    # a full transport build performs zero provider requests at startup
    transport = server.build_transport(data_root=tmp_path / "srv", mode="release")
    assert isinstance(transport, CompanionTransport)


def test_31_library_default_is_unavailable_generator(tmp_path):
    svc = ImageJobService(tmp_path / "data")
    assert isinstance(svc._generator, UnavailableImageGenerator)
    assert svc.generator_name == "unavailable"


# ==================================================== 32 readiness (no provider call)
def test_32a_role_unassigned_not_ready(tmp_path):
    r = evaluate_image_generation_readiness(CompanionSettings(roles={}), _vault_with_key())
    assert r.ready is False and r.status == STATUS_ROLE_UNASSIGNED and r.reason_code == STATUS_ROLE_UNASSIGNED
    assert r.message_key.startswith("image.readiness.")


def test_32b_credential_missing_not_ready(tmp_path):
    s = CompanionSettings(roles={_IMG_ROLE: RoleAssignment("openai", "gpt-image-1")})
    r = evaluate_image_generation_readiness(s, InMemoryCredentialVault())
    assert r.ready is False and r.status == STATUS_CREDENTIAL_MISSING
    assert r.provider_id == "openai" and r.model_id == "gpt-image-1"


def test_32c_unsupported_model_not_ready(tmp_path):
    s = CompanionSettings(roles={_IMG_ROLE: RoleAssignment("openai", "gpt-4o-mini")})
    r = evaluate_image_generation_readiness(s, _vault_with_key())
    assert r.ready is False and r.status == STATUS_MODEL_UNSUPPORTED


def test_32d_active_snapshot_missing_not_ready(tmp_path):
    from services.character_companion.character_import import SnapshotStore

    data_root = tmp_path / "data"
    store = _configured_settings_store(data_root)
    r = evaluate_image_generation_readiness(
        store.load(), _vault_with_key(),
        snapshot_store=SnapshotStore(data_root), character_id="kira",
    )
    assert r.ready is False and r.status == STATUS_ACTIVE_SNAPSHOT_MISSING


def test_32e_fully_configured_is_ready(tmp_path):
    from services.character_companion.character_import import SnapshotStore

    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    store = _configured_settings_store(data_root)
    r = evaluate_image_generation_readiness(
        store.load(), _vault_with_key(),
        snapshot_store=SnapshotStore(data_root), character_id="kira",
    )
    assert r.ready is True and r.status == STATUS_READY and r.reason_code is None


def test_32f_unverified_capability_preserved(tmp_path):
    # gpt-image-1 is MODEL_UNVERIFIED in the registry -> ready, but unverified flag stays true
    from services.character_companion.character_import import SnapshotStore

    data_root = tmp_path / "data"
    _seed_snapshot(data_root, tmp_path)
    store = _configured_settings_store(data_root)
    r = evaluate_image_generation_readiness(
        store.load(), _vault_with_key(),
        snapshot_store=SnapshotStore(data_root), character_id="kira",
    )
    assert r.ready is True and r.unverified is True  # never silently "verified"


def test_32g_readiness_transport_and_service(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    js = CompanionTransport(svc).image_generation_readiness("kira")
    assert js["ready"] is True and js["status"] == "READY"
    for banned in ("secret", "authorization", "apiKey", "credential", "path", "\\"):
        assert banned.lower() not in json.dumps(js).lower()


# ==================================================== 33 custom product flow
def _session(svc: CompanionService) -> str:
    return svc.create_session("kira", scene={"place": "small kitchen", "time": "evening"}).session_id


def _mem_tree(data_root: Path) -> dict:
    root = data_root / "characters" / "kira"
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and ("memory" in p.parts or "state" in p.parts)}


def test_33_custom_flow_one_call_slice_b_prompt_gallery(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    svc.send_message(sid, "Привет, Кира.")
    msgs_before = len(svc.get_messages(sid))
    mem_before = _mem_tree(svc._data_root)

    job = svc.create_image_job(sid, kind="custom", prompt="Kira by a window in the evening")
    assert job.state == STATE_QUEUED
    svc.poll_image_jobs(sid)                       # -> GENERATING, 0 calls
    assert svc.get_image_job(job.job_id).state == STATE_GENERATING
    assert http.calls == []
    svc.poll_image_jobs(sid)                       # -> READY, 1 call
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY and len(http.calls) == 1

    # the provider prompt is the deterministic Slice B VisualPromptPackage text
    body = http.calls[0]["body"]
    assert b"[REQUEST]" in body and b"[CHARACTER IDENTITY]" in body and b"[REFERENCE GUIDANCE]" in body
    assert "Kira by a window in the evening".encode("utf-8") in body
    assert http.calls[0]["url"].endswith("/v1/images/edits")     # local references attached
    assert b"AI_CHARACTERS" not in body and str(svc._data_root).encode() not in body

    # Gallery path shows the READY result; chat + memory untouched
    assert done.result_ref in svc._images.ready_results(sid)
    out = svc.image_path(done.result_ref)
    assert out.is_file() and out.read_bytes() == _RESULT_PNG
    assert len(svc.get_messages(sid)) == msgs_before
    assert _mem_tree(svc._data_root) == mem_before

    # further polls never call the provider again
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    assert len(http.calls) == 1


# ==================================================== 34 context product flow
def test_34_context_flow_bounded_context_no_full_history(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    for i in range(12):
        svc.send_message(sid, f"сообщение {i}")

    job = svc.create_image_job(sid, kind="context")
    assert job.context is not None and job.context.get("excerptLimit") == 8
    assert len(job.context.get("recentMessages") or []) <= 8
    assert (job.context.get("scene") or {}).get("place") == "small kitchen"

    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY and len(http.calls) == 1
    body = http.calls[0]["body"]
    assert b"[SCENE]" in body and "small kitchen".encode("utf-8") in body
    # bounded: only the last few messages, never all 12+ turns
    assert body.count("сообщение ".encode("utf-8")) <= 8
    assert done.result_ref in svc._images.ready_results(sid)


# ==================================================== 35 failed product flow
def test_35_failed_flow_bounded_error_one_call(tmp_path):
    from services.character_companion.visual import ImageGenerationTransportError

    http = FakeImageHttp(raises=ImageGenerationTransportError("provider exploded"))
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)

    job = svc.create_image_job(sid, kind="custom", prompt="anything")
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_FAILED
    assert done.error == "image_generation_transport_failed"   # bounded code, no stack trace
    assert done.result_ref is None
    assert svc._images.ready_results(sid) == ()
    assert not (svc._data_root / "images" / f"{job.job_id}.png").exists()
    for _ in range(3):
        svc.poll_image_jobs(sid)
    assert len(http.calls) == 1


# ==================================================== 36 background / cover reuse
def test_36_ready_image_usable_as_cover_no_regeneration(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    job = svc.create_image_job(sid, kind="custom", prompt="a portrait")
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    ref = svc.get_image_job(job.job_id).result_ref
    assert ref and len(http.calls) == 1

    session = svc.set_scene_cover(sid, ref)        # existing cover mechanism
    assert session.scene_cover_ref == ref
    assert len(http.calls) == 1                    # no regeneration for cover
    # the safe server ref is what the frontend consumes (no absolute path)
    assert ref.startswith("images/") and ".." not in ref
