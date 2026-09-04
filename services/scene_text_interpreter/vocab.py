#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlled v0 scene-tag vocabulary for the Scene Text Interpreter.

OWNER_DECISION #8 (preflight recommended default): the interpreter may emit
ONLY these tokens. The Reference Semantic Catalog uses open tag strings, but
v0 is deliberately bounded so the proposal never invents synonyms that can
never match the catalog. Deterministic re-validation rejects anything else.

Rule (preflight): the interpreter must NOT re-emit the resolved ``location_id``
as a scene tag -- the AUTO reference selector already prepends the location.
"""

from __future__ import annotations

# Ordered for stable presentation; membership is what matters.
SCENE_TAG_VOCAB_V0: tuple[str, ...] = (
    "gym",
    "yoga",
    "stretching",
    "training",
    "motion",
    "neutral",
    "athletic",
)

_VOCAB_SET = frozenset(SCENE_TAG_VOCAB_V0)


def is_allowed_scene_tag(tag: str) -> bool:
    """Return True iff ``tag`` is in the controlled v0 vocabulary."""
    return tag in _VOCAB_SET
