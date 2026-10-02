#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.1) -- public API.

Exposes the pure, UI-independent authoring model plus the cross-object
integrity boundary, local persistence (SE-1.2), and the deterministic
authoring->OrderedASS projection boundary (SE-1.3).

The model/validation/persistence modules are self-contained (stdlib only) and
never import an existing service, the Ren'Py exporter, or Character Lab. The
``projection`` module is the deliberate, documented SE-1.3 boundary that
imports only the accepted ``services.scene_body`` contract to produce
``SceneBody`` output (which the existing ``build_ordered_ass`` then projects to
``ass/0.2``). No canonical accepted-scene schema is modified.
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
from .projection import (
    DISPLAY_PORTION_MANIFEST_SCHEMA_ID,
    DisplayPortionManifest,
    OverrideRecord,
    PortionRecord,
    Projection,
    ProjectionConfig,
    ProjectionError,
    SceneMembership,
    UnsupportedProjectionError,
    project_scenes,
)
from .portable import (
    PACKAGE_EXTENSION,
    PACKAGE_FORMAT_NAMESPACE,
    PACKAGE_FORMAT_VERSION,
    PACKAGE_MANIFEST_SCHEMA_VERSION,
    ExportReport,
    PackageSummary,
    PortableProjectError,
    PortableProjectExportError,
    PortableProjectImportError,
    PortableProjectValidationError,
    export_project,
    import_project,
    validate_package,
)
from .renpy_integration import (
    RenpyExportResult,
    export_project_to_renpy,
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
    # Projection (SE-1.3)
    "DISPLAY_PORTION_MANIFEST_SCHEMA_ID",
    "SceneMembership",
    "ProjectionConfig",
    "Projection",
    "DisplayPortionManifest",
    "PortionRecord",
    "OverrideRecord",
    "project_scenes",
    "ProjectionError",
    "UnsupportedProjectionError",
    # Portable project container (SE-1.4)
    "PACKAGE_EXTENSION",
    "PACKAGE_FORMAT_NAMESPACE",
    "PACKAGE_FORMAT_VERSION",
    "PACKAGE_MANIFEST_SCHEMA_VERSION",
    "ExportReport",
    "PackageSummary",
    "PortableProjectError",
    "PortableProjectExportError",
    "PortableProjectValidationError",
    "PortableProjectImportError",
    "export_project",
    "validate_package",
    "import_project",
    # Ren'Py export integration (SE-1.5)
    "RenpyExportResult",
    "export_project_to_renpy",
]
