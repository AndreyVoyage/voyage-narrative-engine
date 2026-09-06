#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core epistemic foundation -- point-in-time visibility (pure).

Proves: WORLD_FACT is not automatic character knowledge; a holder always sees
their own belief/interpretation; explicit perceivers (and only they) see other
kinds; causal-sequence cutoffs are respected in both directions; contradictory
envelopes coexist and the selector never reconciles them; malformed envelopes
fail closed; and the production module carries no character-specific rule.

Offline, standard-library only, no provider.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from services.character_core.epistemics import (
    HOLDER_ADDRESSABLE_KINDS,
    EpistemicEnvelope,
    EpistemicEnvelopeError,
    EpistemicKind,
    EpistemicVisibility,
    assess_epistemic_visibility,
    is_holder_addressable,
    select_visible_epistemic_context,
)

_MODULE = Path(__file__).resolve().parents[2] / "services" / "character_core" / "epistemics.py"


def _vis(env, who, seq):
    return assess_epistemic_visibility(env, perceiver_id=who, at_seq=seq)


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------


def test_kind_values_are_stable_and_distinct():
    assert [k.value for k in EpistemicKind] == [
        "WORLD_FACT",
        "USER_REPORT",
        "CHARACTER_BELIEF",
        "CHARACTER_INTERPRETATION",
    ]
    assert HOLDER_ADDRESSABLE_KINDS == (
        EpistemicKind.CHARACTER_BELIEF,
        EpistemicKind.CHARACTER_INTERPRETATION,
    )
    assert is_holder_addressable("CHARACTER_BELIEF")
    assert is_holder_addressable(EpistemicKind.CHARACTER_INTERPRETATION)
    assert not is_holder_addressable("WORLD_FACT")
    assert not is_holder_addressable("USER_REPORT")


# --------------------------------------------------------------------------
# 1 + 2. WORLD_FACT: truth alone is not knowledge
# --------------------------------------------------------------------------


def test_1_world_fact_with_no_perceiver_is_invisible_to_a_character():
    fact = EpistemicEnvelope(
        meaning="The door is locked.",
        epistemic_kind="WORLD_FACT",
        provenance="scene_state",
        basis_event_ids=("evt-10",),
        confidence=1.0,
        valid_from_seq=10,
    )
    r = _vis(fact, "kira", 11)
    assert r.visible is False
    assert r.reason is EpistemicVisibility.NOT_AVAILABLE_TO_PERCEIVER


def test_2_world_fact_with_explicit_perceiver_is_visible():
    fact = EpistemicEnvelope(
        meaning="The door is locked.",
        epistemic_kind="WORLD_FACT",
        provenance="scene_state",
        basis_event_ids=("evt-10",),
        confidence=1.0,
        perceiver_ids=("kira",),
        valid_from_seq=10,
    )
    r = _vis(fact, "kira", 11)
    assert r.visible is True and r.reason is EpistemicVisibility.VISIBLE


# --------------------------------------------------------------------------
# 3 + 4 + 11. USER_REPORT: point-in-time + explicit perceiver only
# --------------------------------------------------------------------------


def _report():
    return EpistemicEnvelope(
        meaning="Марина уже уехала.",
        epistemic_kind="USER_REPORT",
        provenance="dialogue_turn",
        basis_event_ids=("evt-30",),
        confidence=0.6,
        holder_id="andrey",
        perceiver_ids=("kira",),
        valid_from_seq=30,
    )


def test_3_user_report_respects_the_causal_cutoff():
    rep = _report()
    assert _vis(rep, "kira", 29).visible is False
    assert _vis(rep, "kira", 29).reason is EpistemicVisibility.NOT_YET_VALID
    assert _vis(rep, "kira", 30).visible is True
    assert _vis(rep, "kira", 31).visible is True


def test_4_and_7_only_explicit_perceivers_see_it_no_inheritance():
    rep = _report()
    # a different character is never a perceiver here
    assert _vis(rep, "nika", 40).visible is False
    assert _vis(rep, "nika", 40).reason is EpistemicVisibility.NOT_AVAILABLE_TO_PERCEIVER
    # even the holder of a USER_REPORT is not an implicit perceiver
    assert _vis(rep, "andrey", 40).visible is False
    # adding the perceiver explicitly grants access
    rep2 = EpistemicEnvelope(
        meaning=rep.meaning, epistemic_kind="USER_REPORT", provenance="dialogue_turn",
        basis_event_ids=("evt-30",), confidence=0.6, holder_id="andrey",
        perceiver_ids=("kira", "nika"), valid_from_seq=30,
    )
    assert _vis(rep2, "nika", 40).visible is True


