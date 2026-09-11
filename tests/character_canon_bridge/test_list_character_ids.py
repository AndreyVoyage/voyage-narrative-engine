#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the additive read-only ``list_character_ids`` discovery helper."""

from __future__ import annotations

from pathlib import Path

from services.character_canon_bridge import list_character_ids


def test_empty_when_root_missing(tmp_path: Path):
    assert list_character_ids(tmp_path / "does-not-exist") == ()


def test_empty_when_no_ai_characters_dir(tmp_path: Path):
    assert list_character_ids(tmp_path) == ()


def test_lists_discovered_ids_sorted(tmp_path: Path):
    for character_id in ("ZED", "KIRA", "ALPHA"):
        char_dir = tmp_path / "AI_CHARACTERS" / character_id / "10_notes"
        char_dir.mkdir(parents=True, exist_ok=True)
        (char_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
            "{}", encoding="utf-8"
        )
    assert list_character_ids(tmp_path) == ("ALPHA", "KIRA", "ZED")


def test_ignores_missing_preset_file(tmp_path: Path):
    # A directory with no matching preset is skipped.
    (tmp_path / "AI_CHARACTERS" / "EMPTY_ONE").mkdir(parents=True, exist_ok=True)
    assert list_character_ids(tmp_path) == ()
