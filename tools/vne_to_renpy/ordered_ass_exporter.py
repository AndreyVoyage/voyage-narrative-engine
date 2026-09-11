#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderedASS -> Ren'Py source renderer v1 (pure, OrderedASS-only).

Renders an accepted ``services.ass.OrderedASS`` into a deterministic Ren'Py
source string using explicit export dependencies only:

- a compile-time ``reading_mode`` (classic_vn / psychological / mind_reading);
- an explicit ``character_id -> Character symbol`` mapping;
- the set of known scene IDs (for SCENE choice targets);
- a pre-resolved ``asset_id -> ResolvedAsset`` mapping.

The renderer is a PURE source renderer: it returns a string and never performs
filesystem writes, never scans the workspace, never invokes the Ren'Py SDK, and
never constructs a ProductionMediaAssetBinding. The legacy Scenario V2 exporter
(``tools/renpy_v2_playable_exporter.py``) and the legacy visual statement
emitter are unaffected.

OrderedASS is the ONLY accepted input: legacy ``ASS`` (ass/0.1), ``SceneBody``,
``dict`` and duck-typed objects are rejected.
"""

from __future__ import annotations

import base64
import keyword
import re
import unicodedata
from typing import Literal, Mapping

from services.ass import OrderedASS
from services.production_media_asset_binding import ResolvedAsset
from services.scene_body import (
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_NARRATIVE,
    TEXT_PRESENTATION_THOUGHT,
    TARGET_KIND_END,
    TARGET_KIND_ENTRY,
    TARGET_KIND_SCENE,
    VISUAL_OP_CLEAR,
    VISUAL_OP_SET,
    ChoiceEntry,
    ChoiceTarget,
    TextEntry,
    VisualChangeEvent,
)

__all__ = [
    "render_ordered_ass",
    "READING_MODES",
    "ReadingMode",
    "OrderedExportError",
    "scene_start_label",
    "scene_end_label",
    "entry_label",
]

# ---------------------------------------------------------------------------
# Reading modes (compile-time only; never emitted as runtime state)
# ---------------------------------------------------------------------------

ReadingMode = Literal["classic_vn", "psychological", "mind_reading"]
READING_MODES = ("classic_vn", "psychological", "mind_reading")

# canonical thought_visibility values (unchanged from SceneBody semantics)
_THOUGHT_HIDDEN = "hidden"
_THOUGHT_REVEALED = "revealed"
_THOUGHT_ALWAYS = "always"

# reading_mode -> {thought_visibility: visible}
_THOUGHT_VISIBLE: dict[str, dict[str, bool]] = {
    "classic_vn": {
        _THOUGHT_HIDDEN: False,
        _THOUGHT_REVEALED: False,
        _THOUGHT_ALWAYS: True,
    },
    "psychological": {
        _THOUGHT_HIDDEN: False,
        _THOUGHT_REVEALED: True,
        _THOUGHT_ALWAYS: True,
    },
    "mind_reading": {
        _THOUGHT_HIDDEN: True,
        _THOUGHT_REVEALED: True,
        _THOUGHT_ALWAYS: True,
    },
}

# Transition allowlist: value -> emitted "with ..." line (None = no line).
_TRANSITION_WITH_LINE: dict[str, str] = {
    "fade": "with fade",
    "dissolve": "with dissolve",
}
_TRANSITION_NO_LINE = (None, "cut")

# The single dedicated visual alias used for every SET/CLEAR.
VISUAL_SLOT_ALIAS = "vne_scene_visual"

_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\Z")

_RESERVED_SYMBOLS = frozenset(keyword.kwlist) | frozenset({
    "narrator",
    "label", "menu", "jump", "call", "return", "show", "hide", "scene",
    "with", "define", "default", "init", "image", "transform", "screen",
    "style", "if", "elif", "else", "while", "for", "pass", "python",
    "at", "behind", "onlayer", "zorder", "as", "expression", "window",
    "character", "store", "renpy", "true", "false", "none", "persistent",
    "config", "pause", "play", "queue", "stop", "voice", "centered",
    "extend", "e",
})


class OrderedExportError(ValueError):
    """Raised when an OrderedASS cannot be rendered to Ren'Py source. Fails closed."""


