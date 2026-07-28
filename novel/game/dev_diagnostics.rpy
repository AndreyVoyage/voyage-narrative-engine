# dev_diagnostics.rpy — RN-DIAG-01-R4 Developer Diagnostics Hub.
#
# Purpose:
#   Permanent, developer-only, on-screen diagnostics for investigating screen
#   visibility, screen-variable lifecycle, input binding, keyboard focus,
#   displayable availability, keymaps, geometry, runtime identity, and the
#   Character Aside chat state. This complements Ren'Py's built-in tools
#   (Shift+O console, Shift+D developer menu, Shift+I style inspector,
#   Shift+R reload, F8 screen profiling).
#
# Scope:
#   Diagnostics infrastructure only. This file does NOT fix the current
#   Character Aside keyboard-input bug; it produces the evidence a later,
#   separately authorized repair will use. See the Input Lab tab and the
#   "Bug Observability Checklist" for the current, honestly-reported state
#   of that investigation.
#
# RN-DIAG-01-R2 (2026-07-21) — modal/zorder made unconditional (Ren'Py's SL2
# parser only captures those as screen keywords when they are direct,
# unconditional children of `screen`), and every root frame sized as a
# proportion of config.screen_width/height (this project runs at Ren'Py's
# 800x600 engine default; nothing overrides it).
#
# RN-DIAG-01-R3 (2026-07-21) — a raw renderer-info dict rendered directly as
# text crashed with "Unknown text tag" (Ren'Py's `{...}` tag parser, not
# disabled by `substitute False`). Fixed with a central `_vne_diag_safe_text()`
# escaping helper. Also replaced the combined input sandbox with three
# isolated single-input probe screens, since the standard Ren'Py screenshot
# keymap (`s`) reaching the global keymap is itself useful evidence that no
# probe input is focused.
#
# RN-DIAG-01-R4 (2026-07-21) — owner ran the actual game after R3: opening
# from Aside, the build marker, and tab-state switching all confirmed
# working, but the tab BODY rendered as a large blank area on every tab
# (Overview, Screens & Focus, Input Lab), and none of the Input Lab launcher
# buttons or isolated probe screens were reachable. A stale traceback.txt
# from an earlier (pre-R3) session confirmed the R2 rendering pipeline DID
# work up to the point of the R2 crash, so viewport rendering is not
# inherently broken - but no fresh exception was produced by the R4 test,
# meaning this is a layout/construction issue, not an unhandled exception.
# Unable to reproduce or instrument the actual Ren'Py display from this
# environment, this revision follows the most defensible path: remove every
# layer of indirection between the tab-switch state and the visible content
# that could not be independently re-verified at runtime - all seven tabs'
# content is now built directly inline in `vne_dev_diagnostics` (no `use`
# statements for tab content), the two previously-`use`d row-renderer helper
# screens are inlined at each call site, the outer `side "c r"` container is
# replaced with a plain `hbox` + `viewport` + `vbar`, and every tab begins
# with an unconditional "TAB CONTENT ACTIVE: ..." marker so the owner can see
# directly whether the dispatch itself reaches a tab's content even if a
# specific data row still fails.
#
# Safety boundaries (see also RN_DIAG_01 task brief):
#   - Gated behind config.developer; no production visibility.
#   - Never mutates canon (v2_*), persona/aside memory, or save files beyond
#     the same ordinary dev-only `default` store variables this project
#     already uses for UI state (e.g. aside_input_text, aside_chat_history).
#   - No network access, no subprocess/shell execution, no Git operations,
#     no background threads, no secrets/tokens/env values, no full LLM
#     prompt/reply bodies (only bounded previews and lengths).
#   - Only public, documented Ren'Py APIs are used (renpy.get_screen,
#     renpy.get_screen_variable, renpy.set_screen_variable,
#     renpy.get_displayable, renpy.set_focus, renpy.show_screen,
#     renpy.hide_screen, renpy.get_mouse_pos, renpy.get_renderer_info,
#     renpy.get_physical_size, renpy.get_autoreload, renpy.set_autoreload,
#     renpy.reload_script, renpy.profile_screen, renpy.input,
#     ScreenVariableInputValue, VariableInputValue, YScrollValue,
#     CopyToClipboard, Confirm).
#   - A focus request (renpy.set_focus) is never reported as proof of
#     successful keyboard focus - only "FOCUS REQUESTED". Opening a screen
#     is only ever reported as "SHOW REQUESTED" - SHOWING indicators are a
#     live renpy.get_screen() check, never inferred from lack of exception.


# ============================================================
# STATE (dev-only UI state; not canon, not persona memory)
# ============================================================

default vne_diag_tab = "overview"
default vne_diag_events = []
default vne_diag_last_result = "(none yet)"
default vne_diag_last_focus_request = None
default vne_diag_last_probe_changed = ""
default vne_diag_last_export_path = ""
default vne_diag_modal_input_result = None
default vne_diag_store_probe_text = ""
default vne_diag_screens_snapshot = []
default vne_diag_displayables_snapshot = []
default vne_diag_aside_snapshot = {}
default vne_diag_typing_confirmations = {}
default vne_diag_s_key_results = {}
default vne_diag_probe_change_events = {}
default vne_diag_case_b_probe_text = ""
default vne_diag_case_c_result = None
default vne_diag_show_grid = False
default vne_diag_show_center = False
default vne_diag_show_safe_area = False
default vne_diag_show_crosshair = False
default vne_diag_show_aside_regions = False
default vne_diag_open_request_count = 0
default vne_diag_last_open_source = "(none yet)"
default vne_diag_last_open_result = "(none yet)"
default vne_diag_last_open_exception = ""
default vne_diag_runtime_acceptance = {}
default vne_diag_probe_open_requests = {}


