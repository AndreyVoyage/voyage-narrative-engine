#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider-neutral local reference contracts for the visual chain.

Adapted from ``services/character_visual_conditioning/model.py`` in the VNE
repo (``ReferenceEntry`` / a single-character ``ReferenceBundle`` shape). The
multi-character ``ReferenceCharacterGroup`` nesting is deliberately NOT carried
over -- Companion V1 conditions on exactly one active character. Machine paths
are OPERATIONAL only and never enter the semantic payload / content hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .hashing import content_hash

REFERENCE_BUNDLE_SCHEMA_VERSION = "companion_reference_bundle/0.1"

FILE_TYPE_TO_CONTENT_TYPE = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


@dataclass(frozen=True)
class ReferenceEntry:
    """One resolved, validated local reference (with its bytes)."""

    character_id: str
    asset_id: str
    roles: Tuple[str, ...]
    relative_path: str            # OPERATIONAL: snapshot-relative; never hashed / never in prose
    sha256: str
    byte_length: int
    image_format: str             # PNG | JPEG | WEBP
    content_type: str
    payload: bytes
    source_semantic_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(self.roles))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "characterId": self.character_id,
            "assetId": self.asset_id,
            "roles": list(self.roles),
            "sha256": self.sha256,
            "byteLength": self.byte_length,
            "imageFormat": self.image_format,
            "contentType": self.content_type,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.semantic_payload()


@dataclass(frozen=True)
class ReferenceBundle:
    """The exact ordered reference selection for one generation input."""

    schema_version: str
    character_id: str
    character_snapshot_version: str
    references: Tuple[ReferenceEntry, ...]
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "characterId": self.character_id,
            "characterSnapshotVersion": self.character_snapshot_version,
            "references": [r.semantic_payload() for r in self.references],
        }

    def compute_hash(self) -> str:
        return content_hash(self.semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            **self.semantic_payload(),
            "contentHash": self.content_hash or self.compute_hash(),
        }
