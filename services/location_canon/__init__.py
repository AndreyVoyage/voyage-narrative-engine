#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Location Canon v0 -- public API.

Exposes the deeply immutable ``LocationCanon`` model plus the deterministic
stdlib-only loader. This package never touches Ren'Py, providers, the LLM,
Character Canon, ASS production code, or any runtime persistence.
"""

from __future__ import annotations

from .errors import (
    LocationCanonError,
    LocationCanonSourceError,
    LocationCanonValidationError,
    LocationNotFoundError,
)
from .hashing import compute_content_hash
from .loader import (
    LOCATION_CANON_SCHEMA_VERSION,
    default_locations_dir,
    load_location,
)
from .model import (
    FixedFeature,
    LocationCanon,
    Provenance,
)

__all__ = [
    "load_location",
    "default_locations_dir",
    "LOCATION_CANON_SCHEMA_VERSION",
    "compute_content_hash",
    "LocationCanon",
    "FixedFeature",
    "Provenance",
    "LocationCanonError",
    "LocationCanonSourceError",
    "LocationCanonValidationError",
    "LocationNotFoundError",
]