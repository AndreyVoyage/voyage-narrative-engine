#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Interpretation Artifact v0 -- deterministic builder.

Assembles a deeply immutable ``SceneInterpretationArtifact`` from approved
public inputs: an accepted ASS, a Location Canon location, zero or more
Character Canon snapshots, and an explicitly caller-supplied interpretation
payload.

This slice performs NO interpretation and NO provider calls. It only
validates source compatibility, freezes exact source anchors, and computes a
deterministic artifact identity.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Sequence

from services.ass import ASS
from services.character_canon_bridge import CharacterCanonSnapshot
from services.location_canon import LocationCanon

from .errors import CharacterStatusUnknownError, SceneInterpretationValidationError
from .hashing import compute_content_hash
from .model import (
    AssAnchor,
    CharacterAnchor,
    LocationAnchor,
    SceneInterpretationArtifact,
)

ARTIFACT_SCHEMA_VERSION = "scene_interpretation/0.1"

_KNOWN_STATUSES = frozenset({"PENDING_APPROVAL", "APPROVED"})
_PRODUCTION_ELIGIBLE_STATUSES = frozenset({"APPROVED"})


def _require_json_compatible(payload: Any) -> None:
    """Reject a payload that is not JSON-serializable."""
    try:
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise SceneInterpretationValidationError(
            f"interpretation_payload is not JSON-compatible: {exc}"
        ) from exc


def build_scene_interpretation_artifact(
    *,
    ass: ASS,
    location: LocationCanon,
    character_snapshots: Sequence[CharacterCanonSnapshot],
    interpretation_payload: dict[str, Any],
) -> SceneInterpretationArtifact:
    """Build the immutable scene interpretation artifact.

    Validation is exact, deterministic, and fail-closed:

    - ``ass.location_id`` must equal ``location.location_id`` exactly.
    - Each character snapshot must resolve to an exact ASS participant
      (no fuzzy/case-fold guessing) and must be unique per character_id.
    - Snapshot status must be a known value; production eligibility requires
      every included snapshot to be explicitly APPROVED.
    """

    if ass.location_id != location.location_id:
        raise SceneInterpretationValidationError(
            f"location_id mismatch: ASS {ass.location_id!r} != LocationCanon {location.location_id!r}"
        )

    _require_json_compatible(interpretation_payload)

    participant_ids = {p.character_id for p in ass.participants}

    anchors: list[CharacterAnchor] = []
    seen: set[str] = set()
    for snapshot in character_snapshots:
        status = snapshot.status
        if status not in _KNOWN_STATUSES:
            raise CharacterStatusUnknownError(
                f"unknown character Canon status {status!r} for {snapshot.character_id!r}"
            )
        if snapshot.character_id not in participant_ids:
            raise SceneInterpretationValidationError(
                f"character {snapshot.character_id!r} is not an ASS participant"
            )
        if snapshot.character_id in seen:
            raise SceneInterpretationValidationError(
                f"duplicate character snapshot for {snapshot.character_id!r}"
            )
        seen.add(snapshot.character_id)

        anchors.append(
            CharacterAnchor(
                character_id=snapshot.character_id,
                status=status,
                snapshot_content_hash=snapshot.content_hash,
                serialized_snapshot=snapshot.to_dict(),
            )
        )

    production_eligible = all(
        a.status in _PRODUCTION_ELIGIBLE_STATUSES for a in anchors
    )

    ass_anchor = AssAnchor(
        scene_id=ass.scene_id,
        ass_id=ass.ass_id,
        version=ass.version,
        content_hash=ass.content_hash,
    )
    location_anchor = LocationAnchor(
        location_id=location.location_id,
        content_hash=location.content_hash,
    )

    provisional = SceneInterpretationArtifact(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        scene_id=ass.scene_id,
        ass_anchor=ass_anchor,
        location_anchor=location_anchor,
        character_anchors=tuple(anchors),
        interpretation_payload=interpretation_payload,
        content_hash="",
        production_eligible=production_eligible,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)