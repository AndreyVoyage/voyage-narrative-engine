#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SceneBody model validity + acceptance-completeness tests."""

from __future__ import annotations

import dataclasses

import pytest

from services.scene_body import (
    AUTHORING_SCHEMA_VERSION,
    TARGET_KIND_END,
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


# ---------------------------------------------------------------------------
# next_target -- explicit successor contract (OD-ORDEREDASS-CONTROL-FLOW-01)
# ---------------------------------------------------------------------------

def test_text_entry_without_next_target_serializes_unchanged() -> None:
    entry = _narrative("e1")
    assert entry.next_target is None
    assert "next_target" not in entry.to_dict()


def test_visual_entry_without_next_target_serializes_unchanged() -> None:
    entry = _visual("v1")
    assert entry.next_target is None
    assert "next_target" not in entry.to_dict()


def test_text_entry_entry_next_target_roundtrip() -> None:
    entry = TextEntry(
        entry_id="e1", presentation="NARRATIVE", text="A",
        next_target=ChoiceTarget(target_kind="ENTRY", target_id="e2"),
    )
    d = entry.to_dict()
    assert d["next_target"] == {"target_kind": "ENTRY", "target_id": "e2"}
    rebuilt = _entry_from_dict_via_body(d)
    assert rebuilt.next_target == ChoiceTarget(target_kind="ENTRY", target_id="e2")
    assert rebuilt.to_dict() == d


def test_text_entry_scene_next_target_roundtrip() -> None:
    entry = TextEntry(
        entry_id="e1", presentation="NARRATIVE", text="A",
        next_target=ChoiceTarget(target_kind="SCENE", target_id="SC_901"),
    )
    d = entry.to_dict()
    assert d["next_target"] == {"target_kind": "SCENE", "target_id": "SC_901"}
    rebuilt = _entry_from_dict_via_body(d)
    assert rebuilt.next_target == ChoiceTarget(target_kind="SCENE", target_id="SC_901")
    assert rebuilt.to_dict() == d


def test_text_entry_end_next_target_roundtrip() -> None:
    entry = TextEntry(
        entry_id="e1", presentation="NARRATIVE", text="A",
        next_target=ChoiceTarget(target_kind="END"),
    )
    d = entry.to_dict()
    # Exact deterministic END representation: target_kind only, no target_id key.
    assert d["next_target"] == {"target_kind": "END"}
    assert "target_id" not in d["next_target"]
    rebuilt = _entry_from_dict_via_body(d)
    assert rebuilt.next_target == ChoiceTarget(target_kind="END")
    assert rebuilt.next_target.target_id is None
    assert rebuilt.to_dict() == d


def test_visual_entry_end_next_target_roundtrip() -> None:
    entry = VisualChangeEvent(
        entry_id="v1", operation="CLEAR", asset_id=None,
        next_target=ChoiceTarget(target_kind="END"),
    )
    d = entry.to_dict()
    assert d["next_target"] == {"target_kind": "END"}
    rebuilt = SceneBody.from_dict(
        _body(entries=(entry,), location_id=None, content_rating=None).to_dict()
    ).entries[0]
    assert rebuilt.next_target == ChoiceTarget(target_kind="END")


def test_end_with_target_id_rejected() -> None:
    with pytest.raises(SceneBodyValidationError):
        ChoiceTarget(target_kind="END", target_id="e1")


def test_end_is_recognized_target_kind() -> None:
    assert TARGET_KIND_END == "END"
    ChoiceTarget(target_kind="END")  # does not raise


def test_invalid_entry_next_target_rejected_at_acceptance() -> None:
    body = _body(
        entries=(
            TextEntry(
                entry_id="e1", presentation="NARRATIVE", text="A",
                next_target=ChoiceTarget(target_kind="ENTRY", target_id="DOES_NOT_EXIST"),
            ),
        ),
    )
    errors = validate_acceptance_complete(body)
    assert any("next_target ENTRY" in e and "does not resolve" in e for e in errors)


def test_valid_entry_next_target_accepted() -> None:
    body = _body(
        entries=(
            TextEntry(
                entry_id="e1", presentation="NARRATIVE", text="A",
                next_target=ChoiceTarget(target_kind="ENTRY", target_id="e2"),
            ),
            _narrative("e2"),
        ),
    )
    assert validate_acceptance_complete(body) == []


def _entry_from_dict_via_body(entry_dict: dict) -> TextEntry:
    """Round-trip one entry dict through SceneBody.from_dict (no private API)."""
    body = _body(entries=(), location_id=None, content_rating=None)
    raw = body.to_dict()
    raw["entries"] = [entry_dict]
    return SceneBody.from_dict(raw).entries[0]


# ---------------------------------------------------------------------------
# Old-JSON backward compatibility (no next_target key anywhere)
# ---------------------------------------------------------------------------

def test_old_serialized_text_entry_loads_without_mutation() -> None:
    old_dict = {
        "entry_id": "e1", "kind": "TEXT", "presentation": "NARRATIVE",
        "text": "A", "character_id": None, "thought_visibility": None,
    }
    entry = _entry_from_dict_via_body(old_dict)
    assert entry.next_target is None
    assert entry.to_dict() == old_dict


def test_old_serialized_visual_entry_loads_without_mutation() -> None:
    old_dict = {
        "entry_id": "v1", "kind": "VISUAL_CHANGE", "operation": "CLEAR",
        "asset_id": None, "transition": None,
    }
    entry = _entry_from_dict_via_body(old_dict)
    assert entry.next_target is None
    assert entry.to_dict() == old_dict


# ---------------------------------------------------------------------------
# Silent multi-branch fallthrough (OD-ORDEREDASS-CONTROL-FLOW-01)
# ---------------------------------------------------------------------------

def _branch_choice(entry_id="c1", targets=("b_a", "b_b", "b_c")) -> ChoiceEntry:
    return ChoiceEntry(
        entry_id=entry_id,
        prompt="Pick",
        options=tuple(
            ChoiceOption(
                option_id=f"o{i + 1}", display_text=f"Option {i + 1}",
                target=ChoiceTarget(target_kind="ENTRY", target_id=t),
            )
            for i, t in enumerate(targets)
        ),
    )


def test_two_branch_missing_successor_rejected() -> None:
    # branch A (b_a) has no next_target and directly precedes branch B's start:
    # silent fallthrough from b_a into b_b.
    body = _body(
        entries=(
            _branch_choice(targets=("b_a", "b_b")),
            _narrative("b_a"),
            _narrative("b_b"),
        ),
    )
    errors = validate_acceptance_complete(body)
    assert any("silent branch fallthrough" in e for e in errors)


def test_two_branch_explicit_end_successor_accepted() -> None:
    body = _body(
        entries=(
            _branch_choice(targets=("b_a", "b_b")),
            TextEntry(
                entry_id="b_a", presentation="NARRATIVE", text="A",
                next_target=ChoiceTarget(target_kind="END"),
            ),
            _narrative("b_b"),
        ),
    )
    assert validate_acceptance_complete(body) == []


def test_three_branch_multi_entry_missing_successor_rejected() -> None:
    # Mirrors the proven SC_017-shaped defect: three 2-entry branches, no
    # explicit successors on the non-final branches.
    body = _body(
        entries=(
            _branch_choice(entry_id="ch1", targets=("a1", "b1", "c1")),
            _narrative("a1"), _narrative("a2"),
            _narrative("b1"), _narrative("b2"),
            _narrative("c1"), _narrative("c2"),
        ),
    )
    errors = validate_acceptance_complete(body)
    # a2 (last entry of branch A, immediately before branch B's start b1) and
    # b2 (last entry of branch B, immediately before branch C's start c1) both
    # lack an explicit successor.
    assert any("a2" in e and "silent branch fallthrough" in e for e in errors)
    assert any("b2" in e and "silent branch fallthrough" in e for e in errors)
    assert not any("c2" in e for e in errors)  # last branch: no next branch to bleed into


def test_three_branch_all_explicit_end_accepted() -> None:
    body = _body(
        entries=(
            _branch_choice(entry_id="ch1", targets=("a1", "b1", "c1")),
            _narrative("a1"),
            TextEntry(entry_id="a2", presentation="NARRATIVE", text="A2",
                      next_target=ChoiceTarget(target_kind="END")),
            _narrative("b1"),
            TextEntry(entry_id="b2", presentation="NARRATIVE", text="B2",
                      next_target=ChoiceTarget(target_kind="END")),
            _narrative("c1"), _narrative("c2"),
        ),
    )
    assert validate_acceptance_complete(body) == []


def test_backward_entry_target_not_treated_as_branch_start() -> None:
    # A single forward ENTRY target plus a backward self-reference must not
    # trigger the multi-branch check (only one forward branch start exists).
    body = _body(
        entries=(
            _narrative("e0"),
            ChoiceEntry(
                entry_id="c1",
                options=(
                    ChoiceOption(option_id="o1", display_text="Forward",
                                 target=ChoiceTarget(target_kind="ENTRY", target_id="e1")),
                    ChoiceOption(option_id="o2", display_text="Back",
                                 target=ChoiceTarget(target_kind="ENTRY", target_id="e0")),
                ),
            ),
            _narrative("e1"),
        ),
    )
    assert validate_acceptance_complete(body) == []


def test_single_branch_scene_unaffected() -> None:
    # The exact shape of the two existing real accepted scenes (one option,
    # one forward branch): never triggers the new invariant.
    body = _body(entries=(_narrative("e1"), _choice(target_kind="ENTRY", target_id="e1")))
    assert validate_acceptance_complete(body) == []


def test_convergent_branches_to_common_join_accepted() -> None:
    # Two branches explicitly converge on a shared join entry via ENTRY
    # next_target, rather than each independently reaching END.
    body = _body(
        entries=(
            _branch_choice(targets=("a1", "b1")),
            TextEntry(entry_id="a1", presentation="NARRATIVE", text="A",
                      next_target=ChoiceTarget(target_kind="ENTRY", target_id="join")),
            TextEntry(entry_id="b1", presentation="NARRATIVE", text="B",
                      next_target=ChoiceTarget(target_kind="ENTRY", target_id="join")),
            _narrative("join", text="Shared continuation."),
        ),
    )
    assert validate_acceptance_complete(body) == []
