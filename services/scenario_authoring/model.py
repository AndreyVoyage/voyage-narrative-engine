#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.1) -- pure, UI-independent plain-data models.

Agreed product structure (OD-SE-AUTHORING-MODEL-01)::

    PROJECT -> CONNECTED CARDS -> SLIDES -> CONTENT ITEMS / UTTERANCES -> DISPLAY PORTIONS

This is an additive, editable authoring layer. A Card is an author's editable
container and is deliberately NOT automatically equal to one SceneBody,
OrderedASS or Ren'Py scene. No accepted ASS contract is modified (existing
``scene_body/1.0``, ``ass/0.2`` and ``vne_story_sequence/0.1`` stay unchanged);
no Card-to-OrderedASS projection is implemented here (that is SE-1.3).

All types are ``@dataclass(frozen=True)`` holding only detached plain data
(sequences frozen to ``tuple``). Identity is always an explicit stable ID,
never a filesystem path, visual position or list index: moving content keeps
identity, copying requires a fresh ID, reordering never mutates identity.

Self-contained (stdlib only); never imports an existing service or the exporter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator, Optional, Tuple

from .errors import ScenarioAuthoringValidationError

# Working technical-draft schema id for the in-memory authoring model. NOT a
# ratified storage/package contract; does not claim ``.vscenario`` is implemented.
SCENARIO_AUTHORING_SCHEMA_VERSION = "scenario_authoring/0.1"

# Content item kinds (minimal typed distinction; no rendering/playback).
CONTENT_KIND_TEXT = "TEXT"
CONTENT_KIND_CHOICE = "CHOICE"
CONTENT_KIND_MEDIA = "MEDIA"
CONTENT_KINDS: Tuple[str, ...] = (CONTENT_KIND_TEXT, CONTENT_KIND_CHOICE, CONTENT_KIND_MEDIA)

# Character Library boundary (reserved minimal provenance; no .vchar import here).
CHARACTER_PROVENANCE_MANUAL = "MANUAL"
CHARACTER_PROVENANCE_CHARACTER_LAB_VCHAR = "CHARACTER_LAB_VCHAR"
CHARACTER_PROVENANCES: Tuple[str, ...] = (
    CHARACTER_PROVENANCE_MANUAL,
    CHARACTER_PROVENANCE_CHARACTER_LAB_VCHAR,
)

# Mirrors the existing lowercase-slug stable-ID convention
# (tools.visual_asset_registry.ASSET_ID_RE / workspace_project.PROJECT_ID_RE).
STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _require_stable_id(value: Any, field: str) -> str:
    """Validate a stable id; never silently normalizes it."""
    if not isinstance(value, str) or not STABLE_ID_RE.match(value):
        raise ScenarioAuthoringValidationError(
            f"{field}: expected a stable id matching ^[a-z][a-z0-9_]{{2,63}}$"
        )
    return value


def _require_non_empty_string(value: Any, field: str) -> str:
    """Validate a required non-empty, untrimmed string (fail closed)."""
    if not isinstance(value, str) or value == "":
        raise ScenarioAuthoringValidationError(f"{field}: required non-empty string")
    if value.strip() != value:
        raise ScenarioAuthoringValidationError(
            f"{field}: must not have leading/trailing whitespace"
        )
    return value


def _require_non_blank_string(value: Any, field: str) -> str:
    """Validate a required non-blank string, preserving the exact authored text.

    Unlike :func:`_require_non_empty_string`, surrounding whitespace is allowed
    and preserved (literary content is never silently stripped or normalized);
    only a value that is not a string or that consists solely of whitespace
    fails.
    """
    if not isinstance(value, str) or not value.strip():
        raise ScenarioAuthoringValidationError(f"{field}: required non-blank string")
    return value


