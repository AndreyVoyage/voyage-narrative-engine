#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relationship + Psychology Evolution v1 -- numeric domains on Runtime State.

Offline only. Evolution is explicit / deterministic / operator-driven; nothing
here lets memory, model output, Scene, or Accepted Package claims mutate a
RELATIONSHIP or PSYCHOLOGY value.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.character_lab import (
    BetaV1CurrentPolicy,
    GroundedV2Policy,
    KIRA_GROUNDED_V2,
    RuntimeService,
    TurnCapture,
    verify_segment_delivered,
)
from services.character_lab.app import CharacterLabApp
from services.character_lab.runtime_policy import (
    _GROUNDED_V2_PSY_HEADER,
    _GROUNDED_V2_REL_HEADER,
    _GROUNDED_V2_STATE_HEADER,
)
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import (
    RuntimeEvent,
    RuntimeMemoryBackend,
    load_accepted_character,
)
from services.character_runtime.state import RuntimeStateBackend

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
_WEB = _REPO_ROOT / "services" / "character_lab" / "web"

REL_MARKER_VALUE = "37"
PSY_MARKER_VALUE = "41"
FACT_MARKER = "ФактМаркерX7"


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


def _make_app(tmp_path):
    return CharacterLabApp(
        acceptance_root=_ACCEPTED_ROOT,
        data_root=tmp_path / "data",
        provider_factory=_recording_provider_factory(),
        provider_info={"provider_id": "p", "model": "m"},
        provider_availability="CONFIGURED",
    )


def _grounded_turn(tmp_path, *, state_root=None, scene=None, turn_id="turn-e1"):
    service = _service()
    cap = TurnCapture(tmp_path / ("cap-" + turn_id))
    result = service.turn(
        "kira", policy=GroundedV2Policy(),
        history=[], user_message="Расскажи о себе.", provider=None,
        provider_factory=_recording_provider_factory(),
        memory_root=tmp_path / ("mem-" + turn_id), state_root=state_root,
        capture=cap, turn_id=turn_id, provider_info={"provider_id": "p", "model": "m"},
        scene=scene,
    )
    return cap, result


def _seed_state(root, rows):
    b = RuntimeStateBackend(root, "kira")
    try:
        for domain, key, value in rows:
            b.record_set(key=key, value=value, domain=domain)
    finally:
        b.close()


def _request_text(cap, turn_id):
    return (cap.turn_dir(turn_id) / "request.json").read_text("utf-8")


# --------------------------------------------------------------- truth boundary

class TestTruthBoundary:
    def _seed_memory(self, root):
        b = RuntimeMemoryBackend(root, "kira")
        try:
            for eid, etype, meaning, prov in [
                ("m-user", "USER_MESSAGE", "Я теперь тебе полностью доверяю.", "USER_STATED"),
                ("m-char", "CHARACTER_MESSAGE", "Мой стресс сейчас очень высокий.", "CHARACTER_UTTERANCE"),
                ("m-legacy", "USER_MESSAGE", "старая запись", None),
            ]:
                b.record_event(RuntimeEvent(
                    event_id=eid, subject_id="kira", session_id="s-prior",
                    event_type=etype, meaning=meaning,
                    created_at="2026-08-10T00:00:00+00:00"), provenance=prov)
        finally:
            b.close()

    def test_memory_scene_model_do_not_evolve_numeric_state(self, tmp_path):
        app = _make_app(tmp_path)
        self._seed_memory(app._current_workspace().memory_root)
        app.select_variant(KIRA_GROUNDED_V2)
        app.set_scene({"title": "T", "location": "L", "participants": ["Андрей"],
                       "prior_events": [], "current_situation": "напряжённый разговор о доверии"})
        assert app.chat("Ты мне доверяешь больше теперь?")["ok"] is True
        st = app.runtime_state()
        assert [e for e in st["current"] if e["domain"] in ("RELATIONSHIP", "PSYCHOLOGY")] == []
        assert st["automatic_evolution"] is False

    def test_accepted_package_load_creates_no_evolution_state(self, tmp_path):
        app = _make_app(tmp_path)
        app.character_inspector()
        app.loaded_state()
        st = app.runtime_state()
        assert st["current"] == [] and st["event_count"] == 0


