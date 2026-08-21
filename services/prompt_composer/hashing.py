#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic content-hash helpers for Prompt Composer v0.

Canonicalization mirrors the proven ``services/ass/hashing.py`` convention::

    json.dumps(payload, ensure_ascii=False, sort_keys=True) -> UTF-8 -> SHA-256

Hash logic is kept local and simple; no provider module is imported.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any, *, compact: bool = False) -> str:
    return hashlib.sha256(canonical_json(payload, compact=compact).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    return sha256_hex(payload)