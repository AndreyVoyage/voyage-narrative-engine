#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for Workspace / Domain Foundation v0 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo_root() -> Path:
    """The real committed repo root (for the already-committed Location Canon
    fixtures ``scenarios/locations/gym.json`` / ``yoga_hall.json``)."""
    return REPO_ROOT


def write_character_preset(canon_root: Path, character_id: str, status: str) -> None:
    """Write a synthetic Character Canon preset under a tmp canon root.

    Mirrors ``tests/character_canon_bridge/conftest.py``'s fixture shape.
    Never touches the real (external) NCC repository.
    """
    char_dir = canon_root / "AI_CHARACTERS" / character_id / "10_notes"
    char_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "character": character_id,
        "active_version": "v1",
        "status": status,
        "active_canon": {
            "face": f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png",
        },
    }
    (char_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def write_asset_registry(registry_path: Path, records: list[dict[str, Any]]) -> None:
    """Write a synthetic Visual Asset Registry file (``tools/visual_asset_registry.py``
    shape) under a tmp path. Never touches the real committed registry."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({"assets": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
