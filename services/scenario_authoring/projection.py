#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.3 -- deterministic authoring->OrderedASS projection foundation.

A pure, UI-independent, stdlib-only projection boundary from a validated
``services.scenario_authoring`` ``Project`` into the existing ``SceneBody``
contract (``scene_body/1.0``). A complete ``SceneBody`` is then projected to
``OrderedASS`` (``ass/0.2``) by the existing ``build_ordered_ass`` -- this
module does NOT reimplement that step and does NOT introduce a custom story
runtime.

The source ``Project`` is never mutated (all authoring entities are frozen) and
is never used to synthesize a competing gameplay graph: the projection only
flattens the author's explicit content order and the author's explicit Card
connections into the existing accepted-scene control-flow vocabulary
(ENTRY / SCENE / END targets and per-entry ``next_target``).

Supported authoring -> SceneBody mappings (see the design draft):
    - Utterance (0 speakers)       -> TextEntry NARRATIVE (whole authoritative text)
    - Utterance (1 speaker)        -> TextEntry DIALOGUE (whole authoritative text)
    - AuthoredChoice               -> ChoiceEntry (each option -> explicit target)
    - Slide.background(asset_id)   -> VisualChangeEvent SET (leading entry of slide)
    - Card linear connection       -> explicit ``next_target`` on the card's last entry
    - Card terminal (no connection)-> explicit ``next_target = END``
    - cross-scene connection       -> SCENE target (start card of the target scene only)

Unsupported authoring content fails closed with an explicit error, never by
silently dropping content:
    - Utterance with >= 2 speakers (group-speaker presentation);
    - ContentItem MEDIA (no media-type discriminator; audio/video unsupported);
    - Slide.background with relative_path (no asset_id for VisualChangeEvent);
    - content after a CHOICE item within one Card (unreachable);
    - a choice option without a resolvable branch connection;
    - a branch connection not referenced by any option of its choice;
    - a Card with no projectable content;
    - more than one linear connection on one Card;
    - a linear continuation to a non-adjacent same-scene Card (implicit story order);
    - a cross-scene target that is not the start card of the target scene
      (unsupported cross-scene ENTRY target);
    - a cross-scene transition not declared in ``supported_scene_transitions``.

Display Portions: the whole Utterance text is always projected (authoritative
and recoverable). Per-portion segmentation / speaker overrides are preserved in
a deterministic, hash-verifiable ``DisplayPortionManifest`` TECHNICAL CANDIDATE
sidecar -- NOT part of OrderedASS, NOT an ``ass/0.2`` extension, and never
presented as accepted publication truth.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from services.scene_body import (
    AUTHORING_SCHEMA_VERSION,
    TARGET_KIND_END,
    TARGET_KIND_ENTRY,
    TARGET_KIND_SCENE,
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_NARRATIVE,
    VISUAL_OP_SET,
    ChoiceEntry as SceneChoiceEntry,
    ChoiceOption as SceneChoiceOption,
    ChoiceTarget,
    Participant,
    SceneBody,
    TextEntry,
    VisualChangeEvent,
)
from services.scene_body.validation import validate_acceptance_complete

from .errors import ScenarioAuthoringError
from .model import (
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_MEDIA,
    CONTENT_KIND_TEXT,
    Card,
    ContentItem,
    MediaReference,
    Project,
    Utterance,
)
from .validation import validate_project

# Working technical-draft schema id for the Display Portion manifest sidecar.
# This is NOT an accepted/ratified canonical format.
DISPLAY_PORTION_MANIFEST_SCHEMA_ID = "scenario_authoring_projection_display_portions/0.1"


class ProjectionError(ScenarioAuthoringError):
    """Raised when a validated authoring Project cannot be deterministically
    projected (a missing/inconsistent target or an ambiguous continuation)."""


class UnsupportedProjectionError(ProjectionError):
    """Raised when authoring content has no representation in the existing
    accepted-scene contract (fail closed, never silently discard)."""


# ---------------------------------------------------------------------------
# Projection input configuration (the explicit scene map the Card model does
# not own -- OD-SE-AUTHORING-MODEL-01 keeps the authoring model unchanged).
# ---------------------------------------------------------------------------

