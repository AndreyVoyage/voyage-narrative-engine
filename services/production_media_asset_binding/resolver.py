#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Media Asset Binding v0 -- pure resolver.

Resolves an immutable binding through an already-loaded set of Visual Asset
Registry records into a runtime result (``ResolvedAsset``), and derives the
generic Ren'Py automatic-image name from a registry ``relative_path``.

This module is pure Python: it performs NO Registry filesystem I/O, imports
NO Ren'Py engine modules, and writes nothing.
"""

from __future__ import annotations

from typing import Any

from .errors import (
    AssetIdAmbiguousError,
    AssetNotFoundError,
    AssetResolutionError,
)
from .model import ProductionMediaAssetBinding, ResolvedAsset

# Repo-root-relative prefix of the Ren'Py game images directory. Ren'Py's
# automatic image discovery scans ``game/images/``; in this repository ``game``
# lives at ``novel/game``, so the repo-relative images root is
# ``novel/game/images/``.
_GAME_IMAGES_PREFIX = "novel/game/images/"

_SUPPORTED_EXTS = ("png", "webp", "jpg")


def renpy_image_name_from_relative_path(relative_path: str) -> str:
    """Derive the Ren'Py 8.5 automatic image name from a Registry relative_path.

    Generic and pure: validates the committed game-images root prefix, removes
    a supported image extension, then returns the lowercase basename stem
    (dropping any ``@`` oversampling suffix). Ren'Py 8.5 automatic-image naming
    is directory-independent (``renpy/common/00images.rpy`` registers the
    basename stem). Fails closed for absolute/traversal paths, unsupported
    extensions, and paths outside the game images root. No special-casing of
    character/category/asset.
    """
    if not isinstance(relative_path, str) or relative_path.strip() == "":
        raise AssetResolutionError("relative_path must be a non-empty string")
    if relative_path.startswith(("/", "\\")):
        raise AssetResolutionError("relative_path must not be absolute")
    if ".." in relative_path.replace("\\", "/").split("/"):
        raise AssetResolutionError("relative_path must not contain traversal")
    if not relative_path.startswith(_GAME_IMAGES_PREFIX):
        raise AssetResolutionError(
            f"relative_path {relative_path!r} is outside the game images root"
        )

    sub = relative_path[len(_GAME_IMAGES_PREFIX):]
    if not sub or sub.startswith("/"):
        raise AssetResolutionError("relative_path has no image name after the images root")

    name = sub
    for ext in _SUPPORTED_EXTS:
        if name.endswith("." + ext):
            name = name[: -(len(ext) + 1)]
            break
    else:
        raise AssetResolutionError(f"relative_path has unsupported image extension: {relative_path!r}")

    if not name:
        raise AssetResolutionError("relative_path yields an empty image name")

    components = name.replace("\\", "/").split("/")
    if any(c in ("", ".") for c in components):
        raise AssetResolutionError(f"relative_path has an empty path component: {relative_path!r}")

    # Ren'Py 8.5 automatic-image naming is directory-independent: the image
    # name is the lowercase basename stem with any @ oversampling suffix
    # removed. Parent directory components are never part of the name.
    stem = components[-1].lower().partition("@")[0]
    if not stem:
        raise AssetResolutionError("relative_path yields an empty image name")

    return stem


def resolve_bound_asset(
    binding: ProductionMediaAssetBinding,
    registry_records: list[dict[str, Any]],
) -> ResolvedAsset:
    """Resolve a binding against already-loaded Registry records.

    Uses ONLY ``binding.asset_id`` as the lookup key (``media_item_id`` is
    never used, so the two identifiers may freely differ). Requires exactly
    one match, obtains its canonical ``relative_path``, and derives the generic
    Ren'Py image name.
    """
    if not isinstance(binding, ProductionMediaAssetBinding):
        raise AssetResolutionError("binding must be a ProductionMediaAssetBinding")

    matches = [r for r in registry_records if r.get("asset_id") == binding.asset_id]
    if not matches:
        raise AssetNotFoundError(f"no Registry record for asset_id {binding.asset_id!r}")
    if len(matches) > 1:
        raise AssetIdAmbiguousError(
            f"multiple Registry records for asset_id {binding.asset_id!r}"
        )

    record = matches[0]
    relative_path = record.get("relative_path")
    if not isinstance(relative_path, str) or relative_path.strip() == "":
        raise AssetResolutionError(
            f"Registry record for {binding.asset_id!r} has no valid relative_path"
        )

    return ResolvedAsset(
        asset_id=binding.asset_id,
        relative_path=relative_path,
        renpy_image_name=renpy_image_name_from_relative_path(relative_path),
    )