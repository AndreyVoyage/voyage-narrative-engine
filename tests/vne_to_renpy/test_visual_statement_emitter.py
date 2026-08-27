#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the pure VNE -> Ren'Py visual statement emitter.

Proves the emitter is generic (statement kind is always explicit, never
inferred from asset identity), emits exactly one modifier-free Ren'Py visual
line for the supported kinds, fails closed on unsupported kinds and malformed
image names, and performs no persistence / no filesystem write.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.production_media_asset_binding import ResolvedAsset  # noqa: E402
from tools.vne_to_renpy.visual_statement_emitter import (  # noqa: E402
    SUPPORTED_STATEMENT_KINDS,
    VisualStatementError,
    emit_visual_statement,
)


def _resolved(
    image_name: str,
    *,
    asset_id: str = "asset_x",
    relative_path: str = "novel/game/images/story/cg/x.png",
) -> ResolvedAsset:
    return ResolvedAsset(
        asset_id=asset_id,
        relative_path=relative_path,
        renpy_image_name=image_name,
    )


# 1. GENERIC_SCENE
def test_generic_scene_statement():
    out = emit_visual_statement(_resolved("story backgrounds hall"), statement_kind="scene")
    assert out == ["scene story backgrounds hall"]


# 2. GENERIC_SHOW
def test_generic_show_statement():
    out = emit_visual_statement(_resolved("story cg abc"), statement_kind="show")
    assert out == ["show story cg abc"]


# 3. REAL_KIRA
def test_real_kira_scene_statement():
    kira = ResolvedAsset(
        asset_id="kira_yoga_hall_pilot_image_01",
        relative_path=(
            "novel/game/images/story/characters/kira/"
            "kira_yoga_hall_pilot_image_01.png"
        ),
        renpy_image_name="story characters kira kira_yoga_hall_pilot_image_01",
    )
    out = emit_visual_statement(kira, statement_kind="scene")
    assert out == ["scene story characters kira kira_yoga_hall_pilot_image_01"]


# 4. UNSUPPORTED_KIND_FAILS
@pytest.mark.parametrize("kind", ["", "SCENE", "image", "scene ", None])
def test_unsupported_kind_fails_closed(kind):
    with pytest.raises(VisualStatementError):
        emit_visual_statement(_resolved("story cg abc"), statement_kind=kind)


# 5 + 6. EMPTY_NAME_FAILS / WHITESPACE_NAME_FAILS
@pytest.mark.parametrize("name", ["", " ", "   ", "\t"])
def test_empty_or_whitespace_image_name_fails_closed(name):
    with pytest.raises(VisualStatementError):
        emit_visual_statement(_resolved(name), statement_kind="scene")


# 7 + 8. SLASH_PATH_FAILS / BACKSLASH_PATH_FAILS
@pytest.mark.parametrize(
    "name",
    [
        "story/characters/kira/kira_yoga_hall_pilot_image_01",
        "story\\characters\\kira\\img",
    ],
)
def test_path_separator_in_image_name_fails_closed(name):
    with pytest.raises(VisualStatementError):
        emit_visual_statement(_resolved(name), statement_kind="scene")


# 9. EXTENSION_INPUT_FAILS
@pytest.mark.parametrize(
    "name",
    ["story cg abc.png", "story cg abc.jpg", "story cg abc.jpeg", "story cg abc.webp", "story cg abc.PNG"],
)
def test_extension_in_image_name_fails_closed(name):
    with pytest.raises(VisualStatementError):
        emit_visual_statement(_resolved(name), statement_kind="scene")


# 10. NO_KIRA_SPECIFIC_LOGIC — same image name, same line, regardless of
#     asset_id / relative_path; the verb is driven ONLY by statement_kind.
def test_no_identity_specific_branching():
    name = "story characters kira kira_yoga_hall_pilot_image_01"
    as_scene = emit_visual_statement(
        _resolved(
            name,
            asset_id="kira_yoga_hall_pilot_image_01",
            relative_path="novel/game/images/story/characters/kira/x.png",
        ),
        statement_kind="scene",
    )
    as_show = emit_visual_statement(
        _resolved(
            name,
            asset_id="totally_unrelated_id",
            relative_path="novel/game/images/story/backgrounds/y.png",
        ),
        statement_kind="show",
    )
    assert as_scene == ["scene " + name]
    assert as_show == ["show " + name]
    assert as_scene[0].split(" ", 1)[0] == "scene"
    assert as_show[0].split(" ", 1)[0] == "show"


# 13. NO_EXTRA_VISUAL_MODIFIERS
@pytest.mark.parametrize("kind", list(SUPPORTED_STATEMENT_KINDS))
def test_no_extra_visual_modifiers(kind):
    out = emit_visual_statement(_resolved("story cg abc"), statement_kind=kind)
    assert out == [f"{kind} story cg abc"]
    padded = f" {out[0]} "
    for forbidden in (" with ", " at ", " onlayer ", " zorder ", " behind ", " hide "):
        assert forbidden not in padded


# 14. NO_PERSISTENCE / NO REPO FILE WRITE FROM PURE EMITTER
def test_no_persistence_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_visual_statement(_resolved("story cg abc"), statement_kind="scene")
    assert result == ["scene story cg abc"]
    assert sorted(p.name for p in tmp_path.iterdir()) == []
    # deterministic, no mutation between calls
    assert emit_visual_statement(_resolved("story cg abc"), statement_kind="scene") == result
