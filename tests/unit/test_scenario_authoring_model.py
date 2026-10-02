#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.1 Scenario Authoring model construction-validity tests (T01-T08)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_TEXT,
    AuthoredChoice,
    Card,
    CardConnection,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    Project,
    ScenarioAuthoringValidationError,
    Slide,
    SpeakerOverride,
    Utterance,
    resolve_effective_overrides,
)

_SCHEMA = SCENARIO_AUTHORING_SCHEMA_VERSION


def _utt(utt_id="utt_a", text="Hello", speakers=(), portions=()):
    return Utterance(utterance_id=utt_id, text=text, speaker_ids=speakers, portions=portions)


def _text_item(item_id="item_1", text="Hello", speakers=(), portions=()):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_TEXT,
        utterance=_utt(f"{item_id}_u", text=text, speakers=speakers, portions=portions),
    )


def _slide(slide_id="slide_1", items=()):
    return Slide(slide_id=slide_id, content_items=items)


def _card(card_id="card_a", slides=None, connections=()):
    return Card(card_id=card_id, slides=slides if slides is not None else (_slide(),),
                connections=connections)


def _project(cards, start):
    return Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=cards,
                   start_card_id=start)


def test_t01_create_valid_project():
    project = _project((_card("card_a"),), "card_a")
    assert project.project_id == "proj_alpha"
    assert project.start_card_id == "card_a"
    assert project.card_ids() == ("card_a",)
    assert project.schema_version == _SCHEMA


def test_t02_two_cards_stable_identity():
    project = _project((_card("card_a"), _card("card_b")), "card_a")
    assert project.card_ids() == ("card_a", "card_b")
    assert project.card_by_id("card_b").card_id == "card_b"


def test_t03_multiple_slides_per_card():
    card = Card(
        card_id="card_a",
        slides=(Slide(slide_id="slide_1"), Slide(slide_id="slide_2"), Slide(slide_id="slide_3")),
    )
    assert card.slide_ids() == ("slide_1", "slide_2", "slide_3")


def test_t04_ordered_content_membership():
    slide = Slide(
        slide_id="slide_1",
        content_items=(_text_item("item_1"), _text_item("item_2"), _text_item("item_3")),
    )
    assert [i.item_id for i in slide.content_items] == ["item_1", "item_2", "item_3"]


def test_t05_complete_utterance():
    utt = _utt("utt_a", text="Full text.", speakers=("kira",))
    assert utt.whole_text() == "Full text."
    assert utt.speaker_ids == ("kira",)
    assert utt.portions == ()


def test_t06_portions_keep_authoritative_whole_text():
    text = "Hello there."
    utt = _utt(
        "utt_a",
        text=text,
        speakers=("kira",),
        portions=(
            DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12),
        ),
    )
    # The whole text is preserved; portions are only offsets into it.
    assert utt.whole_text() == "Hello there."
    assert [p.start_offset for p in utt.portions] == [0, 5]
    assert [p.end_offset for p in utt.portions] == [5, 12]


def test_t07_preserve_per_speaker_overrides():
    utt = _utt(
        "utt_a",
        text="Hello there.",
        speakers=("kira", "marina"),
        portions=(
            DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5,
                           overrides=(SpeakerOverride(character_id="kira", emotion="happy"),)),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12,
                           overrides=(SpeakerOverride(character_id="kira", emotion="sad"),)),
        ),
    )
    assert utt.portions[0].overrides[0].emotion == "happy"
    assert utt.portions[1].overrides[0].emotion == "sad"


def test_t07_override_inheritance():
    utt = _utt(
        "utt_a",
        text="Hello there.",
        speakers=("kira",),
        portions=(
            DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5,
                           overrides=(SpeakerOverride(character_id="kira", emotion="happy"),)),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12),
        ),
    )
    resolved = resolve_effective_overrides(utt)
    assert resolved[0][0].emotion == "happy"
    # Inherited from the previous portion (DW-02).
    assert resolved[1][0].emotion == "happy"


