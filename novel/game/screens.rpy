# ── In-game menu (ESC) and confirmation wiring ─────────────────────────────
init python:
    # Standard Ren'Py game-menu wiring. ESC is bound to the "game_menu"
    # keymap (00keymap.rpy) which calls _invoke_game_menu; when not already
    # inside a menu it calls _game_menu in a new context (00gamemenu.rpy).
    # That label shows the screen named by _game_menu_screen (transient) and
    # returns to the story via _noisy_return when closed, so pressing ESC
    # while the menu is open returns to the current story. No custom keyboard
    # polling is used.
    _game_menu_screen = "game_menu"

    # Route Quit(confirm=True) / MainMenu(confirm=True) to our styled
    # confirmation dialog below instead of the bare built-in prompt.
    config.confirm_screen = "confirm"


screen yesno_prompt(message, yes_action, no_action):
    modal True
    zorder 200

    add Solid("#000000") alpha 0.65

    frame:
        xalign 0.5
        yalign 0.5
        xmaximum 620
        padding (48, 36)
        background Solid("#20202a")

        vbox:
            spacing 28
            xalign 0.5

            text message:
                xalign 0.5
                text_align 0.5
                color "#f4f4f8"
                size 28

            hbox:
                xalign 0.5
                spacing 32

                textbutton "Да":
                    action yes_action
                    padding (28, 12)
                    background Solid("#3a4658")
                    hover_background Solid("#52657f")
                    text_color "#ffffff"
                    text_hover_color "#ffffff"

                textbutton "Нет":
                    action no_action
                    padding (28, 12)
                    background Solid("#3a4658")
                    hover_background Solid("#52657f")
                    text_color "#ffffff"
                    text_hover_color "#ffffff"

    key "K_ESCAPE" action no_action


# ── Player Shell v0 screens ────────────────────────────────────────────────
# main_menu / load / preferences. No images/audio/font assets (OD-UX-04).
# Each submenu screen is self-contained (minimal back navigation), rather
# than replicating the stock shared-chrome game_menu/navigation architecture.

screen main_menu():
    tag menu

    add Solid("#05050a")

    text "НАРРАТИВ":
        xalign 0.5
        yalign 0.28
        size 96
        color "#e8e8ec"
        font "DejaVuSans-Bold.ttf"

    vbox:
        xalign 0.5
        yalign 0.62
        spacing 24

        textbutton "Новая игра":
            action Start("player_shell_new_game")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 40

        textbutton "Продолжить":
            action Continue()
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_insensitive_color "#55555c"
            text_size 40

        textbutton "Загрузить":
            action ShowMenu("load")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 40

        textbutton "Настройки":
            action ShowMenu("preferences")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 40

        textbutton "Выход":
            action Quit(confirm=True)
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 40

    text "{}  v{}".format("НАРРАТИВ", config.version):
        xalign 0.02
        yalign 0.98
        size 16
        color "#55555c"

    if config.developer:
        textbutton "DEV":
            action Start("dev_scene_selector")
            xalign 0.98
            yalign 0.02
            text_color "#55555c"
            text_hover_color "#ffffff"
            text_size 16


screen load():
    tag menu

    add Solid("#05050a")

    frame:
        xalign 0.5
        yalign 0.5
        padding (40, 32)
        background Solid("#20202a")

        vbox:
            spacing 24
            xalign 0.5

            text "Загрузить":
                xalign 0.5
                text_align 0.5
                color "#f4f4f8"
                size 40

            hbox:
                xalign 0.5
                spacing 12

                textbutton "Обычные":
                    action FilePage(1)
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

                textbutton "Авто":
                    action FilePage("auto")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

                textbutton "Быстрые":
                    action FilePage("quick")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

            hbox:
                xalign 0.5
                spacing 16

                textbutton "<":
                    action FilePagePrevious()
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_size 24

                text "Страница [FileCurrentPage()]":
                    yalign 0.5
                    color "#88888c"
                    size 18

                textbutton ">":
                    action FilePageNext()
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_size 24

            grid 3 2:
                xalign 0.5
                spacing 20

                for i in range(1, 7):
                    button:
                        action FileLoad(i)
                        xsize 420
                        ysize 240
                        padding (14, 14)
                        background Solid("#14141e")
                        hover_background Solid("#262636")
                        has vbox
                        xalign 0.5
                        spacing 10

                        add FileScreenshot(i) xalign 0.5

                        text FileTime(i, format="%d.%m.%Y %H:%M", empty="Пусто"):
                            xalign 0.5
                            color "#e8e8ec"
                            size 20

                        text "Слот {}".format(i):
                            xalign 0.5
                            color "#88888c"
                            size 18

            textbutton "Назад":
                action Return()
                xalign 0.5
                text_color "#e8e8ec"
                text_hover_color "#ffffff"
                text_size 28