# ------------------------------------------------------------------- workspace

class TestWorkspaceIsolation:
    def test_clean_normal_isolated_new_clean_empty(self, tmp_path):
        app = _make_app(tmp_path)
        assert app.runtime_state()["current"] == []
        app.select_workspace("normal")
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "50"})
        app.runtime_state_set({"domain": "PSYCHOLOGY", "key": "stress", "value": "20"})
        assert app.runtime_state()["current_count"] == 2
        app.new_clean_test()
        st = app.runtime_state()
        assert st["current"] == [] and st["event_count"] == 0
        app.select_workspace("normal")
        doms = {(e["domain"], e["key"]): e["value"] for e in app.runtime_state()["current"]}
        assert doms[("RELATIONSHIP", "andrey.trust")] == "50"
        assert doms[("PSYCHOLOGY", "stress")] == "20"


# ------------------------------------------------------------------- grounded v2

class TestGroundedV2:
    def test_segments_absent_when_empty(self, tmp_path):
        cap, _ = _grounded_turn(tmp_path, state_root=None, turn_id="turn-empty")
        kinds = [i["kind"] for i in cap.read_manifest("turn-empty")["items"]]
        assert "system.relationship_state" not in kinds
        assert "system.psychology_state" not in kinds

    def test_segments_selected_delivered_ordered(self, tmp_path):
        sroot = tmp_path / "st"
        _seed_state(sroot, [
            ("FACT", "living.city", "Prague"),
            ("RELATIONSHIP", "andrey.trust", REL_MARKER_VALUE),
            ("RELATIONSHIP", "andrey.tension", "-12"),
            ("PSYCHOLOGY", "stress", PSY_MARKER_VALUE),
        ])
        cap, result = _grounded_turn(tmp_path, state_root=sroot, turn_id="turn-ev")
        manifest = cap.read_manifest("turn-ev")
        kinds = [i["kind"] for i in manifest["items"]]
        for k in ("system.runtime_state", "system.relationship_state", "system.psychology_state"):
            assert k in kinds
        assert (kinds.index("system.package_grounding")
                < kinds.index("system.runtime_state")
                < kinds.index("system.relationship_state")
                < kinds.index("system.psychology_state"))
        assert len([i for i in manifest["items"] if i["kind"] == "system.relationship_state_line"]) == 2
        assert len([i for i in manifest["items"] if i["kind"] == "system.psychology_state_line"]) == 1

        req = _request_text(cap, "turn-ev")
        assert _GROUNDED_V2_REL_HEADER in req and _GROUNDED_V2_PSY_HEADER in req
        assert f"andrey.trust: {REL_MARKER_VALUE}" in req
        assert f"stress: {PSY_MARKER_VALUE}" in req
        rel_item = next(i for i in manifest["items"] if i["kind"] == "system.relationship_state")
        psy_item = next(i for i in manifest["items"] if i["kind"] == "system.psychology_state")
        assert verify_segment_delivered(segment_text=rel_item["text"], request_body_text=req)
        assert verify_segment_delivered(segment_text=psy_item["text"], request_body_text=req)
        sys_text = "\n".join(m["content"] for m in result.messages if m["role"] == "system")
        assert "не неизменный канон" in sys_text
        pkg = next(i for i in manifest["items"] if i["kind"] == "system.package_grounding")
        assert REL_MARKER_VALUE not in pkg["text"] and PSY_MARKER_VALUE not in pkg["text"]

    def test_removed_numeric_values_not_delivered(self, tmp_path):
        sroot = tmp_path / "rm"
        b = RuntimeStateBackend(sroot, "kira")
        try:
            b.record_set(key="andrey.trust", value="30", domain="RELATIONSHIP")
            b.record_set(key="sergey.tension", value="55", domain="RELATIONSHIP")
            b.record_remove(key="sergey.tension", domain="RELATIONSHIP")
            b.record_set(key="stress", value="22", domain="PSYCHOLOGY")
            b.record_remove(key="stress", domain="PSYCHOLOGY")
        finally:
            b.close()
        cap, _ = _grounded_turn(tmp_path, state_root=sroot, turn_id="turn-rm")
        manifest = cap.read_manifest("turn-rm")
        req = _request_text(cap, "turn-rm")
        assert "andrey.trust: 30" in req
        assert "sergey.tension" not in req
        rel_block = req.split(_GROUNDED_V2_REL_HEADER)[1]
        assert "55" not in rel_block.split("не неизменн")[0]
        assert "system.psychology_state" not in [i["kind"] for i in manifest["items"]]
        assert _GROUNDED_V2_PSY_HEADER not in req

    def test_beta_v1_ignores_numeric_state(self, tmp_path):
        sroot = tmp_path / "beta"
        _seed_state(sroot, [
            ("RELATIONSHIP", "andrey.trust", REL_MARKER_VALUE),
            ("PSYCHOLOGY", "stress", PSY_MARKER_VALUE),
        ])
        service = _service()
        cap = TurnCapture(tmp_path / "cap-beta")
        service.turn("kira", policy=BetaV1CurrentPolicy(), history=[], user_message="Привет.",
                     provider=None, provider_factory=_recording_provider_factory(),
                     memory_root=tmp_path / "mem-beta", state_root=sroot,
                     capture=cap, turn_id="turn-beta",
                     provider_info={"provider_id": "p", "model": "m"})
        kinds = [i["kind"] for i in cap.read_manifest("turn-beta")["items"]]
        assert not any(k.startswith("system.relationship_state") for k in kinds)
        assert not any(k.startswith("system.psychology_state") for k in kinds)
        req = _request_text(cap, "turn-beta")
        assert _GROUNDED_V2_REL_HEADER not in req and _GROUNDED_V2_PSY_HEADER not in req
        assert REL_MARKER_VALUE not in req and PSY_MARKER_VALUE not in req

    def test_beta_v1_policy_ignores_numeric_runtime_state_key(self):
        acc = load_accepted_character(
            "kira", acceptance_root=_ACCEPTED_ROOT,
            source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT))
        base = {
            "subject_id": "kira", "source_candidate_hash": acc.source_candidate_hash,
            "package_id": acc.package.package_id, "package_version": acc.package.package_version,
            "package_status": acc.package.status.value, "runtime_memory": [],
        }
        aug = dict(base)
        aug["runtime_state"] = [
            {"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "30", "seq": 1},
            {"domain": "PSYCHOLOGY", "key": "stress", "value": "25", "seq": 2},
        ]
        p = BetaV1CurrentPolicy()
        a = p.assemble_context(runtime_context=base, session_id="s", history=[], user_message="hi")
        c = p.assemble_context(runtime_context=aug, session_id="s", history=[], user_message="hi")
        assert list(a.messages) == list(c.messages)
        assert a.manifest == c.manifest

    def test_fact_state_still_works_and_package_separate(self, tmp_path):
        sroot = tmp_path / "fact"
        _seed_state(sroot, [
            ("FACT", "living.city", FACT_MARKER),
            ("RELATIONSHIP", "andrey.trust", "10"),
        ])
        cap, _ = _grounded_turn(tmp_path, state_root=sroot, turn_id="turn-fact")
        manifest = cap.read_manifest("turn-fact")
        req = _request_text(cap, "turn-fact")
        assert _GROUNDED_V2_STATE_HEADER in req and FACT_MARKER in req
        fact_item = next(i for i in manifest["items"] if i["kind"] == "system.runtime_state")
        pkg_item = next(i for i in manifest["items"] if i["kind"] == "system.package_grounding")
        assert verify_segment_delivered(segment_text=fact_item["text"], request_body_text=req)
        assert verify_segment_delivered(segment_text=pkg_item["text"], request_body_text=req)
        assert "ACCEPTED CHARACTER GROUNDING" in req
        assert FACT_MARKER not in pkg_item["text"]


# ------------------------------------------------------------------- app / ui

class TestAppAndUi:
    def test_state_ui_has_three_domain_sections(self):
        html = (_WEB / "index.html").read_text(encoding="utf-8")
        for token in ("Факты", "Отношения", "Психология",
                      'id="rel-subject"', 'id="rel-dimension"', 'id="rel-delta"',
                      'id="rel-set"', 'id="rel-adjust"', 'id="rel-remove"',
                      'id="psy-dimension"', 'id="psy-delta"',
                      'id="psy-set"', 'id="psy-adjust"', 'id="psy-remove"'):
            assert token in html, token
        js = (_WEB / "app.js").read_text(encoding="utf-8")
        for fn in ("setRelationship", "adjustRelationship", "removeRelationship",
                   "setPsychology", "adjustPsychology", "removePsychology"):
            assert fn in js, fn
        assert 'postState("adjust"' in js
        server = (_REPO_ROOT / "tools" / "character_lab_server.py").read_text(encoding="utf-8")
        assert '"/api/runtime-state/adjust"' in server

    def test_operator_set_and_adjust_relationship(self, tmp_path):
        app = _make_app(tmp_path)
        assert app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "20"})["ok"]
        r = app.runtime_state_adjust({"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": 10})
        assert r["ok"] and r["previous_value"] == 20 and r["new_value"] == 30
        cur = {(e["domain"], e["key"]): e for e in app.runtime_state()["current"]}
        assert cur[("RELATIONSHIP", "andrey.trust")]["value"] == "30"
        assert cur[("RELATIONSHIP", "andrey.trust")]["value_int"] == 30

    def test_operator_set_and_adjust_psychology_and_range(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "PSYCHOLOGY", "key": "self_control", "value": "60"})
        assert app.runtime_state_adjust({"domain": "PSYCHOLOGY", "key": "self_control", "delta": -25})["new_value"] == 35
        assert app.runtime_state_adjust({"domain": "PSYCHOLOGY", "key": "self_control", "delta": -200})["ok"] is False
        assert app.runtime_state()["current"][0]["value"] == "35"

    def test_adjust_fact_rejected(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"key": "living.city", "value": "Prague"})
        assert app.runtime_state_adjust({"domain": "FACT", "key": "living.city", "delta": 1})["ok"] is False

    def test_remove_then_adjust_rejected(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "10"})
        assert app.runtime_state_remove({"domain": "RELATIONSHIP", "key": "andrey.trust"})["ok"]
        assert app.runtime_state_adjust({"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": 5})["ok"] is False

    def test_history_transition_arrows(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "20"})
        app.runtime_state_adjust({"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": 10})
        hist = [h for h in app.runtime_state()["history"] if h["domain"] == "RELATIONSHIP"]
        assert [h.get("previous_value") for h in hist] == [None, 20]
        assert [h.get("new_value") for h in hist] == [20, 30]

    def test_no_auto_evolve_surface(self):
        server = (_REPO_ROOT / "tools" / "character_lab_server.py").read_text(encoding="utf-8")
        js = (_WEB / "app.js").read_text(encoding="utf-8")
        html = (_WEB / "index.html").read_text(encoding="utf-8")
        for blob in (server, js, html):
            low = blob.lower()
            for forbidden in ("/api/runtime-state/evolve", "auto_evolve", "autoevolve",
                              "infer_relationship", "analyze_sentiment", "sentiment",
                              "auto-progress", "progress_relationship"):
                assert forbidden not in low, forbidden
        assert server.count('"/api/runtime-state') == 4

    def test_no_arbitrary_path_in_adjust(self, tmp_path):
        app = _make_app(tmp_path)
        target = app._current_workspace().state_root
        app.runtime_state_set({"domain": "PSYCHOLOGY", "key": "stress", "value": "10"})
        app.runtime_state_adjust({"domain": "PSYCHOLOGY", "key": "stress", "delta": 5,
                                  "state_root": "/etc", "path": "../../x", "root": str(tmp_path / "evil")})
        assert (target / "runtime_state.sqlite3").exists()
        assert not (tmp_path / "evil").exists()
        assert app.runtime_state()["current"][0]["value"] == "15"


