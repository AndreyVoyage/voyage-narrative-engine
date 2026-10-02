#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.3 Scenario Authoring deterministic projection tests (T01-T18 + vertical example)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import build_ordered_ass, parse_ordered_ass, serialize_ordered_ass  # noqa: E402
from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_MEDIA,
    CONTENT_KIND_TEXT,
    AuthoredChoice,
    Card,
    CardConnection,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    Project,
    ProjectionConfig,
    ProjectionError,
    SceneMembership,
    Slide,
    SpeakerOverride,
    UnsupportedProjectionError,
    Utterance,
    project_scenes,
)
from services.scene_body import (  # noqa: E402
    TARGET_KIND_END,
    TARGET_KIND_ENTRY,
    TARGET_KIND_SCENE,
    TEXT_PRESENTATION_DIALOGUE,
    TEXT_PRESENTATION_NARRATIVE,
    ChoiceEntry,
    TextEntry,
    VisualChangeEvent,
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


def _choice_item(item_id="item_ch", choice_id="ch_1", options=(), prompt="Choose:"):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_CHOICE,
        choice=AuthoredChoice(choice_id=choice_id, prompt=prompt, options=options),
    )


def _media_item(item_id="item_m", asset_id="asset_media"):
    return ContentItem(item_id=item_id, kind=CONTENT_KIND_MEDIA, media=MediaReference(asset_id=asset_id))


def _slide(slide_id="slide_1", items=(), background=None):
    return Slide(slide_id=slide_id, content_items=items, background=background)


def _card(card_id="card_a", slides=None, connections=()):
    return Card(card_id=card_id, slides=slides if slides is not None else (_slide(),),
                connections=connections)


def _project(cards, start):
    return Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=cards, start_card_id=start)


def _conn(connection_id, target, label=None, choice_id=None):
    return CardConnection(connection_id=connection_id, target_card_id=target, label=label, choice_id=choice_id)


def _membership(scene_id, card_ids, location_id="loc_x", content_rating="pg"):
    return SceneMembership(
        scene_id=scene_id, card_ids=tuple(card_ids), location_id=location_id,
        content_rating=content_rating,
    )


def _config(scenes, transitions=()):
    return ProjectionConfig(scenes=tuple(scenes), supported_scene_transitions=tuple(transitions))


def _body_entries(result, scene_index=0):
    return result.scene_bodies[scene_index].entries


def test_t01_projection_uses_author_order():
    card_a = _card("card_a", slides=(
        _slide("slide_1", items=(_text_item("item_1", "one"), _text_item("item_2", "two"))),
        _slide("slide_2", items=(_text_item("item_3", "three"),)),
    ))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    entries = _body_entries(project_scenes(project, config))
    assert [e.entry_id for e in entries] == [
        "card_a.slide_1.item_1", "card_a.slide_1.item_2", "card_a.slide_2.item_3",
    ]


def test_t02_one_card_multiple_slides():
    card = _card("card_a", slides=(
        _slide("slide_1", items=(_text_item("item_1", "a"),)),
        _slide("slide_2", items=(_text_item("item_2", "b"),)),
        _slide("slide_3", items=(_text_item("item_3", "c"),)),
    ))
    project = _project((card,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    entries = _body_entries(project_scenes(project, config))
    assert [e.entry_id for e in entries] == [
        "card_a.slide_1.item_1", "card_a.slide_2.item_2", "card_a.slide_3.item_3",
    ]
    assert len(entries) == 3


def test_t03_several_cards_mapped_into_one_scene():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_c", "c"),)),))
    project = _project((card_a, card_b, card_c), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b", "card_c")),))
    result = project_scenes(project, config)
    assert len(result.scene_bodies) == 1
    entries = _body_entries(result)
    assert [e.entry_id for e in entries] == [
        "card_a.slide_1.item_a", "card_b.slide_1.item_b", "card_c.slide_1.item_c",
    ]


def test_t04_stable_entry_identities():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "a"),)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    first = project_scenes(project, config)
    second = project_scenes(project, config)
    assert [e.entry_id for e in _body_entries(first)] == [
        e.entry_id for e in _body_entries(second)
    ]
    assert _body_entries(first)[0].entry_id == "card_a.slide_1.item_1"


def test_t05_explicit_linear_continuation():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_b"),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b")),))
    entries = _body_entries(project_scenes(project, config))
    last_a = entries[0]
    assert isinstance(last_a, TextEntry)
    assert last_a.next_target is not None
    assert last_a.next_target.target_kind == TARGET_KIND_ENTRY
    assert last_a.next_target.target_id == "card_b.slide_1.item_b"


