#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor Application Service v1 -- public API.

A thin, UI-agnostic application/facade layer over the proven scene-editor domain
services. Exposes one primary service plus small immutable DTO/result types and
a bounded error model. No UI components, no desktop-wrapper choice, no new
domain model, no parallel persistence.
"""

from __future__ import annotations

from .config import EditorApplicationConfig
from .errors import (
    ACCEPTED_IMMUTABLE,
    ALREADY_EXISTS,
    INTERNAL_ERROR,
    INVALID_INPUT,
    IO_FAILURE,
    NOT_FOUND,
    OK,
    PARTIAL_PROJECT_STATE,
    VALIDATION_FAILED,
    VERSION_CONFLICT_OR_INVALID_VERSION,
    EditorApplicationError,
)
from .results import (
    EditorAcceptanceState,
    EditorCharacterSummary,
    EditorDiagnostic,
    EditorLocationSummary,
    EditorOperationResult,
    EditorSceneSummary,
    EditorSceneWorkspace,
)
from .service import EditorApplicationService

__all__ = [
    "EditorApplicationService",
    "EditorApplicationConfig",
    "EditorApplicationError",
    # Results / DTOs
    "EditorSceneSummary",
    "EditorCharacterSummary",
    "EditorLocationSummary",
    "EditorSceneWorkspace",
    "EditorAcceptanceState",
    "EditorDiagnostic",
    "EditorOperationResult",
    # Error categories
    "OK",
    "NOT_FOUND",
    "INVALID_INPUT",
    "VALIDATION_FAILED",
    "ACCEPTED_IMMUTABLE",
    "ALREADY_EXISTS",
    "VERSION_CONFLICT_OR_INVALID_VERSION",
    "PARTIAL_PROJECT_STATE",
    "IO_FAILURE",
    "INTERNAL_ERROR",
]
