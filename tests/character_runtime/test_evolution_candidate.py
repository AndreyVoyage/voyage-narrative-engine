#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EvolutionCandidate V1 -- candidate -> decision -> approved-mutation workflow.

Offline only. No provider, no network, no memory/consolidated-memory writes, no
accepted-package access. Candidates are constructed directly (no auto-proposer).
Every state mutation goes through the existing RuntimeStateBackend.
"""

from __future__ import annotations

import pytest

from services.character_runtime.evolution import (
    CANDIDATE_STATUS_APPROVED,
    CANDIDATE_STATUS_PENDING,
    CANDIDATE_STATUS_REJECTED,
    DECISION_APPROVE,
    DECISION_REJECT,
    SOURCE_REF_PREFIX,
    EvolutionCandidate,
    EvolutionCandidateError,
    EvolutionCandidateWorkflow,
)
from services.character_runtime.state import (
    DOMAIN_PSYCHOLOGY,
    DOMAIN_RELATIONSHIP,
    SOURCE_OPERATOR_CONFIRMED,
    RuntimeStateBackend,
    RuntimeStateError,
)

SUBJECT = "kira"
OP = "operator-1"


def _backend(tmp_path):
    return RuntimeStateBackend(tmp_path / "ws", SUBJECT)


def _current(backend, domain, key):
    for e in backend.load_current_state(SUBJECT):
        if e.domain == domain and e.key == key:
            return e.value
    return None


def _wf():
    return EvolutionCandidateWorkflow()


def _rel_set(wf, **over):
    kw = dict(
        subject_id=SUBJECT, domain=DOMAIN_RELATIONSHIP, key="andrey.trust",
        operation="SET", reason="ставит границу и принимает ответ",
        basis_event_ids=("event-17", "event-21"), confidence=0.6,
        timescale="MEDIUM", proposed_value=37,
    )
    kw.update(over)
    return wf.create_candidate(**kw)


def _psy_adjust(wf, **over):
    kw = dict(
        subject_id=SUBJECT, domain=DOMAIN_PSYCHOLOGY, key="stress",
        operation="ADJUST", reason="конфликт без разрешения повышает напряжение",
        basis_event_ids=("event-30",), confidence=0.5, timescale="FAST",
        proposed_delta=10,
    )
    kw.update(over)
    return wf.create_candidate(**kw)


# --------------------------------------------------------------- 1..4 create OK
def test_01_valid_relationship_set_candidate():
    c = _rel_set(_wf())
    assert c.domain == DOMAIN_RELATIONSHIP and c.operation == "SET"
    assert c.proposed_value == 37 and c.proposed_delta is None
    assert c.status == CANDIDATE_STATUS_PENDING


def test_02_valid_relationship_adjust_candidate():
    c = _psy_adjust(_wf(), domain=DOMAIN_RELATIONSHIP, key="andrey.trust", proposed_delta=-8)
    assert c.domain == DOMAIN_RELATIONSHIP and c.operation == "ADJUST"
    assert c.proposed_delta == -8 and c.proposed_value is None


def test_03_valid_psychology_set_candidate():
    c = _rel_set(_wf(), domain=DOMAIN_PSYCHOLOGY, key="self_reliance", proposed_value=-12)
    assert c.domain == DOMAIN_PSYCHOLOGY and c.operation == "SET" and c.proposed_value == -12


def test_04_valid_psychology_adjust_candidate():
    c = _psy_adjust(_wf())
    assert c.domain == DOMAIN_PSYCHOLOGY and c.operation == "ADJUST" and c.proposed_delta == 10


# --------------------------------------------------------------- 5..11 fail-closed
def test_05_fact_domain_rejected():
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), domain="FACT", key="living_city")


def test_06_invalid_key_rejected_via_existing_semantics():
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), key="Andrey.Trust")            # uppercase -> RELATIONSHIP regex fails
    with pytest.raises(EvolutionCandidateError):
        _psy_adjust(_wf(), key="stress.level")         # dot not allowed for PSYCHOLOGY


def test_07_out_of_range_set_value_rejected():
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), proposed_value=150)
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), proposed_value=-101)


def test_08_malformed_value_vs_delta_shape_rejected():
    wf = _wf()
    with pytest.raises(EvolutionCandidateError):                       # SET + delta
        _rel_set(wf, proposed_delta=5)
    with pytest.raises(EvolutionCandidateError):                       # SET, no value
        _rel_set(wf, proposed_value=None)
    with pytest.raises(EvolutionCandidateError):                       # ADJUST + value
        _psy_adjust(wf, proposed_value=10)
    with pytest.raises(EvolutionCandidateError):                       # ADJUST, no delta
        _psy_adjust(wf, proposed_delta=None)
    with pytest.raises(EvolutionCandidateError):                       # both present
        wf.create_candidate(
            subject_id=SUBJECT, domain=DOMAIN_PSYCHOLOGY, key="stress",
            operation="ADJUST", reason="x", basis_event_ids=("e1",),
            confidence=0.5, timescale="FAST", proposed_value=1, proposed_delta=1,
        )
    with pytest.raises(EvolutionCandidateError):                       # bad float value
        _rel_set(wf, proposed_value=3.5)


def test_09_invalid_confidence_rejected():
    for bad in (1.5, -0.01, True, "high", None):
        with pytest.raises(EvolutionCandidateError):
            _rel_set(_wf(), confidence=bad)


def test_10_invalid_basis_event_ids_rejected():
    for bad in ((), ("",), ("e1", "e1"), ("e1", "  "), ("e1", 2)):
        with pytest.raises(EvolutionCandidateError):
            _rel_set(_wf(), basis_event_ids=bad)


def test_11_invalid_timescale_rejected():
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), timescale="INSTANT")
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), reason="   ")                  # blank reason
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), subject_id="")                 # blank subject
    with pytest.raises(EvolutionCandidateError):
        _rel_set(_wf(), operation="REMOVE")            # REMOVE excluded from V1


# --------------------------------------------------- 12..13 no mutation on create/reject
def test_12_candidate_creation_causes_zero_runtime_state_mutation(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        _rel_set(wf)
        _psy_adjust(wf)
        assert b.load_events(SUBJECT) == ()
        assert b.load_current_state(SUBJECT) == ()
    finally:
        b.close()


def test_13_reject_causes_zero_runtime_state_mutation(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c = _rel_set(wf)
        d = wf.reject_candidate(c.candidate_id, decided_by=OP, reason="недостаточно оснований")
        assert d.decision == DECISION_REJECT and d.decided_by == OP
        assert wf.get_candidate(c.candidate_id).status == CANDIDATE_STATUS_REJECTED
        assert b.load_events(SUBJECT) == ()
    finally:
        b.close()


# --------------------------------------------------- 14..17 approval + state path
def test_14_approve_set_creates_exactly_one_runtime_state_event(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c = _rel_set(wf, proposed_value=37)
        appr = wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        events = b.load_events(SUBJECT)
        assert len(events) == 1
        ev = events[0]
        assert ev.domain == DOMAIN_RELATIONSHIP and ev.key == "andrey.trust"
        assert ev.action == "SET" and ev.value == "37"
        assert ev.source_kind == SOURCE_OPERATOR_CONFIRMED
        assert ev.source_ref == f"{SOURCE_REF_PREFIX}{c.candidate_id}"
        assert appr.state_event.event_id == ev.event_id
        assert appr.decision.decision == DECISION_APPROVE
        assert wf.get_candidate(c.candidate_id).status == CANDIDATE_STATUS_APPROVED
    finally:
        b.close()


def test_15_approve_adjust_uses_current_authoritative_value(tmp_path):
    b = _backend(tmp_path)
    try:
        # operator initialises stress = 20, candidate says ADJUST +10
        b.record_set(domain=DOMAIN_PSYCHOLOGY, key="stress", value="20")
        wf = _wf()
        c = _psy_adjust(wf, proposed_delta=10)
        # state moves on to 25 BEFORE approval
        b.record_set(domain=DOMAIN_PSYCHOLOGY, key="stress", value="25")
        wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        assert _current(b, DOMAIN_PSYCHOLOGY, "stress") == "35"   # 25 + 10, not 20 + 10
    finally:
        b.close()


def test_16_approval_respects_numeric_range(tmp_path):
    b = _backend(tmp_path)
    try:
        b.record_set(domain=DOMAIN_RELATIONSHIP, key="andrey.trust", value="95")
        wf = _wf()
        c = _psy_adjust(wf, domain=DOMAIN_RELATIONSHIP, key="andrey.trust", proposed_delta=5)
        wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        assert _current(b, DOMAIN_RELATIONSHIP, "andrey.trust") == "100"
    finally:
        b.close()


def test_17_out_of_range_approved_adjust_fails_closed(tmp_path):
    b = _backend(tmp_path)
    try:
        b.record_set(domain=DOMAIN_PSYCHOLOGY, key="stress", value="95")
        wf = _wf()
        c = _psy_adjust(wf, proposed_delta=10)                     # 95 + 10 = 105
        with pytest.raises(RuntimeStateError):
            wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        assert _current(b, DOMAIN_PSYCHOLOGY, "stress") == "95"    # unchanged
        assert len(b.load_events(SUBJECT)) == 1                    # only the operator SET
        assert wf.get_candidate(c.candidate_id).status == CANDIDATE_STATUS_PENDING
        assert wf.decisions() == ()                               # no decision recorded
    finally:
        b.close()


# --------------------------------------------------- 18..21 governance
def test_18_same_candidate_cannot_be_terminally_decided_twice(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c1 = _rel_set(wf, candidate_id="c-double-1", proposed_value=10)
        wf.approve_candidate(c1.candidate_id, decided_by=OP, state_backend=b)
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c1.candidate_id, decided_by=OP, state_backend=b)
        with pytest.raises(EvolutionCandidateError):
            wf.reject_candidate(c1.candidate_id, decided_by=OP)

        c2 = _rel_set(wf, candidate_id="c-double-2", proposed_value=10)
        wf.reject_candidate(c2.candidate_id, decided_by=OP)
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c2.candidate_id, decided_by=OP, state_backend=b)
        # one approve above => exactly one state event
        assert len(b.load_events(SUBJECT)) == 1
    finally:
        b.close()


def test_19_approval_is_explicitly_operator_attributed(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c = _rel_set(wf, proposed_value=5)
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c.candidate_id, decided_by="  ", state_backend=b)
        assert b.load_events(SUBJECT) == ()                       # nothing on failed attribution
        appr = wf.approve_candidate(c.candidate_id, decided_by="operator-42", state_backend=b)
        assert appr.decision.decided_by == "operator-42"
        assert appr.decision.decided_at
    finally:
        b.close()


def test_20_candidate_metadata_survive_unchanged():
    wf = _wf()
    basis = ("event-17", "event-21")
    c = _rel_set(wf, reason="конкретное основание X7", confidence=0.42,
                 basis_event_ids=basis, timescale="SLOW")
    assert c.reason == "конкретное основание X7"
    assert c.confidence == 0.42
    assert c.basis_event_ids == basis
    assert c.timescale == "SLOW"
    # frozen -- cannot be mutated after creation
    with pytest.raises(Exception):
        c.confidence = 0.99


def test_21_author_only_candidate_does_not_auto_apply(tmp_path):
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c = _rel_set(wf, timescale="AUTHOR_ONLY", proposed_value=15)
        assert c.timescale == "AUTHOR_ONLY" and c.status == CANDIDATE_STATUS_PENDING
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        assert b.load_events(SUBJECT) == ()
        assert wf.get_candidate(c.candidate_id).status == CANDIDATE_STATUS_PENDING
        # it may still be rejected for the record
        wf.reject_candidate(c.candidate_id, decided_by=OP, reason="только автор")
        assert wf.get_candidate(c.candidate_id).status == CANDIDATE_STATUS_REJECTED
    finally:
        b.close()


# --------------------------------------------------- 22..24 isolation invariants
def test_22_module_imports_only_stdlib_and_runtime_state():
    import inspect

    import services.character_runtime.evolution as mod

    import_lines = [
        ln.strip()
        for ln in inspect.getsource(mod).splitlines()
        if ln.strip().startswith(("import ", "from "))
    ]
    assert import_lines  # sanity
    for ln in import_lines:
        for banned in ("requests", "httpx", "http.client", "socket", "urllib",
                       "openai", "deepseek", "aiohttp", "websocket"):
            assert banned not in ln, ln
    # the only intra-repo import is the Runtime State backend/validators
    repo_imports = [ln for ln in import_lines if "services" in ln or ln.startswith("from .")]
    assert repo_imports == ["from .state import ("]


def test_23_workflow_touches_no_memory_backend(tmp_path):
    # the workflow only ever receives a RuntimeStateBackend; approving with any
    # other object fails closed before any write.
    b = _backend(tmp_path)
    try:
        wf = _wf()
        c = _rel_set(wf, proposed_value=5)
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=object())
        assert b.load_events(SUBJECT) == ()
    finally:
        b.close()


def test_24_subject_mismatch_between_candidate_and_backend_fails_closed(tmp_path):
    b = RuntimeStateBackend(tmp_path / "ws", "someone-else")
    try:
        wf = _wf()
        c = _rel_set(wf, proposed_value=5)                        # subject "kira"
        with pytest.raises(EvolutionCandidateError):
            wf.approve_candidate(c.candidate_id, decided_by=OP, state_backend=b)
        assert b.load_events("someone-else") == ()
    finally:
        b.close()
