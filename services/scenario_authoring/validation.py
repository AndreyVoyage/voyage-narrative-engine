#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.1) -- cross-object integrity validation.

Model construction validity (stable ids, duplicate rejection, segmentation,
media-reference shape) is enforced in ``model.py`` at construction time. This
module performs the cross-object checks a single entity cannot see on its own:

- every Card connection target resolves to an existing Card;
- every branch connection (with ``choice_id``) references an authored CHOICE
  item inside the source Card;
- every ChoiceOption ``target_connection_id`` resolves to a connection of the
  same Card.

No filesystem I/O, no external lookup, no runtime/gameplay analysis.
"""

from __future__ import annotations

from .model import CONTENT_KIND_CHOICE, Project


def validate_project(project: Project) -> list[str]:
    """Return human-readable cross-object violations (empty == consistent).

    This is intentionally separate from construction validity: a project may be
    perfectly well-formed but internally inconsistent (e.g. a dangling
    connection). Construction never fails for these; this function reports them.
    """
    errors: list[str] = []
    card_ids = {card.card_id for card in project.cards}

    for card in project.cards:
        connection_ids = {connection.connection_id for connection in card.connections}
        choice_ids = card.choice_ids()

        for connection in card.connections:
            if connection.target_card_id not in card_ids:
                errors.append(
                    f"card {card.card_id!r}: connection {connection.connection_id!r} "
                    f"targets unknown card {connection.target_card_id!r}"
                )
            if (
                connection.choice_id is not None
                and connection.choice_id not in choice_ids
            ):
                errors.append(
                    f"card {card.card_id!r}: branch connection "
                    f"{connection.connection_id!r} references unknown choice "
                    f"{connection.choice_id!r}"
                )

        for item in card.iter_content_items():
            if item.kind != CONTENT_KIND_CHOICE or item.choice is None:
                continue
            for option in item.choice.options:
                if (
                    option.target_connection_id is not None
                    and option.target_connection_id not in connection_ids
                ):
                    errors.append(
                        f"card {card.card_id!r}: choice {item.choice.choice_id!r} "
                        f"option {option.option_id!r} references unknown connection "
                        f"{option.target_connection_id!r}"
                    )

    return errors


def is_project_consistent(project: Project) -> bool:
    """Convenience predicate: True iff ``validate_project`` is empty."""
    return not validate_project(project)
