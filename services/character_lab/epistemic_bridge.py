#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime -> Character Core epistemic bridge (projection only, no prompt change).

Projects REAL existing runtime information into
:class:`services.character_core.epistemics.EpistemicEnvelope` values and then
asks the ALREADY-ACCEPTED Core selector
(:func:`select_visible_epistemic_context`) which of them a given perceiver
could have at a given causal sequence point.

Direction:

    runtime USER_STATED events
    active approved Consolidated Memory USER_REPORT records
    explicit caller-authored EpistemicEnvelope values
            |
            v   (this module: build envelopes, nothing else)
    Character Core EpistemicEnvelope
            |
            v   select_visible_epistemic_context(...)
    EpistemicContextSnapshot

This module does NOT:

- create any database / table / cache / event log;
- reimplement any temporal or perceiver visibility rule (that lives ONLY in
  ``services.character_core.epistemics``);
- turn a character's own message/utterance into a CHARACTER_BELIEF or
  CHARACTER_INTERPRETATION -- speech is not internal belief;
- turn a USER_REPORT into a WORLD_FACT;
- touch free-form Scene text (the current Scene model carries no claim-level
  epistemic kind / perceiver / causal-availability metadata, so mapping it to
  WORLD_FACT would recreate omniscient-character leakage -- it stays outside);
- change what is sent to the provider.

It reuses the existing promotion-eligibility vocabulary from
``services.character_runtime.consolidated_memory`` -- no second vocabulary is
invented here. It contains no character-specific rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from services.character_core.epistemics import (
    EpistemicEnvelope,
    EpistemicKind,
    select_visible_epistemic_context,
)
from services.character_runtime.consolidated_memory import (
    ELIGIBLE_SOURCE_EVENT_TYPES,
    EPISTEMIC_USER_REPORT,
    PROVENANCE_USER_STATED,
    RECORD_STATUS_ACTIVE,
    ConsolidatedMemoryRecord,
)
from services.character_runtime.memory import RuntimeEvent

__all__ = [
    "EpistemicBridgeError",
    "EpistemicContextSnapshot",
    "project_runtime_user_report",
    "project_consolidated_user_report",
    "build_runtime_epistemic_context",
]

#: Confidence attached to a projected USER_REPORT. It is confidence that the
#: report WAS received/stated in the runtime -- NEVER a claim that its content
#: is objectively true. A USER_REPORT is never promoted to WORLD_FACT here.
_REPORT_RECEIPT_CONFIDENCE = 1.0


