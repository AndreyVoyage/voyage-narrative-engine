#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 2 deterministic TRANSIENT_STATE_UPDATE (P4).

Lightweight, fully deterministic updater for the transient P4 state
(spec §11, plan §9/§14 Slice 2): a bounded categorical stimulus moves the
state, and a turn-count-based categorical reversion (TD-9) returns it to the
baseline after N turns without reinforcing stimulus.

Hard constraints enforced by design:

* The only state space is the existing ``contracts.P4State`` /
  ``ALLOWED_P4_STATES`` -- the four source-backed categorical combinations
  from ``psychology/AFFECT_REGULATION.json``. No numerical arousal/anxiety
  scale is added; invalid states fail closed through the existing contract
  validation, never silently coerced or mapped to baseline.
* Decay is a CATEGORICAL STATE-MACHINE REVERSION (TD-9), never a continuous
  / floating-point / exponential decay curve.
* P4 is always ephemeral: nothing here persists -- no canon, no files, no
  pilot state outside the returned immutable value. P3 and P0 are never
  read or mutated.
* No module-level mutable state: the updater is a pure function
  ``previous -> stimulus -> new value``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import ContractValidationError, P4State

# ---------------------------------------------------------------------------
# TD-9 reversion turn count (documented implementation default)
# ---------------------------------------------------------------------------
#
# TD-9 (plan §15) mandates a categorical, turn-count-based reversion toward
# the AFFECT_REGULATION baseline strategy "after N turns without reinforcing
# stimulus" -- explicitly NOT a numeric decay -- and records
# OWNER_DECISION_REQUIRED: NO for the mechanism; no source document fixes a
# literal N, so the value is delegated to the implementation layer as an
# auditable constant (same delegation pattern as TD-10).
#
# Derivation of the value 3 (not an arbitrary pick):
#   * It must be > 1, otherwise a transient state could never persist beyond
#     the turn it was set on, making the mechanism meaningless.
#   * It should be small: P4 is defined as fast-changing and ephemeral
#     (spec §11, Concept §5 "каждая сцена").
#   * 3 matches the repo's existing small-integer convention for gated
#     accumulation (Concept §12 Q13 recommends "начать с 3" for the
#     evolution accumulation parameter -- an analogous advisory default, not
#     a new number).
#   * 3 gives usable boundary tests at N-1 (state retained), N (reversion),
#     N+1 (remains baseline).
#
# This constant is module-level, integer, > 0, used by every decay decision,
# and is NOT configurable via env/provider/CLI.
TRANSIENT_REVERSION_TURNS = 3

# The categorical baseline P4 reverts to (spec §11 / PD-4 "наименее
# активированное source-backed состояние"; TD-9 "toward the AFFECT_REGULATION
# baseline strategy").
P4_BASELINE_STATE = P4State(arousal="low", anxiety="low", strategy="exploration")


class TransientStateError(RuntimeError):
    """Fail-closed error for structurally invalid updater input (wrong
    types). Invalid P4 content itself fails closed earlier, inside the
    existing ``P4State`` contract validation."""


@dataclass(frozen=True)
class TransientP4State:
    """Immutable transient P4 value: the current categorical ``P4State``
    plus the deterministic turn counter used by TD-9 reversion. Ephemeral
    metadata only -- never persisted, never canon."""

    current: P4State
    turns_without_reinforcement: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.current, P4State):
            raise ContractValidationError("current must be a P4State instance")
        if isinstance(self.turns_without_reinforcement, bool) or not isinstance(
            self.turns_without_reinforcement, int
        ):
            raise ContractValidationError("turns_without_reinforcement must be a plain int")
        if self.turns_without_reinforcement < 0:
            raise ContractValidationError("turns_without_reinforcement must be >= 0")


def initial_transient_state() -> TransientP4State:
    """The deterministic starting point: baseline, zero counter."""
    return TransientP4State(current=P4_BASELINE_STATE, turns_without_reinforcement=0)


def update_transient_state(
    previous: TransientP4State, stimulus: Optional[P4State]
) -> TransientP4State:
    """Deterministic transient P4 update (pure function, new value returned,
    ``previous`` never mutated).

    * ``stimulus`` is a reinforcing categorical signal (a ``P4State`` from the
      allowed source-backed set): the state moves to it and the turn counter
      resets to 0.
    * ``stimulus is None`` means "no reinforcing stimulus this turn":
      - already at baseline -> stays baseline, counter stays 0;
      - otherwise the counter advances by 1; when it reaches
        ``TRANSIENT_REVERSION_TURNS`` the state reverts to baseline and the
        counter resets to 0 (TD-9 categorical reversion);
      - after reversion, further no-stimulus turns simply stay at baseline
        (documented N+1 behavior).
    """
    if not isinstance(previous, TransientP4State):
        raise TransientStateError("previous must be a TransientP4State instance")
    if stimulus is not None and not isinstance(stimulus, P4State):
        raise TransientStateError("stimulus must be a P4State instance or None")

    if stimulus is not None:
        # Reinforcing stimulus: adopt the stimulus state, reset the counter.
        return TransientP4State(current=stimulus, turns_without_reinforcement=0)

    if previous.current == P4_BASELINE_STATE:
        # Already baseline: nothing to decay; counter stays pinned at 0.
        return TransientP4State(current=P4_BASELINE_STATE, turns_without_reinforcement=0)

    turns = previous.turns_without_reinforcement + 1
    if turns >= TRANSIENT_REVERSION_TURNS:
        return TransientP4State(current=P4_BASELINE_STATE, turns_without_reinforcement=0)
    return TransientP4State(current=previous.current, turns_without_reinforcement=turns)