def test_t06_valid_authored_choice_and_branching():
    choice = _choice_item("item_ch", "ch_1", options=(
        ChoiceOption(option_id="opt_1", label="Left", target_connection_id="conn_1"),
        ChoiceOption(option_id="opt_2", label="Right", target_connection_id="conn_2"),
    ))
    card_a = _card("card_a", slides=(_slide("slide_1", items=(choice,)),),
                   connections=(
                       _conn("conn_1", "card_b", choice_id="ch_1"),
                       _conn("conn_2", "card_c", choice_id="ch_1"),
                   ))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_c", "c"),)),))
    project = _project((card_a, card_b, card_c), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b", "card_c")),))
    entries = _body_entries(project_scenes(project, config))
    choice_entry = entries[0]
    assert isinstance(choice_entry, ChoiceEntry)
    assert [o.option_id for o in choice_entry.options] == ["opt_1", "opt_2"]
    assert choice_entry.options[0].target.target_kind == TARGET_KIND_ENTRY
    assert choice_entry.options[0].target.target_id == "card_b.slide_1.item_b"
    assert choice_entry.options[1].target.target_id == "card_c.slide_1.item_c"


def test_t07_reject_dangling_targets():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_missing"),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    with pytest.raises(ProjectionError):
        project_scenes(project, config)


def test_t08_reject_duplicate_card_membership():
    with pytest.raises(ProjectionError):
        ProjectionConfig(scenes=(
            _membership("scene_1", ("card_a",)),
            _membership("scene_2", ("card_a",)),
        ))


def test_t09_correct_valid_start_position():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b")),))
    result = project_scenes(project, config)
    assert result.start_scene_id == "scene_1"
    assert result.scene_order == ("scene_1",)


def test_t10_reject_middle_of_scene_start():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_b")  # start is the middle card
    config = _config((_membership("scene_1", ("card_a", "card_b")),))
    with pytest.raises(ProjectionError):
        project_scenes(project, config)


def test_t11_supported_cross_scene_continuation():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_b"),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((
        _membership("scene_1", ("card_a",)),
        _membership("scene_2", ("card_b",)),
    ), transitions=(("scene_1", "scene_2"),))
    result = project_scenes(project, config)
    last_a = result.scene_bodies[0].entries[-1]
    assert last_a.next_target.target_kind == TARGET_KIND_SCENE
    assert last_a.next_target.target_id == "scene_2"


def test_t12_reject_cross_scene_entry_target():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_c"),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_c", "c"),)),))
    project = _project((card_a, card_b, card_c), "card_a")
    config = _config((
        _membership("scene_1", ("card_a",)),
        _membership("scene_2", ("card_b", "card_c")),
    ), transitions=(("scene_1", "scene_2"),))
    with pytest.raises(UnsupportedProjectionError):
        project_scenes(project, config)


