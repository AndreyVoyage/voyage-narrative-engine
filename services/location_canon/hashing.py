#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic content-hash helpers for Location Canon v0.

Canonicalization mirrors the proven ``services/ass/hashing.py`` (and
``tools/llm_provider.py``) convention exactly::

    json.dumps(payload, ensure_ascii=False, sort_keys=True) -> UTF-8 -> SHA-256

Hash logic is kept local and simple; no provider module is imported.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for a semantic payload."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Compute the LocationCanon ``content_hash`` over the semantic payload.

    ``payload`` is produced by ``LocationCanon.semantic_payload()`` and
    contains only the semantic location identity fields. Envelope/source
    metadata (schema_version, provenance, content_hash) are excluded.
    """
    return sha256_hex(payload)


def compute_source_hash(source_payload: dict[str, Any]) -> str:
    """Compute the provenance ``source_hash`` over the raw source JSON."""
    return sha256_hex(source_payload)