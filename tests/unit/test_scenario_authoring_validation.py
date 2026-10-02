#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.1 Scenario Authoring cross-object integrity tests (T10, T11, T14)."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CONTENT_KIND_CHOICE,
    AuthoredChoice,
    Card,
    CardConnection,
    ChoiceOption,
    ContentItem,
    Project,
    Slide,
    is_project_consistent,
    validate_project,
)

_SCHEMA = SCENARIO_AUTHORING_SCHEMA_VERSION


def _choice_item(item_id="item_ch", choice_id="ch_1", options=()):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_CHOICE,
        choice=AuthoredChoice(choice_id=choice_id, prompt="Choose:", options=options),
    )


def _card(card_id, slides=None, connections=()):
    return Card(card_id=card_id, slides=slides if slides is not None else (Slide(slide_id="slide_1"),),
                connections=connections)


def _project(cards, start):
    return Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=cards, start_card_id=start)


def test_t10_reject_dangling_card_connection():
    card_a = _card(
        "card_a",
        connections=(CardConnection(connection_id="conn_1", target_card_id="card_missing"),),
    )
    project = _project((card_a,), "card_a")
    errors = validate_project(project)
    assert any("unknown card" in error for error in errors)
    assert not is_project_consistent(project)


def test_t11_validate_explicit_authored_branch():
    choice = _choice_item(
        options=(ChoiceOption(option_id="opt_1", label="Left"),
                 ChoiceOption(option_id="opt_2", label="Right")),
    )
    card_a = _card(
        "card_a",
        slides=(Slide(slide_id="slide_1", content_items=(choice,)),),
        connections=(
            CardConnection(connection_id="conn_1", target_card_id="card_b", label="Left", choice_id="ch_1"),
            CardConnection(connection_id="conn_2", target_card_id="card_c", label="Right", choice_id="ch_1"),
        ),
    )
    project = _project((card_a, _card("card_b"), _card("card_c")), "card_a")
    assert validate_project(project) == []
    assert is_project_consistent(project)


def test_branch_connection_must_reference_valid_choice():
    card_a = _card(
        "card_a",
        connections=(CardConnection(connection_id="conn_1", target_card_id="card_b", choice_id="missing_ch"),),
    )
    project = _project((card_a, _card("card_b")), "card_a")
    errors = validate_project(project)
    assert any("unknown choice" in error for error in errors)


def test_option_must_reference_valid_connection():
    choice = _choice_item(
        options=(ChoiceOption(option_id="opt_1", label="Go", target_connection_id="missing_conn"),),
    )
    card_a = _card("card_a", slides=(Slide(slide_id="slide_1", content_items=(choice,)),))
    project = _project((card_a,), "card_a")
    errors = validate_project(project)
    assert any("unknown connection" in error for error in errors)


def test_t14_prevent_implicit_branch_reassignment():
    connection = (CardConnection(connection_id="conn_1", target_card_id="card_b", label="Next"),)
    s1 = Slide(slide_id="slide_1")
    s2 = Slide(slide_id="slide_2")
    original = Card(card_id="card_a", slides=(s1, s2), connections=connection)
    # Reordering slides does NOT touch authoring connections (no implicit
    # reassignment); connections are explicit, ordered authoring data.
    reordered = Card(card_id="card_a", slides=(s2, s1), connections=connection)
    assert original.connections == reordered.connections
    assert [c.target_card_id for c in reordered.connections] == ["card_b"]
    # Connections are frozen and carry no mutator, so they cannot be silently
    # re-targeted (e.g. by a split/merge or content move).
    with pytest.raises(dataclasses.FrozenInstanceError):
        original.connections[0].target_card_id = "card_c"
