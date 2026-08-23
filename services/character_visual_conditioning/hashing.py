#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic content-hash helpers for Character Visual Reference
Conditioning v0 (C3).

Canonicalization mirrors the proven ASS / Scene Interpretation /
Generated Image Review convention::

    json.dumps(payload, ensure_ascii=False, sort_keys=True) -> UTF-8 -> SHA-256

No provider module is imported. Absolute machine paths never enter a semantic
hash; they are operational-only.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for a semantic payload."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Compute the artifact ``content_hash`` over the semantic payload."""
    return sha256_hex(payload)


def validate_hex_sha256(value: str) -> str:
    """Return the validated, stripped lowercase SHA-256 hex digest.

    Fails closed on anything that is not exactly 64 lowercase hex characters.
    """
    if not isinstance(value, str):
        raise ValueError("sha256 must be a string")
    digest = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError(f"invalid sha256 hex digest: {value!r}")
    return digest