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

init python:
    import sys
    from pathlib import Path

    # Path to repo tools. Lazy import inside helpers keeps RenPy lint/SDK
    # validation clean when tools/ are not present (e.g. temp copies).
    _VNE_TOOLS_DIR = str(Path(config.gamedir).parent.parent / "tools")

    def _vne_readonly_canon_snapshot():
        """Build a past-only canon snapshot reading v2_* (read-only)."""
        import store

        # Read-only copies; no mutation of the source sets/dicts.
        flags = sorted(list(store.v2_flags))
        completed_scenes = sorted(list(store.v2_completed_scenes))
        levels = dict(store.v2_levels)
        relationships = dict(store.v2_relationships)

        return {
            "scene_id": store.vne_current_scene_id,
            "beat_id": store.vne_current_beat_id,
            "progress_index": store.vne_current_progress_index,
            "flags": flags,
            "completed_scenes": completed_scenes,
            "levels": levels,
            "relationships": relationships,
            "content_rating": store.vne_current_content_rating,
        }

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

    def _vne_run_aside_turn(character_id, player_message, save_slot):
        """Run one aside turn and append to isolated memory.

        Uses the configured provider; falls back to mock on Ollama connection
        errors. Returns a dict: {"reply": str, "fallback": bool, "warning": str}.
        """
        import store

        if _VNE_TOOLS_DIR not in sys.path:
            sys.path.insert(0, _VNE_TOOLS_DIR)

        import aside_context_builder
        import aside_memory_store
        import llm_provider

        snapshot = _vne_readonly_canon_snapshot()
        root = _vne_aside_memory_root()
        progress = snapshot["progress_index"]
        provider = store.vne_aside_config_provider
        base_url = store.vne_aside_config_base_url
        model = store.vne_aside_config_model

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
            canon_snapshot=snapshot,
            aside_memory=memory,
            player_message=player_message,
        )

        fallback = False
        warning = ""

        if provider == "local":
            try:
                reply = llm_provider.complete(
                    messages,
                    provider="local",
                    model=model,
                    params={"base_url": base_url},
                )
            except llm_provider.LLMProviderError as exc:
                if _vne_is_connection_error(exc):
                    # Auto-fallback to mock with a visible warning.
                    warning = f"Ollama unavailable ({exc}); fallback to mock"
                    reply = llm_provider.complete(messages, provider="mock")
                    fallback = True
                else:
                    raise
        else:
            # Mock or any other explicit non-local choice.
            reply = llm_provider.complete(messages, provider="mock")

        # Persist turn to isolated aside memory.
        session = {
            "scene_id": snapshot["scene_id"],
            "beat_id": snapshot["beat_id"],
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

    def _vne_cycle_provider():
        """Cycle provider setting between local and mock."""
        import store
        store.vne_aside_config_provider = (
            "mock" if store.vne_aside_config_provider == "local" else "local"
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

    frame:
        xfill True
        yfill True
        background Solid("#1a1a24")
        padding (20, 20)

        vbox:
            xfill True
            yfill True
            spacing 12

            text "Character Aside — [character_id] ([vne_aside_config_provider])":
                size 26
                color "#f4f4f8"

            viewport:
                id "aside_viewport"
                yfill True
                mousewheel True
                scrollbars "vertical"

                vbox:
                    spacing 6
                    for line in aside_chat_history:
                        text "[line]":
                            color "#d8d8e8"

            # Provider settings row.
            hbox:
                spacing 10
                xfill True

                textbutton "Provider: [vne_aside_config_provider]":
                    action Function(_vne_cycle_provider)
                    padding (10, 6)
                    background Solid("#3a4658")
                    hover_background Solid("#52657f")
                    text_color "#ffffff"

                text "URL:":
                    yalign 0.5
                    color "#888888"

                input:
                    value VariableInputValue("vne_aside_config_base_url")
                    length 120
                    xfill True
                    color "#f4f4f8"

                text "Model:":
                    yalign 0.5
                    color "#888888"

                input:
                    value VariableInputValue("vne_aside_config_model")
                    length 40
                    color "#f4f4f8"

            # Message input + actions row.
            hbox:
                spacing 10
                xfill True

                input:
                    value VariableInputValue("aside_input_text")
                    length 240
                    xfill True
                    color "#f4f4f8"

                textbutton "Send":
                    action Return("send")
                    sensitive aside_input_text.strip() != ""
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
                    action Return("close")
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

    call aside_chat_loop("kira", aside_save_slot)

    return


label aside_chat_loop(character_id, save_slot):
    while True:
        $ result = renpy.call_screen(
            "aside_chat_log",
            character_id=character_id,
            save_slot=save_slot,
        )

        if result == "close":
            return

        if result == "send":
            $ msg = aside_input_text.strip()
            if not msg:
                return

            $ aside_chat_history.append("You: " + msg)
            $ turn = _vne_run_aside_turn(character_id, msg, save_slot)
            $ aside_chat_history.append(character_id.capitalize() + ": " + turn["reply"])
            if turn["fallback"]:
                $ aside_chat_history.append("⚠ " + turn["warning"])
            $ aside_input_text = ""

    return


# Quick entry point for console/direct access.
label aside_quick:
    $ aside_save_slot = "dev_slot"
    $ aside_chat_history = []
    $ aside_input_text = ""

    call aside_chat_loop("kira", aside_save_slot)

    return
