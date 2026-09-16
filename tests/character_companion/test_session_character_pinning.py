#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8B adversarial tests: exact character selection + immutable session pinning.

Everything runs offline against synthetic Package V1 fixtures under
``pytest tmp_path``. No production package storage, no network, no provider,
no real KIRA package, no memory/state namespace for PINNED_V1 sessions.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from services.character_companion import (
    CompanionCatalog,
    CompanionCharacterEntry,
    CompanionError,
    CompanionService,
)
from services.character_companion.character_import import (
    CharacterPackageManagementService,
)
from services.character_companion.package_runtime import (
    ExactPackageRuntimeBinding,
    load_runtime_character_definition,
)
from services.character_companion.session_character import (
    ExactCharacterSelectionV1,
    SessionCharacterPinStatus,
)
from services.crp_authoring.auditor_checks import compute_package_hash
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package

from tests.character_companion.conftest import (
    ACCEPTED_ROOT,
    FAKE_PROVIDER_INFO,
    make_fake_factory,
)


# --------------------------------------------------------------------------- #
# synthetic Package V1 fixtures
# --------------------------------------------------------------------------- #
def _canonical(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _candidate_payload(character_id: str, package_id: str, package_version: int) -> dict:
    return {
        "package_id": package_id,
        "subject_id": character_id,
        "package_version": package_version,
        "source_snapshot_id": f"snap-{character_id}-{package_version}",
        "role_result_refs": [],
        "claims": [],
        "contradictions": [],
        "unknowns": [],
        "psychology_candidate": {},
        "voice_candidate": {},
        "validation_results": {},
        "audit_result": None,
        "provenance_manifest": {},
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "HUMAN_APPROVED",
        "lineage": None,
        "behavioral_validation_refs": [],
        "intimacy_candidate": {},
        "identity_biography_candidate": {},
        "behavior_candidate": {},
        "relationships_candidate": {},
        "boundaries_candidate": {},
        "seed_memory_candidate": {},
    }


def _dimension_definition() -> dict:
    return {
        "domain": "RELATIONSHIP",
        "id": "trust",
        "label": "Trust",
        "description": "How much the character trusts the user",
        "band_meanings": {
            "VERY_LOW": "no trust",
            "LOW": "low trust",
            "MID": "neutral trust",
            "HIGH": "high trust",
            "VERY_HIGH": "complete trust",
        },
        "band_guidance": {},
    }


def make_crp_package(
    tmp_path: Path,
    *,
    dirname: str,
    character_id: str,
    release_id: str,
    package_id: str | None = None,
    package_version: int = 1,
) -> Path:
    """Build a minimal, valid, immutable CRP-import Package V1 on disk."""
    package_id = package_id or f"pkg-{character_id}-{release_id}"
    root = tmp_path / dirname
    root.mkdir()

    candidate_payload = _candidate_payload(character_id, package_id, package_version)
    candidate = rehydrate_candidate_package(candidate_payload)
    accepted_semantic_hash = compute_package_hash(candidate)

    acceptance_envelope = {
        "artifact_type": "CRP_ACCEPTANCE_RECORD",
        "schema_version": "1",
        "acceptance_record": {
            "acceptance_id": f"acc-{package_id}",
            "package_id": package_id,
            "package_version": package_version,
            "subject_id": character_id,
            "package_hash": accepted_semantic_hash,
            "audit_id": None,
            "decision": "HUMAN_APPROVED",
            "decided_by": "test-authority",
            "decided_at": "2026-01-01T00:00:00+00:00",
            "reason": None,
            "supersedes": None,
        },
    }

    dimension_semantics = {
        "character_id": character_id,
        "extension_type": "dimension_semantics",
        "extension_version": 1,
        "target_accepted_source_hash": accepted_semantic_hash,
        "core_contract_version": "1.0",
        "description": "synthetic dimension semantics",
        "dimensions": [_dimension_definition()],
    }

    visual_identity = {
        "domainId": "visual_identity",
        "domainSchemaVersion": "1.0",
        "contentState": "EXPLICITLY_EMPTY",
        "content": {"legacyPayload": [], "structured": {}},
        "provenanceRefs": [],
    }

    package_meta = {
        "packageSchemaVersion": "1.0",
        "characterId": character_id,
        "releaseId": release_id,
        "displayName": character_id.title(),
        "authorityClass": "LEGACY_COMPAT",
        "packageOrigin": "LEGACY_IMPORT",
    }

    files = {
        "package.json": (_canonical(package_meta), "PACKAGE_METADATA"),
        "provenance/source_candidate.json": (
            _canonical(candidate_payload),
            "SOURCE_CANDIDATE_RECORD",
        ),
        "provenance/source_acceptance.json": (
            _canonical(acceptance_envelope),
            "SOURCE_ACCEPTANCE_RECORD",
        ),
        "extensions/dimension_semantics/v1.json": (
            _canonical(dimension_semantics),
            "DIMENSION_SEMANTICS_EXTENSION",
        ),
        "domains/visual_identity.json": (_canonical(visual_identity), "DOMAIN"),
    }

    descriptors = []
    for rel, (data, role) in files.items():
        destination = root.joinpath(*rel.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        descriptors.append(
            {
                "path": rel,
                "sha256": _sha256(data),
                "byteLength": len(data),
                "semanticRole": role,
                "normalization": "CANONICAL_JSON_V1",
                "required": True,
            }
        )

    manifest = {
        "files": sorted(descriptors, key=lambda item: item["path"]),
        "manifestSchemaVersion": "1.0",
    }
    (root / "manifest.json").write_bytes(_canonical(manifest))
    return root


def _resolve_ids(
    package_root: Path, character_id: str, release_id: str
) -> tuple[str, str]:
    package_hash = _sha256((package_root / "manifest.json").read_bytes())
    definition = load_runtime_character_definition(
        ExactPackageRuntimeBinding(
            package_root=package_root,
            expected_character_id=character_id,
            expected_release_id=release_id,
            expected_package_hash=package_hash,
        )
    )
    return package_hash, definition.runtime_definition_hash


def _synthetic_catalog(*character_ids: str) -> CompanionCatalog:
    return CompanionCatalog(
        [
            CompanionCharacterEntry(
                character_id=cid,
                display_name=cid.title(),
                subject_id=cid,
                available=True,
            )
            for cid in character_ids
        ]
    )


def _setup_pinned(
    tmp_path: Path,
    *,
    character_id: str = "alice",
    release_id: str = "v1",
    dirname: str = "src-pkg",
    package_id: str | None = None,
):
    data_root = tmp_path / "companion-data"
    data_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "acceptance").mkdir(parents=True, exist_ok=True)

    src = make_crp_package(
        tmp_path,
        dirname=dirname,
        character_id=character_id,
        release_id=release_id,
        package_id=package_id,
    )
    package_hash, runtime_hash = _resolve_ids(src, character_id, release_id)
    CharacterPackageManagementService(data_root).import_package(src)

    catalog = _synthetic_catalog(character_id)
    service = CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=catalog,
    )
    selection = ExactCharacterSelectionV1(
        character_id, release_id, package_hash, runtime_hash
    )
    return service, selection, data_root, src


