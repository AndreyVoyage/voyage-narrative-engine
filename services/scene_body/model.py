#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Body v1 -- the single editable authoring payload for the Scene Editor.

``SceneBody`` is the ONE authoritative ordered body authored in the Editor. It
is the editable/history artifact; the canonical accepted contract remains ASS
(``services.ass``). Acceptance deterministically projects a complete SceneBody
into an OrderedASS (``ass/0.2``) without semantic loss.

All value types are ``@dataclass(frozen=True)`` and hold only detached, deeply
immutable plain data. Mappings are frozen to ``types.MappingProxyType`` and
sequences to ``tuple`` at construction, so neither a caller-retained input
reference nor the object itself can be mutated. ``to_dict()`` always returns
freshly-allocated plain JSON-compatible data and is deterministic.

Two independent boundaries are kept strictly separate:

- **Model validity** (enforced here, at construction): exact schema version,
  primitive/container structure, deep immutability, non-empty stable scene_id,
  unique entry_id / option_id, recognized discriminators, and impossible field
  combinations (e.g. ``CLEAR + asset_id``). Incomplete authoring is permitted.
- **Acceptance completeness** (``services/scene_body/validation.py``): the
  player-relevant gates required before projection into OrderedASS.

This module is self-contained (stdlib only) and does not import ``services.ass``
or ``tools``, keeping a clean one-way dependency: ASS -> scene_body.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Optional, Tuple

AUTHORING_SCHEMA_VERSION = "scene_body/1.0"

# ---------------------------------------------------------------------------
# Recognized discriminators
# ---------------------------------------------------------------------------

ENTRY_KIND_TEXT = "TEXT"
ENTRY_KIND_CHOICE = "CHOICE"
ENTRY_KIND_VISUAL_CHANGE = "VISUAL_CHANGE"

TEXT_PRESENTATION_NARRATIVE = "NARRATIVE"
TEXT_PRESENTATION_DIALOGUE = "DIALOGUE"
TEXT_PRESENTATION_THOUGHT = "THOUGHT"
TEXT_PRESENTATIONS = (
    TEXT_PRESENTATION_NARRATIVE,
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_THOUGHT,
)

# Reuse the existing Scenario V2 thought-visibility semantic values verbatim
# (``tools.narrative_schema_v2.THOUGHT_VISIBILITY``). Scenario V2 is unchanged.
THOUGHT_VISIBILITY_HIDDEN = "hidden"
THOUGHT_VISIBILITY_REVEALED = "revealed"
THOUGHT_VISIBILITY_ALWAYS = "always"
THOUGHT_VISIBILITIES = (
    THOUGHT_VISIBILITY_HIDDEN,
    THOUGHT_VISIBILITY_REVEALED,
    THOUGHT_VISIBILITY_ALWAYS,
)

VISUAL_OP_SET = "SET"
VISUAL_OP_CLEAR = "CLEAR"
VISUAL_OPS = (VISUAL_OP_SET, VISUAL_OP_CLEAR)

TARGET_KIND_ENTRY = "ENTRY"
TARGET_KIND_SCENE = "SCENE"
TARGET_KINDS = (TARGET_KIND_ENTRY, TARGET_KIND_SCENE)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SceneBodyError(Exception):
    """Root of the scene_body exception hierarchy."""


class SceneBodyValidationError(SceneBodyError):
    """Raised on a MODEL-validity violation (structure, schema, discriminator,
    IDs, impossible field combinations). Distinct from acceptance completeness."""


class SceneBodyAcceptanceError(SceneBodyError):
    """Raised when an acceptance-completeness boundary is violated."""


# ---------------------------------------------------------------------------
# Freeze / plain helpers (mirrors the repo-wide immutability house style)
# ---------------------------------------------------------------------------

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


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise SceneBodyValidationError(f"{field}: required non-empty string")
    return value


