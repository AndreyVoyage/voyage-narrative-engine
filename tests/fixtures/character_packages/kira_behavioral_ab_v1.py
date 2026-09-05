#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA dimension-semantics behavioral A/B SPEC (prepared, NOT executed live).

A pre-registered directional rubric for the first behavioral validation of the
KIRA dimension-semantics extension. It fixes everything except one numeric
state value and records the direction each rubric axis is expected to move --
never an exact output wording (OD-MEM-EVO-12).

This module is a SPEC/fixture only. It performs no provider call. A future
bounded live A/B task consumes it.
"""

from __future__ import annotations

# Held constant across every run of a given A/B pair.
SHARED_SETUP = {
    "character_id": "kira",
    "variant_id": "KIRA_GROUNDED_V2",
    "accepted_source_hash": "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd",
    "package": "same",
    "memory": "same",
    "scene": "same",
    "user_input": "same",
}

# direction: value in the VERY_HIGH arm relative to the LOW arm.
TRUST_AB_SPEC = {
    "dimension": {"domain": "RELATIONSHIP", "key": "test_subject.trust", "id": "trust"},
    "arms": {"low": {"value": -40, "band": "LOW"}, "very_high": {"value": 80, "band": "VERY_HIGH"}},
    "vary_only": "test_subject.trust",
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
    "exact_wording_required": False,
}

BEHAVIORAL_AB_SPECS = {"trust": TRUST_AB_SPEC, "stress": STRESS_AB_SPEC}
