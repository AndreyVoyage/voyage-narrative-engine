#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidated Memory v1 -- Grounded v2 integration (offline, NO provider).

Covers: Grounded v2 receives active approved consolidated memory; rejected /
unapproved memory never reaches it; cross-session same-workspace retrieval;
cross-workspace isolation; the raw source event can fall outside the bounded
raw working-context window while the consolidated record stays available; raw +
consolidated working contexts are bounded; SUPERSEDES / CONFLICTS_WITH render
correctly; Beta v1 assembly is byte-unchanged; no Runtime State mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_lab import (
    BetaV1CurrentPolicy,
    GroundedV2Policy,
    RuntimeService,
    TurnCapture,
)
from services.character_lab.runtime_policy import (
    GROUNDED_V2_CONSOLIDATED_MAX_RECORDS,
    GROUNDED_V2_RAW_MEMORY_MAX_EVENTS,
    _GROUNDED_V2_CONSMEM_HEADER,
    _GROUNDED_V2_CONSMEM_LINE_PREFIX,
    _GROUNDED_V2_MEMORY_LINE_PREFIX,
)
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import (
    ConsolidatedMemoryBackend,
    RuntimeEvent,
    RuntimeMemoryBackend,
)
from services.character_runtime.consolidated_memory import (
    DECISION_APPROVE,
    DECISION_REJECT,
    RELATION_CONFLICTS_WITH,
    RELATION_SUPERSEDES,
)
from services.character_runtime.state import RuntimeStateBackend

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
SUBJECT = "kira"
PARTY = "Я терпеть не могу большие шумные вечеринки."
QUESTION = (
    "Как думаешь, куда мне лучше сходить в пятницу — на огромную клубную "
    "вечеринку или куда-нибудь спокойно посидеть?"
)


def _service():
    return RuntimeService(
        acceptance_root=_ACCEPTED_ROOT,
        source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT),
    )


def _fake_factory(response="[KIRA-FAKE] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {
                    "id": "fake", "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
            return response
        return provider
    return factory


def _add(mb, eid, etype, meaning, prov, session_id, ts):
    mb.record_event(
        RuntimeEvent(event_id=eid, subject_id=SUBJECT, session_id=session_id,
                     event_type=etype, meaning=meaning, created_at=ts),
        provenance=prov,
    )


def _grounded_request_text(tmp_path, *, mem_root, state_root=None, policy=None, turn_id="live", user_message=QUESTION):
    cap = TurnCapture(tmp_path / f"cap-{turn_id}")
    _service().turn(
        SUBJECT, policy=policy or GroundedV2Policy(), history=[], user_message=user_message,
        provider=None, provider_factory=_fake_factory(), memory_root=mem_root, state_root=state_root,
        capture=cap, turn_id=turn_id, provider_info={"provider_id": "p", "model": "m"},
    )
    return (cap.turn_dir(turn_id) / "request.json").read_text("utf-8"), cap.read_manifest(turn_id)


def _system_lines(req_text):
    data = json.loads(req_text)
    return "\n".join(m["content"] for m in data["messages"] if m["role"] == "system")


# ---------------------------------------------------------- cross-session proof

class TestCrossSessionAndIsolation:
    def _seed_workspace_a(self, tmp_path):
        mem_a = tmp_path / "wsA" / "mem"
        mb = RuntimeMemoryBackend(mem_a, SUBJECT)
        # SESSION 1: the durable statement (oldest), then many newer eligible
        # events so the original source falls outside the newest-20 raw window.
        _add(mb, "evt-party", "USER_MESSAGE", PARTY, "USER_STATED", "sess-1", "2026-01-01T00:00:00+00:00")
        for i in range(25):
            _add(mb, f"evt-fill-{i:02d}", "USER_MESSAGE", f"Проходное сообщение номер {i}.",
                 "USER_STATED", "sess-1", f"2026-01-02T00:{i:02d}:00+00:00")
        cm = ConsolidatedMemoryBackend(mem_a, SUBJECT)
        cand = cm.propose(memory_backend=mb, source_event_id="evt-party")
        dec = cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="operator:test")
        cm.close()
        mb.close()
        return mem_a, dec.record_id

    def test_session2_same_workspace_has_consolidated_but_not_raw_source(self, tmp_path):
        mem_a, record_id = self._seed_workspace_a(tmp_path)
        req, manifest = _grounded_request_text(tmp_path, mem_root=mem_a, turn_id="s2")
        sys_text = _system_lines(req)

        raw_lines = [l for l in sys_text.splitlines() if l.startswith(_GROUNDED_V2_MEMORY_LINE_PREFIX)]
        cons_lines = [l for l in sys_text.splitlines() if l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)]

        # 1. old raw source event is NOT in the raw working-memory block
        assert not any(PARTY in l for l in raw_lines)
        assert len(raw_lines) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS  # newest 20 of 26

        # 2. approved consolidated record IS present ...
        assert any(PARTY in l for l in cons_lines)
        # 3. ... rendered as a USER_REPORT / remembered user statement
        assert _GROUNDED_V2_CONSMEM_HEADER in sys_text
        line = next(l for l in cons_lines if PARTY in l)
        assert line.startswith("- [USER_REPORT] ")
        assert "не независимо подтверждённые факты" in sys_text  # epistemic honesty

        # 4. manifest proves which consolidated records were delivered
        cm_items = [i for i in manifest["items"] if i["kind"] == "system.consolidated_memory_line"]
        assert len(cm_items) == 1
        assert cm_items[0]["meta"]["record_id"] == record_id
        assert cm_items[0]["meta"]["epistemic_kind"] == "USER_REPORT"
        assert cm_items[0]["meta"]["basis_event_ids"] == ["evt-party"]
        assert cm_items[0]["meta"]["source_event_id"] == "evt-party"

    def test_fresh_workspace_b_does_not_see_workspace_a_memory(self, tmp_path):
        self._seed_workspace_a(tmp_path)
        mem_b = tmp_path / "wsB" / "mem"
        RuntimeMemoryBackend(mem_b, SUBJECT).close()  # fresh, empty
        req, manifest = _grounded_request_text(tmp_path, mem_root=mem_b, turn_id="b")
        sys_text = _system_lines(req)
        assert PARTY not in sys_text
        assert _GROUNDED_V2_CONSMEM_HEADER not in sys_text
        assert not any(i["kind"].startswith("system.consolidated_memory") for i in manifest["items"])

    def test_no_runtime_state_mutation_from_a_consolidated_turn(self, tmp_path):
        mem_a, _ = self._seed_workspace_a(tmp_path)
        state_root = tmp_path / "wsA" / "state"
        RuntimeStateBackend(state_root, SUBJECT).close()
        _grounded_request_text(tmp_path, mem_root=mem_a, state_root=state_root, turn_id="nostate")
        b = RuntimeStateBackend(state_root, SUBJECT)
        try:
            assert b.load_events(SUBJECT) == ()
            assert b.load_current_state(SUBJECT) == ()
        finally:
            b.close()