init python:
    import datetime
    import json
    import platform
    import sys
    from pathlib import Path

    VNE_DIAG_BUILD_MARKER = "RN-DIAG-01-R6"
    VNE_DIAG_MAX_EVENTS = 200

    _VNE_DIAG_KNOWN_SCREENS = [
        "aside_chat_log",
        "aside_dev_overlay",
        "story_state_dev_overlay",
        "vne_dev_diagnostics",
        "vne_diag_store_probe_screen",
        "vne_diag_screen_probe_screen",
        "vne_diag_multiline_probe_screen",
        "vne_diag_case_b_probe_screen",
        "vne_diag_case_c_probe_screen",
    ]

    _VNE_DIAG_KNOWN_DISPLAYABLES = [
        ("aside_chat_log", "aside_message_input"),
        ("aside_chat_log", "aside_history_viewport"),
        ("aside_chat_log", "aside_composer_viewport"),
        ("vne_diag_store_probe_screen", "vne_diag_store_probe_input"),
        ("vne_diag_screen_probe_screen", "vne_diag_screen_probe_input"),
        ("vne_diag_multiline_probe_screen", "vne_diag_multiline_probe_input"),
        ("vne_diag_case_b_probe_screen", "vne_diag_case_b_probe_input"),
        ("vne_diag_case_c_probe_screen", "vne_diag_case_c_probe_input"),
    ]

    # ------------------------------------------------------------------
    # Safe helpers
    # ------------------------------------------------------------------

    def _vne_diag_now():
        return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _vne_diag_truncate(text, limit=200):
        text = "" if text is None else str(text)
        if len(text) > limit:
            return text[:limit] + "...(+{}ch)".format(len(text) - limit)
        return text

    def _vne_diag_preview(text, limit=200):
        """Plain repr-based preview for logging/export/clipboard use only.

        Never pass the result of this directly to a `text` displayable -
        repr() does not escape Ren'Py's `{`/`[` text-tag characters. Use
        _vne_diag_safe_text() (optionally wrapping this) for on-screen use.
        """
        return repr(_vne_diag_truncate(text, limit))

    def _vne_diag_exc(exc):
        return "{}: {}".format(type(exc).__name__, _vne_diag_truncate(str(exc), 200))

    def _vne_diag_safe(func, *args, **kwargs):
        """Run func; return (ok, value_or_error_text). Never raises."""
        try:
            return True, func(*args, **kwargs)
        except Exception as exc:
            return False, _vne_diag_exc(exc)

    def _vne_diag_safe_text(value, limit=200):
        """The single point where any runtime-controlled value (dict/list
        repr, exception text, user-typed text, file paths, renderer
        strings) is made safe before display in a Ren'Py `text` displayable.

        See RN-DIAG-01-R3 header notes for the full rationale (Ren'Py's
        `{...}` text-tag parser vs. `substitute False`). Truncation happens
        BEFORE escaping so a cut can never split an escaped pair.
        """
        try:
            text = "" if value is None else str(value)
        except Exception as exc:
            text = "<unprintable: {}>".format(_vne_diag_exc(exc))
        text = _vne_diag_truncate(text, limit)
        text = text.replace("\n", "\\n")
        text = text.replace("{", "{{").replace("[", "[[")
        return text

    def _vne_diag_text_safety_selftest():
        cases = [
            {"renderer": "gl2", "resizable": True},
            ["a", "b", "c"],
            "{b}NOT A REAL TAG{/b}",
            "[not_a_variable]",
            "C:\\Users\\test\\{folder}\\[brackets]",
            "ValueError: bad value {oops} at [index]",
            "line one\nline two\nline three",
            "Тест кириллицы {и} [скобок] с переносом\nстрок",
        ]
        for case in cases:
            try:
                result = _vne_diag_safe_text(case, limit=500)
            except Exception as exc:
                return False, "case {!r} raised: {}".format(case, _vne_diag_exc(exc))
            source_str = str(case)
            if "{" in source_str and "{{" not in result:
                return False, "case {!r} did not escape braces".format(case)
            if "[" in source_str and "[[" not in result:
                return False, "case {!r} did not escape brackets".format(case)
            if "\n" in result:
                return False, "case {!r} left a raw newline in output".format(case)
        return True, "{} cases passed".format(len(cases))

    def _vne_diag_content_self_check():
        """RN-DIAG-01-R4 section 7: SOURCE PRESENCE ONLY.

        These are static facts about this file (verified in the R4 report's
        static feature manifest via grep), not a runtime observation. This
        never claims source presence equals runtime visibility.
        """
        return [
            ("Overview marker", "PASS"),
            ("Screens & Focus marker", "PASS"),
            ("Input Lab launcher definitions", "4/4"),
            ("Probe screen definitions", "3/3"),
            ("Modal control path", "PASS"),
            ("Logs/export controls", "PASS"),
            ("Safe-text helper", "PASS"),
        ]

    def _vne_diag_log(category, action, target="", result="", details=""):
        """Append a plain-data event to the bounded diagnostics ring buffer."""
        import store
        event = {
            "ts": _vne_diag_now(),
            "category": str(category),
            "action": str(action),
            "target": str(target),
            "result": str(result),
            "details": _vne_diag_truncate(details, 300),
        }
        events = list(store.vne_diag_events) + [event]
        if len(events) > VNE_DIAG_MAX_EVENTS:
            events = events[-VNE_DIAG_MAX_EVENTS:]
        store.vne_diag_events = events
        store.vne_diag_last_result = "[{}] {} -> {}".format(category, action, result or "logged")

    def _vne_diag_json_preview(obj):
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            return "ERROR: {}".format(_vne_diag_exc(exc))

    def _vne_diag_copy_text(category, label, text):
        """Invoke Ren'Py's own documented CopyToClipboard action unmodified."""
        ok, err = _vne_diag_safe(CopyToClipboard(text))
        if ok:
            _vne_diag_log(category, label, result="OK", details="len={}".format(len(text)))
        else:
            _vne_diag_log(category, label, result="CLIPBOARD UNAVAILABLE", details=err)
        renpy.restart_interaction()

    # ------------------------------------------------------------------
    # Open / close: hub + individual probe screens
    # ------------------------------------------------------------------

    def _vne_diag_open(source):
        import store
        store.vne_diag_open_request_count = store.vne_diag_open_request_count + 1
        store.vne_diag_last_open_source = str(source)

        if not config.developer:
            store.vne_diag_last_open_result = "BLOCKED (config.developer is False)"
            store.vne_diag_last_open_exception = ""
            _vne_diag_log("SYSTEM", "OPEN DIAGNOSTICS", target=str(source), result=store.vne_diag_last_open_result)
            renpy.restart_interaction()
            return

        ok, err = _vne_diag_safe(renpy.show_screen, "vne_dev_diagnostics")
        store.vne_diag_last_open_result = "SHOW REQUESTED" if ok else "ERROR"
        store.vne_diag_last_open_exception = "" if ok else err
        _vne_diag_log(
            "SYSTEM",
            "OPEN DIAGNOSTICS",
            target=str(source),
            result=store.vne_diag_last_open_result,
            details=store.vne_diag_last_open_exception,
        )
        renpy.restart_interaction()

    def _vne_diag_close():
        ok, err = _vne_diag_safe(renpy.hide_screen, "vne_dev_diagnostics")
        _vne_diag_log("SYSTEM", "CLOSE DIAGNOSTICS", result=("OK" if ok else "ERROR"), details=(err or ""))
        renpy.restart_interaction()

    def _vne_diag_set_runtime_acceptance(key, value):
        import store
        state = dict(store.vne_diag_runtime_acceptance)
        state[key] = {"value": value, "ts": _vne_diag_now()}
        store.vne_diag_runtime_acceptance = state
        _vne_diag_log("SYSTEM", "RUNTIME ACCEPTANCE", target=key, result=str(value))
        renpy.restart_interaction()

    def _vne_diag_open_probe_screen(screen_name):
        import store
        state = dict(store.vne_diag_probe_open_requests)
        entry = dict(state.get(screen_name, {"count": 0}))
        entry["count"] = entry.get("count", 0) + 1

        if not config.developer:
            entry["result"] = "BLOCKED (config.developer is False)"
            entry["exception"] = ""
            state[screen_name] = entry
            store.vne_diag_probe_open_requests = state
            _vne_diag_log("SYSTEM", "OPEN PROBE", target=screen_name, result=entry["result"])
            renpy.restart_interaction()
            return

        ok, err = _vne_diag_safe(renpy.show_screen, screen_name)
        entry["result"] = "SHOW REQUESTED" if ok else "ERROR"
        entry["exception"] = "" if ok else err
        showing_status, _ = _vne_diag_screen_status(screen_name)
        entry["showing_after_request"] = showing_status
        state[screen_name] = entry
        store.vne_diag_probe_open_requests = state
        _vne_diag_log("SYSTEM", "OPEN PROBE", target=screen_name, result=entry["result"], details=entry["exception"])
        renpy.restart_interaction()

    def _vne_diag_open_store_probe():
        _vne_diag_open_probe_screen("vne_diag_store_probe_screen")

    def _vne_diag_open_screen_probe():
        _vne_diag_open_probe_screen("vne_diag_screen_probe_screen")

    def _vne_diag_open_multiline_probe():
        _vne_diag_open_probe_screen("vne_diag_multiline_probe_screen")

    # ------------------------------------------------------------------
    # RN-DIAG-01-R6 forensic addendum: Case B and Case C controlled
    # probes. See the R6 report for the full hypothesis matrix. Both use
    # ONLY public/documented APIs (Show/Hide, VariableInputValue,
    # ScreenVariableInputValue, renpy.call_screen,
    # renpy.invoke_in_new_context, Return) - the undocumented
    # current_input_value/input_values mechanism in
    # renpy.display.behavior was read for analysis only and is never
    # called at runtime here.
    # ------------------------------------------------------------------

    def _vne_diag_open_case_b_probe():
        """Case B: identical show_screen approach to the R5 probes, but a
        RAW VariableInputValue with no telemetry wrapper. Test this once
        while Aside is open (Case B) and once after closing Aside first,
        opening Diagnostics directly instead (Case D) - same screen, two
        contexts."""
        ok, err = _vne_diag_safe(renpy.show_screen, "vne_diag_case_b_probe_screen")
        _vne_diag_log(
            "FORENSICS",
            "OPEN CASE B PROBE (show_screen, no wrapper)",
            result=("SHOW REQUESTED" if ok else "ERROR"),
            details=(err or ""),
        )
        renpy.restart_interaction()

    def _vne_diag_open_case_c_probe():
        """Case C: renpy.call_screen run inside a fresh context via the
        documented renpy.invoke_in_new_context(), with _clear_layers=True
        so Aside and the Diagnostics hub are temporarily cleared - only
        this probe's screen exists in that interaction. If the hypothesis
        in the R6 report is correct (Ren'Py tracks a single global
        "currently editable" InputValue per game session, which only
        reassigns when its owner disappears from the current interaction's
        scene), this isolated context should let typing work immediately,
        unlike Cases A/B where Aside's own default=True InputValue never
        leaves the scene.
        """
        import store
        ok, result = _vne_diag_safe(
            renpy.invoke_in_new_context,
            renpy.call_screen,
            "vne_diag_case_c_probe_screen",
            _clear_layers=True,
        )
        store.vne_diag_case_c_result = {
            "ts": _vne_diag_now(),
            "ok": ok,
            "result": (result if ok else None),
            "error": (None if ok else result),
        }
        _vne_diag_log(
            "FORENSICS",
            "RUN CASE C (call_screen, cleared layers)",
            result=("RETURNED" if ok else "ERROR"),
            details=(str(result) if ok else result),
        )
        renpy.restart_interaction()

    def _vne_diag_count_simultaneous_inputs():
        """Public-API-only count of which known input-bearing screens are
        currently showing at once (via renpy.get_screen/get_displayable).
        This is a proxy for "how many Input displayables coexist in the
        current interaction" - it does NOT read the undocumented
        current_input_value/input_values globals (compliance: public/
        documented APIs only at runtime)."""
        rows = []
        for screen_name, disp_id in _VNE_DIAG_KNOWN_DISPLAYABLES:
            status, _ = _vne_diag_displayable_status(screen_name, disp_id)
            if status == "YES":
                rows.append("{}::{}".format(screen_name, disp_id))
        return rows

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def _vne_diag_screen_status(name):
        ok, info = _vne_diag_safe(renpy.get_screen, name)
        if not ok:
            return "UNKNOWN", info
        return ("YES" if info is not None else "NO"), ""

    def _vne_diag_displayable_status(screen_name, disp_id):
        ok, disp = _vne_diag_safe(renpy.get_displayable, screen_name, disp_id)
        if not ok:
            return "UNKNOWN", disp
        return ("YES" if disp is not None else "NO"), ""

    def _vne_diag_check_all_screens():
        import store
        rows = []
        for name in _VNE_DIAG_KNOWN_SCREENS:
            status, detail = _vne_diag_screen_status(name)
            rows.append({"name": name, "status": status, "detail": detail})
        store.vne_diag_screens_snapshot = rows
        _vne_diag_log("SCREEN", "CHECK ALL SCREENS", result="{} checked".format(len(rows)))
        renpy.restart_interaction()

    def _vne_diag_check_all_displayables():
        import store
        rows = []
        for screen_name, disp_id in _VNE_DIAG_KNOWN_DISPLAYABLES:
            status, detail = _vne_diag_displayable_status(screen_name, disp_id)
            rows.append({"screen": screen_name, "id": disp_id, "status": status, "detail": detail})
        store.vne_diag_displayables_snapshot = rows
        _vne_diag_log("DISPLAYABLE", "CHECK ALL DISPLAYABLES", result="{} checked".format(len(rows)))
        renpy.restart_interaction()

    def _vne_diag_request_focus(screen_name, disp_id):
        import store
        found_status, _ = _vne_diag_displayable_status(screen_name, disp_id)
        ok, err = _vne_diag_safe(renpy.set_focus, screen_name, disp_id)
        store.vne_diag_last_focus_request = {
            "ts": _vne_diag_now(),
            "screen": screen_name,
            "id": disp_id,
            "found_before": found_status,
            "error": (None if ok else err),
        }
        _vne_diag_log(
            "FOCUS",
            "REQUEST FOCUS",
            target="{}::{}".format(screen_name, disp_id),
            result=("FOCUS REQUESTED" if ok else "ERROR"),
            details=(err or "found_before={}".format(found_status)),
        )
        renpy.restart_interaction()

    def _vne_diag_clear_focus():
        ok, err = _vne_diag_safe(renpy.set_focus, None, None)
        _vne_diag_log("FOCUS", "CLEAR INPUT FOCUS", result=("OK" if ok else "ERROR"), details=(err or ""))
        renpy.restart_interaction()

    # ------------------------------------------------------------------
    # Aside Bridge helpers
    # ------------------------------------------------------------------

    def _vne_diag_aside_get_message_text():
        import store
        ok, val = _vne_diag_safe(renpy.get_screen_variable, "message_text", screen="aside_chat_log")
        snap = dict(store.vne_diag_aside_snapshot)
        snap["checked_at"] = _vne_diag_now()
        if ok:
            snap["message_text_readable"] = True
            snap["message_text_len"] = len(val or "")
            snap["message_text_preview"] = _vne_diag_preview(val, 200)
            snap["message_text_error"] = ""
            result = "OK len={}".format(len(val or ""))
        else:
            snap["message_text_readable"] = False
            snap["message_text_len"] = None
            snap["message_text_preview"] = ""
            snap["message_text_error"] = val
            result = "SCREEN NOT SHOWING" if "not showing" in str(val).lower() else "ERROR: {}".format(val)
        store.vne_diag_aside_snapshot = snap
        _vne_diag_log("ASIDE", "GET ASIDE message_text", target="aside_chat_log::message_text", result=result)
        renpy.restart_interaction()

    def _vne_diag_aside_set_message_text(new_value):
        import store
        ok_set, err_set = _vne_diag_safe(renpy.set_screen_variable, "message_text", new_value, screen="aside_chat_log")
        ok_get, val = _vne_diag_safe(renpy.get_screen_variable, "message_text", screen="aside_chat_log")
        snap = dict(store.vne_diag_aside_snapshot)
        snap["checked_at"] = _vne_diag_now()
        if ok_set and ok_get:
            confirmed = (val == new_value)
            snap["message_text_set_confirmed"] = confirmed
            snap["message_text_readable"] = True
            snap["message_text_len"] = len(val or "")
            snap["message_text_preview"] = _vne_diag_preview(val, 200)
            snap["message_text_error"] = ""
            result = "SET+CONFIRMED" if confirmed else "SET BUT READBACK DIFFERS"
        elif not ok_set:
            snap["message_text_set_confirmed"] = False
            snap["message_text_error"] = err_set
            result = "SCREEN NOT SHOWING" if "not showing" in str(err_set).lower() else "ERROR: {}".format(err_set)
        else:
            snap["message_text_set_confirmed"] = False
            snap["message_text_readable"] = False
            snap["message_text_error"] = val
            result = "SET OK, READBACK ERROR: {}".format(val)
        store.vne_diag_aside_snapshot = snap
        _vne_diag_log(
            "ASIDE",
            "SET ASIDE message_text",
            target="aside_chat_log::message_text",
            result=result,
            details=repr(new_value)[:100],
        )
        renpy.restart_interaction()

    def _vne_diag_aside_append_marker(suffix):
        ok_get, current = _vne_diag_safe(renpy.get_screen_variable, "message_text", screen="aside_chat_log")
        base = current if (ok_get and isinstance(current, str)) else ""
        _vne_diag_aside_set_message_text(base + suffix)

    def _vne_diag_refresh_aside_snapshot():
        import store
        screen_status, screen_detail = _vne_diag_screen_status("aside_chat_log")
        disp_status, disp_detail = _vne_diag_displayable_status("aside_chat_log", "aside_message_input")
        snap = dict(store.vne_diag_aside_snapshot)
        snap["screen_showing"] = screen_status
        snap["screen_detail"] = screen_detail
        snap["input_discoverable"] = disp_status
        snap["input_detail"] = disp_detail
        snap["aside_input_text_preview"] = _vne_diag_preview(getattr(store, "aside_input_text", ""), 200)
        snap["aside_chat_history_len"] = len(getattr(store, "aside_chat_history", []))
        snap["aside_llm_pending"] = getattr(store, "aside_llm_pending", None)
        snap["aside_provider"] = getattr(store, "vne_aside_config_provider", None)
        store.vne_diag_aside_snapshot = snap
        _vne_diag_log("ASIDE", "REFRESH ASIDE SNAPSHOT", result=screen_status)
        renpy.restart_interaction()
        _vne_diag_aside_get_message_text()

    def _vne_diag_aside_add_marker():
        _vne_diag_log(
            "ASIDE",
            "ADD ASIDE DIAGNOSTIC MARKER",
            target="aside_chat_log",
            result="marker logged (no LLM call, no history mutation)",
        )
        renpy.restart_interaction()

    # ------------------------------------------------------------------
    # Input Lab probe helpers
    # ------------------------------------------------------------------

    def _vne_diag_store_probe_set(text):
        import store
        store.vne_diag_store_probe_text = text
        store.vne_diag_last_probe_changed = "store"
        _vne_diag_log("INPUT", "STORE PROBE SET", target="vne_diag_store_probe_input", details=_vne_diag_preview(text))
        renpy.restart_interaction()

    def _vne_diag_store_probe_append(suffix):
        import store
        _vne_diag_store_probe_set(store.vne_diag_store_probe_text + suffix)

    def _vne_diag_store_probe_clear():
        _vne_diag_store_probe_set("")

    def _vne_diag_screen_probe_set(text):
        import store
        ok, err = _vne_diag_safe(renpy.set_screen_variable, "diag_screen_probe_text", text, screen="vne_diag_screen_probe_screen")
        store.vne_diag_last_probe_changed = "screen"
        _vne_diag_log(
            "INPUT",
            "SCREEN PROBE SET",
            target="vne_diag_screen_probe_input",
            result=("OK" if ok else "ERROR"),
            details=(err or _vne_diag_preview(text)),
        )
        renpy.restart_interaction()

    def _vne_diag_screen_probe_append(suffix):
        ok, current = _vne_diag_safe(renpy.get_screen_variable, "diag_screen_probe_text", screen="vne_diag_screen_probe_screen")
        base = current if (ok and isinstance(current, str)) else ""
        _vne_diag_screen_probe_set(base + suffix)

    def _vne_diag_screen_probe_clear():
        _vne_diag_screen_probe_set("")

    def _vne_diag_multiline_probe_set(text):
        import store
        ok, err = _vne_diag_safe(renpy.set_screen_variable, "diag_multiline_probe_text", text, screen="vne_diag_multiline_probe_screen")
        store.vne_diag_last_probe_changed = "multiline"
        _vne_diag_log(
            "INPUT",
            "MULTILINE PROBE SET",
            target="vne_diag_multiline_probe_input",
            result=("OK" if ok else "ERROR"),
            details=(err or _vne_diag_preview(text, 300)),
        )
        renpy.restart_interaction()

    def _vne_diag_multiline_probe_append_line():
        ok, current = _vne_diag_safe(renpy.get_screen_variable, "diag_multiline_probe_text", screen="vne_diag_multiline_probe_screen")
        base = current if (ok and isinstance(current, str)) else ""
        n = (base.count("\n") + 1) if base else 1
        _vne_diag_multiline_probe_set(base + ("\n" if base else "") + "line {}".format(n))

    def _vne_diag_multiline_probe_clear():
        _vne_diag_multiline_probe_set("")

    def _vne_diag_run_input_control_test():
        """RN-DIAG-01-R5: renpy.input() calls renpy.ui.interact() internally
        (renpy/exports/inputexports.py), which raises
        "Cannot start an interaction in the middle of an interaction,
        without creating a new context." (renpy/display/core.py:2128-2131)
        when called directly from a screen action - the action itself runs
        while context.interacting is already True for the entire
        Diagnostics/Aside interaction. The documented fix, per
        renpy.invoke_in_new_context()'s own docstring ("generally used to
        call a Python function that needs to display information to the
        player ... from inside an event handler"), is to run it inside a
        new context. `_clear_layers=False` is required so the underlying
        Diagnostics hub and Character Aside are not hidden/cleared.
        """
        import store
        ok, result = _vne_diag_safe(
            renpy.invoke_in_new_context,
            renpy.input,
            "RN-DIAG-01-R5 input control test - type then press Enter",
            default="",
            length=200,
            _clear_layers=False,
        )
        entry = {"ts": _vne_diag_now()}
        if ok:
            entry["value_preview"] = _vne_diag_preview(result, 200)
            entry["length"] = len(result or "")
            entry["error"] = None
            entry["cancelled"] = False
            entry["verdict"] = "PASS" if (result and len(result) > 0) else "UNKNOWN"
        else:
            entry["value_preview"] = ""
            entry["length"] = 0
            entry["error"] = result
            entry["cancelled"] = False
            entry["verdict"] = "FAIL"
        store.vne_diag_modal_input_result = entry
        _vne_diag_log(
            "INPUT",
            "RUN renpy.input CONTROL TEST",
            result=entry["verdict"],
            details=(entry["error"] or entry["value_preview"]),
        )
        renpy.restart_interaction()

    def _vne_diag_confirm_typing(probe_key, worked):
        import store
        state = dict(store.vne_diag_typing_confirmations)
        state[probe_key] = {"worked": worked, "ts": _vne_diag_now()}
        store.vne_diag_typing_confirmations = state
        _vne_diag_log(
            "INPUT",
            "MANUAL TYPING CONFIRMATION",
            target=probe_key,
            result=("CONFIRMED WORKS" if worked else "CONFIRMED FAILS"),
        )
        renpy.restart_interaction()

    def _vne_diag_confirm_s_key(probe_key, result):
        import store
        s_state = dict(store.vne_diag_s_key_results)
        s_state[probe_key] = {"result": result, "ts": _vne_diag_now()}
        store.vne_diag_s_key_results = s_state

        typing_state = dict(store.vne_diag_typing_confirmations)
        typing_state[probe_key] = {"worked": (result == "ENTERED ACTIVE PROBE"), "ts": _vne_diag_now()}
        store.vne_diag_typing_confirmations = typing_state

        _vne_diag_log("INPUT", "S KEY RESULT", target=probe_key, result=result)
        renpy.restart_interaction()

    def _vne_diag_probe_result_label(probe_key):
        import store
        entry = store.vne_diag_s_key_results.get(probe_key)
        if entry is None:
            return "NOT TESTED"
        result = entry["result"]
        if result == "ENTERED ACTIVE PROBE":
            return "TYPING WORKS"
        if result == "SCREENSHOT TRIGGERED":
            return "S SCREENSHOT TRIGGERED"
        if result == "UNKNOWN":
            return "TYPING FAILS"
        return "ERROR"

    # ------------------------------------------------------------------
    # RN-DIAG-01-R5: real keystroke telemetry.
    #
    # `renpy.display.behavior.Input.__init__` always does
    # `changed = value.set_text` whenever a `value=` InputValue is given,
    # overriding any `changed=` kwarg passed directly on the `input:`
    # statement (renpy/display/behavior.py:1446-1449) - so a custom
    # `changed` property cannot coexist with `value=`. The documented,
    # supported way to observe real edits is instead to wrap the InputValue
    # itself (InputValue is explicitly "Subclassable by creators" per its
    # docstring in renpy/common/00inputvalues.rpy) and forward get_text/
    # set_text to the real one, recording telemetry in set_text.
    #
    # This only fires for the Input displayable's own internal keystroke/
    # paste handling, which is the ONLY caller of an InputValue's
    # set_text(). A SET TEST button instead assigns the backing store
    # variable directly (bypassing this wrapper entirely), so
    # "KEYBOARD CHANGE OBSERVED" can never be produced by a button click -
    # only by the Input displayable itself processing real input events.
    # ------------------------------------------------------------------

    class _VneDiagTelemetryInputValue(InputValue):
        def __init__(self, inner, probe_key):
            self.inner = inner
            self.probe_key = probe_key
            self.default = getattr(inner, "default", True)
            self.editable = getattr(inner, "editable", True)
            self.returnable = getattr(inner, "returnable", False)

        def get_text(self):
            return self.inner.get_text()

        def set_text(self, s):
            self.inner.set_text(s)
            _vne_diag_record_probe_change(self.probe_key, len(s))

    def _vne_diag_record_probe_change(probe_key, new_length):
        import store
        store.vne_diag_last_probe_changed = probe_key
        state = dict(store.vne_diag_probe_change_events)
        state[probe_key] = {"ts": _vne_diag_now(), "length": new_length}
        store.vne_diag_probe_change_events = state
        _vne_diag_log(
            "INPUT",
            "KEYBOARD CHANGE OBSERVED",
            target=probe_key,
            result="len={}".format(new_length),
        )
        # No renpy.restart_interaction() here: the wrapped InputValue's own
        # set_text() (VariableInputValue/ScreenVariableInputValue) already
        # calls it; calling it twice per keystroke would be redundant.

    # ------------------------------------------------------------------
    # Bug observability checklist (section 13) — never inferred PASS from
    # the mere absence of an exception; every row states its evidence.
    # ------------------------------------------------------------------

    def _vne_diag_bug_checklist():
        import store
        rows = []

        def screen_row(name):
            for r in store.vne_diag_screens_snapshot:
                if r["name"] == name:
                    return r
            return None

        def disp_row(screen_name, disp_id):
            for r in store.vne_diag_displayables_snapshot:
                if r["screen"] == screen_name and r["id"] == disp_id:
                    return r
            return None

        status_to_verdict = {"YES": "PASS", "NO": "FAIL", "UNKNOWN": "UNKNOWN"}

        r = screen_row("aside_chat_log")
        if r is None:
            rows.append(("aside_chat_log showing during normal interaction", "NOT TESTED", "run CHECK ALL SCREENS while Aside is open"))
        else:
            rows.append(("aside_chat_log showing during normal interaction", status_to_verdict.get(r["status"], "UNKNOWN"), r.get("detail", "")))

        snap = store.vne_diag_aside_snapshot or {}
        if "message_text_readable" not in snap:
            rows.append(("message_text readable from an on-screen Action", "NOT TESTED", "run GET ASIDE message_text"))
        else:
            rows.append((
                "message_text readable from an on-screen Action",
                "PASS" if snap.get("message_text_readable") else "FAIL",
                snap.get("message_text_error", ""),
            ))

        if "message_text_set_confirmed" not in snap:
            rows.append(("message_text changeable via renpy.set_screen_variable", "NOT TESTED", "run SET ASIDE = TEST"))
            rows.append(("displayed text updates when message_text changes", "NOT TESTED", "run SET ASIDE = TEST, then look at the Aside screen"))
        else:
            v = "PASS" if snap.get("message_text_set_confirmed") else "FAIL"
            rows.append(("message_text changeable via renpy.set_screen_variable", v, snap.get("message_text_error", "")))
            rows.append((
                "displayed text updates when message_text changes",
                v,
                "readback equals set value" if snap.get("message_text_set_confirmed") else "readback differs from set value",
            ))

        r = disp_row("aside_chat_log", "aside_message_input")
        if r is None:
            rows.append(("aside_message_input discoverable by id", "NOT TESTED", "run CHECK ALL DISPLAYABLES"))
        else:
            rows.append(("aside_message_input discoverable by id", status_to_verdict.get(r["status"], "UNKNOWN"), r.get("detail", "")))

        last_focus = store.vne_diag_last_focus_request
        if not last_focus or "aside" not in str(last_focus.get("id", "")).lower():
            rows.append(("focus request on Aside input raises an exception", "NOT TESTED", "run REQUEST FOCUS: ASIDE INPUT"))
        else:
            v = "FAIL" if last_focus.get("error") else "PASS"
            rows.append((
                "focus request on Aside input raises an exception",
                v,
                last_focus.get("error") or "no exception raised (not proof of real keyboard focus)",
            ))

        confirmations = store.vne_diag_typing_confirmations or {}
        for key, label in (
            ("store_probe", "store-backed probe accepts keyboard input"),
            ("screen_probe", "screen-variable probe accepts keyboard input"),
        ):
            c = confirmations.get(key)
            if c is None:
                rows.append((label, "NOT TESTED", "open the probe screen, type an S, then click a CONFIRM S ... button"))
            else:
                rows.append((label, "PASS" if c["worked"] else "FAIL", "manually confirmed at {}".format(c["ts"])))

        modal = store.vne_diag_modal_input_result
        if modal is None:
            rows.append(("renpy.input accepts keyboard input", "NOT TESTED", "run RUN renpy.input CONTROL TEST"))
        else:
            rows.append(("renpy.input accepts keyboard input", modal.get("verdict", "UNKNOWN"), modal.get("error") or modal.get("value_preview", "")))

        rows.append((
            "config.disable_input unexpectedly True",
            "FAIL" if config.disable_input else "PASS",
            "config.disable_input={}".format(config.disable_input),
        ))

        rows.append((
            "a global key statement captures Enter/printable events",
            "NOT TESTED",
            "not programmatically verifiable via public API - requires manual source review of `key` statements",
        ))

        c = confirmations.get("multiline_probe")
        if c is None:
            rows.append(("multiline probe works without a viewport", "NOT TESTED", "open the multiline probe, type an S, then click a CONFIRM S ... button"))
        else:
            rows.append(("multiline probe works without a viewport", "PASS" if c["worked"] else "FAIL", "manually confirmed at {}".format(c["ts"])))

        return rows

    # ------------------------------------------------------------------
    # Overview / Layout snapshot helpers
    # ------------------------------------------------------------------

    def _vne_diag_collect_overview():
        import store
        rows = []
        rows.append(("diagnostics build marker", VNE_DIAG_BUILD_MARKER))
        ok, val = _vne_diag_safe(renpy.version)
        rows.append(("Ren'Py version", val if ok else "UNAVAILABLE"))
        rows.append(("Python version", sys.version.split()[0]))
        rows.append(("platform", platform.platform()))
        rows.append(("config.developer", config.developer))
        rows.append(("config.console", config.console))
        rows.append(("config.disable_input", config.disable_input))
        rows.append(("config.screen_width", config.screen_width))
        rows.append(("config.screen_height", config.screen_height))
        rows.append(("game directory", config.gamedir))
        ok, val = _vne_diag_safe(renpy.get_mouse_pos)
        rows.append(("mouse position", val if ok else "UNAVAILABLE"))
        ok, val = _vne_diag_safe(renpy.get_renderer_info)
        rows.append(("renderer", val.get("renderer", "UNAVAILABLE") if ok else "UNAVAILABLE"))
        rows.append(("provider (vne_aside_config_provider)", getattr(store, "vne_aside_config_provider", "UNAVAILABLE")))
        rows.append(("aside pending (aside_llm_pending)", getattr(store, "aside_llm_pending", "UNAVAILABLE")))
        rows.append(("aside history length", len(getattr(store, "aside_chat_history", []))))
        rows.append(("diagnostic event count", len(store.vne_diag_events)))
        rows.append(("last diagnostic result", store.vne_diag_last_result or "(none)"))
        rows.append(("latest export report path", store.vne_diag_last_export_path or "(none)"))
        rows.append(("open request count", store.vne_diag_open_request_count))
        rows.append(("last open source", store.vne_diag_last_open_source))
        rows.append(("last open result", store.vne_diag_last_open_result))
        ok_selftest, detail_selftest = _vne_diag_text_safety_selftest()
        rows.append(("TEXT SAFETY SELF-TEST", "PASS" if ok_selftest else "FAIL ({})".format(detail_selftest)))
        return rows

    def _vne_diag_collect_layout():
        rows = []
        rows.append(("configured screen size", "{}x{}".format(config.screen_width, config.screen_height)))
        ok, val = _vne_diag_safe(renpy.get_physical_size)
        rows.append(("physical window size", val if ok else "UNAVAILABLE"))

        ok, info = _vne_diag_safe(renpy.get_renderer_info)
        if ok:
            for key in ("renderer", "resizable", "additive", "model", "gpu_vendor", "gpu_name", "gpu_driver_version"):
                rows.append(("renderer.{}".format(key), info.get(key, "UNAVAILABLE")))
            rows.append(("renderer info (raw, bounded preview)", _vne_diag_json_preview(dict(info))))
        else:
            rows.append(("renderer info", "UNAVAILABLE"))

        ok, val = _vne_diag_safe(renpy.get_mouse_pos)
        rows.append(("mouse position", val if ok else "UNAVAILABLE"))
        rows.append(("active screen variants", getattr(config, "variants", "UNAVAILABLE")))
        rows.append(("platform", platform.platform()))
        ok, val = _vne_diag_safe(lambda: store._preferences.fullscreen)
        rows.append(("fullscreen preference", val if ok else "UNAVAILABLE"))
        return rows

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _vne_diag_narrative_root():
        try:
            return Path(config.gamedir).resolve().parent.parent.parent
        except Exception:
            return None

    def _vne_diag_build_report_text():
        import store
        lines = ["VNE Diagnostics - build {}".format(VNE_DIAG_BUILD_MARKER)]
        lines.append("generated: {}".format(_vne_diag_now()))
        lines.append("events shown: {}".format(len(store.vne_diag_events)))
        for ev in store.vne_diag_events[-40:]:
            lines.append("[{}] {} :: {} -> {}".format(ev["ts"], ev["category"], ev["action"], ev["result"]))
        return "\n".join(lines)

    def _vne_diag_export_report():
        import store
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        lines = []
        lines.append("# VNE Runtime Diagnostics Report")
        lines.append("")
        lines.append("- generated: {}".format(ts))
        lines.append("- build marker: {}".format(VNE_DIAG_BUILD_MARKER))
        lines.append("")

        lines.append("## Runtime Overview")
        for label, value in _vne_diag_collect_overview():
            lines.append("- **{}**: {}".format(label, value))
        lines.append("")

        lines.append("## Known Screens")
        if store.vne_diag_screens_snapshot:
            for row in store.vne_diag_screens_snapshot:
                lines.append("- {}: {} {}".format(row["name"], row["status"], ("({})".format(row["detail"]) if row.get("detail") else "")))
        else:
            lines.append("- (no snapshot taken - use CHECK ALL SCREENS)")
        lines.append("")

        lines.append("## Known Displayables")
        if store.vne_diag_displayables_snapshot:
            for row in store.vne_diag_displayables_snapshot:
                lines.append("- {}::{} -> {} {}".format(row["screen"], row["id"], row["status"], ("({})".format(row["detail"]) if row.get("detail") else "")))
        else:
            lines.append("- (no snapshot taken - use CHECK ALL DISPLAYABLES)")
        lines.append("")

        lines.append("## Input Probe State")
        lines.append("- store probe length: {}".format(len(store.vne_diag_store_probe_text)))
        lines.append("- store probe preview: {}".format(_vne_diag_preview(store.vne_diag_store_probe_text)))
        lines.append("- modal renpy.input result: {}".format(store.vne_diag_modal_input_result))
        lines.append("- manual typing confirmations: {}".format(store.vne_diag_typing_confirmations))
        lines.append("- S key results: {}".format(store.vne_diag_s_key_results))
        lines.append("- probe open requests: {}".format(store.vne_diag_probe_open_requests))
        lines.append("- config.keymap['screenshot']: {}".format(config.keymap.get("screenshot", [])))
        lines.append("")

        lines.append("## Aside Bridge Snapshot")
        aside = store.vne_diag_aside_snapshot or {}
        if aside:
            for key in sorted(aside.keys()):
                lines.append("- **{}**: {}".format(key, aside[key]))
        else:
            lines.append("- (no snapshot yet - use REFRESH ASIDE SNAPSHOT)")
        lines.append("")

        lines.append("## Keymap / Input Configuration")
        lines.append("- config.disable_input: {}".format(config.disable_input))
        lines.append("- config.keymap['input_next_line']: {}".format(config.keymap.get("input_next_line")))
        lines.append("")

        lines.append("## Layout & Runtime")
        for label, value in _vne_diag_collect_layout():
            lines.append("- **{}**: {}".format(label, value))
        lines.append("")

        lines.append("## Open/Close Diagnostics")
        lines.append("- open request count: {}".format(store.vne_diag_open_request_count))
        lines.append("- last open source: {}".format(store.vne_diag_last_open_source))
        lines.append("- last open result: {}".format(store.vne_diag_last_open_result))
        lines.append("- last open exception: {}".format(store.vne_diag_last_open_exception or "(none)"))
        lines.append("")

        lines.append("## Owner Runtime Acceptance")
        if store.vne_diag_runtime_acceptance:
            for key in sorted(store.vne_diag_runtime_acceptance.keys()):
                entry = store.vne_diag_runtime_acceptance[key]
                lines.append("- **{}**: {} (at {})".format(key, entry["value"], entry["ts"]))
        else:
            lines.append("- (no owner confirmations recorded yet)")
        lines.append("")

        lines.append("## Bug Observability Checklist")
        for question, verdict, detail in _vne_diag_bug_checklist():
            lines.append("- [{}] {} - {}".format(verdict, question, detail))
        lines.append("")

        recent = store.vne_diag_events[-50:]
        lines.append("## Diagnostic Events (most recent {})".format(len(recent)))
        for ev in recent:
            lines.append("- `{}` [{}] {} target={!r} result={!r} details={!r}".format(
                ev["ts"], ev["category"], ev["action"], ev["target"], ev["result"], ev["details"],
            ))
        lines.append("")

        lines.append("## Warning")
        lines.append(
            "Focus requests (`renpy.set_focus`) are **not** proof of successful keyboard focus. "
            "Opening a screen is only ever reported as SHOW REQUESTED - SHOWING indicators are a "
            "live renpy.get_screen() check, never inferred from lack of exception. Pressing S with "
            "no input focused triggers Ren'Py's own default screenshot keymap binding - this is "
            "expected engine behavior, not a bug in this file."
        )
        lines.append("")

        content = "\n".join(lines) + "\n"

        root = _vne_diag_narrative_root()
        target_path = None
        fallback = False
        if root is not None:
            try:
                handoffs = root / "LOCAL_STORAGE" / "handoffs"
                handoffs.mkdir(parents=True, exist_ok=True)
                candidate = handoffs / "VNE_RUNTIME_DIAGNOSTICS_LATEST.md"
                candidate.write_text(content, encoding="utf-8")
                target_path = candidate
            except Exception:
                target_path = None

        if target_path is None:
            fallback = True
            fallback_dir = Path(renpy.config.savedir) / "vne_diagnostics_reports"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            target_path = fallback_dir / "VNE_RUNTIME_DIAGNOSTICS_LATEST.md"
            target_path.write_text(content, encoding="utf-8")

        store.vne_diag_last_export_path = str(target_path)
        _vne_diag_log(
            "EXPORT",
            "EXPORT UTF-8 REPORT",
            target=str(target_path),
            result=("FALLBACK (LOCAL_STORAGE unavailable)" if fallback else "OK"),
        )
        renpy.restart_interaction()

    def _vne_diag_clear_log():
        import store
        store.vne_diag_events = []
        store.vne_diag_last_result = "log cleared"
        renpy.restart_interaction()

    def _vne_diag_add_test_event():
        _vne_diag_log("SYSTEM", "ADD TEST EVENT", result="OK", details="manually added test event")
        renpy.restart_interaction()

    # ------------------------------------------------------------------
    # Built-in tools helpers
    # ------------------------------------------------------------------

    def _vne_diag_show_autoreload_status():
        ok, val = _vne_diag_safe(renpy.get_autoreload)
        _vne_diag_log("SYSTEM", "SHOW AUTORELOAD STATUS", result=(str(val) if ok else "UNAVAILABLE"))
        renpy.restart_interaction()

    def _vne_diag_toggle_autoreload():
        ok, cur = _vne_diag_safe(renpy.get_autoreload)
        target = (not cur) if ok else True
        ok2, err2 = _vne_diag_safe(renpy.set_autoreload, target)
        _vne_diag_log(
            "SYSTEM",
            "TOGGLE AUTORELOAD",
            result=("OK -> {}".format(target) if ok2 else "ERROR"),
            details=(err2 or ""),
        )
        renpy.restart_interaction()

    def _vne_diag_reload_script():
        _vne_diag_log("SYSTEM", "RELOAD SCRIPT", result="requested")
        renpy.reload_script()

    def _vne_diag_request_screen_profile():
        ok, err = _vne_diag_safe(renpy.profile_screen, "aside_chat_log", request=True, time=True, debug=True)
        _vne_diag_log(
            "SYSTEM",
            "REQUEST aside_chat_log SCREEN PROFILE",
            result=("armed - press F8 while Aside is open" if ok else "ERROR"),
            details=(err or ""),
        )
        renpy.restart_interaction()

    def _vne_diag_shortcuts_text():
        return "\n".join([
            "Shift+O  Console",
            "Shift+D  Developer Menu",
            "Shift+I  Style Inspector",
            "Shift+R  Reload / Autoreload",
            "F8       Requested screen profiling (after REQUEST SCREEN PROFILE)",
        ])

    # Register the always-on, non-interactive diagnostic overlay layer.
    # Dev-only, mirrors the story_state_dev_overlay.rpy registration pattern.
    if config.developer:
        if "vne_diag_visual_overlays" not in config.overlay_screens:
            config.overlay_screens.append("vne_diag_visual_overlays")


