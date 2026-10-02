#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.1) -- public API.

Exposes the pure, UI-independent authoring model plus the cross-object
integrity boundary. Self-contained (stdlib only); never imports an existing
service, the Ren'Py exporter, or Character Lab.
"""

from __future__ import annotations

from .errors import ScenarioAuthoringError, ScenarioAuthoringValidationError
from .model import (
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CHARACTER_PROVENANCE_CHARACTER_LAB_VCHAR,
    CHARACTER_PROVENANCE_MANUAL,
    CHARACTER_PROVENANCES,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_MEDIA,
    CONTENT_KIND_TEXT,
    CONTENT_KINDS,
    AuthoredChoice,
    Card,
    CardConnection,
    CharacterReference,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    Project,
    Slide,
    SpeakerOverride,
    Utterance,
    project_from_dict,
    resolve_effective_overrides,
)
from .validation import is_project_consistent, validate_project
from .persistence import (
    STORAGE_SCHEMA_VERSION,
    ProjectStore,
    ScenarioAuthoringCorruptionError,
    ScenarioAuthoringNotFoundError,
    ScenarioAuthoringRecoveryError,
    ScenarioAuthoringStorageError,
)

__all__ = [
    # Model
    "Project",
    "Card",
    "Slide",
    "ContentItem",
    "Utterance",
    "DisplayPortion",
    "MediaReference",
    "SpeakerOverride",
    "AuthoredChoice",
    "ChoiceOption",
    "CardConnection",
    "CharacterReference",
    # Constants
    "SCENARIO_AUTHORING_SCHEMA_VERSION",
    "CONTENT_KIND_TEXT",
    "CONTENT_KIND_CHOICE",
    "CONTENT_KIND_MEDIA",
    "CONTENT_KINDS",
    "CHARACTER_PROVENANCE_MANUAL",
    "CHARACTER_PROVENANCE_CHARACTER_LAB_VCHAR",
    "CHARACTER_PROVENANCES",
    # Functions
    "project_from_dict",
    "resolve_effective_overrides",
    "validate_project",
    "is_project_consistent",
    # Errors
    "ScenarioAuthoringError",
    "ScenarioAuthoringValidationError",
    # Persistence (SE-1.2)
    "STORAGE_SCHEMA_VERSION",
    "ProjectStore",
    "ScenarioAuthoringStorageError",
    "ScenarioAuthoringNotFoundError",
    "ScenarioAuthoringCorruptionError",
    "ScenarioAuthoringRecoveryError",
]
