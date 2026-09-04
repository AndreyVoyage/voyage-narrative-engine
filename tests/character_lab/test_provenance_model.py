#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PART Q -- runtime-memory provenance, Beta v1 non-leak (offline, fake provider)."""

from __future__ import annotations

import json
from pathlib import Path

from services.character_lab import CharacterLabApp, provenance
from services.character_runtime import RuntimeMemoryBackend

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _fake_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def _make_app(tmp_path):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        provider_factory=_fake_provider_factory(),
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        provider_availability="CONFIGURED",
    )


def _causal_events(app):
    backend = RuntimeMemoryBackend(app._current_workspace().memory_root, "kira")
    try:
        return backend.load_events_causal("kira")
    finally:
        backend.close()


class TestTaxonomy:
    def test_only_four_v1_categories(self):
        assert set(provenance.V1_PROVENANCE) == {
            "USER_STATED", "CHARACTER_UTTERANCE", "SCENE_SETUP", "LEGACY_UNCLASSIFIED",
        }

    def test_no_category_is_established_fact(self):
        for cat in provenance.V1_PROVENANCE:
            assert provenance.is_established_fact(cat) is False

    def test_normalize_unknown_and_none_to_legacy(self):
        assert provenance.normalize(None) == "LEGACY_UNCLASSIFIED"
        assert provenance.normalize("MODEL_HYPOTHESIS") == "LEGACY_UNCLASSIFIED"
        assert provenance.normalize("USER_STATED") == "USER_STATED"


class TestChatTurnProvenance:
    def test_user_then_character_with_expected_provenance_and_seq(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Привет, Кира.")
        events = _causal_events(app)
        assert [e.event_type for e in events] == ["USER_MESSAGE", "CHARACTER_MESSAGE"]
        assert [e.provenance for e in events] == ["USER_STATED", "CHARACTER_UTTERANCE"]
        user, char = events
        assert user.seq is not None and char.seq is not None
        assert user.seq < char.seq

    def test_memory_inspector_shows_same_causal_order(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Первый вопрос.")
        mem = app.memory()
        assert mem["causal_order"] == "seq"
        rows = mem["events"]
        assert [r["event_type"] for r in rows] == ["USER_MESSAGE", "CHARACTER_MESSAGE"]
        assert [r["provenance"] for r in rows] == ["USER_STATED", "CHARACTER_UTTERANCE"]
        assert rows[0]["seq"] < rows[1]["seq"]


class TestBetaV1NonLeak:
    def test_provenance_and_seq_absent_from_provider_request(self, tmp_path):
        app = _make_app(tmp_path)
        # prior-session memory so a memory line is rendered into the prompt
        backend = RuntimeMemoryBackend(app._current_workspace().memory_root, "kira")
        try:
            from services.character_runtime import RuntimeEvent
            backend.record_event(RuntimeEvent(
                event_id="evt-prior", subject_id="kira", session_id="s-earlier",
                event_type="USER_MESSAGE", meaning="Я люблю зелёный чай.",
                created_at="2026-08-20T00:00:00+00:00",
            ))
            backend.set_provenance("evt-prior", "USER_STATED")
        finally:
            backend.close()

        r = app.chat("Что я люблю?")
        detail = app.turn_detail(r["turn_id"])
        raw = detail["request"]["raw"]
        assert "Я люблю зелёный чай." in raw  # memory line delivered
        assert "USER_STATED" not in raw
        assert "CHARACTER_UTTERANCE" not in raw
        assert "provenance" not in raw
        assert "\"seq\"" not in raw
        # manifest memory-line item renders only [event_type] meaning
        mem_items = [i for i in detail["manifest"]["items"] if i["kind"] == "system.memory_line"]
        assert mem_items and mem_items[0]["text"] == "- [USER_MESSAGE] Я люблю зелёный чай."

    def test_event_type_strings_unchanged(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Привет.")
        events = _causal_events(app)
        assert {e.event_type for e in events} == {"USER_MESSAGE", "CHARACTER_MESSAGE"}
