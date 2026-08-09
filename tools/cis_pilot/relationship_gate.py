#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 3 deterministic RELATIONSHIP_GATE.

Implements the owner-approved relationship transition boundary (spec §9 /
plan §5, §9, §14 Slice 3 / TD-13) as a pure, deterministic gate:

    CHARACTER_INTERPRETATION + current pilot P3State
        ->  deterministic RELATIONSHIP_GATE  ->  new pilot P3State (or no change)

Mandatory invariants:

* MEMORY_KEEP != P3_CHANGE (plan §14 Slice 2 stop condition, TD-13 H): an
  accepted ``CharacterMemory`` never mutates P3 by itself. This gate's only
  evidence input is a ``CharacterInterpretation`` (plus its provenance-linked
  ``WorldEvent``); the S2 memory gate has no P3 access at all.
* TRUST-ONLY (TD-13 E/F): the gate may move only ``trust``. ``attraction`` is
  always carried over unchanged -- attraction is frozen in-pilot (plan §5).
* BOUNDS (TD-13 K): trust is always constrained to 0..100 (enforced
  structurally by the Slice 0 ``P3State`` contract).
* DUPLICATE PROTECTION (TD-13 I): the same source-event/provenance identity
  (``character_id`` + ``world_event_id`` -- the exact S2 dedup identity) never
  applies a relationship delta twice. No fuzzy text dedup, no embeddings, no
  LLM.
* CONFLICT (Concept §7, TD-13 L): the same source event arriving with a
  different evidence classification is CONFLICTED -- both classifications are
  preserved as audit evidence, P3 stays unchanged, nothing is averaged, no
  automatic transition happens, and any later promotion is a human decision.
* PILOT SCOPE ONLY: in-memory state, no files, no SQLite, no canon writes, no
  network, no provider. Canon relationship state is never touched; canon
  promotion is human-only (CIS-Q11).

Slice-local contracts (``RelationshipEvidence``, ``RelationshipTransitionState``
and friends) are intentionally defined in this module rather than
``contracts.py``, following the accepted Slice 1 (``CisContextLayers``) and
Slice 2 (``WorldEvent``/``CharacterMemory``) precedents: they are
Slice-3-scoped and ``contracts.py`` is outside this slice's write-set.

TD-13 numeric defaults (owner decision 2026-08-07): exact delta magnitudes and
caps are PILOT IMPLEMENTATION DEFAULTS -- explicit, deterministic, documented,
boundary-tested module-level constants; not canon personality facts; subject
to later empirical calibration without changing canon. See the constants
block below for the per-value rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .contracts import ContractValidationError, P3State
from .memory_gate import CONFLICT_STATUS, CharacterInterpretation, WorldEvent

# ---------------------------------------------------------------------------
# TD-13 relationship delta pilot defaults (documented implementation defaults)
# ---------------------------------------------------------------------------
#
# TD-13 (owner decision, 2026-08-07) delegates the exact numeric relationship
# delta, threshold and cap values to the implementation layer as auditable
# module-level constants. They are pilot calibration values -- NOT canon
# personality facts and NOT claimed to be psychologically canonical.
#
# Derivation of the values (not arbitrary picks):
#   * The pilot P3 scale is 0..100 with the frozen baseline at trust=75
#     (personas/kira/relationships/MATRIX.json, read-only). Deltas must be
#     small relative to the scale so no single ordinary event causes a large
#     personality-like change (TD-13 §12 of the implementation instruction).
#   * TRUST_DELTA_SUPPORTING = +2: perceptible but conservative movement
#     (2% of the scale); the session cap is reached only after three
#     supporting events, so cap behavior stays observable in tests.
#   * TRUST_DELTA_DAMAGING = -3: asymmetric with the supporting delta (trust
#     erodes faster than it builds -- a conservative pilot stance, not a canon
#     claim); exactly equals the per-event cap so the cap boundary is
#     directly testable.
#   * TRUST_DELTA_PER_EVENT_CAP = 3: no single event may move trust by more
#     than 3 points, whatever the evidence type. Equals the largest delta
#     magnitude, so the cap is load-bearing at the boundary, never
#     pass-through.
#   * TRUST_DELTA_SESSION_CAP = 5: total net movement within one pilot
#     session/transition chain is bounded to 5% of the scale. Reachable in
#     three supporting events (+2, +2, +2 -> the third clamps to +1), which
#     demonstrates deterministic clamping without large swings.
#
# Minimum eligible evidence (TD-13 G) is one valid, provenance-bound,
# non-conflicted CharacterInterpretation with a recognized evidence type; it
# is a structural rule, not a numeric threshold, so no constant represents it.
#
# All constants are integers, module-level, and NOT configurable via
# env/provider/CLI. Changing them later is recalibration of pilot parameters,
# not a new mechanic (TD-13 M).
TRUST_DELTA_SUPPORTING = 2
TRUST_DELTA_DAMAGING = -3
TRUST_DELTA_PER_EVENT_CAP = 3
TRUST_DELTA_SESSION_CAP = 5