# ------------------------------------------------ approval gate reaches grounded

class TestApprovalGate:
    def _mem(self, tmp_path, name):
        return tmp_path / name / "mem"

    def test_unapproved_and_rejected_never_reach_grounded(self, tmp_path):
        mem = self._mem(tmp_path, "ws")
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        _add(mb, "e-pending", "USER_MESSAGE", "Ожидающее утверждения.", "USER_STATED", "s1", "2026-01-01T00:00:00+00:00")
        _add(mb, "e-rejected", "USER_MESSAGE", "Отклонённое утверждение.", "USER_STATED", "s1", "2026-01-01T00:01:00+00:00")
        cm = ConsolidatedMemoryBackend(mem, SUBJECT)
        cm.propose(memory_backend=mb, source_event_id="e-pending")  # left pending
        rj = cm.propose(memory_backend=mb, source_event_id="e-rejected")
        cm.decide(candidate_id=rj.candidate_id, decision=DECISION_REJECT)
        cm.close(); mb.close()
        req, manifest = _grounded_request_text(tmp_path, mem_root=mem, turn_id="gate")
        sys_text = _system_lines(req)
        # No consolidated block at all: nothing was APPROVED.
        assert _GROUNDED_V2_CONSMEM_HEADER not in sys_text
        assert not any(i["kind"].startswith("system.consolidated_memory") for i in manifest["items"])
        cons_lines = [l for l in sys_text.splitlines() if l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)]
        assert cons_lines == []
        # (the raw event log still shows them as raw user-reported lines -- that
        # layer is unfiltered by approval; consolidation is the separate gate.)

    def test_character_utterance_cannot_be_promoted(self, tmp_path):
        from services.character_runtime.consolidated_memory import ConsolidatedMemoryError
        mem = self._mem(tmp_path, "wsc")
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        _add(mb, "e-char", "CHARACTER_MESSAGE", "Я родилась в Париже.", "CHARACTER_UTTERANCE", "s1", "2026-01-01T00:00:00+00:00")
        cm = ConsolidatedMemoryBackend(mem, SUBJECT)
        with pytest.raises(ConsolidatedMemoryError):
            cm.propose(memory_backend=mb, source_event_id="e-char")
        cm.close(); mb.close()


# ------------------------------------------------------ supersede / conflict view

