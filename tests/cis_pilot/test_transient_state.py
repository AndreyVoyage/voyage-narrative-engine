#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 2 tests for tools/cis_pilot/transient_state.py.

No LLM, no network. Covers: existing four P4 states only,
deterministic update, identical-inputs-determinism, reinforcing stimulus,
no-reinforcement counter progression, exact N reversion, N+1 baseline,
categorical turn reversion (NOT floating decay), no numerical arousal scale,
invalid P4 fail closed, no P3/P0 mutation, no persistence/files, no provider.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import (
    ALLOWED_P4_STATES,
    ContractValidationError,
    P3State,
    P4State,
)
from tools.cis_pilot.transient_state import (
    P4_BASELINE_STATE,
    TRANSIENT_REVERSION_TURNS,
    TransientP4State,
    TransientStateError,
    initial_transient_state,
    update_transient_state,
)


# ---------------------------------------------------------------------------
# Existing four P4 states only (item 1)
# ---------------------------------------------------------------------------


def test_four_source_backed_p4_states_exist():
    """Verify the four approved P4 (arousal, anxiety) -> strategy mappings."""
    assert len(ALLOWED_P4_STATES) == 4
    assert ALLOWED_P4_STATES[("high", "low")] == "approach"
    assert ALLOWED_P4_STATES[("high", "high")] == "avoidance"
    assert ALLOWED_P4_STATES[("low", "high")] == "seeking_reassurance"
    assert ALLOWED_P4_STATES[("low", "low")] == "exploration"


def test_baseline_is_low_low_exploration():
    """Baseline must be low/low/exploration (TD-9)."""
    assert P4_BASELINE_STATE.arousal == "low"
    assert P4_BASELINE_STATE.anxiety == "low"
    assert P4_BASELINE_STATE.strategy == "exploration"


def test_initial_transient_state_is_baseline_zero_counter():
    state = initial_transient_state()
    assert state.current == P4_BASELINE_STATE
    assert state.turns_without_reinforcement == 0


# ---------------------------------------------------------------------------
# Deterministic update + identical inputs (items 2-3)
# ---------------------------------------------------------------------------


def test_update_is_deterministic():
    """Same inputs -> same output every time."""
    prev = initial_transient_state()
    stimulus = P4State(arousal="high", anxiety="low", strategy="approach")
    a = update_transient_state(prev, stimulus)
    b = update_transient_state(prev, stimulus)
    assert a == b


def test_identical_inputs_produce_identical_output():
    """Repeated calls with the same (previous, stimulus) give identical output."""
    prev = TransientP4State(
        current=P4State(arousal="low", anxiety="high", strategy="seeking_reassurance"),
        turns_without_reinforcement=1,
    )
    stim = P4State(arousal="high", anxiety="high", strategy="avoidance")
    out1 = update_transient_state(prev, stim)
    out2 = update_transient_state(prev, stim)
    assert out1 == out2


# ---------------------------------------------------------------------------
# No P3 / P0 mutation (items 4-5)
# ---------------------------------------------------------------------------


def test_update_has_no_p3_input_and_never_mutates_p3():
    """Transient updater must not take or mutate P3."""
    signature = inspect.signature(update_transient_state)
    forbidden = {"p3", "p3_state", "trust", "attraction", "relationship"}
    assert forbidden.isdisjoint(signature.parameters.keys())
    p3 = P3State(trust=75, attraction=85)
    prev = initial_transient_state()
    stimulus = P4State(arousal="high", anxiety="low", strategy="approach")
    update_transient_state(prev, stimulus)
    update_transient_state(prev, None)
    assert (p3.trust, p3.attraction) == (75, 85)


def test_update_has_no_p0_parameter():
    """Updater signature must not contain P0."""
    signature = inspect.signature(update_transient_state)
    forbidden = {"p0", "p0_state", "p0_value", "personality"}
    assert forbidden.isdisjoint(signature.parameters.keys())


# ---------------------------------------------------------------------------
# Reinforcing stimulus behavior (item 6)
# ---------------------------------------------------------------------------


def test_reinforcing_stimulus_adopts_state_and_resets_counter():
    prev = TransientP4State(
        current=P4State(arousal="low", anxiety="high", strategy="seeking_reassurance"),
        turns_without_reinforcement=2,
    )
    stimulus = P4State(arousal="high", anxiety="low", strategy="approach")
    result = update_transient_state(prev, stimulus)
    assert result.current == stimulus
    assert result.turns_without_reinforcement == 0


