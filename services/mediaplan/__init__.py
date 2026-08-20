#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaPlan v0 -- public API.

Exposes the deeply immutable ``MediaPlan``/``MediaItem`` models plus the
deterministic ``build_mediaplan`` builder. This package performs NO media
generation, NO provider calls, NO prompt composition, and never modifies
upstream ASS / Location Canon / Character Canon bridge / SceneInterpretation
production code.
"""

from __future__ import annotations

from .builder import MEDIAPLAN_SCHEMA_VERSION, build_mediaplan
from .errors import (
    MediaPlanError,
    MediaPlanValidationError,
    UnknownMediaKindError,
)
from .hashing import compute_content_hash
from .model import MediaItem, MediaKind, MediaPlan

__all__ = [
    "build_mediaplan",
    "MEDIAPLAN_SCHEMA_VERSION",
    "MediaPlan",
    "MediaItem",
    "MediaKind",
    "compute_content_hash",
    "MediaPlanError",
    "MediaPlanValidationError",
    "UnknownMediaKindError",
]