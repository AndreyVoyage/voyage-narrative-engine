#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Evolution Proposer V1 -- a reference, fully inspectable baseline
for turning explicitly supplied Runtime Events into PENDING ``EvolutionCandidate``
values through the existing operator flow.

This is NOT a natural-language engine: there is no sentiment analysis, no
keyword heuristics, no regex/embedding/classifier/LLM inference. A caller
supplies an explicit, immutable list of :class:`DeterministicEvolutionRule` and
an explicit bounded batch of :class:`RuntimeEvent`; a rule fires only on an
EXACT event-type + surrounding-whitespace-normalized ``meaning`` match. Production
code stays character-agnostic -- no ``kira`` / ``trust`` / ``stress`` / ``andrey``
rule is hardcoded here.

Invariants:
- ``propose`` / ``propose_and_store`` cause ZERO Runtime State mutation: no
  APPROVE, no ``record_set`` / ``record_adjust``. The existing operator flow
  (:class:`EvolutionCandidateStore.decide_candidate`) stays the only apply layer.
- Only user-originated events are eligible: ``event_type`` in
  :data:`ELIGIBLE_SOURCE_EVENT_TYPES` AND ``provenance ==``
  :data:`PROVENANCE_USER_STATED` (reused from Consolidated Memory). A
  CHARACTER_MESSAGE / CHARACTER_UTTERANCE / model-origin / LEGACY
  (``provenance is None``) event can never propose evolution -- anti-self-training.
- ``candidate_id`` is a deterministic SHA-256 over canonical inputs (proposer
  version, rule_id, subject_id, basis event_id, domain, key, operation,
  value/delta). No uuid4, wall-clock, db sequence, or randomness. Re-running the
  same rule over the same event is idempotent: CREATED once, then ALREADY_EXISTS.
  A same-id candidate with a different payload fails closed as a collision.
- ``basis_event_ids`` is exactly ``(matched_event.event_id,)``.
- the proposer never loads Runtime history itself: it takes an explicit batch.
- one event -> one matching rule -> one candidate. No multi-event reasoning, no
  rolling windows.

Standard library only. No provider, no network, no canon access.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional, Tuple

from .consolidated_memory import ELIGIBLE_SOURCE_EVENT_TYPES, PROVENANCE_USER_STATED
from .evolution import EvolutionCandidate, EvolutionCandidateError
from .evolution_store import (
    EvolutionCandidateStore,
    EvolutionConflictError,
    EvolutionNotFoundError,
)
from .memory import RuntimeEvent

PROPOSER_VERSION = "deterministic-evolution-proposer/v1"

OUTCOME_CREATED = "CREATED"
OUTCOME_ALREADY_EXISTS = "ALREADY_EXISTS"
OUTCOMES: Tuple[str, ...] = (OUTCOME_CREATED, OUTCOME_ALREADY_EXISTS)


class DeterministicEvolutionRuleError(EvolutionCandidateError):
    """Fail-closed error for a malformed deterministic evolution rule / batch."""


class EvolutionProposerCollisionError(EvolutionCandidateError):
    """A deterministic candidate_id already exists with a DIFFERENT payload."""


def _normalize_content(text: Optional[str]) -> str:
    """The single, minimal, deterministic normalization: strip surrounding
    whitespace only. No case-folding, no internal whitespace collapse, no fuzzy
    / substring / regex / semantic matching."""
    return (text or "").strip()


# ---- rule model --------------------------------------------------------


