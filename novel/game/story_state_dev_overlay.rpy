# story_state_dev_overlay.rpy — Developer-only Story Runtime State overlay.
# RN-AUTO-01-A single-file authorization.
#
# Reads (never writes) the four canonical v2_* store variables:
#   v2_flags, v2_completed_scenes, v2_levels, v2_relationships
#
# Self-registers via config.overlay_screens — no other file needs editing.
# Gated behind config.developer — invisible in release builds.

init python:
    if config.developer:
        config.overlay_screens.append("story_state_dev_overlay")

    _SS_SENTINEL = object()

    def _ss_read(name):
        """Safely read a v2_* variable from the Ren'Py store.

        Returns (kind, data) where:
          kind ∈ {"not_initialized", "set", "dict", "fallback"}
          data is a display-ready list (sorted set or sorted dict items)
          or the fallback display string.
        """
        import store
        val = getattr(store, name, _SS_SENTINEL)
        if val is _SS_SENTINEL:
            return ("not_initialized", "not initialized")
        if isinstance(val, set):
            return ("set", sorted(val))
        if isinstance(val, dict):
            return ("dict", sorted(val.items()))
        return ("fallback", str(val))


# ---- Overlay: always-on developer-mode button ----

screen story_state_dev_overlay():
    if config.developer:
        textbutton "Story State":
            # Place below the existing Aside developer button.
            yoffset 44
            xalign 0.95
            yalign 0.12
            background Solid("#2d5a3a")
            hover_background Solid("#3d7a4a")
            text_color "#ffffff"
            text_size 14
            action Show("story_state_display")


# ---- Modal read-only state view ----

screen story_state_display():
    modal True
    zorder 300

    python:
        f_kind, f_data = _ss_read("v2_flags")
        c_kind, c_data = _ss_read("v2_completed_scenes")
        l_kind, l_data = _ss_read("v2_levels")
        r_kind, r_data = _ss_read("v2_relationships")

    frame:
        xalign 0.5
        yalign 0.5
        xsize 700
        ysize 520
        background Solid("#1a1a2e")
        padding (20, 15)

        vbox:
            spacing 8
            xfill True

            text "Story Runtime State" size 24 bold True color "#ffffff"

            # ---- 1. Flags ----
            text "1. Flags" size 18 bold True color "#88ccff"
            if f_kind == "not_initialized":
                text "  not initialized" color "#888888" size 14
            elif f_kind == "set":
                if f_data:
                    for item in f_data:
                        text "  • " + str(item) color "#cccccc" size 14
                else:
                    text "  (empty)" color "#666666" size 14
            else:
                text "  " + str(f_data) color "#888888" size 14

            null height 4

            # ---- 2. Completed Scenes ----
            text "2. Completed Scenes" size 18 bold True color "#88ccff"
            if c_kind == "not_initialized":
                text "  not initialized" color "#888888" size 14
            elif c_kind == "set":
                if c_data:
                    for item in c_data:
                        text "  • " + str(item) color "#cccccc" size 14
                else:
                    text "  (empty)" color "#666666" size 14
            else:
                text "  " + str(c_data) color "#888888" size 14

            null height 4

            # ---- 3. Levels ----
            text "3. Levels" size 18 bold True color "#88ccff"
            if l_kind == "not_initialized":
                text "  not initialized" color "#888888" size 14
            elif l_kind == "dict":
                if l_data:
                    for k, v in l_data:
                        text "  • " + str(k) + ": " + str(v) color "#cccccc" size 14
                else:
                    text "  (empty)" color "#666666" size 14
            else:
                text "  " + str(l_data) color "#888888" size 14

            null height 4

            # ---- 4. Relationships ----
            text "4. Relationships" size 18 bold True color "#88ccff"
            if r_kind == "not_initialized":
                text "  not initialized" color "#888888" size 14
            elif r_kind == "dict":
                if r_data:
                    for k, v in r_data:
                        text "  • " + str(k) + ": " + str(v) color "#cccccc" size 14
                else:
                    text "  (empty)" color "#666666" size 14
            else:
                text "  " + str(r_data) color "#888888" size 14

            null height 8

            textbutton "Close":
                xalign 1.0
                action Hide("story_state_display")
                background Solid("#5a5a5a")
                hover_background Solid("#7f7f7f")
                text_color "#ffffff"
