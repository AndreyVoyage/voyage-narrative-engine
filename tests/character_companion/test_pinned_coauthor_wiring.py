#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8C2 adversarial tests: pinned co-author context + USER_STATED memory read.

Offline only: synthetic Package V1 fixtures under temp dirs, deterministic
fake/sentinel provider seams, no live provider, no network, no production path.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from services.character_companion import CompanionError, CompanionService
from services.character_companion.character_import import (
    CharacterPackageManagementService,
)
from services.character_companion.character_import.package_importer import (
    CharacterPackageImportService,
)
from services.character_companion.session_character import (
    ExactCharacterSelectionV1,
    SessionCharacterPinV1,
)
from services.character_runtime import RuntimeMemoryBackend
from services.character_runtime.memory import RuntimeEvent

from tests.character_companion.conftest import (
    ACCEPTED_ROOT,
    FAKE_PROVIDER_INFO,
    make_fake_factory,
)
from tests.character_companion.test_session_character_pinning import (
    _resolve_ids,
    _setup_pinned,
    make_crp_package,
)


def _pinned_session(tmp_path):
    service, selection, data_root, src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    return service, selection, session, data_root, src


def _pinned_mem_root(data_root: Path, pin: SessionCharacterPinV1) -> Path:
    return (
        data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id() / "memory"
    )


def _write_event(
    data_root: Path,
    pin: SessionCharacterPinV1,
    session_id: str,
    event_id: str,
    meaning: str,
    *,
    event_type: str = "USER_MESSAGE",
    provenance: str | None = None,
) -> None:
    backend = RuntimeMemoryBackend(_pinned_mem_root(data_root, pin), pin.character_id)
    backend.record_event(
        RuntimeEvent(
            event_id=event_id,
            subject_id=pin.character_id,
            session_id=session_id,
            event_type=event_type,
            meaning=meaning,
            created_at="2026-01-01T00:00:00+00:00",
            provenance=provenance,
        )
    )
    backend.close()


def _write_registry(data_root: Path, rows: list) -> None:
    (data_root / "companion_sessions.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _pinned_row(session_id: str, pin: SessionCharacterPinV1) -> dict:
    return {
        "session_id": session_id,
        "character_id": pin.character_id,
        "purpose": "COMPANION",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "label": "pinned",
        "activity_seq": 1,
        "character_pin_v1": pin.to_json(),
    }


def _assert_no_pinned_storage(data_root: Path, pin: SessionCharacterPinV1) -> None:
    root = data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id()
    assert not (root / "memory").exists()
    assert not (root / "state").exists()


def _poison_factory(monkeypatch, service):
    monkeypatch.setattr(
        service,
        "_dialogue_factory",
        lambda: (_ for _ in ()).throw(AssertionError("provider factory resolved")),
    )


# --------------------------------------------------------------------------- #
# valid pinned co-author context
# --------------------------------------------------------------------------- #
def test_A_valid_pinned_coauthor_resolves_exact_definition(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    ctx = service._coauthor_context(session.session_id)
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}
    assert ctx["visible_history"] == []
    assert ctx["user_memory_block"] is None


def test_B_pinned_coauthor_uses_definition_display_name_not_catalog(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    definition = service.resolve_pinned_definition(session.session_id)
    captured = []
    monkeypatch.setattr(
        service,
        "_require_character",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("catalog lookup used for pinned co-author")
        ),
    )
    monkeypatch.setattr(
        service,
        "_scene_for_display_name",
        lambda row, display_name: captured.append(display_name),
    )
    ctx = service._coauthor_context(session.session_id)
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}
    assert captured == [definition.display_name]