def test_t08_reject_invalid_portion_offsets_and_overlap():
    # Out-of-bounds range.
    with pytest.raises(ScenarioAuthoringValidationError):
        _utt("utt_a", text="abc",
             portions=(DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5),))
    # Overlapping ranges (start != previous end).
    with pytest.raises(ScenarioAuthoringValidationError):
        _utt("utt_a", text="abcdef",
             portions=(DisplayPortion("por_1", 0, 3), DisplayPortion("por_2", 2, 6)))
    # Gap (missing coverage).
    with pytest.raises(ScenarioAuthoringValidationError):
        _utt("utt_a", text="abcdef",
             portions=(DisplayPortion("por_1", 0, 2), DisplayPortion("por_2", 3, 6)))
    # Invalid individual portion range (end <= start).
    with pytest.raises(ScenarioAuthoringValidationError):
        DisplayPortion(portion_id="por_1", start_offset=2, end_offset=1)


def test_t09_reject_duplicate_ids():
    # Duplicate slide ids within one card.
    with pytest.raises(ScenarioAuthoringValidationError):
        Card(card_id="card_a", slides=(Slide(slide_id="slide_1"), Slide(slide_id="slide_1")))
    # Duplicate card ids within one project.
    with pytest.raises(ScenarioAuthoringValidationError):
        _project((_card("card_a"), _card("card_a")), "card_a")
    # Duplicate content-item ids within one slide.
    with pytest.raises(ScenarioAuthoringValidationError):
        Slide(slide_id="slide_1", content_items=(_text_item("item_1"), _text_item("item_1")))


def test_stable_id_format_rejected():
    for bad in ("A", "Card A", "card-a", "card a", "", "ca"):
        with pytest.raises(ScenarioAuthoringValidationError):
            Card(card_id=bad, slides=(Slide(slide_id="slide_1"),))


def test_t12_reject_invalid_start_card_id():
    with pytest.raises(ScenarioAuthoringValidationError):
        _project((_card("card_a"),), "card_missing")


def test_t13_preserve_identity_on_reorder():
    s1 = Slide(slide_id="slide_1")
    s2 = Slide(slide_id="slide_2")
    original = Card(card_id="card_a", slides=(s1, s2))
    reordered = Card(card_id="card_a", slides=(s2, s1))
    assert original.slide_ids() == ("slide_1", "slide_2")
    assert reordered.slide_ids() == ("slide_2", "slide_1")
    # Identity is independent of list position; the same objects keep their ids.
    assert s1.slide_id == "slide_1"
    assert s2.slide_id == "slide_2"
    assert set(original.slide_ids()) == set(reordered.slide_ids())


def test_t15_media_references_not_absolute():
    assert MediaReference(asset_id="asset_a").asset_id == "asset_a"
    assert MediaReference(relative_path="media/bg/room.png").relative_path == "media/bg/room.png"
    for bad in ("C:/media/room.png", "/abs/room.png", "\\windows\\room.png",
                "../room.png", "media//room.png", "media/./room.png"):
        with pytest.raises(ScenarioAuthoringValidationError):
            MediaReference(relative_path=bad)
    with pytest.raises(ScenarioAuthoringValidationError):
        MediaReference()
    with pytest.raises(ScenarioAuthoringValidationError):
        MediaReference(asset_id="asset_a", relative_path="media/bg/room.png")


def test_t16_no_ass_contract_modified():
    import inspect

    import services.scenario_authoring.model as model_module
    import services.scenario_authoring.validation as validation_module
    from services.scene_body import AUTHORING_SCHEMA_VERSION as SCENE_BODY_VERSION

    # The existing accepted-scene contract keeps its own ratified schema id.
    assert SCENE_BODY_VERSION == "scene_body/1.0"
    assert SCENARIO_AUTHORING_SCHEMA_VERSION == "scenario_authoring/0.1"
    assert SCENARIO_AUTHORING_SCHEMA_VERSION != SCENE_BODY_VERSION
    # The new package never imports the accepted-scene contracts, so it cannot
    # modify them: it is a strictly additive, UI-independent authoring layer.
    source = inspect.getsource(model_module) + inspect.getsource(validation_module)
    assert "services.ass" not in source
    assert "services.scene_body" not in source
    assert "services.story_sequence" not in source


def test_project_round_trip():
    from services.scenario_authoring import project_from_dict

    project = _project((_card("card_a"), _card("card_b")), "card_a")
    rebuilt = project_from_dict(project.to_dict())
    assert rebuilt.project_id == "proj_alpha"
    assert rebuilt.start_card_id == "card_a"
    assert rebuilt.card_ids() == ("card_a", "card_b")
    assert rebuilt.to_dict() == project.to_dict()