def _is_safe_relative_path(value: Any) -> bool:
    """True if ``value`` is a portable, forward-slash, traversal-free relative path."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    if "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)

@dataclass(frozen=True)
class MediaReference:
    """A stable media reference, never a machine-specific absolute path.

    Exactly one of ``asset_id`` (stable registry id) or ``relative_path``
    (portable project-relative path) must be supplied.
    """

    asset_id: Optional[str] = None
    relative_path: Optional[str] = None

    def __post_init__(self) -> None:
        has_asset = self.asset_id is not None
        has_path = self.relative_path is not None
        if has_asset == has_path:
            raise ScenarioAuthoringValidationError(
                "MediaReference: exactly one of asset_id / relative_path must be set"
            )
        if has_asset:
            _require_stable_id(self.asset_id, "MediaReference.asset_id")
        elif not _is_safe_relative_path(self.relative_path):
            raise ScenarioAuthoringValidationError(
                "MediaReference.relative_path: must be a safe relative path "
                "(forward slashes, no traversal, no absolute/backslash path)"
            )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.asset_id is not None:
            result["asset_id"] = self.asset_id
        if self.relative_path is not None:
            result["relative_path"] = self.relative_path
        return result


@dataclass(frozen=True)
class SpeakerOverride:
    """Optional per-speaker portrait/emotion override for one Display Portion.

    ``character_id`` must reference a declared speaker of the owning Utterance.
    ``emotion`` is an opaque non-empty string (the standardized named emotion
    catalog is NOT ratified).
    """

    character_id: str
    portrait: Optional[MediaReference] = None
    emotion: Optional[str] = None

    def __post_init__(self) -> None:
        _require_stable_id(self.character_id, "SpeakerOverride.character_id")
        if self.portrait is not None and not isinstance(self.portrait, MediaReference):
            raise ScenarioAuthoringValidationError(
                "SpeakerOverride.portrait: expected MediaReference"
            )
        if self.emotion is not None:
            _require_non_empty_string(self.emotion, "SpeakerOverride.emotion")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"character_id": self.character_id}
        if self.portrait is not None:
            result["portrait"] = self.portrait.to_dict()
        if self.emotion is not None:
            result["emotion"] = self.emotion
        return result


@dataclass(frozen=True)
class DisplayPortion:
    """One reader-facing segment belonging to exactly one Utterance.

    A portion is an **offset range into the authoritative whole Utterance
    text**; it never duplicates or replaces that text. Ordering and non-overlap
    are validated at the Utterance level.
    """

    portion_id: str
    start_offset: int
    end_offset: int
    overrides: Tuple[SpeakerOverride, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.portion_id, "DisplayPortion.portion_id")
        if not isinstance(self.start_offset, int) or isinstance(self.start_offset, bool):
            raise ScenarioAuthoringValidationError("DisplayPortion.start_offset: expected int")
        if not isinstance(self.end_offset, int) or isinstance(self.end_offset, bool):
            raise ScenarioAuthoringValidationError("DisplayPortion.end_offset: expected int")
        if self.start_offset < 0:
            raise ScenarioAuthoringValidationError("DisplayPortion.start_offset: must be >= 0")
        if self.end_offset <= self.start_offset:
            raise ScenarioAuthoringValidationError(
                "DisplayPortion.end_offset: must be > start_offset"
            )
        overrides = tuple(self.overrides)
        object.__setattr__(self, "overrides", overrides)
        seen: dict[str, int] = {}
        for index, override in enumerate(overrides):
            if not isinstance(override, SpeakerOverride):
                raise ScenarioAuthoringValidationError(
                    f"DisplayPortion.overrides[{index}]: expected SpeakerOverride"
                )
            if override.character_id in seen:
                raise ScenarioAuthoringValidationError(
                    f"DisplayPortion.overrides: duplicate character_id {override.character_id!r}"
                )
            seen[override.character_id] = index

    def to_dict(self) -> dict[str, Any]:
        return {
            "portion_id": self.portion_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "overrides": [o.to_dict() for o in self.overrides],
        }

@dataclass(frozen=True)
class Utterance:
    """One complete, authoritative author-authored text (never auto-split).

    ``text`` is the single source of truth. ``speaker_ids`` holds zero or more
    stable character references (zero = narrative; 1+ = dialogue/group). The AI
    dialogue context is always based on the complete ``text``, never on isolated
    Display Portions.

    ``portions``, when non-empty, is an **explicit complete segmentation** of
    ``text``: ordered, non-overlapping, exactly covering ``[0, len(text))``.
    Invalid/stale ranges are rejected (never silently repaired).
    """

    utterance_id: str
    text: str
    speaker_ids: Tuple[str, ...] = ()
    portions: Tuple[DisplayPortion, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.utterance_id, "Utterance.utterance_id")
        if not isinstance(self.text, str):
            raise ScenarioAuthoringValidationError("Utterance.text: expected str")

        speaker_ids = tuple(self.speaker_ids)
        object.__setattr__(self, "speaker_ids", speaker_ids)
        speaker_set: dict[str, int] = {}
        for index, sid in enumerate(speaker_ids):
            _require_stable_id(sid, f"Utterance.speaker_ids[{index}]")
            if sid in speaker_set:
                raise ScenarioAuthoringValidationError(
                    f"Utterance.speaker_ids: duplicate {sid!r}"
                )
            speaker_set[sid] = index

        portions = tuple(self.portions)
        object.__setattr__(self, "portions", portions)
        self._validate_segmentation(portions, len(self.text), speaker_set)

    def _validate_segmentation(
        self,
        portions: Tuple[DisplayPortion, ...],
        text_len: int,
        speaker_set: dict[str, int],
    ) -> None:
        seen: dict[str, int] = {}
        previous_end = 0
        for index, portion in enumerate(portions):
            if not isinstance(portion, DisplayPortion):
                raise ScenarioAuthoringValidationError(
                    f"Utterance.portions[{index}]: expected DisplayPortion"
                )
            if portion.portion_id in seen:
                raise ScenarioAuthoringValidationError(
                    f"Utterance.portions: duplicate portion_id {portion.portion_id!r}"
                )
            seen[portion.portion_id] = index
            if portion.start_offset < 0 or portion.end_offset > text_len:
                raise ScenarioAuthoringValidationError(
                    f"Utterance.portions[{index}] {portion.portion_id!r}: offsets "
                    f"[{portion.start_offset}, {portion.end_offset}) out of text bounds "
                    f"[0, {text_len})"
                )
            if portion.start_offset != previous_end:
                raise ScenarioAuthoringValidationError(
                    f"Utterance.portions[{index}] {portion.portion_id!r}: start_offset "
                    f"{portion.start_offset} does not follow previous end {previous_end} "
                    f"(overlap or gap)"
                )
            previous_end = portion.end_offset
            for override in portion.overrides:
                if override.character_id not in speaker_set:
                    raise ScenarioAuthoringValidationError(
                        f"Utterance.portions[{index}] {portion.portion_id!r}: override "
                        f"speaker {override.character_id!r} is not a declared utterance speaker"
                    )
        if portions and previous_end != text_len:
            raise ScenarioAuthoringValidationError(
                f"Utterance.portions: segmentation ends at {previous_end}, "
                f"expected full text coverage {text_len}"
            )

    def whole_text(self) -> str:
        """The authoritative whole utterance text (never segmented away)."""
        return self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "utterance_id": self.utterance_id,
            "text": self.text,
            "speaker_ids": list(self.speaker_ids),
            "portions": [p.to_dict() for p in self.portions],
        }

@dataclass(frozen=True)
class ChoiceOption:
    """One explicit author-authored branch option inside an AuthoredChoice.

    ``target_connection_id`` may reference a Card connection (validated at the
    project level); a branch is always an explicit author choice, never inferred.
    """

    option_id: str
    label: str
    target_connection_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_stable_id(self.option_id, "ChoiceOption.option_id")
        _require_non_blank_string(self.label, "ChoiceOption.label")
        if self.target_connection_id is not None:
            _require_stable_id(self.target_connection_id, "ChoiceOption.target_connection_id")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"option_id": self.option_id, "label": self.label}
        if self.target_connection_id is not None:
            result["target_connection_id"] = self.target_connection_id
        return result


@dataclass(frozen=True)
class AuthoredChoice:
    """One author-authored reader choice with an ordered set of options."""

    choice_id: str
    prompt: str = ""
    options: Tuple[ChoiceOption, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.choice_id, "AuthoredChoice.choice_id")
        _require_non_blank_string(self.prompt, "AuthoredChoice.prompt")
        options = tuple(self.options)
        object.__setattr__(self, "options", options)
        seen: dict[str, int] = {}
        for index, option in enumerate(options):
            if not isinstance(option, ChoiceOption):
                raise ScenarioAuthoringValidationError(
                    f"AuthoredChoice.options[{index}]: expected ChoiceOption"
                )
            if option.option_id in seen:
                raise ScenarioAuthoringValidationError(
                    f"AuthoredChoice.options: duplicate option_id {option.option_id!r}"
                )
            seen[option.option_id] = index

    def to_dict(self) -> dict[str, Any]:
        return {
            "choice_id": self.choice_id,
            "prompt": self.prompt,
            "options": [o.to_dict() for o in self.options],
        }


@dataclass(frozen=True)
class ContentItem:
    """One authoring content element with the minimal typed distinction.

    ``kind`` is one of TEXT (carries an ``Utterance``), CHOICE (carries an
    ``AuthoredChoice``) or MEDIA (carries a ``MediaReference``). Exactly the
    payload matching the kind must be present. No rendering or playback.
    """

    item_id: str
    kind: str
    utterance: Optional[Utterance] = None
    choice: Optional[AuthoredChoice] = None
    media: Optional[MediaReference] = None

    def __post_init__(self) -> None:
        _require_stable_id(self.item_id, "ContentItem.item_id")
        if self.kind not in CONTENT_KINDS:
            raise ScenarioAuthoringValidationError(
                f"ContentItem.kind: unknown {self.kind!r}"
            )
        if self.utterance is not None and not isinstance(self.utterance, Utterance):
            raise ScenarioAuthoringValidationError("ContentItem.utterance: expected Utterance")
        if self.choice is not None and not isinstance(self.choice, AuthoredChoice):
            raise ScenarioAuthoringValidationError("ContentItem.choice: expected AuthoredChoice")
        if self.media is not None and not isinstance(self.media, MediaReference):
            raise ScenarioAuthoringValidationError("ContentItem.media: expected MediaReference")

        has_utterance = self.utterance is not None
        has_choice = self.choice is not None
        has_media = self.media is not None
        if self.kind == CONTENT_KIND_TEXT and (not has_utterance or has_choice or has_media):
            raise ScenarioAuthoringValidationError(
                "ContentItem TEXT: exactly one utterance payload (no choice/media)"
            )
        if self.kind == CONTENT_KIND_CHOICE and (not has_choice or has_utterance or has_media):
            raise ScenarioAuthoringValidationError(
                "ContentItem CHOICE: exactly one choice payload (no utterance/media)"
            )
        if self.kind == CONTENT_KIND_MEDIA and (not has_media or has_utterance or has_choice):
            raise ScenarioAuthoringValidationError(
                "ContentItem MEDIA: exactly one media payload (no utterance/choice)"
            )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"item_id": self.item_id, "kind": self.kind}
        if self.utterance is not None:
            result["utterance"] = self.utterance.to_dict()
        if self.choice is not None:
            result["choice"] = self.choice.to_dict()
        if self.media is not None:
            result["media"] = self.media.to_dict()
        return result

@dataclass(frozen=True)
class Slide:
    """One slide inside a Card with an optional background and ordered content.

    One Card may contain multiple Slides; a slide has its own background media
    reference and its own ordered content items.
    """

    slide_id: str
    background: Optional[MediaReference] = None
    content_items: Tuple[ContentItem, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.slide_id, "Slide.slide_id")
        if self.background is not None and not isinstance(self.background, MediaReference):
            raise ScenarioAuthoringValidationError("Slide.background: expected MediaReference")
        items = tuple(self.content_items)
        object.__setattr__(self, "content_items", items)
        seen: dict[str, int] = {}
        for index, item in enumerate(items):
            if not isinstance(item, ContentItem):
                raise ScenarioAuthoringValidationError(
                    f"Slide.content_items[{index}]: expected ContentItem"
                )
            if item.item_id in seen:
                raise ScenarioAuthoringValidationError(
                    f"Slide.content_items: duplicate item_id {item.item_id!r}"
                )
            seen[item.item_id] = index

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "slide_id": self.slide_id,
            "content_items": [i.to_dict() for i in self.content_items],
        }
        if self.background is not None:
            result["background"] = self.background.to_dict()
        return result


@dataclass(frozen=True)
class CardConnection:
    """One explicit author-controlled connection from a Card to another Card.

    ``target_card_id`` is a stable reference to the target Card. ``choice_id``,
    when set, references an authored CHOICE content item inside the source Card
    (a branch connection). Connections are authoring data, never a competing
    gameplay runtime, and are never inferred from content order or position.
    """

    connection_id: str
    target_card_id: str
    label: Optional[str] = None
    choice_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require_stable_id(self.connection_id, "CardConnection.connection_id")
        _require_stable_id(self.target_card_id, "CardConnection.target_card_id")
        if self.label is not None:
            _require_non_empty_string(self.label, "CardConnection.label")
        if self.choice_id is not None:
            _require_stable_id(self.choice_id, "CardConnection.choice_id")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "connection_id": self.connection_id,
            "target_card_id": self.target_card_id,
        }
        if self.label is not None:
            result["label"] = self.label
        if self.choice_id is not None:
            result["choice_id"] = self.choice_id
        return result

@dataclass(frozen=True)
class Card:
    """An independent editable authoring container with ordered slides.

    ``card_id`` is stable and independent of filesystem path, visual position or
    current slide index. ``connections`` are explicit author-controlled edges to
    other cards; they are never derived from, or mutated by, content reordering.
    """

    card_id: str
    slides: Tuple[Slide, ...]
    connections: Tuple[CardConnection, ...] = ()

    def __post_init__(self) -> None:
        _require_stable_id(self.card_id, "Card.card_id")
        slides = tuple(self.slides)
        object.__setattr__(self, "slides", slides)
        seen_slides: dict[str, int] = {}
        for index, slide in enumerate(slides):
            if not isinstance(slide, Slide):
                raise ScenarioAuthoringValidationError(
                    f"Card.slides[{index}]: expected Slide"
                )
            if slide.slide_id in seen_slides:
                raise ScenarioAuthoringValidationError(
                    f"Card.slides: duplicate slide_id {slide.slide_id!r}"
                )
            seen_slides[slide.slide_id] = index

        connections = tuple(self.connections)
        object.__setattr__(self, "connections", connections)
        seen_connections: dict[str, int] = {}
        for index, connection in enumerate(connections):
            if not isinstance(connection, CardConnection):
                raise ScenarioAuthoringValidationError(
                    f"Card.connections[{index}]: expected CardConnection"
                )
            if connection.connection_id in seen_connections:
                raise ScenarioAuthoringValidationError(
                    f"Card.connections: duplicate connection_id {connection.connection_id!r}"
                )
            seen_connections[connection.connection_id] = index

        # Branch resolution requires each authored CHOICE id to be unique within
        # the Card (CardConnection.choice_id references it). A duplicate across
        # any two Slides makes branch resolution ambiguous, so reject it here --
        # even before any branch connection exists.
        seen_choice_ids: set[str] = set()
        for item in self.iter_content_items():
            if item.kind == CONTENT_KIND_CHOICE and item.choice is not None:
                choice_id = item.choice.choice_id
                if choice_id in seen_choice_ids:
                    raise ScenarioAuthoringValidationError(
                        f"Card.choice_ids: duplicate choice_id {choice_id!r}"
                    )
                seen_choice_ids.add(choice_id)

    def slide_ids(self) -> Tuple[str, ...]:
        return tuple(s.slide_id for s in self.slides)

    def connection_ids(self) -> Tuple[str, ...]:
        return tuple(c.connection_id for c in self.connections)

    def choice_ids(self) -> frozenset[str]:
        """All authored CHOICE ids present anywhere in this card's content."""
        ids: set[str] = set()
        for item in self.iter_content_items():
            if item.kind == CONTENT_KIND_CHOICE and item.choice is not None:
                ids.add(item.choice.choice_id)
        return frozenset(ids)

    def iter_content_items(self) -> Iterator[ContentItem]:
        for slide in self.slides:
            for item in slide.content_items:
                yield item

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "card_id": self.card_id,
            "slides": [s.to_dict() for s in self.slides],
        }
        if self.connections:
            result["connections"] = [c.to_dict() for c in self.connections]
        return result


