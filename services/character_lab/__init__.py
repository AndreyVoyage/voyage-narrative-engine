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

from .runtime_policy import (
    AssemblyItem,
    AssemblyManifest,
    BETA_V1_VARIANT_VERSION,
    BetaV1CurrentPolicy,
    ContextAssembly,
    KIRA_BETA_V1_CURRENT,
    RuntimePolicy,
    build_assembly_hash,
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
    "KIRA_BETA_V1_CURRENT",
    "BETA_V1_VARIANT_VERSION",
    "build_assembly_hash",
    "manifest_to_jsonable",
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
]
