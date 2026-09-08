#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EvolutionCandidate V1 -- candidate -> decision -> approved-mutation workflow
for the numeric Runtime State domains (RELATIONSHIP, PSYCHOLOGY).

A numeric RELATIONSHIP / PSYCHOLOGY value must never change merely because an
event, a model, or a rule "suggests" it should. Evidence becomes an
``EvolutionCandidate``; the candidate is validated (fail-closed, reusing the
existing Runtime State validators); a human/operator explicitly ``APPROVE``s or
``REJECT``s it; and only an ``APPROVE`` applies the proposed ``SET`` / ``ADJUST``
-- through the existing :class:`RuntimeStateBackend` write path, never a direct
SQLite write and never a bypass.

V1 scope:
- domains: ``RELATIONSHIP`` and ``PSYCHOLOGY`` only. ``FACT`` stays
  operator-authored text and is not an evolution target.
- operations: ``SET`` and ``ADJUST`` only. ``REMOVE`` is explicit operator
  deletion, not evolution, and is intentionally excluded.
- no LLM proposer; no auto-creation from conversation / memory / Scene /
  epistemics; no auto-approval; ``confidence`` never authorises a mutation; no
  decay, timers, or scheduling.
- candidates and decisions are held in memory (no schema change). The ONLY
  durable effect of an ``APPROVE`` is the Runtime State event it appends via the
  existing backend.

``ADJUST`` is never precomputed against an assumed current value: the delta is
applied at approval time against the live authoritative state through
``RuntimeStateBackend.record_adjust`` (which fails closed, never clamps).

Standard library only. No provider, no network, no canon access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

from .state import (
    DOMAIN_PSYCHOLOGY,
    DOMAIN_RELATIONSHIP,
    NUMERIC_STATE_MAX,
    NUMERIC_STATE_MIN,
    SOURCE_OPERATOR_CONFIRMED,
    RuntimeStateBackend,
    RuntimeStateError,
    RuntimeStateEvent,
    _coerce_state_int,
    _validate_numeric_key,
)

# ---- V1 vocabularies -------------------------------------------------------

#: Candidate-supported subset of the numeric Runtime State domains. FACT is
#: deliberately absent: it stays operator-authored text.
EVOLUTION_DOMAINS: Tuple[str, ...] = (DOMAIN_RELATIONSHIP, DOMAIN_PSYCHOLOGY)

OPERATION_SET = "SET"
OPERATION_ADJUST = "ADJUST"
EVOLUTION_OPERATIONS: Tuple[str, ...] = (OPERATION_SET, OPERATION_ADJUST)

TIMESCALE_FAST = "FAST"
TIMESCALE_MEDIUM = "MEDIUM"
TIMESCALE_SLOW = "SLOW"
TIMESCALE_AUTHOR_ONLY = "AUTHOR_ONLY"
#: FAST / MEDIUM / SLOW are cadence metadata only. AUTHOR_ONLY marks a candidate
#: as review/observability-only: it may be created and rejected but must never be
#: applied.
EVOLUTION_TIMESCALES: Tuple[str, ...] = (
    TIMESCALE_FAST,
    TIMESCALE_MEDIUM,
    TIMESCALE_SLOW,
    TIMESCALE_AUTHOR_ONLY,
)

CANDIDATE_STATUS_PENDING = "PENDING"
CANDIDATE_STATUS_APPROVED = "APPROVED"
CANDIDATE_STATUS_REJECTED = "REJECTED"
CANDIDATE_STATUSES: Tuple[str, ...] = (
    CANDIDATE_STATUS_PENDING,
    CANDIDATE_STATUS_APPROVED,
    CANDIDATE_STATUS_REJECTED,
)

DECISION_APPROVE = "APPROVE"
DECISION_REJECT = "REJECT"
DECISIONS: Tuple[str, ...] = (DECISION_APPROVE, DECISION_REJECT)

#: Stamped into the existing free-form ``source_ref`` of the Runtime State event
#: an approval produces. The event's ``source_kind`` stays
#: ``OPERATOR_CONFIRMED`` -- an operator explicitly approved the candidate -- so
#: Runtime State semantics are unchanged.
SOURCE_REF_PREFIX = "evolution-candidate:"


