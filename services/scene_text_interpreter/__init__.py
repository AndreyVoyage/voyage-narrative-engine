#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- public API.

An AUTHORING interpretation boundary that turns ordinary scene prose into a
deterministically validated, frozen ``SceneStillPlan`` (status ``"DRAFT"``).

Design rule: the semantic component is an UNTRUSTED PROPOSER. It may propose
character ids, one location id, actions/interaction facts, scene tags from the
controlled v0 vocabulary, still candidates, and grounding evidence -- but a
deterministic validator independently verifies schema, closed allowlists,
alias resolution, source-substring grounding, character count, and still
completeness, and FAILS CLOSED on any violation. Chain-of-thought is never
requested or stored; evidence is source substrings only.

This package performs NO provider call, NO network I/O, NO NCC read, and NEVER
mutates an accepted ASS or any Canon.
"""

from __future__ import annotations

from .aliases import (
    load_character_roster,
    load_location_roster,
    resolve_character,
    resolve_location,
)
from .errors import (
    AliasDataError,
    CharacterCountError,
    CharacterResolutionError,
    ConfidenceError,
    GroundingError,
    HallucinationError,
    LocationResolutionError,
    PlanLoadError,
    ProposalSchemaError,
    SceneTagError,
    SceneTextInterpreterError,
    StillSelectionError,
    UnresolvedItemsError,
)
from .hashing import canonical_source, match_key, source_text_hash
from .interpreter import build_interpreter_input, interpret_scene_text
from .model import (
    DRAFT_STATUS,
    PROPOSAL_SCHEMA_VERSION,
    STILL_PLAN_SCHEMA_VERSION,
    AllowedCharacter,
    AllowedLocation,
    ChosenStill,
    InterpreterInput,
    PlanBeat,
    ProposedBeat,
    ProposedCharacter,
    ProposedInterpretation,
    ProposedStillCandidate,
    SceneStillPlan,
    StillCandidate,
)
from .plan_io import load_scene_still_plan
from .proposer import FixtureProposer, MockProposer, SceneTextProposer
from .validation import validate_and_build_plan
from .vocab import SCENE_TAG_VOCAB_V0, is_allowed_scene_tag

__all__ = [
    # orchestration
    "build_interpreter_input",
    "interpret_scene_text",
    "validate_and_build_plan",
    "load_scene_still_plan",
    # proposers
    "SceneTextProposer",
    "MockProposer",
    "FixtureProposer",
    # models
    "InterpreterInput",
    "AllowedCharacter",
    "AllowedLocation",
    "ProposedInterpretation",
    "ProposedCharacter",
    "ProposedBeat",
    "ProposedStillCandidate",
    "SceneStillPlan",
    "PlanBeat",
    "StillCandidate",
    "ChosenStill",
    "STILL_PLAN_SCHEMA_VERSION",
    "PROPOSAL_SCHEMA_VERSION",
    "DRAFT_STATUS",
    # alias resolution
    "load_character_roster",
    "load_location_roster",
    "resolve_character",
    "resolve_location",
    # vocab + hashing helpers
    "SCENE_TAG_VOCAB_V0",
    "is_allowed_scene_tag",
    "canonical_source",
    "match_key",
    "source_text_hash",
    # errors
    "SceneTextInterpreterError",
    "AliasDataError",
    "PlanLoadError",
    "ProposalSchemaError",
    "GroundingError",
    "HallucinationError",
    "CharacterResolutionError",
    "CharacterCountError",
    "LocationResolutionError",
    "SceneTagError",
    "ConfidenceError",
    "UnresolvedItemsError",
    "StillSelectionError",
]