# ============================================================
# STYLES (dark dev UI, matching aside.rpy / story_state_dev_overlay.rpy)
# ============================================================

style vne_diag_btn is button:
    background Solid("#3a4658")
    hover_background Solid("#52657f")
    selected_background Solid("#52657f")
    padding (8, 4)

style vne_diag_btn_text is button_text:
    color "#ffffff"
    size 12

style vne_diag_btn_danger is vne_diag_btn:
    background Solid("#5a3a3a")
    hover_background Solid("#7f5252")

style vne_diag_btn_danger_text is vne_diag_btn_text:
    color "#ffffff"

style vne_diag_tab_btn is button:
    background Solid("#242430")
    hover_background Solid("#33334a")
    selected_background Solid("#3a4658")
    padding (6, 3)

style vne_diag_tab_btn_text is button_text:
    color "#999999"
    hover_color "#cccccc"
    selected_color "#ffffff"
    size 11


# ============================================================
# MAIN DIAGNOSTICS HUB
#
# RN-DIAG-01-R4: all seven tabs' content is built directly inline here (no
# `use` statements, no separate per-tab or row-renderer screens) to remove
# every layer of indirection between the tab-switch state and the visible
# content. Each tab begins with an unconditional "TAB CONTENT ACTIVE: ..."
# marker so dispatch failures and content failures are visually
# distinguishable from each other.
# ============================================================