def _require_scene_string(value: Any, field: str) -> str:
    """A scene-level identity/rating/location string: non-empty, untrimmed."""
    if not isinstance(value, str) or value == "":
        raise ProjectionError(f"{field}: required non-empty string")
    if value.strip() != value:
        raise ProjectionError(f"{field}: must not have leading/trailing whitespace")
    return value


def _require_optional_scene_string(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProjectionError(f"{field}: expected string or None")
    return value


@dataclass(frozen=True)
class SceneMembership:
    """One accepted scene's explicit membership: ordered Cards + scene-level
    facts that the authoring Card model deliberately does not own."""

    scene_id: str
    card_ids: Tuple[str, ...]
    location_id: str
    content_rating: str
    scene_title: Optional[str] = None

    def __post_init__(self) -> None:
        _require_scene_string(self.scene_id, "SceneMembership.scene_id")
        if not isinstance(self.card_ids, tuple) or len(self.card_ids) == 0:
            raise ProjectionError("SceneMembership.card_ids: non-empty tuple required")
        seen: set[str] = set()
        for index, card_id in enumerate(self.card_ids):
            _require_scene_string(card_id, f"SceneMembership.card_ids[{index}]")
            if card_id in seen:
                raise ProjectionError(
                    f"SceneMembership.card_ids: duplicate card {card_id!r}"
                )
            seen.add(card_id)
        _require_scene_string(self.location_id, "SceneMembership.location_id")
        _require_scene_string(self.content_rating, "SceneMembership.content_rating")
        _require_optional_scene_string(self.scene_title, "SceneMembership.scene_title")


@dataclass(frozen=True)
class ProjectionConfig:
    """Explicit, validated projection input: scene membership + allowed
    cross-scene transitions.

    ``scenes`` is ordered (it defines the deterministic scene order). Every
    project Card must appear in exactly one scene. ``supported_scene_transitions``
    is the explicit allowlist of ``(from_scene_id, to_scene_id)`` cross-scene
    continuations; an undeclared cross-scene transition is rejected.
    """

    scenes: Tuple[SceneMembership, ...]
    supported_scene_transitions: Tuple[Tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenes, tuple) or len(self.scenes) == 0:
            raise ProjectionError("ProjectionConfig.scenes: non-empty tuple required")

        scenes = tuple(self.scenes)
        object.__setattr__(self, "scenes", scenes)
        scene_ids: set[str] = set()
        card_to_scene: dict[str, str] = {}
        for scene in scenes:
            if not isinstance(scene, SceneMembership):
                raise ProjectionError("ProjectionConfig.scenes: expected SceneMembership")
            if scene.scene_id in scene_ids:
                raise ProjectionError(f"duplicate scene_id {scene.scene_id!r}")
            scene_ids.add(scene.scene_id)
            for card_id in scene.card_ids:
                if card_id in card_to_scene:
                    raise ProjectionError(
                        f"duplicate card membership {card_id!r} "
                        f"(scene {card_to_scene[card_id]!r} and {scene.scene_id!r})"
                    )
                card_to_scene[card_id] = scene.scene_id

        transitions = tuple(self.supported_scene_transitions)
        object.__setattr__(self, "supported_scene_transitions", transitions)
        for transition in transitions:
            if (
                not isinstance(transition, tuple)
                or len(transition) != 2
                or not isinstance(transition[0], str)
                or not isinstance(transition[1], str)
            ):
                raise ProjectionError(
                    f"supported_scene_transitions: expected (from_scene, to_scene) pairs, got {transition!r}"
                )
            if transition[0] not in scene_ids or transition[1] not in scene_ids:
                raise ProjectionError(
                    f"supported_scene_transitions: unknown scene in {transition!r}"
                )

    def scene_ids(self) -> Tuple[str, ...]:
        return tuple(s.scene_id for s in self.scenes)


# ---------------------------------------------------------------------------
# Display Portion manifest (TECHNICAL CANDIDATE -- not an accepted format)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OverrideRecord:
    """Deterministic record of one Display Portion speaker override."""

    character_id: str
    portrait: Optional[MediaReference] = None
    emotion: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"character_id": self.character_id}
        if self.portrait is not None:
            result["portrait"] = self.portrait.to_dict()
        if self.emotion is not None:
            result["emotion"] = self.emotion
        return result


