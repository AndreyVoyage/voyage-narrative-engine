#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accepted Scene Snapshot (ASS v0) -- plain-data models.

All models are ``@dataclass(frozen=True)`` and contain only detached plain
data: ``dict``/``list``/``tuple``/``str``/``int``/``bool``/``None`` (or
nested frozen dataclasses composed exclusively of the same). No model ever
holds Ren'Py objects, live mutable references, open file handles, or
provider objects. Immutability is by construction (frozen dataclass),
matching the ``services/persona_gateway/models.py`` convention.

The field set is exactly the ratified ASS v0 contract:

    Hashed (semantic payload):
        scene_id, scene_title (optional), location_id, participants[],
        ordered_beats[] (including any per-beat accepted_state),
        content_rating, character_state_overrides (optional),
        location_state_overrides (optional).

    Non-hashed envelope:
        schema_version, ass_id, version, provenance, supersedes (optional),
        created_at (optional), author (optional), content_hash (the hash).

Explicitly excluded (each belongs to a named downstream object):
characters_in_frame, camera/shot/composition, visual_cue, canon_refs,
status, and any visual Canon data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


class AcceptedSceneSnapshot:
    """Nominal base marker for the ASS v0 data model.

    Instances are always the frozen ``ASS`` dataclass below. The marker
    exists so callers and type hints can reference the concept without
    depending on field layout.
    """


@dataclass(frozen=True)
class Participant:
    """One participant in the accepted scene (not "in frame").

    See OD-MA-04: ``characters_in_frame`` never lives on ASS globally; it
    belongs on MediaItem/VisualShot. ASS carries only presence.
    """

    character_id: str
    role: str
    present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "role": self.role,
            "present": self.present,
        }


@dataclass(frozen=True)
class Beat:
    """One accepted beat of narrative content, in stable order.

    ``text`` is the derived single content channel (one of speech/action/
    thought/narration). ``accepted_state`` may only ever be populated via
    an explicit caller-supplied acceptance input -- never auto-copied from
    source ``beat.emotion`` (which holds state-machine codes like
    ``"U5-выбор"``, not human-reviewable emotion).
    """

    beat_id: str
    type: str
    speaker: Optional[str]
    text: str
    accepted_state: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "beat_id": self.beat_id,
            "type": self.type,
            "speaker": self.speaker,
            "text": self.text,
        }
        if self.accepted_state is not None:
            result["accepted_state"] = self.accepted_state
        return result


@dataclass(frozen=True)
class LocationStateOverride:
    """One accepted, scene-specific temporary fact about the location.

    Shape ``{predicate, value}`` -- e.g. ``{"predicate": "lights",
    "value": "off"}``. Never mutates permanent Location Canon
    ``fixed_features``.
    """

    predicate: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"predicate": self.predicate, "value": self.value}


@dataclass(frozen=True)
class Provenance:
    """Narrative-source-only provenance. No visual Canon refs.

    ``source_ref`` is a repository-relative path (never an absolute machine
    path); ``source_hash`` is the importer-computed SHA-256 of the
    canonicalized source payload.
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
class ASS(AcceptedSceneSnapshot):
    """The immutable accepted scene snapshot.

    Construct this directly only when the caller supplies every field,
    including an already-computed ``content_hash`` (see
    ``services.ass.importer`` for the normal path, which computes it).
    """

    schema_version: str
    ass_id: str
    version: int
    scene_id: str
    location_id: str
    participants: Tuple[Participant, ...]
    ordered_beats: Tuple[Beat, ...]
    content_rating: str
    provenance: Provenance
    content_hash: str
    scene_title: Optional[str] = None
    character_state_overrides: Optional[dict[str, dict[str, Any]]] = None
    location_state_overrides: Optional[Tuple[LocationStateOverride, ...]] = None
    supersedes: Optional[str] = None
    created_at: Optional[str] = None
    author: Optional[str] = None

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload from the contract.

        Optional fields are omitted (not defaulted) when absent.
        """
        payload: dict[str, Any] = {
            "scene_id": self.scene_id,
            "location_id": self.location_id,
            "participants": [p.to_dict() for p in self.participants],
            "ordered_beats": [b.to_dict() for b in self.ordered_beats],
            "content_rating": self.content_rating,
        }
        if self.scene_title is not None:
            payload["scene_title"] = self.scene_title
        if self.character_state_overrides is not None:
            payload["character_state_overrides"] = self.character_state_overrides
        if self.location_state_overrides is not None:
            payload["location_state_overrides"] = [
                o.to_dict() for o in self.location_state_overrides
            ]
        return payload

    def to_dict(self) -> dict[str, Any]:
        """Return the full ASS envelope (hashed + non-hashed fields)."""
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ass_id": self.ass_id,
            "version": self.version,
            "scene_id": self.scene_id,
            "location_id": self.location_id,
            "participants": [p.to_dict() for p in self.participants],
            "ordered_beats": [b.to_dict() for b in self.ordered_beats],
            "content_rating": self.content_rating,
            "provenance": self.provenance.to_dict(),
            "content_hash": self.content_hash,
        }
        if self.scene_title is not None:
            result["scene_title"] = self.scene_title
        if self.character_state_overrides is not None:
            result["character_state_overrides"] = self.character_state_overrides
        if self.location_state_overrides is not None:
            result["location_state_overrides"] = [
                o.to_dict() for o in self.location_state_overrides
            ]
        if self.supersedes is not None:
            result["supersedes"] = self.supersedes
        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.author is not None:
            result["author"] = self.author
        return result