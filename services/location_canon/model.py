#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Location Canon v0 -- plain-data models.

Deeply immutable, stdlib-only. Mirrors the ASS v0 immutability pattern:
frozen dataclasses + recursive ``MappingProxyType``/``tuple`` freezing +
fresh-plain serialization for output.

Location Canon owns VISUAL / PHYSICAL LOCATION IDENTITY only. It does NOT
own story behaviour, character psychology, relationships, scene-specific
character actions, Character Canon, camera composition, MediaPlan,
SceneInterpretationArtifact, prompt generation, or runtime export.

Field set (v0):

    Hashed (semantic payload):
        location_id, tier, scale, identity, palette, fixed_features

    Non-hashed envelope:
        schema_version, content_hash (the hash), provenance
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional, Tuple


def _freeze(value: Any) -> Any:
    """Deeply convert a value into an immutable representation.

    - dict/Mapping -> MappingProxyType of recursively-frozen values
      (a fresh dict is built first, severing any caller alias).
    - list/tuple -> tuple of recursively-frozen items.
    - other values (str/int/float/bool/None) are already immutable.
    """
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


def _freeze_string_tuple(items: Any) -> tuple:
    if items is None:
        return ()
    return tuple(str(item) for item in items)


@dataclass(frozen=True)
class FixedFeature:
    """One persistent, canonical physical feature of a location.

    ``count`` is an optional positive integer for countable features
    (e.g. the pilot's exactly-two treadmills). It carries no brand/model/
    biography -- those would be invented facts and are out of scope.
    """

    feature_id: str
    label: str
    count: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "feature_id": self.feature_id,
            "label": self.label,
        }
        if self.count is not None:
            result["count"] = self.count
        return result


@dataclass(frozen=True)
class Provenance:
    """Loader-generated, portable source provenance.

    ``source_ref`` is a repository-relative path and must never carry an
    absolute machine path. ``source_hash`` is the deterministic SHA-256 of
    the canonicalized raw source JSON.
    """

    source_kind: str
    source_ref: str
    source_hash: str
    source_schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "source_hash": self.source_hash,
            "source_schema_version": self.source_schema_version,
        }


@dataclass(frozen=True)
class LocationCanon:
    """The immutable canonical location identity snapshot.

    Construct directly only when the caller supplies every field, including
    an already-computed ``content_hash``; the normal path is
    ``services.location_canon.loader``, which computes it.
    """

    schema_version: str
    location_id: str
    tier: str
    scale: Tuple[str, ...]
    identity: Tuple[str, ...]
    palette: Tuple[str, ...]
    fixed_features: Tuple[FixedFeature, ...]
    content_hash: str
    provenance: Optional[Provenance] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scale", _freeze_string_tuple(self.scale))
        object.__setattr__(self, "identity", _freeze_string_tuple(self.identity))
        object.__setattr__(self, "palette", _freeze_string_tuple(self.palette))
        object.__setattr__(self, "fixed_features", tuple(self.fixed_features))

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload (fresh plain data)."""
        return {
            "location_id": self.location_id,
            "tier": self.tier,
            "scale": _to_plain(self.scale),
            "identity": _to_plain(self.identity),
            "palette": _to_plain(self.palette),
            "fixed_features": [f.to_dict() for f in self.fixed_features],
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the full LocationCanon envelope (fresh plain data)."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "location_id": self.location_id,
            "tier": self.tier,
            "scale": _to_plain(self.scale),
            "identity": _to_plain(self.identity),
            "palette": _to_plain(self.palette),
            "fixed_features": [f.to_dict() for f in self.fixed_features],
            "content_hash": self.content_hash,
        }
        if self.provenance is not None:
            result["provenance"] = self.provenance.to_dict()
        return result

    @property
    def treadmill_count(self) -> int:
        """Convenience accessor for the pilot's countable treadmill feature.

        Returns 0 when no treadmills feature is present (not the pilot).
        """
        for feature in self.fixed_features:
            if feature.feature_id == "treadmills":
                return int(feature.count or 0)
        return 0