@dataclass(frozen=True)
class PortionRecord:
    """Deterministic record of one Display Portion (exact source segmentation)."""

    portion_id: str
    start_offset: int
    end_offset: int
    overrides: Tuple[OverrideRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "portion_id": self.portion_id,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "overrides": [o.to_dict() for o in self.overrides],
        }


@dataclass(frozen=True)
class DisplayPortionManifest:
    """Deterministic, hash-verifiable record of Display Portion metadata.

    TECHNICAL CANDIDATE ONLY. It preserves exact source segmentation, stable
    portion identity, order, and speaker portrait/emotion overrides WITHOUT
    mutating any canonical schema (scene_body/1.0, ass/0.2, story_sequence/0.1).
    It is not published as accepted truth and is not an ass/0.2 extension.
    """

    schema_id: str
    scene_id: str
    utterance_id: str
    text: str
    portions: Tuple[PortionRecord, ...]
    content_hash: str

    def semantic_payload(self) -> dict[str, Any]:
        """The deterministic payload that ``content_hash`` covers."""
        return {
            "schema_id": self.schema_id,
            "scene_id": self.scene_id,
            "utterance_id": self.utterance_id,
            "text": self.text,
            "portions": [p.to_dict() for p in self.portions],
        }

    def to_dict(self) -> dict[str, Any]:
        result = self.semantic_payload()
        result["content_hash"] = self.content_hash
        return result


def _manifest_hash(payload: dict[str, Any]) -> str:
    """Lowercase-hex SHA-256 over canonical JSON, mirroring ``services.ass.hashing``."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Projection result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Projection:
    """The deterministic projection result: one SceneBody per scene, plus the
    scene order, the designated start scene, and any Display Portion manifests."""

    scene_bodies: Tuple[SceneBody, ...]
    scene_order: Tuple[str, ...]
    start_scene_id: str
    portion_manifests: Tuple[DisplayPortionManifest, ...] = ()


# ---------------------------------------------------------------------------
# Internal projection context (resolved maps shared across a run)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ProjectionContext:
    card_scene: Mapping[str, str]
    scene_card_ids: Mapping[str, Tuple[str, ...]]
    scene_start_card: Mapping[str, str]
    first_entry_id: Mapping[str, str]
    supported_transitions: frozenset


# ---------------------------------------------------------------------------
# Card structural analysis (entry ids + unsupported-content rejection)
# ---------------------------------------------------------------------------

def _card_segments(card: Card) -> list:
    """Return the ordered ``(entry_id, kind, payload)`` segments of a Card.

    ``kind`` is ``"bg"`` (a slide background) or ``"item"`` (a content item).
    Order is exact author order: slides in order, background before the slide's
    items, items in order. Structural unsupported-content checks happen here so
    the entry-id pass and the build pass can never diverge.
    """
    segments: list = []
    has_content = False
    has_choice = False

    for slide in card.slides:
        if slide.background is not None:
            if has_choice:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r}: content after a CHOICE item is unsupported "
                    f"(it would be unreachable in the accepted ordered flow)"
                )
            if slide.background.asset_id is None:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r} slide {slide.slide_id!r}: background with "
                    f"relative_path is unsupported (VisualChangeEvent requires an asset_id)"
                )
            segments.append((f"{card.card_id}.{slide.slide_id}.@bg", "bg", slide.background))

        for item in slide.content_items:
            if has_choice:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r}: content after a CHOICE item is unsupported "
                    f"(it would be unreachable in the accepted ordered flow)"
                )
            if item.kind == CONTENT_KIND_MEDIA:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r}: MEDIA content item {item.item_id!r} is "
                    f"unsupported (no media-type discriminator; audio/video are not "
                    f"representable in OrderedASS)"
                )
            if item.kind == CONTENT_KIND_CHOICE:
                has_choice = True
            elif item.kind == CONTENT_KIND_TEXT:
                if item.utterance is not None and len(item.utterance.speaker_ids) >= 2:
                    raise UnsupportedProjectionError(
                        f"card {card.card_id!r}: group-speaker utterance "
                        f"{item.utterance.utterance_id!r} is unsupported "
                        f"(no group presentation in OrderedASS)"
                    )
            else:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r}: unknown content kind {item.kind!r}"
                )
            segments.append((f"{card.card_id}.{slide.slide_id}.{item.item_id}", "item", item))
            has_content = True

    if not has_content:
        raise ProjectionError(f"card {card.card_id!r}: no projectable content (empty Card)")
    return segments


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def _resolve_target(
    ctx: _ProjectionContext, source_scene_id: str, target_card_id: str
) -> ChoiceTarget:
    if target_card_id not in ctx.card_scene:
        raise ProjectionError(f"connection targets unknown card {target_card_id!r}")
    target_scene = ctx.card_scene[target_card_id]
    if target_scene == source_scene_id:
        return ChoiceTarget(
            target_kind=TARGET_KIND_ENTRY,
            target_id=ctx.first_entry_id[target_card_id],
        )
    # Cross-scene: only a scene's start card may be entered from outside.
    if ctx.scene_start_card[target_scene] != target_card_id:
        raise UnsupportedProjectionError(
            f"cross-scene target card {target_card_id!r} is not the start card of "
            f"scene {target_scene!r} (unsupported cross-scene ENTRY target)"
        )
    transition = (source_scene_id, target_scene)
    if transition not in ctx.supported_transitions:
        raise UnsupportedProjectionError(
            f"unsupported cross-scene transition {transition!r}"
        )
    return ChoiceTarget(target_kind=TARGET_KIND_SCENE, target_id=target_scene)


def _resolve_exit(
    ctx: _ProjectionContext,
    card: Card,
    linear: list,
    source_scene_id: str,
    index: int,
    total: int,
) -> ChoiceTarget:
    """Resolve a card's linear continuation (or its explicit END)."""
    if not linear:
        return ChoiceTarget(target_kind=TARGET_KIND_END, target_id=None)

    target_card_id = linear[0].target_card_id
    target_scene = ctx.card_scene[target_card_id]
    if target_scene == source_scene_id:
        ordered = ctx.scene_card_ids[source_scene_id]
        if index + 1 >= total:
            raise ProjectionError(
                f"card {card.card_id!r}: linear continuation targets same-scene card "
                f"{target_card_id!r} but it is the last card in scene {source_scene_id!r}"
            )
        next_card_id = ordered[index + 1]
        if target_card_id != next_card_id:
            raise ProjectionError(
                f"card {card.card_id!r}: linear continuation targets {target_card_id!r}, "
                f"which is not the next card {next_card_id!r} in scene order "
                f"(implicit story order is not invented)"
            )
        return ChoiceTarget(
            target_kind=TARGET_KIND_ENTRY,
            target_id=ctx.first_entry_id[target_card_id],
        )
    return _resolve_target(ctx, source_scene_id, target_card_id)


