#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- public API.

A thin, UI-agnostic application/facade layer over the read-only Character
Canon bridge plus a local, offline session model. No UI components, no
desktop-wrapper choice, no new Character Canon parsing, no provider/network
call anywhere in this package.
"""

from __future__ import annotations

from .config import CharacterLabApplicationConfig
from .errors import (
    AUTHORING_ALREADY_EXISTS,
    AUTHORING_INVALID_LIFECYCLE_TRANSITION,
    AUTHORING_NOT_EDITABLE,
    AUTHORING_NOT_FOUND,
    AUTHORING_PERSISTENCE_FAILED,
    AUTHORING_STALE_REVISION,
    AUTHORING_STALE_SNAPSHOT,
    AUTHORING_UNAVAILABLE,
    AUTHORING_VALIDATION_FAILED,
    CANON_UNAVAILABLE,
    CRP_VALIDATION_FAILED,
    DERIVATION_SOURCE_NOT_APPROVED,
    IMMUTABLE_PERSISTENCE_FAILED,
    IMPORT_REQUIRES_AUTHORING_COMPLETION,
    IMPORT_SOURCE_UNAVAILABLE,
    INTERNAL_ERROR,
    INVALID_INPUT,
    NOT_FOUND,
    OK,
    PUBLICATION_NOT_APPROVED,
    PUBLICATION_PACKAGE_COLLISION,
    PUBLICATION_SOURCE_CORRUPT,
    PUBLICATION_STALE_REVISION,
    PUBLICATION_STALE_SNAPSHOT,
    PUBLICATION_STORAGE_FAILED,
    PUBLICATION_VALIDATION_FAILED,
    CharacterLabApplicationError,
)
from .results import (
    CharacterAuthoringResult,
    CharacterPublicationResult,
    CharacterSessionPin,
    CharacterInspectorDetail,
    CharacterSummary,
    CharacterVersionSummary,
    LabSession,
    Message,
)
from .service import CharacterLabApplicationService

# Re-exported CRP application-facing result types -- the same objects
# services.crp_authoring.application_adapter already returns. Not duplicated
# DTOs; this is the one seam through which a future UI layer can reference
# them without importing services.crp_authoring directly.
from services.crp_authoring.application_adapter import (
    AcceptedReconstructionResult,
    R3RelevanceResult,
    ReconstructionPlan,
)

__all__ = [
    "CharacterLabApplicationService",
    "CharacterLabApplicationConfig",
    "CharacterLabApplicationError",
    # Results / DTOs
    "CharacterSummary",
    "CharacterVersionSummary",
    "CharacterInspectorDetail",
    "Message",
    "LabSession",
    "CharacterAuthoringResult",
    "CharacterPublicationResult",
    "CharacterSessionPin",
    # CRP application-facing result types (re-exported, not duplicated)
    "R3RelevanceResult",
    "ReconstructionPlan",
    "AcceptedReconstructionResult",
    # Error categories
    "OK",
    "NOT_FOUND",
    "INVALID_INPUT",
    "CANON_UNAVAILABLE",
    "INTERNAL_ERROR",
    "CRP_VALIDATION_FAILED",
    "AUTHORING_UNAVAILABLE",
    "AUTHORING_ALREADY_EXISTS",
    "AUTHORING_INVALID_LIFECYCLE_TRANSITION",
    "AUTHORING_NOT_FOUND",
    "AUTHORING_NOT_EDITABLE",
    "AUTHORING_STALE_REVISION",
    "AUTHORING_STALE_SNAPSHOT",
    "AUTHORING_VALIDATION_FAILED",
    "AUTHORING_PERSISTENCE_FAILED",
    "IMMUTABLE_PERSISTENCE_FAILED",
    "IMPORT_SOURCE_UNAVAILABLE",
    "IMPORT_REQUIRES_AUTHORING_COMPLETION",
    "DERIVATION_SOURCE_NOT_APPROVED",
    "PUBLICATION_NOT_APPROVED",
    "PUBLICATION_STALE_REVISION",
    "PUBLICATION_STALE_SNAPSHOT",
    "PUBLICATION_SOURCE_CORRUPT",
    "PUBLICATION_VALIDATION_FAILED",
    "PUBLICATION_PACKAGE_COLLISION",
    "PUBLICATION_STORAGE_FAILED",
]