screen vne_dev_diagnostics():

    # modal/zorder MUST be unconditional, direct children of the screen
    # block (RN-DIAG-01-R2 finding - see file header).
    modal True
    zorder 500

    if config.developer:
        $ _diag_showing_status, _diag_showing_detail = _vne_diag_screen_status("vne_dev_diagnostics")
        $ _diag_showing_color = "#7fdc7f" if _diag_showing_status == "YES" else "#e08a8a"
        $ _diag_status_line = _vne_diag_safe_text("showing={}  opens={}  last_source={}  tab={}".format(
            _diag_showing_status, vne_diag_open_request_count, vne_diag_last_open_source, vne_diag_tab,
        ), 300)
        $ _diag_ra_line = _vne_diag_safe_text(
            "  ".join("{}={}".format(k, vne_diag_runtime_acceptance[k]["value"]) for k in sorted(vne_diag_runtime_acceptance.keys()))
            if vne_diag_runtime_acceptance else "(no owner confirmations recorded yet)",
            300,
        )
        $ _diag_last_result_safe = _vne_diag_safe_text(vne_diag_last_result, 300)

        frame:
            xalign 0.5
            yalign 0.5
            xsize int(config.screen_width * 0.94)
            ysize int(config.screen_height * 0.92)
            background Solid("#14141c")
            padding (12, 10)

            vbox:
                spacing 5
                xfill True
                yfill True

                hbox:
                    xfill True
                    text "VNE Diagnostics - [VNE_DIAG_BUILD_MARKER]":
                        size 15
                        bold True
                        color "#ffffff"
                        xfill True
                    textbutton "Close":
                        style "vne_diag_btn"
                        action Function(_vne_diag_close)

                text "[_diag_status_line]":
                    size 10
                    color _diag_showing_color

                hbox:
                    spacing 3
                    for _tab_id, _tab_label in [
                        ("overview", "Overview"),
                        ("screens", "Screens & Focus"),
                        ("input", "Input Lab"),
                        ("aside", "Aside Bridge"),
                        ("layout", "Layout & Runtime"),
                        ("logs", "Logs & Export"),
                        ("tools", "Built-in Tools"),
                    ]:
                        textbutton _tab_label:
                            style "vne_diag_tab_btn"
                            text_size 11
                            selected (vne_diag_tab == _tab_id)
                            action SetVariable("vne_diag_tab", _tab_id)

                # ---- Single outer scrollable body: plain hbox, no `side` ----
                frame:
                    xfill True
                    yfill True
                    background Solid("#1a1a24")
                    padding (8, 8)

                    hbox:
                        xfill True
                        yfill True
                        spacing 4

                        viewport:
                            id "vne_diag_body_viewport"
                            xfill True
                            yfill True
                            mousewheel True
                            draggable True
                            pagekeys True

                            vbox:
                                xfill True
                                spacing 6

                                # ============================================================
                                # TAB: OVERVIEW
                                # ============================================================
                                if vne_diag_tab == "overview":
                                    text "TAB CONTENT ACTIVE: OVERVIEW":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _overview_rows = _vne_diag_collect_overview()
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _label, _value in _overview_rows:
                                            $ _label_safe = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe]:":
                                                    xsize 240
                                                    color "#88ccff"
                                                    size 12
                                                text "[_value_safe]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                    text "DIAGNOSTICS CONTENT SELF-CHECK (SOURCE PRESENCE ONLY)":
                                        size 12
                                        bold True
                                        color "#88ccff"

                                    $ _self_check_rows = _vne_diag_content_self_check()
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _label, _value in _self_check_rows:
                                            $ _label_safe2 = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe2 = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe2]:":
                                                    xsize 280
                                                    color "#e0c97f"
                                                    size 12
                                                text "[_value_safe2]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                # ============================================================
                                # TAB: SCREENS & FOCUS
                                # ============================================================
                                elif vne_diag_tab == "screens":
                                    text "TAB CONTENT ACTIVE: SCREENS & FOCUS":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _screen_rows = [
                                        {"label": r["name"], "status": r["status"], "detail": r.get("detail", "")}
                                        for r in vne_diag_screens_snapshot
                                    ]
                                    $ _disp_rows = [
                                        {"label": "{} :: {}".format(r["screen"], r["id"]), "status": r["status"], "detail": r.get("detail", "")}
                                        for r in vne_diag_displayables_snapshot
                                    ]
                                    $ _last_focus_line_safe = _vne_diag_safe_text((
                                        "screen={} id={} found_before={} error={}".format(
                                            vne_diag_last_focus_request["screen"],
                                            vne_diag_last_focus_request["id"],
                                            vne_diag_last_focus_request["found_before"],
                                            vne_diag_last_focus_request["error"],
                                        ) if vne_diag_last_focus_request else "(none yet)"
                                    ), 300)

                                    text "Known Screens" size 13 bold True color "#ffffff"
                                    vbox:
                                        spacing 3
                                        xfill True
                                        if not _screen_rows:
                                            text "(no snapshot - click CHECK ALL SCREENS)" color "#666666" size 12
                                        for _row in _screen_rows:
                                            $ _status_color = (
                                                "#7fdc7f" if _row["status"] in ("YES", "FOUND", "PASS") else
                                                "#e08a8a" if _row["status"] in ("NO", "NOT FOUND", "FAIL") else
                                                "#999999" if _row["status"] == "NOT TESTED" else
                                                "#e0c97f"
                                            )
                                            $ _row_label_safe = _vne_diag_safe_text(_row["label"], 200)
                                            $ _row_status_safe = _vne_diag_safe_text(_row["status"], 60)
                                            $ _row_detail_safe = _vne_diag_safe_text(_row.get("detail", ""), 200)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_row_label_safe]":
                                                    xsize 320
                                                    color "#e0e0e0"
                                                    size 12
                                                text "[_row_status_safe]":
                                                    color _status_color
                                                    size 12
                                                    xsize 90
                                                text "[_row_detail_safe]":
                                                    color "#888888"
                                                    size 11
                                                    xfill True

                                    text "Known Displayables" size 13 bold True color "#ffffff"
                                    vbox:
                                        spacing 3
                                        xfill True
                                        if not _disp_rows:
                                            text "(no snapshot - click CHECK ALL DISPLAYABLES)" color "#666666" size 12
                                        for _row in _disp_rows:
                                            $ _status_color2 = (
                                                "#7fdc7f" if _row["status"] in ("YES", "FOUND", "PASS") else
                                                "#e08a8a" if _row["status"] in ("NO", "NOT FOUND", "FAIL") else
                                                "#999999" if _row["status"] == "NOT TESTED" else
                                                "#e0c97f"
                                            )
                                            $ _row_label_safe2 = _vne_diag_safe_text(_row["label"], 200)
                                            $ _row_status_safe2 = _vne_diag_safe_text(_row["status"], 60)
                                            $ _row_detail_safe2 = _vne_diag_safe_text(_row.get("detail", ""), 200)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_row_label_safe2]":
                                                    xsize 320
                                                    color "#e0e0e0"
                                                    size 12
                                                text "[_row_status_safe2]":
                                                    color _status_color2
                                                    size 12
                                                    xsize 90
                                                text "[_row_detail_safe2]":
                                                    color "#888888"
                                                    size 11
                                                    xfill True

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "CHECK ALL SCREENS":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_check_all_screens)
                                        textbutton "CHECK ALL DISPLAYABLES":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_check_all_displayables)
                                        textbutton "REQUEST FOCUS: ASIDE INPUT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_focus, "aside_chat_log", "aside_message_input")

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "REQUEST FOCUS: STORE PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_focus, "vne_diag_store_probe_screen", "vne_diag_store_probe_input")
                                        textbutton "REQUEST FOCUS: SCREEN PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_focus, "vne_diag_screen_probe_screen", "vne_diag_screen_probe_input")
                                        textbutton "REQUEST FOCUS: MULTILINE PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_focus, "vne_diag_multiline_probe_screen", "vne_diag_multiline_probe_input")

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "CLEAR INPUT FOCUS":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_clear_focus)
                                        textbutton "REFRESH SNAPSHOT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action [Function(_vne_diag_check_all_screens), Function(_vne_diag_check_all_displayables)]

                                    text "Last focus request: [_last_focus_line_safe]":
                                        size 10
                                        color "#e0c97f"
                                        xfill True
                                    text "A successful call only means FOCUS REQUESTED - never proof of real keyboard focus.":
                                        size 10
                                        color "#666666"
                                        xfill True

                                # ============================================================
                                # TAB: INPUT LAB
                                # ============================================================
                                elif vne_diag_tab == "input":
                                    text "TAB CONTENT ACTIVE: INPUT LAB":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    text "Each probe below is an independent, isolated modal screen with exactly one input.":
                                        size 11
                                        color "#aaaaaa"
                                        xfill True

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "OPEN STORE PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_open_store_probe)
                                        textbutton "OPEN SCREEN-VARIABLE PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_open_screen_probe)

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "OPEN MULTILINE PROBE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_open_multiline_probe)
                                        textbutton "RUN MODAL renpy.input CONTROL TEST":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_run_input_control_test)

                                    text "Latest Probe Results" size 12 bold True color "#88ccff"
                                    $ _probe_rows = [
                                        {"label": "Store-backed probe", "status": _vne_diag_probe_result_label("store_probe"), "detail": ""},
                                        {"label": "Screen-variable probe", "status": _vne_diag_probe_result_label("screen_probe"), "detail": ""},
                                        {"label": "Multiline probe", "status": _vne_diag_probe_result_label("multiline_probe"), "detail": ""},
                                    ]
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _row in _probe_rows:
                                            $ _status_color3 = (
                                                "#7fdc7f" if _row["status"] in ("YES", "FOUND", "PASS", "TYPING WORKS") else
                                                "#e08a8a" if _row["status"] in ("NO", "NOT FOUND", "FAIL", "TYPING FAILS", "S SCREENSHOT TRIGGERED") else
                                                "#999999" if _row["status"] == "NOT TESTED" else
                                                "#e0c97f"
                                            )
                                            $ _row_label_safe3 = _vne_diag_safe_text(_row["label"], 200)
                                            $ _row_status_safe3 = _vne_diag_safe_text(_row["status"], 60)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_row_label_safe3]":
                                                    xsize 240
                                                    color "#e0e0e0"
                                                    size 12
                                                text "[_row_status_safe3]":
                                                    color _status_color3
                                                    size 12
                                                    xfill True

                                    $ _modal = vne_diag_modal_input_result
                                    if _modal is not None:
                                        $ _modal_preview_safe = _vne_diag_safe_text(_modal["value_preview"], 200)
                                        text "Modal control test: verdict=[_modal['verdict']] length=[_modal['length']] preview=[_modal_preview_safe]":
                                            size 11
                                            color "#aaaaaa"
                                            xfill True

                                    text "Input State Indicators" size 12 bold True color "#88ccff"
                                    $ _modal_len_display = _modal["length"] if _modal else "NOT TESTED"
                                    $ _last_focus_display = (
                                        "{}::{}".format(vne_diag_last_focus_request["screen"], vne_diag_last_focus_request["id"])
                                        if vne_diag_last_focus_request else "(none)"
                                    )
                                    $ _input_indicator_rows = [
                                        ("config.disable_input", config.disable_input),
                                        ("config.keymap['input_next_line']", config.keymap.get("input_next_line")),
                                        ("config.keymap['screenshot']", config.keymap.get("screenshot", [])),
                                        ("store probe length", len(vne_diag_store_probe_text)),
                                        ("modal input result length", _modal_len_display),
                                        ("last focus request", _last_focus_display),
                                        ("last probe that visibly changed", vne_diag_last_probe_changed or "(none)"),
                                    ]
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _label, _value in _input_indicator_rows:
                                            $ _label_safe3 = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe3 = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe3]:":
                                                    xsize 240
                                                    color "#88ccff"
                                                    size 12
                                                text "[_value_safe3]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                    text "S without an active input focused may trigger Ren'Py's default screenshot keymap binding (config.keymap['screenshot']) - expected engine behavior, used here only as an owner-observed focus indicator.":
                                        size 10
                                        color "#666666"
                                        xfill True

                                    text "Bug Observability Checklist (12 questions, section 13 of RN-DIAG-01)" size 12 bold True color "#88ccff"
                                    $ _checklist_rows = [
                                        {"label": q, "status": v, "detail": d}
                                        for q, v, d in _vne_diag_bug_checklist()
                                    ]
                                    vbox:
                                        spacing 3
                                        xfill True
                                        if not _checklist_rows:
                                            text "(no data)" color "#666666" size 12
                                        for _row in _checklist_rows:
                                            $ _status_color4 = (
                                                "#7fdc7f" if _row["status"] in ("YES", "FOUND", "PASS") else
                                                "#e08a8a" if _row["status"] in ("NO", "NOT FOUND", "FAIL") else
                                                "#999999" if _row["status"] == "NOT TESTED" else
                                                "#e0c97f"
                                            )
                                            $ _row_label_safe4 = _vne_diag_safe_text(_row["label"], 200)
                                            $ _row_status_safe4 = _vne_diag_safe_text(_row["status"], 60)
                                            $ _row_detail_safe4 = _vne_diag_safe_text(_row.get("detail", ""), 200)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_row_label_safe4]":
                                                    xsize 320
                                                    color "#e0e0e0"
                                                    size 12
                                                text "[_row_status_safe4]":
                                                    color _status_color4
                                                    size 12
                                                    xsize 90
                                                text "[_row_detail_safe4]":
                                                    color "#888888"
                                                    size 11
                                                    xfill True

                                    text "FORENSICS (R6) - controlled Cases B/C/D" size 12 bold True color "#88ccff"
                                    text "See RN_DIAG_01_R6_FORENSIC_ADDENDUM for the full hypothesis matrix. These probes isolate whether the R5 telemetry wrapper, or Ren'Py's own single-editable-input mechanism, blocks typing.":
                                        size 10
                                        color "#666666"
                                        xfill True

                                    $ _simultaneous_inputs = _vne_diag_count_simultaneous_inputs()
                                    $ _simultaneous_inputs_safe = _vne_diag_safe_text(", ".join(_simultaneous_inputs) if _simultaneous_inputs else "(none currently showing)", 300)
                                    text "Known input-bearing screens currently showing: [_simultaneous_inputs_safe]":
                                        size 10
                                        color "#e0c97f"
                                        xfill True

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "OPEN CASE B PROBE (show_screen, no wrapper)":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_open_case_b_probe)
                                        textbutton "RUN CASE C (call_screen, cleared layers)":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_open_case_c_probe)

                                    text "Case D = the SAME Case B screen, opened after closing Aside first (no separate button - compare the 'Current context' line shown on that screen).":
                                        size 10
                                        color "#666666"
                                        xfill True

                                    if vne_diag_case_c_result is not None:
                                        $ _case_c_ts_safe = _vne_diag_safe_text(vne_diag_case_c_result["ts"], 60)
                                        $ _case_c_len_safe = _vne_diag_safe_text(vne_diag_case_c_result["result"]["length"] if vne_diag_case_c_result["ok"] else "(error)", 60)
                                        $ _case_c_preview_result_safe = _vne_diag_safe_text(vne_diag_case_c_result["result"]["preview"] if vne_diag_case_c_result["ok"] else vne_diag_case_c_result["error"], 200)
                                        $ _case_c_result_color = "#7fdc7f" if vne_diag_case_c_result["ok"] else "#e08a8a"
                                        text "Last Case C result @ [_case_c_ts_safe]: length=[_case_c_len_safe] preview=[_case_c_preview_result_safe]":
                                            size 10
                                            color _case_c_result_color
                                            xfill True
                                    else:
                                        text "Case C not run yet." size 10 color "#666666"

                                # ============================================================
                                # TAB: ASIDE BRIDGE
                                # ============================================================
                                elif vne_diag_tab == "aside":
                                    text "TAB CONTENT ACTIVE: ASIDE BRIDGE":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _aside_snapshot = vne_diag_aside_snapshot or {}
                                    $ _aside_rows = [(k, _aside_snapshot[k]) for k in sorted(_aside_snapshot.keys())]
                                    vbox:
                                        spacing 3
                                        xfill True
                                        if not _aside_rows:
                                            text "(no data)" color "#666666" size 12
                                        for _label, _value in _aside_rows:
                                            $ _label_safe4 = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe4 = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe4]:":
                                                    xsize 240
                                                    color "#88ccff"
                                                    size 12
                                                text "[_value_safe4]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "REFRESH ASIDE SNAPSHOT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_refresh_aside_snapshot)
                                        textbutton "GET ASIDE message_text":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_aside_get_message_text)

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "SET ASIDE = TEST":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_aside_set_message_text, "diagnostic test value")
                                        textbutton "APPEND X TO ASIDE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_aside_append_marker, "X")

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "CLEAR ASIDE message_text":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_aside_set_message_text, "")
                                        textbutton "REQUEST FOCUS: ASIDE INPUT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_focus, "aside_chat_log", "aside_message_input")

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "COPY ASIDE SNAPSHOT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_copy_text, "ASIDE", "COPY ASIDE SNAPSHOT", _vne_diag_json_preview(_aside_snapshot))
                                        textbutton "ADD ASIDE DIAGNOSTIC MARKER":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_aside_add_marker)

                                # ============================================================
                                # TAB: LAYOUT & RUNTIME
                                # ============================================================
                                elif vne_diag_tab == "layout":
                                    text "TAB CONTENT ACTIVE: LAYOUT & RUNTIME":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _layout_rows = _vne_diag_collect_layout()
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _label, _value in _layout_rows:
                                            $ _label_safe5 = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe5 = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe5]:":
                                                    xsize 240
                                                    color "#88ccff"
                                                    size 12
                                                text "[_value_safe5]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                    text "Diagnostic Visual Overlays (semi-transparent, non-interactive)" size 11 bold True color "#88ccff"

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "SHOW GRID":
                                            style "vne_diag_btn"
                                            text_size 11
                                            selected vne_diag_show_grid
                                            action ToggleVariable("vne_diag_show_grid")
                                        textbutton "SHOW CENTER LINES":
                                            style "vne_diag_btn"
                                            text_size 11
                                            selected vne_diag_show_center
                                            action ToggleVariable("vne_diag_show_center")
                                        textbutton "SHOW SAFE AREA":
                                            style "vne_diag_btn"
                                            text_size 11
                                            selected vne_diag_show_safe_area
                                            action ToggleVariable("vne_diag_show_safe_area")

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "SHOW MOUSE CROSSHAIR":
                                            style "vne_diag_btn"
                                            text_size 11
                                            selected vne_diag_show_crosshair
                                            action ToggleVariable("vne_diag_show_crosshair")
                                        textbutton "SHOW EXPECTED ASIDE REGIONS":
                                            style "vne_diag_btn"
                                            text_size 11
                                            selected vne_diag_show_aside_regions
                                            action ToggleVariable("vne_diag_show_aside_regions")

                                    text "Aside regions are illustrative EXPECTED layout boxes, not measured bounds.":
                                        size 10
                                        color "#666666"
                                        xfill True

                                # ============================================================
                                # TAB: LOGS & EXPORT
                                # ============================================================
                                elif vne_diag_tab == "logs":
                                    text "TAB CONTENT ACTIVE: LOGS & EXPORT":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _event_count = len(vne_diag_events)
                                    $ _events_reversed = list(reversed(vne_diag_events))
                                    $ _export_path_display_safe = _vne_diag_safe_text(vne_diag_last_export_path or "(none yet)", 300)

                                    text "Diagnostic Event Log ([_event_count]/[VNE_DIAG_MAX_EVENTS])":
                                        size 13
                                        bold True
                                        color "#ffffff"

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "CLEAR LOG":
                                            style "vne_diag_btn_danger"
                                            text_size 11
                                            action Function(_vne_diag_clear_log)
                                        textbutton "ADD TEST EVENT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_add_test_event)

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "REFRESH SNAPSHOT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action [
                                                Function(_vne_diag_check_all_screens),
                                                Function(_vne_diag_check_all_displayables),
                                                Function(_vne_diag_refresh_aside_snapshot),
                                            ]
                                        textbutton "COPY VISIBLE REPORT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_copy_text, "EXPORT", "COPY VISIBLE REPORT", _vne_diag_build_report_text())

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "EXPORT UTF-8 REPORT":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_export_report)

                                    text "Latest export: [_export_path_display_safe]":
                                        size 10
                                        color "#888888"
                                        xfill True

                                    vbox:
                                        spacing 2
                                        xfill True
                                        if not _events_reversed:
                                            text "(no events yet)" color "#666666" size 11
                                        for _ev in _events_reversed:
                                            $ _ev_line_safe = _vne_diag_safe_text("[{}] {} :: {} -> {} target={} {}".format(
                                                _ev["ts"], _ev["category"], _ev["action"], _ev["result"], _ev["target"],
                                                ("({})".format(_ev["details"]) if _ev["details"] else ""),
                                            ), 400)
                                            text _ev_line_safe:
                                                size 10
                                                color "#cccccc"
                                                xfill True

                                # ============================================================
                                # TAB: BUILT-IN TOOLS
                                # ============================================================
                                elif vne_diag_tab == "tools":
                                    text "TAB CONTENT ACTIVE: BUILT-IN TOOLS":
                                        size 12
                                        bold True
                                        color "#7fdc7f"

                                    $ _autoreload_ok, _autoreload_val = _vne_diag_safe(renpy.get_autoreload)
                                    $ _autoreload_display_safe = _vne_diag_safe_text(_autoreload_val if _autoreload_ok else "UNAVAILABLE", 60)
                                    $ _shortcut_rows = [
                                        ("Shift+O", "Console"),
                                        ("Shift+D", "Developer Menu"),
                                        ("Shift+I", "Style Inspector"),
                                        ("Shift+R", "Reload / Autoreload"),
                                        ("F8", "Requested screen profiling (arm it below first)"),
                                    ]
                                    vbox:
                                        spacing 3
                                        xfill True
                                        for _label, _value in _shortcut_rows:
                                            $ _label_safe6 = _vne_diag_safe_text(_label, 120)
                                            $ _value_safe6 = _vne_diag_safe_text(_value, 300)
                                            hbox:
                                                xfill True
                                                spacing 6
                                                text "[_label_safe6]:":
                                                    xsize 240
                                                    color "#88ccff"
                                                    size 12
                                                text "[_value_safe6]":
                                                    color "#e0e0e0"
                                                    size 12
                                                    xfill True

                                    text "autoreload flag: [_autoreload_display_safe]":
                                        size 12
                                        color "#aaaaaa"

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "SHOW AUTORELOAD STATUS":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_show_autoreload_status)
                                        textbutton "TOGGLE AUTORELOAD":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_toggle_autoreload)

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "RELOAD SCRIPT":
                                            style "vne_diag_btn_danger"
                                            text_size 11
                                            action Confirm(
                                                "Reload the script now? This saves, reloads the script, and reloads the save (dev-only).",
                                                yes=Function(_vne_diag_reload_script),
                                            )
                                        textbutton "REQUEST aside_chat_log SCREEN PROFILE":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_request_screen_profile)

                                    hbox:
                                        spacing 4
                                        xfill True
                                        textbutton "COPY BUILT-IN TOOL SHORTCUTS":
                                            style "vne_diag_btn"
                                            text_size 11
                                            action Function(_vne_diag_copy_text, "SYSTEM", "COPY BUILT-IN TOOL SHORTCUTS", _vne_diag_shortcuts_text())

                        vbar:
                            xsize 10
                            yfill True
                            value YScrollValue("vne_diag_body_viewport")
                            unscrollable "hide"
                            base_bar Frame(Solid("#2a2a3a"), 6, 0)
                            thumb Frame(Solid("#5a5a7a"), 6, 0)

                text "Last: [_diag_last_result_safe]":
                    size 10
                    color "#666666"
                    xfill True

                # ---- Runtime Acceptance: visible on every tab, owner-only ----
                frame:
                    xfill True
                    background Solid("#101018")
                    padding (5, 3)
                    vbox:
                        spacing 2
                        xfill True
                        text "RUNTIME ACCEPTANCE (owner-controlled; never modifies game state)":
                            size 10
                            bold True
                            color "#88ccff"
                        hbox:
                            spacing 3
                            xfill True
                            textbutton "UI FITS":
                                style "vne_diag_btn"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "ui_fits", True)
                            textbutton "UI OVERFLOW":
                                style "vne_diag_btn_danger"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "ui_fits", False)
                            textbutton "TYPING WORKS":
                                style "vne_diag_btn"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "typing_works", True)
                            textbutton "TYPING FAILS":
                                style "vne_diag_btn_danger"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "typing_works", False)
                            textbutton "ASIDE-OPEN WORKS":
                                style "vne_diag_btn"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "open_from_aside", True)
                            textbutton "ASIDE-OPEN FAILS":
                                style "vne_diag_btn_danger"
                                text_size 9
                                action Function(_vne_diag_set_runtime_acceptance, "open_from_aside", False)
                        text "[_diag_ra_line]":
                            size 9
                            color "#888888"
                            xfill True


