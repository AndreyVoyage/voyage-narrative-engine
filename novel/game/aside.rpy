# aside.rpy — N6 Character Aside screen (local Ollama LLM + mock fallback, isolated memory)
#
# Invariants:
# - Reads v2_flags / v2_completed_scenes / v2_levels / v2_relationships ONLY.
# - Never assigns to v2_* or calls mutating methods on them.
# - Uses local Ollama provider by default; falls back to mock if Ollama is unreachable.
# - Writes aside memory only under RenPy save directory, never into canon.
# - Provider settings are saved under "vne_aside_config_" namespace, isolated from canon.
# - Not wired into the SC_003–SC_018 playable selector.

# Dev/test tracking variables for the current scene/beat. These are local UI
# state, not canon; v2_* remains the single source of canonical truth.
default vne_current_scene_id = "SC_017"
default vne_current_beat_id = "sc_017_v2_1a"
default vne_current_progress_index = 17
default vne_current_content_rating = "PG-13"

# Isolated Aside provider configuration (saved with RenPy save, not canon).
default vne_aside_config_provider = "local"
default vne_aside_config_base_url = "http://localhost:11434"
default vne_aside_config_model = "llama3"

# Top-level UI state for the Aside chat. Required for VariableInputValue and
# for Shift+O console access; reset on entry, never written to canon.
default aside_input_text = ""
default aside_chat_history = []

# Pending flag for async LLM calls; prevents duplicate submits and shows status.
default aside_llm_pending = False

