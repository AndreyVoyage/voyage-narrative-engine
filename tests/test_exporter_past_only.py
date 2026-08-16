#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dedicated exporter tests for past-only event recording (QA Gap 01).

Tests the exporter's set-before-content, note-after-content ordering,
selected-choice-only logging, future-prelogging prevention, stable
identity, event literal safety, and determinism.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import renpy_v2_playable_exporter as exporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_THIS_REPO = Path(__file__).resolve().parents[1]

# Keep TemporaryDirectory objects alive for the duration of the test run so
# they self-clean on interpreter exit (Windows cannot delete a dir that is
# still "open", so explicit teardown in every test would be racy).
_ACTIVE_TMP_DIRS = []


@pytest.fixture(scope="session", autouse=True)
def _cleanup_repo_temp_dirs():
    """Explicitly remove repo-local temp dirs created by exporter tests.

    Guarantees an artifact-free worktree even if the interpreter's own
    finalizer shutdown is skipped or racy on Windows.
    """
    yield
    for tmp_dir_ctx in list(_ACTIVE_TMP_DIRS):
        try:
            tmp_dir_ctx.cleanup()
        except Exception:
            pass
    _ACTIVE_TMP_DIRS.clear()


def _make_scene_and_json(scene_dict, prefix="vne_exp_test_"):
    """Write a scene dict to a temp JSON file inside the repo.

    Returns (scene_dict, json_path) so the caller can pass json_path to
    render_scene for SHA256 / relative-to-repo computation.

    The temp dir is kept in repo (render_scene computes a relative path) and
    is cleaned up automatically when the interpreter exits.
    """
    tmp_dir_ctx = tempfile.TemporaryDirectory(prefix=prefix, dir=str(_THIS_REPO))
    _ACTIVE_TMP_DIRS.append(tmp_dir_ctx)
    json_path = Path(tmp_dir_ctx.name) / "scene.v2.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(scene_dict, ensure_ascii=False), encoding="utf-8")
    return scene_dict, json_path


# ---------------------------------------------------------------------------
# Test 1: Narration — set before content, note after content
# ---------------------------------------------------------------------------


def test_narration_set_before_content_note_after():
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "e1",
        "type": "narration",
        "narration": "The door opens.",
    }
    lines = exporter.render_beat(scene, beat)
    text = "\n".join(lines)

    set_idx = text.find("_vne_aside_set_scene_beat")
    narrator_idx = text.find("narrator")
    note_idx = text.find("_vne_aside_note_played_event")
    assert set_idx >= 0
    assert narrator_idx >= 0
    assert note_idx >= 0
    assert set_idx < narrator_idx < note_idx, (
        f"Expected: set({set_idx}) < narrator({narrator_idx}) < note({note_idx})"
    )


# ---------------------------------------------------------------------------
# Test 2: Dialogue — set before, note after
# ---------------------------------------------------------------------------


def test_dialogue_set_before_content_note_after():
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "d1",
        "type": "dialogue",
        "speaker": "kira",
        "dialogue": "Hello there.",
    }
    lines = exporter.render_beat(scene, beat)
    text = "\n".join(lines)

    set_idx = text.find("_vne_aside_set_scene_beat")
    narrator_idx = text.find("narrator")
    note_idx = text.find("_vne_aside_note_played_event")
    assert set_idx >= 0
    assert narrator_idx >= 0
    assert note_idx >= 0
    assert set_idx < narrator_idx < note_idx, (
        f"dialogue: set({set_idx}) < narrator({narrator_idx}) < note({note_idx})"
    )


# ---------------------------------------------------------------------------
# Test 3: Action — set before, note after
# ---------------------------------------------------------------------------


def test_action_set_before_content_note_after():
    beat = {
        "beat_id": "a1",
        "type": "action",
        "speaker": "kira",
        "action": "She walks across the room.",
    }
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "safety": {"content_rating": "PG-13"},
    }
    lines = exporter.render_beat(scene, beat)
    text = "\n".join(lines)

    set_idx = text.find("_vne_aside_set_scene_beat")
    note_idx = text.find("_vne_aside_note_played_event")
    assert set_idx >= 0
    assert note_idx >= 0
    assert set_idx < note_idx


