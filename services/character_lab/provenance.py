#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab V1 runtime-memory provenance taxonomy (minimal, ratified).

Four categories only (Grounded-v2 categories such as MODEL_HYPOTHESIS /
CONFIRMED_RUNTIME_FACT and any automatic truth-promotion are explicitly out of
scope):

- ``USER_STATED``          -- the user said this. NOT "objectively true".
- ``CHARACTER_UTTERANCE``  -- the model/KIRA said this. NEVER an established fact.
- ``SCENE_SETUP``          -- owner-authored situational input for a scene.
- ``LEGACY_UNCLASSIFIED``  -- row predates provenance semantics. Never rewritten
                              to a stronger claim.

Storage stores a raw label or ``NULL``. ``NULL`` / anything unrecognised is
surfaced (never persisted) as ``LEGACY_UNCLASSIFIED``.
"""

from __future__ import annotations

from typing import Optional

USER_STATED = "USER_STATED"
CHARACTER_UTTERANCE = "CHARACTER_UTTERANCE"
SCENE_SETUP = "SCENE_SETUP"
LEGACY_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"

#: The complete V1 taxonomy. Order is presentation-neutral.
V1_PROVENANCE = (USER_STATED, CHARACTER_UTTERANCE, SCENE_SETUP, LEGACY_UNCLASSIFIED)

#: Labels that a runtime dialogue turn is allowed to persist.
PERSISTABLE_DIALOGUE_PROVENANCE = (USER_STATED, CHARACTER_UTTERANCE)


def normalize(raw: Optional[str]) -> str:
    """Map a stored provenance value to a V1 category for display/serialisation.

    A missing / unknown value is honestly reported as ``LEGACY_UNCLASSIFIED`` --
    it is never written back to storage.
    """
    if isinstance(raw, str) and raw in V1_PROVENANCE:
        return raw
    return LEGACY_UNCLASSIFIED


def is_established_fact(_provenance: str) -> bool:
    """No V1 provenance category is an established fact. Ever.

    Present as an explicit, testable statement of the core invariant: a
    ``CHARACTER_UTTERANCE`` (or any other category) must never be automatically
    promoted to canonical truth in V1.
    """
    return False


def display_hint_from_event_type(event_type: str) -> str:
    """A NON-persisted UI hint for legacy rows, derived only from ``event_type``.

    This is a display convenience for ``LEGACY_UNCLASSIFIED`` rows. It is never
    stored and never treated as proven provenance.
    """
    mapping = {
        "USER_MESSAGE": USER_STATED,
        "CHARACTER_MESSAGE": CHARACTER_UTTERANCE,
    }
    return mapping.get(event_type, LEGACY_UNCLASSIFIED)
