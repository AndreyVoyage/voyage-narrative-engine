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
import threading
import time
from pathlib import Path
from typing import Optional

import pytest

from services.character_companion import CompanionError, CompanionService
from services.character_companion.character_import import CharacterImportService
from services.character_companion.credentials import InMemoryCredentialVault
from services.character_companion.image_jobs import (
    PINNED_GENERATION_SPEC_SCHEMA_VERSION,
    STATE_CANCELLED,
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    ImageJob,
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
            "body_canon_b": f"{gen_rel}/body_b.jpg",
            "expression_canon": f"{gen_rel}/expr.webp",
            "motion_reference": f"{gen_rel}/motion.png",
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
    (gen / "body_b.jpg").write_bytes(_jpeg(30))
    (gen / "expr.webp").write_bytes(_webp(16))
    (gen / "motion.png").write_bytes(_png(24))
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


def _advance_row(job: ImageJob, **changes) -> ImageJob:
    """Local equivalent of image_jobs._with -- kept test-side so no private
    helper needs to be exported."""
    row = job.to_row()
    row.update(changes)
    row["updated_at"] = "2020-01-01T00:00:00+00:00"
    return ImageJob.from_row(row)


class _BlockingGenerator:
    """Deterministic thread-control generator for concurrency tests. QUEUED ->
    GENERATING is instant (no provider call); a GENERATING call blocks on
    `release` until the test lets it proceed, then returns READY. Never opens a
    socket. `prepare_generation_spec` is delegated to a real generator bound to
    a fake HTTP transport (spec computation is provider-call-free per V1A)."""

    def __init__(self, spec_source) -> None:
        self._spec_source = spec_source
        self.calls = 0
        self._calls_lock = threading.Lock()
        self.entered = threading.Event()   # set once a GENERATING call is blocking
        self.release = threading.Event()   # the test sets this to let it finish

    def prepare_generation_spec(self, *, character_id: str):
        return self._spec_source.prepare_generation_spec(character_id=character_id)

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        if job.state == STATE_QUEUED:
            return _advance_row(job, state=STATE_GENERATING)
        if job.state == STATE_GENERATING:
            with self._calls_lock:
                self.calls += 1
            self.entered.set()
            if not self.release.wait(timeout=10):
                raise TimeoutError("test blocking generator was never released")
            return _advance_row(job, state=STATE_READY, result_ref=f"images/{job.job_id}.svg")
        return job


class _CountingGenerator:
    """Counts every advance() call; used to prove a restarted/orphan-detecting
    instance never reaches the provider."""

    def __init__(self) -> None:
        self.calls = 0

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        self.calls += 1
        return job

    def prepare_generation_spec(self, *, character_id: str):
        raise NotImplementedError


def _blocking_service(tmp_path, *, data_root=None):
    """A CompanionService bound to a _BlockingGenerator, for deterministic
    concurrency control. Returns (service, generator)."""
    data_root = Path(data_root or (tmp_path / "companion-data"))
    _seed_snapshot(data_root, tmp_path)
    settings_store = _configured_settings_store(data_root)
    vault = _vault_with_key()
    spec_source = RealCompanionImageGenerator(
        data_root=data_root,
        settings_store=settings_store,
        credential_vault=vault,
        adapter=ImageProviderAdapter(http_post=FakeImageHttp()),
    )
    blocker = _BlockingGenerator(spec_source)
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        image_generator=blocker,
        settings_store=settings_store,
        credential_vault=vault,
    )
    return svc, blocker


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


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _assert_pinned_spec(job, *, kind: str) -> dict:
    assert job.kind == kind
    spec = job.context["generationSpec"]
    assert spec["schemaVersion"] == PINNED_GENERATION_SPEC_SCHEMA_VERSION
    identity = spec["identity"]
    assert identity["characterId"] == "kira"
    assert identity["snapshotVersion"] == "v1"
    assert len(identity["snapshotHash"]) == 64
    source = identity["sourceCanon"]
    assert source["status"] == "APPROVED_AS_CANON"
    assert len(source["contentHash"]) == 64
    assert len(source["sourceHash"]) == 64
    assert source["sourceCharacterId"] == "kira"
    refs = spec["references"]
    assert 2 <= len(refs) <= 4
    assert len({ref["assetId"] for ref in refs}) == len(refs)
    for ref in refs:
        assert set(ref) == {
            "assetId", "roles", "relativePath", "sha256", "fileType",
            "byteLength", "sourceSemanticKey",
        }
        assert ref["roles"] and ref["relativePath"].startswith("references/")
        assert len(ref["sha256"]) == 64
        assert ref["fileType"] in {"PNG", "JPEG", "WEBP"}
        assert ref["byteLength"] > 0
    assert spec["provider"] == {
        "providerId": "openai",
        "modelId": "gpt-image-1",
        "baseUrl": "https://api.openai.com",
    }
    assert spec["parameters"] == {"size": "1024x1024", "quality": "low"}
    return spec


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
    custom_spec = _assert_pinned_spec(job, kind="custom")
    persisted = json.loads(
        (svc._data_root / "companion_image_jobs.json").read_text(encoding="utf-8")
    )
    assert persisted[0]["context"]["generationSpec"] == custom_spec
    assert "test-key-not-real" not in json.dumps(custom_spec)
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
    _assert_pinned_spec(job, kind="context")
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