# ============================================================
# ISOLATED PROBE SCREEN A: store-backed single-line probe
# ============================================================

screen vne_diag_store_probe_screen():
    modal True
    zorder 600

    # RN-DIAG-01-R5: one-shot (repeat False is Timer's own default; stated
    # explicitly here) delayed focus request, fired once after this show,
    # by which point the screen and its input displayable definitely exist.
    timer 0.15 action Function(_vne_diag_request_focus, "vne_diag_store_probe_screen", "vne_diag_store_probe_input") repeat False

    $ _store_screen_showing, _ = _vne_diag_screen_status("vne_diag_store_probe_screen")

    frame:
        xalign 0.5
        yalign 0.5
        xsize int(config.screen_width * 0.7)
        ysize int(config.screen_height * 0.7)
        background Solid("#14141c")
        padding (12, 10)

        vbox:
            spacing 8
            xfill True
            yfill True

            hbox:
                xfill True
                text "Store Probe - [VNE_DIAG_BUILD_MARKER]":
                    size 14
                    bold True
                    color "#ffffff"
                    xfill True
                textbutton "Close":
                    style "vne_diag_btn"
                    action Hide("vne_diag_store_probe_screen")

            $ _store_screen_showing_color = "#7fdc7f" if _store_screen_showing == "YES" else "#e08a8a"
            text "SHOWING: [_store_screen_showing]  (screen: vne_diag_store_probe_screen)":
                size 10
                color _store_screen_showing_color

            text "Exactly one input on this screen (VariableInputValue).":
                size 11
                color "#aaaaaa"
                xfill True

            text "CLICK INSIDE THE FIELD AND TYPE":
                size 12
                bold True
                color "#ffcc00"

            frame:
                xfill True
                background Solid("#5a5a6e")
                padding (2, 2)
                frame:
                    xfill True
                    xminimum 400
                    yminimum 48
                    background Solid("#2a2a38")
                    padding (10, 8)
                    input:
                        id "vne_diag_store_probe_input"
                        default_focus 100
                        value _VneDiagTelemetryInputValue(VariableInputValue("vne_diag_store_probe_text"), "store_probe")
                        length 500
                        xfill True
                        copypaste True
                        color "#ffffff"

            text "BACKING VALUE PREVIEW":
                size 10
                bold True
                color "#88ccff"
            $ _store_preview_safe = _vne_diag_safe_text(_vne_diag_preview(vne_diag_store_probe_text), 200)
            $ _store_len = len(vne_diag_store_probe_text)
            text "text: [_store_preview_safe]  (len=[_store_len])":
                size 11
                color "#aaaaaa"

            $ _store_disp_status, _store_disp_detail = _vne_diag_displayable_status("vne_diag_store_probe_screen", "vne_diag_store_probe_input")
            $ _store_focus_requested = "YES" if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_store_probe_input") else "NO"
            $ _store_change_entry = vne_diag_probe_change_events.get("store_probe")
            $ _store_change_observed = "YES" if _store_change_entry else "NO"
            $ _store_last_change_ts = _store_change_entry["ts"] if _store_change_entry else "(none)"
            $ _store_current_len = _store_change_entry["length"] if _store_change_entry else _store_len
            $ _store_last_exc_safe = _vne_diag_safe_text(
                (vne_diag_last_focus_request["error"] if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_store_probe_input" and vne_diag_last_focus_request["error"]) else "(none)"),
                200,
            )
            text "DISPLAYABLE FOUND: [_store_disp_status]  FOCUS REQUESTED: [_store_focus_requested]":
                size 10
                color "#aaaaaa"
            $ _store_change_color = "#7fdc7f" if _store_change_observed == "YES" else "#999999"
            text "VALUE CHANGE OBSERVED (real keystrokes only): [_store_change_observed]":
                size 10
                color _store_change_color
            text "CURRENT LENGTH: [_store_current_len]  LAST CHANGE TIME: [_store_last_change_ts]":
                size 10
                color "#aaaaaa"
            text "LAST EXCEPTION: [_store_last_exc_safe]":
                size 10
                color "#aaaaaa"

            hbox:
                spacing 4
                textbutton "SET TEST":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_store_probe_set, "diagnostic test value")
                textbutton "APPEND X":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_store_probe_append, "X")
                textbutton "CLEAR":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_store_probe_clear)
                textbutton "REQUEST FOCUS":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_request_focus, "vne_diag_store_probe_screen", "vne_diag_store_probe_input")
                textbutton "COPY VALUE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_copy_text, "INPUT", "COPY STORE PROBE VALUE", vne_diag_store_probe_text)

            $ _s_entry_a = vne_diag_s_key_results.get("store_probe")
            $ _s_label_safe_a = _vne_diag_safe_text("NOT TESTED" if _s_entry_a is None else _s_entry_a["result"], 60)
            $ _s_color_a = (
                "#999999" if _s_entry_a is None else
                "#7fdc7f" if _s_entry_a["result"] == "ENTERED ACTIVE PROBE" else
                "#e08a8a"
            )
            text "S KEY RESULT: [_s_label_safe_a]":
                size 11
                color _s_color_a
            text "Type the letter S while this field has focus. If S enters the field, typing works. If a screenshot notification appears instead, this field never captured the S key.":
                size 10
                color "#666666"
                xfill True
            hbox:
                spacing 4
                textbutton "CONFIRM S ENTERED PROBE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "store_probe", "ENTERED ACTIVE PROBE")
                textbutton "CONFIRM S TOOK SCREENSHOT":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "store_probe", "SCREENSHOT TRIGGERED")
                textbutton "CONFIRM TYPING FAILED":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "store_probe", "UNKNOWN")


