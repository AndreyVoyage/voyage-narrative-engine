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
