"""Durability, atomicity and multi-connection operator decisions; offline."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import sqlite3

import pytest

from services.character_runtime.evolution import EvolutionCandidateError, EvolutionCandidateWorkflow
from services.character_runtime.evolution_store import (
    EvolutionCandidateStore, EvolutionConflictError, EvolutionNotFoundError,
)
from services.character_runtime.state import RuntimeStateBackend, RuntimeStateError


def create(store, **overrides):
    fields = dict(domain='PSYCHOLOGY', key='stress', operation='SET',
                  proposed_value=20, reason='explicit review',
                  basis_event_ids=['event-1'], confidence=0.8, timescale='MEDIUM')
    fields.update(overrides)
    return store.create_candidate(**fields)


def test_memory_workflow_validates_decision_reason_before_state_write(tmp_path):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    workflow = EvolutionCandidateWorkflow()
    c = create(workflow, subject_id='kira')
    with pytest.raises(EvolutionCandidateError):
        workflow.approve_candidate(c.candidate_id, state_backend=backend,
                                   decided_by='operator', reason=42)
    assert backend.load_events('kira') == ()
    assert workflow.get_candidate(c.candidate_id).status == 'PENDING'
    assert workflow.decisions() == ()
    backend.close()


def test_basis_string_is_not_split_into_character_ids():
    with pytest.raises(EvolutionCandidateError):
        create(EvolutionCandidateWorkflow(), subject_id='kira', basis_event_ids='event-123')


def test_reopen_creation_rejection_and_approval(tmp_path):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    approved = create(store, candidate_id='approve')
    rejected = create(store, candidate_id='reject')
    assert backend.load_events('kira') == ()
    store.decide_candidate(rejected.candidate_id, decision='REJECT', decided_by='reviewer', reason='unsupported')
    assert backend.load_events('kira') == ()
    backend.close()
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    assert store.get_candidate('approve') == approved
    assert store.list_candidates(status='REJECTED')[0][1].reason == 'unsupported'
    result = store.decide_candidate('approve', decision='APPROVE', decided_by='operator', reason='confirmed')
    event_id = result[2]
    backend.close()
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    rows = store.list_candidates(status='APPROVED')
    assert len(rows) == 1
    assert rows[0][0].status == 'APPROVED'
    assert rows[0][1].decided_by == 'operator'
    assert rows[0][1].reason == 'confirmed'
    assert rows[0][1].decided_at
    assert rows[0][2] == event_id
    events = backend.load_events('kira')
    assert len(events) == 1
    assert events[0].event_id == event_id
    assert events[0].source_ref == 'evolution-candidate:approve'
    assert events[0].source_kind == 'OPERATOR_CONFIRMED'
    for candidate_id in ('approve', 'reject'):
        for decision in ('APPROVE', 'REJECT'):
            with pytest.raises(EvolutionConflictError):
                store.decide_candidate(candidate_id, decision=decision, decided_by='again')
    assert len(backend.load_events('kira')) == 1
    backend.close()


def test_adjust_reads_live_value_and_rollback_on_decision_insert_failure(tmp_path):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    backend.record_set(domain='PSYCHOLOGY', key='stress', value='20')
    c = create(store, operation='ADJUST', proposed_value=None, proposed_delta=10)
    backend.record_adjust(domain='PSYCHOLOGY', key='stress', delta=5)
    with backend.transaction() as conn:
        conn.execute("""CREATE TRIGGER fail_decision BEFORE INSERT ON evolution_decisions
                        BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='injected failure'):
        store.decide_candidate(c.candidate_id, decision='APPROVE', decided_by='operator')
    assert backend.current_numeric('PSYCHOLOGY', 'stress') == 25
    assert len(backend.load_events('kira')) == 2
    assert store.get_candidate(c.candidate_id).status == 'PENDING'
    backend.close()
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    assert store.list_candidates()[0][1] is None
    with backend.transaction() as conn:
        conn.execute('DROP TRIGGER fail_decision')
    store.decide_candidate(c.candidate_id, decision='APPROVE', decided_by='operator')
    assert backend.current_numeric('PSYCHOLOGY', 'stress') == 35
    assert len(backend.load_events('kira')) == 3
    backend.close()


