#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHARACTER COMPANION APP MVP V1 -- backend service.

Offline only: deterministic fake provider, temp workspace, no network, no
Accepted Package writes. Proves the MVP user flow end to end plus durability,
isolation, and error handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_companion import (
    CompanionCatalog,
    CompanionCharacterEntry,
    CompanionError,
    CompanionProviderError,
    CompanionService,
    build_default_catalog,
)
from services.character_runtime import RuntimeEvent, RuntimeMemoryBackend

from tests.character_companion.conftest import (
    ACCEPTED_ROOT,
    FAKE_PROVIDER_INFO,
    FAKE_REPLY,
    make_fake_factory,
    make_failing_factory,
)


def _service(tmp_path, *, factory=None, catalog=None, data_root=None):
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "companion-data"),
        provider_factory=factory or make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
        catalog=catalog,
    )


# ------------------------------------------------------------ catalog (1, 2, 15)
def test_01_accepted_kira_appears_in_catalog(tmp_path):
    svc = _service(tmp_path)
    ids = [c.character_id for c in svc.list_characters()]
    assert ids == ["kira"]
    kira = svc.list_characters()[0]
    assert kira.available and kira.subject_id == "kira"
    assert kira.package_id and kira.source_hash            # resolved from accepted package


def test_02_non_accepted_candidate_does_not_become_available(tmp_path):
    # a synthetic entry that never resolved an accepted package
    synthetic = CompanionCharacterEntry(
        character_id="not-accepted", display_name="X", subject_id="not-accepted",
        available=False,
    )
    catalog = build_default_catalog(ACCEPTED_ROOT, extra=(synthetic,))
    svc = _service(tmp_path, catalog=catalog)
    assert [c.character_id for c in svc.list_characters()] == ["kira"]
    with pytest.raises(CompanionError) as exc:
        svc.create_session("not-accepted")
    assert exc.value.code == "unknown_character"


