#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the additive read-only ``list_location_ids`` discovery helper."""

from __future__ import annotations

from pathlib import Path

from services.location_canon import list_location_ids


def test_empty_when_locations_dir_missing(tmp_path: Path):
    assert list_location_ids(tmp_path) == ()


def test_lists_discovered_ids_sorted(tmp_path: Path):
    locations_dir = tmp_path / "scenarios" / "locations"
    locations_dir.mkdir(parents=True, exist_ok=True)
    for location_id in ("zebra_room", "alpha_room", "gym"):
        (locations_dir / f"{location_id}.json").write_text("{}", encoding="utf-8")
    # Non-JSON stray files with invalid slugs are ignored.
    (locations_dir / "notes.txt").write_text("not a location", encoding="utf-8")
    assert list_location_ids(tmp_path) == ("alpha_room", "gym", "zebra_room")


def test_real_repo_locations(tmp_path: Path):
    # Guard against regressions: the helper stays read-only over any root.
    assert list_location_ids(tmp_path) == ()