def _registry_rows(data_root: Path) -> list:
    path = data_root / "companion_sessions.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_registry(data_root: Path, rows: list) -> None:
    path = data_root / "companion_sessions.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _legacy_row(session_id: str, character_id: str = "alice", **extra) -> dict:
    row = {
        "session_id": session_id,
        "character_id": character_id,
        "purpose": "COMPANION",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "label": "legacy",
        "activity_seq": 1,
    }
    row.update(extra)
    return row


# --------------------------------------------------------------------------- #
# exact selection + pinning
# --------------------------------------------------------------------------- #
def test_01_exact_selection_resolves_requested_character_release(tmp_path):
    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    assert session.character_id == "alice"
    assert session.character_pin_status == SessionCharacterPinStatus.PINNED_V1.value
    assert session.character_pin == selection.to_pin()


def test_02_multiple_releases_exact_selected_release_used(tmp_path):
    data_root = tmp_path / "companion-data"
    data_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "acceptance").mkdir(parents=True, exist_ok=True)

    src_v1 = make_crp_package(
        tmp_path, dirname="src-v1", character_id="alice", release_id="v1",
        package_id="pkg-alice-v1",
    )
    src_v2 = make_crp_package(
        tmp_path, dirname="src-v2", character_id="alice", release_id="v2",
        package_id="pkg-alice-v2",
    )
    hash_v1, rt_v1 = _resolve_ids(src_v1, "alice", "v1")
    hash_v2, rt_v2 = _resolve_ids(src_v2, "alice", "v2")
    assert hash_v1 != hash_v2

    management = CharacterPackageManagementService(data_root)
    management.import_package(src_v1)
    management.import_package(src_v2)

    service = CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=_synthetic_catalog("alice"),
    )

    pinned_v1 = service.create_pinned_session(
        ExactCharacterSelectionV1("alice", "v1", hash_v1, rt_v1)
    )
    assert pinned_v1.character_pin.release_id == "v1"
    assert pinned_v1.character_pin.package_hash == hash_v1

    pinned_v2 = service.create_pinned_session(
        ExactCharacterSelectionV1("alice", "v2", hash_v2, rt_v2)
    )
    assert pinned_v2.character_pin.release_id == "v2"
    assert pinned_v2.character_pin.package_hash == hash_v2
    assert pinned_v1.session_id != pinned_v2.session_id