def test_reinforcement_preserves_state_across_multiple_turns():
    """Reinforcing each turn keeps the state and counter at 0."""
    state = initial_transient_state()
    stim = P4State(arousal="high", anxiety="low", strategy="approach")
    for _ in range(5):
        state = update_transient_state(state, stim)
        assert state.current == stim
        assert state.turns_without_reinforcement == 0


# ---------------------------------------------------------------------------
# No-reinforcement N-1 behavior (item 7)
# ---------------------------------------------------------------------------


def test_no_reinforcement_counter_advances_below_threshold():
    """Without stimulus, counter advances but state is retained until threshold."""
    prev = TransientP4State(
        current=P4State(arousal="high", anxiety="low", strategy="approach"),
        turns_without_reinforcement=0,
    )
    for expected_counter in range(1, TRANSIENT_REVERSION_TURNS):
        result = update_transient_state(prev, None)
        assert result.current == prev.current, (
            f"State should not revert before N={TRANSIENT_REVERSION_TURNS}, "
            f"at counter {expected_counter}"
        )
        assert result.turns_without_reinforcement == expected_counter
        prev = result


# ---------------------------------------------------------------------------
# Exact N reversion (item 8)
# ---------------------------------------------------------------------------


def test_exact_n_reversion():
    """At exactly N turns without reinforcement, state reverts to baseline."""
    prev = TransientP4State(
        current=P4State(arousal="high", anxiety="low", strategy="approach"),
        turns_without_reinforcement=TRANSIENT_REVERSION_TURNS - 1,
    )
    result = update_transient_state(prev, None)
    assert result.current == P4_BASELINE_STATE
    assert result.turns_without_reinforcement == 0


# ---------------------------------------------------------------------------
# N+1 remains baseline (item 9)
# ---------------------------------------------------------------------------


def test_beyond_n_remains_baseline():
    """After reversion, further no-stimulus turns stay at baseline."""
    # First, get to N-1 then trigger reversion
    prev = TransientP4State(
        current=P4State(arousal="high", anxiety="low", strategy="approach"),
        turns_without_reinforcement=TRANSIENT_REVERSION_TURNS - 1,
    )
    reverted = update_transient_state(prev, None)
    assert reverted.current == P4_BASELINE_STATE
    assert reverted.turns_without_reinforcement == 0
    # N+1: already baseline, no further change
    next_state = update_transient_state(reverted, None)
    assert next_state.current == P4_BASELINE_STATE
    assert next_state.turns_without_reinforcement == 0


def test_baseline_stays_baseline_regardless_of_counter():
    """Already-baseline state with no stimulus stays baseline, counter at 0."""
    state = initial_transient_state()
    for _ in range(10):
        state = update_transient_state(state, None)
        assert state.current == P4_BASELINE_STATE
        assert state.turns_without_reinforcement == 0


# ---------------------------------------------------------------------------
# Baseline assertion (item 10) — already covered above, explicit test
# ---------------------------------------------------------------------------


def test_baseline_is_explicitly_low_low_exploration():
    assert P4_BASELINE_STATE == P4State(arousal="low", anxiety="low", strategy="exploration")


# ---------------------------------------------------------------------------
# No floating decay / no numerical scale (items 11-12)
# ---------------------------------------------------------------------------


def test_no_floating_point_decay():
    """Counter and all fields are integers, never floats."""
    prev = initial_transient_state()
    result = update_transient_state(prev, None)
    assert isinstance(result.turns_without_reinforcement, int)
    assert not isinstance(result.turns_without_reinforcement, float)


def test_no_numerical_arousal_anxiety_scale():
    """P4State fields are strings (categorical), not numbers.
    ALLOWED_P4_STATES is a dict mapping (arousal, anxiety) -> strategy
    with categorical 'high'/'low' string keys."""
    for (arousal, anxiety), strategy in ALLOWED_P4_STATES.items():
        assert isinstance(arousal, str)
        assert isinstance(anxiety, str)
        assert isinstance(strategy, str)
        assert arousal in ("high", "low")
        assert anxiety in ("high", "low")
        assert strategy in ("approach", "avoidance", "seeking_reassurance", "exploration")
    # Also verify that constructed P4State instances use only strings.
    for (a_val, an_val), strat in ALLOWED_P4_STATES.items():
        s = P4State(arousal=a_val, anxiety=an_val, strategy=strat)
        assert isinstance(s.arousal, str)
        assert isinstance(s.anxiety, str)
        assert isinstance(s.strategy, str)


def test_no_exponential_or_continuous_decay_imported():
    """transient_state module must not import math for decay."""
    from tools.cis_pilot import transient_state

    imported = _imported_module_names(Path(transient_state.__file__))
    forbidden = {"math", "numpy", "random", "statistics"}
    assert forbidden.isdisjoint(imported), f"Forbidden imports: {imported & forbidden}"


