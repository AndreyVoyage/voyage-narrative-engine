#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Canon Read Bridge v0 -- public API.

Exposes the deeply immutable ``CharacterCanonSnapshot`` model plus the
read-only, deterministic ``read_character_canon`` bridge. This package never
writes to Character Canon, never touches Ren'Py/providers/LLM, and never
modifies ASS or Location Canon production code.
"""

from __future__ import annotations

from .errors import (
    AmbiguousCharacterError,
    CanonFormatError,
    CanonRootMissingError,
    CanonStatusUnknownError,
    CharacterCanonBridgeError,
    CharacterNotFoundError,
    ProductionNotAllowedError,
    ReferencePathSafetyError,
    UnsupportedUsageContextError,
)
from .hashing import compute_content_hash
from .model import (
    CanonReference,
    CharacterCanonSnapshot,
    Provenance,
)
from .reader import (
    SNAPSHOT_SCHEMA_VERSION,
    read_character_canon,
)

__all__ = [
    "read_character_canon",
    "SNAPSHOT_SCHEMA_VERSION",
    "CharacterCanonSnapshot",
    "CanonReference",
    "Provenance",
    "compute_content_hash",
    "CharacterCanonBridgeError",
    "CanonRootMissingError",
    "CharacterNotFoundError",
    "AmbiguousCharacterError",
    "CanonFormatError",
    "CanonStatusUnknownError",
    "ReferencePathSafetyError",
    "ProductionNotAllowedError",
    "UnsupportedUsageContextError",
]