@dataclass(frozen=True)
class CharacterReference:
    """Minimal reserved character boundary for the future project model.

    Represents the three-way split (CHARACTER / CHARACTER MEDIA LIBRARY /
    CHARACTER AI ASSISTANT) by recording ONLY stable identity + provenance.
    SE-1.1 does NOT implement ``.vchar`` import, casting, dialogue, provider
    activation, or a replacement package format.
    """

    character_id: str
    provenance: str
    name: Optional[str] = None

    def __post_init__(self) -> None:
        _require_stable_id(self.character_id, "CharacterReference.character_id")
        if self.provenance not in CHARACTER_PROVENANCES:
            raise ScenarioAuthoringValidationError(
                f"CharacterReference.provenance: unknown {self.provenance!r}"
            )
        if self.name is not None:
            _require_non_empty_string(self.name, "CharacterReference.name")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "character_id": self.character_id,
            "provenance": self.provenance,
        }
        if self.name is not None:
            result["name"] = self.name
        return result

@dataclass(frozen=True)
class Project:
    """The immutable authoring project: ordered Cards + an explicit start Card.

    ``cards`` is the ordered authoring Card membership; ``start_card_id`` must
    resolve to an existing Card. ``characters`` reserves the minimal
    character-boundary (stable id + provenance) for the future project model.
    """

    schema_version: str
    project_id: str
    cards: Tuple[Card, ...]
    start_card_id: str
    characters: Tuple[CharacterReference, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SCENARIO_AUTHORING_SCHEMA_VERSION:
            raise ScenarioAuthoringValidationError(
                f"schema_version {self.schema_version!r} unsupported; "
                f"expected {SCENARIO_AUTHORING_SCHEMA_VERSION!r}"
            )
        _require_stable_id(self.project_id, "project_id")

        cards = tuple(self.cards)
        object.__setattr__(self, "cards", cards)
        if len(cards) == 0:
            raise ScenarioAuthoringValidationError("cards: at least one Card is required")
        seen_cards: dict[str, int] = {}
        for index, card in enumerate(cards):
            if not isinstance(card, Card):
                raise ScenarioAuthoringValidationError(f"cards[{index}]: expected Card")
            if card.card_id in seen_cards:
                raise ScenarioAuthoringValidationError(
                    f"cards: duplicate card_id {card.card_id!r}"
                )
            seen_cards[card.card_id] = index

        start = _require_stable_id(self.start_card_id, "start_card_id")
        object.__setattr__(self, "start_card_id", start)
        if start not in seen_cards:
            raise ScenarioAuthoringValidationError(
                f"start_card_id {start!r} is not an existing Card"
            )

        characters = tuple(self.characters)
        object.__setattr__(self, "characters", characters)
        seen_characters: dict[str, int] = {}
        for index, character in enumerate(characters):
            if not isinstance(character, CharacterReference):
                raise ScenarioAuthoringValidationError(
                    f"characters[{index}]: expected CharacterReference"
                )
            if character.character_id in seen_characters:
                raise ScenarioAuthoringValidationError(
                    f"characters: duplicate character_id {character.character_id!r}"
                )
            seen_characters[character.character_id] = index

    def card_ids(self) -> Tuple[str, ...]:
        return tuple(c.card_id for c in self.cards)

    def card_by_id(self, card_id: str) -> Card:
        for card in self.cards:
            if card.card_id == card_id:
                return card
        raise KeyError(card_id)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "cards": [c.to_dict() for c in self.cards],
            "start_card_id": self.start_card_id,
        }
        if self.characters:
            result["characters"] = [c.to_dict() for c in self.characters]
        return result

