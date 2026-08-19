#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accepted Scene Snapshot (ASS v0) -- scenario JSON v2 importer.

Turns an already-parsed, semantically-valid Voyage Scenario Schema V2
payload into an immutable ``ASS``. This module performs the normalization
mapping defined by the ratified ASS v0 contract:

    id -> scene_id
    name -> scene_title (optional)
    characters[] -> participants[] (id->character_id, role, present)
    location -> location_id (explicit caller input; never auto-slugged)
    beat's one non-empty content channel -> single text
    safety.content_rating -> content_rating (verbatim)
    safety's other sub-fields are NOT copied in.

The source is first validated with the shared
``tools.narrative_schema_v2.validate_scene``; any error aborts the import
(no partial import is ever produced). Duplicate ``beat_id`` is additionally
rejected at this layer (defense in depth, not relying solely on the shared
validator having run).

Normalization rules enforced here (per the Phase A1 preflight):
- ``entry_beats`` are always imported. A choice-point branch's beats are
  appended only when the caller explicitly names ``branch_id`` -- never a
  guessed/default "first branch".
- ``accepted_state`` on a beat is populated ONLY from the explicit
  ``accepted_states`` map keyed by ``beat_id``; source ``beat.emotion``
  (a state-machine code such as ``"U5-выбор"``) is NEVER auto-copied.
- Optional fields (``scene_title``, overrides, ``supersedes``,
  ``created_at``, ``author``) are omitted when absent, never defaulted to
  an invented value.

Stdlib only. No network, no provider calls, no filesystem access here.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from tools.narrative_schema_v2 import validate_scene

from .errors import ASSNormalizationError, ASSSourceError
from .hashing import compute_content_hash, compute_source_hash
from .model import (
    ASS,
    Beat,
    LocationStateOverride,
    Participant,
    Provenance,
)

# The ASS envelope's own contract/format version, distinct from the source
# schema's ``schema_version`` (which becomes provenance.source_schema_version).
ASS_SCHEMA_VERSION = "ass/0.1"

SOURCE_KIND_IMPORT = "scenario_json_v2_import"

_CONTENT_CHANNELS = ("speech", "action", "thought", "narration")


