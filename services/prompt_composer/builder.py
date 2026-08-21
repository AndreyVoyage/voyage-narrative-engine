#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt Composer v0 -- deterministic builder.

Transforms an already-frozen SceneInterpretationArtifact and MediaPlan into a
provider-neutral, byte-deterministic PromptPackage. It performs NO provider
call, NO LLM call, NO creative inference, and NO media generation.

Visual items include frozen Character Canon snapshot material ONLY for the
characters listed in that item's characters_in_frame. AUDIO items gain no
visual-frame semantics.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from typing import Any

from services.mediaplan import MediaItem, MediaKind, MediaPlan
from services.scene_interpretation import SceneInterpretationArtifact

from .errors import PromptComposerValidationError
from .hashing import compute_content_hash
from .model import PromptItem, PromptPackage

PROMPT_PACKAGE_SCHEMA_VERSION = "prompt_composer/0.1"

_VISUAL_KINDS = {MediaKind.IMAGE, MediaKind.VIDEO}

_SECTION_SEP = "\n\n"


def _to_plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _compact_json(value: Any) -> str:
    return json.dumps(_to_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _build_prompt_text(
    item: MediaItem,
    interpretation_payload: Mapping[str, Any],
    anchors_by_id: dict[str, Any],
) -> str:
    kind = item.media_kind.value
    sections: list[str] = [
        "[MEDIA]",
        f"kind={kind}",
        f"item_id={item.media_item_id}",
    ]
    sections.append("[SCENE INTERPRETATION]")
    sections.append(_compact_json(interpretation_payload))

    if item.media_kind in _VISUAL_KINDS:
        frame = list(item.characters_in_frame)
        sections.append("[CHARACTERS IN FRAME]")
        sections.append(_compact_json(frame))
        sections.append("[CHARACTER CANON SNAPSHOTS]")
        snapshots = [anchors_by_id[cid] for cid in item.characters_in_frame]
        sections.append(_compact_json(snapshots))

    sections.append("[MEDIA PLAN]")
    sections.append(_compact_json(item.planning_payload))

    if item.source_refs:
        sections.append("[SOURCE REFERENCES]")
        sections.append(_compact_json(item.source_refs))

    return _SECTION_SEP.join(sections)


def build_prompt_package(
    *,
    scene_interpretation: SceneInterpretationArtifact,
    mediaplan: MediaPlan,
) -> PromptPackage:
    """Compose the deterministic provider-neutral PromptPackage.

    Validation (fail closed):

    - scene ids must match.
    - mediaplan.scene_interpretation_content_hash must equal
      scene_interpretation.content_hash.
    - if scene_interpretation is not production eligible, the MediaPlan must
      not claim production eligibility (never promote upstream state).
    - every visual item's characters_in_frame must be an exact known Character
      Canon anchor in the frozen interpretation.
    """

    if scene_interpretation.scene_id != mediaplan.scene_id:
        raise PromptComposerValidationError(
            f"scene_id mismatch: interpretation {scene_interpretation.scene_id!r} vs mediaplan {mediaplan.scene_id!r}"
        )

    if mediaplan.scene_interpretation_content_hash != scene_interpretation.content_hash:
        raise PromptComposerValidationError(
            "mediaplan scene_interpretation_content_hash does not match interpretation content_hash"
        )

    if not scene_interpretation.production_eligible and mediaplan.production_eligible:
        raise PromptComposerValidationError(
            "mediaplan claims production eligibility while interpretation is not production eligible"
        )

    anchors_by_id: dict[str, Any] = {}
    for anchor in scene_interpretation.character_anchors:
        anchors_by_id[anchor.character_id] = anchor.to_dict()

    # Validate visual frames against known anchors (exact IDs, no fuzzy match).
    for item in mediaplan.media_items:
        if item.media_kind in _VISUAL_KINDS:
            for cid in item.characters_in_frame:
                if cid not in anchors_by_id:
                    raise PromptComposerValidationError(
                        f"character {cid!r} in frame is not a frozen Character Canon anchor"
                    )

    prompt_items: list[PromptItem] = []
    for item in mediaplan.media_items:
        prompt_text = _build_prompt_text(
            item,
            _to_plain(scene_interpretation.interpretation_payload),
            anchors_by_id,
        )
        prompt_item = PromptItem(
            media_item_id=item.media_item_id,
            media_kind=item.media_kind.value,
            prompt_text=prompt_text,
            characters_in_frame=tuple(item.characters_in_frame),
            content_hash="",
        )
        item_hash = compute_content_hash(prompt_item.semantic_payload())
        prompt_items.append(dataclasses.replace(prompt_item, content_hash=item_hash))

    provisional = PromptPackage(
        schema_version=PROMPT_PACKAGE_SCHEMA_VERSION,
        scene_id=scene_interpretation.scene_id,
        scene_interpretation_content_hash=scene_interpretation.content_hash,
        mediaplan_content_hash=mediaplan.content_hash,
        prompt_items=tuple(prompt_items),
        content_hash="",
        production_eligible=mediaplan.production_eligible,
    )
    package_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=package_hash)