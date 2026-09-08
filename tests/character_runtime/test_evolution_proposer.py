#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Evolution Proposer V1 -- explicit rules + explicit event batch
-> deterministic PENDING EvolutionCandidate through the existing operator flow.

Offline only. No provider, no network. Synthetic ``trust`` / ``stress`` examples
live only in tests; production stays character-agnostic.
"""

from __future__ import annotations

import inspect

import pytest

from services.character_runtime.evolution import EvolutionCandidateError
from services.character_runtime.evolution_proposer import (
    OUTCOME_ALREADY_EXISTS,
    OUTCOME_CREATED,
    PROPOSER_VERSION,
    DeterministicEvolutionProposer,
    DeterministicEvolutionRule,
    DeterministicEvolutionRuleError,
    EvolutionProposerCollisionError,
    _deterministic_candidate_id,
)
from services.character_runtime.evolution_store import (
    EvolutionCandidateStore,
    EvolutionConflictError,
)
from services.character_runtime.memory import RuntimeEvent
from services.character_runtime.state import (
    DOMAIN_PSYCHOLOGY,
    DOMAIN_RELATIONSHIP,
    RuntimeStateBackend,
)

SUBJECT = "kira"
OP = "operator-1"
TRUST_MEANING = "я тебе полностью доверяю"
STRESS_MEANING = "мне очень тяжело и тревожно"


def _evt(eid, meaning, *, seq, etype="USER_MESSAGE", prov="USER_STATED",
         subject=SUBJECT, session="s1", created_at=None):
    return RuntimeEvent(
        event_id=eid, subject_id=subject, session_id=session, event_type=etype,
        meaning=meaning, created_at=created_at or f"2026-01-01T00:00:{seq:02d}+00:00",
        seq=seq, provenance=prov,
    )


def _trust_rule(**over):
    kw = dict(
        rule_id="r-trust-adjust", source_event_type="USER_MESSAGE",
        exact_meaning=TRUST_MEANING, domain=DOMAIN_RELATIONSHIP, key="andrey.trust",
        operation="ADJUST", proposed_delta=10, reason="явное заявление о доверии",
        confidence=0.6, timescale="MEDIUM",
    )
    kw.update(over)
    return DeterministicEvolutionRule(**kw)


def _stress_rule(**over):
    kw = dict(
        rule_id="r-stress-set", source_event_type="USER_MESSAGE",
        exact_meaning=STRESS_MEANING, domain=DOMAIN_PSYCHOLOGY, key="stress",
        operation="SET", proposed_value=60, reason="явное заявление о тревоге",
        confidence=0.5, timescale="FAST",
    )
    kw.update(over)
    return DeterministicEvolutionRule(**kw)


def _store(tmp_path, subject=SUBJECT):
    return EvolutionCandidateStore(RuntimeStateBackend(tmp_path / "ws", subject))


def _state_events(store):
    return store.state.load_events(store.state.subject_id)


def _candidates(store, **kw):
    # EvolutionCandidateStore.list_candidates -> tuple of (candidate, decision, event_id)
    return [row[0] for row in store.list_candidates(**kw)]


# ------------------------------------------------------------ 1..5 matching
def test_01_exact_match_rule_produces_candidate():
    run = DeterministicEvolutionProposer().propose(
        events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], subject_id=SUBJECT,
    )
    assert run.rule_matches == 1 and run.eligible_events == 1
    c = run.matches[0].candidate
    assert c.domain == DOMAIN_RELATIONSHIP and c.operation == "ADJUST" and c.proposed_delta == 10
    assert c.status == "PENDING"


def test_02_nonmatching_text_produces_no_candidate():
    run = DeterministicEvolutionProposer().propose(
        events=[_evt("e1", "погода сегодня хорошая", seq=1)],
        rules=[_trust_rule()], subject_id=SUBJECT,
    )
    assert run.rule_matches == 0 and run.eligible_events == 1


def test_03_wrong_event_type_produces_no_candidate():
    run = DeterministicEvolutionProposer().propose(
        events=[_evt("e1", TRUST_MEANING, seq=1, etype="SYSTEM_NOTE")],
        rules=[_trust_rule()], subject_id=SUBJECT,
    )
    assert run.eligible_events == 0 and run.rule_matches == 0


def test_04_character_message_never_proposes():
    for etype, prov in (("CHARACTER_MESSAGE", "CHARACTER_UTTERANCE"),
                        ("CHARACTER_UTTERANCE", "CHARACTER_UTTERANCE"),
                        ("USER_MESSAGE", "CHARACTER_UTTERANCE")):
        run = DeterministicEvolutionProposer().propose(
            events=[_evt("e1", TRUST_MEANING, seq=1, etype=etype, prov=prov)],
            rules=[_trust_rule()], subject_id=SUBJECT,
        )
        assert run.eligible_events == 0 and run.rule_matches == 0, (etype, prov)


def test_05_legacy_event_never_proposes():
    run = DeterministicEvolutionProposer().propose(
        events=[_evt("e1", TRUST_MEANING, seq=1, prov=None)],   # provenance None -> LEGACY
        rules=[_trust_rule()], subject_id=SUBJECT,
    )
    assert run.eligible_events == 0 and run.rule_matches == 0


# ------------------------------------------------------------ 6..11 rule validation
def test_06_fact_target_rule_rejected():
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(domain="FACT", key="living_city")


def test_07_remove_rule_rejected():
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(operation="REMOVE", proposed_delta=None)


def test_08_invalid_key_rejected():
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(key="Andrey.Trust")               # uppercase -> RELATIONSHIP regex fails
    with pytest.raises(DeterministicEvolutionRuleError):
        _stress_rule(key="stress.level")              # dot invalid for PSYCHOLOGY


def test_09_malformed_set_adjust_rejected():
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(proposed_value=10)                # ADJUST + value
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(proposed_delta=None)             # ADJUST, no delta
    with pytest.raises(DeterministicEvolutionRuleError):
        _stress_rule(proposed_delta=5)               # SET + delta
    with pytest.raises(DeterministicEvolutionRuleError):
        _stress_rule(proposed_value=None)           # SET, no value
    with pytest.raises(DeterministicEvolutionRuleError):
        _stress_rule(proposed_value=250)           # out of range


def test_10_invalid_confidence_rejected():
    for bad in (1.5, -0.1, True, "x"):
        with pytest.raises(DeterministicEvolutionRuleError):
            _trust_rule(confidence=bad)


def test_11_invalid_timescale_and_blanks_rejected():
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(timescale="INSTANT")
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(reason="   ")
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(rule_id="  ")
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(exact_meaning="   ")
    with pytest.raises(DeterministicEvolutionRuleError):
        _trust_rule(source_event_type="CHARACTER_MESSAGE")


# ------------------------------------------------------------ 12..15 identity / basis
def test_12_candidate_id_deterministic_across_instances():
    ev = _evt("e1", TRUST_MEANING, seq=1)
    a = DeterministicEvolutionProposer().propose(events=[ev], rules=[_trust_rule()], subject_id=SUBJECT)
    b = DeterministicEvolutionProposer().propose(events=[ev], rules=[_trust_rule()], subject_id=SUBJECT)
    cid = a.matches[0].candidate.candidate_id
    assert cid == b.matches[0].candidate.candidate_id
    assert cid.startswith("evc-det-") and len(cid) == len("evc-det-") + 40
    # equals an independent recomputation from canonical inputs
    assert cid == _deterministic_candidate_id(
        subject_id=SUBJECT, rule_id="r-trust-adjust", basis_event_id="e1",
        domain=DOMAIN_RELATIONSHIP, key="andrey.trust", operation="ADJUST",
        proposed_value=None, proposed_delta=10,
    )


def test_13_candidate_id_changes_with_rule_id():
    ev = _evt("e1", TRUST_MEANING, seq=1)
    one = DeterministicEvolutionProposer().propose(events=[ev], rules=[_trust_rule()], subject_id=SUBJECT)
    two = DeterministicEvolutionProposer().propose(
        events=[ev], rules=[_trust_rule(rule_id="r-trust-adjust-v2")], subject_id=SUBJECT)
    assert one.matches[0].candidate.candidate_id != two.matches[0].candidate.candidate_id


def test_14_candidate_id_changes_with_basis_event():
    r = _trust_rule()
    one = DeterministicEvolutionProposer().propose(
        events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[r], subject_id=SUBJECT)
    two = DeterministicEvolutionProposer().propose(
        events=[_evt("e2", TRUST_MEANING, seq=1)], rules=[r], subject_id=SUBJECT)
    assert one.matches[0].candidate.candidate_id != two.matches[0].candidate.candidate_id


def test_15_basis_event_ids_exactly_matched_event():
    run = DeterministicEvolutionProposer().propose(
        events=[_evt("e-42", TRUST_MEANING, seq=1)], rules=[_trust_rule()], subject_id=SUBJECT)
    assert run.matches[0].candidate.basis_event_ids == ("e-42",)


# ------------------------------------------------------------ 16..18 idempotency
def test_16_17_same_event_same_rule_rerun_is_noop(tmp_path):
    store = _store(tmp_path)
    ev, rule = _evt("e1", TRUST_MEANING, seq=1), _trust_rule()
    p = DeterministicEvolutionProposer()
    first = p.propose_and_store(events=[ev], rules=[rule], store=store)
    assert first.created == 1 and first.already_existing == 0
    assert first.results[0].outcome == OUTCOME_CREATED
    second = p.propose_and_store(events=[ev], rules=[rule], store=store)
    assert second.created == 0 and second.already_existing == 1
    assert second.results[0].outcome == OUTCOME_ALREADY_EXISTS
    assert len(_candidates(store)) == 1                       # no duplicate


def test_18_same_id_different_payload_fails_closed(tmp_path):
    store = _store(tmp_path)
    ev = _evt("e1", TRUST_MEANING, seq=1)
    p = DeterministicEvolutionProposer()
    p.propose_and_store(events=[ev], rules=[_trust_rule(reason="first reason")], store=store)
    # same rule_id / domain / key / op / delta -> same candidate_id, but reason differs
    with pytest.raises(EvolutionProposerCollisionError):
        p.propose_and_store(events=[ev], rules=[_trust_rule(reason="edited reason")], store=store)
    assert _candidates(store)[0].reason == "first reason"     # not overwritten


# ------------------------------------------------------------ 19..22 state safety / ordering
def test_19_proposer_creates_zero_runtime_state_events(tmp_path):
    store = _store(tmp_path)
    p = DeterministicEvolutionProposer()
    p.propose(events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], subject_id=SUBJECT)
    p.propose_and_store(events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], store=store)
    assert _state_events(store) == ()                              # no SET / ADJUST ever


def test_20_multiple_rules_execute_deterministically(tmp_path):
    store = _store(tmp_path)
    events = [_evt("e1", TRUST_MEANING, seq=1), _evt("e2", STRESS_MEANING, seq=2)]
    rules = [_stress_rule(), _trust_rule()]                        # deliberately unsorted
    a = DeterministicEvolutionProposer().propose_and_store(events=events, rules=rules, store=store)
    ids = [(r.event_id, r.rule_id) for r in a.results]
    assert ids == [("e1", "r-trust-adjust"), ("e2", "r-stress-set")]
    # rerun with reversed containers -> identical order + all ALREADY_EXISTS
    b = DeterministicEvolutionProposer().propose_and_store(
        events=list(reversed(events)), rules=list(reversed(rules)), store=store)
    assert [(r.event_id, r.rule_id) for r in b.results] == ids
    assert all(r.outcome == OUTCOME_ALREADY_EXISTS for r in b.results)


def test_21_event_ordering_follows_causal_seq():
    events = [_evt("late", TRUST_MEANING, seq=9), _evt("early", TRUST_MEANING, seq=2)]
    run = DeterministicEvolutionProposer().propose(events=events, rules=[_trust_rule()], subject_id=SUBJECT)
    assert [m.event_id for m in run.matches] == ["early", "late"]


def test_22_proposer_never_retrieves_history_itself():
    src = inspect.getsource(
        __import__("services.character_runtime.evolution_proposer", fromlist=["x"])
    )
    for banned in ("load_events", "load_events_causal", "RuntimeMemoryBackend",
                   "load_current_state"):
        assert banned not in src, banned
    # propose / propose_and_store require an explicit events batch
    for meth in ("propose", "propose_and_store"):
        params = inspect.signature(getattr(DeterministicEvolutionProposer, meth)).parameters
        assert "events" in params
    # constructor takes no backend
    assert vars(DeterministicEvolutionProposer()) == {}          # holds no state / backend


# ------------------------------------------------------------ 23..28 operator flow
def test_23_created_candidate_survives_store_reopen(tmp_path):
    root = tmp_path / "ws"
    s1 = EvolutionCandidateStore(RuntimeStateBackend(root, SUBJECT))
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], store=s1)
    cid = _candidates(s1)[0].candidate_id
    s1.state.close()
    s2 = EvolutionCandidateStore(RuntimeStateBackend(root, SUBJECT))
    assert s2.get_candidate(cid).status == "PENDING"


def test_24_pending_visible_in_existing_operator_flow(tmp_path):
    store = _store(tmp_path)
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], store=store)
    pend = _candidates(store, status="PENDING")
    assert len(pend) == 1 and pend[0].status == "PENDING"


def test_25_existing_approve_applies_proposer_candidate(tmp_path):
    store = _store(tmp_path)
    store.state.record_set(domain=DOMAIN_RELATIONSHIP, key="andrey.trust", value="20")
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule(proposed_delta=10)], store=store)
    cid = _candidates(store)[0].candidate_id
    _cand, decision, event_id = store.decide_candidate(cid, decision="APPROVE", decided_by=OP)
    assert decision.decision == "APPROVE" and event_id
    cur = {(e.domain, e.key): e.value for e in store.state.load_current_state(SUBJECT)}
    assert cur[(DOMAIN_RELATIONSHIP, "andrey.trust")] == "30"      # 20 + 10 via existing path


def test_26_existing_reject_leaves_runtime_state_unchanged(tmp_path):
    store = _store(tmp_path)
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", STRESS_MEANING, seq=1)], rules=[_stress_rule()], store=store)
    cid = _candidates(store)[0].candidate_id
    store.decide_candidate(cid, decision="REJECT", decided_by=OP, reason="not warranted")
    assert store.state.load_events(SUBJECT) == ()
    assert store.get_candidate(cid).status == "REJECTED"


def test_27_adjust_uses_current_value_at_later_approval(tmp_path):
    store = _store(tmp_path)
    store.state.record_set(domain=DOMAIN_PSYCHOLOGY, key="stress", value="20")
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", STRESS_MEANING, seq=1)],
        rules=[_stress_rule(operation="ADJUST", proposed_value=None, proposed_delta=10)],
        store=store)
    cid = _candidates(store)[0].candidate_id
    store.state.record_set(domain=DOMAIN_PSYCHOLOGY, key="stress", value="25")  # moves on
    store.decide_candidate(cid, decision="APPROVE", decided_by=OP)
    cur = {(e.domain, e.key): e.value for e in store.state.load_current_state(SUBJECT)}
    assert cur[(DOMAIN_PSYCHOLOGY, "stress")] == "35"             # 25 + 10, not 20 + 10


def test_28_author_only_candidate_not_approvable_via_operator_path(tmp_path):
    store = _store(tmp_path)
    DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", TRUST_MEANING, seq=1)],
        rules=[_trust_rule(timescale="AUTHOR_ONLY")], store=store)
    cid = _candidates(store)[0].candidate_id
    with pytest.raises(EvolutionCandidateError):
        store.decide_candidate(cid, decision="APPROVE", decided_by=OP)
    assert store.state.load_events(SUBJECT) == ()
    assert store.get_candidate(cid).status == "PENDING"
    # still rejectable for the record
    store.decide_candidate(cid, decision="REJECT", decided_by=OP)
    assert store.get_candidate(cid).status == "REJECTED"


# ------------------------------------------------------------ 29..31 isolation / purity
def test_29_workspace_isolation_preserved(tmp_path):
    p = DeterministicEvolutionProposer()
    a = EvolutionCandidateStore(RuntimeStateBackend(tmp_path / "wsA", SUBJECT))
    b = EvolutionCandidateStore(RuntimeStateBackend(tmp_path / "wsB", SUBJECT))
    p.propose_and_store(events=[_evt("e1", TRUST_MEANING, seq=1)], rules=[_trust_rule()], store=a)
    assert len(a.list_candidates()) == 1
    assert _candidates(b) == []


def test_30_subject_isolation_preserved(tmp_path):
    store = _store(tmp_path, subject="kira")
    run = DeterministicEvolutionProposer().propose_and_store(
        events=[_evt("e1", TRUST_MEANING, seq=1, subject="other-subject")],
        rules=[_trust_rule()], store=store)
    assert run.eligible_events == 0 and run.created == 0
    assert _candidates(store) == []


def test_31_no_provider_or_network_imports():
    src = inspect.getsource(
        __import__("services.character_runtime.evolution_proposer", fromlist=["x"])
    )
    import_lines = [ln.strip() for ln in src.splitlines()
                    if ln.strip().startswith(("import ", "from "))]
    for ln in import_lines:
        for banned in ("requests", "httpx", "socket", "urllib", "openai", "deepseek",
                       "aiohttp", "websocket", "http.client"):
            assert banned not in ln, ln
    assert PROPOSER_VERSION == "deterministic-evolution-proposer/v1"
