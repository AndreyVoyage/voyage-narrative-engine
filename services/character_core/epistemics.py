#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core epistemic foundation -- WORLD FACT is NOT CHARACTER KNOWLEDGE.

A pure, deterministic, standard-library-only contract that keeps four
epistemic categories separate and answers ONE narrow question:

    could this perceiver have this piece of information at this causal
    sequence point?

It stores nothing, integrates with no runtime, renders no prompt, calls no
model, and reconciles no contradictions. A ``WORLD_FACT`` and a
``CHARACTER_BELIEF`` that disagree are both allowed to exist and both allowed
to be selected -- this module never decides which one is "true".

Design rules:

- ``WORLD_FACT`` != ``CHARACTER_BELIEF`` != ``USER_REPORT`` !=
  ``CHARACTER_INTERPRETATION``. Nothing here promotes, corrects, or merges one
  kind into another.
- A ``WORLD_FACT`` with no perceiver listed is NOT visible to anyone merely
  because it is true.
- A subject always has access to its OWN ``CHARACTER_BELIEF`` /
  ``CHARACTER_INTERPRETATION`` (``holder_id == perceiver_id``) without having
  to be redundantly listed as a perceiver. No other kind gets that.
- Any perceiver explicitly listed in ``perceiver_ids`` gets access (subject to
  the temporal window). Nothing is inherited; "everyone knows every report"
  is never implied.
- Visibility respects causal order: an envelope with ``valid_from_seq = 20``
  is invisible at ``at_seq = 19`` -- no retroactive knowledge.

This module MUST NOT import ``services.character_lab`` or
``services.character_runtime``, and it contains no character-specific rules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Tuple

__all__ = [
    "EpistemicKind",
    "HOLDER_ADDRESSABLE_KINDS",
    "is_holder_addressable",
    "EpistemicVisibility",
    "EpistemicEnvelopeError",
    "EpistemicEnvelope",
    "EpistemicVisibilityResult",
    "assess_epistemic_visibility",
    "select_visible_epistemic_context",
]


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------


class EpistemicKind(Enum):
    """What epistemic category an :class:`EpistemicEnvelope` represents.

    These are deliberately NOT interchangeable. Something true in the world is
    not thereby something a character knows; something a user said is not
    thereby a verified fact; a character's read of a situation is not thereby
    a fact.
    """

    #: True in the world. Truth alone confers no visibility.
    WORLD_FACT = "WORLD_FACT"
    #: A user/other party stated this. "They said it", not "it is verified".
    USER_REPORT = "USER_REPORT"
    #: A specific character holds this as a belief (may be wrong).
    CHARACTER_BELIEF = "CHARACTER_BELIEF"
    #: A specific character's interpretation/inference from what they saw.
    CHARACTER_INTERPRETATION = "CHARACTER_INTERPRETATION"


#: The kinds a subject can access purely by being their ``holder_id`` -- a
#: character always has access to its own belief/interpretation. WORLD_FACT
#: and USER_REPORT get NO such implicit visibility.
HOLDER_ADDRESSABLE_KINDS: Tuple[EpistemicKind, ...] = (
    EpistemicKind.CHARACTER_BELIEF,
    EpistemicKind.CHARACTER_INTERPRETATION,
)


def is_holder_addressable(kind) -> bool:
    """True when a kind is one the holder can access via ``holder_id``."""
    return _coerce_kind(kind) in HOLDER_ADDRESSABLE_KINDS


class EpistemicVisibility(Enum):
    """Deterministic outcome of a point-in-time visibility assessment."""

    VISIBLE = "VISIBLE"
    #: ``at_seq`` is before ``valid_from_seq`` -- not knowable yet.
    NOT_YET_VALID = "NOT_YET_VALID"
    #: ``at_seq`` is after ``valid_to_seq`` -- no longer in the window.
    NO_LONGER_VALID = "NO_LONGER_VALID"
    #: This perceiver was never permitted to have this information.
    NOT_AVAILABLE_TO_PERCEIVER = "NOT_AVAILABLE_TO_PERCEIVER"


class EpistemicEnvelopeError(ValueError):
    """Fail-closed error for a malformed :class:`EpistemicEnvelope` or a
    malformed visibility query."""