init python:
    import datetime
    import json
    import os
    import sys
    import threading
    from pathlib import Path

    _aside_trace_lock = threading.Lock()

    def _vne_aside_trace_path_main_thread():
        """Resolve the trace file path from Ren'Py config.

        Reads renpy.config.savedir; must only be called from the main
        thread. Never call this from _vne_aside_worker or anything it calls
        with a detached snapshot — use the pre-resolved snapshot["trace_path"]
        there instead.
        """
        return os.path.join(renpy.config.savedir, "aside_internal_trace.jsonl")

    def _vne_aside_trace_write_at_path(trace_path, event, payload):
        """Pure thread-safe filesystem writer.

        Accepts an already-resolved absolute path. Never reads renpy.config,
        renpy.store, store, or screen variables, so it is safe to call from
        either the main thread or a background worker thread.
        """
        if not isinstance(trace_path, str) or not trace_path.strip():
            return

        record = {
            "ts": datetime.datetime.now().isoformat(timespec="milliseconds"),
            "event": str(event),
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
        }
        sensitive_fields = {"msg", "reply_preview", "history_last", "error"}
        for key, value in dict(payload or {}).items():
            key = str(key)
            if key in sensitive_fields and isinstance(value, str):
                record[key] = "<redacted:{} chars>".format(len(value))
            else:
                record[key] = value[:400] if isinstance(value, str) else value
        try:
            os.makedirs(os.path.dirname(trace_path), exist_ok=True)
            with _aside_trace_lock:
                with open(trace_path, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False, default=repr) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
        except Exception:
            pass

    def _vne_aside_trace(event, **fields):
        """Write dev-only JSONL evidence without rendering trace UI.

        Main-thread only: resolves the trace path itself and reads store for
        context. Never call this from _vne_aside_worker; that path must use
        _vne_aside_worker_trace instead.
        """
        if not config.developer:
            return

        import store
        payload = dict(fields)
        history = list(getattr(store, "aside_chat_history", []))
        payload.setdefault("provider", getattr(store, "vne_aside_config_provider", "<unknown>"))
        payload.setdefault("pending", getattr(store, "aside_llm_pending", None))
        payload.setdefault("history_len", len(history))
        payload.setdefault("history_last", str(history[-1])[:300] if history else None)
        _vne_aside_trace_write_at_path(
            _vne_aside_trace_path_main_thread(),
            event,
            payload,
        )

    def _vne_aside_worker_trace(snapshot, event, **fields):
        """Worker-safe trace wrapper.

        Takes the trace path from the detached snapshot; never touches
        renpy.config, store, or screen variables. Safe to call from
        _vne_aside_worker.
        """
        _vne_aside_trace_write_at_path(
            snapshot.get("trace_path"),
            event,
            dict(fields),
        )

    # Path to repo tools. Lazy import inside helpers keeps RenPy lint/SDK
    # validation clean when tools/ are not present (e.g. temp copies).
    _VNE_TOOLS_DIR = str(Path(config.gamedir).parent.parent / "tools")

    def _vne_assert_plain_worker_payload(value, path="payload"):
        """Reject live or non-plain values before crossing the thread boundary."""
        allowed_scalars = (str, int, float, bool, type(None))

        if isinstance(value, allowed_scalars):
            return

        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                _vne_assert_plain_worker_payload(
                    item,
                    "{}[{}]".format(path, index),
                )
            return

        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(
                        "{} contains non-string key: {!r}".format(path, key)
                    )
                _vne_assert_plain_worker_payload(
                    item,
                    "{}.{}".format(path, key),
                )
            return

        raise TypeError(
            "{} contains unsafe worker value of type {}".format(
                path,
                type(value).__name__,
            )
        )

    def _vne_detach_plain_worker_value(value, path):
        """Recursively copy store values into detached built-in containers."""
        allowed_scalars = (str, int, float, bool, type(None))

        if isinstance(value, allowed_scalars):
            return value

        if isinstance(value, list):
            return [
                _vne_detach_plain_worker_value(item, "{}[{}]".format(path, index))
                for index, item in enumerate(value)
            ]

        if isinstance(value, tuple):
            return tuple(
                _vne_detach_plain_worker_value(item, "{}[{}]".format(path, index))
                for index, item in enumerate(value)
            )

        if isinstance(value, dict):
            detached = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(
                        "{} contains non-string key: {!r}".format(path, key)
                    )
                detached[str(key)] = _vne_detach_plain_worker_value(
                    item,
                    "{}.{}".format(path, key),
                )
            return detached

        raise TypeError(
            "{} contains unsafe worker value of type {}".format(
                path,
                type(value).__name__,
            )
        )

    def _vne_build_aside_turn_snapshot(character_id, player_message, save_slot):
        """Capture detached store/config values on the Ren'Py main thread."""
        import store

        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Aside turn snapshot must be built on MainThread")

        snapshot = {
            "character_id": str(character_id),
            "player_message": str(player_message),
            "save_slot": str(save_slot),
            "provider": str(store.vne_aside_config_provider),
            "base_url": str(store.vne_aside_config_base_url),
            "model": str(store.vne_aside_config_model),
            "diagnostics_enabled": bool(config.developer),
            "trace_path": str(_vne_aside_trace_path_main_thread()),
            "memory_root": str(_vne_aside_memory_root()),
            "canon": {
                "scene_id": str(store.vne_current_scene_id),
                "beat_id": str(store.vne_current_beat_id),
                "progress_index": int(store.vne_current_progress_index),
                "flags": sorted(str(value) for value in store.v2_flags),
                "completed_scenes": sorted(
                    str(value) for value in store.v2_completed_scenes
                ),
                "levels": _vne_detach_plain_worker_value(
                    store.v2_levels,
                    "payload.canon.levels",
                ),
                "relationships": _vne_detach_plain_worker_value(
                    store.v2_relationships,
                    "payload.canon.relationships",
                ),
                "content_rating": str(store.vne_current_content_rating),
            },
        }
        _vne_assert_plain_worker_payload(snapshot)
        return snapshot

    def _vne_aside_memory_root():
        """Isolated aside memory root inside RenPy save directory."""
        return Path(renpy.config.savedir) / "vne_aside_memory"

    def _vne_is_connection_error(exc):
        """Return True if an LLMProviderError is a connection/timeout failure."""
        msg = str(exc).lower()
        return (
            "connection failed" in msg
            or "connection timed out" in msg
            or "timed out" in msg
            or "urlerror" in msg
        )

    def _vne_run_aside_turn_from_snapshot(snapshot):
        """Worker-safe turn execution using only a detached plain snapshot.

        Uses the configured provider. Local-provider errors are surfaced to the
        caller and never routed to mock. Returns a dict containing the reply and
        compatibility fallback/warning fields.
        """
        if _VNE_TOOLS_DIR not in sys.path:
            sys.path.insert(0, _VNE_TOOLS_DIR)

        import aside_context_builder
        import aside_memory_store
        import llm_provider

        character_id = snapshot["character_id"]
        player_message = snapshot["player_message"]
        save_slot = snapshot["save_slot"]
        canon = snapshot["canon"]
        root = Path(snapshot["memory_root"])
        progress = canon["progress_index"]
        provider = snapshot["provider"]
        base_url = snapshot["base_url"]
        model = snapshot["model"]

        # Load isolated aside memory (past-only, progress-gated).
        memory = aside_memory_store.load_memory(
            root=root,
            slot=save_slot,
            character=character_id,
            progress=progress,
        )

        # Build context: persona + past canon + aside memory + player message.
        messages = aside_context_builder.build_context(
            character_id=character_id,
            canon_snapshot=canon,
            aside_memory=memory,
            player_message=player_message,
        )

        fallback = False
        warning = ""

        if provider == "local":
            # A selected local provider must never silently route to mock.
            # Connection failures are surfaced by the async worker as LLM errors.
            reply = llm_provider.complete(
                messages,
                provider="local",
                model=model,
                params={
                    "base_url": base_url,
                    "timeout_s": 120,
                },
            )
        else:
            # Mock or any other explicit non-local choice.
            reply = llm_provider.complete(messages, provider="mock")

        # Persist turn to isolated aside memory.
        session = {
            "scene_id": canon["scene_id"],
            "beat_id": canon["beat_id"],
            "progress_index": progress,
            "summary": "Player: " + player_message,
            "transcript": [
                {"role": "user", "content": player_message},
                {"role": "assistant", "content": reply},
            ],
        }
        aside_memory_store.append_session(
            root=root,
            slot=save_slot,
            character=character_id,
            session=session,
        )

        return {"reply": reply, "fallback": fallback, "warning": warning}

    def _vne_reset_aside_memory(character_id, save_slot):
        """Reset isolated aside memory for this character/slot and clear chat."""
        import store

        if _VNE_TOOLS_DIR not in sys.path:
            sys.path.insert(0, _VNE_TOOLS_DIR)

        import aside_memory_store

        root = _vne_aside_memory_root()
        aside_memory_store.reset_memory(
            root=root,
            slot=save_slot,
            character=character_id,
        )
        store.aside_chat_history = []
        store.aside_input_text = ""
        store.aside_llm_pending = False

    def _vne_cycle_provider():
        """Cycle provider setting between local and mock."""
        import store
        store.vne_aside_config_provider = (
            "mock" if store.vne_aside_config_provider == "local" else "local"
        )

    def _vne_aside_input_changed(value):
        """Explicitly sync the message input value into the store variable.

        VariableInputValue does not reliably sync before submit in this screen,
        so we use `changed` callback + `default` binding instead.
        """
        import store
        store.aside_input_text = value

    def _vne_aside_submit_message():
        """Return a structured ("send", msg) tuple if there is a message.

        The tuple is returned as the call_screen result so the loop can read
        the actual message text without relying on VariableInputValue.
        """
        import store
        msg = store.aside_input_text.strip()
        if msg:
            return ("send", msg)
        return None

    def _vne_aside_finish_reply(character_id, msg, reply):
        """Finalize one turn in the main thread and refresh the Aside UI."""
        import store
        _vne_aside_trace("main_thread_callback", msg=msg, reply_preview=reply[:160])

        user_line = "You: " + msg
        thinking_line = character_id.capitalize() + ": [[thinking...]]"

        # Screen-action mutations may not survive the interaction restarted by
        # the background callback. Reconcile the complete turn here, where the
        # final reply is committed to the live store history. Reassign (rather
        # than mutate in place) so screen re-execution reliably picks up the
        # change and rollback/save tracking sees a new list.
        history = list(store.aside_chat_history)
        for index in range(len(history) - 1, -1, -1):
            if history[index] == thinking_line:
                del history[index]
                break
        if not history or history[-1] != user_line:
            history = history + [user_line]

        store.aside_llm_pending = False
        history = history + [character_id.capitalize() + ": " + reply]
        store.aside_chat_history = history
        _vne_aside_trace("final_history_write", msg=msg, reply_preview=reply[:160])
        renpy.restart_interaction()

    def _vne_aside_send_message(character_id, save_slot, msg):
        """Send a message from the Aside screen without relying on call_screen Return.

        Called as a screen action in the main thread. Appends the user message to
        chat history, shows a pending indicator, and dispatches the blocking LLM
        call to a background thread.
        """
        import store

        msg = (msg or "").strip()
        if not msg:
            return

        store.aside_chat_history = store.aside_chat_history + ["You: " + msg]
        _vne_aside_trace("history_write", msg=msg)

        if store.aside_llm_pending:
            store.aside_chat_history = store.aside_chat_history + [
                character_id.capitalize() + ": [LLM BUSY] Previous request is still running."
            ]
            renpy.restart_interaction()
            return

        try:
            worker_snapshot = _vne_build_aside_turn_snapshot(
                character_id,
                msg,
                save_slot,
            )
            _vne_assert_plain_worker_payload(worker_snapshot)
        except Exception as exc:
            store.aside_llm_pending = False
            store.aside_chat_history = store.aside_chat_history + [
                character_id.capitalize()
                + ": [LLM ERROR] Cannot prepare worker payload: "
                + str(exc)
            ]
            _vne_aside_trace("worker_payload_error", error=str(exc))
            renpy.restart_interaction()
            return

        store.aside_llm_pending = True
        store.aside_chat_history = store.aside_chat_history + [
            character_id.capitalize() + ": [[thinking...]]"
        ]
        _vne_aside_trace("worker_dispatch", msg=msg)
        renpy.invoke_in_thread(_vne_aside_worker, worker_snapshot)
        renpy.restart_interaction()

    def _vne_aside_send_current_message(character_id, save_slot):
        """Read the live screen input value at action execution time."""
        import store
        _vne_aside_trace("ui_submit", character_id=character_id)

        try:
            msg = renpy.get_screen_variable(
                "message_text",
                screen="aside_chat_log",
            )
        except Exception as exc:
            store.aside_chat_history = store.aside_chat_history + [
                character_id.capitalize()
                + ": [UI ERROR] Cannot read Message field: "
                + str(exc)
            ]
            renpy.restart_interaction()
            return

        msg = (msg or "").strip()
        _vne_aside_trace("message_capture", msg=msg)

        if not msg:
            renpy.restart_interaction()
            return

        try:
            renpy.set_screen_variable(
                "message_text",
                "",
                screen="aside_chat_log",
            )
        except Exception as exc:
            store.aside_chat_history = store.aside_chat_history + [
                character_id.capitalize()
                + ": [UI WARNING] Cannot clear Message field: "
                + str(exc)
            ]

        _vne_aside_send_message(character_id, save_slot, msg)
        renpy.restart_interaction()

    def _vne_aside_worker(snapshot):
        """Background worker for the blocking LLM call.

        Runs in a Ren'Py background thread using detached plain data only.
        The result is marshalled back to the main thread via
        renpy.invoke_in_main_thread.
        """
        character_id = snapshot["character_id"]
        msg = snapshot["player_message"]
        diagnostics_enabled = snapshot["diagnostics_enabled"]
        if diagnostics_enabled:
            _vne_aside_worker_trace(
                snapshot,
                "worker_start",
                character_id=character_id,
                msg=msg,
            )
        try:
            turn = _vne_run_aside_turn_from_snapshot(snapshot)
            if isinstance(turn, dict):
                reply = turn.get("reply", str(turn))
            else:
                reply = str(turn)
            if diagnostics_enabled:
                _vne_aside_worker_trace(
                    snapshot,
                    "provider_result",
                    reply_preview=reply[:160],
                )
        except Exception as exc:
            reply = "[LLM ERROR] " + str(exc)
            if diagnostics_enabled:
                _vne_aside_worker_trace(
                    snapshot,
                    "provider_error",
                    error=str(exc),
                )

        if diagnostics_enabled:
            _vne_aside_worker_trace(
                snapshot,
                "main_thread_callback_queued",
                reply_preview=reply[:160],
            )
        renpy.invoke_in_main_thread(
            _vne_aside_finish_reply,
            character_id,
            msg,
            reply,
        )

    # Overlay visible always (RenPy sets config.developer AFTER init python).
    config.overlay_screens.append("aside_dev_overlay")