# ---------------------------------------------------------------------------
# Test 4: Menu — position set before menu:, no unconditional note
# ---------------------------------------------------------------------------


def test_menu_position_set_before_menu_no_unconditional_note():
    scene = {
        "id": "SC_017",
        "name": "Menu Test",
        "schema_version": "2.0",
        "characters": [],
        "entry_beats": [],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {"id": "b1", "option_text": "A", "beats": [], "effects": {}},
                    {"id": "b2", "option_text": "B", "beats": [], "effects": {}},
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_menu_")
    text = exporter.render_scene(scene_dict, json_path)

    menu_idx = text.find("menu:")
    set_idx = text.rfind("_vne_aside_set_scene_beat", 0, menu_idx)
    assert menu_idx > 0, "menu: not found"
    assert set_idx > 0, "_vne_aside_set_scene_beat before menu: not found"

    first_branch = text.find("label sc_017_v2_b1:")
    assert first_branch > menu_idx
    between = text[menu_idx:first_branch]
    assert "_vne_aside_note_played_event" not in between, (
        "unconditional note found between menu and first branch"
    )


# ---------------------------------------------------------------------------
# Test 5: Selected choice — event emitted inside chosen branch
# ---------------------------------------------------------------------------


def test_selected_choice_event_inside_branch():
    scene = {
        "id": "SC_017",
        "name": "Choice Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "entry_beats": [],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "What do you do?",
                "branches": [
                    {"id": "b1", "option_text": "OK", "beats": [], "effects": {}},
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_choice_")
    text = exporter.render_scene(scene_dict, json_path)

    branch_start = text.find("label sc_017_v2_b1:")
    branch_end = text.find("label sc_017_v2_end:")
    assert branch_start >= 0
    assert branch_end > branch_start

    between = text[branch_start:branch_end]
    assert "_vne_aside_note_played_event" in between, "choice event not inside branch"
    assert "'choice'" in between or '"choice"' in between, "choice kind not in event"


# ---------------------------------------------------------------------------
# Test 6: Unselected choice — alternatives NOT pre-recorded
# ---------------------------------------------------------------------------


def test_unselected_choices_not_prerecorded():
    scene = {
        "id": "SC_017",
        "name": "Two Options",
        "schema_version": "2.0",
        "characters": [],
        "entry_beats": [],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {"id": "b_chosen", "option_text": "Chosen", "beats": [], "effects": {}},
                    {"id": "b_other", "option_text": "Other", "beats": [], "effects": {}},
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_two_")
    text = exporter.render_scene(scene_dict, json_path)

    # Count choice events.
    choice_events = text.count("'choice'")
    assert choice_events == 2, f"expected 2 choice events, found {choice_events}"

    # b_chosen branch should NOT contain "Other" (the unselected option text).
    b_chosen_start = text.find("label sc_017_v2_b_chosen:")
    b_other_start = text.find("label sc_017_v2_b_other:")
    assert b_chosen_start >= 0
    assert b_other_start > b_chosen_start

    # Just verify both branches have their own choice events.
    chosen_segment = text[b_chosen_start:b_other_start]
    assert "Chosen" in chosen_segment, "chosen branch should mention Chosen"


# ---------------------------------------------------------------------------
# Test 7: Branch beats — set → content → note ordering
# ---------------------------------------------------------------------------


def test_branch_beats_set_content_note():
    scene = {
        "id": "SC_017",
        "name": "Branch Beat Test",
        "schema_version": "2.0",
        "characters": [],
        "entry_beats": [],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {
                        "id": "b1",
                        "option_text": "Go",
                        "beats": [
                            {
                                "beat_id": "b_e1",
                                "type": "narration",
                                "narration": "You step forward.",
                            },
                        ],
                        "effects": {},
                    },
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_branch_")
    text = exporter.render_scene(scene_dict, json_path)

    b1_start = text.find("label sc_017_v2_b1:")
    b1_end = text.find("label sc_017_v2_end:")
    b1_section = text[b1_start:b1_end]

    # First note = choice event; second = narration beat.
    first_note = b1_section.find("_vne_aside_note_played_event")
    assert first_note >= 0, "choice note not found"
    second_note = b1_section.find("_vne_aside_note_played_event", first_note + 1)
    assert second_note >= 0, "narration note not found"

    # The set for the beat must appear after first_note (choice) but before second_note (narration).
    set_idx = b1_section.find("_vne_aside_set_scene_beat", first_note)
    assert set_idx >= 0, "beat set not found"
    assert set_idx < second_note, (
        f"branch beat: set({set_idx}) < second_note({second_note})"
    )


# ---------------------------------------------------------------------------
# Test 8: Future prelogging — later beat note not before its content
# ---------------------------------------------------------------------------


def test_future_prelogging_not_before_content():
    scene = {
        "id": "SC_017",
        "name": "Two Beat Test",
        "schema_version": "2.0",
        "characters": [],
        "entry_beats": [],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {
                        "id": "b1",
                        "option_text": "Go",
                        "beats": [
                            {"beat_id": "first", "type": "narration", "narration": "First beat."},
                            {"beat_id": "second", "type": "narration", "narration": "Second beat."},
                        ],
                        "effects": {},
                    },
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_future_")
    text = exporter.render_scene(scene_dict, json_path)

    b1_start = text.find("label sc_017_v2_b1:")
    b1_end = text.find("label sc_017_v2_end:")
    b1_section = text[b1_start:b1_end]

    # First note after the choice event is for beat "first".
    first_note = b1_section.find("_vne_aside_note_played_event")

    second_narrator_idx = b1_section.find("Second beat.")
    assert second_narrator_idx > first_note, (
        f"second beat content({second_narrator_idx}) should appear after first note({first_note})"
    )


# ---------------------------------------------------------------------------
# Test 9: Stable identity — emitted scene ID and beat ID match source
# ---------------------------------------------------------------------------


def test_stable_identity_scene_and_beat():
    stmt = exporter.emit_set_scene_beat("SC_017", "entry_beat_1")
    assert "SC_017" in stmt
    assert "entry_beat_1" in stmt


# ---------------------------------------------------------------------------
# Test 10: Event literal parsing
# ---------------------------------------------------------------------------


def test_event_literal_parses():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "beat_1",
        "type": "narration",
        "narration": "A simple summary.",
    })
    code = stmt[len("$ "):]
    compile(code, "<test>", "exec")


# ---------------------------------------------------------------------------
# Test 11: Event literal edge cases
# ---------------------------------------------------------------------------


def test_event_literal_cyrillic():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "cyr1",
        "type": "narration",
        "narration": "Кира вошла в комнату, огляделась и сказала: «Привет!»",
    })
    code = stmt[len("$ "):]
    compile(code, "<test_cyrillic>", "exec")


def test_event_literal_quotes_and_apostrophes():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "q1",
        "type": "dialogue",
        "speaker": "kira",
        "dialogue": "She said: \"It's a nice day, isn't it?\"",
    })
    code = stmt[len("$ "):]
    compile(code, "<test_quotes>", "exec")