screen preferences():
    tag menu

    add Solid("#05050a")

    frame:
        xalign 0.5
        yalign 0.5
        padding (48, 36)
        background Solid("#20202a")

        vbox:
            spacing 28
            xalign 0.5

            text "Настройки":
                xalign 0.5
                text_align 0.5
                color "#f4f4f8"
                size 40

            hbox:
                spacing 16
                text "Экран":
                    color "#e8e8ec"
                    size 28
                textbutton "Оконный":
                    action Preference("display", "window")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24
                textbutton "Полный экран":
                    action Preference("display", "fullscreen")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

            hbox:
                spacing 16
                text "Скорость текста":
                    color "#e8e8ec"
                    size 28
                textbutton "Мгновенно":
                    action Preference("text speed", 0)
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24
                textbutton "Быстро":
                    action Preference("text speed", 60)
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24
                textbutton "Медленно":
                    action Preference("text speed", 20)
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

            hbox:
                spacing 16
                text "Автопереход":
                    color "#e8e8ec"
                    size 28
                textbutton "Вкл":
                    action Preference("auto-forward", "enable")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24
                textbutton "Выкл":
                    action Preference("auto-forward", "disable")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

            textbutton "Назад":
                action Return()
                xalign 0.5
                text_color "#e8e8ec"
                text_hover_color "#ffffff"
                text_size 28


screen game_menu():
    tag menu

    add Solid("#05050a")

    text "МЕНЮ ИГРЫ":
        xalign 0.5
        yalign 0.12
        size 64
        color "#e8e8ec"
        font "DejaVuSans-Bold.ttf"

    vbox:
        xalign 0.5
        yalign 0.36
        spacing 20

        textbutton "Продолжить":
            action Return()
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Сохранить":
            action ShowMenu("save")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Загрузить":
            action ShowMenu("load")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Настройки":
            action ShowMenu("preferences")
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Главное меню":
            action MainMenu(confirm=True)
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Выход из игры":
            action Quit(confirm=True)
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Быстрое сохранение":
            action QuickSave()
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36

        textbutton "Быстрая загрузка":
            action QuickLoad()
            text_color "#e8e8ec"
            text_hover_color "#ffffff"
            text_size 36


screen save():
    tag menu

    add Solid("#05050a")

    frame:
        xalign 0.5
        yalign 0.5
        padding (40, 32)
        background Solid("#20202a")

        vbox:
            spacing 24
            xalign 0.5

            text "Сохранить":
                xalign 0.5
                text_align 0.5
                color "#f4f4f8"
                size 40

            hbox:
                xalign 0.5
                spacing 12

                textbutton "Обычные":
                    action FilePage(1)
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

                textbutton "Авто":
                    action FilePage("auto")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

                textbutton "Быстрые":
                    action FilePage("quick")
                    selected_background Solid("#e8e8ec")
                    selected_hover_background Solid("#ffffff")
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_selected_color "#14141c"
                    text_selected_hover_color "#000000"
                    text_size 24

            hbox:
                xalign 0.5
                spacing 16

                textbutton "<":
                    action FilePagePrevious()
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_size 24

                text "Страница [FileCurrentPage()]":
                    yalign 0.5
                    color "#88888c"
                    size 18

                textbutton ">":
                    action FilePageNext()
                    text_color "#e8e8ec"
                    text_hover_color "#ffffff"
                    text_size 24

            grid 3 2:
                xalign 0.5
                spacing 20

                for i in range(1, 7):
                    button:
                        action FileSave(i)
                        xsize 420
                        ysize 240
                        padding (14, 14)
                        background Solid("#14141e")
                        hover_background Solid("#262636")
                        has vbox
                        xalign 0.5
                        spacing 10

                        add FileScreenshot(i) xalign 0.5

                        text FileTime(i, format="%d.%m.%Y %H:%M", empty="Пусто"):
                            xalign 0.5
                            color "#e8e8ec"
                            size 20

                        text "Слот {}".format(i):
                            xalign 0.5
                            color "#88888c"
                            size 18

            textbutton "Назад":
                action Return()
                xalign 0.5
                text_color "#e8e8ec"
                text_hover_color "#ffffff"
                text_size 28


screen confirm(message, yes_action, no_action):
    modal True
    zorder 200

    add Solid("#000000") alpha 0.65

    frame:
        xalign 0.5
        yalign 0.5
        xmaximum 620
        padding (48, 36)
        background Solid("#20202a")

        vbox:
            spacing 28
            xalign 0.5

            text message:
                xalign 0.5
                text_align 0.5
                color "#f4f4f8"
                size 28

            hbox:
                xalign 0.5
                spacing 32

                textbutton "Да":
                    action yes_action
                    padding (28, 12)
                    background Solid("#3a4658")
                    hover_background Solid("#52657f")
                    text_color "#ffffff"
                    text_hover_color "#ffffff"

                textbutton "Нет":
                    action no_action
                    padding (28, 12)
                    background Solid("#3a4658")
                    hover_background Solid("#52657f")
                    text_color "#ffffff"
                    text_hover_color "#ffffff"

    key "K_ESCAPE" action no_action
