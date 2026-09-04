#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime State v1 -- workspace isolation, truth boundary, Grounded v2, API.

Offline only. Runtime State is created ONLY by an explicit operator action;
nothing here promotes memory / model output / Scene into state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_lab import (
    BetaV1CurrentPolicy,
    GroundedV2Policy,
    KIRA_GROUNDED_V2,
    RuntimeService,
    TurnCapture,
    verify_segment_delivered,
)
from services.character_lab.app import CharacterLabApp
from services.character_lab.runtime_policy import _GROUNDED_V2_STATE_HEADER
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import RuntimeEvent, RuntimeMemoryBackend, load_accepted_character
from services.character_runtime.state import RuntimeStateBackend

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
_WEB = _REPO_ROOT / "services" / "character_lab" / "web"

STATE_VALUE_MARKER = "ГородТекущегоСостоянияХ7"
REMOVED_VALUE_MARKER = "УдаляемоеЗначениеZ9"


def _recording_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake", "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
            return response
        return provider
    return factory


def _service():
    loader = build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT)
    return RuntimeService(acceptance_root=_ACCEPTED_ROOT, source_loader=loader)


def _make_app(tmp_path, sub="data"):
    return CharacterLabApp(
        acceptance_root=_ACCEPTED_ROOT,
        data_root=tmp_path / sub,
        provider_factory=_recording_provider_factory(),
        provider_info={"provider_id": "p", "model": "m"},
        provider_availability="CONFIGURED",
    )


def _grounded_turn(tmp_path, *, state_root=None, scene=None, memory_root=None, turn_id="turn-s1"):
    service = _service()
    cap = TurnCapture(tmp_path / ("cap-" + turn_id))
    result = service.turn(
        "kira", policy=GroundedV2Policy(), history=[], user_message="Расскажи о себе.",
        provider=None, provider_factory=_recording_provider_factory(),
        memory_root=memory_root or (tmp_path / ("mem-" + turn_id)),
        state_root=state_root, capture=cap, turn_id=turn_id,
        provider_info={"provider_id": "p", "model": "m"}, scene=scene,
    )
    return cap, result


def _sys_text(messages):
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


# --------------------------------------------------------------------- workspace

class TestWorkspaceIsolation:
    def test_clean_test_and_normal_are_isolated(self, tmp_path):
        app = _make_app(tmp_path)
        # default workspace is a fresh CLEAN_TEST
        assert app.runtime_state()["current"] == []
        app.select_workspace("normal")
        app.runtime_state_set({"key": "living.city", "value": "NormalCity"})
        assert [e["value"] for e in app.runtime_state()["current"]] == ["NormalCity"]
        r = app.new_clean_test()
        assert r["workspace_kind"] == "CLEAN_TEST"
        assert app.runtime_state()["current"] == []  # clean test sees nothing
        app.select_workspace("normal")
        assert [e["value"] for e in app.runtime_state()["current"]] == ["NormalCity"]

    def test_new_clean_test_has_empty_state(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"key": "k", "value": "v"})
        assert app.runtime_state()["current_count"] == 1
        app.new_clean_test()
        st = app.runtime_state()
        assert st["current"] == [] and st["event_count"] == 0

    def test_workspace_switch_does_not_copy_state(self, tmp_path):
        app = _make_app(tmp_path)
        first_ws = app.loaded_state()["workspace_id"]
        app.runtime_state_set({"key": "a.b", "value": "one"})
        second = app.new_clean_test()["workspace_id"]
        app.runtime_state_set({"key": "c.d", "value": "two"})
        assert [e["key"] for e in app.runtime_state()["current"]] == ["c.d"]
        app.select_workspace(first_ws)
        assert [e["key"] for e in app.runtime_state()["current"]] == ["a.b"]
        app.select_workspace(second)
        assert [e["key"] for e in app.runtime_state()["current"]] == ["c.d"]


# ------------------------------------------------------------------ truth boundary