# Dev overlay button. Visible always.
screen aside_dev_overlay():
    zorder 200

    frame:
        xalign 0.95
        yalign 0.05
        padding (8, 8)
        background Solid("#20202a")

        vbox:
            spacing 4

            text "N6f dev":
                size 14
                color "#888888"

            textbutton "Aside":
                action Jump("aside_dev_entry")
                text_size 14
                padding (10, 4)
                background Solid("#3a4658")
                hover_background Solid("#52657f")
                text_color "#ffffff"


# Character Aside chat screen. Called repeatedly by aside_chat_loop.
screen aside_chat_log(character_id="kira", save_slot="dev_slot"):
    modal True
    zorder 100
    default message_text = ""

    frame:
        xfill True
        yfill True
        padding (20, 20)
        background Solid("#171821")

        fixed:
            xfill True
            yfill True

            text "Character Aside — [character_id] ([vne_aside_config_provider])":
                xpos 0
                ypos 0
                size 26
                color "#f4f4f8"

            frame:
                xpos 0
                ypos 60
                xfill True
                ysize 360
                background Solid("#171821")
                padding (0, 0)

                $ _aside_visible_history = list(aside_chat_history[-10:])

                vbox:
                    xfill True
                    spacing 6

                    for line in _aside_visible_history:
                        text line:
                            substitute False
                            color "#d8d8e8"
                            xmaximum 740

            frame:
                xpos 0
                ypos 425
                xsize 760
                ysize 78
                padding (8, 7)
                background Solid("#202127")

                hbox:
                    spacing 10
                    xfill True

                    text "Message:":
                        xsize 100
                        yalign 0.5
                        color "#aaaaaa"
                        size 18

                    frame:
                        xsize 630
                        ysize 62
                        padding (8, 6)
                        background Solid("#2a2a2a")

                        input:
                            id "aside_message_input"
                            focus "aside_message_input"
                            value ScreenVariableInputValue(
                                "message_text",
                                default=True,
                                returnable=False
                            )
                            length 240
                            xmaximum 600
                            ymaximum 48
                            pixel_width 600
                            multiline True
                            default_focus 100
                            action Function(
                                _vne_aside_send_current_message,
                                character_id,
                                save_slot
                            )

            frame:
                xpos 0
                ypos 511
                xsize 760
                ysize 49
                padding (8, 5)
                background Solid("#202127")

                hbox:
                    spacing 10
                    xfill True

                    textbutton "Provider: [vne_aside_config_provider]":
                        action Function(_vne_cycle_provider)
                        padding (10, 6)
                        background Solid("#3a4658")
                        hover_background Solid("#52657f")
                        text_color "#ffffff"

                    if aside_llm_pending:
                        text "[[thinking...]]":
                            yalign 0.5
                            color "#888888"

                    textbutton "Send":
                        action Function(
                            _vne_aside_send_current_message,
                            character_id,
                            save_slot
                        )
                        sensitive message_text.strip() != "" and not aside_llm_pending
                        padding (14, 6)
                        background Solid("#3a4658")
                        hover_background Solid("#52657f")
                        text_color "#ffffff"

                    textbutton "Reset Aside":
                        action Function(_vne_reset_aside_memory, character_id, save_slot)
                        padding (14, 6)
                        background Solid("#5a3a3a")
                        hover_background Solid("#7f5252")
                        text_color "#ffffff"

                    textbutton "Close":
                        action Return("__close__")
                        padding (14, 6)
                        background Solid("#5a5a5a")
                        hover_background Solid("#7f7f7f")
                        text_color "#ffffff"


# Dev/test entry point. Opt-in: reachable via the dev overlay (developer mode)
# or by jumping to this label from the RenPy console.
label aside_dev_entry:
    $ aside_save_slot = "dev_slot"
    $ aside_chat_history = []
    $ aside_input_text = ""
    $ aside_llm_pending = False

    call aside_chat_loop("kira", aside_save_slot)

    return


label aside_chat_loop(character_id, save_slot):
    while True:
        $ result = renpy.call_screen(
            "aside_chat_log",
            character_id=character_id,
            save_slot=save_slot,
        )

        if result == "__close__" or result == "close":
            return

    return


# Quick entry point for console/direct access.
label aside_quick:
    $ aside_save_slot = "dev_slot"
    $ aside_chat_history = []
    $ aside_input_text = ""
    $ aside_llm_pending = False

    call aside_chat_loop("kira", aside_save_slot)

    return
