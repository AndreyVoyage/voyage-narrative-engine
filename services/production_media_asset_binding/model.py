#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Media Asset Binding v0 -- plain-data models.

Represents the explicit, immutable binding of a planned downstream media item
(``media_item_id``) to a production asset (``asset_id``) already registered in
the Visual Asset Registry.

``media_item_id`` and ``asset_id`` are DISTINCT stable identifiers. String
equality between them is never an implicit contract: the binding exists to
make the relationship explicit, and it must work even when the two differ.

The binding stores stable identifiers only. It never stores relative or
absolute filesystem paths, Registry filenames, media binary SHA-256, MediaPlan
hashes, provider metadata, character/scene IDs, or timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass

BINDING_SCHEMA_VERSION = "production_media_asset_binding/0.1"


@dataclass(frozen=True)
class ProductionMediaAssetBinding:
    """Immutable media-item -> production-asset binding.

    ``content_hash`` is derived (never caller-supplied as authority). The
    semantic payload covers exactly the two stable identifiers plus the schema
    version; the envelope ``content_hash`` itself is excluded from the hash.
    """

    schema_version: str
    media_item_id: str
    asset_id: str
    content_hash: str

    def semantic_payload(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "media_item_id": self.media_item_id,
            "asset_id": self.asset_id,
        }

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "media_item_id": self.media_item_id,
            "asset_id": self.asset_id,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class ResolvedAsset:
    """Result of resolving a binding's asset_id through the Registry.

    ``relative_path`` and ``renpy_image_name`` are runtime concerns derived
    from the Registry record; they are not part of the binding identity.
    """

    asset_id: str
    relative_path: str
    renpy_image_name: str

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "relative_path": self.relative_path,
            "renpy_image_name": self.renpy_image_name,
        }