def test_C_pinned_coauthor_user_memory_reads_real_pinned_events(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    _write_event(
        data_root, pin, "cmp-other-session", "evt-1",
        "я живу в Москве", provenance="USER_STATED",
    )
    ctx = service._coauthor_context(session.session_id)
    # Other-session USER_STATED event in the SAME pinned namespace is visible.
    assert ctx["user_memory_block"] == "- [со слов пользователя] я живу в Москве"
    # Current-session history is empty (event belongs to another session).
    assert ctx["visible_history"] == []


def test_D_current_session_user_stated_excluded(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    _write_event(
        data_root, pin, session.session_id, "evt-1",
        "current session statement", provenance="USER_STATED",
    )
    ctx = service._coauthor_context(session.session_id)
    assert ctx["user_memory_block"] is None


def test_E_non_user_stated_provenance_excluded(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    _write_event(
        data_root, pin, "cmp-other", "evt-1", "plain user message", provenance=None,
    )
    ctx = service._coauthor_context(session.session_id)
    assert ctx["user_memory_block"] is None


def test_F_two_releases_isolated_user_memory(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)  # release v1
    src2 = make_crp_package(
        tmp_path, dirname="src2", character_id="alice", release_id="v2",
        package_id="pkg-alice-v2",
    )
    CharacterPackageManagementService(data_root).import_package(src2)
    hash2, rt2 = _resolve_ids(src2, "alice", "v2")
    session2 = service.create_pinned_session(
        ExactCharacterSelectionV1("alice", "v2", hash2, rt2)
    )

    _write_event(
        data_root, selection.to_pin(), "cmp-other-v1", "evt-1",
        "v1 memory", provenance="USER_STATED",
    )
    # Release v2 co-author must NOT see release v1 USER_STATED memory.
    ctx2 = service._coauthor_context(session2.session_id)
    assert ctx2["user_memory_block"] is None


def test_G_wrong_package_hash_fails_closed_before_storage_and_provider(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad = SessionCharacterPinV1(
        pin.character_id, pin.release_id, "0" * 64, pin.runtime_definition_hash
    )
    sid = "cmp-bad-ph"
    _write_registry(data_root, [_pinned_row(sid, bad)])
    _poison_factory(monkeypatch, service)
    with pytest.raises(CompanionError) as exc:
        service._coauthor_context(sid)
    assert exc.value.code == "package_identity_mismatch"
    _assert_no_pinned_storage(data_root, bad)


def test_H_wrong_runtime_definition_hash_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad = SessionCharacterPinV1(
        pin.character_id, pin.release_id, pin.package_hash, "0" * 64
    )
    sid = "cmp-bad-rth"
    _write_registry(data_root, [_pinned_row(sid, bad)])
    _poison_factory(monkeypatch, service)
    with pytest.raises(CompanionError) as exc:
        service._coauthor_context(sid)
    assert exc.value.code == "runtime_definition_mismatch"
    _assert_no_pinned_storage(data_root, bad)


def test_I_package_missing_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    importer = CharacterPackageImportService(data_root)
    shutil.rmtree(importer.installed_path(pin.character_id, pin.release_id))
    _poison_factory(monkeypatch, service)
    with pytest.raises(CompanionError) as exc:
        service._coauthor_context(session.session_id)
    assert exc.value.code == "package_missing"
    _assert_no_pinned_storage(data_root, pin)


# --------------------------------------------------------------------------- #
# legacy unchanged + still-blocked paths + message contract
# --------------------------------------------------------------------------- #
def test_J_legacy_coauthor_unchanged(tmp_path):
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=tmp_path / "companion-data",
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
    )
    session = svc.create_session("kira")
    ctx = svc._coauthor_context(session.session_id)
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}
    assert ctx["visible_history"] == []
    assert ctx["user_memory_block"] is None


def test_K_no_dimension_semantics_in_pinned_coauthor(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    ctx = service._coauthor_context(session.session_id)
    # S8C2: dimension semantics are NOT part of the co-author context, even
    # though the resolved synthetic definition carries a dimension set.
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}
    assert "dimension_definitions" not in ctx
    assert "dimensions" not in ctx


def test_L_pinned_image_remains_blocked(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    with pytest.raises(CompanionError) as exc:
        service.create_image_job(session.session_id, kind="custom", prompt="x")
    assert exc.value.code == "pinned_execution_blocked"


def test_M_pinned_visibility_hidden_remains_blocked(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    with pytest.raises(CompanionError) as exc:
        service.set_message_visibility(session.session_id, 1, hidden=True)
    assert exc.value.code == "pinned_execution_blocked"


def test_N_guard_message_no_longer_claims_enabled_ops_blocked(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    with pytest.raises(CompanionError) as exc:
        service.create_image_job(session.session_id, kind="custom", prompt="x")
    assert exc.value.code == "pinned_execution_blocked"
    msg = exc.value.message
    assert "dialogue" not in msg
    assert "history" not in msg
    assert "co-author" not in msg


def test_O_metadata_side_effect_free(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    meta = service.get_session(session.session_id)
    assert meta.character_id == pin.character_id
    listed = service.list_sessions(pin.character_id)
    assert [s.session_id for s in listed] == [session.session_id]
    _assert_no_pinned_storage(data_root, pin)