class TestSupersedeAndConflictRendering:
    def _rc(self, records):
        return {
            "accepted_package": None, "source_candidate_hash": "h",
            "runtime_memory": [], "causal_memory": [], "runtime_state": [],
            "consolidated_memory": records,
        }

    def test_superseded_record_absent_from_grounded_block(self, tmp_path):
        mem = tmp_path / "m"
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        _add(mb, "e-msk", "USER_MESSAGE", "Я родился в Москве.", "USER_STATED", "s1", "2026-01-01T00:00:00+00:00")
        _add(mb, "e-tula", "USER_MESSAGE", "Нет, я родился в Туле.", "USER_STATED", "s2", "2026-01-02T00:00:00+00:00")
        cm = ConsolidatedMemoryBackend(mem, SUBJECT)
        old = cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="e-msk").candidate_id, decision=DECISION_APPROVE)
        cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="e-tula").candidate_id,
                  decision=DECISION_APPROVE, relations=[(RELATION_SUPERSEDES, old.record_id)])
        cm.close(); mb.close()
        req, manifest = _grounded_request_text(tmp_path, mem_root=mem, turn_id="sup")
        sys_text = _system_lines(req)
        cons = [l for l in sys_text.splitlines() if l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)]
        assert any("Туле" in l for l in cons)
        assert not any("Москве" in l for l in cons)      # superseded -> not in active view
        assert len([i for i in manifest["items"] if i["kind"] == "system.consolidated_memory_line"]) == 1

    def test_conflict_pair_both_present_with_marker(self, tmp_path):
        mem = tmp_path / "m2"
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        _add(mb, "e-cat", "USER_MESSAGE", "У меня есть кот.", "USER_STATED", "s1", "2026-01-01T00:00:00+00:00")
        _add(mb, "e-nocat", "USER_MESSAGE", "У меня нет животных.", "USER_STATED", "s2", "2026-01-02T00:00:00+00:00")
        cm = ConsolidatedMemoryBackend(mem, SUBJECT)
        a = cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="e-cat").candidate_id, decision=DECISION_APPROVE)
        cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="e-nocat").candidate_id,
                  decision=DECISION_APPROVE, relations=[(RELATION_CONFLICTS_WITH, a.record_id)])
        cm.close(); mb.close()
        req, manifest = _grounded_request_text(tmp_path, mem_root=mem, turn_id="conf")
        sys_text = _system_lines(req)
        cons = [l for l in sys_text.splitlines() if l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)]
        assert any("кот" in l for l in cons) and any("нет животных" in l for l in cons)
        assert sum("ПРОТИВОРЕЧИЕ" in l for l in cons) == 2       # both flagged, unresolved
        block = next(i for i in manifest["items"] if i["kind"] == "system.consolidated_memory")
        assert block["meta"]["conflict_count"] == 2


# --------------------------------------------------------------------- bounds

class TestBounds:
    def test_raw_working_context_is_bounded(self, tmp_path):
        mem = tmp_path / "mb"
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        for i in range(40):
            _add(mb, f"e-{i:02d}", "USER_MESSAGE", f"Событие {i}.", "USER_STATED", "s1", f"2026-01-01T00:{i:02d}:00+00:00")
        mb.close()
        req, _ = _grounded_request_text(tmp_path, mem_root=mem, turn_id="rawbound")
        raw = [l for l in _system_lines(req).splitlines() if l.startswith(_GROUNDED_V2_MEMORY_LINE_PREFIX)]
        assert len(raw) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS
        assert "Событие 39." in "\n".join(raw) and "Событие 0." not in "\n".join(raw)  # newest kept

    def test_consolidated_context_is_bounded(self, tmp_path):
        mem = tmp_path / "mc"
        mb = RuntimeMemoryBackend(mem, SUBJECT)
        cm = ConsolidatedMemoryBackend(mem, SUBJECT)
        for i in range(GROUNDED_V2_CONSOLIDATED_MAX_RECORDS + 5):
            eid = f"e-{i:02d}"
            _add(mb, eid, "USER_MESSAGE", f"Долгосрочный факт {i}.", "USER_STATED", "s1", f"2026-01-01T00:{i:02d}:00+00:00")
            cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id=eid).candidate_id, decision=DECISION_APPROVE)
        cm.close(); mb.close()
        req, _ = _grounded_request_text(tmp_path, mem_root=mem, turn_id="consbound")
        cons = [l for l in _system_lines(req).splitlines() if l.startswith(_GROUNDED_V2_CONSMEM_LINE_PREFIX)]
        assert len(cons) == GROUNDED_V2_CONSOLIDATED_MAX_RECORDS
        assert "Долгосрочный факт 24." in "\n".join(cons)  # newest kept
        assert "Долгосрочный факт 0." not in "\n".join(cons)


# ---------------------------------------------------------------- beta unchanged

class TestBetaUnchanged:
    def test_beta_v1_assembly_byte_identical_with_consolidated_key(self, tmp_path):
        from services.character_runtime import load_accepted_character
        acc = load_accepted_character(
            SUBJECT, acceptance_root=_ACCEPTED_ROOT,
            source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT))
        base = {
            "subject_id": SUBJECT, "source_candidate_hash": acc.source_candidate_hash,
            "package_id": acc.package.package_id, "package_version": acc.package.package_version,
            "package_status": acc.package.status.value, "runtime_memory": [],
        }
        aug = dict(base)
        aug["consolidated_memory"] = [
            {"record_id": "memrec-x", "source_event_id": "e1", "basis_event_ids": ["e1"],
             "memory_kind": "SEMANTIC", "epistemic_kind": "USER_REPORT", "provenance": "USER_STATED",
             "meaning": PARTY, "seq": 1, "in_conflict": False},
        ]
        p = BetaV1CurrentPolicy()
        a = p.assemble_context(runtime_context=base, session_id="s", history=[], user_message="привет")
        b = p.assemble_context(runtime_context=aug, session_id="s", history=[], user_message="привет")
        assert list(a.messages) == list(b.messages)
        assert a.manifest == b.manifest
