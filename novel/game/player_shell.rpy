# player_shell.rpy — Player Shell v0: splash + main-menu context bootstrap.
#
# Responsibilities (Player Shell v0, OD-UX-01..06):
# - label splashscreen: typography-only "НАРРАТИВ" fade-in/hold/fade-out.
# - label main_menu: explicit main-menu context (call screen main_menu).
# - label player_shell_new_game: player-facing entry to the first-real canonical scene.
#
# Screens live in screens.rpy, not here (file-ownership design).
# The player-facing new-game entry routes to the first-real canonical scene
# (OD-FIRST-REAL-PLAYER-ENTRY-01).


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
    # First-real canonical scene entry (OD-FIRST-REAL-PLAYER-ENTRY-01).
    # Not permanent Chapter 1; a later accepted story-start may replace this.
    jump vne_scene_onrv623jojqv66lpm5qv62dbnrwf653bojwxk4c7gaydc_start