# ========================================== V1A pinned generation specification
def test_37_active_snapshot_settings_and_selection_drift_are_ignored(tmp_path, monkeypatch):
    from services.character_companion.character_import import SnapshotStore
    import services.character_companion.visual.reference_bundle as bundle_module
    import services.character_companion.visual.reference_selection as selection_module

    data_root = tmp_path / "data"
    canon_root = _make_canon(tmp_path)
    importer = CharacterImportService(data_root)
    importer.import_character(canon_root, "kira", "add")
    settings_store = _configured_settings_store(data_root)
    http = FakeImageHttp()
    svc = _service(
        tmp_path, data_root=data_root, http=http, settings_store=settings_store,
    )
    sid = _session(svc)

    job = svc.create_image_job(sid, kind="custom", prompt="pinned portrait")
    spec = _assert_pinned_spec(job, kind="custom")
    pinned_refs = tuple((ref["assetId"], ref["sha256"]) for ref in spec["references"])
    assert len(pinned_refs) == 4
    assert "motion_reference" not in {asset_id for asset_id, _sha in pinned_refs}
    snapshot_store = SnapshotStore(data_root)
    v1_dir = snapshot_store.version_dir("kira", "v1")
    v1_payloads = [
        (v1_dir / ref["relativePath"]).read_bytes() for ref in spec["references"]
    ]

    # A later explicit import/activation produces v2 with different identity bytes.
    preset_path = (
        canon_root / "AI_CHARACTERS" / "kira" / "10_notes"
        / "kira_REFERENCE_PRESETS.json"
    )
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    preset["identity_summary"]["hair_direction"] = "long straight auburn hair"
    preset["active_canon"] = {
        "primary_face_reference": "AI_CHARACTERS/kira/07_generated/face.png",
        "expression_canon": "AI_CHARACTERS/kira/07_generated/expr.webp",
        "motion_reference": "AI_CHARACTERS/kira/07_generated/motion.png",
    }
    preset_path.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")
    v2_face = b"\x89PNG\r\n\x1a\n" + b"v2-face-bytes" * 3
    (canon_root / "AI_CHARACTERS" / "kira" / "07_generated" / "face.png").write_bytes(v2_face)
    updated = importer.import_character(canon_root, "kira", "update")
    assert updated.snapshot_version == "v2"
    importer.activate_snapshot("kira", "v2")
    v2_snapshot = snapshot_store.load_active_snapshot("kira")
    from services.character_companion.visual import build_reference_bundle
    v2_bundle = build_reference_bundle(
        snapshot=v2_snapshot,
        snapshot_dir=snapshot_store.version_dir("kira", "v2"),
    )
    assert tuple(ref.asset_id for ref in v2_bundle.references) != tuple(
        asset_id for asset_id, _sha in pinned_refs
    )

    # Current settings become unusable and point elsewhere after job creation.
    changed = settings_store.load()
    changed.roles[_IMG_ROLE] = RoleAssignment("openai", "gpt-4o-mini")
    changed.base_urls["openai"] = "https://changed.invalid"
    settings_store.save(changed)

    def selection_must_not_run(*_args, **_kwargs):
        pytest.fail("reference selection was rerun during pinned execution")

    monkeypatch.setattr(bundle_module, "select_reference_asset_ids", selection_must_not_run)
    monkeypatch.setattr(selection_module, "select_reference_asset_ids", selection_must_not_run)

    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == "https://api.openai.com/v1/images/edits"
    assert b"gpt-image-1" in call["body"] and b"gpt-4o-mini" not in call["body"]
    assert b"1024x1024" in call["body"] and b"\r\nlow\r\n" in call["body"]
    for payload in v1_payloads:
        assert payload in call["body"]
    assert v2_face not in call["body"]
    assert done.context["generationSpec"] == spec
    assert done.context["result"]["snapshotVersion"] == "v1"
    assert snapshot_store.read_active_version("kira") == "v2"


