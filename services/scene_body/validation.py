#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Body v1 -- acceptance-completeness validation.

This module implements ONLY the **acceptance-completeness** boundary, which is
deliberately separate from model construction validity (enforced in
``services/scene_body/model.py``). A SceneBody may be a perfectly valid but
incomplete Draft; ``validate_acceptance_complete`` reports the player-relevant
gates that must hold before projection into an OrderedASS (``ass/0.2``).

No external scene lookup, no physical asset lookup, no Story Graph, and no
variable evaluation happen here. Entry/option ID uniqueness is already
guaranteed by model construction and is therefore not re-checked.

The Visual Change asset_id syntax reuses the existing Visual Asset Registry v0
convention verbatim (``tools/visual_asset_registry.ASSET_ID_RE``) without
modifying the registry and without introducing a stronger/newer format.
"""

from __future__ import annotations

from tools.visual_asset_registry import ASSET_ID_RE

from .model import (
    AUTHORING_SCHEMA_VERSION,
    TARGET_KIND_ENTRY,
    TARGET_KIND_SCENE,
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_NARRATIVE,
    TEXT_PRESENTATION_THOUGHT,
    THOUGHT_VISIBILITIES,
    VISUAL_OP_CLEAR,
    VISUAL_OP_SET,
    ChoiceEntry,
    SceneBody,
    TextEntry,
    VisualChangeEvent,
)


def _non_blank(value: str) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _check_text(entry: TextEntry, participant_ids: frozenset[str], errors: list[str]) -> None:
    if not _non_blank(entry.text):
        errors.append(f"text entry {entry.entry_id!r}: text must be non-blank")
    if entry.presentation == TEXT_PRESENTATION_NARRATIVE:
        if entry.character_id is not None:
            errors.append(f"text entry {entry.entry_id!r}: NARRATIVE must not carry character_id")
        if entry.thought_visibility is not None:
            errors.append(f"text entry {entry.entry_id!r}: NARRATIVE must not carry thought_visibility")
    elif entry.presentation == TEXT_PRESENTATION_DIALOGUE:
        if not _non_blank(entry.character_id or ""):
            errors.append(f"text entry {entry.entry_id!r}: DIALOGUE requires character_id")
        elif entry.character_id not in participant_ids:
            errors.append(f"text entry {entry.entry_id!r}: character {entry.character_id!r} is not a participant")
        if entry.thought_visibility is not None:
            errors.append(f"text entry {entry.entry_id!r}: DIALOGUE must not carry thought_visibility")
    elif entry.presentation == TEXT_PRESENTATION_THOUGHT:
        if not _non_blank(entry.character_id or ""):
            errors.append(f"text entry {entry.entry_id!r}: THOUGHT requires character_id")
        elif entry.character_id not in participant_ids:
            errors.append(f"text entry {entry.entry_id!r}: character {entry.character_id!r} is not a participant")
        if entry.thought_visibility not in THOUGHT_VISIBILITIES:
            errors.append(
                f"text entry {entry.entry_id!r}: THOUGHT requires a valid thought_visibility "
                f"from {THOUGHT_VISIBILITIES!r}"
            )


def _check_choice(entry: ChoiceEntry, entry_ids: frozenset[str], errors: list[str]) -> None:
    if len(entry.options) == 0:
        errors.append(f"choice entry {entry.entry_id!r}: at least one option is required")
        return
    for option in entry.options:
        if not _non_blank(option.display_text):
            errors.append(f"choice option {option.option_id!r}: display_text must be non-blank")
        if option.target is None:
            errors.append(f"choice option {option.option_id!r}: a target is required")
            continue
        if option.target.target_kind == TARGET_KIND_ENTRY:
            if option.target.target_id not in entry_ids:
                errors.append(
                    f"choice option {option.option_id!r}: ENTRY target "
                    f"{option.target.target_id!r} does not resolve inside this SceneBody"
                )
        elif option.target.target_kind == TARGET_KIND_SCENE:
            if not _non_blank(option.target.target_id):
                errors.append(f"choice option {option.option_id!r}: SCENE target must be a non-empty id")
        # No external scene lookup; no reachability/cycle/execution validation.


def _check_visual(entry: VisualChangeEvent, errors: list[str]) -> None:
    if entry.operation == VISUAL_OP_SET:
        if not _non_blank(entry.asset_id or ""):
            errors.append(f"visual entry {entry.entry_id!r}: SET requires an asset_id")
        elif ASSET_ID_RE.fullmatch(entry.asset_id) is None:
            errors.append(
                f"visual entry {entry.entry_id!r}: asset_id {entry.asset_id!r} does not "
                f"satisfy the Visual Asset Registry v0 syntax"
            )
    elif entry.operation == VISUAL_OP_CLEAR:
        if entry.asset_id is not None:
            errors.append(f"visual entry {entry.entry_id!r}: CLEAR must not carry an asset_id")
    # No physical asset existence lookup in this slice.


def validate_acceptance_complete(body: SceneBody) -> list[str]:
    """Return the list of acceptance-completeness violations (empty == complete).

    This is NOT the same as model construction validity: a structurally valid
    but incomplete Draft is expected and reported here, never rejected at
    construction time.
    """
    errors: list[str] = []

    if body.authoring_schema_version != AUTHORING_SCHEMA_VERSION:
        errors.append(f"authoring_schema_version must be {AUTHORING_SCHEMA_VERSION!r}")

    if not _non_blank(body.location_id or ""):
        errors.append("location_id must be a non-empty string")
    if not _non_blank(body.content_rating or ""):
        errors.append("content_rating must be a non-empty string")
    if len(body.entries) == 0:
        errors.append("at least one ordered entry is required")

    participant_ids = body.participant_ids()
    entry_ids = body.entry_ids()

    for entry in body.entries:
        if isinstance(entry, TextEntry):
            _check_text(entry, participant_ids, errors)
        elif isinstance(entry, ChoiceEntry):
            _check_choice(entry, entry_ids, errors)
        elif isinstance(entry, VisualChangeEvent):
            _check_visual(entry, errors)

    return errors


def is_acceptance_complete(body: SceneBody) -> bool:
    """Convenience predicate: True iff ``validate_acceptance_complete`` is empty."""
    return not validate_acceptance_complete(body)
