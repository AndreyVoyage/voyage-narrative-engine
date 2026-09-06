#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderedASS production-asset resolver v1 (asset_id-only).

Resolves an explicit set of ``asset_id`` strings directly against the existing
Visual Asset Registry, producing an immutable ``asset_id -> ResolvedAsset``
mapping whose ``renpy_image_name`` values feed the OrderedASS renderer.

Key boundary differences from the legacy media-item adapter:

- NO ``media_item_id`` is required or fabricated: OrderedASS VisualChangeEvent
  carries only ``asset_id``, so no ``ProductionMediaAssetBinding`` is built and
  ``resolve_bound_asset`` is never called.
- Physical/integrity checks (existence, regular file, symlink rejection, path
  containment, recorded SHA-256 equality) happen here, at the integration
  boundary, before any source is emitted.
- Image-name collision is checked across the explicit supplied asset set.

Pure, deterministic, no filesystem writes, no registry mutation, no copy, no
``import renpy``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import MappingProxyType
from typing import Collection, Mapping

from services.production_media_asset_binding import AssetResolutionError, ResolvedAsset
from services.production_media_asset_binding.resolver import (
    renpy_image_name_from_relative_path,
)
from tools.visual_asset_registry import ASSET_ID_RE, load_registry, lookup_asset

__all__ = ["resolve_ordered_assets_for_renpy", "OrderedAssetResolutionError"]

_GAME_IMAGES_RELATIVE_PREFIX = "novel/game/images/"

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


class OrderedAssetResolutionError(ValueError):
    """Raised when an asset_id cannot be safely resolved for Ren'Py."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_safe_relative(relative_path: str) -> bool:
    if not relative_path:
        return False
    if relative_path.startswith("/") or relative_path.startswith("\\"):
        return False
    if _DRIVE_PREFIX_RE.match(relative_path):
        return False
    parts = relative_path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if any(p in ("", ".") for p in parts):
        return False
    return True


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _dedupe_validate_asset_ids(asset_ids: Collection[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for asset_id in asset_ids:
        if not isinstance(asset_id, str) or ASSET_ID_RE.fullmatch(asset_id) is None:
            raise OrderedAssetResolutionError("invalid asset_id {!r}".format(asset_id))
        if asset_id not in seen:
            seen.add(asset_id)
            result.append(asset_id)
    return result


def _resolve_one(record: Mapping[str, object], repo_root: Path) -> ResolvedAsset:
    asset_id = record.get("asset_id")
    if not isinstance(asset_id, str):
        raise OrderedAssetResolutionError("registry record has no string asset_id")

    relative_path = record.get("relative_path")
    if not isinstance(relative_path, str) or relative_path.strip() == "":
        raise OrderedAssetResolutionError(
            "registry record {!r} has no valid relative_path".format(asset_id)
        )
    if not _is_safe_relative(relative_path):
        raise OrderedAssetResolutionError(
            "registry record {!r} relative_path is absolute/traversal/unsafe".format(asset_id)
        )

    try:
        image_name = renpy_image_name_from_relative_path(relative_path)
    except AssetResolutionError as exc:
        raise OrderedAssetResolutionError(str(exc)) from exc

    abs_path = repo_root / relative_path
    images_root = (repo_root / _GAME_IMAGES_RELATIVE_PREFIX).resolve()
    if not _is_under(abs_path, images_root):
        raise OrderedAssetResolutionError(
            "asset {!r} resolves outside the game images root".format(asset_id)
        )

    if not abs_path.exists():
        raise OrderedAssetResolutionError("asset {!r} file does not exist".format(asset_id))
    if not abs_path.is_file():
        raise OrderedAssetResolutionError(
            "asset {!r} path is not a regular file".format(asset_id)
        )
    if abs_path.is_symlink():
        raise OrderedAssetResolutionError("asset {!r} is a symlink".format(asset_id))

    imported_hash = record.get("imported_hash")
    try:
        actual_hash = _sha256_bytes(abs_path.read_bytes())
    except OSError as exc:
        raise OrderedAssetResolutionError(
            "asset {!r} is not readable: {}".format(asset_id, exc)
        ) from exc
    if imported_hash != actual_hash:
        raise OrderedAssetResolutionError(
            "asset {!r} imported_hash mismatch (recorded {}, actual {})".format(
                asset_id, imported_hash, actual_hash
            )
        )

    return ResolvedAsset(
        asset_id=asset_id,
        relative_path=relative_path,
        renpy_image_name=image_name,
    )


def resolve_ordered_assets_for_renpy(
    asset_ids: Collection[str],
    *,
    registry_path: Path,
    repo_root: Path,
) -> Mapping[str, ResolvedAsset]:
    """Resolve explicit asset IDs to safe Ren'Py image names.

    Loads the registry exactly once, resolves each unique asset_id with full
    physical/integrity checks, rejects cross-asset image-name collisions, and
    returns an immutable (read-only) ``Mapping[str, ResolvedAsset]``. Repeated
    use of the same asset_id is valid. No file copy, no registry mutation.
    """
    if not isinstance(registry_path, Path):
        raise OrderedAssetResolutionError("registry_path must be a Path")
    if not isinstance(repo_root, Path):
        raise OrderedAssetResolutionError("repo_root must be a Path")

    if not registry_path.exists():
        raise OrderedAssetResolutionError("registry path does not exist: {}".format(registry_path))
    if not registry_path.is_file():
        raise OrderedAssetResolutionError("registry path is not a regular file: {}".format(registry_path))

    try:
        records = load_registry(registry_path)
    except Exception as exc:
        raise OrderedAssetResolutionError("failed to load registry: {}".format(exc)) from exc
    if not isinstance(records, list):
        raise OrderedAssetResolutionError("registry must contain an assets array")

    result: dict[str, ResolvedAsset] = {}
    for asset_id in _dedupe_validate_asset_ids(asset_ids):
        try:
            record = lookup_asset(records, asset_id)
        except ValueError as exc:
            raise OrderedAssetResolutionError(str(exc)) from exc
        result[asset_id] = _resolve_one(record, repo_root)

    by_name: dict[str, str] = {}
    for asset_id, resolved in result.items():
        name = resolved.renpy_image_name
        if name in by_name:
            raise OrderedAssetResolutionError(
                "asset_id {!r} and {!r} resolve to the same Ren'Py image name {!r}".format(
                    by_name[name], asset_id, name
                )
            )
        by_name[name] = asset_id

    return MappingProxyType(dict(result))
