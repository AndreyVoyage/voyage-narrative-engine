#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures/helpers for Reference Library v0 (SVA-RL1) tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDED_MANIFEST = (
    REPO_ROOT / "authoring" / "reference_library" / "REFERENCE_LIBRARY_MANIFEST.json"
)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_record(**overrides: Any) -> dict[str, Any]:
    """Return a valid reference record dict; overrides win."""
    base: dict[str, Any] = {
        "asset_id": "kira_neutral",
        "character_id": "TEST_NEW_CHARACTER",
        "relative_path": (
            "authoring/reference_library/assets/characters/"
            "TEST_NEW_CHARACTER/kira_neutral.png"
        ),
        "filename": "kira_neutral.png",
        "sha256": sha256_of(b"kira_neutral"),
        "file_type": "PNG",
    }
    base.update(overrides)
    return base
