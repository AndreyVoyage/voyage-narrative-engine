#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8C1 adversarial tests: pinned text-runtime wiring + pinned history read.

Offline only: synthetic Package V1 fixtures under temp dirs, stubbed runtime
seam, no live provider, no network, no production path.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

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
from services.character_companion.character_import.package_importer import (
    CharacterPackageImportService,
)
from services.character_companion.session_character import (
    ExactCharacterSelectionV1,
    SessionCharacterPinV1,
)
from services.character_runtime import AcceptedCharacter

from tests.character_companion.conftest import (
    ACCEPTED_ROOT,
    FAKE_PROVIDER_INFO,
    FAKE_REPLY,
    make_fake_factory,
)
from tests.character_companion.test_session_character_pinning import (
    _resolve_ids,
    _setup_pinned,
    _synthetic_catalog,
    make_crp_package,
)


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


def _pinned_session(tmp_path):
    service, selection, data_root, src = _setup_pinned(tmp_path)
    session = service.create_pinned_session(selection)
    return service, selection, session, data_root, src


def _stub_resolved_turn(service, monkeypatch):
    """Stub the resolved seam; record calls; return a deterministic result."""
    calls = []

    def fake(accepted, subject_id, **kwargs):
        calls.append((accepted, subject_id, kwargs))
        return SimpleNamespace(response="ok")

    monkeypatch.setattr(service._runtime, "turn_with_resolved_character", fake)
    return calls


def _turn_sentinels(service, monkeypatch):
    """Sentinel both turn paths; raise if either is ever invoked."""
    calls = []

    def boom(*a, **k):
        calls.append(k)
        raise AssertionError("runtime turn was invoked for an invalid path")

    monkeypatch.setattr(service._runtime, "turn", boom)
    monkeypatch.setattr(service._runtime, "turn_with_resolved_character", boom)
    return calls


def _assert_no_pinned_storage(data_root: Path, pin: SessionCharacterPinV1) -> None:
    root = data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id()
    assert not (root / "memory").exists()
    assert not (root / "state").exists()
    assert not (root / "memory" / "runtime_memory.sqlite3").exists()
    assert not (root / "state" / "runtime_state.sqlite3").exists()


