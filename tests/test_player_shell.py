#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic Player Shell v0 source-level structural tests.

These are static, offline checks against the actual .rpy source text
(no Ren'Py runtime, no provider calls). They enforce the ratified
OD-UX-01..06 contracts:

- 1920x1080 baseline via options.rpy (no gui.rpy / gui.init()).
- typography-only splash "НАРРАТИВ".
- five-entry main menu: Новая игра / Продолжить / Загрузить / Настройки / Выход.
- New Game routes through player_shell_new_game (not SC_017 directly).
- Continue() standard action.
- dev_scene_selector preserves all 17 original scene jump targets.
- label start no longer hosts the dev selector menu.
- aside_dev_overlay registration is developer-gated only.
- no provider/network imports in the new shell files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_GAME = _REPO / "novel" / "game"

_OPTIONS = _GAME / "options.rpy"
_SCREENS = _GAME / "screens.rpy"
_SCRIPT = _GAME / "script.rpy"
_PLAYER_SHELL = _GAME / "player_shell.rpy"
_ASIDE = _GAME / "aside.rpy"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start_label: str, end_label: str) -> str:
    """Return the text between two Ren'Py label headers (exclusive)."""
    start = text.index(start_label)
    end = text.index(end_label, start)
    return text[start:end]


# The 17 original QA scene-selector jump targets (regression guard).
_SCENE_JUMP_TARGETS = [
    "jump sc_003_start",
    "jump sc_004_start",
    "jump sc_005_start",
    "jump sc_006_start",
    "jump sc_007_start",
    "jump sc_008_start",
    "jump sc_009_start",
    "jump sc_010_start",
    "jump sc_011_start",
    "jump sc_012_start",
    "jump sc_013_start",
    "jump sc_014_start",
    "jump sc_015_start",
    "jump sc_016_start",
    "jump sc_017_v2_start",
    "jump sc_018_start",
    "jump sc_017_start",
]


# --------------------------------------------------------------------------
# Resolution baseline (OD-UX-06): 1920x1080 via options.rpy, no gui.rpy.
# --------------------------------------------------------------------------

def test_options_declare_1920x1080():
    text = _read(_OPTIONS)
    assert re.search(r"config\.screen_width\s*=\s*1920\b", text) is not None, (
        "options.rpy must declare config.screen_width = 1920"
    )
    assert re.search(r"config\.screen_height\s*=\s*1080\b", text) is not None, (
        "options.rpy must declare config.screen_height = 1080"
    )


def test_no_gui_rpy_present():
    assert not (_GAME / "gui.rpy").exists(), (
        "gui.rpy must not exist; resolution is set directly in options.rpy"
    )


def test_no_gui_init_call():
    for name in ("options.rpy", "screens.rpy", "player_shell.rpy"):
        text = _read(_GAME / name)
        assert "gui.init(" not in text, (
            f"{name} must not call gui.init(); set config directly"
        )


# --------------------------------------------------------------------------
# Splashscreen (OD-UX-01 / OD-UX-04): typography-only "НАРРАТИВ".
# --------------------------------------------------------------------------

def test_splashscreen_label_present():
    text = _read(_PLAYER_SHELL)
    assert re.search(r"^label splashscreen:", text, re.MULTILINE) is not None


def test_splashscreen_typography_only():
    text = _read(_PLAYER_SHELL)
    splash = _section(text, "label splashscreen:", "label main_menu:")
    assert "НАРРАТИВ" in splash, "splash must show the НАРРАТИВ title text"
    for asset_token in ("image ", "play ", "audio ", "movie "):
        assert asset_token not in splash, (
            f"splash must be typography-only, found asset token {asset_token!r}"
        )


