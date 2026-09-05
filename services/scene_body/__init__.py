#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Body v1 -- public API.

Exposes the single authoritative editable ordered body (``SceneBody``) plus the
acceptance-completeness validation boundary. This package is self-contained and
stdlib-only; it never imports ``services.ass``, ``tools`` (except the asset-id
syntax constant in ``validation``), personas, the exporter, or Ren'Py.
"""

from __future__ import annotations

from .model import (
    AUTHORING_SCHEMA_VERSION,
    ENTRY_KIND_CHOICE,
    ENTRY_KIND_TEXT,
    ENTRY_KIND_VISUAL_CHANGE,
    TARGET_KIND_ENTRY,
    TARGET_KIND_SCENE,
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_NARRATIVE,
    TEXT_PRESENTATION_THOUGHT,
    THOUGHT_VISIBILITIES,
    VISUAL_OP_CLEAR,
    VISUAL_OP_SET,
    ChoiceEntry,
    ChoiceOption,
    ChoiceTarget,
    Entry,
    LocationStateOverride,
    Participant,
    SceneBody,
    SceneBodyAcceptanceError,
    SceneBodyError,
    SceneBodyValidationError,
    TextEntry,
    VisualChangeEvent,
)
from .validation import is_acceptance_complete, validate_acceptance_complete

__all__ = [
    # Model
    "SceneBody",
    "Entry",
    "Participant",
    "TextEntry",
    "ChoiceEntry",
    "ChoiceOption",
    "ChoiceTarget",
    "VisualChangeEvent",
    "LocationStateOverride",
    # Constants
    "AUTHORING_SCHEMA_VERSION",
    "ENTRY_KIND_TEXT",
    "ENTRY_KIND_CHOICE",
    "ENTRY_KIND_VISUAL_CHANGE",
    "TEXT_PRESENTATION_NARRATIVE",
    "TEXT_PRESENTATION_DIALOGUE",
    "TEXT_PRESENTATION_THOUGHT",
    "THOUGHT_VISIBILITIES",
    "VISUAL_OP_SET",
    "VISUAL_OP_CLEAR",
    "TARGET_KIND_ENTRY",
    "TARGET_KIND_SCENE",
    # Validation
    "validate_acceptance_complete",
    "is_acceptance_complete",
    # Errors
    "SceneBodyError",
    "SceneBodyValidationError",
    "SceneBodyAcceptanceError",
]
