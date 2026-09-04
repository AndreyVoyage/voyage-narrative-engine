#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for the Scene Text Interpreter v0.

The interpreter treats the semantic component as an UNTRUSTED PROPOSER. Every
error here is raised by the DETERMINISTIC validator when a proposal cannot be
independently verified against the submitted source text and the closed
allowlists. The interpreter never "repairs" a semantic hallucination -- it
fails closed.
"""

from __future__ import annotations


class SceneTextInterpreterError(Exception):
    """Root of the Scene Text Interpreter exception hierarchy."""


class AliasDataError(SceneTextInterpreterError):
    """A VNE-owned alias/config data file is missing, malformed, references an
    unknown roster id, or defines an ambiguous surface alias."""


class ProposalSchemaError(SceneTextInterpreterError):
    """The untrusted proposal is not shaped like a valid interpretation
    (missing field, wrong type, malformed JSON, duplicate/conflicting id)."""


class GroundingError(SceneTextInterpreterError):
    """A proposed evidence span is not a verbatim substring of the submitted
    source text, so the claim it supports is not grounded."""


class HallucinationError(SceneTextInterpreterError):
    """The proposal names a character/location/action outside the grounded
    source evidence or the closed allowlists, or contradicts a deterministic
    resolution."""


class CharacterResolutionError(SceneTextInterpreterError):
    """A surface name cannot be resolved to exactly one allowed character."""


class CharacterCountError(SceneTextInterpreterError):
    """The number of grounded in-frame characters is outside the v0 bound
    (exactly two)."""


class LocationResolutionError(SceneTextInterpreterError):
    """A location cannot be resolved to exactly one allowed Location Canon id,
    or resolution is ambiguous."""


class SceneTagError(SceneTextInterpreterError):
    """A proposed scene tag is outside the controlled v0 vocabulary, or
    duplicates the resolved location id."""


class ConfidenceError(SceneTextInterpreterError):
    """The proposer did not return high confidence; v0 fails closed."""


class UnresolvedItemsError(SceneTextInterpreterError):
    """The proposal left a mandatory item unresolved."""


class StillSelectionError(SceneTextInterpreterError):
    """No proposed still candidate can be grounded and scored above the v0
    threshold (fail closed -- never emit an ungrounded still)."""


class PlanLoadError(SceneTextInterpreterError):
    """A persisted SceneStillPlan is malformed, tampered (recomputed
    content_hash mismatch), the wrong schema/status, or fails a bridge
    invariant. Replay fails closed and never falls back to a semantic call."""