# --------------------------------------------------------------------------
# RELATIONSHIP_ADJUST_BUTTON_FIX
#
# Root cause: both the "Отношения" and "Психология" Δ inputs carry the
# placeholder "напр. +10 или -5", inviting a leading "+". The backend
# (RuntimeStateBackend._coerce_state_int, unchanged) only accepts a canonical
# decimal integer -- no leading "+" -- so an unfixed "+10" silently made
# runtime_state_adjust return ok:false and the UI never advanced past that
# rejected POST: no value change, no new history transition, exactly the
# reported symptom. app.js now strips a redundant leading "+" (normalizeDelta)
# before building the ADJUST payload, for both domains. Backend validation,
# range, and reject-not-clamp semantics are provably unchanged below.
# --------------------------------------------------------------------------

class TestRelationshipAdjustButtonFix:
    def test_app_js_normalizes_delta_for_both_domains(self):
        js = (_WEB / "app.js").read_text(encoding="utf-8")
        assert "function normalizeDelta" in js
        assert 'delta: normalizeDelta($("rel-delta").value)' in js
        assert 'delta: normalizeDelta($("psy-delta").value)' in js

    def test_relationship_adjust_with_leading_plus_delta_now_reaches_40(self, tmp_path):
        """Exact reported scenario: andrey.trust = 30, Δ = "+10" typed in the
        UI's rel-delta field -> after app.js's normalizeDelta() the backend
        receives the canonical delta "10" -> new value 40, with a fresh
        append-only SET transition (30 -> 40) in history."""
        app = _make_app(tmp_path)
        assert app.runtime_state_set(
            {"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "30"}
        )["ok"] is True

        ui_delta_field_value = "+10"           # what the operator actually typed
        sent_delta = ui_delta_field_value.strip()
        if sent_delta.startswith("+"):          # mirrors app.js normalizeDelta()
            sent_delta = sent_delta[1:].strip()
        assert sent_delta == "10"

        r = app.runtime_state_adjust(
            {"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": sent_delta}
        )
        assert r["ok"] is True
        assert r["previous_value"] == 30
        assert r["new_value"] == 40

        cur = {(e["domain"], e["key"]): e for e in app.runtime_state()["current"]}
        assert cur[("RELATIONSHIP", "andrey.trust")]["value"] == "40"
        assert cur[("RELATIONSHIP", "andrey.trust")]["value_int"] == 40

        hist = [h for h in app.runtime_state()["history"] if h["domain"] == "RELATIONSHIP"]
        assert [h["action"] for h in hist] == ["SET", "SET"]          # append-only
        assert [h["value"] for h in hist] == ["30", "40"]             # old event kept
        assert hist[-1]["previous_value"] == 30 and hist[-1]["new_value"] == 40

    def test_raw_unnormalized_plus_delta_still_rejected_by_backend(self, tmp_path):
        """Backend canonical-integer validation is unchanged: a raw "+10"
        (as it would have reached the server before the app.js fix) is still
        rejected, proving this was a frontend formatting gap, not a relaxed
        backend contract."""
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "30"})
        r = app.runtime_state_adjust(
            {"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": "+10"}
        )
        assert r["ok"] is False
        assert app.runtime_state()["current"][0]["value"] == "30"     # state unchanged

    def test_psychology_adjust_still_works_unchanged(self, tmp_path):
        """Preserve the already-working Psychology path (and note it shares
        the exact same "+10" gap, closed by the same normalizeDelta fix)."""
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "PSYCHOLOGY", "key": "stress", "value": "50"})
        sent_delta = "+15"[1:]  # mirrors normalizeDelta("+15") == "15"
        r = app.runtime_state_adjust({"domain": "PSYCHOLOGY", "key": "stress", "delta": sent_delta})
        assert r["ok"] is True and r["previous_value"] == 50 and r["new_value"] == 65

    def test_numeric_range_and_reject_not_clamp_unchanged(self, tmp_path):
        app = _make_app(tmp_path)
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "90"})
        r = app.runtime_state_adjust({"domain": "RELATIONSHIP", "key": "andrey.trust", "delta": "20"})
        assert r["ok"] is False   # 90 + 20 = 110, out of -100..100, rejected not clamped
        assert app.runtime_state()["current"][0]["value"] == "90"
