#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused adapter-boundary tests for the VNE -> Ren'Py visual asset consumer.

Proves the first real production asset (KIRA) can reach the VNE -> Ren'Py
adapter as a Ren'Py-consumable image name, that resolution is keyed on
``asset_id`` (never ``media_item_id``), that unknown/duplicate/missing/malformed
inputs fail closed, and that no persistence side effects occur.

No provider call, no media generation, no scene write, no Registry write, no
PNG write, no ``.rpy`` generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.production_media_asset_binding import (  # noqa: E402
    AssetIdAmbiguousError,
    AssetNotFoundError,
    BindingValidationError,
    ResolvedAsset,
)
from tools.vne_to_renpy.visual_asset_consumer import (  # noqa: E402
    resolve_media_asset_for_renpy,
)

KIRA_MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"
KIRA_ASSET_ID = "kira_yoga_hall_pilot_image_01"
KIRA_RELATIVE_PATH = (
    "novel/game/images/story/characters/kira/kira_yoga_hall_pilot_image_01.png"
)
KIRA_RENPY_NAME = "kira_yoga_hall_pilot_image_01"

_KIRA_REGISTRY_PATH = (
    _REPO_ROOT / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
)


def _write_registry(tmp_path: Path, records: list[dict]) -> Path:
    registry = tmp_path / "ASSET_REGISTRY.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({"assets": records}, indent=2), encoding="utf-8")
    return registry


def _record(asset_id: str, relative_path: str) -> dict:
    return {"asset_id": asset_id, "relative_path": relative_path}


# ---------------------------------------------------------------------------
# Real KIRA first production consumption
# ---------------------------------------------------------------------------


def test_kira_real_registry_resolves_to_renpy_image_name():
    result = resolve_media_asset_for_renpy(
        media_item_id=KIRA_MEDIA_ITEM_ID,
        asset_id=KIRA_ASSET_ID,
        registry_path=_KIRA_REGISTRY_PATH,
    )
    assert isinstance(result, ResolvedAsset)
    assert result.asset_id == KIRA_ASSET_ID
    assert result.relative_path == KIRA_RELATIVE_PATH
    assert result.renpy_image_name == KIRA_RENPY_NAME


def test_public_export_surface():
    from tools.vne_to_renpy import resolve_media_asset_for_renpy as exported

    assert exported is resolve_media_asset_for_renpy


# ---------------------------------------------------------------------------
# Unequal media_item_id / asset_id proof
# ---------------------------------------------------------------------------


def test_unequal_ids_resolve_keyed_on_asset_id(tmp_path):
    registry_path = _write_registry(
        tmp_path,
        [_record("production_asset_abc", "novel/game/images/story/cg/abc.png")],
    )
    result = resolve_media_asset_for_renpy(
        media_item_id="scene_media_need_001",
        asset_id="production_asset_abc",
        registry_path=registry_path,
    )
    assert result.asset_id == "production_asset_abc"
    assert result.relative_path == "novel/game/images/story/cg/abc.png"
    assert result.renpy_image_name == "abc"


# ---------------------------------------------------------------------------
# Fail-closed adapter boundary cases
# ---------------------------------------------------------------------------


def test_unknown_asset_id_fails_closed(tmp_path):
    registry_path = _write_registry(
        tmp_path,
        [_record("production_asset_abc", "novel/game/images/story/cg/abc.png")],
    )
    with pytest.raises(AssetNotFoundError):
        resolve_media_asset_for_renpy(
            media_item_id="scene_media_need_001",
            asset_id="asset_missing",
            registry_path=registry_path,
        )


def test_duplicate_asset_id_fails_closed(tmp_path):
    registry_path = _write_registry(
        tmp_path,
        [
            _record("asset_dup", "novel/game/images/story/cg/a.png"),
            _record("asset_dup", "novel/game/images/story/cg/b.png"),
        ],
    )
    with pytest.raises(AssetIdAmbiguousError):
        resolve_media_asset_for_renpy(
            media_item_id="scene_media_need_001",
            asset_id="asset_dup",
            registry_path=registry_path,
        )


def test_missing_registry_path_fails_closed(tmp_path):
    missing = tmp_path / "does_not_exist" / "ASSET_REGISTRY.json"
    with pytest.raises(AssetNotFoundError):
        resolve_media_asset_for_renpy(
            media_item_id="scene_media_need_001",
            asset_id="production_asset_abc",
            registry_path=missing,
        )


def test_malformed_registry_raises(tmp_path):
    bad = tmp_path / "ASSET_REGISTRY.json"
    bad.write_text(json.dumps({"not_assets": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_media_asset_for_renpy(
            media_item_id="scene_media_need_001",
            asset_id="production_asset_abc",
            registry_path=bad,
        )


def test_invalid_binding_identifiers_raise(tmp_path):
    registry_path = _write_registry(
        tmp_path,
        [_record("production_asset_abc", "novel/game/images/story/cg/abc.png")],
    )
    with pytest.raises(BindingValidationError):
        resolve_media_asset_for_renpy(
            media_item_id="",
            asset_id="production_asset_abc",
            registry_path=registry_path,
        )
    with pytest.raises(BindingValidationError):
        resolve_media_asset_for_renpy(
            media_item_id="scene_media_need_001",
            asset_id="Invalid-Asset!",
            registry_path=registry_path,
        )


# ---------------------------------------------------------------------------
# No persistence side effects
# ---------------------------------------------------------------------------


def test_no_persistence_side_effects(tmp_path):
    registry_path = _write_registry(
        tmp_path,
        [_record("production_asset_abc", "novel/game/images/story/cg/abc.png")],
    )
    before_bytes = registry_path.read_bytes()
    before_tree = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    resolve_media_asset_for_renpy(
        media_item_id="scene_media_need_001",
        asset_id="production_asset_abc",
        registry_path=registry_path,
    )

    after_tree = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert registry_path.read_bytes() == before_bytes
    assert after_tree == before_tree
