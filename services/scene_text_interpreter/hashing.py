#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic helpers for the Scene Text Interpreter v0.

Canonicalization mirrors the proven ``services/ass/hashing.py`` /
``services/scene_interpretation/hashing.py`` convention::

    json.dumps(payload, ensure_ascii=False, sort_keys=True) -> UTF-8 -> SHA-256

Plus text normalization used for the ``source_text_hash`` and for grounding
substring checks. No provider module is imported; stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_WS_RUN = re.compile(r"\s+")


def canonical_json(payload: Any) -> str:
    """Return the canonical JSON string for a semantic payload."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonical JSON of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Compute a plan ``content_hash`` over its semantic payload."""
    return sha256_hex(payload)


def canonical_source(text: str) -> str:
    """Return the stable canonical form of submitted source text.

    NFC-normalized, every run of whitespace (including newlines) collapsed to a
    single space, leading/trailing whitespace stripped. Case is preserved so
    the hash is faithful to the author's text.
    """
    if not isinstance(text, str):
        raise TypeError("source text must be a string")
    return _WS_RUN.sub(" ", unicodedata.normalize("NFC", text)).strip()


def source_text_hash(text: str) -> str:
    """SHA-256 (hex) of the canonical source form."""
    return hashlib.sha256(canonical_source(text).encode("utf-8")).hexdigest()


def match_key(text: str) -> str:
    """Return the case-insensitive matching key for grounding/alias checks.

    ``casefold`` of the canonical source form. A span S is considered grounded
    in source T iff ``match_key(S) in match_key(T)``.
    """
    return canonical_source(text).casefold()