def resolve_effective_overrides(
    utterance: Utterance,
) -> Tuple[Tuple[SpeakerOverride, ...], ...]:
    """Resolve effective per-speaker presentation across an Utterance's portions.

    Mirrors DW-02 (``SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md`` §H):
    a speaker's portrait/emotion may change per portion, inheriting the previous
    portion's value by default when the current portion does not override it.
    The authoritative whole ``text`` is never touched.

    Returns one tuple per portion, in stable ``speaker_ids`` order; a speaker
    that has never specified a value keeps ``None`` for portrait/emotion.
    """
    resolved: list[tuple[SpeakerOverride, ...]] = []
    current: dict[str, tuple[Optional[MediaReference], Optional[str]]] = {}
    for portion in utterance.portions:
        by_speaker = {o.character_id: o for o in portion.overrides}
        effective: list[SpeakerOverride] = []
        for sid in utterance.speaker_ids:
            override = by_speaker.get(sid)
            if override is not None:
                current[sid] = (override.portrait, override.emotion)
            portrait, emotion = current.get(sid, (None, None))
            effective.append(
                SpeakerOverride(character_id=sid, portrait=portrait, emotion=emotion)
            )
        resolved.append(tuple(effective))
    return tuple(resolved)


def _required(data: dict, key: str, context: str) -> Any:
    """Fetch a required key, raising a controlled validation error if absent.

    Used by the ``*_from_dict`` helpers so a missing required field raises
    :class:`ScenarioAuthoringValidationError` instead of leaking a raw
    ``KeyError``. No automatic default is supplied for a missing required field.
    """
    if key not in data:
        raise ScenarioAuthoringValidationError(
            f"{context}: missing required field {key!r}"
        )
    return data[key]


