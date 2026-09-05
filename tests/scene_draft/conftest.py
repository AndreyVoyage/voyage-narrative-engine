#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for scene_draft v0 tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from services.scene_draft import SceneDraftStore

SCENE_ID = "SC_900"


def make_body(scene_id: str = SCENE_ID, **overrides) -> dict[str, Any]:
    """A valid complete SceneBody (scene_body/1.0) as a plain dict."""
    body: dict[str, Any] = {
        "authoring_schema_version": "scene_body/1.0",
        "scene_id": scene_id,
        "scene_title": "Test scene",
        "location_id": "yoga_hall",
        "participants": [{"character_id": "KIRA", "role": "protagonist", "present": True}],
        "content_rating": "PG",
        "character_state_overrides": None,
        "location_state_overrides": None,
        "entries": [
            {
                "entry_id": "e1",
                "kind": "TEXT",
                "presentation": "NARRATIVE",
                "text": "Kira enters the yoga hall.",
                "character_id": None,
                "thought_visibility": None,
            },
            {
                "entry_id": "c1",
                "kind": "CHOICE",
                "prompt": "What next?",
                "options": [
                    {
                        "option_id": "o1",
                        "display_text": "Continue",
                        "target": {"target_kind": "SCENE", "target_id": "SC_901"},
                    }
                ],
            },
            {
                "entry_id": "v1",
                "kind": "VISUAL_CHANGE",
                "operation": "SET",
                "asset_id": "kira_yoga_hall",
                "transition": "fade",
            },
        ],
    }
    body.update(overrides)
    return body


@pytest.fixture
def scene_id() -> str:
    return SCENE_ID


@pytest.fixture
def valid_body() -> dict[str, Any]:
    return make_body()


@pytest.fixture
def store(tmp_path: Path) -> SceneDraftStore:
    return SceneDraftStore(tmp_path / "scene_draft")
