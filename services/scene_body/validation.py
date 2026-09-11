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
    TARGET_KIND_END,
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


def _check_next_target(
    entry_id: str,
    label: str,
    next_target,
    entry_ids: frozenset[str],
    errors: list[str],
) -> None:
    """Validate an optional explicit successor (OD-ORDEREDASS-CONTROL-FLOW-01).

    ``None`` (absent) is always valid -- it preserves existing fallthrough and
    is never required. Mirrors the existing ChoiceEntry ENTRY/SCENE target
    checks in ``_check_choice``: no external scene lookup, no reachability/
    cycle/execution validation.
    """
    if next_target is None:
        return
    if next_target.target_kind == TARGET_KIND_ENTRY:
        if next_target.target_id not in entry_ids:
            errors.append(
                f"{label} {entry_id!r}: next_target ENTRY {next_target.target_id!r} "
                f"does not resolve inside this SceneBody"
            )
    elif next_target.target_kind == TARGET_KIND_SCENE:
        if not _non_blank(next_target.target_id):
            errors.append(f"{label} {entry_id!r}: next_target SCENE must be a non-empty id")
    elif next_target.target_kind == TARGET_KIND_END:
        if next_target.target_id is not None:
            errors.append(f"{label} {entry_id!r}: next_target END must not carry a target_id")
    # No external scene lookup; no reachability/cycle/execution validation.


def _check_text(
    entry: TextEntry, participant_ids: frozenset[str], entry_ids: frozenset[str], errors: list[str]
) -> None:
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
    _check_next_target(entry.entry_id, "text entry", entry.next_target, entry_ids, errors)


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


def _check_visual(entry: VisualChangeEvent, entry_ids: frozenset[str], errors: list[str]) -> None:
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
    _check_next_target(entry.entry_id, "visual entry", entry.next_target, entry_ids, errors)


def _check_branch_fallthrough(body: SceneBody, errors: list[str]) -> None:
    """Reject the exact known silent multi-branch fallthrough condition
    (OD-ORDEREDASS-CONTROL-FLOW-01).

    Bounded to the concrete failure mode only: a ``ChoiceEntry`` with two or
    more DISTINCT FORWARD ``ENTRY`` branch starts (options whose target
    entry_id is positioned after the ChoiceEntry itself) requires that the
    entry immediately preceding every branch start after the first carry an
    explicit ``next_target`` -- otherwise that boundary entry would silently
    fall through into the next branch's content.

    This is NOT general reachability/cycle/graph analysis: only the single
    entry immediately adjacent to a subsequent forward branch start is
    inspected. Backward and self ENTRY targets never open a "forward branch"
    here and are therefore never restricted by this check, matching existing
    supported behavior (``_check_choice`` already permits them unconditionally).
    A boundary entry that is itself a ``ChoiceEntry`` is exempt: every
    ``ChoiceEntry`` option already renders an explicit jump, so it carries no
    fallthrough risk.
    """
    entries = body.entries
    position_by_id = {e.entry_id: index for index, e in enumerate(entries)}

    for choice_index, entry in enumerate(entries):
        if not isinstance(entry, ChoiceEntry):
            continue

        forward_starts: dict[str, int] = {}
        for option in entry.options:
            target = option.target
            if target is None or target.target_kind != TARGET_KIND_ENTRY:
                continue
            target_position = position_by_id.get(target.target_id)
            if target_position is None or target_position <= choice_index:
                continue  # unknown / backward / self: out of scope for this check
            forward_starts.setdefault(target.target_id, target_position)

        if len(forward_starts) < 2:
            continue

        ordered_positions = sorted(forward_starts.values())
        for next_start_position in ordered_positions[1:]:
            boundary_entry = entries[next_start_position - 1]
            if not isinstance(boundary_entry, (TextEntry, VisualChangeEvent)):
                continue  # a ChoiceEntry boundary always jumps explicitly
            if boundary_entry.next_target is None:
                errors.append(
                    f"choice entry {entry.entry_id!r}: entry {boundary_entry.entry_id!r} "
                    f"immediately precedes another branch start and has no explicit "
                    f"next_target (silent branch fallthrough)"
                )


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
            _check_text(entry, participant_ids, entry_ids, errors)
        elif isinstance(entry, ChoiceEntry):
            _check_choice(entry, entry_ids, errors)
        elif isinstance(entry, VisualChangeEvent):
            _check_visual(entry, entry_ids, errors)

    _check_branch_fallthrough(body, errors)

    return errors


def is_acceptance_complete(body: SceneBody) -> bool:
    """Convenience predicate: True iff ``validate_acceptance_complete`` is empty."""
    return not validate_acceptance_complete(body)
