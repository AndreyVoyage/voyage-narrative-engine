#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaPlan v0 -- deterministic builder.

Assembles an immutable, ordered ``MediaPlan`` from a frozen
``SceneInterpretationArtifact`` and an explicit, caller-supplied list of typed
MediaItems. It performs NO generation, NO provider calls, and NO prompt
composition.

characters_in_frame is validated at item level: every listed character must be
an exact Character Canon anchor in the upstream artifact, with no fuzzy or
case-fold matching and no duplicates per item.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Sequence

from services.scene_interpretation import SceneInterpretationArtifact

from .errors import MediaPlanValidationError, UnknownMediaKindError
from .hashing import compute_content_hash
from .model import MediaItem, MediaKind, MediaPlan, _to_plain

MEDIAPLAN_SCHEMA_VERSION = "mediaplan/0.1"

_VISUAL_KINDS = frozenset({MediaKind.IMAGE, MediaKind.VIDEO})


def _require_json_compatible(value: Any, field: str) -> None:
    try:
        json.dumps(_to_plain(value), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise MediaPlanValidationError(f"{field} is not JSON-compatible: {exc}") from exc


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise MediaPlanValidationError(f"{field}: required non-empty string")
    return value


def build_mediaplan(
    *,
    scene_interpretation: SceneInterpretationArtifact,
    media_items: Sequence[MediaItem],
) -> MediaPlan:
    """Build the immutable downstream MediaPlan.

    Exact validation rules:

    - Every media item must be a ``MediaItem`` with a known ``MediaKind``.
    - ``media_item_id`` must be non-empty and unique within this plan.
    - For IMAGE/VIDEO, ``characters_in_frame`` may contain exact character IDs
      drawn from the upstream artifact's character anchors (ordered, no
      duplicates). For AUDIO it must be empty.
    - ``planning_payload`` must be JSON-compatible.
    - Production eligibility is monotonic: it never exceeds the upstream
      artifact's ``production_eligible``.
    """

    if media_items is None:
        media_items = ()

    known_character_ids = {anchor.character_id for anchor in scene_interpretation.character_anchors}

    validated: list[MediaItem] = []
    seen_ids: set[str] = set()
    for item in media_items:
        if not isinstance(item, MediaItem):
            raise MediaPlanValidationError("media item is not a MediaItem")

        _require_json_compatible(item.planning_payload, "planning_payload")

        item_id = _require_non_empty_string(item.media_item_id, "media_item_id")
        if item_id in seen_ids:
            raise MediaPlanValidationError(f"duplicate media_item_id {item_id!r}")
        seen_ids.add(item_id)

        kind = item.media_kind
        if not isinstance(kind, MediaKind):
            raise UnknownMediaKindError(f"unknown media kind {kind!r}")

        frame = item.characters_in_frame
        if kind in _VISUAL_KINDS:
            seen_frame: set[str] = set()
            for cid in frame:
                if not isinstance(cid, str) or cid.strip() == "":
                    raise MediaPlanValidationError("characters_in_frame: empty character id")
                if cid not in known_character_ids:
                    raise MediaPlanValidationError(
                        f"character {cid!r} in frame is not a Character Canon anchor"
                    )
                if cid in seen_frame:
                    raise MediaPlanValidationError(
                        f"duplicate character {cid!r} in characters_in_frame"
                    )
                seen_frame.add(cid)
        else:
            # AUDIO must not gain visual-frame semantics.
            if frame:
                raise MediaPlanValidationError(
                    "AUDIO media items must not specify characters_in_frame"
                )

        validated.append(item)

    provisional = MediaPlan(
        schema_version=MEDIAPLAN_SCHEMA_VERSION,
        scene_id=scene_interpretation.scene_id,
        scene_interpretation_content_hash=scene_interpretation.content_hash,
        media_items=tuple(validated),
        content_hash="",
        production_eligible=scene_interpretation.production_eligible,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)