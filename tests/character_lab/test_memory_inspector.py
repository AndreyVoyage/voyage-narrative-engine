#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PART T + PART G -- live Memory Inspector / STORED-LOADED-SELECTED-DELIVERED."""

from __future__ import annotations

import json
from pathlib import Path

from services.character_lab import CharacterLabApp
from services.character_runtime import RuntimeEvent, RuntimeMemoryBackend

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _fake_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {"choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
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


def _seed_prior(app, meaning="Я живу у моря."):
    backend = RuntimeMemoryBackend(app._current_workspace().memory_root, "kira")
    try:
        backend.record_event(RuntimeEvent(
            event_id="evt-prior", subject_id="kira", session_id="s-earlier",
            event_type="USER_MESSAGE", meaning=meaning,
            created_at="2026-08-10T00:00:00+00:00",
        ))
        backend.set_provenance("evt-prior", "USER_STATED")
    finally:
        backend.close()


class TestOrderingAndProvenance:
    def test_endpoint_uses_causal_seq_order(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("A")
        app.chat("B")
        mem = app.memory()
        seqs = [r["seq"] for r in mem["events"]]
        assert seqs == sorted(seqs)
        assert mem["causal_order"] == "seq"

    def test_provenance_serialized_honestly(self, tmp_path):
        app = _make_app(tmp_path)
        _seed_prior(app)
        app.chat("Привет.")
        rows = {r["event_id"]: r for r in app.memory()["events"]}
        assert rows["evt-prior"]["provenance"] == "USER_STATED"
        new_user = [r for r in rows.values() if r["event_type"] == "USER_MESSAGE" and r["event_id"] != "evt-prior"][0]
        assert new_user["provenance"] == "USER_STATED"
        new_char = [r for r in rows.values() if r["event_type"] == "CHARACTER_MESSAGE"][0]
        assert new_char["provenance"] == "CHARACTER_UTTERANCE"

    def test_legacy_unclassified_serialized_honestly(self, tmp_path):
        app = _make_app(tmp_path)
        backend = RuntimeMemoryBackend(app._current_workspace().memory_root, "kira")
        try:
            backend.record_event(RuntimeEvent(
                event_id="evt-legacy", subject_id="kira", session_id="s0",
                event_type="CHARACTER_MESSAGE", meaning="без происхождения",
                created_at="2026-08-01T00:00:00+00:00",
            ))
        finally:
            backend.close()
        row = [r for r in app.memory()["events"] if r["event_id"] == "evt-legacy"][0]
        assert row["provenance"] == "LEGACY_UNCLASSIFIED"
        # non-persisted display hint only
        assert row["provenance_display_hint"] == "CHARACTER_UTTERANCE"


class TestStoredLoadedSelectedDelivered:
    def test_without_turn_selected_and_delivered_are_unknown(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Привет.")
        rows = app.memory()["events"]
        for r in rows:
            assert r["stored"] is True
            assert r["loaded"] is True
            assert r["selected"] is None      # -> UI renders UNKNOWN / —
            assert r["delivered"] is None

    def test_with_turn_selected_and_delivered_from_artifact(self, tmp_path):
        app = _make_app(tmp_path)
        _seed_prior(app, meaning="Уникальный факт про море.")
        r = app.chat("Расскажи обо мне.")
        mem = app.memory(turn_id=r["turn_id"])
        prior = [e for e in mem["events"] if e["event_id"] == "evt-prior"][0]
        # prior-session line is selected by Beta v1 and mechanically delivered
        assert prior["selected"] is True
        assert prior["delivered"] is True
        # the CURRENT-turn events are stored but were not part of THIS request
        current = [e for e in mem["events"] if e["event_id"] != "evt-prior"]
        assert current and all(e["selected"] is False for e in current)
        assert all(e["delivered"] is False for e in current)

    def test_no_fake_truth_or_confidence_fields(self, tmp_path):
        app = _make_app(tmp_path)
        app.chat("Привет.")
        blob = json.dumps(app.memory(), ensure_ascii=False).lower()
        for forbidden in ("confidence", "truth_score", "hallucination", "risk"):
            assert forbidden not in blob


class TestLiveUpdate:
    def test_memory_updates_after_each_turn(self, tmp_path):
        app = _make_app(tmp_path)
        assert app.memory()["event_count"] == 0
        app.chat("Один.")
        assert app.memory()["event_count"] == 2
        app.chat("Два.")
        assert app.memory()["event_count"] == 4