class TestTruthBoundary:
    def _seed_memory(self, root):
        b = RuntimeMemoryBackend(root, "kira")
        try:
            for eid, etype, meaning, prov in [
                ("m-user", "USER_MESSAGE", "Я живу в Париже.", "USER_STATED"),
                ("m-char", "CHARACTER_MESSAGE", "У меня есть игуана Нора.", "CHARACTER_UTTERANCE"),
                ("m-legacy", "USER_MESSAGE", "Старая незанесённая запись.", None),
            ]:
                b.record_event(RuntimeEvent(
                    event_id=eid, subject_id="kira", session_id="s-prior",
                    event_type=etype, meaning=meaning,
                    created_at="2026-08-10T00:00:00+00:00"), provenance=prov)
        finally:
            b.close()

    def test_no_memory_or_model_or_scene_auto_creates_state(self, tmp_path):
        app = _make_app(tmp_path)
        mem_root = app._current_workspace().memory_root
        self._seed_memory(mem_root)
        app.select_variant(KIRA_GROUNDED_V2)
        app.set_scene({"title": "T", "location": "L", "participants": ["A"],
                       "prior_events": [], "current_situation": "now"})
        r = app.chat("Привет.")
        assert r["ok"] is True
        st = app.runtime_state()
        assert st["current"] == []            # USER_STATED / CHARACTER_UTTERANCE / LEGACY
        assert st["event_count"] == 0          # provider response persisted to memory, not state
        assert st["automatic_promotion"] is False
        # memory row still exists and is untouched
        mem = app.memory()
        kinds = {e["provenance"] for e in mem["events"]}
        assert "CHARACTER_UTTERANCE" in kinds

    def test_state_only_appears_after_explicit_operator_action(self, tmp_path):
        app = _make_app(tmp_path)
        assert app.runtime_state()["current"] == []
        app.runtime_state_set({"key": "living.city", "value": "Prague"})
        assert [e["value"] for e in app.runtime_state()["current"]] == ["Prague"]


# --------------------------------------------------------------------- grounded v2

