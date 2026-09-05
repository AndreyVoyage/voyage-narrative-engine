#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SYNTHETIC dimension definitions for Character Core semantic tests.

These are TEST FIXTURES ONLY. They are NOT KIRA canon, NOT an Accepted
Character Package, and NOT a repository serialization format -- they exist
purely to prove that numeric-state meaning is CHARACTER-PACKAGE-DECLARED and
that Character Core carries no built-in dimension semantics.

``trust`` and ``stress`` here are illustrative examples of a RELATIONSHIP and
a PSYCHOLOGY dimension; nothing in Character Core requires either to exist.
"""

from __future__ import annotations

from services.character_core.dimensions import DimensionSet

# A synthetic, non-canon test character identity.
SYNTHETIC_CHARACTER_ID = "testchar"

# RELATIONSHIP dimension -- id is the dimension only; the runtime key stays
# "<subject>.trust" and the subject is runtime data, never part of this def.
TRUST_DEFINITION_DICT = {
    "domain": "RELATIONSHIP",
    "id": "trust",
    "label": "Trust",
    "description": "How reliable and safe this subject feels to the character.",
    "band_meanings": {
        "VERY_LOW": "strong distrust of this subject",
        "LOW": "low trust in this subject",
        "MID": "uncertain / neutral trust in this subject",
        "HIGH": "high trust in this subject",
        "VERY_HIGH": "strong trust toward this subject",
    },
    "band_guidance": {
        "VERY_LOW": "guards information; expects bad intent",
        "VERY_HIGH": "shares openly; assumes good intent",
    },
}

# PSYCHOLOGY dimension -- id is the whole runtime key.
STRESS_DEFINITION_DICT = {
    "domain": "PSYCHOLOGY",
    "id": "stress",
    "label": "Stress",
    "description": "The character's current internal stress load.",
    "band_meanings": {
        "VERY_LOW": "very low current stress",
        "LOW": "low current stress",
        "MID": "moderate / baseline current stress",
        "HIGH": "high current stress",
        "VERY_HIGH": "severe current stress",
    },
}

SYNTHETIC_DIMENSION_DICTS = [TRUST_DEFINITION_DICT, STRESS_DEFINITION_DICT]


def synthetic_dimension_set() -> DimensionSet:
    """A validated DimensionSet with the synthetic trust + stress dimensions."""
    return DimensionSet.from_dicts(SYNTHETIC_DIMENSION_DICTS)