# ---------------------------------------------------------------------------
# Invalid P4 fail closed (item 13)
# ---------------------------------------------------------------------------


def test_invalid_p4_state_fails_closed_in_contract():
    """P4State with unknown values must fail at construction."""
    with pytest.raises(ContractValidationError):
        P4State(arousal="medium", anxiety="low", strategy="approach")


def test_invalid_p4_state_not_in_allowed_set():
    """ALLOWED_P4_STATES has exactly 4 entries; invalid keys cannot be looked up."""
    assert len(ALLOWED_P4_STATES) == 4
    assert ("medium", "medium") not in ALLOWED_P4_STATES
    assert ("high", "medium") not in ALLOWED_P4_STATES


def test_wrong_type_stimulus_fails_closed():
    """Passing something other than P4State or None must fail."""
    prev = initial_transient_state()
    with pytest.raises(TransientStateError):
        update_transient_state(prev, "not_a_p4state")  # type: ignore[arg-type]


def test_wrong_type_previous_fails_closed():
    """Previous must be a TransientP4State."""
    with pytest.raises(TransientStateError):
        update_transient_state("not_a_state", None)  # type: ignore[arg-type]


def test_negative_counter_fails_closed():
    """TransientP4State must reject negative turn counters."""
    with pytest.raises(ContractValidationError):
        TransientP4State(
            current=P4_BASELINE_STATE, turns_without_reinforcement=-1
        )


def test_bool_counter_fails_closed():
    """TransientP4State must reject boolean counter (no silent coercion)."""
    with pytest.raises(ContractValidationError):
        TransientP4State(current=P4_BASELINE_STATE, turns_without_reinforcement=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# No persistence / files (item 14)
# ---------------------------------------------------------------------------


def test_transient_updater_creates_no_files():
    """update_transient_state must not create any files or directories."""
    state = initial_transient_state()
    stimulus = P4State(arousal="high", anxiety="low", strategy="approach")
    for _ in range(20):
        state = update_transient_state(state, stimulus)
        state = update_transient_state(state, None)
    assert not (_REPO_ROOT / "local_runs").exists()


# ---------------------------------------------------------------------------
# No network / provider (item 15)
# ---------------------------------------------------------------------------


def test_transient_state_requires_no_network_or_provider():
    """No provider imports in transient_state.py."""
    from tools.cis_pilot import transient_state

    imported = _imported_module_names(Path(transient_state.__file__))
    forbidden_fragments = (
        "openai", "anthropic", "deepseek", "kimi", "ollama",
        "requests", "httpx", "urllib", "socket", "llm_provider",
        "provider_boundary",
    )
    for name in imported:
        for fragment in forbidden_fragments:
            assert fragment not in name.lower(), f"forbidden import {name}"


def test_transient_constants_are_integers():
    """TD-9 constant is an integer > 0."""
    assert isinstance(TRANSIENT_REVERSION_TURNS, int)
    assert TRANSIENT_REVERSION_TURNS > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _imported_module_names(source_path: Path) -> set:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


# ---------------------------------------------------------------------------
# Transient state machine: full stimulus-no-stimulus cycle
# ---------------------------------------------------------------------------


def test_full_stimulus_decay_cycle():
    """Stimulus -> decay over N turns -> revert -> baseline persists."""
    stim = P4State(arousal="high", anxiety="low", strategy="approach")

    # Apply stimulus
    state = update_transient_state(initial_transient_state(), stim)
    assert state.current == stim
    assert state.turns_without_reinforcement == 0

    # Decay: N-1 turns without stimulus -> state retained
    for counter in range(1, TRANSIENT_REVERSION_TURNS):
        state = update_transient_state(state, None)
        assert state.current == stim
        assert state.turns_without_reinforcement == counter

    # Nth turn: reversion
    state = update_transient_state(state, None)
    assert state.current == P4_BASELINE_STATE
    assert state.turns_without_reinforcement == 0

    # Post-reversion: stays baseline
    for _ in range(5):
        state = update_transient_state(state, None)
        assert state.current == P4_BASELINE_STATE


def test_interleaved_stimulus_resets_counter_each_time():
    """Each reinforcing stimulus resets the decay counter."""
    stim = P4State(arousal="high", anxiety="low", strategy="approach")
    state = initial_transient_state()

    for _ in range(10):
        state = update_transient_state(state, stim)
        assert state.turns_without_reinforcement == 0
        state = update_transient_state(state, None)
        assert state.turns_without_reinforcement == 1
        state = update_transient_state(state, stim)
        assert state.turns_without_reinforcement == 0