def test_splash_text_properties_not_atl_statements():
    # Regression guard for the "ATL statement contains two expressions in a
    # row" runtime error. Text presentation properties (font/size/color) are
    # passed to a Text() displayable, never emitted as bare ATL transform
    # statements like:
    #     size 96
    #     color "#e8e8ec"
    #     font "DejaVuSans-Bold.ttf"
    text = _read(_PLAYER_SHELL)
    m = re.search(
        r"^label splashscreen:(.*?)^label main_menu:",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m is not None, "splashscreen label must be present"
    splash = m.group(1)
    assert "Text(" in splash, (
        "splash must construct the title via Text() with style kwargs"
    )
    for prop in ("font", "size", "color"):
        # A bare ATL statement is an indented line beginning with the
        # property name followed by whitespace (e.g. "        size 96").
        bad = re.search(rf"^\s+{prop}\s+", splash, re.MULTILINE)
        assert bad is None, (
            f"splash must not emit text property {prop!r} as an ATL "
            f"transform statement; pass it to Text() instead"
        )


# --------------------------------------------------------------------------
# Main menu (OD-UX-01): five entries, standard actions.
# --------------------------------------------------------------------------

def test_main_menu_screen_present():
    text = _read(_SCREENS)
    assert re.search(r"^screen main_menu\(\):", text, re.MULTILINE) is not None


def test_main_menu_five_buttons():
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    for label in ("Новая игра", "Продолжить", "Загрузить", "Настройки", "Выход"):
        assert f'textbutton "{label}"' in main_menu, (
            f"main menu must contain textbutton {label!r}"
        )


def test_new_game_routes_through_player_shell():
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    assert 'action Start("player_shell_new_game")' in main_menu, (
        "New Game must route through Start('player_shell_new_game')"
    )
    assert "sc_017_v2_start" not in main_menu, (
        "main menu must not hardwire the temporary SC_017 entry (OD-UX-02)"
    )


def test_continue_uses_standard_action():
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    assert "action Continue()" in main_menu, (
        "Continue must use the standard Continue() action"
    )


def test_load_and_preferences_screens_present():
    text = _read(_SCREENS)
    assert re.search(r"^screen load\(\):", text, re.MULTILINE) is not None
    assert re.search(r"^screen preferences\(\):", text, re.MULTILINE) is not None


def test_quit_uses_confirm():
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    assert "action Quit(confirm=True)" in main_menu, (
        "Quit must use Quit(confirm=True)"
    )


def test_developer_entry_gated():
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    # The only "if config.developer:" inside main_menu guards the DEV entry.
    gate_idx = main_menu.find("if config.developer:")
    dev_idx = main_menu.find('textbutton "DEV"')
    assert gate_idx != -1, "main menu must contain an if config.developer: gate"
    assert dev_idx != -1, "main menu must contain the developer entry"
    assert gate_idx < dev_idx, (
        "developer entry (textbutton DEV) must be placed after the "
        "if config.developer: gate"
    )


def test_developer_entry_uses_context_exit_not_jump():
    # Regression guard for the MAJOR defect: a plain Jump() stays inside the
    # special main-menu context created by call_in_new_context("_main_menu"),
    # so dev_scene_selector and selected scenes would run with rollback
    # disabled and the dialogue window forced off. The DEV entry must use a
    # context-exiting action (Start -> jump_out_of_context), matching New Game.
    text = _read(_SCREENS)
    main_menu = _section(text, "screen main_menu():", "screen load():")
    dev_entry = re.search(
        r'textbutton "DEV":\s*\n\s*action\s+([A-Za-z_]+)\("dev_scene_selector"\)',
        main_menu,
    )
    assert dev_entry is not None, (
        "DEV entry must reference dev_scene_selector via an action"
    )
    action_kind = dev_entry.group(1)
    assert action_kind != "Jump", (
        "DEV entry must not use Jump(); Jump stays inside the main-menu "
        "context (rollback disabled, window forced off). Use Start() instead."
    )
    assert action_kind == "Start", (
        f"DEV entry must use Start('dev_scene_selector') to exit the menu "
        f"context; found {action_kind}"
    )


# --------------------------------------------------------------------------
# In-game menu (ESC -> game_menu) — DEFECT A: story ESC must open a menu.
# --------------------------------------------------------------------------

def test_game_menu_screen_present():
    text = _read(_SCREENS)
    assert re.search(r"^screen game_menu\(\):", text, re.MULTILINE) is not None


def test_game_menu_wired_via_standard_keymap():
    # ESC is handled by the stock "game_menu" keymap -> _invoke_game_menu,
    # which shows the screen named by _game_menu_screen. No custom polling.
    text = _read(_SCREENS)
    assert re.search(r'_game_menu_screen\s*=\s*"game_menu"', text) is not None, (
        "_game_menu_screen must be set to 'game_menu' so ESC opens the menu"
    )


def test_game_menu_no_custom_escape_polling():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert 'key "K_ESCAPE"' not in game_menu, (
        "game_menu must rely on the standard game_menu keymap, "
        "not a custom ESC key binding"
    )


def test_game_menu_entries():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    for label in (
        "Продолжить",
        "Сохранить",
        "Загрузить",
        "Настройки",
        "Главное меню",
        "Выход из игры",
    ):
        assert f'textbutton "{label}"' in game_menu, (
            f"game menu must contain textbutton {label!r}"
        )


def test_game_menu_continue_returns_to_story():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    continue_entry = re.search(
        r'textbutton "Продолжить":\s*\n\s*action Return\(\)',
        game_menu,
    )
    assert continue_entry is not None, (
        "Продолжить must use Return() so menu close resumes the story"
    )


def test_game_menu_submenu_entries_shared():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert 'action ShowMenu("save")' in game_menu, "Сохранить must open save"
    assert 'action ShowMenu("load")' in game_menu, "Загрузить must open load"
    assert 'action ShowMenu("preferences")' in game_menu, (
        "Настройки must open preferences"
    )


def test_game_menu_main_menu_confirmation():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert "action MainMenu(confirm=True)" in game_menu, (
        "Главное меню must use MainMenu(confirm=True) to return to the "
        "Player Shell main menu via standard game-menu semantics"
    )


def test_game_menu_quit_confirmation():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert "action Quit(confirm=True)" in game_menu, (
        "Выход из игры must use Quit(confirm=True)"
    )


def test_save_screen_uses_standard_action():
    text = _read(_SCREENS)
    assert re.search(r"^screen save\(\):", text, re.MULTILINE) is not None
    save = _section(text, "screen save():", "screen confirm(")
    assert "action FileSave(i)" in save, (
        "Сохранить must use the standard FileSave(i) action"
    )
    assert "sqlite" not in save.lower(), (
        "save screen must not use SQLite/custom persistence"
    )


def test_confirm_screen_present_and_wired():
    text = _read(_SCREENS)
    assert re.search(
        r"^screen confirm\(message, yes_action, no_action\):",
        text,
        re.MULTILINE,
    ) is not None
    assert re.search(r'config\.confirm_screen\s*=\s*"confirm"', text) is not None, (
        "Quit(confirm=True)/MainMenu(confirm=True) must route to a 'confirm' "
        "screen via config.confirm_screen"
    )


# --------------------------------------------------------------------------
# Save/load stock card coverage (stock-first UX completion).
# --------------------------------------------------------------------------

def test_save_uses_file_screenshot():
    text = _read(_SCREENS)
    save = _section(text, "screen save():", "screen confirm(")
    assert "FileScreenshot(" in save, "save card must use stock FileScreenshot"


def test_load_uses_file_screenshot():
    text = _read(_SCREENS)
    load = _section(text, "screen load():", "screen preferences():")
    assert "FileScreenshot(" in load, "load card must use stock FileScreenshot"


def test_save_uses_file_time():
    text = _read(_SCREENS)
    save = _section(text, "screen save():", "screen confirm(")
    assert "FileTime(" in save, "save card must use stock FileTime"


def test_load_uses_file_time():
    text = _read(_SCREENS)
    load = _section(text, "screen load():", "screen preferences():")
    assert "FileTime(" in load, "load card must use stock FileTime"


def test_save_empty_slot_fallback():
    text = _read(_SCREENS)
    save = _section(text, "screen save():", "screen confirm(")
    assert 'empty="Пусто"' in save, "empty save slot must show a clear fallback"


def test_load_empty_slot_fallback():
    text = _read(_SCREENS)
    load = _section(text, "screen load():", "screen preferences():")
    assert 'empty="Пусто"' in load, "empty load slot must show a clear fallback"


def test_six_slots_per_page():
    text = _read(_SCREENS)
    save = _section(text, "screen save():", "screen confirm(")
    load = _section(text, "screen load():", "screen preferences():")
    assert "range(1, 7)" in save, "save must keep 6 slots per page"
    assert "range(1, 7)" in load, "load must keep 6 slots per page"


def test_normal_page_uses_file_page():
    text = _read(_SCREENS)
    save = _section(text, "screen save():", "screen confirm(")
    load = _section(text, "screen load():", "screen preferences():")
    assert "FilePage(1)" in save, "save must expose numbered normal page via FilePage"
    assert "FilePage(1)" in load, "load must expose numbered normal page via FilePage"


def test_auto_page_uses_file_page_auto():
    text = _read(_SCREENS)
    for section in (
        _section(text, "screen save():", "screen confirm("),
        _section(text, "screen load():", "screen preferences():"),
    ):
        assert 'FilePage("auto")' in section, "auto page must use FilePage('auto')"


def test_quick_page_uses_file_page_quick():
    text = _read(_SCREENS)
    for section in (
        _section(text, "screen save():", "screen confirm("),
        _section(text, "screen load():", "screen preferences():"),
    ):
        assert 'FilePage("quick")' in section, "quick page must use FilePage('quick')"


def test_page_navigation_uses_stock_actions():
    text = _read(_SCREENS)
    for section in (
        _section(text, "screen save():", "screen confirm("),
        _section(text, "screen load():", "screen preferences():"),
    ):
        assert "FilePagePrevious()" in section, "must use stock FilePagePrevious"
        assert "FilePageNext()" in section, "must use stock FilePageNext"


def test_game_menu_quick_save():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert "QuickSave()" in game_menu, "game menu must expose QuickSave()"


def test_game_menu_quick_load():
    text = _read(_SCREENS)
    game_menu = _section(text, "screen game_menu():", "screen save():")
    assert "QuickLoad()" in game_menu, "game menu must expose QuickLoad()"


def test_no_custom_autosave_machinery():
    text = _read(_SCREENS)
    for token in (
        "config.has_autosave",
        "renpy.autosave",
        "force_autosave",
        "autosave_frequency",
    ):
        assert token not in text, "must not configure custom autosave machinery"


def test_no_custom_quick_save_persistence():
    text = _read(_SCREENS)
    for token in (
        "quicksave_slots",
        "_quick_slot",
        "quick_save_slot",
        "cycle_slot",
    ):
        assert token not in text, "must not implement custom quick-save persistence"


def test_no_sqlite_in_save_load():
    text = _read(_SCREENS)
    for section in (
        _section(text, "screen save():", "screen confirm("),
        _section(text, "screen load():", "screen preferences():"),
    ):
        assert "sqlite" not in section.lower(), "save/load must not use SQLite"


def test_no_manual_rename_input_ui():
    text = _read(_SCREENS)
    for section in (
        _section(text, "screen save():", "screen confirm("),
        _section(text, "screen load():", "screen preferences():"),
    ):
        assert "FileSaveName" not in section, "v0 card must not depend on save name"
        assert "FilePageNameInputValue" not in section, "no page rename input"
        assert "input" not in section, "no rename/input UI in v0 save/load"


def test_load_uses_stock_file_load():
    text = _read(_SCREENS)
    load = _section(text, "screen load():", "screen preferences():")
    assert "FileLoad(i)" in load, "load must use stock FileLoad(i)"


# --------------------------------------------------------------------------
# Settings selected state (DEFECT B): active option must be visible.
# --------------------------------------------------------------------------

def test_preferences_selected_state_present():
    text = _read(_SCREENS)
    prefs = _section(text, "screen preferences():", "screen game_menu():")
    # 7 option buttons: screen (2), text speed (3), auto-forward (2).
    for attr in (
        "selected_background Solid(",
        "selected_hover_background Solid(",
        "text_selected_color",
        "text_selected_hover_color",
    ):
        assert prefs.count(attr) >= 7, (
            f"preferences must set {attr!r} on every option button for a "
            f"visible selected state; found {prefs.count(attr)}"
        )


def test_preferences_selected_state_distinct_from_hover():
    text = _read(_SCREENS)
    prefs = _section(text, "screen preferences():", "screen game_menu():")
    # Selected differs from normal (transparent bg) and hover (white text):
    # selected uses a light background with dark text.
    assert 'text_hover_color "#ffffff"' in prefs, "hover state must use white text"
    assert 'text_selected_color "#14141c"' in prefs, (
        "selected state must use a dark text color distinct from hover"
    )
    assert 'selected_background Solid("#e8e8ec")' in prefs, (
        "selected state must use a light background distinct from hover"
    )


# --------------------------------------------------------------------------
# Dev selector extraction (OD-UX-03): label dev_scene_selector + safety net.
# --------------------------------------------------------------------------

def test_dev_scene_selector_label_present():
    text = _read(_SCRIPT)
    assert re.search(r"^label dev_scene_selector:", text, re.MULTILINE) is not None


def test_dev_scene_selector_preserves_all_17_targets():
    text = _read(_SCRIPT)
    selector = _section(text, "label dev_scene_selector:", "label sc_003_start:")
    missing = [t for t in _SCENE_JUMP_TARGETS if t not in selector]
    assert missing == [], (
        f"dev_scene_selector dropped jump targets: {missing}"
    )


def test_label_start_no_longer_hosts_menu():
    text = _read(_SCRIPT)
    start = _section(text, "label start:", "label dev_scene_selector:")
    assert "menu:" not in start, (
        "label start must no longer contain the dev selector menu"
    )


def test_label_start_safety_net_routes():
    text = _read(_SCRIPT)
    start = _section(text, "label start:", "label dev_scene_selector:")
    assert "jump dev_scene_selector" in start
    assert "jump player_shell_new_game" in start
    assert "if config.developer:" in start


# --------------------------------------------------------------------------
# New Game bootstrap (OD-UX-02): only bootstrap knows SC_017 entry.
# --------------------------------------------------------------------------

def test_player_shell_new_game_label_present():
    text = _read(_PLAYER_SHELL)
    assert re.search(
        r"^label player_shell_new_game:", text, re.MULTILINE
    ) is not None


def test_player_shell_new_game_jumps_to_sc017():
    text = _read(_PLAYER_SHELL)
    # The bootstrap label is the final block in the file; take everything
    # after its header.
    idx = text.index("label player_shell_new_game:")
    body = text[idx:]
    assert "jump sc_017_v2_start" in body


def test_sc017_only_referenced_in_bootstrap():
    text = _read(_PLAYER_SHELL)
    # The temporary entry is jumped to from exactly one place: the bootstrap
    # label body. (Header comments may mention the label; only the jump
    # statement is a routing reference.)
    occurrences = re.findall(r"jump sc_017_v2_start", text)
    assert len(occurrences) == 1, (
        f"expected exactly one 'jump sc_017_v2_start' in player_shell.rpy, "
        f"found {len(occurrences)}"
    )


# --------------------------------------------------------------------------
# aside.rpy developer gate (OD-UX-05): one-hunk visibility guard only.
# --------------------------------------------------------------------------

def test_aside_overlay_gated():
    text = _read(_ASIDE)
    gated = re.search(
        r"if config\.developer:\s*\n\s*config\.overlay_screens\.append\(\"aside_dev_overlay\"\)",
        text,
    )
    assert gated is not None, (
        "aside_dev_overlay registration must be guarded by if config.developer:"
    )


def test_aside_overlay_not_unconditional():
    text = _read(_ASIDE)
    # The guarded form must be the only occurrence of this registration.
    guarded_only = text.count(
        'config.overlay_screens.append("aside_dev_overlay")'
    ) == 1
    assert guarded_only, (
        "aside_dev_overlay should be registered exactly once, guarded"
    )


# --------------------------------------------------------------------------
# No provider/network imports (OD-UX-04 / firewall).
# --------------------------------------------------------------------------

def test_shell_files_have_no_provider_imports():
    for name in ("player_shell.rpy", "screens.rpy", "options.rpy", "script.rpy"):
        text = _read(_GAME / name)
        for forbidden in ("deepseek", "ollama", "llm_provider", "socket", "requests"):
            assert forbidden not in text, (
                f"{name} must not reference {forbidden!r}"
            )