# Relationship evidence classification (finite, explicit, deterministic).
# Classification is an INPUT to the deterministic gate (supplied by the
# caller / injected proposal stub), never derived inside the gate by an LLM.
EVIDENCE_TRUST_SUPPORTING = "trust_supporting"
EVIDENCE_TRUST_DAMAGING = "trust_damaging"
EVIDENCE_NEUTRAL = "neutral"

RECOGNIZED_EVIDENCE_TYPES = (
    EVIDENCE_TRUST_SUPPORTING,
    EVIDENCE_TRUST_DAMAGING,
    EVIDENCE_NEUTRAL,
)

# Gate decision outcomes (plain string constants -- no enum dependency).
DECISION_APPLIED = "applied"
DECISION_NO_CHANGE = "no_change"
DECISION_DUPLICATE = "duplicate"
DECISION_CONFLICTED = "conflicted"
DECISION_CAPPED = "capped"


class RelationshipGateError(RuntimeError):
    """Fail-closed error for structurally invalid gate input (wrong-type
    argument, broken provenance linkage, unrecognized evidence type). Never
    silently substitutes a value."""


# ---------------------------------------------------------------------------
# Relationship evidence (Slice 3 input contract, slice-local)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationshipEvidence:
    """One deterministic, provenance-bound relationship evidence item.

    Bundles the S2 ``CharacterInterpretation`` (the belief/meaning layer) with
    its provenance-linked ``WorldEvent`` (repo-relative scenario path, JSON
    path, source SHA-256) and an explicit deterministic ``evidence_type``
    classification. The duplicate/conflict identity is exactly the S2
    provenance identity: ``character_id`` + ``world_event.event_id``.

    Construction is fail-closed: unrecognized evidence types and broken
    linkage are rejected here and re-checked by the gate itself.
    """

    character_id: str
    interpretation: CharacterInterpretation
    world_event: WorldEvent
    evidence_type: str

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        if not isinstance(self.interpretation, CharacterInterpretation):
            raise ContractValidationError(
                "interpretation must be a CharacterInterpretation instance"
            )
        if not isinstance(self.world_event, WorldEvent):
            raise ContractValidationError("world_event must be a WorldEvent instance")
        if self.evidence_type not in RECOGNIZED_EVIDENCE_TYPES:
            raise ContractValidationError(
                f"evidence_type must be one of {RECOGNIZED_EVIDENCE_TYPES}, "
                f"got {self.evidence_type!r}"
            )
        if self.interpretation.world_event_id != self.world_event.event_id:
            raise ContractValidationError(
                "interpretation is not linked to this world_event "
                f"({self.interpretation.world_event_id!r} != {self.world_event.event_id!r})"
            )
        if self.interpretation.character_id != self.character_id:
            raise ContractValidationError(
                "interpretation character_id does not match evidence character_id"
            )


# ---------------------------------------------------------------------------
# Pilot relationship transition state (IN-MEMORY ONLY, immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationshipTransitionRecord:
    """Audit record for one newly seen source-event identity: the evidence
    classification and the trust delta actually applied (0 for neutral or
    fully capped evidence). ``resulting_trust`` is the pilot trust value
    immediately after this record."""

    character_id: str
    world_event_id: str
    evidence_type: str
    applied_delta: int
    resulting_trust: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        _require_non_empty_str(self.world_event_id, "world_event_id")
        if self.evidence_type not in RECOGNIZED_EVIDENCE_TYPES:
            raise ContractValidationError(
                f"evidence_type must be one of {RECOGNIZED_EVIDENCE_TYPES}, "
                f"got {self.evidence_type!r}"
            )
        if isinstance(self.applied_delta, bool) or not isinstance(self.applied_delta, int):
            raise ContractValidationError("applied_delta must be a plain int")
        if isinstance(self.resulting_trust, bool) or not isinstance(self.resulting_trust, int):
            raise ContractValidationError("resulting_trust must be a plain int")
        if not 0 <= self.resulting_trust <= 100:
            raise ContractValidationError(
                f"resulting_trust must be within 0..100, got {self.resulting_trust}"
            )


