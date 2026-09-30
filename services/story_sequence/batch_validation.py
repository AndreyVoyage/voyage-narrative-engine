#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story Sequence v0 -- accepted OrderedASS batch validation.

Validates a ``StorySequence`` against the resolved accepted OrderedASS
publication batch. V0 requires EXACT coverage: ``StorySequence.ordered_scene_ids``
must be a permutation of the full resolved batch's scene-id set. The publication
batch is the full production set; the StorySequence only ORDERS it and designates
the entry -- it never selects a subset, and it never falls back to ascending
raw scene_id.

Every ordered scene_id and the ``start_scene_id`` must resolve; no accepted
scene may be silently appended, dropped, or reordered.

This module is stdlib-only and imports neither ``services.ass`` nor ``tools``;
it validates against the caller-supplied batch scene-id set.
"""

from __future__ import annotations

from typing import Iterable

from .errors import StorySequenceBatchValidationError
from .model import StorySequence


def validate_against_batch(
    story_sequence: StorySequence,
    batch_scene_ids: Iterable[str],
) -> list[str]:
    """Return the list of batch-validation violations (empty == valid).

    Requires exact coverage:
    - every ``ordered_scene_ids`` entry must be an accepted scene in the batch;
    - every accepted scene in the batch must appear in ``ordered_scene_ids``;
    - ``start_scene_id`` must be an accepted scene in the batch.

    No silent append, drop, reorder, or alphabetical fallback.
    """
    if not isinstance(story_sequence, StorySequence):
        raise StorySequenceBatchValidationError(
            "story_sequence must be a StorySequence"
        )

    batch = frozenset(batch_scene_ids)
    ordered = frozenset(story_sequence.ordered_scene_ids)

    errors: list[str] = []
    for scene_id in story_sequence.ordered_scene_ids:
        if scene_id not in batch:
            errors.append(
                f"ordered_scene_id {scene_id!r} is not an accepted scene in the batch"
            )
    for scene_id in sorted(batch):
        if scene_id not in ordered:
            errors.append(
                f"accepted scene {scene_id!r} is missing from the story sequence"
            )
    if story_sequence.start_scene_id not in batch:
        errors.append(
            f"start_scene_id {story_sequence.start_scene_id!r} "
            f"is not an accepted scene in the batch"
        )
    return errors