class TestGroundedV2StateSegment:
    def test_empty_state_no_segment(self, tmp_path):
        cap, _ = _grounded_turn(tmp_path, state_root=None, turn_id="turn-empty")
        kinds = [i["kind"] for i in cap.read_manifest("turn-empty")["items"]]
        assert "system.runtime_state" not in kinds
        assert "system.runtime_state_line" not in kinds

    def test_nonempty_state_segment_selected_and_delivered(self, tmp_path):
        sroot = tmp_path / "st"
        b = RuntimeStateBackend(sroot, "kira")
        try:
            b.record_set(key="living.city", value=STATE_VALUE_MARKER)
            b.record_set(key="current.project", value="alpha")
        finally:
            b.close()
        cap, result = _grounded_turn(tmp_path, state_root=sroot, turn_id="turn-state")
        manifest = cap.read_manifest("turn-state")
        items = {i["kind"] for i in manifest["items"]}
        assert "system.runtime_state" in items
        line_items = [i for i in manifest["items"] if i["kind"] == "system.runtime_state_line"]
        assert len(line_items) == 2
        # order: role_instruction, package_grounding, runtime_state, ...
        kinds_seq = [i["kind"] for i in manifest["items"]]
        assert kinds_seq.index("system.package_grounding") < kinds_seq.index("system.runtime_state")

        request_text = (cap.turn_dir("turn-state") / "request.json").read_text("utf-8")
        assert _GROUNDED_V2_STATE_HEADER in request_text
        assert STATE_VALUE_MARKER in request_text
        state_item = next(i for i in manifest["items"] if i["kind"] == "system.runtime_state")
        assert verify_segment_delivered(segment_text=state_item["text"], request_body_text=request_text)
        for li in line_items:
            assert verify_segment_delivered(segment_text=li["text"], request_body_text=request_text)
        # honest text about not rewriting the package
        assert "не переписыв" in _sys_text(result.messages)

    def test_removed_fact_is_not_delivered(self, tmp_path):
        sroot = tmp_path / "st2"
        b = RuntimeStateBackend(sroot, "kira")
        try:
            b.record_set(key="keep.key", value="KeptValue")
            b.record_set(key="drop.key", value=REMOVED_VALUE_MARKER)
            b.record_remove(key="drop.key")
        finally:
            b.close()
        cap, _ = _grounded_turn(tmp_path, state_root=sroot, turn_id="turn-rm")
        request_text = (cap.turn_dir("turn-rm") / "request.json").read_text("utf-8")
        assert "KeptValue" in request_text
        assert REMOVED_VALUE_MARKER not in request_text
        line_items = [i for i in cap.read_manifest("turn-rm")["items"]
                      if i["kind"] == "system.runtime_state_line"]
        assert len(line_items) == 1 and "keep.key" in line_items[0]["text"]

    def test_beta_v1_never_gets_state_segment(self, tmp_path):
        sroot = tmp_path / "st3"
        b = RuntimeStateBackend(sroot, "kira")
        try:
            b.record_set(key="living.city", value=STATE_VALUE_MARKER)
        finally:
            b.close()
        service = _service()
        cap = TurnCapture(tmp_path / "cap-beta")
        service.turn("kira", policy=BetaV1CurrentPolicy(), history=[], user_message="Привет.",
                     provider=None, provider_factory=_recording_provider_factory(),
                     memory_root=tmp_path / "mem-beta", state_root=sroot,
                     capture=cap, turn_id="turn-beta",
                     provider_info={"provider_id": "p", "model": "m"})
        manifest = cap.read_manifest("turn-beta")
        kinds = [i["kind"] for i in manifest["items"]]
        assert "system.runtime_state" not in kinds
        assert "system.runtime_state_line" not in kinds
        request_text = (cap.turn_dir("turn-beta") / "request.json").read_text("utf-8")
        assert _GROUNDED_V2_STATE_HEADER not in request_text
        assert STATE_VALUE_MARKER not in request_text

    def test_beta_v1_policy_ignores_runtime_state_key(self, tmp_path):
        acc = load_accepted_character(
            "kira", acceptance_root=_ACCEPTED_ROOT,
            source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT))
        base = {
            "subject_id": "kira", "source_candidate_hash": acc.source_candidate_hash,
            "package_id": acc.package.package_id, "package_version": acc.package.package_version,
            "package_status": acc.package.status.value, "runtime_memory": [],
        }
        aug = dict(base)
        aug["runtime_state"] = [{"domain": "FACT", "key": "living.city", "value": "X", "seq": 1}]
        p = BetaV1CurrentPolicy()
        a = p.assemble_context(runtime_context=base, session_id="s", history=[], user_message="hi")
        c = p.assemble_context(runtime_context=aug, session_id="s", history=[], user_message="hi")
        assert list(a.messages) == list(c.messages)
        assert a.manifest == c.manifest

    def test_package_and_scene_stay_separate_segments(self, tmp_path):
        app = _make_app(tmp_path)
        app.select_variant(KIRA_GROUNDED_V2)
        app.runtime_state_set({"key": "living.city", "value": STATE_VALUE_MARKER})
        app.set_scene({"title": "T", "location": "L", "participants": ["A"],
                       "prior_events": [], "current_situation": "СценаМаркер"})
        r = app.chat("Привет.")
        detail = app.turn_detail(r["turn_id"])
        kinds = [i["kind"] for i in detail["manifest"]["items"]]
        assert "system.package_grounding" in kinds
        assert "system.runtime_state" in kinds
        assert "system.scene" in kinds
        pkg = next(i for i in detail["manifest"]["items"] if i["kind"] == "system.package_grounding")
        st = next(i for i in detail["manifest"]["items"] if i["kind"] == "system.runtime_state")
        sc = next(i for i in detail["manifest"]["items"] if i["kind"] == "system.scene")
        assert pkg["delivered"] and st["delivered"] and sc["delivered"]
        assert STATE_VALUE_MARKER not in pkg["text"] and "СценаМаркер" not in st["text"]


# ------------------------------------------------------------------------- api/ui