def test_11_no_retroactive_knowledge_via_the_selector():
    rep = _report()
    assert select_visible_epistemic_context([rep], perceiver_id="kira", at_seq=29) == ()
    assert select_visible_epistemic_context([rep], perceiver_id="kira", at_seq=30) == (rep,)


# --------------------------------------------------------------------------
# 5 + 6 + 7. Holder access to own belief / interpretation
# --------------------------------------------------------------------------


def _belief():
    return EpistemicEnvelope(
        meaning="The door is unlocked.",
        epistemic_kind="CHARACTER_BELIEF",
        provenance="prior_scene",
        basis_event_ids=("evt-5",),
        confidence=0.7,
        holder_id="kira",
        valid_from_seq=5,
    )


def _interpretation():
    return EpistemicEnvelope(
        meaning="Он, возможно, раздражён.",
        epistemic_kind="CHARACTER_INTERPRETATION",
        provenance="derived_from_turn",
        basis_event_ids=("evt-42",),
        confidence=0.4,
        holder_id="kira",
        valid_from_seq=42,
    )


def test_5_holder_sees_own_belief_without_being_listed_as_perceiver():
    b = _belief()
    assert b.perceiver_ids == ()
    assert _vis(b, "kira", 6).visible is True
    assert _vis(b, "kira", 4).reason is EpistemicVisibility.NOT_YET_VALID


def test_6_holder_sees_own_interpretation():
    i = _interpretation()
    assert _vis(i, "kira", 42).visible is True
    assert _vis(i, "kira", 100).visible is True


def test_7_other_character_cannot_see_a_private_belief_unless_added():
    b = _belief()
    assert _vis(b, "nika", 50).visible is False
    assert _vis(b, "nika", 50).reason is EpistemicVisibility.NOT_AVAILABLE_TO_PERCEIVER
    shared = EpistemicEnvelope(
        meaning=b.meaning, epistemic_kind="CHARACTER_BELIEF", provenance="prior_scene",
        basis_event_ids=("evt-5",), confidence=0.7, holder_id="kira",
        perceiver_ids=("nika",), valid_from_seq=5,
    )
    assert _vis(shared, "nika", 50).visible is True


def test_world_fact_and_user_report_get_no_holder_visibility():
    # holder_id set, but NOT a holder-addressable kind -> holder still needs
    # to be an explicit perceiver
    wf = EpistemicEnvelope(
        meaning="X happened.", epistemic_kind="WORLD_FACT", provenance="scene_state",
        basis_event_ids=("evt-1",), confidence=1.0, holder_id="kira",
    )
    assert _vis(wf, "kira", 5).visible is False


# --------------------------------------------------------------------------
# 8. valid_to_seq boundary (inclusive)
# --------------------------------------------------------------------------


def test_8_valid_to_seq_is_inclusive_then_expires():
    env = EpistemicEnvelope(
        meaning="A transient condition.",
        epistemic_kind="WORLD_FACT",
        provenance="scene_state",
        basis_event_ids=("evt-12",),
        confidence=0.9,
        perceiver_ids=("kira",),
        valid_from_seq=12,
        valid_to_seq=20,
    )
    assert _vis(env, "kira", 12).visible is True   # lower boundary inclusive
    assert _vis(env, "kira", 20).visible is True   # upper boundary inclusive
    assert _vis(env, "kira", 21).visible is False
    assert _vis(env, "kira", 21).reason is EpistemicVisibility.NO_LONGER_VALID
    assert _vis(env, "kira", 11).reason is EpistemicVisibility.NOT_YET_VALID


def test_unbounded_intervals():
    env = EpistemicEnvelope(
        meaning="Always-on.", epistemic_kind="WORLD_FACT", provenance="scene_state",
        basis_event_ids=("evt-0",), confidence=1.0, perceiver_ids=("kira",),
    )
    assert _vis(env, "kira", -999).visible is True
    assert _vis(env, "kira", 10**9).visible is True