def test_38_pinned_reference_tamper_fails_closed_without_substitution(tmp_path, monkeypatch):
    import services.character_companion.visual.reference_bundle as bundle_module

    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    job = svc.create_image_job(sid, kind="custom", prompt="identity portrait")
    spec = _assert_pinned_spec(job, kind="custom")
    assert len(spec["references"]) == 4  # the fifth usable motion ref is not selected

    pinned = spec["references"][0]
    snapshot_dir = svc._data_root / "characters" / "kira" / "snapshots" / "v1"
    (snapshot_dir / pinned["relativePath"]).write_bytes(_png(77))

    def selection_must_not_run(*_args, **_kwargs):
        pytest.fail("tampered pinned input was replaced through reselection")

    monkeypatch.setattr(bundle_module, "select_reference_asset_ids", selection_must_not_run)
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    failed = svc.get_image_job(job.job_id)
    assert failed.state == STATE_FAILED
    assert failed.error == "generation_spec_snapshot_invalid"
    assert failed.context["generationSpec"] == spec
    assert http.calls == []


def test_39_ready_output_does_not_mutate_snapshot_canon_or_pinned_refs(tmp_path):
    data_root = tmp_path / "data"
    canon_root = _make_canon(tmp_path)
    CharacterImportService(data_root).import_character(canon_root, "kira", "add")
    http = FakeImageHttp()
    svc = _service(tmp_path, data_root=data_root, http=http)
    sid = _session(svc)
    job = svc.create_image_job(sid, kind="context")
    spec_before = json.loads(json.dumps(job.context["generationSpec"]))
    snapshot_root = data_root / "characters" / "kira" / "snapshots"
    snapshot_before = _tree_bytes(snapshot_root)
    canon_before = _tree_bytes(canon_root)

    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY and len(http.calls) == 1
    assert _tree_bytes(snapshot_root) == snapshot_before
    assert _tree_bytes(canon_root) == canon_before
    assert done.context["generationSpec"]["references"] == spec_before["references"]
    assert done.context["generationSpec"]["identity"]["sourceCanon"]["status"] == "APPROVED_AS_CANON"
    assert done.result_ref.startswith("images/")


