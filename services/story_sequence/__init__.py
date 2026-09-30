#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story Sequence v0 -- public API.

Scenario-owned story-level structure above immutable accepted scenes: the
canonical project scene order (``ordered_scene_ids``) and the designated entry
scene (``start_scene_id``). No story graph, no conditions/flags/variables, no
player state, no media/characters/locations, no workspace membership, no
runtime state, and no scene-to-scene runtime control flow.

This package is stdlib-only and never imports ``services.ass``, ``tools``,
personas, or Ren'Py. ``services/__init__.py`` is intentionally absent
(implicit PEP 420 namespace package).
"""

from __future__ import annotations

from .batch_validation import validate_against_batch
from .errors import (
    StorySequenceBatchValidationError,
    StorySequenceError,
    StorySequenceNotFoundError,
    StorySequenceStoreError,
    StorySequenceValidationError,
)
from .manifest import (
    load_story_sequence,
    parse_story_sequence,
    save_story_sequence,
    serialize_story_sequence,
    validate_story_sequence,
)
from .model import STORY_SEQUENCE_SCHEMA_VERSION, StorySequence

__all__ = [
    "StorySequence",
    "STORY_SEQUENCE_SCHEMA_VERSION",
    "serialize_story_sequence",
    "parse_story_sequence",
    "load_story_sequence",
    "save_story_sequence",
    "validate_story_sequence",
    "validate_against_batch",
    "StorySequenceError",
    "StorySequenceValidationError",
    "StorySequenceStoreError",
    "StorySequenceNotFoundError",
    "StorySequenceBatchValidationError",
]