def test_03_full_four_field_pin_persisted(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    service.create_pinned_session(selection)
    rows = _registry_rows(data_root)
    assert len(rows) == 1
    pin = rows[0]["character_pin_v1"]
    assert set(pin) == {
        "character_id",
        "release_id",
        "package_hash",
        "runtime_definition_hash",
    }
    assert pin["character_id"] == "alice"
    assert pin["release_id"] == "v1"
    assert pin["package_hash"] == selection.package_hash
    assert pin["runtime_definition_hash"] == selection.runtime_definition_hash


def test_04_fresh_service_returns_same_pin(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    created = service.create_pinned_session(selection)
    del service

    reopened = CompanionService(
        acceptance_root=tmp_path / "acceptance",
        data_root=data_root,
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=_synthetic_catalog("alice"),
    )
    reopened_session = reopened.get_session(created.session_id)
    assert reopened_session.character_pin == selection.to_pin()
    assert reopened_session.character_pin_status == "PINNED_V1"


def test_05_later_selection_does_not_alter_earlier_pin(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    first = service.create_pinned_session(selection)

    src_v2 = make_crp_package(
        tmp_path, dirname="src-v2", character_id="alice", release_id="v2",
        package_id="pkg-alice-v2",
    )
    hash_v2, rt_v2 = _resolve_ids(src_v2, "alice", "v2")
    CharacterPackageManagementService(data_root).import_package(src_v2)
    service.create_pinned_session(
        ExactCharacterSelectionV1("alice", "v2", hash_v2, rt_v2)
    )

    rows = _registry_rows(data_root)
    first_row = next(r for r in rows if r["session_id"] == first.session_id)
    assert first_row["character_pin_v1"] == selection.to_pin().to_json()


# --------------------------------------------------------------------------- #
# fail-closed identity checks
# --------------------------------------------------------------------------- #
def test_06_wrong_package_hash_fails_before_write(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    wrong = ExactCharacterSelectionV1(
        selection.character_id,
        selection.release_id,
        "0" * 64,
        selection.runtime_definition_hash,
    )
    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(wrong)
    assert exc.value.code == "package_identity_mismatch"
    assert _registry_rows(data_root) == []


def test_07_wrong_runtime_definition_hash_fails_before_write(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    wrong = ExactCharacterSelectionV1(
        selection.character_id,
        selection.release_id,
        selection.package_hash,
        "1" * 64,
    )
    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(wrong)
    assert exc.value.code == "runtime_definition_mismatch"
    assert _registry_rows(data_root) == []


def test_08_wrong_character_id_fails(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    wrong = ExactCharacterSelectionV1(
        "bob",
        selection.release_id,
        selection.package_hash,
        selection.runtime_definition_hash,
    )
    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(wrong)
    assert exc.value.code == "package_missing"
    assert _registry_rows(data_root) == []


def test_09_wrong_release_id_fails(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    wrong = ExactCharacterSelectionV1(
        selection.character_id,
        "nope",
        selection.package_hash,
        selection.runtime_definition_hash,
    )
    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(wrong)
    assert exc.value.code == "package_missing"
    assert _registry_rows(data_root) == []


def test_10_same_release_name_changed_bytes_fails(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    alt_src = make_crp_package(
        tmp_path,
        dirname="alt-src",
        character_id="alice",
        release_id="v1",
        package_id="pkg-alice-v1-altered",
    )
    target = data_root / "character_packages" / "alice" / "v1"
    shutil.rmtree(target)
    shutil.copytree(alt_src, target)

    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(selection)
    assert exc.value.code == "package_identity_mismatch"
    assert _registry_rows(data_root) == []


def test_11_missing_package_fails_without_partial_row(tmp_path):
    service, _selection, data_root, _src = _setup_pinned(tmp_path)
    missing = ExactCharacterSelectionV1("alice", "v9", "2" * 64, "3" * 64)
    with pytest.raises(CompanionError) as exc:
        service.create_pinned_session(missing)
    assert exc.value.code == "package_missing"
    assert _registry_rows(data_root) == []


def test_12_package_removal_metadata_readable_resolution_fails(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    shutil.rmtree(data_root / "character_packages" / "alice" / "v1")

    got = service.get_session(session.session_id)
    assert got.character_pin is not None
    assert got.character_pin.package_hash == selection.package_hash

    with pytest.raises(CompanionError) as exc:
        service.resolve_pinned_definition(session.session_id)
    assert exc.value.code == "package_missing"

    row = service._session_row(session.session_id)
    assert row["character_pin_v1"] == selection.to_pin().to_json()


# --------------------------------------------------------------------------- #
# pin classification + corruption
# --------------------------------------------------------------------------- #
def test_13_legacy_row_without_pin_is_legacy_unpinned(tmp_path):
    service, _selection, data_root, _src = _setup_pinned(tmp_path)
    _write_registry(data_root, [_legacy_row("cmp-legacy")])
    session = service.get_session("cmp-legacy")
    assert session.character_pin_status == "LEGACY_UNPINNED"
    assert session.character_pin is None


def test_14_missing_key_vs_malformed_pin(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)

    _write_registry(data_root, [_legacy_row("cmp-absent")])
    assert service.get_session("cmp-absent").character_pin_status == "LEGACY_UNPINNED"

    _write_registry(data_root, [_legacy_row("cmp-null", character_pin_v1=None)])
    with pytest.raises(CompanionError) as exc:
        service.get_session("cmp-null")
    assert exc.value.code == "pin_invalid"

    _write_registry(
        data_root,
        [_legacy_row("cmp-partial", character_pin_v1={"character_id": "alice"})],
    )
    with pytest.raises(CompanionError) as exc:
        service.get_session("cmp-partial")
    assert exc.value.code == "pin_invalid"

    bad_pin = selection.to_pin().to_json()
    bad_pin["package_hash"] = "not-a-sha256"
    _write_registry(data_root, [_legacy_row("cmp-badhash", character_pin_v1=bad_pin)])
    with pytest.raises(CompanionError) as exc:
        service.get_session("cmp-badhash")
    assert exc.value.code == "pin_invalid"


def test_15_nested_pin_character_id_mismatch(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    pin = selection.to_pin().to_json()
    pin["character_id"] = "bob"
    _write_registry(
        data_root, [_legacy_row("cmp-mismatch", "alice", character_pin_v1=pin)]
    )
    with pytest.raises(CompanionError) as exc:
        service.get_session("cmp-mismatch")
    assert exc.value.code == "pin_invalid"


def test_16_metadata_update_does_not_mutate_pin(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    renamed = service.rename_session(session.session_id, "New Title")
    assert renamed.title_override == "New Title"
    assert renamed.character_pin == selection.to_pin()

    row = service._session_row(session.session_id)
    assert row["character_pin_v1"] == selection.to_pin().to_json()


def test_17_identity_mutation_through_update_api_fails(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    with pytest.raises(CompanionError) as exc:
        service._mutate_row(session.session_id, {"character_id": "evil"})
    assert exc.value.code == "session_identity_immutable"

    with pytest.raises(CompanionError) as exc:
        service._mutate_row(
            session.session_id,
            {"character_pin_v1": selection.to_pin().to_json() | {"release_id": "v9"}},
        )
    assert exc.value.code == "session_identity_immutable"


def test_18_corrupt_registry_fails_closed_not_replaced(tmp_path):
    service, _selection, data_root, _src = _setup_pinned(tmp_path)
    path = data_root / "companion_sessions.json"

    bad_json = "{ not valid json"
    path.write_text(bad_json, encoding="utf-8")
    with pytest.raises(CompanionError) as exc:
        service.list_sessions("alice")
    assert exc.value.code == "registry_corrupt"
    assert path.read_text(encoding="utf-8") == bad_json

    not_a_list = json.dumps({"not": "a list"})
    path.write_text(not_a_list, encoding="utf-8")
    with pytest.raises(CompanionError) as exc:
        service.list_sessions("alice")
    assert exc.value.code == "registry_corrupt"
    assert path.read_text(encoding="utf-8") == not_a_list


# --------------------------------------------------------------------------- #
# metadata-only + execution blocking
# --------------------------------------------------------------------------- #
def test_19_pinned_create_does_not_initialize_memory(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    service.create_pinned_session(selection)
    assert not (data_root / "characters").exists()


def test_20_pinned_get_does_not_initialize_memory(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    service.get_session(session.session_id)
    assert not (data_root / "characters").exists()


def test_21_pinned_list_does_not_initialize_memory(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    service.create_pinned_session(selection)
    service.list_sessions("alice")
    assert not (data_root / "characters").exists()


def test_22_pinned_send_reaches_resolved_runtime_seam(tmp_path, monkeypatch):
    from types import SimpleNamespace

    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    calls = []
    monkeypatch.setattr(
        service._runtime,
        "turn_with_resolved_character",
        lambda accepted, subject_id, **kwargs: calls.append((subject_id, kwargs))
        or SimpleNamespace(response="ok"),
    )
    turn = service.send_message(session.session_id, "Hello")
    assert turn.response == "ok"
    assert len(calls) == 1
    assert calls[0][0] == selection.character_id


def test_23_pinned_history_reads_pinned_namespace(tmp_path):
    from services.character_runtime import RuntimeMemoryBackend
    from services.character_runtime.memory import RuntimeEvent

    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    pin = selection.to_pin()
    mem_root = (
        data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id() / "memory"
    )
    backend = RuntimeMemoryBackend(mem_root, pin.character_id)
    backend.record_event(
        RuntimeEvent(
            event_id="evt-1",
            subject_id=pin.character_id,
            session_id=session.session_id,
            event_type="USER_MESSAGE",
            meaning="hello",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    backend.close()

    # S8C1: pinned history reads from the S8B2 namespace; it is no longer
    # rejected by the generic pinned guard and needs no package or provider.
    messages = service.get_messages(session.session_id)
    assert [m.text for m in messages] == ["hello"]


def test_24_pinned_coauthor_resolves_exact_definition(tmp_path):
    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    # S8C2: pinned co-author is no longer generically blocked; it proceeds
    # through exact Package V1 definition resolution and context assembly.
    ctx = service._coauthor_context(session.session_id)
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}


def test_25_pinned_image_execution_fails_before_provider(tmp_path, monkeypatch):
    from services.character_companion.image_jobs import KIND_CONTEXT

    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    calls = []
    monkeypatch.setattr(
        service._images, "create_job", lambda *a, **k: calls.append(1)
    )
    with pytest.raises(CompanionError) as exc:
        service.create_image_job(session.session_id, kind=KIND_CONTEXT)
    assert exc.value.code == "pinned_execution_blocked"
    assert calls == []


def test_26_still_blocked_pinned_paths_have_stable_error(tmp_path):
    from services.character_companion.image_jobs import KIND_CONTEXT

    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    for op in (
        lambda: service.create_image_job(session.session_id, kind=KIND_CONTEXT),
        lambda: service.set_message_visibility(session.session_id, 1, hidden=True),
    ):
        with pytest.raises(CompanionError) as exc:
            op()
        assert exc.value.code == "pinned_execution_blocked"
        assert "PINNED_V1" in exc.value.message


def test_27_legacy_path_retains_compatibility(tmp_path):
    service = CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=tmp_path / "companion-data",
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
    )
    session = service.create_session("kira")
    assert session.character_pin_status == "LEGACY_UNPINNED"
    assert session.character_pin is None

    turn = service.send_message(session.session_id, "Привет.")
    assert turn.response
    messages = service.get_messages(session.session_id)
    assert [m.role for m in messages] == ["user", "character"]


# --------------------------------------------------------------------------- #
# source / boundary gates
# --------------------------------------------------------------------------- #
_SERVICE_SOURCE_FILES = (
    "services/character_companion/session_character.py",
    "services/character_companion/service.py",
    "services/character_companion/transport.py",
)


def test_28_no_hardcoded_real_kira_path(tmp_path):
    forbidden = ("KIRA_CURRENT_PACKAGE_V1_ROOT", "AppData", "KiraCompanion")
    repo_root = Path(__file__).resolve().parents[2]
    for relative in _SERVICE_SOURCE_FILES:
        text = (repo_root / relative).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{relative} hard-codes {token!r}"


def test_29_no_production_package_path_accessed(tmp_path, monkeypatch):
    monkeypatch.delenv("KIRA_CURRENT_PACKAGE_V1_ROOT", raising=False)
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    assert session.character_id == "alice"
    assert data_root.is_relative_to(tmp_path)


def test_30_no_memory_or_state_namespace_created(tmp_path):
    service, selection, data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    service.get_session(session.session_id)
    service.list_sessions("alice")
    assert not (data_root / "characters").exists()
    assert not (data_root / "characters" / "alice" / "memory").exists()
    assert not (data_root / "characters" / "alice" / "state").exists()


def test_31_s8a_definition_not_passed_to_runtime_turn(tmp_path, monkeypatch):
    from services.character_runtime.definition import RuntimeCharacterDefinition

    service, selection, _data_root, _src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)

    turn_calls = []
    monkeypatch.setattr(service._runtime, "turn", lambda *a, **k: turn_calls.append(k))

    definition = service.resolve_pinned_definition(session.session_id)
    assert isinstance(definition, RuntimeCharacterDefinition)
    assert definition.runtime_definition_hash == selection.runtime_definition_hash
    assert turn_calls == []


def test_32_package_install_or_activation_never_invoked(tmp_path, monkeypatch):
    service, selection, _data_root, _src = _setup_pinned(tmp_path)

    install_calls = []
    monkeypatch.setattr(
        CharacterPackageManagementService, "import_package",
        lambda self, *a, **k: install_calls.append(1),
    )

    session = service.create_pinned_session(selection)
    service.get_session(session.session_id)
    service.list_sessions("alice")
    service.resolve_pinned_definition(session.session_id)

    assert install_calls == []
