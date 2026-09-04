#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab V1 -- thin developer/test/observability service layer.

Slice 1 foundation. Composes the existing Character Runtime, acceptance gate,
RuntimeMemoryBackend, and an injected provider callable. Adds the repo-controlled
accepted-source loader, the RuntimePolicy (Variant) abstraction, the runtime
service boundary, and append-only turn capture.

No provider, no network, no acceptance mutation, no accepted-package writer path.
"""

from __future__ import annotations

from . import provenance
from .app import (
    CHARACTER_LAB_DATA_ROOT_ENV,
    CharacterLabApp,
    resolve_data_root,
)
from .scene import (
    Scene,
    SceneError,
    new_scene,
    render_scene_block,
    scene_from_jsonable,
    scene_hash,
    scene_to_jsonable,
)
from .workspace import (
    NORMAL_ID,
    WORKSPACE_KIND_CLEAN_TEST,
    WORKSPACE_KIND_NORMAL,
    Workspace,
    WorkspaceError,
    WorkspaceManager,
)
from .grounding import (
    GROUNDING_HEADER,
    grounding_char_length,
    render_accepted_grounding,
)
from .runtime_policy import (
    AssemblyItem,
    AssemblyManifest,
    BETA_V1_VARIANT_VERSION,
    BetaV1CurrentPolicy,
    ContextAssembly,
    EXPERIMENTAL_VARIANT_ID,
    GROUNDED_V2_VARIANT_VERSION,
    GroundedV2Policy,
    KIRA_BETA_V1_CURRENT,
    KIRA_GROUNDED_V2,
    RuntimePolicy,
    SUPPORTED_VARIANT_IDS,
    UnknownVariantError,
    build_assembly_hash,
    build_policy,
    manifest_to_jsonable,
)
from .runtime_service import (
    LoadedState,
    RuntimeService,
    TurnResult,
    build_provider_attribution,
    extract_response_metadata,
)
from .source_loader import (
    DEFAULT_ACCEPTANCE_ROOT,
    SOURCE_CANDIDATE_FILENAME,
    build_repo_source_loader,
)
from .turn_capture import (
    TurnCapture,
    compute_request_hash,
    verify_segment_delivered,
)

__all__ = [
    "AssemblyItem",
    "AssemblyManifest",
    "ContextAssembly",
    "RuntimePolicy",
    "BetaV1CurrentPolicy",
    "GroundedV2Policy",
    "KIRA_BETA_V1_CURRENT",
    "KIRA_GROUNDED_V2",
    "BETA_V1_VARIANT_VERSION",
    "GROUNDED_V2_VARIANT_VERSION",
    "EXPERIMENTAL_VARIANT_ID",
    "SUPPORTED_VARIANT_IDS",
    "UnknownVariantError",
    "build_policy",
    "build_assembly_hash",
    "manifest_to_jsonable",
    "GROUNDING_HEADER",
    "render_accepted_grounding",
    "grounding_char_length",
    "LoadedState",
    "TurnResult",
    "RuntimeService",
    "build_provider_attribution",
    "extract_response_metadata",
    "build_repo_source_loader",
    "SOURCE_CANDIDATE_FILENAME",
    "DEFAULT_ACCEPTANCE_ROOT",
    "TurnCapture",
    "compute_request_hash",
    "verify_segment_delivered",
    "CharacterLabApp",
    "CHARACTER_LAB_DATA_ROOT_ENV",
    "resolve_data_root",
    "provenance",
    "Scene",
    "SceneError",
    "new_scene",
    "render_scene_block",
    "scene_from_jsonable",
    "scene_hash",
    "scene_to_jsonable",
    "NORMAL_ID",
    "WORKSPACE_KIND_CLEAN_TEST",
    "WORKSPACE_KIND_NORMAL",
    "Workspace",
    "WorkspaceError",
    "WorkspaceManager",
]