# ---------------------------------------------------------------------------
# SE-1.1 targeted integrity-correction regression tests.
# ---------------------------------------------------------------------------


def _choice_item(item_id, choice_id, prompt="Pick one:", option_id="opt_1"):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_CHOICE,
        choice=AuthoredChoice(
            choice_id=choice_id,
            prompt=prompt,
            options=(ChoiceOption(option_id=option_id, label="Option"),),
        ),
    )


def test_duplicate_choice_id_across_slides_rejected():
    slide_1 = Slide(slide_id="slide_1", content_items=(_choice_item("item_1", "ch_1", option_id="opt_1"),))
    slide_2 = Slide(slide_id="slide_2", content_items=(_choice_item("item_2", "ch_1", option_id="opt_2"),))
    # Rejected at construction even though no branch connection exists yet.
    with pytest.raises(ScenarioAuthoringValidationError):
        Card(card_id="card_a", slides=(slide_1, slide_2))


def test_distinct_choice_ids_and_branch_connections_pass():
    choice = _choice_item("item_1", "ch_1")
    card = Card(
        card_id="card_a",
        slides=(Slide(slide_id="slide_1", content_items=(choice,)),),
        connections=(CardConnection(connection_id="conn_1", target_card_id="card_b", choice_id="ch_1"),),
    )
    assert card.choice_ids() == frozenset({"ch_1"})


def test_card_choice_ids_across_slides():
    slide_1 = Slide(slide_id="slide_1", content_items=(_choice_item("item_1", "ch_1"),))
    slide_2 = Slide(slide_id="slide_2", content_items=(_choice_item("item_2", "ch_2"),))
    card = Card(card_id="card_a", slides=(slide_1, slide_2))
    assert card.choice_ids() == frozenset({"ch_1", "ch_2"})


def test_choice_option_label_rejects_blank():
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(ScenarioAuthoringValidationError):
            ChoiceOption(option_id="opt_1", label=bad)
    opt = ChoiceOption(option_id="opt_1", label="  Go left  ")
    assert opt.label == "  Go left  "


def test_authored_choice_prompt_rejects_blank():
    for bad in ("", "   ", "\n\t"):
        with pytest.raises(ScenarioAuthoringValidationError):
            AuthoredChoice(choice_id="ch_1", prompt=bad)
    choice = AuthoredChoice(choice_id="ch_1", prompt="  What do you do?  ")
    assert choice.prompt == "  What do you do?  "


def test_project_from_dict_missing_required_field():
    from services.scenario_authoring import project_from_dict

    with pytest.raises(ScenarioAuthoringValidationError) as exc:
        project_from_dict({
            "schema_version": _SCHEMA,
            "cards": [{"card_id": "card_a", "slides": []}],
            "start_card_id": "card_a",
        })
    assert "project_id" in str(exc.value)


def test_project_from_dict_missing_nested_required_field():
    from services.scenario_authoring import project_from_dict

    with pytest.raises(ScenarioAuthoringValidationError) as exc:
        project_from_dict({
            "schema_version": _SCHEMA,
            "project_id": "proj_alpha",
            "cards": [{"slides": []}],
            "start_card_id": "card_a",
        })
    assert "card_id" in str(exc.value)


def test_unc_and_drive_relative_media_paths_rejected():
    for bad in ("//server/share/room.png", r"\\server\share\room.png", "C:media/room.png"):
        with pytest.raises(ScenarioAuthoringValidationError):
            MediaReference(relative_path=bad)


def test_utterance_text_preserves_whitespace_and_line_breaks():
    text = "  Line one.\n\tLine two.  "
    utt = Utterance(utterance_id="utt_a", text=text)
    assert utt.text == text
    assert utt.whole_text() == text


def test_portrait_inheritance_across_portions():
    portrait = MediaReference(asset_id="asset_portrait")
    utt = Utterance(
        utterance_id="utt_a",
        text="Hello there.",
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                portion_id="por_1",
                start_offset=0,
                end_offset=5,
                overrides=(SpeakerOverride(character_id="kira", portrait=portrait),),
            ),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12),
        ),
    )
    resolved = resolve_effective_overrides(utt)
    assert resolved[0][0].portrait == portrait
    # Inherited from the previous portion (DW-02).
    assert resolved[1][0].portrait == portrait