def _media_from_dict(data: Any) -> MediaReference:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("media: expected object")
    return MediaReference(asset_id=data.get("asset_id"), relative_path=data.get("relative_path"))


def _override_from_dict(data: Any) -> SpeakerOverride:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("override: expected object")
    raw_portrait = data.get("portrait")
    return SpeakerOverride(
        character_id=_required(data, "character_id", "override"),
        portrait=_media_from_dict(raw_portrait) if raw_portrait is not None else None,
        emotion=data.get("emotion"),
    )


def _portion_from_dict(data: Any) -> DisplayPortion:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("portion: expected object")
    raw_overrides = data.get("overrides", [])
    if not isinstance(raw_overrides, list):
        raise ScenarioAuthoringValidationError("portion.overrides: expected array")
    return DisplayPortion(
        portion_id=_required(data, "portion_id", "portion"),
        start_offset=_required(data, "start_offset", "portion"),
        end_offset=_required(data, "end_offset", "portion"),
        overrides=tuple(_override_from_dict(o) for o in raw_overrides),
    )


def _utterance_from_dict(data: Any) -> Utterance:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("utterance: expected object")
    raw_portions = data.get("portions", [])
    if not isinstance(raw_portions, list):
        raise ScenarioAuthoringValidationError("utterance.portions: expected array")
    return Utterance(
        utterance_id=_required(data, "utterance_id", "utterance"),
        text=_required(data, "text", "utterance"),
        speaker_ids=tuple(data.get("speaker_ids", [])),
        portions=tuple(_portion_from_dict(p) for p in raw_portions),
    )


