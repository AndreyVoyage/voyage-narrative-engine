#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for Character Canon Read Bridge v0 tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def _write_preset(canon_root: Path, character_id: str, payload: dict[str, Any]) -> None:
    char_dir = canon_root / "AI_CHARACTERS" / character_id / "10_notes"
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def canon_root(tmp_path: Path) -> Path:
    return tmp_path / "character-canon"


def _base_preset(character_id: str, status: str) -> dict[str, Any]:
    return {
        "character": character_id,
        "active_version": "v1",
        "status": status,
        "active_canon": {
            "face": f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png",
            "body": f"AI_CHARACTERS/{character_id}/04_body_sheet/body.png",
        },
        "scene_presets": {
            "portrait": {
                "reference_images": [
                    f"AI_CHARACTERS/{character_id}/03_face_sheet/face.png"
                ]
            }
        },
    }


@pytest.fixture
def pending_kira(canon_root: Path) -> str:
    _write_preset(canon_root, "KIRA", _base_preset("KIRA", "PENDING_APPROVAL"))
    return "KIRA"


def make_approved(canon_root: Path, character_id: str = "APPROVED_ONE") -> str:
    _write_preset(canon_root, character_id, _base_preset(character_id, "APPROVED_AS_CANON"))
    return character_id


def make_bare_approved(canon_root: Path, character_id: str = "BARE_APPROVED_ONE") -> str:
    _write_preset(canon_root, character_id, _base_preset(character_id, "APPROVED"))
    return character_id


def make_status(canon_root: Path, character_id: str, status: str) -> str:
    _write_preset(canon_root, character_id, _base_preset(character_id, status))
    return character_id


def make_pending(canon_root: Path, character_id: str = "PENDING_ONE") -> str:
    _write_preset(canon_root, character_id, _base_preset(character_id, "PENDING_APPROVAL"))
    return character_id