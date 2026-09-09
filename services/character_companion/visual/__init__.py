#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline, deterministic Companion visual-preparation chain (Slice B).

Pipeline (no provider, no network, no Character Canon)::

    active CharacterLocalSnapshot
      + CompanionScene fields
      + bounded linear conversation (<= 8 messages)
      + optional explicit description (<= 4000 chars)
        -> build_visual_context()        -> VisualContext
        -> build_reference_bundle()      -> ReferenceBundle   (bytes from the
                                            snapshot dir only, fail-closed)
        -> build_visual_prompt()         -> VisualPromptPackage

    Output stops at VisualPromptPackage + ReferenceBundle. A real image-model
    call (Slice C) consumes them and is out of scope for this package.
"""

from __future__ import annotations

from .context import (
    MAX_DESCRIPTION_CHARS,
    REQUEST_KIND_CONTEXT,
    REQUEST_KIND_CUSTOM,
    VISUAL_CONTEXT_SCHEMA_VERSION,
    VISUAL_RECENT_MESSAGE_LIMIT,
    VisualContext,
    VisualLocation,
    VisualMessage,
    VisualScene,
    build_visual_context,
)
from .errors import (
    ReferenceBundleError,
    ReferenceSelectionError,
    VisualContextError,
    VisualPipelineError,
    VisualPromptError,
)
from .hashing import compute_sha256, content_hash, is_valid_sha256, sha256_hex
from .physical import render_physical_block
from .prompt import (
    VISUAL_PROMPT_SCHEMA_VERSION,
    VisualPromptPackage,
    build_visual_prompt,
)
from .reference_bundle import build_reference_bundle, validate_reference_bundle_integrity
from .reference_model import (
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ReferenceBundle,
    ReferenceEntry,
)
from .reference_selection import (
    MAX_AUTO_REFS,
    MIN_AUTO_REFS,
    select_reference_asset_ids,
)

__all__ = [
    # context
    "VISUAL_CONTEXT_SCHEMA_VERSION",
    "VISUAL_RECENT_MESSAGE_LIMIT",
    "MAX_DESCRIPTION_CHARS",
    "REQUEST_KIND_CUSTOM",
    "REQUEST_KIND_CONTEXT",
    "VisualContext",
    "VisualScene",
    "VisualLocation",
    "VisualMessage",
    "build_visual_context",
    # reference selection + bundle
    "MIN_AUTO_REFS",
    "MAX_AUTO_REFS",
    "select_reference_asset_ids",
    "REFERENCE_BUNDLE_SCHEMA_VERSION",
    "ReferenceEntry",
    "ReferenceBundle",
    "build_reference_bundle",
    "validate_reference_bundle_integrity",
    # physical + prompt
    "render_physical_block",
    "VISUAL_PROMPT_SCHEMA_VERSION",
    "VisualPromptPackage",
    "build_visual_prompt",
    # hashing
    "content_hash",
    "sha256_hex",
    "compute_sha256",
    "is_valid_sha256",
    # errors
    "VisualPipelineError",
    "VisualContextError",
    "ReferenceSelectionError",
    "ReferenceBundleError",
    "VisualPromptError",
]