@dataclass(frozen=True)
class RelationshipConflict:
    """Conflict evidence (Concept §7, TD-13 L): the same source event arrived
    with a different evidence classification. Both classifications are
    retained verbatim, status CONFLICTED, never averaged, never auto-resolved.
    Recording a conflict is not a canon write and not a promotion; any later
    promotion is a human decision outside Slice 3."""

    character_id: str
    world_event_id: str
    existing_evidence_type: str
    conflicting_evidence_type: str
    status: str = CONFLICT_STATUS

    def __post_init__(self) -> None:
        _require_non_empty_str(self.character_id, "character_id")
        _require_non_empty_str(self.world_event_id, "world_event_id")
        _require_non_empty_str(self.existing_evidence_type, "existing_evidence_type")
        _require_non_empty_str(self.conflicting_evidence_type, "conflicting_evidence_type")
        if self.status != CONFLICT_STATUS:
            raise ContractValidationError(f"status must be {CONFLICT_STATUS!r}")


@dataclass(frozen=True)
class RelationshipTransitionState:
    """The pilot-scope relationship transition state: the current pilot
    ``P3State`` plus the audit trail of seen evidence. IN-MEMORY ONLY -- no
    files, no SQLite, no pickle, no canon, no globals. The gate returns a NEW
    state instead of mutating (pure functional behavior).

    ``cumulative_trust_delta`` is the net signed trust movement since this
    transition chain started; it must always equal the sum of the records'
    ``applied_delta`` values (checked at construction) and is the quantity
    bounded by ``TRUST_DELTA_SESSION_CAP``.
    """

    current_p3: P3State
    records: Tuple[RelationshipTransitionRecord, ...] = ()
    conflicts: Tuple[RelationshipConflict, ...] = ()
    cumulative_trust_delta: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.current_p3, P3State):
            raise ContractValidationError("current_p3 must be a P3State instance")
        if not isinstance(self.records, tuple) or not isinstance(self.conflicts, tuple):
            raise ContractValidationError("records and conflicts must be tuples")
        for record in self.records:
            if not isinstance(record, RelationshipTransitionRecord):
                raise ContractValidationError(
                    "records must contain RelationshipTransitionRecord instances"
                )
        for conflict in self.conflicts:
            if not isinstance(conflict, RelationshipConflict):
                raise ContractValidationError(
                    "conflicts must contain RelationshipConflict instances"
                )
        if isinstance(self.cumulative_trust_delta, bool) or not isinstance(
            self.cumulative_trust_delta, int
        ):
            raise ContractValidationError("cumulative_trust_delta must be a plain int")
        recorded = sum(record.applied_delta for record in self.records)
        if self.cumulative_trust_delta != recorded:
            raise ContractValidationError(
                f"cumulative_trust_delta ({self.cumulative_trust_delta}) != "
                f"sum of record deltas ({recorded}); the audit trail is inconsistent"
            )


@dataclass(frozen=True)
class RelationshipGateResult:
    """Deterministic gate outcome: the decision plus the NEW transition state
    (the input state is never mutated). ``reason`` is a stable, documented
    explanation string for auditability."""

    decision: str
    state: RelationshipTransitionState
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in (
            DECISION_APPLIED,
            DECISION_NO_CHANGE,
            DECISION_DUPLICATE,
            DECISION_CONFLICTED,
            DECISION_CAPPED,
        ):
            raise ContractValidationError(f"unknown gate decision: {self.decision!r}")
        if not isinstance(self.state, RelationshipTransitionState):
            raise ContractValidationError(
                "state must be a RelationshipTransitionState instance"
            )
        _require_non_empty_str(self.reason, "reason")


