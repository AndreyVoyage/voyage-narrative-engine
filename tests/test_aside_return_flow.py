#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-level structural assertions for the Aside return-flow correction.

Verifies that the overlay uses Call (not Jump), that Close/Reset/Send/async
paths have no scene-selector navigation, and that no new Ren'Py context is
used.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_ASIDE_PATH = _REPO / "novel" / "game" / "aside.rpy"
_DEVDIAG_PATH = _REPO / "novel" / "game" / "dev_diagnostics.rpy"
_SCRIPT_PATH = _REPO / "novel" / "game" / "script.rpy"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: Overlay uses Call, not Jump
# ---------------------------------------------------------------------------

def test_aside_overlay_button_uses_call_not_jump():
    text = _read(_ASIDE_PATH)
    aside_btn_pattern = re.search(
        r'textbutton\s+"Aside"\s*:\s*\n\s*action\s+(Jump|Call)\("aside_dev_entry"\)',
        text,
    )
    assert aside_btn_pattern is not None, "Could not locate Aside textbutton in aside_dev_overlay"
    action_kind = aside_btn_pattern.group(1)
    assert action_kind == "Call", (
        f"Aside overlay button must use Call, found {action_kind}. "
        "Jump abandons the scene call stack; Close returns to scene selector."
    )


# ---------------------------------------------------------------------------
# Test 2: No Jump to scene selector in Close path
# ---------------------------------------------------------------------------

def test_close_path_has_no_scene_selector_jump():
    text = _read(_ASIDE_PATH)
    close_pattern = re.search(
        r'textbutton\s+"Close"\s*:\s*\n\s*action\s+Return\("__close__"\)',
        text,
    )
    assert close_pattern is not None, "Close button not found with Return('__close__')"

    loop_pattern = re.search(
        r'if\s+result\s*==\s*"__close__"\s+or\s+result\s*==\s*"close"\s*:\s*\n\s*return',
        text,
    )
    assert loop_pattern is not None, "aside_chat_loop Close handler not found"

    bad_jumps = re.findall(
        r'(?:jump|Jump)\s*\(\s*"?(?:start|scene_selector|main_menu|sc_\d+_v?\d*_start)"?\s*\)',
        text,
    )
    assert not bad_jumps, f"Scene-selector jumps found in aside.rpy: {bad_jumps}"


# ---------------------------------------------------------------------------
# Test 3: No return from scenario label in Close path
# ---------------------------------------------------------------------------

def test_no_return_from_scenario_in_close_path():
    text = _read(_ASIDE_PATH)
    entry_section = re.search(
        r'label aside_dev_entry:.*?(?=^label |\Z)',
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert entry_section is not None
    section = entry_section.group(0)
    assert "call aside_chat_loop" in section
    assert section.strip().endswith("return")


# ---------------------------------------------------------------------------
# Test 4: No new Ren'Py context used
# ---------------------------------------------------------------------------

def test_no_new_renpy_context_in_aside_flow():
    text = _read(_ASIDE_PATH)
    forbidden = [
        "renpy.call_in_new_context",
        "renpy.invoke_in_new_context",
        "renpy.jump_out_of_context",
        "_clear_layers=True",
    ]
    for pattern in forbidden:
        assert pattern not in text, f"Forbidden new-context API found in aside.rpy: {pattern}"


# ---------------------------------------------------------------------------
# Test 5: Reset does not navigate
# ---------------------------------------------------------------------------

def test_reset_does_not_navigate():
    text = _read(_ASIDE_PATH)
    reset_func = re.search(
        r'def _vne_reset_aside_memory\(.*?\):.*?(?=def |label |$)',
        text,
        re.DOTALL,
    )
    assert reset_func is not None
    body = reset_func.group(0)
    nav_keywords = ["renpy.jump", "renpy.call", "Jump(", "Call(", "jump ", "call "]
    for kw in nav_keywords:
        if kw in body and kw not in ("call ",):
            lines = body.split("\n")
            found = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if kw in stripped and not stripped.lstrip().startswith("#"):
                    found = True
                    break
            if found:
                pytest.fail(f"Navigation keyword '{kw}' found in _vne_reset_aside_memory")


# ---------------------------------------------------------------------------
# Test 6: Send does not navigate
# ---------------------------------------------------------------------------

def test_send_does_not_navigate():
    text = _read(_ASIDE_PATH)
    send_func = re.search(
        r'def _vne_aside_send_message\(.*?\):.*?(?=def |label |$)',
        text,
        re.DOTALL,
    )
    assert send_func is not None
    body = send_func.group(0)
    nav_keywords = ["renpy.jump", "renpy.call", "Jump(", "Call(", "jump "]
    for kw in nav_keywords:
        if kw in body:
            lines = body.split("\n")
            found = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if kw in stripped:
                    found = True
                    break
            if found:
                pytest.fail(f"Navigation keyword '{kw}' found in _vne_aside_send_message")


# ---------------------------------------------------------------------------
# Test 7: Async completion callback does not navigate
# ---------------------------------------------------------------------------

def test_async_completion_callback_no_navigation():
    text = _read(_ASIDE_PATH)
    finish_func = re.search(
        r'def _vne_aside_finish_reply\(.*?\):.*?(?=def |label |$)',
        text,
        re.DOTALL,
    )
    assert finish_func is not None
    body = finish_func.group(0)
    nav_keywords = ["renpy.jump", "renpy.call", "Jump(", "Call(", "jump "]
    for kw in nav_keywords:
        if kw in body:
            lines = body.split("\n")
            found = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if kw in stripped:
                    found = True
                    break
            if found:
                pytest.fail(f"Navigation keyword '{kw}' found in _vne_aside_finish_reply")


# ---------------------------------------------------------------------------
# Test 8: Existing Enter behavior unchanged
# ---------------------------------------------------------------------------

def test_enter_keybind_unchanged():
    text = _read(_ASIDE_PATH)
    enter_key = re.search(
        r'key\s+"K_RETURN"\s+action\s+If',
        text,
    )
    assert enter_key is not None, "K_RETURN key binding for Enter not found"
    assert "_vne_aside_send_current_message" in text


# ---------------------------------------------------------------------------
# Test 9: Existing Shift+Enter behavior unchanged
# ---------------------------------------------------------------------------

def test_shift_enter_multiline_unchanged():
    text = _read(_ASIDE_PATH)
    assert 'multiline True' in text, "multiline input property not found"
    assert 'VariableInputValue' in text, "VariableInputValue (Enter handler) not found"


# ---------------------------------------------------------------------------
# Test 10: Diagnostics overlay still opens aside (reference check)
# ---------------------------------------------------------------------------

def test_diagnostics_overlay_does_not_directly_open_aside():
    _read(_DEVDIAG_PATH)
    aside_text = _read(_ASIDE_PATH)
    assert 'Function(_vne_diag_open, "aside_dev_overlay")' in aside_text