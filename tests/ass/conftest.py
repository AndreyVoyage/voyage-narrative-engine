#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for ASS v0 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "ass"
SCENARIOS_DIR = REPO_ROOT / "scenarios"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def synthetic_sc029_source() -> dict[str, Any]:
    """The committed synthetic SC_029 fixture (Canon-free pilot)."""
    return _load_json(FIXTURES_DIR / "SC_029_SYNTHETIC.v2.json")


@pytest.fixture
def sc017_source() -> dict[str, Any]:
    """Read-only reference to the real committed SC_017 v2 scene."""
    return _load_json(SCENARIOS_DIR / "SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json")


@pytest.fixture
def synthetic_source_bytes(synthetic_sc029_source: dict[str, Any]) -> bytes:
    """The synthetic source as canonical bytes, for hashing assertions."""
    import json as _json

    return _json.dumps(
        synthetic_sc029_source, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")