# --------------------------------------------------------------------------
# 9 + 10. Contradictions coexist; the selector never reconciles
# --------------------------------------------------------------------------


def test_9_and_10_contradictory_fact_and_belief_coexist_selector_keeps_both():
    world = EpistemicEnvelope(
        meaning="The door is locked.", epistemic_kind="WORLD_FACT",
        provenance="scene_state", basis_event_ids=("evt-10",), confidence=1.0,
        perceiver_ids=("kira",), valid_from_seq=10,
    )
    belief = EpistemicEnvelope(
        meaning="The door is unlocked.", epistemic_kind="CHARACTER_BELIEF",
        provenance="prior_scene", basis_event_ids=("evt-5",), confidence=0.7,
        holder_id="kira", valid_from_seq=5,
    )
    # Kira only ever perceived the world fact here because it lists her; her
    # own belief is always hers. Both are visible and BOTH are returned.
    ctx = select_visible_epistemic_context([world, belief], perceiver_id="kira", at_seq=15)
    assert ctx == (world, belief)
    assert {e.epistemic_kind for e in ctx} == {
        EpistemicKind.WORLD_FACT, EpistemicKind.CHARACTER_BELIEF
    }
    # opposite meanings survive side by side -- nothing was reconciled
    assert sorted(e.meaning for e in ctx) == ["The door is locked.", "The door is unlocked."]

    # Kira with ONLY her belief (never perceived the fact): context is the
    # belief, not "the truth".
    world_unseen = EpistemicEnvelope(
        meaning="The door is locked.", epistemic_kind="WORLD_FACT",
        provenance="scene_state", basis_event_ids=("evt-10",), confidence=1.0,
        valid_from_seq=10,
    )
    ctx2 = select_visible_epistemic_context(
        [world_unseen, belief], perceiver_id="kira", at_seq=15
    )
    assert ctx2 == (belief,)


def test_interpretation_stays_distinct_from_world_fact():
    interp = _interpretation()
    world = EpistemicEnvelope(
        meaning="Andrey is irritated.", epistemic_kind="WORLD_FACT",
        provenance="scene_state", basis_event_ids=("evt-42",), confidence=1.0,
        valid_from_seq=42,
    )
    assert interp.epistemic_kind is EpistemicKind.CHARACTER_INTERPRETATION
    assert world.epistemic_kind is EpistemicKind.WORLD_FACT
    ctx = select_visible_epistemic_context([interp, world], perceiver_id="kira", at_seq=45)
    assert ctx == (interp,)  # the world fact was never perceived by Kira


def test_selector_preserves_input_order_and_does_not_deduplicate():
    a = EpistemicEnvelope(
        meaning="same text", epistemic_kind="USER_REPORT", provenance="turn_a",
        basis_event_ids=("evt-a",), confidence=0.5, perceiver_ids=("kira",), valid_from_seq=1,
    )
    b = EpistemicEnvelope(
        meaning="same text", epistemic_kind="USER_REPORT", provenance="turn_b",
        basis_event_ids=("evt-b",), confidence=0.5, perceiver_ids=("kira",), valid_from_seq=1,
    )
    c = EpistemicEnvelope(
        meaning="third", epistemic_kind="USER_REPORT", provenance="turn_c",
        basis_event_ids=("evt-c",), confidence=0.5, perceiver_ids=("kira",), valid_from_seq=1,
    )
    ctx = select_visible_epistemic_context([b, a, c], perceiver_id="kira", at_seq=5)
    assert ctx == (b, a, c)  # order preserved, both "same text" envelopes kept


def test_selector_does_not_mutate_input():
    env = _report()
    src = [env]
    before = (env.meaning, env.perceiver_ids, env.valid_from_seq)
    select_visible_epistemic_context(src, perceiver_id="kira", at_seq=40)
    assert src == [env]
    assert (env.meaning, env.perceiver_ids, env.valid_from_seq) == before


# --------------------------------------------------------------------------
# 12 - 16. Fail-closed validation
# --------------------------------------------------------------------------


_BASE = dict(
    meaning="claim", epistemic_kind="WORLD_FACT", provenance="scene_state",
    basis_event_ids=("evt-1",), confidence=0.5,
)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0, float("nan"), float("inf"), float("-inf"), True, False, "0.5"])
def test_12_malformed_confidence_rejected(bad):
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "confidence": bad})