@dataclass(frozen=True)
class DeterministicEvolutionRule:
    """An explicit, immutable exact-match rule.

    Every domain field is validated by constructing a probe
    :class:`EvolutionCandidate` (so FACT target, REMOVE, bad key, malformed
    SET/ADJUST shape, out-of-range value, bad confidence/timescale, blank reason
    are all rejected by the *existing* contract -- never re-implemented here).
    """

    rule_id: str
    source_event_type: str
    exact_meaning: str
    domain: str
    key: str
    operation: str
    reason: str
    confidence: float
    timescale: str
    proposed_value: Optional[int] = None
    proposed_delta: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise DeterministicEvolutionRuleError("rule_id must be a non-empty string")
        if self.source_event_type not in ELIGIBLE_SOURCE_EVENT_TYPES:
            raise DeterministicEvolutionRuleError(
                f"source_event_type {self.source_event_type!r} is not an eligible "
                f"user-originated event type (allowed: {ELIGIBLE_SOURCE_EVENT_TYPES}); "
                f"character/model/legacy events must never propose evolution"
            )
        meaning = _normalize_content(self.exact_meaning)
        if not meaning:
            raise DeterministicEvolutionRuleError("exact_meaning must be non-empty")
        object.__setattr__(self, "exact_meaning", meaning)

        # Reuse the EvolutionCandidate contract for ALL domain validation.
        try:
            probe = EvolutionCandidate(
                candidate_id="rule-probe",
                subject_id="rule-probe",
                domain=self.domain,
                key=self.key,
                operation=self.operation,
                reason=self.reason,
                basis_event_ids=("rule-probe",),
                confidence=self.confidence,
                timescale=self.timescale,
                proposed_value=self.proposed_value,
                proposed_delta=self.proposed_delta,
            )
        except EvolutionCandidateError as exc:
            raise DeterministicEvolutionRuleError(str(exc)) from exc

        # store back the contract-normalized values so candidate identity is
        # stable regardless of incidental formatting in the rule
        object.__setattr__(self, "key", probe.key)
        object.__setattr__(self, "proposed_value", probe.proposed_value)
        object.__setattr__(self, "proposed_delta", probe.proposed_delta)

    def matches(self, event: RuntimeEvent) -> bool:
        return (
            event.event_type == self.source_event_type
            and _normalize_content(event.meaning) == self.exact_meaning
        )


# ---- result model ----------------------------------------------------


@dataclass(frozen=True)
class ProposedCandidate:
    """One rule/event match from :meth:`DeterministicEvolutionProposer.propose`
    -- a validated but NOT-yet-persisted candidate."""

    candidate: EvolutionCandidate
    rule_id: str
    event_id: str


@dataclass(frozen=True)
class ProposalRun:
    matches: Tuple[ProposedCandidate, ...]
    events_seen: int
    eligible_events: int
    rule_matches: int


@dataclass(frozen=True)
class ProposalResult:
    candidate: EvolutionCandidate
    outcome: str
    rule_id: str
    event_id: str


@dataclass(frozen=True)
class StoredProposalRun:
    results: Tuple[ProposalResult, ...]
    events_seen: int
    eligible_events: int
    rule_matches: int
    created: int
    already_existing: int


# ---- helpers -------------------------------------------------------


