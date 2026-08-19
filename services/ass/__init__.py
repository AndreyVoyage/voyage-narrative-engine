#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accepted Scene Snapshot (ASS v0) -- public API.

Exposes the immutable ASS data model plus the scenario JSON v2 importer.
This package is stdlib-only, has no provider/network calls, and never
touches personas, scenarios (write-side), visual Canon, the exporter,
Ren'Py, or Voyage.

``services/__init__.py`` is intentionally absent: ``services`` resolves as
an implicit PEP 420 namespace package (matching the existing
``persona_authoring``/``persona_gateway`` convention).
"""

from __future__ import annotations

from .errors import ASSError, ASSNormalizationError, ASSSourceError
from .hashing import compute_content_hash, compute_source_hash
from .importer import (
    ASS_SCHEMA_VERSION,
    SOURCE_KIND_IMPORT,
    import_scene,
)
from .model import (
    ASS,
    AcceptedSceneSnapshot,
    Beat,
    LocationStateOverride,
    Participant,
    Provenance,
)

__all__ = [
    # Importer
    "import_scene",
    "ASS_SCHEMA_VERSION",
    "SOURCE_KIND_IMPORT",
    # Models
    "AcceptedSceneSnapshot",
    "ASS",
    "Participant",
    "Beat",
    "LocationStateOverride",
    "Provenance",
    # Hashing
    "compute_content_hash",
    "compute_source_hash",
    # Errors
    "ASSError",
    "ASSSourceError",
    "ASSNormalizationError",
]