@pytest.mark.parametrize('kind', ['missing', 'range', 'author', 'operator', 'reason', 'decision'])
def test_fail_closed(tmp_path, kind):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    fields = {}
    decision = dict(decision='APPROVE', decided_by='operator')
    if kind in ('missing', 'range'):
        fields.update(operation='ADJUST', proposed_value=None, proposed_delta=50)
    if kind == 'range':
        backend.record_set(domain='PSYCHOLOGY', key='stress', value='90')
    if kind == 'author':
        fields['timescale'] = 'AUTHOR_ONLY'
    if kind == 'operator':
        decision['decided_by'] = ' '
    if kind == 'reason':
        decision['reason'] = 42
    if kind == 'decision':
        decision['decision'] = 'AUTO'
    c = create(store, **fields)
    before = backend.load_events('kira')
    with pytest.raises((EvolutionCandidateError, RuntimeStateError)):
        store.decide_candidate(c.candidate_id, **decision)
    assert backend.load_events('kira') == before
    assert store.list_candidates()[0][0].status == 'PENDING'
    assert store.list_candidates()[0][1:] == (None, None)
    backend.close()


def test_isolation_and_duplicate_candidate(tmp_path):
    a = RuntimeStateBackend(tmp_path / 'a', 'kira')
    b = RuntimeStateBackend(tmp_path / 'b', 'kira')
    other = RuntimeStateBackend(tmp_path / 'a', 'other')
    sa, sb, so = map(EvolutionCandidateStore, (a, b, other))
    c = create(sa, candidate_id='same')
    with pytest.raises(EvolutionConflictError):
        create(sa, candidate_id='same')
    assert sb.list_candidates() == so.list_candidates() == ()
    for store in (sb, so):
        with pytest.raises(EvolutionNotFoundError):
            store.decide_candidate(c.candidate_id, decision='APPROVE', decided_by='x')
        create(store, candidate_id='same')
    with pytest.raises(EvolutionCandidateError):
        create(sa, subject_id='other')
    for backend in (a, b, other):
        assert backend.load_events(backend.subject_id) == ()
        backend.close()


@pytest.mark.parametrize('decisions', [('APPROVE', 'APPROVE'), ('APPROVE', 'REJECT')])
def test_concurrent_decisions_are_terminal_once(tmp_path, decisions):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    create(EvolutionCandidateStore(backend), candidate_id='race')
    backend.close()
    barrier = Barrier(2)
    def run(decision):
        b = RuntimeStateBackend(tmp_path, 'kira')
        s = EvolutionCandidateStore(b)
        barrier.wait(timeout=10)
        try:
            s.decide_candidate('race', decision=decision, decided_by=decision)
            return decision
        except EvolutionConflictError:
            return 'conflict'
        finally:
            b.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, decisions))
    assert results.count('conflict') == 1
    backend = RuntimeStateBackend(tmp_path, 'kira')
    row = EvolutionCandidateStore(backend).list_candidates()[0]
    assert row[1].decision in decisions
    assert len(backend.load_events('kira')) == (1 if row[1].decision == 'APPROVE' else 0)
    backend.close()


def test_two_distinct_adjusts_serialize_live_read(tmp_path):
    backend = RuntimeStateBackend(tmp_path, 'kira')
    store = EvolutionCandidateStore(backend)
    backend.record_set(domain='PSYCHOLOGY', key='stress', value='0')
    for cid in ('one', 'two'):
        create(store, candidate_id=cid, operation='ADJUST', proposed_value=None, proposed_delta=10)
    backend.close()
    barrier = Barrier(2)
    def run(cid):
        b = RuntimeStateBackend(tmp_path, 'kira')
        s = EvolutionCandidateStore(b)
        barrier.wait(timeout=10)
        try:
            s.decide_candidate(cid, decision='APPROVE', decided_by='operator')
        finally:
            b.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, ('one', 'two')))
    backend = RuntimeStateBackend(tmp_path, 'kira')
    assert backend.current_numeric('PSYCHOLOGY', 'stress') == 20
    assert len(backend.load_events('kira')) == 3
    backend.close()