def _option_from_dict(data: Any) -> ChoiceOption:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("option: expected object")
    return ChoiceOption(
        option_id=_required(data, "option_id", "option"),
        label=_required(data, "label", "option"),
        target_connection_id=data.get("target_connection_id"),
    )


def _choice_from_dict(data: Any) -> AuthoredChoice:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("choice: expected object")
    raw_options = data.get("options", [])
    if not isinstance(raw_options, list):
        raise ScenarioAuthoringValidationError("choice.options: expected array")
    return AuthoredChoice(
        choice_id=_required(data, "choice_id", "choice"),
        prompt=_required(data, "prompt", "choice"),
        options=tuple(_option_from_dict(o) for o in raw_options),
    )


def _item_from_dict(data: Any) -> ContentItem:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("content item: expected object")
    raw_utterance = data.get("utterance")
    raw_choice = data.get("choice")
    raw_media = data.get("media")
    return ContentItem(
        item_id=_required(data, "item_id", "content item"),
        kind=_required(data, "kind", "content item"),
        utterance=_utterance_from_dict(raw_utterance) if raw_utterance is not None else None,
        choice=_choice_from_dict(raw_choice) if raw_choice is not None else None,
        media=_media_from_dict(raw_media) if raw_media is not None else None,
    )

def _slide_from_dict(data: Any) -> Slide:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("slide: expected object")
    raw_background = data.get("background")
    raw_items = data.get("content_items", [])
    if not isinstance(raw_items, list):
        raise ScenarioAuthoringValidationError("slide.content_items: expected array")
    return Slide(
        slide_id=_required(data, "slide_id", "slide"),
        background=_media_from_dict(raw_background) if raw_background is not None else None,
        content_items=tuple(_item_from_dict(i) for i in raw_items),
    )