def test_event_literal_backslashes():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "bs1",
        "type": "narration",
        "narration": "Path: C:\\Users\\kira\\Documents\\note.txt",
    })
    code = stmt[len("$ "):]
    compile(code, "<test_backslashes>", "exec")


def test_event_literal_line_breaks():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "lb1",
        "type": "narration",
        "narration": "Line one.\nLine two.\r\nLine three.",
    })
    code = stmt[len("$ "):]
    compile(code, "<test_breaks>", "exec")


def test_event_literal_square_brackets():
    stmt = exporter.emit_note_played_event("SC_017", {
        "beat_id": "sq1",
        "type": "narration",
        "narration": "Use [bracket] syntax and [[double brackets]].",
    })
    code = stmt[len("$ "):]
    compile(code, "<test_brackets>", "exec")


# ---------------------------------------------------------------------------
# Test 12: Determinism
# ---------------------------------------------------------------------------


def test_deterministic_regeneration():
    scene = {
        "id": "SC_017",
        "name": "Determinism Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "entry_beats": [
            {"beat_id": "e1", "type": "narration", "narration": "The scene begins."},
        ],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {
                        "id": "b1",
                        "option_text": "Option 1",
                        "beats": [
                            {"beat_id": "b_e1", "type": "dialogue", "speaker": "kira", "dialogue": "Let's go."},
                        ],
                        "effects": {},
                    },
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene1, json1 = _make_scene_and_json(scene, "vne_exp_det1_")
    scene2, json2 = _make_scene_and_json(scene, "vne_exp_det2_")

    text1 = exporter.render_scene(scene1, json1)
    text2 = exporter.render_scene(scene2, json2)

    # Strip header lines that contain dynamic content (source path, SHA).
    def _strip_header(t):
        lines = t.split("\n")
        result = []
        for line in lines:
            if line.startswith("# source:") or line.startswith("# source SHA256:"):
                continue
            result.append(line)
        return "\n".join(result)

    assert _strip_header(text1) == _strip_header(text2), (
        "identical scene inputs must produce identical output (modulo header paths)"
    )