def test_15_unknown_character_rejected(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(CompanionError) as exc:
        svc.create_session("nobody")
    assert exc.value.code == "unknown_character"
    with pytest.raises(CompanionError):
        svc.list_sessions("nobody")


# ------------------------------------------------------- sessions (3, 4, 5, 16)
def test_03_04_create_companion_session(tmp_path):
    svc = _service(tmp_path)
    session = svc.create_session("kira")
    assert session.session_id.startswith("cmp-")
    assert session.character_id == "kira"
    assert session.purpose == "COMPANION"
    assert session.label and session.created_at
    listed = svc.list_sessions("kira")
    assert [s.session_id for s in listed] == [session.session_id]


def test_05_session_list_persists_across_backend_reopen(tmp_path):
    data_root = tmp_path / "companion-data"
    s1 = _service(tmp_path, data_root=data_root)
    a = s1.create_session("kira")
    b = s1.create_session("kira")
    del s1
    s2 = _service(tmp_path, data_root=data_root)
    assert {s.session_id for s in s2.list_sessions("kira")} == {a.session_id, b.session_id}


def test_16_unknown_session_rejected(tmp_path):
    svc = _service(tmp_path)
    with pytest.raises(CompanionError) as exc:
        svc.get_messages("cmp-does-not-exist")
    assert exc.value.code == "unknown_session"
    with pytest.raises(CompanionError):
        svc.send_message("cmp-does-not-exist", "привет")


# --------------------------------------------- chat + persistence (6..11, 14)
def test_06_07_08_09_send_receive_persist_order(tmp_path):
    svc = _service(tmp_path)
    session = svc.create_session("kira")
    assert svc.get_messages(session.session_id) == ()          # new history is empty

    turn1 = svc.send_message(session.session_id, "Привет, Кира.")
    assert turn1.response == FAKE_REPLY
    roles = [(m.role, m.text) for m in svc.get_messages(session.session_id)]
    assert roles == [("user", "Привет, Кира."), ("character", FAKE_REPLY)]

    svc.send_message(session.session_id, "Как дела?")
    hist = svc.get_messages(session.session_id)
    assert [m.role for m in hist] == ["user", "character", "user", "character"]
    assert [m.text for m in hist][:3] == ["Привет, Кира.", FAKE_REPLY, "Как дела?"]
    seqs = [m.seq for m in hist]
    assert seqs == sorted(seqs) and len(set(seqs)) == 4        # strict causal order


def test_10_11_restart_preserves_and_continues_conversation(tmp_path):
    data_root = tmp_path / "companion-data"
    s1 = _service(tmp_path, data_root=data_root)
    session = s1.create_session("kira")
    s1.send_message(session.session_id, "Первое сообщение.")
    s1.send_message(session.session_id, "Второе сообщение.")
    before = [(m.role, m.text) for m in s1.get_messages(session.session_id)]
    assert len(before) == 4
    del s1

    s2 = _service(tmp_path, data_root=data_root)
    assert session.session_id in {s.session_id for s in s2.list_sessions("kira")}
    assert [(m.role, m.text) for m in s2.get_messages(session.session_id)] == before

    s2.send_message(session.session_id, "Третье сообщение после перезапуска.")
    after = s2.get_messages(session.session_id)
    assert len(after) == 6
    assert after[4].role == "user" and after[4].text == "Третье сообщение после перезапуска."
    assert after[5].role == "character"
    assert [m.seq for m in after] == sorted(m.seq for m in after)


def test_14_empty_message_rejected(tmp_path):
    svc = _service(tmp_path)
    session = svc.create_session("kira")
    for bad in ("", "   ", "\n\t"):
        with pytest.raises(CompanionError) as exc:
            svc.send_message(session.session_id, bad)
        assert exc.value.code == "empty_message"
    assert svc.get_messages(session.session_id) == ()          # nothing persisted


# ---------------------------------------------------- isolation (12, 13)
def test_12_character_session_isolation(tmp_path):
    synthetic = CompanionCharacterEntry(
        character_id="synthetic-b", display_name="B", subject_id="synthetic-b",
        available=True,   # visible for listing, but only KIRA is chat-capable
    )
    catalog = build_default_catalog(ACCEPTED_ROOT, extra=(synthetic,))
    svc = _service(tmp_path, catalog=catalog)
    a = svc.create_session("kira")
    b = svc.create_session("synthetic-b")
    assert [s.session_id for s in svc.list_sessions("kira")] == [a.session_id]
    assert [s.session_id for s in svc.list_sessions("synthetic-b")] == [b.session_id]


def test_13_foreign_session_events_not_surfaced_as_companion_conversation(tmp_path):
    svc = _service(tmp_path)
    session = svc.create_session("kira")
    svc.send_message(session.session_id, "Настоящее сообщение.")

    # a Character Lab TESTING/AUTHORING turn would carry a different session_id;
    # even written into the same memory root it must not appear in this
    # Companion conversation, and it is not in the Companion session registry.
    char_mem = tmp_path / "companion-data" / "characters" / "kira" / "memory"
    backend = RuntimeMemoryBackend(char_mem, "kira")
    try:
        backend.record_event(
            RuntimeEvent(
                event_id="lab-evt-1", subject_id="kira", session_id="lab-testing-999",
                event_type="USER_MESSAGE", meaning="ЛАБОРАТОРНОЕ сообщение",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            provenance="USER_STATED",
        )
    finally:
        backend.close()

    texts = [m.text for m in svc.get_messages(session.session_id)]
    assert "ЛАБОРАТОРНОЕ сообщение" not in texts
    assert [s.session_id for s in svc.list_sessions("kira")] == [session.session_id]


# ---------------------------------------- provider / runtime reuse (17..20)
def test_17_provider_failure_leaves_prior_history_intact(tmp_path):
    data_root = tmp_path / "companion-data"
    ok = _service(tmp_path, data_root=data_root)
    session = ok.create_session("kira")
    ok.send_message(session.session_id, "Сообщение до сбоя.")
    prior = [(m.role, m.text) for m in ok.get_messages(session.session_id)]
    assert len(prior) == 2

    broken = _service(tmp_path, data_root=data_root, factory=make_failing_factory())
    with pytest.raises(CompanionProviderError) as exc:
        broken.send_message(session.session_id, "Это упадёт.")
    assert exc.value.code == "provider_failed"
    assert [(m.role, m.text) for m in broken.get_messages(session.session_id)] == prior


def test_18_no_internal_events_rendered_as_chat(tmp_path):
    svc = _service(tmp_path)
    session = svc.create_session("kira")
    svc.send_message(session.session_id, "Проверка типов событий.")
    for m in svc.get_messages(session.session_id):
        assert m.role in ("user", "character")                 # never system/grounding/epistemic


def test_19_reuses_existing_runtime_memory_path(tmp_path):
    data_root = tmp_path / "companion-data"
    svc = _service(tmp_path, data_root=data_root)
    session = svc.create_session("kira")
    svc.send_message(session.session_id, "Привет.")
    char_mem = data_root / "characters" / "kira" / "memory"
    backend = RuntimeMemoryBackend(char_mem, "kira")
    try:
        events = backend.load_events_causal("kira")
    finally:
        backend.close()
    kinds = [(e.event_type, e.provenance) for e in events]
    assert ("USER_MESSAGE", "USER_STATED") in kinds
    assert ("CHARACTER_MESSAGE", "CHARACTER_UTTERANCE") in kinds
    # state root is the ordinary runtime-state location, not a bespoke store
    assert (data_root / "characters" / "kira" / "state").is_dir()


def test_20_provider_abstraction_exercised_not_bypassed(tmp_path):
    factory = make_fake_factory()
    svc = _service(tmp_path, factory=factory)
    session = svc.create_session("kira")
    svc.send_message(session.session_id, "Привет.")
    assert len(factory.calls) == 1                             # the injected provider was called
    # the provider received an assembled message list (system grounding + user)
    messages = factory.calls[0]
    assert any(m.get("role") == "user" and m.get("content") == "Привет." for m in messages)
    assert any(m.get("role") == "system" for m in messages)
