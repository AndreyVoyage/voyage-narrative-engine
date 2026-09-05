#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SceneBody model validity + acceptance-completeness tests."""

from __future__ import annotations

import dataclasses

import pytest

from services.scene_body import (
    AUTHORING_SCHEMA_VERSION,
    ChoiceEntry,
    ChoiceOption,
    ChoiceTarget,
    Participant,
    SceneBody,
    SceneBodyValidationError,
    TextEntry,
    VisualChangeEvent,
    is_acceptance_complete,
    validate_acceptance_complete,
)


def _narrative(entry_id="e1", text="Kira enters the yoga hall.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="NARRATIVE", text=text)


def _dialogue(entry_id="e2", character_id="KIRA", text="Hello.") -> TextEntry:
    return TextEntry(
        entry_id=entry_id,
        presentation="DIALOGUE",
        text=text,
        character_id=character_id,
    )


def _thought(entry_id="e3", character_id="KIRA", text="I should stretch.", visibility="hidden") -> TextEntry:
    return TextEntry(
        entry_id=entry_id,
        presentation="THOUGHT",
        text=text,
        character_id=character_id,
        thought_visibility=visibility,
    )


def _choice(entry_id="c1", option_id="o1", target_kind="SCENE", target_id="SC_901") -> ChoiceEntry:
    return ChoiceEntry(
        entry_id=entry_id,
        prompt="What next?",
        options=(ChoiceOption(option_id=option_id, display_text="Continue",
                              target=ChoiceTarget(target_kind=target_kind, target_id=target_id)),),
    )


def _visual(entry_id="v1", operation="SET", asset_id="kira_yoga_hall", transition="fade") -> VisualChangeEvent:
    return VisualChangeEvent(entry_id=entry_id, operation=operation, asset_id=asset_id, transition=transition)


def _body(**overrides) -> SceneBody:
    fields = dict(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id="SC_900",
        participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
        entries=(_narrative(),),
        scene_title="Test scene",
        location_id="yoga_hall",
        content_rating="PG",
    )
    fields.update(overrides)
    return SceneBody(**fields)


# ---------------------------------------------------------------------------
# Model validity -- construction
# ---------------------------------------------------------------------------

def test_valid_complete_body() -> None:
    body = _body()
    assert body.scene_id == "SC_900"
    assert body.location_id == "yoga_hall"
    assert len(body.entries) == 1


def test_exact_schema_version_enforced() -> None:
    with pytest.raises(SceneBodyValidationError):
        _body(authoring_schema_version="scene_body/0.9")
    with pytest.raises(SceneBodyValidationError):
        _body(authoring_schema_version="scene_body/2.0")


def test_scene_id_non_empty() -> None:
    with pytest.raises(SceneBodyValidationError):
        _body(scene_id="")


def test_unknown_entry_kind_rejected_via_dict() -> None:
    data = _body().to_dict()
    data["entries"] = [{"entry_id": "x1", "kind": "UNKNOWN"}]
    with pytest.raises(SceneBodyValidationError):
        SceneBody.from_dict(data)


def test_unknown_presentation_rejected() -> None:
    with pytest.raises(SceneBodyValidationError):
        TextEntry(entry_id="e1", presentation="ACTION", text="runs")


def test_unknown_visual_operation_rejected() -> None:
    with pytest.raises(SceneBodyValidationError):
        VisualChangeEvent(entry_id="v1", operation="FADE")


def test_unknown_target_kind_rejected() -> None:
    with pytest.raises(SceneBodyValidationError):
        ChoiceTarget(target_kind="ENTRY_TWO", target_id="e1")


def test_duplicate_entry_ids_rejected() -> None:
    with pytest.raises(SceneBodyValidationError):
        _body(entries=(_narrative("e1"), _narrative("e1")))


def test_duplicate_option_ids_rejected_across_choices() -> None:
    with pytest.raises(SceneBodyValidationError):
        _body(
            entries=(
                ChoiceEntry(entry_id="c1", options=(ChoiceOption(option_id="o1", display_text="A"),)),
                ChoiceEntry(entry_id="c2", options=(ChoiceOption(option_id="o1", display_text="B"),)),
            )
        )


def test_clear_with_asset_structurally_invalid() -> None:
    with pytest.raises(SceneBodyValidationError):
        VisualChangeEvent(entry_id="v1", operation="CLEAR", asset_id="kira_yoga_hall")


def test_set_without_asset_draft_valid() -> None:
    entry = VisualChangeEvent(entry_id="v1", operation="SET", asset_id=None)
    assert entry.asset_id is None


def test_clear_without_asset_draft_valid() -> None:
    entry = VisualChangeEvent(entry_id="v1", operation="CLEAR", asset_id=None)
    assert entry.operation == "CLEAR"


# ---------------------------------------------------------------------------
# Draft incomplete allowed (model validity, not acceptance)
# ---------------------------------------------------------------------------

def test_empty_entries_draft_allowed() -> None:
    body = _body(entries=(), location_id=None, content_rating=None)
    assert body.entries == ()
    assert not is_acceptance_complete(body)


def test_blank_text_draft_allowed() -> None:
    body = _body(entries=(_narrative(text=""),), location_id=None, content_rating=None)
    assert body.entries[0].text == ""


def test_zero_choice_options_draft_allowed() -> None:
    body = _body(entries=(ChoiceEntry(entry_id="c1"),), location_id=None, content_rating=None)
    assert body.entries[0].options == ()


def test_blank_choice_display_draft_allowed() -> None:
    body = _body(
        entries=(ChoiceEntry(entry_id="c1", options=(ChoiceOption(option_id="o1", display_text=""),)),),
        location_id=None,
        content_rating=None,
    )
    assert body.entries[0].options[0].display_text == ""


def test_missing_target_draft_allowed() -> None:
    body = _body(
        entries=(ChoiceEntry(entry_id="c1", options=(ChoiceOption(option_id="o1", display_text="A"),)),),
        location_id=None,
        content_rating=None,
    )
    assert body.entries[0].options[0].target is None


# ---------------------------------------------------------------------------
# Acceptance completeness
# ---------------------------------------------------------------------------

def test_complete_body_is_acceptance_complete() -> None:
    body = _body(entries=(_narrative(), _dialogue(), _choice(), _visual()))
    assert validate_acceptance_complete(body) == []
    assert is_acceptance_complete(body)


def test_missing_location_and_rating_rejected_at_acceptance() -> None:
    body = _body(location_id=None, content_rating=None)
    errors = validate_acceptance_complete(body)
    assert any("location_id" in e for e in errors)
    assert any("content_rating" in e for e in errors)


def test_blank_narrative_rejected_at_acceptance() -> None:
    body = _body(entries=(_narrative(text=""),))
    assert any("text must be non-blank" in e for e in validate_acceptance_complete(body))


def test_dialogue_character_must_resolve() -> None:
    body = _body(entries=(_dialogue(character_id="SERGEY"),))
    assert any("not a participant" in e for e in validate_acceptance_complete(body))


def test_thought_visibility_required() -> None:
    body = _body(entries=(_thought(visibility=None),))
    assert any("thought_visibility" in e for e in validate_acceptance_complete(body))


def test_zero_options_rejected_at_acceptance() -> None:
    body = _body(entries=(ChoiceEntry(entry_id="c1"),))
    assert any("at least one option" in e for e in validate_acceptance_complete(body))


def test_blank_option_text_rejected_at_acceptance() -> None:
    body = _body(entries=(ChoiceEntry(entry_id="c1", options=(ChoiceOption(option_id="o1", display_text=""),)),))
    assert any("display_text" in e for e in validate_acceptance_complete(body))


def test_missing_target_rejected_at_acceptance() -> None:
    body = _body(entries=(ChoiceEntry(entry_id="c1", options=(ChoiceOption(option_id="o1", display_text="A"),)),))
    assert any("target is required" in e for e in validate_acceptance_complete(body))


def test_unresolved_entry_target_rejected() -> None:
    body = _body(entries=(_narrative("e1"), _choice(target_kind="ENTRY", target_id="DOES_NOT_EXIST")))
    assert any("does not resolve" in e for e in validate_acceptance_complete(body))


def test_entry_target_self_reference_allowed() -> None:
    body = _body(entries=(_choice(entry_id="c1", target_kind="ENTRY", target_id="c1"),))
    assert validate_acceptance_complete(body) == []


def test_set_without_asset_rejected_at_acceptance() -> None:
    body = _body(entries=(_visual(asset_id=None),))
    assert any("SET requires an asset_id" in e for e in validate_acceptance_complete(body))


def test_set_invalid_asset_syntax_rejected() -> None:
    body = _body(entries=(_visual(asset_id="NOT_A_VALID_asset-id"),))
    assert any("asset_id" in e for e in validate_acceptance_complete(body))


def test_clear_accepted() -> None:
    body = _body(entries=(_visual(operation="CLEAR", asset_id=None),))
    assert validate_acceptance_complete(body) == []


# ---------------------------------------------------------------------------
# Serialization / immutability / id stability
# ---------------------------------------------------------------------------

def test_to_dict_round_trip_preserves_order_and_ids() -> None:
    body = _body(entries=(_narrative("e1"), _dialogue("e2"), _choice("c1"), _visual("v1")))
    rebuilt = SceneBody.from_dict(body.to_dict())
    assert rebuilt.to_dict() == body.to_dict()
    assert [e.entry_id for e in rebuilt.entries] == ["e1", "e2", "c1", "v1"]


def test_entry_ids_stable_through_reorder() -> None:
    a = _body(entries=(_narrative("e1"), _dialogue("e2")))
    b = _body(entries=(_dialogue("e2"), _narrative("e1")))
    assert {e.entry_id for e in a.entries} == {e.entry_id for e in b.entries}
    assert a.to_dict()["entries"][0]["entry_id"] == "e1"
    assert b.to_dict()["entries"][0]["entry_id"] == "e2"


def test_immutable_body() -> None:
    body = _body()
    with pytest.raises(dataclasses.FrozenInstanceError):
        body.scene_id = "X"  # type: ignore[misc]


def test_to_dict_returns_fresh_data() -> None:
    body = _body()
    d = body.to_dict()
    d["scene_id"] = "MUTATED"
    assert body.scene_id == "SC_900"
    assert body.to_dict()["scene_id"] == "SC_900"
