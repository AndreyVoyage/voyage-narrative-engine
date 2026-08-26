#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Media Asset Binding v0 -- deterministic builder.

Constructs the immutable ``ProductionMediaAssetBinding`` from the two stable
identifiers. ``content_hash`` is DERIVED here; callers never supply it.

The canonical content-hash convention mirrors the repository-native pattern
(``services/ass``, ``services/scene_interpretation``,
``services/generated_image_review``)::

    json.dumps(payload, ensure_ascii=False, sort_keys=True) -> UTF-8 -> SHA-256
"""

from __future__ import annotations

import hashlib
import json
import re

from .errors import BindingValidationError
from .model import BINDING_SCHEMA_VERSION, ProductionMediaAssetBinding

# Mirrors the Visual Asset Registry asset-id semantics without importing the
# tools/ module (the binding layer does not depend on the integration layer).
_ASSET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _content_hash(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_production_media_asset_binding(media_item_id: str, asset_id: str) -> ProductionMediaAssetBinding:
    """Build an immutable media-item -> production-asset binding.

    Both identifiers must be non-empty strings; ``asset_id`` must additionally
    satisfy the existing Visual Asset Registry v0 asset-id syntax. The derived
    ``content_hash`` is never caller-supplied.
    """
    if not isinstance(media_item_id, str) or media_item_id.strip() == "":
        raise BindingValidationError("media_item_id must be a non-empty string")
    if not isinstance(asset_id, str) or asset_id.strip() == "":
        raise BindingValidationError("asset_id must be a non-empty string")
    if _ASSET_ID_RE.fullmatch(asset_id) is None:
        raise BindingValidationError(
            f"asset_id {asset_id!r} does not satisfy the Visual Asset Registry v0 asset-id syntax"
        )

    provisional = ProductionMediaAssetBinding(
        schema_version=BINDING_SCHEMA_VERSION,
        media_item_id=media_item_id,
        asset_id=asset_id,
        content_hash="",
    )
    content_hash = _content_hash(provisional.semantic_payload())
    return ProductionMediaAssetBinding(
        schema_version=BINDING_SCHEMA_VERSION,
        media_item_id=media_item_id,
        asset_id=asset_id,
        content_hash=content_hash,
    )