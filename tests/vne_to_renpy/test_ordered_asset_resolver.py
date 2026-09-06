#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the OrderedASS asset_id-only resolver v1."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.vne_to_renpy.ordered_asset_resolver import (  # noqa: E402
    OrderedAssetResolutionError,
    resolve_ordered_assets_for_renpy,
)

_PNG_DATA = b"\x89PNG\r\n\x1a\n" + b"fake-bytes-for-hash" * 4


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(asset_id: str, relative_path: str, data: bytes) -> dict:
    return {
        "asset_id": asset_id,
        "type": "character",
        "relative_path": relative_path,
        "source_kind": "character_canon",
        "source_character_id": "kira",
        "imported_hash": _sha(data),
        "format": "png",
        "mime_type": "image/png",
    }


def _setup(*, records=None, data=None):
    repo_root = Path(tempfile.mkdtemp(prefix="vne_ordered_assets_"))
    registry_path = repo_root / "registry.json"
    data = data if data is not None else _PNG_DATA
    if records is None:
        records = [_record("asset_one", "novel/game/images/story/kira/asset_one.png", data)]
    for rec in records:
        p = repo_root / rec["relative_path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    registry_path.write_text(json.dumps({"assets": records}), encoding="utf-8")
    return repo_root, registry_path


def _resolve(asset_ids, repo_root, registry_path):
    return resolve_ordered_assets_for_renpy(
        asset_ids, registry_path=registry_path, repo_root=repo_root
    )


def test_valid_registry_hit():
    repo_root, registry_path = _setup()
    result = _resolve(["asset_one"], repo_root, registry_path)
    assert result["asset_one"].renpy_image_name == "asset_one"
    assert result["asset_one"].asset_id == "asset_one"


def test_result_is_immutable():
    repo_root, registry_path = _setup()
    result = _resolve(["asset_one"], repo_root, registry_path)
    assert not isinstance(result, dict)
    with pytest.raises(TypeError):
        result["new_asset"] = result["asset_one"]  # type: ignore[index]


def test_same_asset_reused_safely():
    repo_root, registry_path = _setup()
    result = _resolve(["asset_one", "asset_one"], repo_root, registry_path)
    assert set(result.keys()) == {"asset_one"}


def test_missing_record_fails():
    repo_root, registry_path = _setup()
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_ghost"], repo_root, registry_path)


def test_duplicate_registry_id_fails_closed():
    data = _PNG_DATA
    records = [
        _record("asset_one", "novel/game/images/story/kira/a.png", data),
        _record("asset_one", "novel/game/images/story/kira/b.png", data),
    ]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_registry_path_missing_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, repo_root / "nope.json")


def test_registry_path_not_regular_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    registry_path = repo_root / "registry_dir"
    registry_path.mkdir()
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_asset_file_missing_fails():
    repo_root, registry_path = _setup()
    (repo_root / "novel/game/images/story/kira/asset_one.png").unlink()
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_asset_is_directory_fails():
    repo_root, registry_path = _setup()
    p = repo_root / "novel/game/images/story/kira/asset_one.png"
    p.unlink()
    p.mkdir()
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_symlink_asset_rejected(tmp_path):
    repo_root, registry_path = _setup()
    target = tmp_path / "real.png"
    target.write_bytes(_PNG_DATA)
    asset_path = repo_root / "novel/game/images/story/kira/asset_one.png"
    asset_path.unlink()
    try:
        asset_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_absolute_relative_path_rejected():
    data = _PNG_DATA
    records = [_record("asset_one", "/novel/game/images/story/kira/asset_one.png", data)]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_traversal_relative_path_rejected():
    data = _PNG_DATA
    records = [_record("asset_one", "novel/game/images/../escape.png", data)]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_unsupported_extension_rejected():
    data = _PNG_DATA
    records = [_record("asset_one", "novel/game/images/story/kira/asset_one.gif", data)]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_hash_mismatch_rejected():
    data = _PNG_DATA
    records = [_record("asset_one", "novel/game/images/story/kira/asset_one.png", data)]
    repo_root, registry_path = _setup(records=records)
    p = repo_root / "novel/game/images/story/kira/asset_one.png"
    p.write_bytes(b"tampered")
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one"], repo_root, registry_path)


def test_valid_hash_passes():
    repo_root, registry_path = _setup()
    result = _resolve(["asset_one"], repo_root, registry_path)
    assert result["asset_one"].relative_path.endswith("asset_one.png")


def test_image_name_collision_rejected():
    data = _PNG_DATA
    records = [
        _record("asset_one", "novel/game/images/a/asset_one.png", data),
        _record("asset_two", "novel/game/images/b/asset_one.png", data),
    ]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one", "asset_two"], repo_root, registry_path)


def test_larger_asset_set_catches_cross_scene_collision():
    data = _PNG_DATA
    records = [
        _record("asset_one", "novel/game/images/a/asset_one.png", data),
        _record("asset_two", "novel/game/images/b/asset_one.png", data),
        _record("asset_three", "novel/game/images/c/asset_three.png", data),
    ]
    repo_root, registry_path = _setup(records=records)
    with pytest.raises(OrderedAssetResolutionError):
        _resolve(["asset_one", "asset_two", "asset_three"], repo_root, registry_path)


def test_no_file_copy_or_registry_mutation():
    repo_root, registry_path = _setup()
    before_registry = registry_path.read_bytes()
    before_files = {str(p) for p in repo_root.rglob("*") if p.is_file()}
    _resolve(["asset_one"], repo_root, registry_path)
    after_registry = registry_path.read_bytes()
    after_files = {str(p) for p in repo_root.rglob("*") if p.is_file()}
    assert before_registry == after_registry
    assert before_files == after_files