def initial_relationship_state(p3: P3State) -> RelationshipTransitionState:
    """Start a pilot relationship transition chain from a frozen-baseline
    ``P3State`` (e.g. trust=75, attraction=85 from the read-only MATRIX
    source). No file reads; structured input only."""
    if not isinstance(p3, P3State):
        raise RelationshipGateError("p3 must be a P3State instance")
    return RelationshipTransitionState(current_p3=p3)


# ---------------------------------------------------------------------------
# Deterministic RELATIONSHIP_GATE
# ---------------------------------------------------------------------------


def evaluate_relationship_evidence(
    evidence: RelationshipEvidence,
    state: RelationshipTransitionState,
) -> RelationshipGateResult:
    """Deterministic applied / no_change / duplicate / conflicted / capped
    decision for one relationship evidence item.

    Order of checks (all fail-closed or deterministic):

    1. Type checks on both arguments.
    2. Provenance identity (``character_id`` + ``world_event_id`` -- the exact
       S2 dedup identity): an identity already seen with the SAME
       ``evidence_type`` -> DECISION_DUPLICATE, no second delta, state
       unchanged; an identity already seen with a DIFFERENT ``evidence_type``
       -> DECISION_CONFLICTED, both classifications kept as CONFLICTED audit
       evidence, P3 unchanged, automatic transition blocked (Concept §7:
       never average, never auto-pick, human-only promotion).
    3. Neutral evidence -> DECISION_NO_CHANGE; the identity is recorded with
       a zero delta so a later re-classification of the same source event is
       caught by check 2, but P3 is never touched.
    4. Delta computation: the fixed TD-13 delta for the evidence type,
       clamped by the per-event cap, then by the cumulative session cap,
       then by the 0..100 trust bounds (enforced again by the ``P3State``
       contract). If clamping reduced the delta -> DECISION_CAPPED, else
       DECISION_APPLIED. The clamped-to-zero identity is still recorded, so
       it can never apply a delta later (TD-13 I).

    ``attraction`` is carried over unchanged on every path (TD-13 F).
    No network, no provider, no file I/O, no canon write, no P4 access.
    """
    if not isinstance(evidence, RelationshipEvidence):
        raise RelationshipGateError("evidence must be a RelationshipEvidence instance")
    if not isinstance(state, RelationshipTransitionState):
        raise RelationshipGateError("state must be a RelationshipTransitionState instance")

    current_p3 = state.current_p3

    # 2. Duplicate / conflict by provenance identity.
    for record in state.records:
        if (
            record.character_id == evidence.character_id
            and record.world_event_id == evidence.world_event.event_id
        ):
            if record.evidence_type == evidence.evidence_type:
                return RelationshipGateResult(
                    decision=DECISION_DUPLICATE,
                    state=state,
                    reason=(
                        f"event {evidence.world_event.event_id!r} already seen with the "
                        "same evidence classification; no second relationship delta applied"
                    ),
                )
            conflict = RelationshipConflict(
                character_id=evidence.character_id,
                world_event_id=evidence.world_event.event_id,
                existing_evidence_type=record.evidence_type,
                conflicting_evidence_type=evidence.evidence_type,
            )
            return RelationshipGateResult(
                decision=DECISION_CONFLICTED,
                state=RelationshipTransitionState(
                    current_p3=current_p3,
                    records=state.records,
                    conflicts=state.conflicts + (conflict,),
                    cumulative_trust_delta=state.cumulative_trust_delta,
                ),
                reason=(
                    f"conflicting evidence classification for event "
                    f"{evidence.world_event.event_id!r}: both classifications kept as "
                    "CONFLICTED evidence, P3 unchanged, automatic transition blocked "
                    "(human review)"
                ),
            )

    # 3. Neutral evidence: recorded for identity protection, never moves P3.
    if evidence.evidence_type == EVIDENCE_NEUTRAL:
        return RelationshipGateResult(
            decision=DECISION_NO_CHANGE,
            state=RelationshipTransitionState(
                current_p3=current_p3,
                records=state.records
                + (
                    RelationshipTransitionRecord(
                        character_id=evidence.character_id,
                        world_event_id=evidence.world_event.event_id,
                        evidence_type=evidence.evidence_type,
                        applied_delta=0,
                        resulting_trust=current_p3.trust,
                    ),
                ),
                conflicts=state.conflicts,
                cumulative_trust_delta=state.cumulative_trust_delta,
            ),
            reason="neutral evidence; P3 unchanged",
        )

    # 4. Deterministic delta with per-event cap, session cap and 0..100 bounds.
    if evidence.evidence_type == EVIDENCE_TRUST_SUPPORTING:
        requested = TRUST_DELTA_SUPPORTING
    elif evidence.evidence_type == EVIDENCE_TRUST_DAMAGING:
        requested = TRUST_DELTA_DAMAGING
    else:
        # Unreachable: RelationshipEvidence construction rejects unknown
        # types. Re-checked so the gate itself is never bypassable.
        raise RelationshipGateError(
            f"unrecognized evidence_type at gate level: {evidence.evidence_type!r}"
        )

    per_event = _clamp_magnitude(requested, TRUST_DELTA_PER_EVENT_CAP)
    session_clamped = _clamp_to_session_cap(state.cumulative_trust_delta, per_event)
    new_trust = min(100, max(0, current_p3.trust + session_clamped))
    applied = new_trust - current_p3.trust

    new_p3 = P3State(trust=new_trust, attraction=current_p3.attraction)
    new_state = RelationshipTransitionState(
        current_p3=new_p3,
        records=state.records
        + (
            RelationshipTransitionRecord(
                character_id=evidence.character_id,
                world_event_id=evidence.world_event.event_id,
                evidence_type=evidence.evidence_type,
                applied_delta=applied,
                resulting_trust=new_trust,
            ),
        ),
        conflicts=state.conflicts,
        cumulative_trust_delta=state.cumulative_trust_delta + applied,
    )
    if applied != requested:
        return RelationshipGateResult(
            decision=DECISION_CAPPED,
            state=new_state,
            reason=(
                f"requested delta {requested:+d} clamped to {applied:+d} by deterministic "
                f"caps/bounds (per-event cap {TRUST_DELTA_PER_EVENT_CAP}, session cap "
                f"{TRUST_DELTA_SESSION_CAP}, trust bounds 0..100); trust "
                f"{current_p3.trust} -> {new_trust}"
            ),
        )
    return RelationshipGateResult(
        decision=DECISION_APPLIED,
        state=new_state,
        reason=(
            f"{evidence.evidence_type} evidence applied delta {applied:+d}; "
            f"trust {current_p3.trust} -> {new_trust}"
        ),
    )


