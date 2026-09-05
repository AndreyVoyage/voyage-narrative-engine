#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accepted Scene Snapshot (ASS v0) -- plain-data models.

All models are ``@dataclass(frozen=True)`` and hold only detached,
**deeply immutable** plain data. Top-level fields are frozen by the
dataclass; nested semantic structures (mappings/lists) are recursively
frozen to ``types.MappingProxyType`` (mappings) and ``tuple`` (sequences)
at construction time, so a caller can neither mutate an ASS through a
retained input reference nor through the ASS object itself. This preserves
the contract's "stored content_hash is a stable joint reference without
recomputing" guarantee.

``semantic_payload()``/``to_dict()`` always return **freshly-allocated**
plain JSON-compatible dicts/lists (via ``_to_plain``) -- mutating the
returned data never mutates the ASS, and never exposes an internal alias.

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

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional, Protocol, Tuple

from .errors import ASSInvariantError

# The legacy ASS envelope's own contract/format version. Enforced exactly on
# ``ASS`` construction so a legacy ASS can never claim ``ass/0.2``.
LEGACY_ASS_SCHEMA_VERSION = "ass/0.1"


class AcceptedSceneSnapshot:
    """Nominal base marker for the ASS v0 data model.

    Instances are always the frozen ``ASS`` dataclass below. The marker
    exists so callers and type hints can reference the concept without
    depending on field layout.
    """


class AcceptedScene(Protocol):
    """Common accepted-scene input contract shared by legacy ASS and OrderedASS.

    Downstream consumers (``services/scene_interpretation``) accept either
    concrete type through this stable anchor-field surface, avoiding ``Any``
    and avoiding a dependency on a specific schema version.
    """

    scene_id: str
    ass_id: str
    version: int
    location_id: str
    participants: Tuple["Participant", ...]
    content_hash: str


def _freeze(value: Any) -> Any:
    """Deeply convert a value into an immutable representation.

    - ``dict``/``Mapping`` -> ``MappingProxyType`` of recursively-frozen
      values (a fresh dict is built first, severing any caller alias).
    - ``list``/``tuple`` -> ``tuple`` of recursively-frozen items.
    - any other value (str/int/float/bool/None) is already immutable and is
      returned unchanged.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _to_plain(value: Any) -> Any:
    """Deeply convert a (possibly frozen) value into fresh plain data.

    Always allocates new dicts/lists; the returned structure shares no
    storage with internal ASS state, and mutating it cannot affect the ASS.
    """
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


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

    ``accepted_state`` is deeply frozen at construction (``MappingProxyType``
    recursively), so it cannot be mutated through the ASS nor through any
    retained caller input reference.
    """

    beat_id: str
    type: str
    speaker: Optional[str]
    text: str
    accepted_state: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.accepted_state is not None:
            object.__setattr__(self, "accepted_state", _freeze(self.accepted_state))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "beat_id": self.beat_id,
            "type": self.type,
            "speaker": self.speaker,
            "text": self.text,
        }
        if self.accepted_state is not None:
            result["accepted_state"] = _to_plain(self.accepted_state)
        return result


@dataclass(frozen=True)
class LocationStateOverride:
    """One accepted, scene-specific temporary fact about the location.

    Shape ``{predicate, value}`` -- e.g. ``{"predicate": "lights",
    "value": "off"}``. Never mutates permanent Location Canon
    ``fixed_features``. ``value`` is deeply frozen at construction.
    """

    predicate: str
    value: Any

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {"predicate": self.predicate, "value": _to_plain(self.value)}


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

    ``participants``/``ordered_beats``/``location_state_overrides`` are
    coerced to tuples; ``character_state_overrides`` is deeply frozen
    (recursive ``MappingProxyType``) at construction.
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

    def __post_init__(self) -> None:
        if self.schema_version != LEGACY_ASS_SCHEMA_VERSION:
            raise ASSInvariantError(
                f"ASS schema_version {self.schema_version!r} unsupported; "
                f"expected {LEGACY_ASS_SCHEMA_VERSION!r}"
            )
        object.__setattr__(self, "participants", tuple(self.participants))
        object.__setattr__(self, "ordered_beats", tuple(self.ordered_beats))
        if self.location_state_overrides is not None:
            object.__setattr__(self, "location_state_overrides", tuple(self.location_state_overrides))
        if self.character_state_overrides is not None:
            object.__setattr__(self, "character_state_overrides", _freeze(self.character_state_overrides))

    def semantic_payload(self) -> dict[str, Any]:
        """Return exactly the hashed semantic payload from the contract.

        Optional fields are omitted (not defaulted) when absent. Nested
        semantic structures are returned as fresh plain data (no aliases).
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
            payload["character_state_overrides"] = _to_plain(self.character_state_overrides)
        if self.location_state_overrides is not None:
            payload["location_state_overrides"] = [
                o.to_dict() for o in self.location_state_overrides
            ]
        return payload

    def to_dict(self) -> dict[str, Any]:
        """Return the full ASS envelope (hashed + non-hashed fields).

        Nested semantic structures are returned as fresh plain data (no
        aliases into internal ASS storage).
        """
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
            result["character_state_overrides"] = _to_plain(self.character_state_overrides)
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