#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic authored-body content hashing for ``services/scene_draft``.

Canonicalization mirrors the proven repo precedent
(``services/ass/hashing.py`` and ``tools/llm_provider.py``):

    json.dumps(payload, ensure_ascii=False, sort_keys=True)

``sort_keys=True`` makes the hash insertion-order independent;
``ensure_ascii=False`` preserves raw Unicode (real scenario content is Russian).

The authored-body hash covers only the authored ``body`` content. Acceptance
lifecycle metadata (the ``acceptance`` link) is never part of this hash, so the
DRAFT -> ACCEPTED transition does not alter it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for an authored body."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_authored_body_hash(body: dict[str, Any]) -> str:
    """Compute the authored-body content hash over the scene ``body`` dict."""
    return sha256_hex(body)
