#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic content-hash helpers for Accepted Scene Snapshot (ASS v0).

Canonicalization mirrors the proven ``tools/llm_provider.py``
``_canonical_payload`` precedent exactly::

    json.dumps(payload, ensure_ascii=False, sort_keys=True)

no explicit ``indent``, default separators. ``sort_keys=True`` makes the
hash insertion-order independent; ``ensure_ascii=False`` preserves raw
Unicode (the real scenario data is entirely Russian). NOTE: per the Phase
A1 preflight's REQUIRED_MINOR precision note, this uses the default
separator form rather than the final contract's ``separators=(",", ":")``
variant, for maximum consistency with the one repo file that already does
exactly this canonicalize-then-hash job.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for a semantic payload.

    Deterministic given identical input semantic content: keys are sorted
    and Unicode is preserved. Used for both ``content_hash`` and
    ``provenance.source_hash``.
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Compute the ASS ``content_hash`` over the semantic payload.

    ``payload`` is produced by ``ASS.semantic_payload()`` and contains only
    the hashed fields (identity + participants + ordered beats + rating +
    optional overrides). The envelope fields are intentionally excluded.
    """
    return sha256_hex(payload)


def compute_source_hash(source_payload: dict[str, Any]) -> str:
    """Compute the provenance ``source_hash`` over the raw source JSON."""
    return sha256_hex(source_payload)