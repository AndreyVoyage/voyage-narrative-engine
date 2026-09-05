#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for scene_draft v0 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from services.scene_draft import SceneDraftStore

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENE_ID = "SC_900"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "SC_900_THOUGHT_VISIBILITY.v2.json"


@pytest.fixture
def scene_id() -> str:
    """The fixture scene's stable id (matches the committed SC_900 body)."""
    return SCENE_ID


@pytest.fixture
def valid_body() -> dict[str, Any]:
    """A committed valid Scenario V2 body (already satisfies the unmodified validator)."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path: Path) -> SceneDraftStore:
    """A fresh SceneDraftStore rooted under the pytest tmp dir."""
    return SceneDraftStore(tmp_path / "scene_draft")
