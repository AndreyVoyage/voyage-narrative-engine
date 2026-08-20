#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Interpretation Artifact v0 -- plain-data models.

Deeply immutable, stdlib-only. Mirrors the ASS / Location Canon / Character
Canon bridge immutability pattern: frozen dataclasses + recursive
``MappingProxyType``/``tuple`` freezing + fresh-plain serialization.

The artifact freezes exact downstream source anchors (ASS, Location Canon,
Character Canon snapshots) plus an explicitly caller-supplied interpretation
payload. It performs NO interpretation and NO provider calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional, Tuple


def _freeze(value: Any) -> Any:
    """Deeply convert a value into an immutable representation."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _to_plain(value: Any) -> Any:
    """Deeply convert a (possibly frozen) value into fresh plain data."""
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class AssAnchor:
    """Exact accepted-scene version anchor (never mutated or reinterpreted)."""

    scene_id: str
    ass_id: str
    version: int
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "ass_id": self.ass_id,
            "version": self.version,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class LocationAnchor:
    """Exact Location Canon version anchor."""

    location_id: str
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {"location_id": self.location_id, "content_hash": self.content_hash}


@dataclass(frozen=True)
class CharacterAnchor:
    """Frozen Character Canon snapshot state used by the interpretation.

    ``serialized_snapshot`` is the portable, deeply-frozen serialized
    representation of the CharacterCanonSnapshot that was actually used, so
    downstream does not silently depend on live Canon state. It contains no
    absolute machine paths.
    """

    character_id: str
    status: str
    snapshot_content_hash: str
    serialized_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "serialized_snapshot", _freeze(self.serialized_snapshot))

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "status": self.status,
            "snapshot_content_hash": self.snapshot_content_hash,
            "serialized_snapshot": _to_plain(self.serialized_snapshot),
        }


@dataclass(frozen=True)
class SceneInterpretationArtifact:
    """Immutable downstream interpretation artifact.

    ``interpretation_payload`` is an explicitly supplied, deeply frozen,
    JSON-compatible authoring payload. This slice never generates, enriches,
    or validates it semantically.

    ``production_eligible`` is derived only from the included Character Canon
    snapshots: true iff all snapshot statuses are explicitly APPROVED. A
    PENDING_APPROVAL snapshot (or any unknown status) results in false.
    """

    schema_version: str
    scene_id: str
    ass_anchor: AssAnchor
    location_anchor: LocationAnchor
    character_anchors: Tuple[CharacterAnchor, ...]
    interpretation_payload: Mapping[str, Any]
    content_hash: str
    production_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "character_anchors", tuple(self.character_anchors))
        object.__setattr__(self, "interpretation_payload", _freeze(self.interpretation_payload))

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload (fresh plain data).

        Machine-specific roots never enter. Envelope metadata (schema_version,
        content_hash) is excluded.
        """
        anchors = [a.to_dict() for a in self.character_anchors]
        anchors.sort(key=lambda a: a["character_id"])
        return {
            "scene_id": self.scene_id,
            "ass_anchor": self.ass_anchor.to_dict(),
            "location_anchor": self.location_anchor.to_dict(),
            "character_anchors": anchors,
            "interpretation_payload": _to_plain(self.interpretation_payload),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the full artifact envelope (fresh plain data)."""
        anchors = [a.to_dict() for a in self.character_anchors]
        anchors.sort(key=lambda a: a["character_id"])
        return {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "ass_anchor": self.ass_anchor.to_dict(),
            "location_anchor": self.location_anchor.to_dict(),
            "character_anchors": anchors,
            "interpretation_payload": _to_plain(self.interpretation_payload),
            "content_hash": self.content_hash,
            "production_eligible": self.production_eligible,
        }