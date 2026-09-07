#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VNE -> Ren'Py adapter package public surface."""

from __future__ import annotations

from .ordered_asset_resolver import (
    OrderedAssetResolutionError,
    resolve_ordered_assets_for_renpy,
)
from .ordered_ass_candidate_lint import (
    CandidateLintResult,
    OrderedCandidateLintError,
    lint_ordered_ass_candidate,
)
from .ordered_ass_canonical_publisher import (
    CANONICAL_ORDERED_ASS_RELATIVE_PATH,
    ORDERED_ASS_GENERATED_OWNERSHIP_MARKER,
    OrderedCanonicalPublishError,
    OrderedCanonicalPublishResult,
    prepare_ordered_candidate_for_canonical_publication,
    publish_ordered_project_candidate,
)
from .ordered_ass_exporter import (
    READING_MODES,
    OrderedExportError,
    entry_label,
    render_ordered_ass,
    scene_end_label,
    scene_start_label,
)
from .ordered_ass_project_exporter import (
    ORDERED_ASS_CANDIDATE_FILENAME,
    OrderedProjectCandidate,
    OrderedProjectExportError,
    build_ordered_project_candidate,
)
from .visual_asset_consumer import resolve_media_asset_for_renpy
from .visual_statement_emitter import emit_visual_statement

__all__ = [
    "resolve_media_asset_for_renpy",
    "emit_visual_statement",
    "render_ordered_ass",
    "resolve_ordered_assets_for_renpy",
    "build_ordered_project_candidate",
    "lint_ordered_ass_candidate",
    "prepare_ordered_candidate_for_canonical_publication",
    "publish_ordered_project_candidate",
    "READING_MODES",
    "OrderedExportError",
    "OrderedAssetResolutionError",
    "OrderedProjectExportError",
    "OrderedCandidateLintError",
    "OrderedCanonicalPublishError",
    "OrderedProjectCandidate",
    "CandidateLintResult",
    "OrderedCanonicalPublishResult",
    "ORDERED_ASS_CANDIDATE_FILENAME",
    "CANONICAL_ORDERED_ASS_RELATIVE_PATH",
    "ORDERED_ASS_GENERATED_OWNERSHIP_MARKER",
    "scene_start_label",
    "scene_end_label",
    "entry_label",
]