# ============================================================
# ISOLATED PROBE SCREEN B: screen-variable single-line probe
# ============================================================

screen vne_diag_screen_probe_screen():
    modal True
    zorder 600

    default diag_screen_probe_text = ""

    timer 0.15 action Function(_vne_diag_request_focus, "vne_diag_screen_probe_screen", "vne_diag_screen_probe_input") repeat False

    $ _screen_probe_showing, _ = _vne_diag_screen_status("vne_diag_screen_probe_screen")

    frame:
        xalign 0.5
        yalign 0.5
        xsize int(config.screen_width * 0.7)
        ysize int(config.screen_height * 0.7)
        background Solid("#14141c")
        padding (12, 10)

        vbox:
            spacing 8
            xfill True
            yfill True

            hbox:
                xfill True
                text "Screen-Variable Probe - [VNE_DIAG_BUILD_MARKER]":
                    size 14
                    bold True
                    color "#ffffff"
                    xfill True
                textbutton "Close":
                    style "vne_diag_btn"
                    action Hide("vne_diag_screen_probe_screen")

            $ _screen_probe_showing_color = "#7fdc7f" if _screen_probe_showing == "YES" else "#e08a8a"
            text "SHOWING: [_screen_probe_showing]  (screen: vne_diag_screen_probe_screen)":
                size 10
                color _screen_probe_showing_color

            text "Exactly one input on this screen (ScreenVariableInputValue).":
                size 11
                color "#aaaaaa"
                xfill True

            text "CLICK INSIDE THE FIELD AND TYPE":
                size 12
                bold True
                color "#ffcc00"

            frame:
                xfill True
                background Solid("#5a5a6e")
                padding (2, 2)
                frame:
                    xfill True
                    xminimum 400
                    yminimum 48
                    background Solid("#2a2a38")
                    padding (10, 8)
                    input:
                        id "vne_diag_screen_probe_input"
                        default_focus 100
                        value _VneDiagTelemetryInputValue(ScreenVariableInputValue("diag_screen_probe_text", default=True, returnable=False), "screen_probe")
                        length 500
                        xfill True
                        copypaste True
                        color "#ffffff"

            text "BACKING VALUE PREVIEW":
                size 10
                bold True
                color "#88ccff"
            $ _screen_probe_preview_safe = _vne_diag_safe_text(_vne_diag_preview(diag_screen_probe_text), 200)
            $ _screen_probe_len = len(diag_screen_probe_text)
            text "text: [_screen_probe_preview_safe]  (len=[_screen_probe_len])":
                size 11
                color "#aaaaaa"

            $ _screen_probe_disp_status, _screen_probe_disp_detail = _vne_diag_displayable_status("vne_diag_screen_probe_screen", "vne_diag_screen_probe_input")
            $ _screen_probe_focus_requested = "YES" if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_screen_probe_input") else "NO"
            $ _screen_probe_change_entry = vne_diag_probe_change_events.get("screen_probe")
            $ _screen_probe_change_observed = "YES" if _screen_probe_change_entry else "NO"
            $ _screen_probe_last_change_ts = _screen_probe_change_entry["ts"] if _screen_probe_change_entry else "(none)"
            $ _screen_probe_current_len = _screen_probe_change_entry["length"] if _screen_probe_change_entry else _screen_probe_len
            $ _screen_probe_last_exc_safe = _vne_diag_safe_text(
                (vne_diag_last_focus_request["error"] if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_screen_probe_input" and vne_diag_last_focus_request["error"]) else "(none)"),
                200,
            )
            text "DISPLAYABLE FOUND: [_screen_probe_disp_status]  FOCUS REQUESTED: [_screen_probe_focus_requested]":
                size 10
                color "#aaaaaa"
            $ _screen_probe_change_color = "#7fdc7f" if _screen_probe_change_observed == "YES" else "#999999"
            text "VALUE CHANGE OBSERVED (real keystrokes only): [_screen_probe_change_observed]":
                size 10
                color _screen_probe_change_color
            text "CURRENT LENGTH: [_screen_probe_current_len]  LAST CHANGE TIME: [_screen_probe_last_change_ts]":
                size 10
                color "#aaaaaa"
            text "LAST EXCEPTION: [_screen_probe_last_exc_safe]":
                size 10
                color "#aaaaaa"

            hbox:
                spacing 4
                textbutton "SET TEST":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_screen_probe_set, "diagnostic test value")
                textbutton "APPEND X":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_screen_probe_append, "X")
                textbutton "CLEAR":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_screen_probe_clear)
                textbutton "REQUEST FOCUS":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_request_focus, "vne_diag_screen_probe_screen", "vne_diag_screen_probe_input")
                textbutton "COPY VALUE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_copy_text, "INPUT", "COPY SCREEN PROBE VALUE", diag_screen_probe_text)

            $ _s_entry_b = vne_diag_s_key_results.get("screen_probe")
            $ _s_label_safe_b = _vne_diag_safe_text("NOT TESTED" if _s_entry_b is None else _s_entry_b["result"], 60)
            $ _s_color_b = (
                "#999999" if _s_entry_b is None else
                "#7fdc7f" if _s_entry_b["result"] == "ENTERED ACTIVE PROBE" else
                "#e08a8a"
            )
            text "S KEY RESULT: [_s_label_safe_b]":
                size 11
                color _s_color_b
            text "Type the letter S while this field has focus. If S enters the field, typing works. If a screenshot notification appears instead, this field never captured the S key.":
                size 10
                color "#666666"
                xfill True
            hbox:
                spacing 4
                textbutton "CONFIRM S ENTERED PROBE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "screen_probe", "ENTERED ACTIVE PROBE")
                textbutton "CONFIRM S TOOK SCREENSHOT":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "screen_probe", "SCREENSHOT TRIGGERED")
                textbutton "CONFIRM TYPING FAILED":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "screen_probe", "UNKNOWN")