def _require_optional_string(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SceneBodyValidationError(f"{field}: expected string or None")
    return value


# ---------------------------------------------------------------------------
# Entry value types
# ---------------------------------------------------------------------------

class Entry:
    """Nominal base marker for ordered scene-body entries.

    Concrete entries are ``TextEntry`` / ``ChoiceEntry`` /
    ``VisualChangeEvent`` (and, in a later slice, ``CharacterStateEvent``).
    """


@dataclass(frozen=True)
class Participant:
    """One authored participant (character presence) in the scene."""

    character_id: str
    role: str = ""
    present: bool = True

    def __post_init__(self) -> None:
        _require_non_empty_string(self.character_id, "participant.character_id")
        if not isinstance(self.role, str):
            raise SceneBodyValidationError("participant.role: expected string")
        if not isinstance(self.present, bool):
            raise SceneBodyValidationError("participant.present: expected bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "role": self.role,
            "present": self.present,
        }


@dataclass(frozen=True)
class TextEntry(Entry):
    """An authored text entry (NARRATIVE / DIALOGUE / THOUGHT)."""

    entry_id: str
    presentation: str
    text: str
    character_id: Optional[str] = None
    thought_visibility: Optional[str] = None
    kind: str = field(init=False, default=ENTRY_KIND_TEXT, repr=True)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.entry_id, "text_entry.entry_id")
        if self.presentation not in TEXT_PRESENTATIONS:
            raise SceneBodyValidationError(
                f"text_entry.presentation: expected one of {TEXT_PRESENTATIONS!r}"
            )
        if not isinstance(self.text, str):
            raise SceneBodyValidationError("text_entry.text: expected string")
        _require_optional_string(self.character_id, "text_entry.character_id")
        _require_optional_string(self.thought_visibility, "text_entry.thought_visibility")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "presentation": self.presentation,
            "text": self.text,
            "character_id": self.character_id,
            "thought_visibility": self.thought_visibility,
        }


@dataclass(frozen=True)
class ChoiceTarget:
    """A stable choice-option target: an entry inside this body, or another scene."""

    target_kind: str
    target_id: str

    def __post_init__(self) -> None:
        if self.target_kind not in TARGET_KINDS:
            raise SceneBodyValidationError(
                f"choice_target.target_kind: expected one of {TARGET_KINDS!r}"
            )
        _require_non_empty_string(self.target_id, "choice_target.target_id")

    def to_dict(self) -> dict[str, Any]:
        return {"target_kind": self.target_kind, "target_id": self.target_id}


@dataclass(frozen=True)
class ChoiceOption:
    """One ordered option of a ChoiceEntry."""

    option_id: str
    display_text: str
    target: Optional[ChoiceTarget] = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.option_id, "choice_option.option_id")
        if not isinstance(self.display_text, str):
            raise SceneBodyValidationError("choice_option.display_text: expected string")
        if self.target is not None and not isinstance(self.target, ChoiceTarget):
            raise SceneBodyValidationError("choice_option.target: expected ChoiceTarget or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "display_text": self.display_text,
            "target": self.target.to_dict() if self.target is not None else None,
        }


@dataclass(frozen=True)
class ChoiceEntry(Entry):
    """An authored choice point with an ordered option list."""

    entry_id: str
    prompt: Optional[str] = None
    options: Tuple[ChoiceOption, ...] = ()
    kind: str = field(init=False, default=ENTRY_KIND_CHOICE, repr=True)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.entry_id, "choice_entry.entry_id")
        _require_optional_string(self.prompt, "choice_entry.prompt")
        object.__setattr__(self, "options", tuple(self.options))
        for option in self.options:
            if not isinstance(option, ChoiceOption):
                raise SceneBodyValidationError("choice_entry.options: expected ChoiceOption")

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "prompt": self.prompt,
            "options": [o.to_dict() for o in self.options],
        }


@dataclass(frozen=True)
class VisualChangeEvent(Entry):
    """An ordered visual change (SET or CLEAR) with an optional transition."""

    entry_id: str
    operation: str
    asset_id: Optional[str] = None
    transition: Optional[str] = None
    kind: str = field(init=False, default=ENTRY_KIND_VISUAL_CHANGE, repr=True)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.entry_id, "visual_entry.entry_id")
        if self.operation not in VISUAL_OPS:
            raise SceneBodyValidationError(
                f"visual_entry.operation: expected one of {VISUAL_OPS!r}"
            )
        _require_optional_string(self.asset_id, "visual_entry.asset_id")
        _require_optional_string(self.transition, "visual_entry.transition")
        if self.transition is not None and self.transition == "":
            raise SceneBodyValidationError("visual_entry.transition: must be non-empty if present")
        if self.operation == VISUAL_OP_CLEAR and self.asset_id is not None:
            raise SceneBodyValidationError(
                "visual_entry: CLEAR must not carry an asset_id (structurally invalid)"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "operation": self.operation,
            "asset_id": self.asset_id,
            "transition": self.transition,
        }