def test_40_legacy_terminal_jobs_load_and_nonterminal_job_fails_closed(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True)
    old = "2026-01-01T00:00:00+00:00"
    rows = [
        {
            "job_id": "legacy-ready", "session_id": "s1", "character_id": "kira",
            "kind": "custom", "state": STATE_READY, "created_at": old,
            "updated_at": old, "prompt": "old", "context": None,
            "result_ref": "images/legacy.png", "error": None,
        },
        {
            "job_id": "legacy-failed", "session_id": "s1", "character_id": "kira",
            "kind": "custom", "state": STATE_FAILED, "created_at": old,
            "updated_at": old, "prompt": "old", "context": None,
            "result_ref": None, "error": "old_failure",
        },
        {
            "job_id": "legacy-cancelled", "session_id": "s1", "character_id": "kira",
            "kind": "context", "state": STATE_CANCELLED, "created_at": old,
            "updated_at": old, "prompt": None, "context": {},
            "result_ref": None, "error": None,
        },
        {
            "job_id": "legacy-queued", "session_id": "s1", "character_id": "kira",
            "kind": "custom", "state": STATE_QUEUED, "created_at": old,
            "updated_at": old, "prompt": "old queued", "context": None,
            "result_ref": None, "error": None,
        },
    ]
    (data_root / "companion_image_jobs.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    http = FakeImageHttp()
    jobs = ImageJobService(data_root, RealCompanionImageGenerator(
        data_root=data_root,
        settings_store=_configured_settings_store(data_root),
        credential_vault=_vault_with_key(),
        adapter=ImageProviderAdapter(http_post=http),
    ))
    assert jobs.get_job("legacy-ready").state == STATE_READY
    assert jobs.get_job("legacy-failed").state == STATE_FAILED
    assert jobs.get_job("legacy-cancelled").state == STATE_CANCELLED
    assert jobs.ready_results("s1") == ("images/legacy.png",)

    jobs.tick()
    failed = jobs.get_job("legacy-queued")
    assert failed.state == STATE_FAILED and failed.error == "generation_spec_missing"
    assert jobs.get_job("legacy-ready").state == STATE_READY
    assert jobs.ready_results("s1") == ("images/legacy.png",)
    assert http.calls == []


def test_41_unapproved_local_snapshot_fails_at_creation_without_provider(tmp_path):
    from services.character_companion.character_import import CharacterLocalSnapshot

    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    manifest_path = (
        svc._data_root / "characters" / "kira" / "snapshots" / "v1" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sourceCanon"]["status"] = "DRAFT"
    manifest["snapshotHash"] = ""
    snapshot = CharacterLocalSnapshot.from_dict(manifest)
    manifest["snapshotHash"] = snapshot.compute_hash()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(CompanionError) as exc:
        svc.create_image_job(sid, kind="custom", prompt="must not run")
    assert exc.value.code == "image_generation_snapshot_not_approved"
    assert not (svc._data_root / "companion_image_jobs.json").exists()
    assert http.calls == []


# ============================================================================
# COMPANION_IMAGE_IDENTITY_V1B -- job concurrency and idempotency
#
# Safety invariant under test: ONE persisted ImageJob may initiate AT MOST ONE
# image-provider operation. Rapid clicks, concurrent POSTs, overlapping
# polling, and backend-restart recovery must never cause provider attempt #2
# for the same job. Offline: fake/blocking generators only, temp data roots.
# ============================================================================

# ---------------------------------------------------- 50 create idempotency
def test_50_idempotent_same_request_returns_same_job(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    j1 = svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    j2 = svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    assert j1.job_id == j2.job_id
    rows = json.loads((svc._data_root / "companion_image_jobs.json").read_text(encoding="utf-8"))
    assert len(rows) == 1


def test_51_requestid_conflict_different_prompt(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    with pytest.raises(CompanionError) as exc:
        svc.create_image_job(sid, kind="custom", prompt="different", request_id="req-1")
    assert exc.value.code == "image_job_idempotency_conflict"
    rows = json.loads((svc._data_root / "companion_image_jobs.json").read_text(encoding="utf-8"))
    assert len(rows) == 1  # the conflicting attempt created nothing


def test_52_requestid_conflict_different_session(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid_a = _session(svc)
    sid_b = _session(svc)
    svc.create_image_job(sid_a, kind="custom", prompt="hello", request_id="req-1")
    with pytest.raises(CompanionError) as exc:
        svc.create_image_job(sid_b, kind="custom", prompt="hello", request_id="req-1")
    assert exc.value.code == "image_job_idempotency_conflict"


def test_53_requestid_conflict_different_kind(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    with pytest.raises(CompanionError) as exc:
        svc.create_image_job(sid, kind="context", request_id="req-1")
    assert exc.value.code == "image_job_idempotency_conflict"


def test_54_terminal_idempotent_replay_returns_original(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    job = svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY and len(http.calls) == 1

    replay = svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    assert replay.job_id == job.job_id
    assert replay.state == STATE_READY
    assert len(http.calls) == 1  # the replay never touched the provider


def test_55_new_request_after_terminal_creates_new_job(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    job1 = svc.create_image_job(sid, kind="custom", prompt="hello", request_id="req-1")
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    assert svc.get_image_job(job1.job_id).state == STATE_READY

    job2 = svc.create_image_job(sid, kind="custom", prompt="hello again", request_id="req-2")
    assert job2.job_id != job1.job_id
    assert job2.state == STATE_QUEUED


def test_56_request_id_validation_and_legacy_caller(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    with pytest.raises(CompanionError) as exc:
        svc.create_image_job(sid, kind="custom", prompt="x", request_id="has a space")
    assert exc.value.code == "invalid_request"
    with pytest.raises(CompanionError) as exc2:
        svc.create_image_job(sid, kind="custom", prompt="x", request_id="x" * 200)
    assert exc2.value.code == "invalid_request"
    assert not (svc._data_root / "companion_image_jobs.json").exists()

    # a legacy caller with no requestId at all still works and is still
    # protected by the session+character single-flight check.
    job = svc.create_image_job(sid, kind="custom", prompt="legacy ok")
    assert job.request_id is None
    with pytest.raises(CompanionError) as exc3:
        svc.create_image_job(sid, kind="custom", prompt="legacy ok 2")
    assert exc3.value.code == "image_job_active_conflict"


# ---------------------------------------------------- 57/58 single-flight create
def test_57_concurrent_create_same_session_exactly_one_active(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)

    barrier = threading.Barrier(2)
    results: dict[str, tuple] = {}

    def attempt(name: str, request_id: str) -> None:
        try:
            barrier.wait(timeout=5)
            job = svc.create_image_job(sid, kind="custom", prompt="race", request_id=request_id)
            results[name] = ("ok", job)
        except CompanionError as exc:
            results[name] = ("error", exc.code)

    t1 = threading.Thread(target=attempt, args=("a", "req-race-a"))
    t2 = threading.Thread(target=attempt, args=("b", "req-race-b"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    outcomes = [results["a"], results["b"]]
    oks = [o for o in outcomes if o[0] == "ok"]
    errs = [o for o in outcomes if o[0] == "error"]
    assert len(oks) == 1 and len(errs) == 1
    assert errs[0][1] == "image_job_active_conflict"

    rows = json.loads((svc._data_root / "companion_image_jobs.json").read_text(encoding="utf-8"))
    active = [r for r in rows if r.get("session_id") == sid and r.get("state") not in ("READY", "FAILED", "CANCELLED")]
    assert len(active) == 1  # exactly one active job persisted -- no duplicate work


def test_58_different_sessions_get_independent_active_jobs(tmp_path):
    svc = _service(tmp_path)
    _seed_snapshot(svc._data_root, tmp_path)
    sid_a = _session(svc)
    sid_b = _session(svc)
    job_a = svc.create_image_job(sid_a, kind="custom", prompt="A scene", request_id="req-a")
    job_b = svc.create_image_job(sid_b, kind="custom", prompt="B scene", request_id="req-b")
    assert job_a.job_id != job_b.job_id
    assert job_a.state == STATE_QUEUED and job_b.state == STATE_QUEUED


# ---------------------------------------------------- 59 concurrent poll
def test_59_concurrent_poll_exactly_one_provider_call(tmp_path):
    svc, blocker = _blocking_service(tmp_path)
    sid = _session(svc)
    job = svc.create_image_job(sid, kind="custom", prompt="race poll", request_id="req-poll")
    svc.poll_image_jobs(sid)  # QUEUED -> GENERATING, 0 provider calls
    assert svc.get_image_job(job.job_id).state == STATE_GENERATING

    t = threading.Thread(target=lambda: svc.poll_image_jobs(sid))
    t.start()
    assert blocker.entered.wait(timeout=5), "thread A never entered the provider call"

    # a second, concurrent poll on the SAME process must not call the provider
    # again and must not fail the legitimate in-flight job.
    svc.poll_image_jobs(sid)
    assert blocker.calls == 1
    assert svc.get_image_job(job.job_id).state == STATE_GENERATING

    blocker.release.set()
    t.join(timeout=5)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY
    assert blocker.calls == 1  # exactly one provider attempt for the whole job


# ---------------------------------------------------- 60 provider outside lock
def test_60_provider_call_does_not_hold_the_registry_lock(tmp_path):
    svc, blocker = _blocking_service(tmp_path)
    sid_a = _session(svc)
    sid_b = _session(svc)
    job_a = svc.create_image_job(sid_a, kind="custom", prompt="A", request_id="req-a")
    svc.poll_image_jobs(sid_a)  # QUEUED -> GENERATING

    t = threading.Thread(target=lambda: svc.poll_image_jobs(sid_a))
    t.start()
    assert blocker.entered.wait(timeout=5), "thread never entered the provider call"

    # while A's provider call is deliberately blocked, an unrelated create for a
    # DIFFERENT session must proceed promptly -- proving the registry lock is
    # released before the (potentially long) provider call, never held across it.
    started = time.monotonic()
    job_b = svc.create_image_job(sid_b, kind="custom", prompt="B", request_id="req-b")
    elapsed = time.monotonic() - started
    assert job_b.state == STATE_QUEUED
    assert elapsed < 5.0, "create for an unrelated session waited on the blocked provider call"

    blocker.release.set()
    t.join(timeout=5)
    assert svc.get_image_job(job_a.job_id).state == STATE_READY


# ---------------------------------------------------- 61 restart / orphan claim
def test_61_restart_orphan_claim_fails_closed_no_retry(tmp_path):
    data_root = tmp_path / "companion-data"
    svc1, blocker1 = _blocking_service(tmp_path, data_root=data_root)
    sid = _session(svc1)
    job = svc1.create_image_job(sid, kind="custom", prompt="orphan", request_id="req-orphan")
    svc1.poll_image_jobs(sid)  # QUEUED -> GENERATING

    t = threading.Thread(target=lambda: svc1.poll_image_jobs(sid))
    t.start()
    assert blocker1.entered.wait(timeout=5), "thread never entered the provider call"

    # the claim is durably persisted BEFORE the (still-blocked) provider call returns
    rows = json.loads((data_root / "companion_image_jobs.json").read_text(encoding="utf-8"))
    row = next(r for r in rows if r["job_id"] == job.job_id)
    assert row["execution"]["state"] == "CLAIMED"
    assert "execution" not in (row.get("context") or {})  # claim never pollutes the pinned context

    # A FRESH ImageJobService instance against the SAME data root -- no live
    # ownership of this claim -- simulates a restarted process. It must fail the
    # job closed without ever calling its own generator, and without waiting for
    # svc1's still-blocked call.
    counting = _CountingGenerator()
    svc2_images = ImageJobService(data_root, generator=counting)
    moved = svc2_images.tick()
    assert moved >= 1
    assert counting.calls == 0  # zero provider attempts after "restart"

    after = svc2_images.get_job(job.job_id)
    assert after.state == STATE_FAILED
    assert after.error == "generation_interrupted_ambiguous"

    # releasing the original blocked call must NOT resurrect or overwrite the
    # already-failed-closed job -- no automatic retry, no reviving a stale attempt.
    blocker1.release.set()
    t.join(timeout=5)
    final = svc2_images.get_job(job.job_id)
    assert final.state == STATE_FAILED
    assert final.error == "generation_interrupted_ambiguous"
    assert blocker1.calls == 1  # exactly one attempt was ever made, by svc1


# ============================== V1C context visual grounding (visible-only)
def test_62_context_excludes_presentation_hidden_messages(tmp_path):
    svc = _service(tmp_path, http=FakeImageHttp())
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    for i in range(6):
        svc.send_message(sid, f"видимое {i}")
    msgs = svc.get_messages(sid)
    hidden_msg = next(m for m in reversed(msgs) if m.role == "user")
    svc.set_message_visibility(sid, hidden_msg.seq, True)

    job = svc.create_image_job(sid, kind="context")
    excerpt = job.context.get("recentMessages") or []
    texts = [m["text"] for m in excerpt]

    assert hidden_msg.text not in texts
    assert len(excerpt) <= 8
    # bounded + chronological: the excerpt is a suffix of the visible history
    visible = [m.text for m in msgs if m.seq != hidden_msg.seq]
    assert texts == visible[-len(texts):]


def test_63_context_scene_drops_freeform_keeps_structured(tmp_path):
    svc = _service(tmp_path, http=FakeImageHttp())
    _seed_snapshot(svc._data_root, tmp_path)
    sid = svc.create_session("kira", scene={
        "place": "кухня", "time": "вечер", "situation": "пьют чай",
        "mood": "спокойно", "freeform": "КИРА_ТАЙНО_ПЛАНИРУЕТ",
    }).session_id

    job = svc.create_image_job(sid, kind="context")
    scene = job.context.get("scene") or {}
    assert scene.get("place") == "кухня"
    assert scene.get("time") == "вечер"
    assert scene.get("situation") == "пьют чай"
    assert scene.get("mood") == "спокойно"
    assert "freeform" not in scene
    assert "КИРА_ТАЙНО_ПЛАНИРУЕТ" not in json.dumps(job.context)


def test_64_context_prompt_is_visible_only(tmp_path):
    http = FakeImageHttp()
    svc = _service(tmp_path, http=http)
    _seed_snapshot(svc._data_root, tmp_path)
    sid = svc.create_session("kira", scene={
        "place": "кухня", "time": "вечер", "situation": "пьют чай", "mood": "спокойно",
        "freeform": "КИРА_ТАЙНО_ПЛАНИРУЕТ",
    }).session_id
    svc.send_message(sid, "СКРЫТОЕ_НАМЕРЕНИЕ")
    msgs = svc.get_messages(sid)
    hidden_msg = next(m for m in reversed(msgs) if m.role == "user")
    svc.set_message_visibility(sid, hidden_msg.seq, True)

    job = svc.create_image_job(sid, kind="context")
    svc.poll_image_jobs(sid)
    svc.poll_image_jobs(sid)
    done = svc.get_image_job(job.job_id)
    assert done.state == STATE_READY and len(http.calls) == 1

    body = http.calls[0]["body"]
    assert "кухня".encode("utf-8") in body            # location/time remain available
    assert "пьют чай".encode("utf-8") in body         # observable situation preserved
    assert "СКРЫТОЕ_НАМЕРЕНИЕ".encode("utf-8") not in body    # hidden message excluded
    assert "КИРА_ТАЙНО_ПЛАНИРУЕТ".encode("utf-8") not in body  # freeform excluded


def test_65_manual_custom_is_context_free_except_identity(tmp_path):
    svc = _service(tmp_path, http=FakeImageHttp())
    _seed_snapshot(svc._data_root, tmp_path)
    sid = _session(svc)
    svc.send_message(sid, "контекст")
    job = svc.create_image_job(sid, kind="custom", prompt="портрет")
    assert job.kind == "custom"
    assert job.context.get("scene") is None
    assert job.context.get("recentMessages") is None