# ============================================================
# ISOLATED PROBE SCREEN C: screen-variable multiline probe
# ============================================================

screen vne_diag_multiline_probe_screen():
    modal True
    zorder 600

    default diag_multiline_probe_text = ""

    timer 0.15 action Function(_vne_diag_request_focus, "vne_diag_multiline_probe_screen", "vne_diag_multiline_probe_input") repeat False

    $ _multiline_probe_showing, _ = _vne_diag_screen_status("vne_diag_multiline_probe_screen")

    frame:
        xalign 0.5
        yalign 0.5
        xsize int(config.screen_width * 0.7)
        # RN-DIAG-01-R5: taller than the other two probes (0.92 vs 0.7,
        # matching the main hub's own proven-safe maximum) because this
        # screen carries more vertical content (the yminimum-150 multiline
        # field plus the new visible-field/telemetry rows below).
        ysize int(config.screen_height * 0.92)
        background Solid("#14141c")
        padding (12, 10)

        vbox:
            spacing 8
            xfill True
            yfill True

            hbox:
                xfill True
                text "Multiline Probe - [VNE_DIAG_BUILD_MARKER]":
                    size 14
                    bold True
                    color "#ffffff"
                    xfill True
                textbutton "Close":
                    style "vne_diag_btn"
                    action Hide("vne_diag_multiline_probe_screen")

            $ _multiline_probe_showing_color = "#7fdc7f" if _multiline_probe_showing == "YES" else "#e08a8a"
            text "SHOWING: [_multiline_probe_showing]  (screen: vne_diag_multiline_probe_screen)":
                size 10
                color _multiline_probe_showing_color

            text "Exactly one input, no viewport - reliable keyboard capture is the only goal.":
                size 11
                color "#aaaaaa"
                xfill True

            text "CLICK INSIDE THE FIELD AND TYPE":
                size 12
                bold True
                color "#ffcc00"

            frame:
                xfill True
                background Solid("#5a5a6e")
                padding (2, 2)
                frame:
                    xfill True
                    yminimum 150
                    background Solid("#2a2a38")
                    padding (10, 8)
                    input:
                        id "vne_diag_multiline_probe_input"
                        default_focus 100
                        value _VneDiagTelemetryInputValue(ScreenVariableInputValue("diag_multiline_probe_text", default=True, returnable=False), "multiline_probe")
                        length 4000
                        multiline True
                        copypaste True
                        xfill True
                        color "#ffffff"

            text "BACKING VALUE PREVIEW":
                size 10
                bold True
                color "#88ccff"
            $ _multiline_len = len(diag_multiline_probe_text)
            $ _multiline_lines = (diag_multiline_probe_text.count("\n") + 1) if diag_multiline_probe_text else 0
            $ _multiline_preview_safe = _vne_diag_safe_text(_vne_diag_preview(diag_multiline_probe_text, 200), 220)
            text "length=[_multiline_len]  lines=[_multiline_lines]":
                size 11
                color "#aaaaaa"
            text "preview: [_multiline_preview_safe]":
                size 10
                color "#888888"
                xfill True

            $ _multiline_disp_status, _multiline_disp_detail = _vne_diag_displayable_status("vne_diag_multiline_probe_screen", "vne_diag_multiline_probe_input")
            $ _multiline_focus_requested = "YES" if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_multiline_probe_input") else "NO"
            $ _multiline_change_entry = vne_diag_probe_change_events.get("multiline_probe")
            $ _multiline_change_observed = "YES" if _multiline_change_entry else "NO"
            $ _multiline_last_change_ts = _multiline_change_entry["ts"] if _multiline_change_entry else "(none)"
            $ _multiline_current_len = _multiline_change_entry["length"] if _multiline_change_entry else _multiline_len
            $ _multiline_last_exc_safe = _vne_diag_safe_text(
                (vne_diag_last_focus_request["error"] if (vne_diag_last_focus_request and vne_diag_last_focus_request["id"] == "vne_diag_multiline_probe_input" and vne_diag_last_focus_request["error"]) else "(none)"),
                200,
            )
            text "DISPLAYABLE FOUND: [_multiline_disp_status]  FOCUS REQUESTED: [_multiline_focus_requested]":
                size 10
                color "#aaaaaa"
            $ _multiline_change_color = "#7fdc7f" if _multiline_change_observed == "YES" else "#999999"
            text "VALUE CHANGE OBSERVED (real keystrokes only): [_multiline_change_observed]":
                size 10
                color _multiline_change_color
            text "CURRENT LENGTH: [_multiline_current_len]  LAST CHANGE TIME: [_multiline_last_change_ts]":
                size 10
                color "#aaaaaa"
            text "LAST EXCEPTION: [_multiline_last_exc_safe]":
                size 10
                color "#aaaaaa"

            hbox:
                spacing 4
                textbutton "SET MULTILINE TEST":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_multiline_probe_set, "diagnostic\nmultiline\ntest value")
                textbutton "APPEND LINE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_multiline_probe_append_line)
                textbutton "CLEAR":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_multiline_probe_clear)
                textbutton "REQUEST FOCUS":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_request_focus, "vne_diag_multiline_probe_screen", "vne_diag_multiline_probe_input")
                textbutton "COPY VALUE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_copy_text, "INPUT", "COPY MULTILINE PROBE VALUE", diag_multiline_probe_text)

            $ _s_entry_c = vne_diag_s_key_results.get("multiline_probe")
            $ _s_label_safe_c = _vne_diag_safe_text("NOT TESTED" if _s_entry_c is None else _s_entry_c["result"], 60)
            $ _s_color_c = (
                "#999999" if _s_entry_c is None else
                "#7fdc7f" if _s_entry_c["result"] == "ENTERED ACTIVE PROBE" else
                "#e08a8a"
            )
            text "S KEY RESULT: [_s_label_safe_c]":
                size 11
                color _s_color_c
            text "Type the letter S while this field has focus. If S enters the field, typing works. If a screenshot notification appears instead, this field never captured the S key.":
                size 10
                color "#666666"
                xfill True
            hbox:
                spacing 4
                textbutton "CONFIRM S ENTERED PROBE":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "multiline_probe", "ENTERED ACTIVE PROBE")
                textbutton "CONFIRM S TOOK SCREENSHOT":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "multiline_probe", "SCREENSHOT TRIGGERED")
                textbutton "CONFIRM TYPING FAILED":
                    style "vne_diag_btn_danger"
                    text_size 10
                    action Function(_vne_diag_confirm_s_key, "multiline_probe", "UNKNOWN")