# ---------------------------------------------------------------------------
# Trust-only override path for T3-P3 controlled state construction (plan §5)
# ---------------------------------------------------------------------------


def construct_t3_p3_trust_override(current_p3: P3State, target_trust: int) -> P3State:
    """Pilot-only trust override for controlled T3-P3 state construction
    (plan §5: "trust-only override path for T3-P3; attraction always frozen
    in-pilot").

    This is NOT the normal relationship-event processing path -- it exists so
    the pilot can construct the fixed A/B trust states (e.g. trust=75 vs
    trust=55) that Test 3 injects directly per PD-3. Deterministic, trust
    only, attraction carried unchanged, bounds enforced by the ``P3State``
    contract, no canon write, no cap bypass beyond the 0..100 bounds.
    """
    if not isinstance(current_p3, P3State):
        raise RelationshipGateError("current_p3 must be a P3State instance")
    if isinstance(target_trust, bool) or not isinstance(target_trust, int):
        raise RelationshipGateError("target_trust must be a plain int")
    return P3State(trust=target_trust, attraction=current_p3.attraction)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clamp_magnitude(delta: int, cap: int) -> int:
    """Clamp a signed delta to +/- cap."""
    if delta > cap:
        return cap
    if delta < -cap:
        return -cap
    return delta


def _clamp_to_session_cap(cumulative: int, delta: int) -> int:
    """Clamp ``delta`` so that ``|cumulative + delta| <= TRUST_DELTA_SESSION_CAP``.

    Opposite-sign movement (back toward the baseline) is always allowed in
    full; same-sign movement is limited to the remaining deterministic room.
    """
    projected = cumulative + delta
    if projected > TRUST_DELTA_SESSION_CAP:
        return TRUST_DELTA_SESSION_CAP - cumulative
    if projected < -TRUST_DELTA_SESSION_CAP:
        return -TRUST_DELTA_SESSION_CAP - cumulative
    return delta


def _require_non_empty_str(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