# ---------------------------------------------------------------------------
# Entry builders
# ---------------------------------------------------------------------------

def _text_entry(
    scene_id: str, entry_id: str, utterance: Utterance
) -> tuple:
    if utterance is None:
        raise ProjectionError(f"text entry {entry_id!r}: missing utterance payload")
    speakers = utterance.speaker_ids
    if len(speakers) == 0:
        entry = TextEntry(
            entry_id=entry_id,
            presentation=TEXT_PRESENTATION_NARRATIVE,
            text=utterance.text,
        )
    else:
        # Exactly one speaker (>=2 already rejected during structural analysis).
        entry = TextEntry(
            entry_id=entry_id,
            presentation=TEXT_PRESENTATION_DIALOGUE,
            text=utterance.text,
            character_id=speakers[0],
        )

    manifest = None
    if utterance.portions:
        manifest = _build_portion_manifest(scene_id, utterance)
    return entry, manifest


def _build_portion_manifest(scene_id: str, utterance: Utterance) -> DisplayPortionManifest:
    portions = tuple(
        PortionRecord(
            portion_id=p.portion_id,
            start_offset=p.start_offset,
            end_offset=p.end_offset,
            overrides=tuple(
                OverrideRecord(
                    character_id=o.character_id,
                    portrait=o.portrait,
                    emotion=o.emotion,
                )
                for o in p.overrides
            ),
        )
        for p in utterance.portions
    )
    provisional = DisplayPortionManifest(
        schema_id=DISPLAY_PORTION_MANIFEST_SCHEMA_ID,
        scene_id=scene_id,
        utterance_id=utterance.utterance_id,
        text=utterance.text,
        portions=portions,
        content_hash="",
    )
    content_hash = _manifest_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def _choice_entry(
    ctx: _ProjectionContext, entry_id: str, choice: Any, card: Card
) -> tuple:
    """Build a ChoiceEntry and return it plus the referenced branch connection ids."""
    connection_by_id = {c.connection_id: c for c in card.connections}
    source_scene_id = ctx.card_scene[card.card_id]
    options = []
    referenced: set = set()

    for option in choice.options:
        if option.target_connection_id is None:
            raise ProjectionError(
                f"card {card.card_id!r}: choice {choice.choice_id!r} option "
                f"{option.option_id!r} has no target connection (dangling/incomplete branch)"
            )
        connection = connection_by_id.get(option.target_connection_id)
        if connection is None:
            raise ProjectionError(
                f"card {card.card_id!r}: choice {choice.choice_id!r} option "
                f"{option.option_id!r} references unknown connection "
                f"{option.target_connection_id!r}"
            )
        if connection.choice_id != choice.choice_id:
            raise ProjectionError(
                f"card {card.card_id!r}: option {option.option_id!r} references connection "
                f"{connection.connection_id!r} with choice_id {connection.choice_id!r}, "
                f"expected {choice.choice_id!r}"
            )
        target = _resolve_target(ctx, source_scene_id, connection.target_card_id)
        options.append(
            SceneChoiceOption(
                option_id=option.option_id,
                display_text=option.label,
                target=target,
            )
        )
        referenced.add(connection.connection_id)

    return (
        SceneChoiceEntry(entry_id=entry_id, prompt=choice.prompt, options=tuple(options)),
        referenced,
    )


