#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic hashing for the visual chain.

Reuses the already-vendored primitives from
``services.character_companion.character_import.hashing`` (canonical JSON ->
UTF-8 -> SHA-256; raw-byte SHA-256; digest-format check). No new hashing
convention is introduced here.
"""

from __future__ import annotations

from typing import Any

from ..character_import.hashing import (  # noqa: F401 -- re-exported
    canonical_json,
    compute_sha256,
    is_valid_sha256,
    sha256_hex,
)


def content_hash(semantic_payload: Any) -> str:
    """Content hash of a JSON-compatible semantic payload (sorted keys)."""
    return sha256_hex(semantic_payload)
