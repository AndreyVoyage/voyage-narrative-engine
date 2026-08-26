#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Media Asset Binding v0 -- public API.

An explicit, immutable binding of a planned downstream media item to an
already-registered production asset, plus a pure runtime resolver.

Reference (generic, no KIRA-specific behavior):

    ProductionMediaAssetBinding  (media_item_id -> asset_id)
    resolve_bound_asset          (binding + Registry records -> ResolvedAsset)
    renpy_image_name_from_relative_path  (pure generic transform)

``media_item_id`` and ``asset_id`` are DISTINCT stable identifiers.
"""

from __future__ import annotations

from .builder import build_production_media_asset_binding
from .errors import (
    AssetIdAmbiguousError,
    AssetNotFoundError,
    AssetResolutionError,
    BindingValidationError,
    ProductionMediaAssetBindingError,
)
from .model import (
    BINDING_SCHEMA_VERSION,
    ProductionMediaAssetBinding,
    ResolvedAsset,
)
from .resolver import renpy_image_name_from_relative_path, resolve_bound_asset

__all__ = [
    "build_production_media_asset_binding",
    "ProductionMediaAssetBinding",
    "ResolvedAsset",
    "resolve_bound_asset",
    "renpy_image_name_from_relative_path",
    "BINDING_SCHEMA_VERSION",
    "ProductionMediaAssetBindingError",
    "BindingValidationError",
    "AssetResolutionError",
    "AssetNotFoundError",
    "AssetIdAmbiguousError",
]