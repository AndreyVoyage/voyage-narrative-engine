#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA dimension-semantics behavioral A/B SPEC (prepared, NOT executed live).

A pre-registered directional rubric for the first behavioral validation of the
KIRA dimension-semantics extension. It fixes everything except one numeric
state value and records the direction each rubric axis is expected to move --
never an exact output wording (OD-MEM-EVO-12).

The experiment input is now fully specified and reproducible:

- ``SHARED_USER_INPUT`` -- the single exact user message used for all four
  arms (two TRUST arms + two STRESS arms), byte-for-byte;
- ``SHARED_SCENE`` -- Python ``None``, meaning NO scene object is supplied
  (distinct from a scene whose text happens to be the string ``"NONE"``);
- ``SHARED_MEMORY`` -- an empty runtime-memory baseline in every arm.

This module is a SPEC/fixture only. It performs no provider call. A future
bounded live A/B task consumes it.
"""

from __future__ import annotations

# The exact user message. Identical, unchanged, for all four arms.
SHARED_USER_INPUT = (
    "Кира, мне важно понять, что с тобой сейчас происходит. Расскажи столько, "
    "сколько считаешь нужным: что тебя сейчас больше всего тревожит и чем я "
    "могу помочь?"
)

# Explicit "no scene": a real absence of a scene object, NOT a scene whose
# content is the literal word "NONE". The live runner must pass no scene.
SHARED_SCENE = None

# Every arm starts from an empty runtime-memory baseline (no prior events).
SHARED_MEMORY = "empty"

# Held constant across every run of a given A/B pair.
SHARED_SETUP = {
    "character_id": "kira",
    "variant_id": "KIRA_GROUNDED_V2",
    "accepted_source_hash": "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd",
    "dimension_semantics_extension": "character_packages/kira/extensions/dimension_semantics/v1.json",
    "package": "same",
    "memory": SHARED_MEMORY,
    "scene": SHARED_SCENE,
    "scene_present": False,
    "user_input": SHARED_USER_INPUT,
}

# What every runner MUST hold identical between the two arms of a pair; only
# the single tested dimension key may differ.
_PAIR_ISOLATION_COMMON = (
    "Accepted KIRA package (accepted_source_hash)",
    "Grounded v2 variant",
    "dimension-semantics extension v1",
    "user_input (SHARED_USER_INPUT)",
    "scene = NONE (SHARED_SCENE is None)",
    "empty runtime-memory baseline",
    "all unrelated runtime state",
)

# direction: value in the VERY_HIGH arm relative to the LOW arm.
TRUST_AB_SPEC = {
    "dimension": {"domain": "RELATIONSHIP", "key": "andrey.trust", "id": "trust"},
    "arms": {"low": {"value": -40, "band": "LOW"}, "very_high": {"value": 80, "band": "VERY_HIGH"}},
    "vary_only": "andrey.trust",
    "directional_rubric": {
        "willingness_to_disclose": "higher",
        "cooperation": "higher",
        "defensiveness": "lower",
        "suspicion": "lower",
        "social_distance": "lower",
    },
    "must_not_change": [
        "character boundaries",
        "canon",
        "safety posture",
        "established relationship facts",
    ],
    "pair_isolation": {
        "identical_across_arms": list(_PAIR_ISOLATION_COMMON),
        "varies": "andrey.trust",
        "other_numeric_state": {
            "PSYCHOLOGY/stress": "absent / unset in BOTH arms",
            "other RELATIONSHIP keys": "absent / unset in BOTH arms",
        },
    },
    "exact_wording_required": False,
}

STRESS_AB_SPEC = {
    "dimension": {"domain": "PSYCHOLOGY", "key": "stress", "id": "stress"},
    "arms": {"low": {"value": -40, "band": "LOW"}, "very_high": {"value": 80, "band": "VERY_HIGH"}},
    "vary_only": "stress",
    "directional_rubric": {
        "tension": "higher",
        "patience": "lower",
        "response_compression": "higher",
        "emotional_regulation": "lower",
        "cognitive_spaciousness": "lower",
    },
    "must_not_change": [
        "hostility (must not become hostile by definition)",
        "rationality (must not become irrational by definition)",
        "canon",
        "identity and boundaries",
    ],
    "pair_isolation": {
        "identical_across_arms": list(_PAIR_ISOLATION_COMMON),
        "varies": "stress",
        "other_numeric_state": {
            "RELATIONSHIP/*": "absent / unset in BOTH arms",
            "other PSYCHOLOGY keys": "absent / unset in BOTH arms",
        },
    },
    "exact_wording_required": False,
}

BEHAVIORAL_AB_SPECS = {"trust": TRUST_AB_SPEC, "stress": STRESS_AB_SPEC}