def test_t13_complete_utterance_text_preserved():
    text = "Hello there."
    utt = _utt("utt_a", text=text, speakers=("kira",), portions=(
        DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5),
        DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12),
    ))
    item = ContentItem(item_id="item_1", kind=CONTENT_KIND_TEXT, utterance=utt)
    card_a = _card("card_a", slides=(_slide("slide_1", items=(item,)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    entry = _body_entries(project_scenes(project, config))[0]
    assert isinstance(entry, TextEntry)
    assert entry.text == "Hello there."


def test_t14_display_portion_metadata_not_silently_lost():
    text = "Hello there."
    utt = _utt("utt_a", text=text, speakers=("kira",), portions=(
        DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5,
                       overrides=(SpeakerOverride(character_id="kira", emotion="calm"),)),
        DisplayPortion(portion_id="por_2", start_offset=5, end_offset=12,
                       overrides=(SpeakerOverride(character_id="kira", emotion="warm"),)),
    ))
    item = ContentItem(item_id="item_1", kind=CONTENT_KIND_TEXT, utterance=utt)
    card_a = _card("card_a", slides=(_slide("slide_1", items=(item,)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    result = project_scenes(project, config)

    # The accepted SceneBody entry does NOT carry portion metadata.
    entry = result.scene_bodies[0].entries[0]
    assert isinstance(entry, TextEntry)
    assert entry.text == text
    assert not hasattr(entry, "portions")

    # The metadata is preserved in a deterministic, hash-verifiable sidecar.
    assert len(result.portion_manifests) == 1
    manifest = result.portion_manifests[0]
    assert manifest.utterance_id == "utt_a"
    assert manifest.text == text
    assert [p.portion_id for p in manifest.portions] == ["por_1", "por_2"]
    assert [p.start_offset for p in manifest.portions] == [0, 5]
    assert [p.end_offset for p in manifest.portions] == [5, 12]
    assert manifest.portions[0].overrides[0].emotion == "calm"
    assert manifest.portions[1].overrides[0].emotion == "warm"
    assert manifest.content_hash != ""
    assert len(manifest.content_hash) == 64


def test_t15_unsupported_media_and_presentation_error():
    media_card = _card("card_a", slides=(_slide("slide_1", items=(_media_item("item_m"),)),))
    project = _project((media_card,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    with pytest.raises(UnsupportedProjectionError):
        project_scenes(project, config)

    group = ContentItem(
        item_id="item_1", kind=CONTENT_KIND_TEXT,
        utterance=_utt("utt_g", "Together", speakers=("kira", "marina")),
    )
    group_card = _card("card_a", slides=(_slide("slide_1", items=(group,)),))
    project2 = _project((group_card,), "card_a")
    with pytest.raises(UnsupportedProjectionError):
        project_scenes(project2, config)

    bg = _slide("slide_1", items=(_text_item("item_1", "a"),),
                background=MediaReference(relative_path="images/bg.png"))
    bg_card = _card("card_a", slides=(bg,))
    project3 = _project((bg_card,), "card_a")
    with pytest.raises(UnsupportedProjectionError):
        project_scenes(project3, config)


def test_background_projects_to_visual_change():
    bg = MediaReference(asset_id="kira_yoga_hall")
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "a"),),
                                            background=bg),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    entries = _body_entries(project_scenes(project, config))
    assert isinstance(entries[0], VisualChangeEvent)
    assert entries[0].asset_id == "kira_yoga_hall"


def test_t16_equivalent_inputs_produce_identical_output():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_b"),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b")),))

    first = project_scenes(project, config)
    second = project_scenes(project, config)
    assert [b.to_dict() for b in first.scene_bodies] == [b.to_dict() for b in second.scene_bodies]
    assert [m.to_dict() for m in first.portion_manifests] == [
        m.to_dict() for m in second.portion_manifests
    ]
    assert first.scene_order == second.scene_order
    assert first.start_scene_id == second.start_scene_id


def test_t17_source_project_is_not_mutated():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))
    before = project.to_dict()
    project_scenes(project, config)
    assert project.to_dict() == before


