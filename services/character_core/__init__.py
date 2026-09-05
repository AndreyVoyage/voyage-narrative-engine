#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core Release Boundary v1.

A stable, transport-neutral boundary around the existing Character Runtime /
Character Lab implementation (OD-CHAR-PLATFORM-01(A)). This package defines
the contract (:mod:`.contract`) and release metadata / Core-vs-Package-vs-
Runtime-data classification (:mod:`.release`) only -- it contains NO
concrete implementation and MUST NOT import ``services.character_lab`` or
``services.character_runtime``. The first proof-of-contract implementation is
``services.character_lab.service_adapter`` (Character Lab is a CLIENT of this
contract, not the other way around).
"""

from __future__ import annotations

from .contract import (
    KNOWN_CAPABILITIES,
    CapabilitySet,
    ChatTurnResult,
    CharacterDebugService,
    CharacterPackageRef,
    CharacterService,
    CharacterSession,
    CharacterSummary,
    CharacterVariantSummary,
    ContextManifestSummary,
    ManifestItemSummary,
    MemoryEventSummary,
    MemorySummary,
    RequestCaptureSummary,
    RuntimeStateEntrySummary,
    RuntimeStateSummary,
    SceneSummary,
    SessionPurpose,
    SessionPurposeNotImplementedError,
    TurnDebugBundle,
    TurnSummary,
    WorkspaceSummary,
)
from .dimensions import (
    BAND_THRESHOLDS,
    NUMERIC_STATE_MAX,
    NUMERIC_STATE_MIN,
    REQUIRED_BANDS,
    DimensionBandMeaning,
    DimensionDefinition,
    DimensionDefinitionError,
    DimensionSet,
    DimensionValueStatus,
    InterpretedDimensionState,
    StateBand,
    StateDomain,
    band_for_value,
    interpret_state_entry,
    interpret_value,
    key_to_dimension_id,
    render_semantic_state,
    semantic_state_line,
)
from .release import (
    CHARACTER_CORE_RELEASE_BOUNDARY,
    CONTRACT_VERSION,
    CORE_NAME,
    CORE_VERSION,
    RELEASE_FORMAT_VERSION,
    CoreReleaseInfo,
    ReleaseArtifactCategory,
    ReleaseBoundary,
    build_core_release_info,
)

__all__ = [
    "SessionPurpose",
    "SessionPurposeNotImplementedError",
    "KNOWN_CAPABILITIES",
    "CapabilitySet",
    "CharacterPackageRef",
    "CharacterVariantSummary",
    "CharacterSummary",
    "WorkspaceSummary",
    "CharacterSession",
    "ChatTurnResult",
    "RuntimeStateEntrySummary",
    "RuntimeStateSummary",
    "MemoryEventSummary",
    "MemorySummary",
    "SceneSummary",
    "TurnSummary",
    "ManifestItemSummary",
    "ContextManifestSummary",
    "RequestCaptureSummary",
    "TurnDebugBundle",
    "CharacterService",
    "CharacterDebugService",
    "CORE_NAME",
    "CORE_VERSION",
    "CONTRACT_VERSION",
    "RELEASE_FORMAT_VERSION",
    "CoreReleaseInfo",
    "build_core_release_info",
    "ReleaseArtifactCategory",
    "ReleaseBoundary",
    "CHARACTER_CORE_RELEASE_BOUNDARY",
    "StateDomain",
    "StateBand",
    "DimensionValueStatus",
    "NUMERIC_STATE_MIN",
    "NUMERIC_STATE_MAX",
    "BAND_THRESHOLDS",
    "REQUIRED_BANDS",
    "DimensionDefinitionError",
    "DimensionBandMeaning",
    "DimensionDefinition",
    "DimensionSet",
    "InterpretedDimensionState",
    "band_for_value",
    "interpret_value",
    "key_to_dimension_id",
    "interpret_state_entry",
    "semantic_state_line",
    "render_semantic_state",
]