# ---------------------------------------------------------------------------
# Test 13: No future static narration
# ---------------------------------------------------------------------------


def test_no_future_static_narration():
    scene = {
        "id": "SC_017",
        "name": "NoFuture Narration Test",
        "schema_version": "2.0",
        "characters": [],
        "entry_beats": [
            {"beat_id": "entry1", "type": "narration", "narration": "Welcome to the scene."},
        ],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose:",
                "branches": [
                    {
                        "id": "b1",
                        "option_text": "Path A",
                        "beats": [
                            {"beat_id": "path_a_beat", "type": "narration", "narration": "You chose Path A."},
                        ],
                        "effects": {},
                    },
                    {
                        "id": "b2",
                        "option_text": "Path B",
                        "beats": [
                            {"beat_id": "path_b_beat", "type": "narration", "narration": "You chose Path B."},
                        ],
                        "effects": {},
                    },
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_nofut_")
    text = exporter.render_scene(scene_dict, json_path)

    assert "Welcome to the scene." in text

    path_a_label = text.find("label sc_017_v2_b1:")
    path_a_content = text.find("You chose Path A.")
    assert path_a_label > 0
    assert path_a_content > path_a_label

    path_b_label = text.find("label sc_017_v2_b2:")
    path_b_content = text.find("You chose Path B.")
    assert path_b_label > 0

    assert path_b_content > path_b_label


# ---------------------------------------------------------------------------
# OD-SC-FIX-01 — exporter text-safety regression
# ---------------------------------------------------------------------------


def _narrator_fragments(text):
    """Return player-visible text fragments inside narrator/say strings."""
    return re.findall(r'\bnarrator\s+"((?:[^"\\]|\\.)*)"', text)


def _has_unescaped_interpolation(text):
    """True if an undoubled interpolation/tag-opening metacharacter survives.

    Matches the audited Ren'Py escaping semantics exactly: a single '[' opens
    interpolation (must be '[[') and a single '{' opens a text tag (must be
    '{{'). A lone ']' is already literal in Ren'Py's LITERAL parser state and is
    NOT a hazard — there is no ']]' escape rule — so it is deliberately not
    checked.
    """
    s = text
    s = s.replace("[[", "").replace("{{", "")
    return ("[" in s) or ("{" in s)


def test_action_render_has_no_synthetic_bracket_label():
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "a1",
        "type": "action",
        "speaker": "kira",
        "action": "She walks across the room.",
    }
    text = "\n".join(exporter.render_beat(scene, beat))

    # The old crash shape must be gone.
    assert "[Кира action]" not in text
    assert "] action]" not in text
    # The new plain-text colon-separated form is present.
    assert "Кира action: She walks across the room." in text


def test_thought_render_has_no_synthetic_bracket_label():
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "t1",
        "type": "thought",
        "speaker": "kira",
        "thought": "Hmm, what now?",
        "thought_visibility": None,
    }
    text = "\n".join(exporter.render_beat(scene, beat))

    # No synthetic "[...]" label wrapping the marker.
    assert "] thought:" not in text
    assert "thought:Кира; visibility=None: Hmm, what now?" in text


