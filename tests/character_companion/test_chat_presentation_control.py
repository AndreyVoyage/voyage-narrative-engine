#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT CONTROL AND COMPOSER ASSISTANT V1 -- durable PRESENTATION metadata.

CORE INVARIANT:  UI HISTORY != ACTIVE CHARACTER MEMORY != LONG-TERM MEMORY.
Hiding a chat or a message, or renaming a chat, changes only presentation
metadata in the Companion session registry. No Memory event is deleted, updated
or filtered from Runtime retrieval; Runtime State, generated media and the
Character Package are untouched. Offline, deterministic fake provider.
"""

from __future__ import annotations

import json

import pytest

from services.character_companion import (
    CompanionError,
    CompanionService,
    CompanionTransport,
    InMemoryCredentialVault,
    SettingsStore,
)
from services.character_runtime import RuntimeMemoryBackend

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory


def _service(tmp_path, data_root=None):
    dr = data_root or (tmp_path / "cd")
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT, data_root=dr,
        provider_factory=make_fake_factory("Ответ Киры."), provider_info=FAKE_PROVIDER_INFO,
        settings_store=SettingsStore(dr), credential_vault=InMemoryCredentialVault(),
    )


def _events(data_root, character_id="kira"):
    backend = RuntimeMemoryBackend(data_root / "characters" / character_id / "memory", character_id)
    try:
        return list(backend.load_events_causal(character_id))
    finally:
        backend.close()


def _seed(svc):
    s = svc.create_session("kira", title="Seed")
    svc.send_message(s.session_id, "первое")
    svc.send_message(s.session_id, "второе")
    return s.session_id


# --------------------------------------------------------------- rename
def test_rename_persists_and_falls_back(tmp_path):
    svc = _service(tmp_path)
    sid = _seed(svc)
    out = svc.rename_session(sid, "  Вечерний разговор  ")
    assert out.title_override == "Вечерний разговор"
    assert svc.get_session(sid).title_override == "Вечерний разговор"
    # empty -> clears the override, automatic label still available
    cleared = svc.rename_session(sid, "   ")
    assert cleared.title_override is None
    assert cleared.label  # automatic label untouched


def test_rename_does_not_touch_memory_or_scene(tmp_path):
    svc = _service(tmp_path)
    sid = _seed(svc)
    before = [(e.event_type, e.meaning, e.seq) for e in _events(tmp_path / "cd")]
    svc.rename_session(sid, "Новое имя")
    assert [(e.event_type, e.meaning, e.seq) for e in _events(tmp_path / "cd")] == before
    assert svc.get_session(sid).scene is None  # scene facts unchanged


# --------------------------------------------------------------- hide message
def test_hide_message_is_presentation_only(tmp_path):
    svc = _service(tmp_path)
    sid = _seed(svc)
    msgs = svc.get_messages(sid)
    target = msgs[0].seq
    before_events = [(e.event_type, e.meaning, e.seq) for e in _events(tmp_path / "cd")]

    out = svc.set_message_visibility(sid, target, True)
    assert target in out.hidden_message_ids

    # underlying event log is byte-for-byte the same set
    assert [(e.event_type, e.meaning, e.seq) for e in _events(tmp_path / "cd")] == before_events
    # get_messages (UI history read) still returns every message -- Runtime
    # retrieval is NEVER filtered by hidden ids
    assert svc.get_messages(sid) == msgs

    # unhide restores rendering eligibility
    restored = svc.set_message_visibility(sid, target, False)
    assert target not in restored.hidden_message_ids


def test_hide_message_rejects_unknown_seq(tmp_path):
    svc = _service(tmp_path)
    sid = _seed(svc)
    with pytest.raises(CompanionError) as e:
        svc.set_message_visibility(sid, 999999, True)
    assert e.value.code == "unknown_message"


def test_hidden_message_id_survives_restart(tmp_path):
    dr = tmp_path / "cd"
    svc = _service(tmp_path, data_root=dr)
    sid = _seed(svc)
    target = svc.get_messages(sid)[1].seq
    svc.set_message_visibility(sid, target, True)

    fresh = _service(tmp_path, data_root=dr)   # brand-new instance, same data root
    assert target in fresh.get_session(sid).hidden_message_ids
    assert len(fresh.get_messages(sid)) == 4   # full history intact (2 turns)


# --------------------------------------------------------------- hide chat
def test_hide_chat_keeps_everything_underneath(tmp_path):
    svc = _service(tmp_path)
    sid = _seed(svc)
    before_events = [(e.event_type, e.meaning) for e in _events(tmp_path / "cd")]

    hidden = svc.set_session_visibility(sid, True)
    assert hidden.hidden is True
    # the session row still exists and history is intact
    assert svc.get_session(sid).session_id == sid
    assert len(svc.get_messages(sid)) == 4
    assert [(e.event_type, e.meaning) for e in _events(tmp_path / "cd")] == before_events
    # list_sessions still returns it (React filters on `hidden`); nothing deleted
    assert any(s.session_id == sid for s in svc.list_sessions("kira"))

    restored = svc.set_session_visibility(sid, False)
    assert restored.hidden is False


def test_hidden_chat_persists_across_restart(tmp_path):
    dr = tmp_path / "cd"
    sid = _seed(_service(tmp_path, data_root=dr))
    _service(tmp_path, data_root=dr).set_session_visibility(sid, True)
    assert _service(tmp_path, data_root=dr).get_session(sid).hidden is True


# --------------------------------------------------------------- compatibility
def test_backward_compatible_session_row_without_presentation(tmp_path):
    dr = tmp_path / "cd"
    dr.mkdir(parents=True, exist_ok=True)
    (dr / "companion_sessions.json").write_text(json.dumps([{
        "session_id": "cmp-legacy-1", "character_id": "kira", "purpose": "COMPANION",
        "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
        "label": "Диалог от 2026-01-01 00:00:00", "activity_seq": 1,
    }]), encoding="utf-8")
    svc = _service(tmp_path, data_root=dr)
    s = svc.get_session("cmp-legacy-1")
    assert s.title_override is None and s.hidden is False and s.hidden_message_ids == ()


def test_no_physical_delete_of_history_or_session(tmp_path):
    dr = tmp_path / "cd"
    svc = _service(tmp_path, data_root=dr)
    sid = _seed(svc)
    reg_before = json.loads((dr / "companion_sessions.json").read_text(encoding="utf-8"))
    ev_before = len(_events(dr))

    svc.set_session_visibility(sid, True)
    svc.set_message_visibility(sid, svc.get_messages(sid)[0].seq, True)
    svc.rename_session(sid, "x")

    reg_after = json.loads((dr / "companion_sessions.json").read_text(encoding="utf-8"))
    assert len(reg_after) == len(reg_before) == 1          # session row still there
    assert reg_after[0]["session_id"] == sid
    assert "presentation" in reg_after[0]                  # metadata added, additively
    assert len(_events(dr)) == ev_before                   # no ledger truncation


# --------------------------------------------------------------- transport
def test_transport_presentation_roundtrip(tmp_path):
    t = CompanionTransport(_service(tmp_path))
    sid = _seed(t._service)  # noqa: SLF001 -- test seeding only
    msgs = t.get_messages(sid)["messages"]
    seq = msgs[0]["seq"]

    r1 = t.rename_session({"sessionId": sid, "title": "Переименованный"})
    assert r1["titleOverride"] == "Переименованный"
    r2 = t.set_message_visibility({"sessionId": sid, "messageId": seq, "hidden": True})
    assert seq in r2["hiddenMessageIds"]
    r3 = t.set_session_visibility({"sessionId": sid, "hidden": True})
    assert r3["hidden"] is True
    r4 = t.set_session_visibility({"sessionId": sid, "hidden": False})
    assert r4["hidden"] is False
    # message history endpoint still returns everything
    assert len(t.get_messages(sid)["messages"]) == 4
