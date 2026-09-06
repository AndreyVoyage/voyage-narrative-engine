#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidated Memory v1 -- domain layer (offline, no provider).

Covers selection/promotion: eligible USER_STATED -> candidate; CHARACTER_UTTERANCE
rejected; candidate != consolidated; APPROVE creates a verbatim record; REJECT
creates nothing; exact duplicate blocked; provenance + single source event
retained; epistemic kind USER_REPORT retained; SUPERSEDES keeps history but
drops the old record from the active view; CONFLICTS_WITH keeps both, unresolved.
"""

from __future__ import annotations

import pytest

from services.character_runtime import (
    ConsolidatedMemoryBackend,
    ConsolidatedMemoryError,
    RuntimeEvent,
    RuntimeMemoryBackend,
)
from services.character_runtime.consolidated_memory import (
    DECISION_APPROVE,
    DECISION_REJECT,
    EPISTEMIC_USER_REPORT,
    MEMORY_KIND_SEMANTIC,
    RECORD_STATUS_ACTIVE,
    RECORD_STATUS_SUPERSEDED,
    RELATION_CONFLICTS_WITH,
    RELATION_SUPERSEDES,
    normalize_meaning,
)

SUBJECT = "kira"


def _mem(root):
    return RuntimeMemoryBackend(root, SUBJECT)


def _add_event(mb, event_id, event_type, meaning, provenance, session_id="s1", created_at="2026-01-01T00:00:00+00:00"):
    mb.record_event(
        RuntimeEvent(event_id=event_id, subject_id=SUBJECT, session_id=session_id,
                     event_type=event_type, meaning=meaning, created_at=created_at),
        provenance=provenance,
    )


@pytest.fixture()
def wired(tmp_path):
    root = tmp_path / "ws"
    mb = _mem(root)
    _add_event(mb, "evt-user-1", "USER_MESSAGE", "Я терпеть не могу большие шумные вечеринки.", "USER_STATED")
    _add_event(mb, "evt-char-1", "CHARACTER_MESSAGE", "Я родилась в Париже в 1990 году.", "CHARACTER_UTTERANCE")
    _add_event(mb, "evt-legacy-1", "USER_MESSAGE", "старая запись без provenance", None)
    cm = ConsolidatedMemoryBackend(root, SUBJECT)
    yield mb, cm, root
    cm.close()
    mb.close()


# 1
def test_eligible_user_stated_event_becomes_candidate(wired):
    mb, cm, _ = wired
    cand = cm.propose(memory_backend=mb, source_event_id="evt-user-1", memory_kind=MEMORY_KIND_SEMANTIC)
    assert cand.candidate_id.startswith("memcand-")
    assert cand.source_event_id == "evt-user-1"
    assert cand.basis_event_ids == ("evt-user-1",)
    assert cand.epistemic_kind == EPISTEMIC_USER_REPORT
    assert cand.provenance == "USER_STATED"
    assert cand.meaning == "Я терпеть не могу большие шумные вечеринки."  # verbatim
    assert cm.load_candidates()[0].candidate_id == cand.candidate_id


# 2
def test_character_utterance_is_rejected_as_ineligible(wired):
    mb, cm, _ = wired
    with pytest.raises(ConsolidatedMemoryError) as ei:
        cm.propose(memory_backend=mb, source_event_id="evt-char-1")
    assert "utterance" in str(ei.value).lower() or "event_type" in str(ei.value).lower()
    with pytest.raises(ConsolidatedMemoryError):
        cm.propose(memory_backend=mb, source_event_id="evt-legacy-1")  # provenance not USER_STATED
    with pytest.raises(ConsolidatedMemoryError):
        cm.propose(memory_backend=mb, source_event_id="evt-missing")   # missing


# 3
def test_candidate_alone_is_not_consolidated_memory(wired):
    mb, cm, _ = wired
    cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    assert cm.load_active_records() == ()
    assert cm.load_all_records() == ()


# 4
def test_approve_creates_verbatim_active_record(wired):
    mb, cm, _ = wired
    cand = cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    dec = cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="operator:test")
    assert dec.decision == DECISION_APPROVE and dec.record_id is not None
    recs = cm.load_active_records()
    assert len(recs) == 1
    r = recs[0]
    assert r.status == RECORD_STATUS_ACTIVE
    assert r.meaning == "Я терпеть не могу большие шумные вечеринки."       # 7 verbatim
    assert r.epistemic_kind == EPISTEMIC_USER_REPORT                        # 8
    assert r.basis_event_ids == ("evt-user-1",)                            # single source
    assert r.provenance == "USER_STATED"
    assert r.approved_by == "operator:test"
    # decision ledger + candidate both persisted (auditable)
    assert [d.decision for d in cm.load_decisions(cand.candidate_id)] == [DECISION_APPROVE]


# 5
def test_reject_creates_no_record(wired):
    mb, cm, _ = wired
    cand = cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    dec = cm.decide(candidate_id=cand.candidate_id, decision=DECISION_REJECT, decided_by="operator:test", note="not durable")
    assert dec.record_id is None
    assert cm.load_active_records() == () and cm.load_all_records() == ()
    # decision is still auditable
    assert [d.decision for d in cm.load_decisions(cand.candidate_id)] == [DECISION_REJECT]


def test_a_candidate_cannot_be_decided_twice(wired):
    mb, cm, _ = wired
    cand = cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE)
    with pytest.raises(ConsolidatedMemoryError):
        cm.decide(candidate_id=cand.candidate_id, decision=DECISION_REJECT)


# 6
def test_exact_normalized_duplicate_is_blocked(wired):
    mb, cm, root = wired
    c1 = cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    cm.decide(candidate_id=c1.candidate_id, decision=DECISION_APPROVE)
    # a second user event with the same statement (extra whitespace / case)
    _add_event(mb, "evt-user-2", "USER_MESSAGE", "  Я  ТЕРПЕТЬ не могу большие шумные   вечеринки.  ", "USER_STATED", session_id="s2")
    c2 = cm.propose(memory_backend=mb, source_event_id="evt-user-2")
    with pytest.raises(ConsolidatedMemoryError) as ei:
        cm.decide(candidate_id=c2.candidate_id, decision=DECISION_APPROVE)
    assert "duplicate" in str(ei.value).lower()
    assert len(cm.load_active_records()) == 1


# 9
def test_supersedes_keeps_history_but_drops_old_from_active(wired):
    mb, cm, _ = wired
    _add_event(mb, "evt-birth-msk", "USER_MESSAGE", "Я родился в Москве.", "USER_STATED", session_id="s1")
    _add_event(mb, "evt-birth-tula", "USER_MESSAGE", "Нет, я оговорился, я родился в Туле.", "USER_STATED", session_id="s2")
    c_old = cm.propose(memory_backend=mb, source_event_id="evt-birth-msk")
    d_old = cm.decide(candidate_id=c_old.candidate_id, decision=DECISION_APPROVE)
    c_new = cm.propose(memory_backend=mb, source_event_id="evt-birth-tula")
    d_new = cm.decide(candidate_id=c_new.candidate_id, decision=DECISION_APPROVE,
                      relations=[(RELATION_SUPERSEDES, d_old.record_id)])
    active = cm.load_active_records()
    assert [r.record_id for r in active] == [d_new.record_id]              # old gone from active
    all_recs = {r.record_id: r for r in cm.load_all_records()}
    assert d_old.record_id in all_recs                                    # still persisted
    assert all_recs[d_old.record_id].status == RECORD_STATUS_SUPERSEDED
    assert all_recs[d_old.record_id].superseded_by_record_id == d_new.record_id
    assert all_recs[d_old.record_id].meaning == "Я родился в Москве."     # never rewritten
    assert all_recs[d_new.record_id].basis_event_ids == ("evt-birth-tula",)
    # relation is auditable
    rels = cm.load_relations()
    assert len(rels) == 1 and rels[0].kind == RELATION_SUPERSEDES


# 10
def test_conflicts_with_keeps_both_unresolved(wired):
    mb, cm, _ = wired
    _add_event(mb, "evt-cat", "USER_MESSAGE", "У меня есть кот.", "USER_STATED", session_id="s1")
    _add_event(mb, "evt-nocat", "USER_MESSAGE", "У меня нет никаких домашних животных.", "USER_STATED", session_id="s2")
    a = cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="evt-cat").candidate_id,
                  decision=DECISION_APPROVE)
    b = cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="evt-nocat").candidate_id,
                  decision=DECISION_APPROVE, relations=[(RELATION_CONFLICTS_WITH, a.record_id)])
    active = {r.record_id for r in cm.load_active_records()}
    assert active == {a.record_id, b.record_id}          # neither deleted
    conflicted = cm.active_conflict_record_ids()
    assert conflicted == frozenset({a.record_id, b.record_id})  # both flagged, no resolution
    rels = cm.load_relations()
    assert len(rels) == 1 and rels[0].kind == RELATION_CONFLICTS_WITH


def test_relations_only_valid_on_approve(wired):
    mb, cm, _ = wired
    a = cm.decide(candidate_id=cm.propose(memory_backend=mb, source_event_id="evt-user-1").candidate_id,
                  decision=DECISION_APPROVE)
    _add_event(mb, "evt-user-3", "USER_MESSAGE", "Ещё одно утверждение.", "USER_STATED", session_id="s3")
    c3 = cm.propose(memory_backend=mb, source_event_id="evt-user-3")
    with pytest.raises(ConsolidatedMemoryError):
        cm.decide(candidate_id=c3.candidate_id, decision=DECISION_REJECT,
                  relations=[(RELATION_SUPERSEDES, a.record_id)])


def test_durability_across_backend_reinstantiation(wired):
    mb, cm, root = wired
    cand = cm.propose(memory_backend=mb, source_event_id="evt-user-1")
    cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE)
    cm.close()
    cm2 = ConsolidatedMemoryBackend(root, SUBJECT)
    try:
        assert len(cm2.load_active_records()) == 1
        assert cm2.load_active_records()[0].meaning == "Я терпеть не могу большие шумные вечеринки."
    finally:
        cm2.close()


def test_module_does_not_touch_runtime_state(wired):
    import services.character_runtime.consolidated_memory as m
    src = __import__("pathlib").Path(m.__file__).read_text("utf-8")
    assert "runtime_state" not in src
    assert "RuntimeStateBackend" not in src
    assert "EvolutionCandidate" not in src
    assert normalize_meaning("  A  b ") == "a b"