def _with_next_target(entry: Any, target: ChoiceTarget) -> Any:
    if isinstance(entry, TextEntry):
        return dataclasses.replace(entry, next_target=target)
    if isinstance(entry, VisualChangeEvent):
        return dataclasses.replace(entry, next_target=target)
    raise ProjectionError(f"cannot attach next_target to entry type {type(entry).__name__!r}")


def _project_card(
    ctx: _ProjectionContext,
    card: Card,
    segments: list,
    index: int,
    total: int,
    scene_id: str,
) -> tuple:
    linear = []
    branch_ids: set = set()
    for connection in card.connections:
        if connection.choice_id is None:
            linear.append(connection)
        else:
            branch_ids.add(connection.connection_id)

    if len(linear) > 1:
        raise ProjectionError(
            f"card {card.card_id!r}: multiple linear connections (ambiguous continuation)"
        )

    entries = []
    manifests = []
    referenced_branch_ids: set = set()

    for entry_id, kind, payload in segments:
        if kind == "bg":
            entries.append(
                VisualChangeEvent(entry_id=entry_id, operation=VISUAL_OP_SET, asset_id=payload.asset_id)
            )
        else:
            item = payload
            if item.kind == CONTENT_KIND_TEXT:
                entry, manifest = _text_entry(scene_id, entry_id, item.utterance)
                entries.append(entry)
                if manifest is not None:
                    manifests.append(manifest)
            elif item.kind == CONTENT_KIND_CHOICE:
                choice_entry, referenced = _choice_entry(ctx, entry_id, item.choice, card)
                entries.append(choice_entry)
                referenced_branch_ids |= referenced
            else:
                raise UnsupportedProjectionError(
                    f"card {card.card_id!r}: unsupported content kind {item.kind!r}"
                )

    last = entries[-1]
    if isinstance(last, SceneChoiceEntry):
        if linear:
            raise ProjectionError(
                f"card {card.card_id!r}: a Card ending in a CHOICE must not carry a "
                f"linear continuation (ambiguous exit)"
            )
        unreferenced = branch_ids - referenced_branch_ids
        if unreferenced:
            raise ProjectionError(
                f"card {card.card_id!r}: branch connection(s) {sorted(unreferenced)!r} "
                f"not referenced by any option"
            )
    else:
        if branch_ids:
            raise ProjectionError(
                f"card {card.card_id!r}: branch connections present but the Card has no CHOICE"
            )
        exit_target = _resolve_exit(
            ctx, card, linear, ctx.card_scene[card.card_id], index, total
        )
        entries[-1] = _with_next_target(last, exit_target)

    return entries, manifests


def _scene_speakers(cards: list) -> list:
    """Union of utterance speaker ids across a scene, in first-appearance order."""
    seen = []
    seen_set: set = set()
    for card in cards:
        for item in card.iter_content_items():
            if item.kind == CONTENT_KIND_TEXT and item.utterance is not None:
                for sid in item.utterance.speaker_ids:
                    if sid not in seen_set:
                        seen_set.add(sid)
                        seen.append(sid)
    return seen