def _require_non_empty(value: Optional[str], field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ASSNormalizationError(f"{field}: required non-empty string")
    return value


def _derive_beat_text(beat: dict[str, Any], beat_id: str) -> str:
    populated = [channel for channel in _CONTENT_CHANNELS if _is_non_empty(beat.get(channel))]
    if len(populated) != 1:
        raise ASSNormalizationError(
            f"beat {beat_id}: exactly one content channel must be non-empty, got {populated}"
        )
    value = beat.get(populated[0])
    if not isinstance(value, str):
        raise ASSNormalizationError(f"beat {beat_id}: content channel {populated[0]} must be a string")
    return value


def _is_non_empty(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _collect_branch_beats(source: dict[str, Any], branch_id: str) -> list[dict[str, Any]]:
    for choice_point in source.get("choice_points", []):
        if not isinstance(choice_point, dict):
            continue
        for branch in choice_point.get("branches", []):
            if isinstance(branch, dict) and branch.get("id") == branch_id:
                beats = branch.get("beats")
                if isinstance(beats, list):
                    return [b for b in beats if isinstance(b, dict)]
                return []
    raise ASSNormalizationError(f"branch_id not found in source: {branch_id}")


def import_scene(
    source: dict[str, Any],
    *,
    ass_id: str,
    version: int,
    location_id: str,
    source_ref: str,
    source_kind: str = SOURCE_KIND_IMPORT,
    branch_id: Optional[str] = None,
    character_state_overrides: Optional[dict[str, dict[str, Any]]] = None,
    location_state_overrides: Optional[list[dict[str, Any]]] = None,
    accepted_states: Optional[dict[str, dict[str, Any]]] = None,
    supersedes: Optional[str] = None,
    created_at: Optional[str] = None,
    author: Optional[str] = None,
) -> ASS:
    """Import a validated scenario JSON v2 payload into an immutable ASS.

    ``source`` must be a parsed dict representing a Scenario Schema V2
    scene. ``location_id`` and ``source_ref`` are required explicit inputs
    (never derived automatically). ``source_ref`` must be a
    repository-relative path, never an absolute machine path.
    """
    if not isinstance(source, dict):
        raise ASSSourceError("source: expected object")

    errors, _warnings = validate_scene(source)
    if errors:
        raise ASSSourceError(
            f"source failed validation: {errors[0]}"
            + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")
        )

    ass_id = _require_non_empty(ass_id, "ass_id")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ASSNormalizationError("version: expected integer >= 1")
    location_id = _require_non_empty(location_id, "location_id")
    source_ref = _require_non_empty(source_ref, "source_ref")
    if source_ref.startswith("/") or source_ref.startswith("\\") or ":" in source_ref.split("\\")[0]:
        raise ASSNormalizationError("source_ref: must be a repository-relative path")

    scene_id = source["id"]
    scene_title = source.get("name") if _is_non_empty(source.get("name")) else None
    source_schema_version = source.get("schema_version")
    if not _is_non_empty(source_schema_version):
        source_schema_version = "2.0"

    participants = [
        Participant(
            character_id=char["id"],
            role=char.get("role") or "",
            present=bool(char.get("present")),
        )
        for char in source.get("characters", [])
        if isinstance(char, dict)
    ]

    beat_sources: list[dict[str, Any]] = [
        b for b in source.get("entry_beats", []) if isinstance(b, dict)
    ]
    if branch_id is not None:
        beat_sources.extend(_collect_branch_beats(source, branch_id))

    ordered_beats: list[Beat] = []
    seen_beat_ids: set[str] = set()
    accepted_states = accepted_states or {}
    for beat in beat_sources:
        beat_id = beat.get("beat_id")
        if not _is_non_empty(beat_id):
            raise ASSNormalizationError("beat.beat_id: required non-empty string")
        if beat_id in seen_beat_ids:
            raise ASSNormalizationError(f"duplicate beat_id at ASS layer: {beat_id}")
        seen_beat_ids.add(beat_id)

        text = _derive_beat_text(beat, beat_id)
        accepted_state = accepted_states.get(beat_id)
        ordered_beats.append(
            Beat(
                beat_id=beat_id,
                type=beat.get("type") or "",
                speaker=beat.get("speaker"),
                text=text,
                accepted_state=accepted_state if isinstance(accepted_state, dict) else None,
            )
        )

    safety = source.get("safety")
    content_rating = ""
    if isinstance(safety, dict) and _is_non_empty(safety.get("content_rating")):
        content_rating = safety["content_rating"]

    loc_overrides: tuple[LocationStateOverride, ...] = ()
    if location_state_overrides is not None:
        normalized_overrides: list[LocationStateOverride] = []
        for item in location_state_overrides:
            if not isinstance(item, dict):
                raise ASSNormalizationError("location_state_overrides: each item must be an object")
            predicate = _require_non_empty(item.get("predicate"), "location_state_overrides[].predicate")
            normalized_overrides.append(LocationStateOverride(predicate=predicate, value=item.get("value")))
        loc_overrides = tuple(normalized_overrides)

    provenance = Provenance(
        source_kind=source_kind,
        source_ref=source_ref,
        source_hash=compute_source_hash(source),
        source_schema_version=source_schema_version,
    )

    provisional = ASS(
        schema_version=ASS_SCHEMA_VERSION,
        ass_id=ass_id,
        version=version,
        scene_id=scene_id,
        location_id=location_id,
        participants=tuple(participants),
        ordered_beats=tuple(ordered_beats),
        content_rating=content_rating,
        provenance=provenance,
        content_hash="",
        scene_title=scene_title,
        character_state_overrides=character_state_overrides,
        location_state_overrides=loc_overrides,
        supersedes=supersedes,
        created_at=created_at,
        author=author,
    )

    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)