def test_confidence_boundaries_accepted():
    for ok in (0.0, 1.0, 0.5, 0, 1):
        e = EpistemicEnvelope(**{**_BASE, "confidence": ok})
        assert 0.0 <= e.confidence <= 1.0
        assert isinstance(e.confidence, float)


def test_13_empty_meaning_provenance_or_basis_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "meaning": "   "})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "provenance": ""})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "basis_event_ids": ()})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "basis_event_ids": ("evt-1", "  ")})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "basis_event_ids": "evt-1"})  # bare string


def test_14_duplicate_basis_ids_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "basis_event_ids": ("evt-1", "evt-1")})


def test_15_duplicate_or_blank_perceiver_ids_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "perceiver_ids": ("kira", "kira")})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "perceiver_ids": ("kira", " ")})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "perceiver_ids": "kira"})  # bare string


def test_blank_holder_id_when_supplied_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "holder_id": "   "})


def test_belief_and_interpretation_require_a_holder():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "epistemic_kind": "CHARACTER_BELIEF"})
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "epistemic_kind": "CHARACTER_INTERPRETATION"})
    # but with a holder they build fine
    EpistemicEnvelope(**{**_BASE, "epistemic_kind": "CHARACTER_BELIEF", "holder_id": "kira"})


def test_16_invalid_temporal_interval_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "valid_from_seq": 20, "valid_to_seq": 19})
    # equal bounds are a valid single-point window
    e = EpistemicEnvelope(**{**_BASE, "valid_from_seq": 20, "valid_to_seq": 20,
                             "perceiver_ids": ("kira",)})
    assert _vis(e, "kira", 20).visible is True
    assert _vis(e, "kira", 19).visible is False
    assert _vis(e, "kira", 21).visible is False


@pytest.mark.parametrize("bad_seq", [1.5, "5", True])
def test_non_integer_temporal_bounds_rejected(bad_seq):
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "valid_from_seq": bad_seq})


def test_none_temporal_bounds_are_the_unbounded_sentinel():
    e = EpistemicEnvelope(**{**_BASE, "valid_from_seq": None, "valid_to_seq": None,
                             "perceiver_ids": ("kira",)})
    assert e.valid_from_seq is None and e.valid_to_seq is None
    assert _vis(e, "kira", 0).visible is True


def test_unknown_epistemic_kind_rejected():
    with pytest.raises(EpistemicEnvelopeError):
        EpistemicEnvelope(**{**_BASE, "epistemic_kind": "GOSSIP"})


def test_envelope_is_immutable():
    e = EpistemicEnvelope(**_BASE)
    with pytest.raises(Exception):
        e.meaning = "changed"  # type: ignore[misc]


def test_query_validates_its_own_args():
    e = EpistemicEnvelope(**{**_BASE, "perceiver_ids": ("kira",)})
    with pytest.raises(EpistemicEnvelopeError):
        assess_epistemic_visibility(e, perceiver_id="", at_seq=1)
    with pytest.raises(EpistemicEnvelopeError):
        assess_epistemic_visibility(e, perceiver_id="kira", at_seq=1.5)
    with pytest.raises(EpistemicEnvelopeError):
        assess_epistemic_visibility("not-an-envelope", perceiver_id="kira", at_seq=1)


# --------------------------------------------------------------------------
# 17. No character-specific behavior in the production module
# --------------------------------------------------------------------------


def test_17_production_module_has_no_character_specific_rule():
    src = _MODULE.read_text(encoding="utf-8").lower()
    for forbidden in ("kira", "andrey", "nika", "marina", "sergey", "deepseek"):
        assert forbidden not in src, forbidden
    # no id-literal branching / hard-coded perceiver identities
    assert 'holder_id ==' in src  # generic comparison IS expected
    assert 'perceiver_id == "' not in src
    assert 'holder_id == "' not in src


def test_perceiver_check_precedes_temporal_check():
    # a perceiver who is never permitted gets NOT_AVAILABLE_TO_PERCEIVER even
    # when the query time is also outside the window.
    e = EpistemicEnvelope(**{**_BASE, "perceiver_ids": ("kira",),
                             "valid_from_seq": 30, "valid_to_seq": 40})
    r = _vis(e, "nika", 5)
    assert r.reason is EpistemicVisibility.NOT_AVAILABLE_TO_PERCEIVER
