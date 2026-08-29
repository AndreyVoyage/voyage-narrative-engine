#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic SHA-256 primitives for the Reference Library manifest contract.

Stdlib-only. Hashes are lowercase hex digests of the committed asset bytes;
this package never decodes or validates image pixels.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def compute_sha256(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def is_valid_sha256(value: Any) -> bool:
    """Return True if ``value`` is a 64-character lowercase hex digest."""
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))
