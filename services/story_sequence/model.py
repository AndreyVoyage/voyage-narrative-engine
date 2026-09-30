#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story Sequence v0 -- plain-data model.

``StorySequence`` is the Scenario-owned story-level structure above immutable
accepted scenes. It holds exactly two semantic facts for V0:

- ``ordered_scene_ids`` -- the canonical, deterministic project scene order;
- ``start_scene_id`` -- the designated entry scene.

It deliberately owns NO story-graph nodes, edges, conditions, flags, variables,
player state, media, characters, locations, workspace membership, or runtime
state. Scene-to-scene runtime control flow remains owned by SceneBody /
OrderedASS (ENTRY / SCENE / END targets and per-scene ``next_target``); this
model never synthesizes a scene-to-next-scene jump from list order.

The model is ``@dataclass(frozen=True)`` and holds only detached immutable data
(the sequence is a ``tuple``). ``to_dict()`` returns fresh plain data and is
deterministic; list order is preserved because order IS the semantic payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

from .errors import StorySequenceValidationError

STORY_SEQUENCE_SCHEMA_VERSION = "vne_story_sequence/0.1"


def _require_scene_id(value: Any, field: str) -> str:
    """Validate a scene identity per the existing project-metadata identity
    rules (mirrors ``services/workspace_project`` ``_require_non_empty_string``):
    non-empty, and no leading/trailing whitespace. Never silently normalized."""
    if not isinstance(value, str) or value == "":
        raise StorySequenceValidationError(f"{field}: required non-empty string")
    if value.strip() != value:
        raise StorySequenceValidationError(
            f"{field}: must not have leading/trailing whitespace"
        )
    return value


@dataclass(frozen=True)
class StorySequence:
    """The immutable, deterministic story-level scene order + entry scene."""

    schema_version: str
    ordered_scene_ids: Tuple[str, ...]
    start_scene_id: str

    def __post_init__(self) -> None:
        if self.schema_version != STORY_SEQUENCE_SCHEMA_VERSION:
            raise StorySequenceValidationError(
                f"schema_version {self.schema_version!r} unsupported; "
                f"expected {STORY_SEQUENCE_SCHEMA_VERSION!r}"
            )

        ids = tuple(self.ordered_scene_ids)
        if len(ids) == 0:
            raise StorySequenceValidationError("ordered_scene_ids: must be non-empty")

        seen: dict[str, int] = {}
        for index, scene_id in enumerate(ids):
            normalized = _require_scene_id(scene_id, f"ordered_scene_ids[{index}]")
            if normalized in seen:
                raise StorySequenceValidationError(
                    f"duplicate scene_id {normalized!r} "
                    f"(also at ordered_scene_ids[{seen[normalized]}])"
                )
            seen[normalized] = index
        object.__setattr__(self, "ordered_scene_ids", ids)

        start = _require_scene_id(self.start_scene_id, "start_scene_id")
        object.__setattr__(self, "start_scene_id", start)
        if start not in seen:
            raise StorySequenceValidationError(
                f"start_scene_id {start!r} is not present in ordered_scene_ids"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical plain dict (fresh data, order-preserving)."""
        return {
            "schema_version": self.schema_version,
            "ordered_scene_ids": list(self.ordered_scene_ids),
            "start_scene_id": self.start_scene_id,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "StorySequence":
        """Build a StorySequence from plain dict data (fail closed)."""
        if not isinstance(data, dict):
            raise StorySequenceValidationError("story sequence root must be an object")
        allowed = {"schema_version", "ordered_scene_ids", "start_scene_id"}
        unknown = set(data) - allowed
        if unknown:
            raise StorySequenceValidationError(
                f"story sequence: unknown field(s) {sorted(unknown)!r}"
            )
        for field in ("schema_version", "ordered_scene_ids", "start_scene_id"):
            if field not in data:
                raise StorySequenceValidationError(f"{field}: required field missing")
        raw_ids = data["ordered_scene_ids"]
        if not isinstance(raw_ids, list):
            raise StorySequenceValidationError("ordered_scene_ids: expected an array")
        return cls(
            schema_version=data["schema_version"],
            ordered_scene_ids=tuple(raw_ids),
            start_scene_id=data["start_scene_id"],
        )