# --------------------------------------------------------------------------- #
# valid pinned text-runtime wiring
# --------------------------------------------------------------------------- #
def test_A_valid_pinned_reaches_resolved_seam(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    expected_root = data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id()
    calls = _stub_resolved_turn(service, monkeypatch)
    turn = service.send_message(session.session_id, "Hello")
    assert turn.response == "ok"
    assert len(calls) == 1
    accepted, subject_id, kwargs = calls[0]
    assert isinstance(accepted, AcceptedCharacter)
    assert subject_id == pin.character_id
    assert kwargs["memory_root"] == expected_root / "memory"
    assert kwargs["state_root"] == expected_root / "state"
    assert kwargs["session_id"] == session.session_id


def test_B_pinned_uses_package_v1_candidate_not_legacy_loader(tmp_path, monkeypatch):
    import services.character_lab.runtime_service as rs

    service, selection, session, data_root, src = _pinned_session(tmp_path)
    sentinel = []
    monkeypatch.setattr(rs, "load_accepted_character", lambda *a, **k: sentinel.append(1))
    calls = _stub_resolved_turn(service, monkeypatch)
    service.send_message(session.session_id, "Hello")
    assert sentinel == []
    accepted, subject_id, kwargs = calls[0]
    assert accepted.package.package_id == "pkg-alice-v1"


def test_C_pinned_uses_package_v1_dimensions(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    definition = service.resolve_pinned_definition(session.session_id)
    calls = _stub_resolved_turn(service, monkeypatch)
    service.send_message(session.session_id, "Hello")
    assert calls[0][2]["dimension_set"] == definition.dimension_semantics.dimension_set


def test_E_two_releases_distinct_roots(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    src2 = make_crp_package(
        tmp_path, dirname="src2", character_id="alice", release_id="v2",
        package_id="pkg-alice-v2",
    )
    CharacterPackageManagementService(data_root).import_package(src2)
    hash2, rt2 = _resolve_ids(src2, "alice", "v2")
    session2 = service.create_pinned_session(
        ExactCharacterSelectionV1("alice", "v2", hash2, rt2)
    )
    roots = []

    def fake(accepted, subject_id, **kwargs):
        roots.append((kwargs["memory_root"], kwargs["state_root"]))
        return SimpleNamespace(response="ok")

    monkeypatch.setattr(service._runtime, "turn_with_resolved_character", fake)
    service.send_message(session.session_id, "a")
    service.send_message(session2.session_id, "b")
    assert roots[0][0] != roots[1][0]
    assert roots[0][1] != roots[1][1]


def test_R_runtime_definition_hash_change_keeps_namespace(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin1 = SessionCharacterPinV1("alice", "v1", selection.package_hash, "1" * 64)
    pin2 = SessionCharacterPinV1("alice", "v1", selection.package_hash, "2" * 64)
    assert pin1.storage_namespace_id() == pin2.storage_namespace_id()


# --------------------------------------------------------------------------- #
# fail-closed pinned execution
# --------------------------------------------------------------------------- #
def test_F_wrong_package_hash_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad = SessionCharacterPinV1(
        pin.character_id, pin.release_id, "0" * 64, pin.runtime_definition_hash
    )
    sid = "session-bad-ph"
    _write_registry(data_root, [_pinned_row(sid, bad)])
    calls = _turn_sentinels(service, monkeypatch)
    with pytest.raises(CompanionError) as exc:
        service.send_message(sid, "hi")
    assert exc.value.code == "package_identity_mismatch"
    assert calls == []
    _assert_no_pinned_storage(data_root, bad)


def test_G_wrong_runtime_definition_hash_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad = SessionCharacterPinV1(
        pin.character_id, pin.release_id, pin.package_hash, "0" * 64
    )
    sid = "session-bad-rth"
    _write_registry(data_root, [_pinned_row(sid, bad)])
    calls = _turn_sentinels(service, monkeypatch)
    with pytest.raises(CompanionError) as exc:
        service.send_message(sid, "hi")
    assert exc.value.code == "runtime_definition_mismatch"
    assert calls == []
    _assert_no_pinned_storage(data_root, bad)


def test_H_package_missing_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    importer = CharacterPackageImportService(data_root)
    shutil.rmtree(importer.installed_path(pin.character_id, pin.release_id))
    calls = _turn_sentinels(service, monkeypatch)
    with pytest.raises(CompanionError) as exc:
        service.send_message(session.session_id, "hi")
    assert exc.value.code == "package_missing"
    assert calls == []
    _assert_no_pinned_storage(data_root, pin)


def test_I_malformed_pin_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    calls = _turn_sentinels(service, monkeypatch)
    for i, bad_pin in enumerate(["not-json", {"character_id": "alice"}]):
        row = _pinned_row(f"session-malformed-{i}", selection.to_pin())
        row["character_pin_v1"] = bad_pin
        _write_registry(data_root, [row])
        with pytest.raises(CompanionError) as exc:
            service.send_message(f"session-malformed-{i}", "hi")
        assert exc.value.code == "pin_invalid"
    assert calls == []


def test_J_pin_session_character_mismatch_fails_closed(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad = SessionCharacterPinV1(
        "bob", pin.release_id, pin.package_hash, pin.runtime_definition_hash
    )
    row = _pinned_row("session-mismatch", bad)
    row["character_id"] = "alice"  # session claims alice, pin claims bob
    _write_registry(data_root, [row])
    calls = _turn_sentinels(service, monkeypatch)
    with pytest.raises(CompanionError) as exc:
        service.send_message("session-mismatch", "hi")
    assert exc.value.code == "pin_invalid"
    assert calls == []


def test_S_invalid_definitions_never_begin_provider(tmp_path, monkeypatch):
    # The runtime seam is the ONLY place the provider is ever invoked, so its
    # sentinel proves the provider never begins for invalid definitions.
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    bad_pins = [
        SessionCharacterPinV1(pin.character_id, pin.release_id, "0" * 64, pin.runtime_definition_hash),
        SessionCharacterPinV1(pin.character_id, pin.release_id, pin.package_hash, "0" * 64),
    ]
    for i, bad in enumerate(bad_pins):
        _write_registry(data_root, [_pinned_row(f"session-invalid-{i}", bad)])
    calls = _turn_sentinels(service, monkeypatch)
    for i in range(len(bad_pins)):
        with pytest.raises(CompanionError):
            service.send_message(f"session-invalid-{i}", "hi")
    assert calls == []


# --------------------------------------------------------------------------- #
# legacy unchanged
# --------------------------------------------------------------------------- #
def test_L_legacy_send_message_unchanged(tmp_path, monkeypatch):
    svc = CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=tmp_path / "companion-data",
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
    )
    session = svc.create_session("kira")
    captured = []

    def fake_turn(subject_id, **kwargs):
        captured.append((subject_id, kwargs))
        return SimpleNamespace(response=FAKE_REPLY)

    monkeypatch.setattr(svc._runtime, "turn", fake_turn)
    turn = svc.send_message(session.session_id, "Привет")
    assert turn.response == FAKE_REPLY
    subject_id, kwargs = captured[0]
    assert subject_id == "kira"
    assert kwargs["memory_root"] == svc._char_root("kira") / "memory"
    assert kwargs["state_root"] == svc._char_root("kira") / "state"


def test_M_legacy_runtime_turn_contract_operational(tmp_path):
    from services.character_lab import BetaV1CurrentPolicy, TurnResult
    from tests.character_lab.test_runtime_service import _service as make_runtime_service

    service, package = make_runtime_service(tmp_path)

    def provider(messages):
        return "[KIRA] ответ"

    result = service.turn(
        "kira",
        policy=BetaV1CurrentPolicy(),
        history=[],
        user_message="Привет.",
        provider=provider,
        memory_root=tmp_path / "mem",
    )
    assert isinstance(result, TurnResult)
    assert result.response == "[KIRA] ответ"
    assert len(result.persisted_event_ids) == 2


# --------------------------------------------------------------------------- #
# pinned history read
# --------------------------------------------------------------------------- #
def test_N_pinned_history_resolves_pinned_root(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    expected = (
        data_root / "character_namespaces" / "pinned-v1" / pin.storage_namespace_id() / "memory"
    )
    captured = []
    monkeypatch.setattr(
        service,
        "_read_history",
        lambda memory_root, subject_id, session_id: captured.append(
            (memory_root, subject_id)
        ),
    )
    service.get_messages(session.session_id)
    assert captured == [(expected, pin.character_id)]


def test_O_pinned_history_no_provider(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    calls = []
    monkeypatch.setattr(service, "_dialogue_factory", lambda: calls.append(1))
    result = service.get_messages(session.session_id)
    assert calls == []
    assert result == ()


def test_P_pinned_history_no_package_lookup(tmp_path, monkeypatch):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    calls = []
    monkeypatch.setattr(
        service, "_resolve_exact_definition", lambda *a, **k: calls.append(1)
    )
    result = service.get_messages(session.session_id)
    assert calls == []
    assert result == ()


# --------------------------------------------------------------------------- #
# package removal semantics
# --------------------------------------------------------------------------- #
def test_Q_package_removed_metadata_history_readable_execution_fails(tmp_path):
    from services.character_runtime import RuntimeMemoryBackend
    from services.character_runtime.memory import RuntimeEvent

    service, selection, session, data_root, src = _pinned_session(tmp_path)
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

    importer = CharacterPackageImportService(data_root)
    shutil.rmtree(importer.installed_path(pin.character_id, pin.release_id))

    meta = service.get_session(session.session_id)
    assert meta.character_id == pin.character_id

    msgs = service.get_messages(session.session_id)
    assert [m.text for m in msgs] == ["hello"]

    with pytest.raises(CompanionError) as exc:
        service.send_message(session.session_id, "hi")
    assert exc.value.code == "package_missing"


# --------------------------------------------------------------------------- #
# blocked pinned paths remain blocked
# --------------------------------------------------------------------------- #
def test_T_image_remains_blocked(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    with pytest.raises(CompanionError) as exc:
        service.create_image_job(session.session_id, kind="custom", prompt="x")
    assert exc.value.code == "pinned_execution_blocked"


def test_U_coauthor_context_resolves_pinned(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    # S8C2: pinned co-author is no longer generically blocked; it resolves the
    # exact Package V1 definition and returns a local context snapshot.
    ctx = service._coauthor_context(session.session_id)
    assert set(ctx) == {"visible_history", "scene_text", "user_memory_block"}


def test_V_visibility_hidden_remains_blocked(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    with pytest.raises(CompanionError) as exc:
        service.set_message_visibility(session.session_id, 1, hidden=True)
    assert exc.value.code == "pinned_execution_blocked"


def test_W_pinned_metadata_get_list_storage_side_effect_free(tmp_path):
    service, selection, session, data_root, src = _pinned_session(tmp_path)
    pin = selection.to_pin()
    meta = service.get_session(session.session_id)
    assert meta.character_id == pin.character_id
    listed = service.list_sessions(pin.character_id)
    assert [s.session_id for s in listed] == [session.session_id]
    _assert_no_pinned_storage(data_root, pin)
