#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic hash primitives for the Companion character-import subsystem.

Two families, both stdlib-only:

* semantic-payload hashing (canonical JSON -> UTF-8 -> SHA-256) for snapshot
  ``content_hash`` / provenance ``source_hash``;
* raw-byte SHA-256 for imported reference assets, plus a digest-format check.

Vendoring note: merged near-as-is from
``services/character_canon_bridge/hashing.py`` and
``services/reference_library/hashing.py`` in the VNE repo
(see docs/character_companion/VISUAL_PIPELINE_VENDOR_PROVENANCE_V1.md).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for a semantic payload."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Snapshot ``content_hash`` over the normalized semantic payload."""
    return sha256_hex(payload)


def compute_source_hash(source_payload: dict[str, Any]) -> str:
    """Provenance ``source_hash`` over the raw source JSON."""
    return sha256_hex(source_payload)


def compute_sha256(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of raw ``data`` bytes."""
    return hashlib.sha256(data).hexdigest()


def is_valid_sha256(value: Any) -> bool:
    """Return True if ``value`` is a 64-character lowercase hex digest."""
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))
