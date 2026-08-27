#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the playable exporter's optional scene-level visual hook.

Proves:
  * text-only exporter output is byte-identical when no visual input is given
    (explicit ``None`` keywords behave exactly like omitting them);
  * an explicit ``ResolvedAsset`` + statement kind inserts exactly one
    modifier-free visual line immediately after the scene label and before any
    position hook / narrative content;
  * the hook stays generic (``show`` works too) and fails closed on a bad kind.

No committed ``.rpy`` file is written: scene JSON is rendered from an
in-repo temp dir that is cleaned up automatically.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import renpy_v2_playable_exporter as exporter  # noqa: E402
from services.production_media_asset_binding import ResolvedAsset  # noqa: E402
from tools.vne_to_renpy.visual_statement_emitter import (  # noqa: E402
    VisualStatementError,
)

_ACTIVE_TMP_DIRS: list = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup_repo_temp_dirs():
    yield
    for ctx in list(_ACTIVE_TMP_DIRS):
        try:
            ctx.cleanup()
        except Exception:
            pass
    _ACTIVE_TMP_DIRS.clear()


def _scene_json(scene: dict) -> Path:
    ctx = tempfile.TemporaryDirectory(prefix="vne_emit_hook_", dir=str(_REPO_ROOT))
    _ACTIVE_TMP_DIRS.append(ctx)
    path = Path(ctx.name) / "scene.v2.json"
    path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")
    return path


_SCENE = {
    "id": "SC_017",
    "name": "Сергей пишет снова",
    "schema_version": "2.0",
    "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
    "entry_beats": [
        {"beat_id": "e1", "type": "narration", "narration": "Телефон загорается."},
    ],
    "choice_points": [
        {
            "id": "cp1",
            "prompt": "Что делает Кира?",
            "branches": [
                {"id": "1a", "option_text": "Показывает сразу.", "beats": [], "effects": {}},
            ],
        }
    ],
    "safety": {"content_rating": "PG-13"},
}

_KIRA = ResolvedAsset(
    asset_id="kira_yoga_hall_pilot_image_01",
    relative_path=(
        "novel/game/images/story/characters/kira/kira_yoga_hall_pilot_image_01.png"
    ),
    renpy_image_name="kira_yoga_hall_pilot_image_01",
)


# 11. TEXT_ONLY_EXPORTER_OUTPUT_UNCHANGED
def test_text_only_output_unchanged_without_visual_input():
    path = _scene_json(_SCENE)
    baseline = exporter.render_scene(_SCENE, path)
    explicit_none = exporter.render_scene(
        _SCENE, path, visual_asset=None, visual_statement_kind=None
    )
    assert explicit_none == baseline
    assert "\n    scene " not in baseline
    assert "\n    show " not in baseline
    assert "scene story" not in baseline
    assert "show story" not in baseline


# 12. VISUAL_LINE_INSERTED_AFTER_LABEL_BEFORE_STORY_CONTENT
def test_visual_line_inserted_after_label_before_story_content():
    path = _scene_json(_SCENE)
    text = exporter.render_scene(
        _SCENE, path, visual_asset=_KIRA, visual_statement_kind="scene"
    )

    label_idx = text.find("label sc_017_v2_start:")
    visual_idx = text.find(
        "    scene kira_yoga_hall_pilot_image_01"
    )
    set_beat_idx = text.find("_vne_aside_set_scene_beat")
    first_narrator_idx = text.find("narrator ")

    assert label_idx >= 0
    assert visual_idx >= 0
    assert set_beat_idx >= 0
    assert first_narrator_idx >= 0
    assert label_idx < visual_idx < set_beat_idx < first_narrator_idx

    # exactly one visual line, on its own line, with no extra modifiers
    assert text.count("scene kira_yoga_hall_pilot_image_01") == 1
    visual_line = text.splitlines()[text[:visual_idx].count("\n")]
    assert visual_line == "    scene kira_yoga_hall_pilot_image_01"
    for forbidden in (" with ", " at ", " onlayer ", " zorder ", " behind "):
        assert forbidden not in visual_line
    assert "hide " not in text


# 13 (through the real hook). GENERIC show semantics reachable, still generic.
def test_generic_show_via_exporter_hook():
    path = _scene_json(_SCENE)
    bg = ResolvedAsset(
        asset_id="some_bg",
        relative_path="novel/game/images/story/cg/abc.png",
        renpy_image_name="abc",
    )
    text = exporter.render_scene(
        _SCENE, path, visual_asset=bg, visual_statement_kind="show"
    )
    assert "\n    show abc\n" in text
    assert "\n    scene abc\n" not in text


def test_exporter_hook_fails_closed_on_bad_kind():
    path = _scene_json(_SCENE)
    with pytest.raises(VisualStatementError):
        exporter.render_scene(
            _SCENE, path, visual_asset=_KIRA, visual_statement_kind="reveal"
        )