class TestApiAndUi:
    def test_state_mode_present_in_ui(self):
        html = (_WEB / "index.html").read_text(encoding="utf-8")
        assert 'data-mode="state"' in html
        assert "Состояние" in html
        js = (_WEB / "app.js").read_text(encoding="utf-8")
        assert "loadRuntimeState" in js
        assert "/api/runtime-state" in js

    def test_state_can_be_listed(self, tmp_path):
        app = _make_app(tmp_path)
        st = app.runtime_state()
        assert st["current"] == []
        assert st["domains_active"] == ["FACT"]
        assert "history" in st

    def test_operator_set_works(self, tmp_path):
        app = _make_app(tmp_path)
        r = app.runtime_state_set({"key": "employment.status", "value": "employed", "source_ref": "note"})
        assert r["ok"] is True and r["action"] == "SET"
        assert r["event"]["key"] == "employment.status"
        assert r["source_ref_status"] == "unverified_annotation"
        cur = app.runtime_state()["current"]
        assert len(cur) == 1 and cur[0]["value"] == "employed"
        assert cur[0]["source_kind"] == "OPERATOR_CONFIRMED"

    def test_operator_remove_appends_removal(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"key": "k", "value": "v"})
        r = app.runtime_state_remove({"key": "k"})
        assert r["ok"] is True and r["action"] == "REMOVE" and r["was_present"] is True
        st = app.runtime_state()
        assert st["current"] == []
        assert st["event_count"] == 2
        assert [h["action"] for h in st["history"]] == ["SET", "REMOVE"]

    def test_source_ref_matched_against_workspace(self, tmp_path):
        app = _make_app(tmp_path)
        mem_root = app._current_workspace().memory_root
        b = RuntimeMemoryBackend(mem_root, "kira")
        try:
            b.record_event(RuntimeEvent(
                event_id="evt-real", subject_id="kira", session_id="s",
                event_type="USER_MESSAGE", meaning="x",
                created_at="2026-08-10T00:00:00+00:00"), provenance="USER_STATED")
        finally:
            b.close()
        r = app.runtime_state_set({"key": "k", "value": "v", "source_ref": "evt-real"})
        assert r["source_ref_status"] == "matched_memory_event"

    def test_no_arbitrary_path_accepted(self, tmp_path):
        app = _make_app(tmp_path)
        target_ws = app._current_workspace().state_root
        # extra 'root'/'state_root'/'path' keys are ignored; backend resolves ws itself
        app.runtime_state_set({"key": "k", "value": "v", "state_root": "/etc",
                               "root": str(tmp_path / "evil"), "path": "../../x"})
        # data landed only in the current workspace ledger
        assert (target_ws / "runtime_state.sqlite3").exists()
        assert not (tmp_path / "evil").exists()
        assert not Path("/etc/runtime_state.sqlite3").exists()
        cur = app.runtime_state()["current"]
        assert len(cur) == 1 and cur[0]["key"] == "k"

    def test_no_automatic_promotion_surface(self):
        server = (_REPO_ROOT / "tools" / "character_lab_server.py").read_text(encoding="utf-8")
        js = (_WEB / "app.js").read_text(encoding="utf-8")
        html = (_WEB / "index.html").read_text(encoding="utf-8")
        # no promotion / extraction endpoint or action anywhere
        for blob in (server, js, html):
            low = blob.lower()
            for forbidden in ("/api/state/promote", "/api/runtime-state/promote",
                              "promote_all", "promote all", "extract_fact",
                              "extract facts", "accept model claim", "accept_claim",
                              "auto_promot"):
                assert forbidden not in low, forbidden
        # server exposes exactly the three explicit runtime-state routes
        assert server.count('"/api/runtime-state') == 3
        assert '"/api/runtime-state"' in server
        assert '"/api/runtime-state/set"' in server
        assert '"/api/runtime-state/remove"' in server

    def test_domains_relationship_psychology_not_active(self, tmp_path):
        app = _make_app(tmp_path)
        r = app.runtime_state_set({"key": "k", "value": "v", "domain": "RELATIONSHIP"})
        assert r["ok"] is False
        r = app.runtime_state_set({"key": "k", "value": "v", "domain": "PSYCHOLOGY"})
        assert r["ok"] is False
        assert app.runtime_state()["domains_active"] == ["FACT"]