# ============================================================
# RN-DIAG-01-R6 FORENSIC CASE B: show_screen + RAW VariableInputValue,
# no telemetry wrapper. Isolates whether the R5 wrapper class itself is
# responsible for the "typing does not change text" symptom. Open this
# screen once while Aside is showing underneath (Case B) and once after
# closing Aside first (Case D) - same screen, two different contexts.
# ============================================================

screen vne_diag_case_b_probe_screen():
    modal True
    zorder 600

    timer 0.15 action Function(_vne_diag_request_focus, "vne_diag_case_b_probe_screen", "vne_diag_case_b_probe_input") repeat False

    $ _case_b_showing, _ = _vne_diag_screen_status("vne_diag_case_b_probe_screen")
    $ _aside_showing_now, _ = _vne_diag_screen_status("aside_chat_log")

    frame:
        xalign 0.5
        yalign 0.5
        xsize int(config.screen_width * 0.7)
        ysize int(config.screen_height * 0.7)
        background Solid("#14141c")
        padding (12, 10)

        vbox:
            spacing 8
            xfill True
            yfill True

            hbox:
                xfill True
                text "FORENSICS CASE B - [VNE_DIAG_BUILD_MARKER]":
                    size 14
                    bold True
                    color "#ffffff"
                    xfill True
                textbutton "Close":
                    style "vne_diag_btn"
                    action Hide("vne_diag_case_b_probe_screen")

            text "show_screen + raw VariableInputValue, NO telemetry wrapper (contrast with the store probe on the previous tab).":
                size 11
                color "#aaaaaa"
                xfill True

            $ _case_b_context_label = "CASE B (Aside currently showing)" if _aside_showing_now == "YES" else "CASE D (Aside NOT showing - non-Aside context)"
            text "Current context: [_case_b_context_label]":
                size 11
                bold True
                color "#ffcc00"

            text "CLICK INSIDE THE FIELD AND TYPE":
                size 12
                bold True
                color "#ffcc00"

            frame:
                xfill True
                background Solid("#5a5a6e")
                padding (2, 2)
                frame:
                    xfill True
                    xminimum 400
                    yminimum 48
                    background Solid("#2a2a38")
                    padding (10, 8)
                    input:
                        id "vne_diag_case_b_probe_input"
                        default_focus 100
                        value VariableInputValue("vne_diag_case_b_probe_text")
                        length 500
                        xfill True
                        copypaste True
                        color "#ffffff"

            text "BACKING VALUE PREVIEW":
                size 10
                bold True
                color "#88ccff"
            $ _case_b_len = len(vne_diag_case_b_probe_text)
            $ _case_b_preview_safe = _vne_diag_safe_text(_vne_diag_preview(vne_diag_case_b_probe_text), 200)
            text "text: [_case_b_preview_safe]  (len=[_case_b_len])":
                size 11
                color "#aaaaaa"

            text "SHOWING: [_case_b_showing]  aside_chat_log showing: [_aside_showing_now]":
                size 10
                color "#aaaaaa"

            hbox:
                spacing 4
                textbutton "CLEAR":
                    style "vne_diag_btn"
                    text_size 10
                    action SetVariable("vne_diag_case_b_probe_text", "")
                textbutton "REQUEST FOCUS":
                    style "vne_diag_btn"
                    text_size 10
                    action Function(_vne_diag_request_focus, "vne_diag_case_b_probe_screen", "vne_diag_case_b_probe_input")


# ============================================================
# RN-DIAG-01-R6 FORENSIC CASE C: renpy.call_screen run inside a fresh
# context via the documented renpy.invoke_in_new_context(), with
# _clear_layers=True so Aside and the Diagnostics hub are temporarily
# cleared - only this screen exists in that interaction. Closing it
# (Return) pops back to the original context, restoring the prior scene
# exactly as invoke_in_new_context documents.
# ============================================================

screen vne_diag_case_c_probe_screen():
    modal True
    zorder 600

    default case_c_probe_text = ""

    timer 0.15 action Function(_vne_diag_request_focus, "vne_diag_case_c_probe_screen", "vne_diag_case_c_probe_input") repeat False

    frame:
        xalign 0.5
        yalign 0.5
        xsize int(config.screen_width * 0.7)
        ysize int(config.screen_height * 0.7)
        background Solid("#14141c")
        padding (12, 10)

        vbox:
            spacing 8
            xfill True
            yfill True

            text "FORENSICS CASE C - [VNE_DIAG_BUILD_MARKER]":
                size 14
                bold True
                color "#ffffff"

            text "Opened via renpy.invoke_in_new_context(renpy.call_screen, ..., _clear_layers=True). Aside and the Diagnostics hub are temporarily cleared - only this screen exists right now.":
                size 11
                color "#aaaaaa"
                xfill True

            text "CLICK INSIDE THE FIELD AND TYPE":
                size 12
                bold True
                color "#ffcc00"

            frame:
                xfill True
                background Solid("#5a5a6e")
                padding (2, 2)
                frame:
                    xfill True
                    xminimum 400
                    yminimum 48
                    background Solid("#2a2a38")
                    padding (10, 8)
                    input:
                        id "vne_diag_case_c_probe_input"
                        default_focus 100
                        value ScreenVariableInputValue("case_c_probe_text", default=True, returnable=False)
                        length 500
                        xfill True
                        copypaste True
                        color "#ffffff"

            text "BACKING VALUE PREVIEW":
                size 10
                bold True
                color "#88ccff"
            $ _case_c_len = len(case_c_probe_text)
            $ _case_c_preview_safe = _vne_diag_safe_text(_vne_diag_preview(case_c_probe_text), 200)
            text "text: [_case_c_preview_safe]  (len=[_case_c_len])":
                size 11
                color "#aaaaaa"

            textbutton "Close (ends Case C test, returns to Diagnostics)":
                style "vne_diag_btn"
                action Return({"length": _case_c_len, "preview": _case_c_preview_safe})


# ============================================================
# VISUAL OVERLAYS (diagnostic only - never intercepts input)
# ============================================================

screen vne_diag_visual_overlays():
    zorder 450

    if config.developer:
        fixed:
            xfill True
            yfill True

            if vne_diag_show_grid:
                $ _grid_step = 100
                for _gx in range(0, config.screen_width, _grid_step):
                    frame:
                        xpos _gx
                        ypos 0
                        xsize 1
                        ysize config.screen_height
                        background Solid("#ffffff22")
                for _gy in range(0, config.screen_height, _grid_step):
                    frame:
                        xpos 0
                        ypos _gy
                        xsize config.screen_width
                        ysize 1
                        background Solid("#ffffff22")

            if vne_diag_show_center:
                frame:
                    xpos (config.screen_width // 2)
                    ypos 0
                    xsize 1
                    ysize config.screen_height
                    background Solid("#66ccff66")
                frame:
                    xpos 0
                    ypos (config.screen_height // 2)
                    xsize config.screen_width
                    ysize 1
                    background Solid("#66ccff66")

            if vne_diag_show_safe_area:
                $ _margin_x = int(config.screen_width * 0.05)
                $ _margin_y = int(config.screen_height * 0.05)
                $ _safe_w = config.screen_width - 2 * _margin_x
                $ _safe_h = config.screen_height - 2 * _margin_y
                frame:
                    xpos _margin_x
                    ypos _margin_y
                    xsize _safe_w
                    ysize 2
                    background Solid("#ffcc0088")
                frame:
                    xpos _margin_x
                    ypos (_margin_y + _safe_h)
                    xsize _safe_w
                    ysize 2
                    background Solid("#ffcc0088")
                frame:
                    xpos _margin_x
                    ypos _margin_y
                    xsize 2
                    ysize _safe_h
                    background Solid("#ffcc0088")
                frame:
                    xpos (_margin_x + _safe_w)
                    ypos _margin_y
                    xsize 2
                    ysize _safe_h
                    background Solid("#ffcc0088")
                text "SAFE AREA":
                    xpos (_margin_x + 6)
                    ypos (_margin_y + 4)
                    size 12
                    color "#ffcc00"

            if vne_diag_show_crosshair:
                python:
                    _ok_mouse, _mouse_val = _vne_diag_safe(renpy.get_mouse_pos)
                    if _ok_mouse:
                        _mx, _my = _mouse_val
                    else:
                        _mx, _my = (0, 0)
                frame:
                    xpos (_mx - 1)
                    ypos 0
                    xsize 2
                    ysize config.screen_height
                    background Solid("#00ffff88")
                frame:
                    xpos 0
                    ypos (_my - 1)
                    xsize config.screen_width
                    ysize 2
                    background Solid("#00ffff88")
                text "([_mx], [_my])":
                    xpos (_mx + 8)
                    ypos (_my + 8)
                    size 12
                    color "#00ffff"

            if vne_diag_show_aside_regions:
                $ _pad = 20
                $ _region_x = _pad
                $ _region_w = config.screen_width - 2 * _pad
                python:
                    _region_y = _pad
                    _region_defs = []
                    for _rlabel, _rh in [
                        ("HEADER (expected)", 40),
                        ("HISTORY (expected)", 250),
                        ("COMPOSER (expected)", 180),
                        ("ACTIONS (expected)", 50),
                    ]:
                        _region_defs.append((_rlabel, _region_y, _rh))
                        _region_y = _region_y + _rh + 10
                for _rlabel, _ry, _rh in _region_defs:
                    frame:
                        xpos _region_x
                        ypos _ry
                        xsize _region_w
                        ysize _rh
                        background Solid("#ff66ff22")
                        padding (4, 2)
                        text "[_rlabel]" size 11 color "#ff66ff"
                text "DEV OVERLAY (expected, top-right corner)":
                    xpos (config.screen_width - 220)
                    ypos 10
                    size 11
                    color "#ff66ff"
