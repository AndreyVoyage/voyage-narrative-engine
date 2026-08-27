#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNE -> Ren'Py visual asset consumer v0 (thin adapter boundary).

Receives a stable ``media_item_id`` plus an explicit ``asset_id``, builds an
immutable ``ProductionMediaAssetBinding`` in memory, loads the existing Visual
Asset Registry (Registry file I/O lives at this adapter boundary), resolves
the binding through the existing pure domain resolver, and returns the
existing ``ResolvedAsset`` whose ``renpy_image_name`` is the Ren'Py-consumable
image name.

No persistence: this module never writes a binding, resolved asset, cache,
JSON, Registry, scene data, or ``.rpy`` file. Each invocation constructs and
resolves entirely in memory.

It must never ``import renpy`` or emit Ren'Py script statements.
"""

from __future__ import annotations

from pathlib import Path

from services.production_media_asset_binding import (
    ResolvedAsset,
    build_production_media_asset_binding,
    resolve_bound_asset,
)
from tools.visual_asset_registry import load_registry

__all__ = ["resolve_media_asset_for_renpy"]


def resolve_media_asset_for_renpy(
    *,
    media_item_id: str,
    asset_id: str,
    registry_path: Path,
) -> ResolvedAsset:
    """Resolve a production media asset to a Ren'Py-consumable image name.

    Builds an immutable ``ProductionMediaAssetBinding`` from the two explicit
    stable identifiers, loads Registry records via the existing
    ``load_registry`` (file I/O belongs at this adapter boundary), then
    delegates to the existing pure ``resolve_bound_asset``.

    ``media_item_id`` and ``asset_id`` are DISTINCT identifiers: resolution is
    keyed strictly on ``binding.asset_id`` and never derives ``asset_id`` from
    ``media_item_id``.

    Returns the existing ``ResolvedAsset`` (``asset_id``, ``relative_path``,
    ``renpy_image_name``). No persistence, no scene write, no ``.rpy`` output.
    """
    binding = build_production_media_asset_binding(
        media_item_id=media_item_id,
        asset_id=asset_id,
    )
    registry_records = load_registry(registry_path)
    return resolve_bound_asset(binding, registry_records)