# ---------------------------------------------------------------------------
# Public projection entry point
# ---------------------------------------------------------------------------

def project_scenes(project: Project, config: ProjectionConfig) -> Projection:
    """Deterministically project a validated authoring Project into SceneBodies.

    Returns one acceptance-complete ``SceneBody`` per scene (in config scene
    order), the deterministic scene order, the start scene, and any Display
    Portion manifests. The source ``Project`` is never mutated.
    """
    if not isinstance(project, Project):
        raise ProjectionError("project: expected Project")
    if not isinstance(config, ProjectionConfig):
        raise ProjectionError("config: expected ProjectionConfig")

    violations = validate_project(project)
    if violations:
        raise ProjectionError(f"project is inconsistent: {violations[0]}")

    # Resolve the explicit scene map against the actual project Cards.
    card_scene: dict[str, str] = {}
    scene_cards: dict[str, list] = {}
    scene_card_ids: dict[str, Tuple[str, ...]] = {}
    scene_start_card: dict[str, str] = {}
    for scene in config.scenes:
        cards = []
        for card_id in scene.card_ids:
            try:
                cards.append(project.card_by_id(card_id))
            except KeyError:
                raise ProjectionError(
                    f"config card {card_id!r} does not resolve to a project Card"
                ) from None
            card_scene[card_id] = scene.scene_id
        scene_cards[scene.scene_id] = cards
        scene_card_ids[scene.scene_id] = scene.card_ids
        scene_start_card[scene.scene_id] = scene.card_ids[0]

    for card in project.cards:
        if card.card_id not in card_scene:
            raise ProjectionError(f"card {card.card_id!r} is not assigned to any scene")

    # Start-card validation: start_card_id must be the first card of its scene.
    start_card_id = project.start_card_id
    start_scene_id = card_scene[start_card_id]
    if scene_start_card[start_scene_id] != start_card_id:
        raise ProjectionError(
            f"start_card_id {start_card_id!r} is not the first card of scene "
            f"{start_scene_id!r} (a middle-of-scene Card is not a valid start)"
        )

    ctx = _ProjectionContext(
        card_scene=card_scene,
        scene_card_ids=scene_card_ids,
        scene_start_card=scene_start_card,
        first_entry_id={},
        supported_transitions=frozenset(config.supported_scene_transitions),
    )

    # Pass A: structural analysis + stable entry ids for every card.
    segments_by_card: dict[str, list] = {}
    for scene in config.scenes:
        for card in scene_cards[scene.scene_id]:
            segments_by_card[card.card_id] = _card_segments(card)
    first_entry_id = {cid: segs[0][0] for cid, segs in segments_by_card.items()}
    ctx = dataclasses.replace(ctx, first_entry_id=first_entry_id)

    # Pass B: build each scene's ordered flow.
    scene_bodies = []
    all_manifests = []
    for scene in config.scenes:
        cards = scene_cards[scene.scene_id]
        participants = tuple(
            Participant(character_id=sid, role="", present=True)
            for sid in _scene_speakers(cards)
        )
        entries = []
        for index, card in enumerate(cards):
            card_entries, manifests = _project_card(
                ctx,
                card,
                segments_by_card[card.card_id],
                index,
                len(cards),
                scene.scene_id,
            )
            entries.extend(card_entries)
            all_manifests.extend(manifests)
        scene_bodies.append(
            SceneBody(
                authoring_schema_version=AUTHORING_SCHEMA_VERSION,
                scene_id=scene.scene_id,
                participants=participants,
                entries=tuple(entries),
                scene_title=scene.scene_title,
                location_id=scene.location_id,
                content_rating=scene.content_rating,
            )
        )

    # Fail closed if any projected body is not acceptance-complete.
    for body in scene_bodies:
        errors = validate_acceptance_complete(body)
        if errors:
            raise ProjectionError(
                f"scene {body.scene_id!r} failed acceptance-completeness: {errors[0]}"
            )

    return Projection(
        scene_bodies=tuple(scene_bodies),
        scene_order=config.scene_ids(),
        start_scene_id=start_scene_id,
        portion_manifests=tuple(all_manifests),
    )






