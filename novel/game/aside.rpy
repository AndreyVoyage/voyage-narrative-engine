# aside.rpy — N6 Character Aside dev/test screen (mock LLM, isolated memory)
#
# Invariants:
# - Reads v2_flags / v2_completed_scenes / v2_levels / v2_relationships ONLY.
# - Never assigns to v2_* or calls mutating methods on them.
# - Uses the mock LLM provider only (no network).
# - Writes aside memory only under RenPy save directory, never into canon.
# - Not wired into the SC_003–SC_018 playable selector.

# Dev/test tracking variables for the current scene/beat. These are local UI
# state, not canon; v2_* remains the single source of canonical truth.
default vne_current_scene_id = "SC_017"
default vne_current_beat_id = "sc_017_v2_1a"
default vne_current_progress_index = 17
default vne_current_content_rating = "PG-13"

init python:
    import sys
    from pathlib import Path

    # Path to repo tools. Lazy import inside _vne_run_aside_turn keeps RenPy
    # lint/SDK validation clean when tools/ are not present (e.g. temp copies).
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

    def _vne_run_aside_turn(character_id, player_message, save_slot):
        """Run one aside turn on mock provider and append to isolated memory."""
        if _VNE_TOOLS_DIR not in sys.path:
            sys.path.insert(0, _VNE_TOOLS_DIR)

        import aside_context_builder
        import aside_memory_store
        import llm_provider

        snapshot = _vne_readonly_canon_snapshot()
        root = _vne_aside_memory_root()
        progress = snapshot["progress_index"]

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

        # N6e: mock provider only, deterministic, no network.
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

        return reply

    # Opt-in dev overlay: visible only when RenPy developer mode is enabled.
    if config.developer:
        config.overlay_screens.append("aside_dev_overlay")


# Dev overlay button. Appears only in developer mode (gated above).
screen aside_dev_overlay():
    zorder 200

    if config.developer:
        frame:
            xalign 0.95
            yalign 0.05
            padding (8, 8)
            background Solid("#20202a")

            vbox:
                spacing 4

                text "N6e dev":
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
screen aside_chat_log(character_id="kira"):
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

            text "Character Aside — [character_id] (MOCK)":
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

                textbutton "Close":
                    action Return("close")
                    padding (14, 6)
                    background Solid("#5a3a3a")
                    hover_background Solid("#7f5252")
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
        $ result = renpy.call_screen("aside_chat_log", character_id=character_id)

        if result == "close":
            return

        if result == "send":
            $ msg = aside_input_text.strip()
            if not msg:
                return

            $ aside_chat_history.append("You: " + msg)
            $ reply = _vne_run_aside_turn(character_id, msg, save_slot)
            $ aside_chat_history.append(character_id.capitalize() + ": " + reply)
            $ aside_input_text = ""

    return
