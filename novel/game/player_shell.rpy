# player_shell.rpy — Player Shell v0: splash + main-menu context bootstrap.
#
# Responsibilities (Player Shell v0, OD-UX-01..06):
# - label splashscreen: typography-only "НАРРАТИВ" fade-in/hold/fade-out.
# - label main_menu: explicit main-menu context (call screen main_menu).
# - label player_shell_new_game: temporary non-canonical bootstrap to SC_017.
#
# Screens live in screens.rpy, not here (file-ownership design).
# The one and only place that knows about the temporary demo entry
# sc_017_v2_start is label player_shell_new_game below (OD-UX-02).


label splashscreen:
    # Typography-only splash (OD-UX-01 / OD-UX-04): no image/audio assets.
    scene black
    show expression Text("НАРРАТИВ", size=96, color="#e8e8ec", font="DejaVuSans-Bold.ttf") as splash_logo:
        xalign 0.5
        yalign 0.5
        alpha 0.0
        linear 0.5 alpha 1.0
    pause 1.8
    hide splash_logo with dissolve
    return


label main_menu:
    # Explicit main-menu context. The engine jumps here when
    # renpy.has_label("main_menu") is true; we then block on our own screen.
    call screen main_menu
    return


label player_shell_new_game:
    # TEMPORARY NON-CANONICAL DEMO ENTRY (OD-UX-02).
    # Replace with the real story-start label once Chapter 1 exists.
    jump sc_017_v2_start