class EvolutionCandidateError(RuntimeError):
    """Fail-closed error for the EvolutionCandidate workflow."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---- domain objects ------------------------------------------------------


@dataclass(frozen=True)
class EvolutionCandidate:
    """An immutable proposal to change one numeric Runtime State value.

    Creating a candidate NEVER mutates Runtime State. All fields are validated
    fail-closed at construction, reusing the Runtime State numeric-key and
    integer/range validators.
    """

    candidate_id: str
    subject_id: str
    domain: str
    key: str
    operation: str
    reason: str
    basis_event_ids: Tuple[str, ...]
    confidence: float
    timescale: str
    proposed_value: Optional[int] = None
    proposed_delta: Optional[int] = None
    status: str = CANDIDATE_STATUS_PENDING
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        for name, val in (
            ("candidate_id", self.candidate_id),
            ("subject_id", self.subject_id),
            ("reason", self.reason),
        ):
            if not isinstance(val, str) or not val.strip():
                raise EvolutionCandidateError(f"{name} must be a non-empty string")
        if self.domain not in EVOLUTION_DOMAINS:
            raise EvolutionCandidateError(
                f"domain {self.domain!r} is not an evolution target in V1 "
                f"(supported: {EVOLUTION_DOMAINS}); FACT stays operator-authored"
            )
        if self.operation not in EVOLUTION_OPERATIONS:
            raise EvolutionCandidateError(
                f"operation must be one of {EVOLUTION_OPERATIONS}, got {self.operation!r}"
            )
        if self.timescale not in EVOLUTION_TIMESCALES:
            raise EvolutionCandidateError(
                f"timescale must be one of {EVOLUTION_TIMESCALES}, got {self.timescale!r}"
            )
        if self.status not in CANDIDATE_STATUSES:
            raise EvolutionCandidateError(f"malformed candidate status {self.status!r}")

        # key -- reuse the Runtime State numeric-key validator verbatim
        try:
            normalized_key = _validate_numeric_key(self.domain, self.key)
        except RuntimeStateError as exc:
            raise EvolutionCandidateError(str(exc)) from exc
        object.__setattr__(self, "key", normalized_key)

        # confidence -- proposal confidence only; never an auto-apply threshold
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float)
        ):
            raise EvolutionCandidateError("confidence must be a number in [0, 1]")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise EvolutionCandidateError(
                f"confidence {self.confidence!r} outside [0, 1]"
            )

        # basis_event_ids -- explicit, immutable, non-empty, unique, no blanks
        if not isinstance(self.basis_event_ids, (list, tuple)):
            raise EvolutionCandidateError("basis_event_ids must be a list or tuple")
        basis = tuple(self.basis_event_ids or ())
        if not basis:
            raise EvolutionCandidateError("basis_event_ids must be non-empty")
        if any(not isinstance(b, str) or not b.strip() for b in basis):
            raise EvolutionCandidateError(
                "every basis_event_id must be a non-empty string"
            )
        if len(set(basis)) != len(basis):
            raise EvolutionCandidateError("basis_event_ids must not contain duplicates")
        object.__setattr__(self, "basis_event_ids", basis)

        # value-vs-delta shape -- reuse Runtime State integer + range semantics
        if self.operation == OPERATION_SET:
            if self.proposed_delta is not None:
                raise EvolutionCandidateError(
                    "SET candidate must not carry proposed_delta"
                )
            if self.proposed_value is None:
                raise EvolutionCandidateError(
                    "SET candidate requires proposed_value"
                )
            try:
                n = _coerce_state_int(self.proposed_value)
            except RuntimeStateError as exc:
                raise EvolutionCandidateError(str(exc)) from exc
            if not (NUMERIC_STATE_MIN <= n <= NUMERIC_STATE_MAX):
                raise EvolutionCandidateError(
                    f"proposed_value {n} out of range "
                    f"[{NUMERIC_STATE_MIN}, {NUMERIC_STATE_MAX}]"
                )
            object.__setattr__(self, "proposed_value", n)
        else:  # OPERATION_ADJUST
            if self.proposed_value is not None:
                raise EvolutionCandidateError(
                    "ADJUST candidate must not carry proposed_value"
                )
            if self.proposed_delta is None:
                raise EvolutionCandidateError(
                    "ADJUST candidate requires proposed_delta"
                )
            try:
                d = _coerce_state_int(self.proposed_delta)
            except RuntimeStateError as exc:
                raise EvolutionCandidateError(str(exc)) from exc
            # NOT range-checked here: the delta is applied at approval against
            # the live authoritative value via RuntimeStateBackend.record_adjust.
            object.__setattr__(self, "proposed_delta", d)


@dataclass(frozen=True)
class EvolutionDecision:
    """One append-only APPROVE / REJECT decision on a candidate."""

    candidate_id: str
    decision: str
    decided_by: str
    reason: Optional[str]
    decided_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            raise EvolutionCandidateError("candidate_id must be a non-empty string")
        if self.decision not in DECISIONS:
            raise EvolutionCandidateError(f"decision must be one of {DECISIONS}")
        if not isinstance(self.decided_by, str) or not self.decided_by.strip():
            raise EvolutionCandidateError(
                "decided_by must be a non-empty string (explicit operator attribution)"
            )
        if self.reason is not None and not isinstance(self.reason, str):
            raise EvolutionCandidateError("reason must be a string or None")


@dataclass(frozen=True)
class EvolutionApproval:
    """Result of an APPROVE: the recorded decision, the single Runtime State
    event it produced through the existing backend, and the now-APPROVED
    candidate."""

    decision: EvolutionDecision
    state_event: RuntimeStateEvent
    candidate: EvolutionCandidate


def _with_status(cand: EvolutionCandidate, status: str) -> EvolutionCandidate:
    return EvolutionCandidate(
        candidate_id=cand.candidate_id,
        subject_id=cand.subject_id,
        domain=cand.domain,
        key=cand.key,
        operation=cand.operation,
        reason=cand.reason,
        basis_event_ids=cand.basis_event_ids,
        confidence=cand.confidence,
        timescale=cand.timescale,
        proposed_value=cand.proposed_value,
        proposed_delta=cand.proposed_delta,
        status=status,
        created_at=cand.created_at,
    )


# ---- workflow -----------------------------------------------------------


class EvolutionCandidateWorkflow:
    """In-memory candidate -> decision -> approved-mutation workflow.

    Holds candidates and decisions per instance (no persistence of its own, no
    schema change). The only durable effect is the Runtime State event an
    ``approve_candidate`` writes through :class:`RuntimeStateBackend`.
    """

    def __init__(self) -> None:
        self._candidates: dict = {}
        self._decisions: list = []

    # -- create ---------------------------------------------------------
    def create_candidate(
        self,
        *,
        subject_id: str,
        domain: str,
        key: str,
        operation: str,
        reason: str,
        basis_event_ids,
        confidence: float,
        timescale: str,
        proposed_value=None,
        proposed_delta=None,
        candidate_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> EvolutionCandidate:
        cid = candidate_id or f"evc-{uuid.uuid4().hex}"
        if not isinstance(cid, str) or not cid.strip():
            raise EvolutionCandidateError("candidate_id must be a non-empty string")
        if cid in self._candidates:
            raise EvolutionCandidateError(f"duplicate candidate_id {cid!r}")
        extra = {"created_at": created_at} if created_at else {}
        cand = EvolutionCandidate(
            candidate_id=cid,
            subject_id=subject_id,
            domain=domain,
            key=key,
            operation=operation,
            reason=reason,
            basis_event_ids=basis_event_ids,
            confidence=confidence,
            timescale=timescale,
            proposed_value=proposed_value,
            proposed_delta=proposed_delta,
            **extra,
        )
        self._candidates[cid] = cand
        return cand

    # -- read ---------------------------------------------------------
    def get_candidate(self, candidate_id: str) -> EvolutionCandidate:
        try:
            return self._candidates[candidate_id]
        except KeyError:
            raise EvolutionCandidateError(
                f"unknown candidate_id {candidate_id!r}"
            ) from None

    def list_candidates(
        self, *, subject_id: Optional[str] = None, status: Optional[str] = None
    ) -> Tuple[EvolutionCandidate, ...]:
        out = [
            c
            for c in self._candidates.values()
            if (subject_id is None or c.subject_id == subject_id)
            and (status is None or c.status == status)
        ]
        return tuple(sorted(out, key=lambda c: (c.created_at, c.candidate_id)))

    def decisions(self) -> Tuple[EvolutionDecision, ...]:
        return tuple(self._decisions)

    # -- decide ---------------------------------------------------------
    def _require_pending(self, candidate_id: str) -> EvolutionCandidate:
        cand = self.get_candidate(candidate_id)
        if cand.status != CANDIDATE_STATUS_PENDING:
            raise EvolutionCandidateError(
                f"candidate {candidate_id!r} is already terminally decided "
                f"({cand.status}); append-only decisions are not reversible"
            )
        return cand

    def reject_candidate(
        self,
        candidate_id: str,
        *,
        decided_by: str,
        reason: Optional[str] = None,
        decided_at: Optional[str] = None,
    ) -> EvolutionDecision:
        """Terminally REJECT a pending candidate. Never mutates Runtime State."""
        self._require_pending(candidate_id)
        decision = EvolutionDecision(
            candidate_id=candidate_id,
            decision=DECISION_REJECT,
            decided_by=decided_by,
            reason=reason,
            decided_at=decided_at or _now_iso(),
        )
        self._candidates[candidate_id] = _with_status(
            self._candidates[candidate_id], CANDIDATE_STATUS_REJECTED
        )
        self._decisions.append(decision)
        return decision

    def approve_candidate(
        self,
        candidate_id: str,
        *,
        decided_by: str,
        state_backend: RuntimeStateBackend,
        reason: Optional[str] = None,
        decided_at: Optional[str] = None,
    ) -> EvolutionApproval:
        """Explicitly APPROVE a pending candidate and apply exactly its proposed
        ``SET`` / ``ADJUST`` through the existing Runtime State write path.

        Fail-closed: if the candidate is AUTHOR_ONLY, if attribution/backends do
        not line up, or if the underlying ``RuntimeStateBackend`` write is
        rejected (e.g. an ADJUST that would leave [-100, 100], or an
        uninitialised ADJUST key), the error propagates, NOTHING is mutated, no
        decision is recorded, and the candidate stays ``PENDING``.
        """
        cand = self._require_pending(candidate_id)
        if not isinstance(decided_by, str) or not decided_by.strip():
            raise EvolutionCandidateError(
                "approve requires an explicit operator (decided_by)"
            )
        if not isinstance(state_backend, RuntimeStateBackend):
            raise EvolutionCandidateError(
                "approve requires a RuntimeStateBackend (no direct table writes)"
            )
        if state_backend.subject_id != cand.subject_id:
            raise EvolutionCandidateError(
                f"state backend subject {state_backend.subject_id!r} != candidate "
                f"subject {cand.subject_id!r}"
            )
        if cand.timescale == TIMESCALE_AUTHOR_ONLY:
            raise EvolutionCandidateError(
                "AUTHOR_ONLY candidate is review-only and must not be applied"
            )

        # defensive re-validation of the candidate shape before any write
        _revalidate(cand)

        decision = EvolutionDecision(
            candidate_id=candidate_id,
            decision=DECISION_APPROVE,
            decided_by=decided_by,
            reason=reason,
            decided_at=decided_at or _now_iso(),
        )
        source_ref = f"{SOURCE_REF_PREFIX}{cand.candidate_id}"
        if cand.operation == OPERATION_SET:
            state_event = state_backend.record_set(
                domain=cand.domain,
                key=cand.key,
                value=str(cand.proposed_value),
                source_kind=SOURCE_OPERATOR_CONFIRMED,
                source_ref=source_ref,
            )
        else:  # OPERATION_ADJUST -- applied against the LIVE current value
            state_event = state_backend.record_adjust(
                domain=cand.domain,
                key=cand.key,
                delta=cand.proposed_delta,
                source_kind=SOURCE_OPERATOR_CONFIRMED,
                source_ref=source_ref,
            )

        self._candidates[candidate_id] = _with_status(cand, CANDIDATE_STATUS_APPROVED)
        self._decisions.append(decision)
        return EvolutionApproval(
            decision=decision,
            state_event=state_event,
            candidate=self._candidates[candidate_id],
        )


def _revalidate(cand: EvolutionCandidate) -> None:
    """Re-run the fail-closed candidate validation (reconstruct the frozen
    object from its own fields; ``__post_init__`` re-checks everything)."""
    EvolutionCandidate(
        candidate_id=cand.candidate_id,
        subject_id=cand.subject_id,
        domain=cand.domain,
        key=cand.key,
        operation=cand.operation,
        reason=cand.reason,
        basis_event_ids=cand.basis_event_ids,
        confidence=cand.confidence,
        timescale=cand.timescale,
        proposed_value=cand.proposed_value,
        proposed_delta=cand.proposed_delta,
        created_at=cand.created_at,
    )
