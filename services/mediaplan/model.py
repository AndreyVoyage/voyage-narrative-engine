#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaPlan v0 -- plain-data models.

Deeply immutable, stdlib-only. Reuses the established ASS / Location Canon /
Character Canon bridge / SceneInterpretationArtifact immutability pattern:
frozen dataclasses + recursive ``MappingProxyType``/``tuple`` freezing +
fresh-plain serialization.

MediaPlan owns WHICH media items are planned downstream. MediaItem owns the
item-level specification. ``characters_in_frame`` lives at MediaItem level.

No generation, no provider, no prompt composition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Tuple


class MediaKind(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class MediaItem:
    """One planned downstream media item.

    ``media_item_id`` is an explicit caller-supplied stable identifier,
    unique within a MediaPlan (never auto-generated). ``maybe_kind`` is the
    exact media kind (never a raw string).

    ``characters_in_frame`` is an ordered tuple of exact character IDs; it is
    valid only for IMAGE/VIDEO and must be empty for AUDIO. ``planning_payload``
    is an opaque, deeply frozen JSON-compatible planning payload.
    """

    media_item_id: str
    media_kind: MediaKind
    characters_in_frame: Tuple[str, ...]
    planning_payload: Mapping[str, Any]
    # Optional explicit source references preserved verbatim; validated only
    # that they are non-empty strings, since A5 does not invent a cue system.
    source_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "characters_in_frame", tuple(self.characters_in_frame))
        object.__setattr__(self, "planning_payload", _freeze(self.planning_payload))
        object.__setattr__(self, "source_refs", tuple(self.source_refs))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "media_item_id": self.media_item_id,
            "media_kind": self.media_kind.value,
            "characters_in_frame": _to_plain(self.characters_in_frame),
            "planning_payload": _to_plain(self.planning_payload),
        }
        if self.source_refs:
            result["source_refs"] = _to_plain(self.source_refs)
        return result


@dataclass(frozen=True)
class MediaPlan:
    """The immutable, ordered downstream media plan.

    ``scene_interpretation_content_hash`` binds the exact
    SceneInterpretationArtifact used; a change upstream changes this plan's
    semantic hash. ``production_eligible`` is monotonic: never True when the
    upstream artifact was not production eligible.
    """

    schema_version: str
    scene_id: str
    scene_interpretation_content_hash: str
    media_items: Tuple[MediaItem, ...]
    content_hash: str
    production_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "media_items", tuple(self.media_items))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_interpretation_content_hash": self.scene_interpretation_content_hash,
            "media_items": [item.to_dict() for item in self.media_items],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "scene_interpretation_content_hash": self.scene_interpretation_content_hash,
            "media_items": [item.to_dict() for item in self.media_items],
            "content_hash": self.content_hash,
            "production_eligible": self.production_eligible,
        }