class EpistemicBridgeError(RuntimeError):
    """Deterministic fail-closed error raised by the bridge.

    ``code`` is one of a small fixed vocabulary the caller can branch on:
    ``subject_mismatch``, ``missing_basis_event``,
    ``unsupported_consolidated_input``, ``unsupported_explicit_input``,
    ``invalid_argument``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _require_non_empty_str(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EpistemicBridgeError("invalid_argument", f"{name} must be a non-empty string")
    return value


def _require_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EpistemicBridgeError("invalid_argument", f"{name} must be an int")
    return value


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EpistemicContextSnapshot:
    """Immutable, deterministic result of one point-in-time bridge build."""

    subject_id: str
    perceiver_id: str
    at_seq: int
    #: Every envelope that entered the Core selector, in deterministic order:
    #: explicit inputs, then consolidated projections, then runtime
    #: projections (with exact-source duplicates suppressed).
    candidate_envelopes: Tuple[EpistemicEnvelope, ...]
    #: The subset the Core selector reported visible to ``perceiver_id`` at
    #: ``at_seq`` -- same relative order as ``candidate_envelopes``.
    visible_envelopes: Tuple[EpistemicEnvelope, ...]
    explicit_count: int = 0
    projected_consolidated_count: int = 0
    projected_runtime_count: int = 0
    #: How many projections were dropped because an envelope with the exact
    #: same (kind, meaning, basis_event_ids) already appeared earlier.
    suppressed_exact_source_count: int = 0


# --------------------------------------------------------------------------
# Projections
# --------------------------------------------------------------------------


def _exact_source_key(env: EpistemicEnvelope) -> Tuple[str, str, Tuple[str, ...]]:
    """Strict, deterministic identity: same kind + same meaning + same basis
    events. NOT semantic/fuzzy -- two distinct or contradictory claims never
    collide."""
    return (env.epistemic_kind.value, env.meaning, tuple(env.basis_event_ids))


def project_runtime_user_report(
    event: RuntimeEvent, *, subject_id: str
) -> Optional[EpistemicEnvelope]:
    """Project ONE runtime event into a USER_REPORT envelope, or ``None`` when
    the accepted runtime semantics do not make it a promotable user report.

    Eligible iff (reusing the Consolidated Memory vocabulary, not a new one):
    ``event_type`` in :data:`ELIGIBLE_SOURCE_EVENT_TYPES`, provenance is
    :data:`PROVENANCE_USER_STATED`, ``meaning`` is non-empty, and it is
    causally sequenced (``seq is not None``). A CHARACTER_MESSAGE /
    CHARACTER_UTTERANCE event is never eligible -- speech is not belief.

    Raises :class:`EpistemicBridgeError` (``subject_mismatch``) if the event
    belongs to a different subject than ``subject_id``.
    """
    if not isinstance(event, RuntimeEvent):
        raise EpistemicBridgeError(
            "unsupported_explicit_input", "runtime_events must contain RuntimeEvent values"
        )
    _require_non_empty_str(subject_id, "subject_id")
    if event.subject_id != subject_id:
        raise EpistemicBridgeError(
            "subject_mismatch",
            f"runtime event {event.event_id!r} subject {event.subject_id!r} "
            f"!= requested subject {subject_id!r}",
        )
    if event.event_type not in ELIGIBLE_SOURCE_EVENT_TYPES:
        return None
    if event.provenance != PROVENANCE_USER_STATED:
        return None
    if not str(event.meaning).strip():
        return None
    if event.seq is None:
        return None
    return EpistemicEnvelope(
        meaning=event.meaning,  # verbatim
        epistemic_kind=EpistemicKind.USER_REPORT,
        provenance=event.provenance,  # preserve accepted runtime provenance
        basis_event_ids=(event.event_id,),
        confidence=_REPORT_RECEIPT_CONFIDENCE,
        holder_id=None,
        perceiver_ids=(subject_id,),  # the character this interaction was with
        valid_from_seq=event.seq,
        valid_to_seq=None,
    )


def project_consolidated_user_report(
    record: ConsolidatedMemoryRecord,
    *,
    subject_id: str,
    runtime_events_by_id: Dict[str, RuntimeEvent],
) -> Optional[EpistemicEnvelope]:
    """Project ONE approved Consolidated Memory record into a USER_REPORT
    envelope, or ``None`` when it is not active current epistemic context
    (superseded, or a non-USER_REPORT kind).

    ``valid_from_seq`` is taken from the ORIGINAL source runtime event's
    causal ``seq`` -- NOT the operator approval sequence. Consolidation is
    durability/storage metadata; the information first became epistemically
    available when the user actually reported it.

    Fail-closed :class:`EpistemicBridgeError`:
    ``unsupported_consolidated_input`` (not a ConsolidatedMemoryRecord),
    ``subject_mismatch`` (different subject), ``missing_basis_event`` (the
    record's basis/source event is absent from the supplied runtime history,
    or is not causally sequenced -- the original availability seq cannot be
    determined and is never guessed).
    """
    if not isinstance(record, ConsolidatedMemoryRecord):
        raise EpistemicBridgeError(
            "unsupported_consolidated_input",
            "consolidated_records must contain ConsolidatedMemoryRecord values "
            "(a PENDING/REJECTED promotion candidate is not a record)",
        )
    _require_non_empty_str(subject_id, "subject_id")
    if record.subject_id != subject_id:
        raise EpistemicBridgeError(
            "subject_mismatch",
            f"consolidated record {record.record_id!r} subject "
            f"{record.subject_id!r} != requested subject {subject_id!r}",
        )
    if record.status != RECORD_STATUS_ACTIVE:
        return None  # SUPERSEDED records are not active current context
    if record.epistemic_kind != EPISTEMIC_USER_REPORT:
        return None

    basis = tuple(record.basis_event_ids)
    if len(basis) != 1:  # V1 records always have exactly one basis event
        raise EpistemicBridgeError(
            "missing_basis_event",
            f"consolidated record {record.record_id!r} does not have exactly "
            f"one basis event: {basis!r}",
        )
    source_event_id = basis[0]
    source = runtime_events_by_id.get(source_event_id)
    if source is None or source.seq is None:
        raise EpistemicBridgeError(
            "missing_basis_event",
            f"consolidated record {record.record_id!r} basis event "
            f"{source_event_id!r} is not present (or not causally sequenced) "
            f"in the supplied runtime history; refusing to guess valid_from_seq",
        )
    return EpistemicEnvelope(
        meaning=record.meaning,  # verbatim
        epistemic_kind=EpistemicKind.USER_REPORT,
        provenance=record.provenance,
        basis_event_ids=(source_event_id,),
        confidence=_REPORT_RECEIPT_CONFIDENCE,
        holder_id=None,
        perceiver_ids=(subject_id,),
        valid_from_seq=source.seq,  # ORIGINAL availability, not approval seq
        valid_to_seq=None,
    )


# --------------------------------------------------------------------------
# Build API
# --------------------------------------------------------------------------


def build_runtime_epistemic_context(
    *,
    subject_id: str,
    runtime_events: Iterable[RuntimeEvent],
    consolidated_records: Iterable[ConsolidatedMemoryRecord],
    explicit_envelopes: Iterable[EpistemicEnvelope] = (),
    perceiver_id: str,
    at_seq: int,
) -> EpistemicContextSnapshot:
    """Build a deterministic point-in-time epistemic snapshot for
    ``perceiver_id`` at ``at_seq``.

    Steps: project supported runtime events; project supported consolidated
    records (original-source ``valid_from_seq``); include explicit envelopes
    unchanged; suppress exact-source duplicates (first occurrence wins, so a
    consolidated projection wins over the raw projection of the same approved
    source); hand the candidate list to
    :func:`select_visible_epistemic_context`; return an immutable snapshot.

    All temporal / perceiver / holder visibility decisions are made by
    Character Core, never here.
    """
    subject_id = _require_non_empty_str(subject_id, "subject_id")
    perceiver_id = _require_non_empty_str(perceiver_id, "perceiver_id")
    at_seq = _require_int(at_seq, "at_seq")

    events = tuple(runtime_events)
    records = tuple(consolidated_records)
    explicit = tuple(explicit_envelopes)

    by_id: Dict[str, RuntimeEvent] = {}
    for event in events:
        if not isinstance(event, RuntimeEvent):
            raise EpistemicBridgeError(
                "unsupported_explicit_input",
                "runtime_events must contain RuntimeEvent values",
            )
        if event.subject_id != subject_id:
            raise EpistemicBridgeError(
                "subject_mismatch",
                f"runtime event {event.event_id!r} subject {event.subject_id!r} "
                f"!= requested subject {subject_id!r}",
            )
        by_id[event.event_id] = event

    seen_keys: set = set()
    candidates: list = []
    explicit_count = 0
    consolidated_count = 0
    runtime_count = 0
    suppressed = 0

    # 1. explicit caller-authored envelopes -- passed through UNCHANGED.
    for env in explicit:
        if not isinstance(env, EpistemicEnvelope):
            raise EpistemicBridgeError(
                "unsupported_explicit_input",
                "explicit_envelopes must contain EpistemicEnvelope values "
                "(free-form text is never auto-mapped to WORLD_FACT)",
            )
        key = _exact_source_key(env)
        if key in seen_keys:
            suppressed += 1
            continue
        seen_keys.add(key)
        candidates.append(env)
        explicit_count += 1

    # 2. approved active Consolidated Memory USER_REPORT records.
    for record in records:
        env = project_consolidated_user_report(
            record, subject_id=subject_id, runtime_events_by_id=by_id
        )
        if env is None:
            continue
        key = _exact_source_key(env)
        if key in seen_keys:
            suppressed += 1
            continue
        seen_keys.add(key)
        candidates.append(env)
        consolidated_count += 1

    # 3. raw runtime USER_STATED events (exact-source dups of a consolidated
    #    projection are suppressed here -- consolidated already won).
    for event in events:
        env = project_runtime_user_report(event, subject_id=subject_id)
        if env is None:
            continue
        key = _exact_source_key(env)
        if key in seen_keys:
            suppressed += 1
            continue
        seen_keys.add(key)
        candidates.append(env)
        runtime_count += 1

    visible = select_visible_epistemic_context(
        candidates, perceiver_id=perceiver_id, at_seq=at_seq
    )

    return EpistemicContextSnapshot(
        subject_id=subject_id,
        perceiver_id=perceiver_id,
        at_seq=at_seq,
        candidate_envelopes=tuple(candidates),
        visible_envelopes=tuple(visible),
        explicit_count=explicit_count,
        projected_consolidated_count=consolidated_count,
        projected_runtime_count=runtime_count,
        suppressed_exact_source_count=suppressed,
    )