@dataclass(frozen=True)
class LocationStateOverride:
    """One authored scene-specific temporary fact about the location."""

    predicate: str
    value: Any

    def __post_init__(self) -> None:
        _require_non_empty_string(self.predicate, "location_state_override.predicate")
        object.__setattr__(self, "value", _freeze(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {"predicate": self.predicate, "value": _to_plain(self.value)}


# Recognized concrete entry types (single ordered-entry vocabulary). Adding a
# future ``CHARACTER_STATE`` entry type only requires appending it here.
ENTRY_TYPES = (TextEntry, ChoiceEntry, VisualChangeEvent)


# ---------------------------------------------------------------------------
# SceneBody
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SceneBody:
    """The single authoritative editable ordered body for a scene."""

    authoring_schema_version: str
    scene_id: str
    participants: Tuple[Participant, ...]
    entries: Tuple[Entry, ...]
    scene_title: Optional[str] = None
    location_id: Optional[str] = None
    content_rating: Optional[str] = None
    character_state_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None
    location_state_overrides: Optional[Tuple[LocationStateOverride, ...]] = None

    def __post_init__(self) -> None:
        if self.authoring_schema_version != AUTHORING_SCHEMA_VERSION:
            raise SceneBodyValidationError(
                f"authoring_schema_version {self.authoring_schema_version!r} unsupported; "
                f"expected {AUTHORING_SCHEMA_VERSION!r}"
            )
        _require_non_empty_string(self.scene_id, "scene_id")
        _require_optional_string(self.scene_title, "scene_title")
        _require_optional_string(self.location_id, "location_id")
        _require_optional_string(self.content_rating, "content_rating")

        participants = tuple(self.participants)
        for p in participants:
            if not isinstance(p, Participant):
                raise SceneBodyValidationError("participants: expected Participant")
        object.__setattr__(self, "participants", participants)

        entries = tuple(self.entries)
        for e in entries:
            if not isinstance(e, ENTRY_TYPES):
                raise SceneBodyValidationError("entries: unrecognized entry type")
        object.__setattr__(self, "entries", entries)

        if self.character_state_overrides is not None:
            if not isinstance(self.character_state_overrides, Mapping):
                raise SceneBodyValidationError("character_state_overrides: expected object or None")
            object.__setattr__(self, "character_state_overrides", _freeze(self.character_state_overrides))
        if self.location_state_overrides is not None:
            overrides = tuple(self.location_state_overrides)
            for o in overrides:
                if not isinstance(o, LocationStateOverride):
                    raise SceneBodyValidationError("location_state_overrides: expected LocationStateOverride")
            object.__setattr__(self, "location_state_overrides", overrides)

        # Stable ID uniqueness invariants (across the whole body).
        seen_entry_ids: set[str] = set()
        seen_option_ids: set[str] = set()
        for e in entries:
            if e.entry_id in seen_entry_ids:
                raise SceneBodyValidationError(f"duplicate entry_id: {e.entry_id!r}")
            seen_entry_ids.add(e.entry_id)
            if isinstance(e, ChoiceEntry):
                for option in e.options:
                    if option.option_id in seen_option_ids:
                        raise SceneBodyValidationError(f"duplicate option_id: {option.option_id!r}")
                    seen_option_ids.add(option.option_id)

    # ------------------------------------------------------------------ ids

    def entry_ids(self) -> frozenset[str]:
        return frozenset(e.entry_id for e in self.entries)

    def participant_ids(self) -> frozenset[str]:
        return frozenset(p.character_id for p in self.participants)

    # ------------------------------------------------------------ plain data

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical plain dict (all fields, explicit nulls, ordered)."""
        return {
            "authoring_schema_version": self.authoring_schema_version,
            "scene_id": self.scene_id,
            "scene_title": self.scene_title,
            "location_id": self.location_id,
            "participants": [p.to_dict() for p in self.participants],
            "content_rating": self.content_rating,
            "character_state_overrides": (
                _to_plain(self.character_state_overrides)
                if self.character_state_overrides is not None
                else None
            ),
            "location_state_overrides": (
                [o.to_dict() for o in self.location_state_overrides]
                if self.location_state_overrides is not None
                else None
            ),
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "SceneBody":
        """Build a SceneBody from persisted plain dict data (fail closed)."""
        if not isinstance(data, dict):
            raise SceneBodyValidationError("SceneBody must be an object")

        raw_participants = data.get("participants")
        if not isinstance(raw_participants, list):
            raise SceneBodyValidationError("participants: expected array")
        participants = tuple(_participant_from_dict(p) for p in raw_participants)

        raw_entries = data.get("entries")
        if not isinstance(raw_entries, list):
            raise SceneBodyValidationError("entries: expected array")
        entries = tuple(_entry_from_dict(e) for e in raw_entries)

        raw_loc_overrides = data.get("location_state_overrides")
        location_state_overrides = None
        if raw_loc_overrides is not None:
            if not isinstance(raw_loc_overrides, list):
                raise SceneBodyValidationError("location_state_overrides: expected array or null")
            location_state_overrides = tuple(_location_override_from_dict(o) for o in raw_loc_overrides)

        return cls(
            authoring_schema_version=data.get("authoring_schema_version"),
            scene_id=data.get("scene_id"),
            participants=participants,
            entries=entries,
            scene_title=data.get("scene_title"),
            location_id=data.get("location_id"),
            content_rating=data.get("content_rating"),
            character_state_overrides=data.get("character_state_overrides"),
            location_state_overrides=location_state_overrides,
        )


def _participant_from_dict(data: Any) -> Participant:
    if not isinstance(data, dict):
        raise SceneBodyValidationError("participant: expected object")
    return Participant(
        character_id=data.get("character_id"),
        role=data.get("role", ""),
        present=data.get("present", True),
    )


def _location_override_from_dict(data: Any) -> LocationStateOverride:
    if not isinstance(data, dict):
        raise SceneBodyValidationError("location_state_override: expected object")
    return LocationStateOverride(predicate=data.get("predicate"), value=data.get("value"))


def _target_from_dict(data: Any) -> ChoiceTarget:
    if not isinstance(data, dict):
        raise SceneBodyValidationError("choice target: expected object")
    return ChoiceTarget(target_kind=data.get("target_kind"), target_id=data.get("target_id"))


def _option_from_dict(data: Any) -> ChoiceOption:
    if not isinstance(data, dict):
        raise SceneBodyValidationError("choice option: expected object")
    raw_target = data.get("target")
    return ChoiceOption(
        option_id=data.get("option_id"),
        display_text=data.get("display_text", ""),
        target=_target_from_dict(raw_target) if raw_target is not None else None,
    )


def _entry_from_dict(data: Any) -> Entry:
    if not isinstance(data, dict):
        raise SceneBodyValidationError("entry: expected object")
    kind = data.get("kind")
    if kind == ENTRY_KIND_TEXT:
        return TextEntry(
            entry_id=data.get("entry_id"),
            presentation=data.get("presentation"),
            text=data.get("text", ""),
            character_id=data.get("character_id"),
            thought_visibility=data.get("thought_visibility"),
        )
    if kind == ENTRY_KIND_CHOICE:
        raw_options = data.get("options", [])
        if not isinstance(raw_options, list):
            raise SceneBodyValidationError("choice_entry.options: expected array")
        return ChoiceEntry(
            entry_id=data.get("entry_id"),
            prompt=data.get("prompt"),
            options=tuple(_option_from_dict(o) for o in raw_options),
        )
    if kind == ENTRY_KIND_VISUAL_CHANGE:
        return VisualChangeEvent(
            entry_id=data.get("entry_id"),
            operation=data.get("operation"),
            asset_id=data.get("asset_id"),
            transition=data.get("transition"),
        )
    raise SceneBodyValidationError(f"unknown entry kind: {kind!r}")
