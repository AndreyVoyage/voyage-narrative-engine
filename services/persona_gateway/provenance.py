#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic provenance construction for the N7 Persona Data Gateway
(P1a-S1 partial runtime).

Provenance is built exclusively from data already in hand (raw module
bytes + manifest-declared version) -- it never touches the filesystem
itself and never returns an absolute local filesystem path or any source
content in error paths.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .models import Provenance


def build_module_provenance(
    *,
    character_id: str,
    module_id: str,
    raw_bytes: bytes,
    version: Optional[str],
) -> Provenance:
    """Build the provenance record for one successfully read module.

    - ``content_hash``: lowercase hex SHA-256 digest of the exact raw
      module bytes (not the decoded text, not the parsed JSON).
    - ``source``: stable logical identifier ``"personas/<character_id>/<module_id>"``
      -- never an absolute machine path.
    - ``schema``: always ``None`` for modular Kira files (P1a-S1 policy:
      JSON_PARSE_ONLY_WITH_STRUCTURAL_MANIFEST_VALIDATION).
    - ``read_only``: always ``True``.
    """
    digest = hashlib.sha256(raw_bytes).hexdigest()
    source = f"personas/{character_id}/{module_id}"
    return Provenance(
        source=source,
        schema=None,
        content_hash=digest,
        version=version,
        read_only=True,
    )