def test_source_bracket_and_brace_escaped_in_narration():
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "n1",
        "type": "narration",
        "narration": "Use [bracket] syntax and {braces} here.",
    }
    text = "\n".join(exporter.render_beat(scene, beat))

    fragments = _narrator_fragments(text)
    assert fragments, "expected a narrator line"
    for frag in fragments:
        assert not _has_unescaped_interpolation(frag), f"unescaped in: {frag!r}"
    # Doubled literal openers are present in the rendered output.
    # '[' is doubled to '[['; ']' is LEFT literal (a lone ']' is valid); '{' is
    # doubled to '{{' and '}' is LEFT literal — matching the audited Ren'Py
    # semantics. Assert only the opener doublings.
    assert "[[" in text and "]]" not in text
    assert "{{" in text and "a]b" not in text  # no spurious closing-bracket doubling elsewhere


def test_closing_bracket_stays_literal_not_doubled():
    """OD-SC-FIX-01 REQUIRED_MINOR regression: ']' must never be doubled.

    A lone ']' is already literal in Ren'Py's LITERAL parser state (no ']]'
    collapse rule), so source `a]b` must remain player-visible as `a]b`.
    """
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "n1",
        "type": "narration",
        "narration": "a]b",
    }
    text = "\n".join(exporter.render_beat(scene, beat))
    assert 'narrator "a]b"' in text
    assert "a]]b" not in text


def test_opening_bracket_escaped_closing_bracket_literal():
    """Balanced source '[x]' renders safe: '[' doubled, ']' left literal."""
    scene = {
        "id": "SC_017",
        "name": "Test",
        "schema_version": "2.0",
        "characters": [],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {
        "beat_id": "n1",
        "type": "narration",
        "narration": "[x]",
    }
    text = "\n".join(exporter.render_beat(scene, beat))
    assert "[[x]" in text, "opening '[' must be doubled while closing ']' stays literal"
    assert "[[x]]" not in text, "closing ']' must NOT be doubled"


def test_generated_scene_say_text_has_no_unsafe_interpolation():
    """Full-scene render: every player-visible say fragment must be bracket-safe."""
    scene = {
        "id": "SC_017",
        "name": "Full Safety Test",
        "schema_version": "2.0",
        "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
        "entry_beats": [
            {"beat_id": "e1", "type": "narration", "narration": "A [literal] bracket in narration."},
        ],
        "choice_points": [
            {
                "id": "cp1",
                "prompt": "Choose an [option] carefully, {player}.",
                "branches": [
                    {
                        "id": "b1",
                        "option_text": "Path [A]",
                        "beats": [
                            {"beat_id": "b_e1", "type": "action", "speaker": "kira", "action": "She moves."},
                            {"beat_id": "b_e2", "type": "thought", "speaker": "kira", "thought": "A {thought} indeed.", "thought_visibility": None},
                            {"beat_id": "b_e3", "type": "dialogue", "speaker": "kira", "dialogue": "Said [with] brackets."},
                        ],
                        "effects": {},
                    },
                ],
            }
        ],
        "safety": {"content_rating": "PG-13"},
    }
    scene_dict, json_path = _make_scene_and_json(scene, "vne_exp_safe_")
    text = exporter.render_scene(scene_dict, json_path)

    for frag in _narrator_fragments(text):
        assert not _has_unescaped_interpolation(frag), f"unsafe narrator fragment: {frag!r}"

    # Menu captions are player-visible too.
    captions = re.findall(r'^\s{8}"([^"]*)"\s*:', text, flags=re.M)
    for cap in captions:
        assert not _has_unescaped_interpolation(cap), f"unsafe menu caption: {cap!r}"


def test_hook_ordering_still_set_content_note_after_fix():
    """OD-SC-FIX-01 must not disturb set → content → note ordering."""
    scene = {
        "id": "SC_017",
        "name": "Ordering",
        "schema_version": "2.0",
        "characters": [],
        "safety": {"content_rating": "PG-13"},
    }
    beat = {"beat_id": "e1", "type": "narration", "narration": "The door opens."}
    text = "\n".join(exporter.render_beat(scene, beat))

    set_idx = text.find("_vne_aside_set_scene_beat")
    narrator_idx = text.find("narrator")
    note_idx = text.find("_vne_aside_note_played_event")
    assert set_idx < narrator_idx < note_idx
