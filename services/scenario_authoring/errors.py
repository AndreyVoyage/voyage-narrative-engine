#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for the Scenario Authoring foundation (SE-1.1).

Small, transport-independent, named exceptions. Messages carry only stable
logical identifiers and field names -- never absolute machine paths, media
bytes, or Character Canon content.
"""

from __future__ import annotations


class ScenarioAuthoringError(Exception):
    """Root of the scenario-authoring exception hierarchy."""


class ScenarioAuthoringValidationError(ScenarioAuthoringError):
    """Raised on a MODEL-validity violation: wrong schema version, an invalid
    or duplicate stable ID, an impossible content-item payload combination, an
    invalid media reference, an invalid Display Portion segmentation, or a
    dangling ``start_card_id`` / duplicate membership.

    Construction-time invariants raise this; cross-object integrity checks
    (``services/scenario_authoring/validation.py``) instead return a list of
    human-readable violations rather than raising.
    """
