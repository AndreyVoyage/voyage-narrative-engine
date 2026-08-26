#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for Production Media Asset Binding v0 + runtime resolver.

Covers the immutable binding, deterministic content hash, unequal
media_item_id/asset_id resolution, fail-closed Registry selection, generic
Ren'Py image-name transformation, and the real KIRA registered asset as a
fixture (with no KIRA-specific branching allowed anywhere).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.production_media_asset_binding import (  # noqa: E402
    AssetIdAmbiguousError,
    AssetNotFoundError,
    AssetResolutionError,
    BindingValidationError,
    ProductionMediaAssetBinding,
    ResolvedAsset,
    build_production_media_asset_binding,
    renpy_image_name_from_relative_path,
    resolve_bound_asset,
)

KIRA_RELATIVE_PATH = "novel/game/images/story/characters/kira/kira_yoga_hall_pilot_image_01.png"
KIRA_RENPY_NAME = "story characters kira kira_yoga_hall_pilot_image_01"


def _record(asset_id: str, relative_path: str) -> dict:
    return {"asset_id": asset_id, "relative_path": relative_path}


# ---------------------------------------------------------------------------
# Binding construction + determinism
# ---------------------------------------------------------------------------


def test_binding_is_frozen():
    b = build_production_media_asset_binding(
        media_item_id="scene_media_need_001", asset_id="production_asset_abc"
    )
    with pytest.raises(AttributeError):
        b.media_item_id = "x"  # type: ignore[misc]


def test_binding_to_dict_has_no_path_authority():
    b = build_production_media_asset_binding("m1", "asset_a")
    d = b.to_dict()
    assert set(d.keys()) == {"schema_version", "media_item_id", "asset_id", "content_hash"}
    assert not any("path" in k for k in d)


def test_content_hash_deterministic():
    a = build_production_media_asset_binding("m1", "asset_a")
    b = build_production_media_asset_binding("m1", "asset_a")
    assert a.content_hash == b.content_hash


def test_different_media_item_id_changes_hash():
    a = build_production_media_asset_binding("m1", "asset_a")
    b = build_production_media_asset_binding("m2", "asset_a")
    assert a.content_hash != b.content_hash


def test_different_asset_id_changes_hash():
    a = build_production_media_asset_binding("m1", "asset_a")
    b = build_production_media_asset_binding("m1", "asset_b")
    assert a.content_hash != b.content_hash


def test_content_hash_is_derived_not_supplied():
    b = build_production_media_asset_binding("m1", "asset_a")
    assert b.content_hash
    # Builder-returned hash equals recomputation over the semantic payload by
    # construction; the builder API has no content_hash parameter at all.
    import inspect

    assert "content_hash" not in inspect.signature(
        build_production_media_asset_binding
    ).parameters


def test_empty_or_invalid_identifiers_fail_closed():
    with pytest.raises(BindingValidationError):
        build_production_media_asset_binding("", "asset_a")
    with pytest.raises(BindingValidationError):
        build_production_media_asset_binding("m1", "")
    with pytest.raises(BindingValidationError):
        build_production_media_asset_binding("m1", "A")  # too short / uppercase
    with pytest.raises(BindingValidationError):
        build_production_media_asset_binding("m1", "UPPER_CASE_ID")


# ---------------------------------------------------------------------------
# Resolver: unequal media_item_id / asset_id is the architectural proof
# ---------------------------------------------------------------------------


def test_unequal_ids_resolve():
    binding = build_production_media_asset_binding(
        media_item_id="scene_media_need_001", asset_id="production_asset_abc"
    )
    result = resolve_bound_asset(
        binding,
        [_record("production_asset_abc", "novel/game/images/story/backgrounds/abc.png")],
    )
    assert result.asset_id == "production_asset_abc"
    assert isinstance(result, ResolvedAsset)


def test_resolver_uses_only_asset_id():
    # A record whose media_item_id would never match proves lookup keys on asset_id.
    binding = build_production_media_asset_binding("scene_media_need_001", "asset_zzz")
    result = resolve_bound_asset(
        binding, [_record("asset_zzz", "novel/game/images/story/cg/zzz.png")]
    )
    assert result.asset_id == "asset_zzz"


def test_resolver_returns_canonical_relative_path():
    binding = build_production_media_asset_binding("m1", "asset_p")
    rel = "novel/game/images/story/characters/marina/marina_pose_01.png"
    result = resolve_bound_asset(binding, [_record("asset_p", rel)])
    assert result.relative_path == rel


def test_unknown_asset_fails_closed():
    binding = build_production_media_asset_binding("m1", "asset_missing")
    with pytest.raises(AssetNotFoundError):
        resolve_bound_asset(binding, [_record("asset_other", "novel/game/images/story/cg/x.png")])


def test_duplicate_asset_id_fails_closed():
    binding = build_production_media_asset_binding("m1", "asset_dup")
    with pytest.raises(AssetIdAmbiguousError):
        resolve_bound_asset(
            binding,
            [
                _record("asset_dup", "novel/game/images/story/cg/a.png"),
                _record("asset_dup", "novel/game/images/story/cg/b.png"),
            ],
        )


# ---------------------------------------------------------------------------
# Ren'Py image-name transform
# ---------------------------------------------------------------------------


def test_generic_renpy_name_transform():
    assert (
        renpy_image_name_from_relative_path(
            "novel/game/images/story/characters/marina/marina_pose_01.png"
        )
        == "story characters marina marina_pose_01"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "/absolute/path.png",
        "../escape.png",
        "novel/game/images/story/../escape.png",
        "novel/game/notimages/foo.png",
        "novel/game/images/story/characters/x.mov",
        "",
    ],
)
def test_invalid_relative_path_fails_closed(bad):
    with pytest.raises(AssetResolutionError):
        renpy_image_name_from_relative_path(bad)


# ---------------------------------------------------------------------------
# Real KIRA asset as first fixture (no KIRA-specific branch anywhere)
# ---------------------------------------------------------------------------


def test_kira_registered_asset_resolves():
    binding = build_production_media_asset_binding(
        media_item_id="kira_yoga_hall_pilot_image_01",
        asset_id="kira_yoga_hall_pilot_image_01",
    )
    result = resolve_bound_asset(binding, [_record("kira_yoga_hall_pilot_image_01", KIRA_RELATIVE_PATH)])
    assert result.asset_id == "kira_yoga_hall_pilot_image_01"
    assert result.relative_path == KIRA_RELATIVE_PATH
    assert result.renpy_image_name == KIRA_RENPY_NAME