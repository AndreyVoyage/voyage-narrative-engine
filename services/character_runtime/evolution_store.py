"""Durable operator candidates and append-only decisions; no proposer.

Two additive tables in the workspace's runtime_state.sqlite3. Candidate payloads
stay immutable; status is derived from the single decision. Approval and its
normal Runtime State event commit together on the backend's connection.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, replace

from .evolution import (
    CANDIDATE_STATUSES, EvolutionCandidate, EvolutionCandidateError,
    EvolutionCandidateWorkflow, EvolutionDecision,
)
from .state import RuntimeStateBackend


class EvolutionNotFoundError(EvolutionCandidateError):
    """Candidate is absent in this workspace/subject."""


class EvolutionConflictError(EvolutionCandidateError):
    """Candidate already exists or has a terminal decision."""


class EvolutionCandidateStore:
    def __init__(self, state_backend: RuntimeStateBackend):
        self.state = state_backend
        with self.state.transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS evolution_candidates (
                subject_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (subject_id, candidate_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS evolution_decisions (
                subject_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                payload TEXT NOT NULL, state_event_id TEXT UNIQUE,
                PRIMARY KEY (subject_id, candidate_id))""")

    def create_candidate(self, **fields) -> EvolutionCandidate:
        if fields.get('subject_id', self.state.subject_id) != self.state.subject_id:
            raise EvolutionCandidateError('candidate subject must match workspace subject')
        fields['subject_id'] = self.state.subject_id
        candidate = EvolutionCandidateWorkflow().create_candidate(**fields)
        try:
            with self.state.transaction() as conn:
                conn.execute('INSERT INTO evolution_candidates VALUES (?, ?, ?)', (
                    candidate.subject_id, candidate.candidate_id,
                    json.dumps(asdict(candidate), ensure_ascii=False, allow_nan=False),
                ))
        except sqlite3.IntegrityError as exc:
            raise EvolutionConflictError('duplicate candidate_id') from exc
        return candidate

    def _get(self, conn, candidate_id):
        row = conn.execute('''SELECT c.payload, d.payload, d.state_event_id
            FROM evolution_candidates c LEFT JOIN evolution_decisions d
            ON c.subject_id = d.subject_id AND c.candidate_id = d.candidate_id
            WHERE c.subject_id = ? AND c.candidate_id = ?''',
            (self.state.subject_id, candidate_id)).fetchone()
        if row is None:
            raise EvolutionNotFoundError('unknown evolution candidate')
        candidate = EvolutionCandidate(**json.loads(row[0]))
        decision = EvolutionDecision(**json.loads(row[1])) if row[1] else None
        if decision:
            candidate = replace(candidate, status=(
                'APPROVED' if decision.decision == 'APPROVE' else 'REJECTED'))
        return candidate, decision, row[2]

    def get_candidate(self, candidate_id):
        with self.state.transaction() as conn:
            return self._get(conn, candidate_id)[0]

    def list_candidates(self, *, status=None):
        if status is not None and status not in CANDIDATE_STATUSES:
            raise EvolutionCandidateError('invalid candidate status')
        with self.state.transaction() as conn:
            ids = conn.execute('SELECT candidate_id FROM evolution_candidates '
                               'WHERE subject_id = ?', (self.state.subject_id,)).fetchall()
            rows = [self._get(conn, row[0]) for row in ids]
        return tuple(sorted(
            (row for row in rows if status is None or row[0].status == status),
            key=lambda row: (row[0].created_at, row[0].candidate_id)))

    def decide_candidate(self, candidate_id, *, decision, decided_by, reason=None):
        # Validate attribution and decision before beginning any state mutation.
        with self.state.transaction() as conn:
            candidate, previous, _ = self._get(conn, candidate_id)
            if previous is not None:
                raise EvolutionConflictError('candidate already terminally decided')
            workflow = EvolutionCandidateWorkflow()
            fields = asdict(candidate)
            fields.pop('status')
            workflow.create_candidate(**fields)
            if decision == 'APPROVE':
                result = workflow.approve_candidate(
                    candidate_id, state_backend=self.state,
                    decided_by=decided_by, reason=reason)
                recorded, event_id = result.decision, result.state_event.event_id
            elif decision == 'REJECT':
                recorded = workflow.reject_candidate(
                    candidate_id, decided_by=decided_by, reason=reason)
                event_id = None
            else:
                raise EvolutionCandidateError('decision must be APPROVE or REJECT')
            conn.execute('INSERT INTO evolution_decisions VALUES (?, ?, ?, ?)', (
                self.state.subject_id, candidate_id,
                json.dumps(asdict(recorded), ensure_ascii=False), event_id,
            ))
            return workflow.get_candidate(candidate_id), recorded, event_id