def _base32_token(raw: str) -> str:
    """RFC 4648 Base32 (UTF-8) -> lowercase, '=' padding stripped.

    Injective for distinct raw strings, ASCII-safe, deterministic, and
    independent of list index / content / filesystem path.
    """
    encoded = base64.b32encode(raw.encode("utf-8"))
    return encoded.decode("ascii").lower().rstrip("=")


def scene_start_label(scene_id: str) -> str:
    return "vne_scene_{}_start".format(_base32_token(scene_id))


def scene_end_label(scene_id: str) -> str:
    return "vne_scene_{}_end".format(_base32_token(scene_id))


def entry_label(scene_id: str, entry_id: str) -> str:
    return "vne_scene_{}_entry_{}".format(
        _base32_token(scene_id), _base32_token(entry_id)
    )


def _escape_ordered_text(text: str) -> str:
    """Escape an authored string for Ren'Py double-quoted text.

    Normalizes CRLF/CR -> LF, rejects Unicode control characters (category Cc)
    except the normalized LF, flattens LF to a single ASCII space, then escapes
    backslash, quote, and Ren'Py interpolation brackets in a deterministic safe
    order. Never inserts raw user text as Ren'Py/Python source.
    """
    if not isinstance(text, str):
        raise OrderedExportError("text must be a string")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in normalized:
        if ch != "\n" and unicodedata.category(ch) == "Cc":
            raise OrderedExportError(
                "control character U+{:04X} is not allowed".format(ord(ch))
            )
    flattened = normalized.replace("\n", " ")
    return (
        flattened
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("[", "[[")
        .replace("{", "{{")
        .replace("\u3010", "\u3010\u3010")  # 【 -> 【【
    )


def _validate_reading_mode(reading_mode: str) -> None:
    if reading_mode not in READING_MODES:
        raise OrderedExportError(
            "unsupported reading_mode {!r}; expected one of {}".format(
                reading_mode, READING_MODES
            )
        )