def _connection_from_dict(data: Any) -> CardConnection:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("connection: expected object")
    return CardConnection(
        connection_id=_required(data, "connection_id", "connection"),
        target_card_id=_required(data, "target_card_id", "connection"),
        label=data.get("label"),
        choice_id=data.get("choice_id"),
    )


def _card_from_dict(data: Any) -> Card:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("card: expected object")
    raw_slides = data.get("slides", [])
    raw_connections = data.get("connections", [])
    if not isinstance(raw_slides, list):
        raise ScenarioAuthoringValidationError("card.slides: expected array")
    if not isinstance(raw_connections, list):
        raise ScenarioAuthoringValidationError("card.connections: expected array")
    return Card(
        card_id=_required(data, "card_id", "card"),
        slides=tuple(_slide_from_dict(s) for s in raw_slides),
        connections=tuple(_connection_from_dict(c) for c in raw_connections),
    )


def _character_from_dict(data: Any) -> CharacterReference:
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("character: expected object")
    return CharacterReference(
        character_id=_required(data, "character_id", "character"),
        provenance=_required(data, "provenance", "character"),
        name=data.get("name"),
    )


def project_from_dict(data: Any) -> Project:
    """Build a validated Project from plain dict data (fail closed)."""
    if not isinstance(data, dict):
        raise ScenarioAuthoringValidationError("project root must be an object")
    raw_cards = data.get("cards")
    raw_characters = data.get("characters", [])
    if not isinstance(raw_cards, list):
        raise ScenarioAuthoringValidationError("cards: expected an array")
    if not isinstance(raw_characters, list):
        raise ScenarioAuthoringValidationError("characters: expected an array")
    return Project(
        schema_version=_required(data, "schema_version", "project"),
        project_id=_required(data, "project_id", "project"),
        cards=tuple(_card_from_dict(c) for c in raw_cards),
        start_card_id=_required(data, "start_card_id", "project"),
        characters=tuple(_character_from_dict(c) for c in raw_characters),
    )