def _coerce_kind(kind) -> EpistemicKind:
    if isinstance(kind, EpistemicKind):
        return kind
    if isinstance(kind, str):
        try:
            return EpistemicKind(kind.strip())
        except ValueError:
            pass
    raise EpistemicEnvelopeError(
        f"epistemic_kind must be one of {[k.value for k in EpistemicKind]}, got {kind!r}"
    )


def _require_seq(value, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EpistemicEnvelopeError(f"{name} must be an int")


def _require_non_empty_str(value, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EpistemicEnvelopeError(f"{name} must be a non-empty string")


# --------------------------------------------------------------------------
# EpistemicEnvelope
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EpistemicEnvelope:
    """One immutable unit of "who could know what, and when".

    It carries a claim (``meaning``), its epistemic category
    (``epistemic_kind``), where the representation came from (``provenance``),
    the source events it rests on (``basis_event_ids``), and a caller-supplied
    ``confidence`` in ``[0.0, 1.0]`` (never computed here).

    Access is governed by:

    - ``holder_id`` -- the subject whose belief/interpretation this is
      (required for ``CHARACTER_BELIEF`` / ``CHARACTER_INTERPRETATION``, since
      those kinds are defined as belonging to a subject);
    - ``perceiver_ids`` -- the exact set of entities allowed to have
      perceived/received this (no inheritance, no defaults);
    - ``valid_from_seq`` / ``valid_to_seq`` -- an inclusive causal-sequence
      window (``None`` = unbounded on that side).
    """

    meaning: str
    epistemic_kind: EpistemicKind
    provenance: str
    basis_event_ids: Tuple[str, ...]
    confidence: float
    holder_id: Optional[str] = None
    perceiver_ids: Tuple[str, ...] = ()
    valid_from_seq: Optional[int] = None
    valid_to_seq: Optional[int] = None

    def __post_init__(self) -> None:
        kind = _coerce_kind(self.epistemic_kind)
        object.__setattr__(self, "epistemic_kind", kind)

        _require_non_empty_str(self.meaning, "meaning")
        _require_non_empty_str(self.provenance, "provenance")

        if isinstance(self.basis_event_ids, str):
            raise EpistemicEnvelopeError(
                "basis_event_ids must be a sequence of ids, not a bare string"
            )
        basis = tuple(self.basis_event_ids)
        if not basis:
            raise EpistemicEnvelopeError("basis_event_ids must contain at least one id")
        seen: set = set()
        for eid in basis:
            _require_non_empty_str(eid, "each basis event id")
            if eid in seen:
                raise EpistemicEnvelopeError(f"duplicate basis event id: {eid!r}")
            seen.add(eid)
        object.__setattr__(self, "basis_event_ids", basis)

        conf = self.confidence
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            raise EpistemicEnvelopeError("confidence must be a real number")
        conf = float(conf)
        if math.isnan(conf) or math.isinf(conf):
            raise EpistemicEnvelopeError("confidence must be a finite number")
        if not (0.0 <= conf <= 1.0):
            raise EpistemicEnvelopeError("confidence must be within [0.0, 1.0] inclusive")
        object.__setattr__(self, "confidence", conf)

        if self.holder_id is not None:
            _require_non_empty_str(self.holder_id, "holder_id (when supplied)")
        if kind in HOLDER_ADDRESSABLE_KINDS and self.holder_id is None:
            raise EpistemicEnvelopeError(
                f"{kind.value} requires a holder_id -- it is defined as belonging to a subject"
            )

        if isinstance(self.perceiver_ids, str):
            raise EpistemicEnvelopeError(
                "perceiver_ids must be a sequence of ids, not a bare string"
            )
        perceivers = tuple(self.perceiver_ids)
        pseen: set = set()
        for pid in perceivers:
            _require_non_empty_str(pid, "each perceiver id")
            if pid in pseen:
                raise EpistemicEnvelopeError(f"duplicate perceiver id: {pid!r}")
            pseen.add(pid)
        object.__setattr__(self, "perceiver_ids", perceivers)

        if self.valid_from_seq is not None:
            _require_seq(self.valid_from_seq, "valid_from_seq")
        if self.valid_to_seq is not None:
            _require_seq(self.valid_to_seq, "valid_to_seq")
        if (
            self.valid_from_seq is not None
            and self.valid_to_seq is not None
            and self.valid_to_seq < self.valid_from_seq
        ):
            raise EpistemicEnvelopeError(
                "valid_to_seq must be >= valid_from_seq"
            )

    # -- pure accessors (no visibility decision here) -------------------
    def permits_perceiver(self, perceiver_id: str) -> bool:
        """Whether ``perceiver_id`` is EVER allowed this envelope, ignoring
        the temporal window. Holder access applies only to holder-addressable
        kinds; every other grant must be explicit in ``perceiver_ids``."""
        _require_non_empty_str(perceiver_id, "perceiver_id")
        if (
            self.epistemic_kind in HOLDER_ADDRESSABLE_KINDS
            and self.holder_id is not None
            and self.holder_id == perceiver_id
        ):
            return True
        return perceiver_id in self.perceiver_ids

    def temporal_state(self, at_seq: int) -> Optional[EpistemicVisibility]:
        """``None`` when ``at_seq`` is inside the inclusive window, else the
        specific out-of-window reason."""
        _require_seq(at_seq, "at_seq")
        if self.valid_from_seq is not None and at_seq < self.valid_from_seq:
            return EpistemicVisibility.NOT_YET_VALID
        if self.valid_to_seq is not None and at_seq > self.valid_to_seq:
            return EpistemicVisibility.NO_LONGER_VALID
        return None


# --------------------------------------------------------------------------
# Visibility API
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EpistemicVisibilityResult:
    """Deterministic, self-describing result of one visibility assessment."""

    visible: bool
    reason: EpistemicVisibility
    perceiver_id: str
    at_seq: int


def assess_epistemic_visibility(
    envelope: EpistemicEnvelope,
    *,
    perceiver_id: str,
    at_seq: int,
) -> EpistemicVisibilityResult:
    """Can ``perceiver_id`` have ``envelope`` at causal sequence ``at_seq``?

    Perceiver permission is checked first: an entity that is never allowed the
    information gets ``NOT_AVAILABLE_TO_PERCEIVER`` regardless of the clock. A
    permitted perceiver then gets ``NOT_YET_VALID`` / ``NO_LONGER_VALID`` if
    outside the inclusive window, otherwise ``VISIBLE``.

    Truth is irrelevant to this function. A ``WORLD_FACT`` no one perceived is
    not visible; a wrong ``CHARACTER_BELIEF`` its holder holds IS visible to
    that holder.
    """
    if not isinstance(envelope, EpistemicEnvelope):
        raise EpistemicEnvelopeError("envelope must be an EpistemicEnvelope")
    _require_non_empty_str(perceiver_id, "perceiver_id")
    _require_seq(at_seq, "at_seq")

    if not envelope.permits_perceiver(perceiver_id):
        return EpistemicVisibilityResult(
            visible=False,
            reason=EpistemicVisibility.NOT_AVAILABLE_TO_PERCEIVER,
            perceiver_id=perceiver_id,
            at_seq=at_seq,
        )

    temporal = envelope.temporal_state(at_seq)
    if temporal is not None:
        return EpistemicVisibilityResult(
            visible=False, reason=temporal, perceiver_id=perceiver_id, at_seq=at_seq
        )

    return EpistemicVisibilityResult(
        visible=True,
        reason=EpistemicVisibility.VISIBLE,
        perceiver_id=perceiver_id,
        at_seq=at_seq,
    )


def select_visible_epistemic_context(
    envelopes: Iterable[EpistemicEnvelope],
    *,
    perceiver_id: str,
    at_seq: int,
) -> Tuple[EpistemicEnvelope, ...]:
    """Pure filter: the sub-tuple of ``envelopes`` visible to ``perceiver_id``
    at ``at_seq``, in the SAME order they were given.

    It does NOT reconcile contradictions, does NOT deduplicate, does NOT pick
    a "true" envelope, and mutates nothing. Two envelopes that disagree both
    pass through if both are visible.
    """
    _require_non_empty_str(perceiver_id, "perceiver_id")
    _require_seq(at_seq, "at_seq")
    return tuple(
        env
        for env in envelopes
        if assess_epistemic_visibility(
            env, perceiver_id=perceiver_id, at_seq=at_seq
        ).visible
    )
