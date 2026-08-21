#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt Composer v0 -- plain-data models.

Deeply immutable, stdlib-only. Reuses the established immutability pattern:
frozen dataclasses + fresh-plain serialization.

``PromptPackage`` is the deterministic provider-neutral composition output.
``PromptItem`` is one composed item bound to a MediaPlan MediaItem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class PromptItem:
    """One composed prompt item.

    Identity is bound to the upstream ``media_item_id`` (no random prompt ID).
    ``prompt_text`` is deterministic UTF-8 text. ``characters_in_frame`` is
    preserved verbatim for visual items and empty for AUDIO.
    """

    media_item_id: str
    media_kind: str
    prompt_text: str
    characters_in_frame: Tuple[str, ...]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "characters_in_frame", tuple(self.characters_in_frame))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "media_item_id": self.media_item_id,
            "media_kind": self.media_kind,
            "prompt_text": self.prompt_text,
            "characters_in_frame": list(self.characters_in_frame),
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.semantic_payload()
        result["content_hash"] = self.content_hash
        return result


@dataclass(frozen=True)
class PromptPackage:
    """The immutable, ordered provider-neutral prompt package.

    Preserves the exact SceneInterpretationArtifact and MediaPlan content
    hashes so downstream can prove exactly what was composed.
    """

    schema_version: str
    scene_id: str
    scene_interpretation_content_hash: str
    mediaplan_content_hash: str
    prompt_items: Tuple[PromptItem, ...]
    content_hash: str
    production_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "prompt_items", tuple(self.prompt_items))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_interpretation_content_hash": self.scene_interpretation_content_hash,
            "mediaplan_content_hash": self.mediaplan_content_hash,
            "prompt_items": [item.semantic_payload() for item in self.prompt_items],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scene_id": self.scene_id,
            "scene_interpretation_content_hash": self.scene_interpretation_content_hash,
            "mediaplan_content_hash": self.mediaplan_content_hash,
            "prompt_items": [item.to_dict() for item in self.prompt_items],
            "content_hash": self.content_hash,
            "production_eligible": self.production_eligible,
        }