def test_t18_result_uses_valid_ordered_ass():
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "a"),)),),
                   connections=(_conn("conn_1", "card_b"),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b")),))
    result = project_scenes(project, config)

    body = result.scene_bodies[0]
    ass = build_ordered_ass(
        body, ass_id="ass_sc1_1", version=1, source_ref="proj_alpha",
        source_hash="0" * 64,
    )
    assert ass.schema_version == "ass/0.2"
    # Round-trip through the existing canonical store validators.
    parsed = parse_ordered_ass(serialize_ordered_ass(ass))
    assert parsed.scene_id == body.scene_id
    assert [e.entry_id for e in parsed.ordered_flow] == [e.entry_id for e in body.entries]
    assert parsed.content_hash == ass.content_hash


def test_vertical_example_three_cards_choice_two_continuations():
    intro = _text_item("item_intro", "You reach a fork.")
    choice = _choice_item("item_ch", "ch_1", options=(
        ChoiceOption(option_id="opt_left", label="Go left", target_connection_id="conn_left"),
        ChoiceOption(option_id="opt_right", label="Go right", target_connection_id="conn_right"),
    ))
    card_a = _card("card_a", slides=(
        _slide("slide_1", items=(intro,)),
        _slide("slide_2", items=(choice,)),
    ), connections=(
        _conn("conn_left", "card_b", label="Left", choice_id="ch_1"),
        _conn("conn_right", "card_c", label="Right", choice_id="ch_1"),
    ))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "You went left."),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_c", "You went right."),)),))
    project = _project((card_a, card_b, card_c), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b", "card_c")),))
    result = project_scenes(project, config)

    assert len(result.scene_bodies) == 1
    entries = result.scene_bodies[0].entries
    assert [e.entry_id for e in entries] == [
        "card_a.slide_1.item_intro",
        "card_a.slide_2.item_ch",
        "card_b.slide_1.item_b",
        "card_c.slide_1.item_c",
    ]

    # Two slides inside one card (intro slide + choice slide) both present.
    assert isinstance(entries[0], TextEntry)
    assert entries[0].presentation == TEXT_PRESENTATION_NARRATIVE
    choice_entry = entries[1]
    assert isinstance(choice_entry, ChoiceEntry)
    assert len(choice_entry.options) == 2

    # Actual target semantics: option targets resolve to the branch cards' entries.
    assert choice_entry.options[0].display_text == "Go left"
    assert choice_entry.options[0].target.target_kind == TARGET_KIND_ENTRY
    assert choice_entry.options[0].target.target_id == "card_b.slide_1.item_b"
    assert choice_entry.options[1].display_text == "Go right"
    assert choice_entry.options[1].target.target_id == "card_c.slide_1.item_c"

    # The two continuations are terminal branches (explicit END, no silent fallthrough).
    assert entries[2].next_target is not None
    assert entries[2].next_target.target_kind == TARGET_KIND_END
    assert entries[3].next_target is not None
    assert entries[3].next_target.target_kind == TARGET_KIND_END

    # Whole projected flow is acceptance-complete and projects to OrderedASS.
    ass = build_ordered_ass(
        result.scene_bodies[0], ass_id="ass_fork_1", version=1,
        source_ref="proj_alpha", source_hash="0" * 64,
    )
    assert [e.entry_id for e in ass.ordered_flow] == [e.entry_id for e in entries]


def test_background_change_after_choice_is_rejected():
    # A background-only Slide appearing after an authored CHOICE is unreachable
    # and must fail closed with a diagnostic that names the real problem.
    choice = _choice_item("item_ch", "ch_1", options=(
        ChoiceOption(option_id="opt_1", label="Left", target_connection_id="conn_1"),
    ))
    card_a = _card(
        "card_a",
        slides=(
            _slide("slide_1", items=(choice,)),
            _slide("slide_2", items=(), background=MediaReference(asset_id="bg_later")),
        ),
        connections=(_conn("conn_1", "card_b", choice_id="ch_1"),),
    )
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "b"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((_membership("scene_1", ("card_a", "card_b")),))

    with pytest.raises(ProjectionError, match="content after a CHOICE"):
        project_scenes(project, config)





