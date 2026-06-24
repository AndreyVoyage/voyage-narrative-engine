screen yesno_prompt(message, yes_action, no_action):
    modal True
    zorder 200

    frame:
        xalign 0.5
        yalign 0.5
        padding (40, 30)

        vbox:
            spacing 20

            text message:
                xalign 0.5
                text_align 0.5

            hbox:
                xalign 0.5
                spacing 40

                textbutton "Да" action yes_action
                textbutton "Нет" action no_action

    key "K_ESCAPE" action no_action