def _deterministic_candidate_id(
    *,
    subject_id: str,
    rule_id: str,
    basis_event_id: str,
    domain: str,
    key: str,
    operation: str,
    proposed_value: Optional[int],
    proposed_delta: Optional[int],
) -> str:
    canonical = json.dumps(
        {
            "proposer_version": PROPOSER_VERSION,
            "rule_id": rule_id,
            "subject_id": subject_id,
            "basis_event_id": basis_event_id,
            "domain": domain,
            "key": key,
            "operation": operation,
            "proposed_value": proposed_value,
            "proposed_delta": proposed_delta,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"evc-det-{digest[:40]}"


def _canonical_payload(cand: EvolutionCandidate) -> str:
    """Identity-defining payload for idempotency / collision checks -- every
    field except the store-derived ``status``."""
    d = asdict(cand)
    d.pop("status", None)
    d["basis_event_ids"] = list(d.get("basis_event_ids") or [])
    return json.dumps(d, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _is_eligible(event: RuntimeEvent, *, subject_id: str) -> bool:
    return (
        event.subject_id == subject_id
        and event.event_type in ELIGIBLE_SOURCE_EVENT_TYPES
        and event.provenance == PROVENANCE_USER_STATED
    )


def _event_sort_key(event: RuntimeEvent):
    # causal seq first (authoritative); deterministic tie-breakers, never wall-clock
    return (event.seq is None, event.seq if event.seq is not None else 0,
            event.created_at, event.event_id)


# ---- proposer -----------------------------------------------------


class DeterministicEvolutionProposer:
    """Stateless. Holds no backend and never retrieves Runtime history."""

    version = PROPOSER_VERSION

    def propose(
        self,
        *,
        events: Iterable[RuntimeEvent],
        rules: Iterable[DeterministicEvolutionRule],
        subject_id: str,
    ) -> ProposalRun:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise DeterministicEvolutionRuleError("subject_id must be a non-empty string")
        rule_tuple = tuple(rules)
        seen_ids: set = set()
        for rule in rule_tuple:
            if not isinstance(rule, DeterministicEvolutionRule):
                raise DeterministicEvolutionRuleError(
                    "every rule must be a DeterministicEvolutionRule"
                )
            if rule.rule_id in seen_ids:
                raise DeterministicEvolutionRuleError(
                    f"duplicate rule_id {rule.rule_id!r} in the rule batch"
                )
            seen_ids.add(rule.rule_id)

        event_tuple = tuple(events)
        ordered_events = sorted(event_tuple, key=_event_sort_key)
        ordered_rules = sorted(rule_tuple, key=lambda r: r.rule_id)

        matches = []
        eligible = 0
        for event in ordered_events:
            if not _is_eligible(event, subject_id=subject_id):
                continue
            eligible += 1
            for rule in ordered_rules:
                if not rule.matches(event):
                    continue
                cid = _deterministic_candidate_id(
                    subject_id=subject_id,
                    rule_id=rule.rule_id,
                    basis_event_id=event.event_id,
                    domain=rule.domain,
                    key=rule.key,
                    operation=rule.operation,
                    proposed_value=rule.proposed_value,
                    proposed_delta=rule.proposed_delta,
                )
                candidate = EvolutionCandidate(
                    candidate_id=cid,
                    subject_id=subject_id,
                    domain=rule.domain,
                    key=rule.key,
                    operation=rule.operation,
                    reason=rule.reason,
                    basis_event_ids=(event.event_id,),
                    confidence=rule.confidence,
                    timescale=rule.timescale,
                    proposed_value=rule.proposed_value,
                    proposed_delta=rule.proposed_delta,
                    created_at=event.created_at,
                )
                matches.append(
                    ProposedCandidate(
                        candidate=candidate,
                        rule_id=rule.rule_id,
                        event_id=event.event_id,
                    )
                )
        return ProposalRun(
            matches=tuple(matches),
            events_seen=len(event_tuple),
            eligible_events=eligible,
            rule_matches=len(matches),
        )

    def propose_and_store(
        self,
        *,
        events: Iterable[RuntimeEvent],
        rules: Iterable[DeterministicEvolutionRule],
        store: EvolutionCandidateStore,
    ) -> StoredProposalRun:
        subject_id = store.state.subject_id
        run = self.propose(events=events, rules=rules, subject_id=subject_id)

        results = []
        created = 0
        already = 0
        for match in run.matches:
            want = match.candidate
            want_payload = _canonical_payload(want)

            existing = self._existing(store, want.candidate_id)
            if existing is not None:
                self._guard_collision(existing, want_payload, want.candidate_id)
                results.append(
                    ProposalResult(existing, OUTCOME_ALREADY_EXISTS,
                                   match.rule_id, match.event_id)
                )
                already += 1
                continue

            try:
                saved = store.create_candidate(
                    candidate_id=want.candidate_id,
                    subject_id=subject_id,
                    domain=want.domain,
                    key=want.key,
                    operation=want.operation,
                    reason=want.reason,
                    basis_event_ids=want.basis_event_ids,
                    confidence=want.confidence,
                    timescale=want.timescale,
                    proposed_value=want.proposed_value,
                    proposed_delta=want.proposed_delta,
                    created_at=want.created_at,
                )
            except EvolutionConflictError:
                existing = self._existing(store, want.candidate_id)
                self._guard_collision(existing, want_payload, want.candidate_id)
                results.append(
                    ProposalResult(existing, OUTCOME_ALREADY_EXISTS,
                                   match.rule_id, match.event_id)
                )
                already += 1
                continue

            results.append(
                ProposalResult(saved, OUTCOME_CREATED, match.rule_id, match.event_id)
            )
            created += 1

        return StoredProposalRun(
            results=tuple(results),
            events_seen=run.events_seen,
            eligible_events=run.eligible_events,
            rule_matches=run.rule_matches,
            created=created,
            already_existing=already,
        )

    @staticmethod
    def _existing(store: EvolutionCandidateStore, candidate_id: str):
        try:
            return store.get_candidate(candidate_id)
        except EvolutionNotFoundError:
            return None

    @staticmethod
    def _guard_collision(existing, want_payload: str, candidate_id: str) -> None:
        if existing is None or _canonical_payload(existing) != want_payload:
            raise EvolutionProposerCollisionError(
                f"deterministic candidate_id {candidate_id!r} already exists with a "
                f"different payload; refusing to overwrite"
            )