def _validate_character_symbols(
    character_symbols: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(character_symbols, Mapping):
        raise OrderedExportError("character_symbols must be a Mapping")
    symbols: dict[str, str] = {}
    seen: dict[str, str] = {}
    for character_id, symbol in character_symbols.items():
        if not isinstance(character_id, str) or character_id == "":
            raise OrderedExportError("character_symbols keys must be non-empty strings")
        if not isinstance(symbol, str):
            raise OrderedExportError("character_symbols values must be strings")
        if _SYMBOL_RE.fullmatch(symbol) is None:
            raise OrderedExportError(
                "character symbol {!r} is not a valid identifier".format(symbol)
            )
        if symbol in _RESERVED_SYMBOLS:
            raise OrderedExportError(
                "character symbol {!r} is a reserved keyword".format(symbol)
            )
        if symbol in seen:
            raise OrderedExportError(
                "character symbols {} and {} map to the same symbol {!r}".format(
                    seen[symbol], character_id, symbol
                )
            )
        seen[symbol] = character_id
        symbols[character_id] = symbol
    return symbols


def _validate_known_scene_ids(ass: OrderedASS, known_scene_ids: frozenset[str]) -> None:
    if not isinstance(known_scene_ids, frozenset):
        raise OrderedExportError("known_scene_ids must be a frozenset[str]")
    for sid in known_scene_ids:
        if not isinstance(sid, str) or sid == "":
            raise OrderedExportError("known_scene_ids must contain non-empty strings")
    if ass.scene_id not in known_scene_ids:
        raise OrderedExportError(
            "scene_id {!r} is not in known_scene_ids".format(ass.scene_id)
        )
    for entry in ass.ordered_flow:
        if isinstance(entry, ChoiceEntry):
            for option in entry.options:
                target = option.target
                if target is not None and target.target_kind == TARGET_KIND_SCENE:
                    if target.target_id not in known_scene_ids:
                        raise OrderedExportError(
                            "SCENE target {!r} is not in known_scene_ids".format(
                                target.target_id
                            )
                        )
        elif isinstance(entry, (TextEntry, VisualChangeEvent)):
            next_target = entry.next_target
            if next_target is not None and next_target.target_kind == TARGET_KIND_SCENE:
                if next_target.target_id not in known_scene_ids:
                    raise OrderedExportError(
                        "next_target SCENE {!r} is not in known_scene_ids".format(
                            next_target.target_id
                        )
                    )


def _validate_resolved_assets(
    resolved_assets: Mapping[str, ResolvedAsset],
) -> dict[str, ResolvedAsset]:
    if not isinstance(resolved_assets, Mapping):
        raise OrderedExportError("resolved_assets must be a Mapping[str, ResolvedAsset]")
    snapshot: dict[str, ResolvedAsset] = {}
    for asset_id, resolved in resolved_assets.items():
        if not isinstance(asset_id, str) or asset_id == "":
            raise OrderedExportError("resolved_assets keys must be non-empty strings")
        if not isinstance(resolved, ResolvedAsset):
            raise OrderedExportError("resolved_assets values must be ResolvedAsset")
        if not isinstance(resolved.renpy_image_name, str) or resolved.renpy_image_name.strip() == "":
            raise OrderedExportError(
                "ResolvedAsset {!r} has an empty renpy_image_name".format(asset_id)
            )
        snapshot[asset_id] = resolved
    return snapshot


def _transition_line(transition: str | None) -> str | None:
    if transition in _TRANSITION_NO_LINE:
        return None
    if transition in _TRANSITION_WITH_LINE:
        return _TRANSITION_WITH_LINE[transition]
    raise OrderedExportError(
        "unsupported transition {!r}; must be one of None/'cut'/'fade'/'dissolve'".format(
            transition
        )
    )


def _render_text_entry(
    entry: TextEntry,
    reading_mode: str,
    symbols: dict[str, str],
    lines: list[str],
) -> None:
    if entry.presentation == TEXT_PRESENTATION_NARRATIVE:
        lines.append('    narrator "{}"'.format(_escape_ordered_text(entry.text)))
    elif entry.presentation == TEXT_PRESENTATION_DIALOGUE:
        symbol = symbols.get(entry.character_id)
        if symbol is None:
            raise OrderedExportError(
                "DIALOGUE character {!r} has no character_symbols mapping".format(
                    entry.character_id
                )
            )
        lines.append('    {} "{}"'.format(symbol, _escape_ordered_text(entry.text)))
    elif entry.presentation == TEXT_PRESENTATION_THOUGHT:
        visible = _THOUGHT_VISIBLE[reading_mode][entry.thought_visibility]
        if visible:
            lines.append('    narrator "{}"'.format(_escape_ordered_text(entry.text)))
        else:
            # Preserve the entry control-flow anchor for ENTRY jump targets.
            lines.append("    pass")
    else:
        raise OrderedExportError(
            "unsupported presentation {!r}".format(entry.presentation)
        )


def _render_next_target(
    next_target: ChoiceTarget | None,
    ass: OrderedASS,
    entry_ids: frozenset[str],
    lines: list[str],
) -> None:
    """Render an entry's optional explicit successor (OD-ORDEREDASS-CONTROL-FLOW-01).

    ``None`` emits nothing -- the existing implicit ordered-flow fallthrough is
    preserved exactly as before. This performs no branch-boundary inference of
    its own: it only ever emits the one jump the model already names.
    """
    if next_target is None:
        return
    if next_target.target_kind == TARGET_KIND_ENTRY:
        if next_target.target_id not in entry_ids:
            raise OrderedExportError(
                "next_target ENTRY {!r} does not exist in this OrderedASS".format(
                    next_target.target_id
                )
            )
        lines.append(
            "    jump {}".format(entry_label(ass.scene_id, next_target.target_id))
        )
    elif next_target.target_kind == TARGET_KIND_SCENE:
        lines.append("    jump {}".format(scene_start_label(next_target.target_id)))
    elif next_target.target_kind == TARGET_KIND_END:
        lines.append("    jump {}".format(scene_end_label(ass.scene_id)))
    else:
        raise OrderedExportError(
            "unsupported next_target kind {!r}".format(next_target.target_kind)
        )


def _render_choice_entry(
    ass: OrderedASS,
    entry: ChoiceEntry,
    entry_ids: frozenset[str],
    lines: list[str],
) -> None:
    if entry.prompt is not None:
        lines.append('    narrator "{}"'.format(_escape_ordered_text(entry.prompt)))
    lines.append("    menu:")
    for option in entry.options:
        lines.append('        "{}":'.format(_escape_ordered_text(option.display_text)))
        target = option.target
        if target is None:
            raise OrderedExportError(
                "choice option {!r} has no target".format(option.option_id)
            )
        if target.target_kind == TARGET_KIND_ENTRY:
            if target.target_id not in entry_ids:
                raise OrderedExportError(
                    "ENTRY target {!r} does not exist in this OrderedASS".format(
                        target.target_id
                    )
                )
            lines.append(
                "            jump {}".format(entry_label(ass.scene_id, target.target_id))
            )
        elif target.target_kind == TARGET_KIND_SCENE:
            lines.append(
                "            jump {}".format(scene_start_label(target.target_id))
            )
        else:
            raise OrderedExportError(
                "unsupported target kind {!r}".format(target.target_kind)
            )


def _render_visual_entry(
    entry: VisualChangeEvent,
    assets: dict[str, ResolvedAsset],
    lines: list[str],
) -> None:
    with_line = _transition_line(entry.transition)
    if entry.operation == VISUAL_OP_SET:
        resolved = assets.get(entry.asset_id)
        if resolved is None:
            raise OrderedExportError(
                "Visual SET asset_id {!r} is not in resolved_assets".format(entry.asset_id)
            )
        lines.append(
            "    show {} as {}".format(resolved.renpy_image_name, VISUAL_SLOT_ALIAS)
        )
    elif entry.operation == VISUAL_OP_CLEAR:
        lines.append("    hide {}".format(VISUAL_SLOT_ALIAS))
    else:
        raise OrderedExportError(
            "unsupported visual operation {!r}".format(entry.operation)
        )
    if with_line is not None:
        lines.append("    {}".format(with_line))


def render_ordered_ass(
    ass: OrderedASS,
    *,
    reading_mode: ReadingMode,
    character_symbols: Mapping[str, str],
    known_scene_ids: frozenset[str],
    resolved_assets: Mapping[str, ResolvedAsset],
) -> str:
    """Render an OrderedASS into a deterministic Ren'Py source string.

    Pure renderer: returns a string only. Fails closed before returning any
    source on any invalid input. See module docstring for the exact boundary.
    """
    if not isinstance(ass, OrderedASS):
        raise OrderedExportError("ass must be an OrderedASS (ass/0.2)")
    _validate_reading_mode(reading_mode)
    symbols = _validate_character_symbols(character_symbols)
    _validate_known_scene_ids(ass, known_scene_ids)
    assets = _validate_resolved_assets(resolved_assets)

    entry_ids = frozenset(e.entry_id for e in ass.ordered_flow)

    lines: list[str] = []
    lines.append("# OrderedASS scene {}".format(ass.scene_id))
    lines.append("# reading_mode: {}".format(reading_mode))
    lines.append("")

    first_entry = ass.ordered_flow[0]
    lines.append("label {}:".format(scene_start_label(ass.scene_id)))
    lines.append(
        "    jump {}".format(entry_label(ass.scene_id, first_entry.entry_id))
    )

    for entry in ass.ordered_flow:
        lines.append("")
        lines.append("label {}:".format(entry_label(ass.scene_id, entry.entry_id)))
        if isinstance(entry, TextEntry):
            _render_text_entry(entry, reading_mode, symbols, lines)
            _render_next_target(entry.next_target, ass, entry_ids, lines)
        elif isinstance(entry, ChoiceEntry):
            _render_choice_entry(ass, entry, entry_ids, lines)
        elif isinstance(entry, VisualChangeEvent):
            _render_visual_entry(entry, assets, lines)
            _render_next_target(entry.next_target, ass, entry_ids, lines)
        else:
            raise OrderedExportError(
                "unsupported entry type {!r}".format(type(entry).__name__)
            )

    lines.append("")
    lines.append("label {}:".format(scene_end_label(ass.scene_id)))
    lines.append("    return")

    return "\n".join(lines) + "\n"
