#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.2 Scenario Authoring local W1 persistence tests (T01-T16 + vertical proof)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CHARACTER_PROVENANCE_MANUAL,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_TEXT,
    AuthoredChoice,
    Card,
    CardConnection,
    CharacterReference,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    Project,
    ProjectStore,
    ScenarioAuthoringCorruptionError,
    ScenarioAuthoringNotFoundError,
    ScenarioAuthoringRecoveryError,
    ScenarioAuthoringStorageError,
    ScenarioAuthoringValidationError,
    Slide,
    SpeakerOverride,
    Utterance,
    project_from_dict,
)

_SCHEMA = SCENARIO_AUTHORING_SCHEMA_VERSION


def _full_project() -> Project:
    """Build a complete, consistent project:

    Project -> two connected Cards -> Slides -> complete Utterance split into
    Display Portions (with per-speaker portrait/emotion overrides) -> saveable
    authored content.
    """
    text = "Hello there, Kira."
    utt = Utterance(
        utterance_id="utt_hello",
        text=text,
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                portion_id="por_1",
                start_offset=0,
                end_offset=5,
                overrides=(
                    SpeakerOverride(
                        character_id="kira",
                        portrait=MediaReference(asset_id="asset_portrait_kira"),
                        emotion="neutral",
                    ),
                ),
            ),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=len(text)),
        ),
    )
    item = ContentItem(item_id="item_hello", kind=CONTENT_KIND_TEXT, utterance=utt)
    slide_a = Slide(slide_id="slide_a1", content_items=(item,))

    choice = AuthoredChoice(
        choice_id="ch_branch",
        prompt="Go on?",
        options=(ChoiceOption(option_id="opt_yes", label="Yes"),),
    )
    item_b = ContentItem(item_id="item_choice", kind=CONTENT_KIND_CHOICE, choice=choice)
    slide_b = Slide(slide_id="slide_b1", content_items=(item_b,))

    card_a = Card(
        card_id="card_a",
        slides=(slide_a,),
        connections=(CardConnection(connection_id="conn_ab", target_card_id="card_b", label="Next"),),
    )
    card_b = Card(card_id="card_b", slides=(slide_b,))

    return Project(
        schema_version=_SCHEMA,
        project_id="proj_alpha",
        cards=(card_a, card_b),
        start_card_id="card_a",
        characters=(CharacterReference(character_id="kira", provenance=CHARACTER_PROVENANCE_MANUAL, name="Kira"),),
    )


def _inconsistent_project() -> Project:
    """A project with a dangling connection (fails validate_project)."""
    card = Card(
        card_id="card_a",
        slides=(Slide(slide_id="slide_1"),),
        connections=(CardConnection(connection_id="conn_bad", target_card_id="card_missing"),),
    )
    return Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card,), start_card_id="card_a")


def test_t01_initial_save_and_reopen(tmp_path):
    store = ProjectStore(tmp_path)
    project = _full_project()
    assert not store.exists()
    store.save(project)
    assert store.exists()
    assert store.load() == project


def test_t02_two_cards_preserve_ids_and_ordering(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    loaded = store.load()
    assert loaded.card_ids() == ("card_a", "card_b")
    assert loaded.card_by_id("card_b").card_id == "card_b"


def test_t03_multiple_slides_survive(tmp_path):
    card = Card(card_id="card_a", slides=(Slide("slide_1"), Slide("slide_2"), Slide("slide_3")))
    project = Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card,), start_card_id="card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    assert store.load().card_by_id("card_a").slide_ids() == ("slide_1", "slide_2", "slide_3")


def test_t04_complete_utterance_text_exact(tmp_path):
    text = "  Line one.\n\tLine two.  "
    item = ContentItem(
        item_id="item_1",
        kind=CONTENT_KIND_TEXT,
        utterance=Utterance(utterance_id="utt_a", text=text),
    )
    card = Card(card_id="card_a", slides=(Slide(slide_id="slide_1", content_items=(item,)),))
    project = Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card,), start_card_id="card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    loaded_utt = store.load().card_by_id("card_a").slides[0].content_items[0].utterance
    assert loaded_utt.whole_text() == text


def test_t05_display_portion_boundaries_exact(tmp_path):
    text = "Hello there."
    utt = Utterance(
        utterance_id="utt_a",
        text=text,
        portions=(DisplayPortion("por_1", 0, 5), DisplayPortion("por_2", 5, len(text))),
    )
    item = ContentItem(item_id="item_1", kind=CONTENT_KIND_TEXT, utterance=utt)
    card = Card(card_id="card_a", slides=(Slide(slide_id="slide_1", content_items=(item,)),))
    project = Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card,), start_card_id="card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    loaded_utt = store.load().card_by_id("card_a").slides[0].content_items[0].utterance
    assert [(p.portion_id, p.start_offset, p.end_offset) for p in loaded_utt.portions] == [
        ("por_1", 0, 5),
        ("por_2", 5, len(text)),
    ]


def test_t06_portrait_emotion_overrides_survive(tmp_path):
    text = "Hello there."
    portrait = MediaReference(asset_id="asset_portrait_kira")
    utt = Utterance(
        utterance_id="utt_a",
        text=text,
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                "por_1", 0, 5,
                overrides=(SpeakerOverride("kira", portrait=portrait, emotion="neutral"),),
            ),
            DisplayPortion("por_2", 5, len(text)),
        ),
    )
    item = ContentItem(item_id="item_1", kind=CONTENT_KIND_TEXT, utterance=utt)
    card = Card(card_id="card_a", slides=(Slide(slide_id="slide_1", content_items=(item,)),))
    project = Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card,), start_card_id="card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    ov = store.load().card_by_id("card_a").slides[0].content_items[0].utterance.portions[0].overrides[0]
    assert ov.character_id == "kira"
    assert ov.portrait == portrait
    assert ov.emotion == "neutral"


def test_t07_card_connections_survive(tmp_path):
    card_a = Card(
        card_id="card_a",
        slides=(Slide("slide_1"),),
        connections=(CardConnection("conn_ab", target_card_id="card_b", label="Next"),),
    )
    card_b = Card(card_id="card_b", slides=(Slide("slide_1"),))
    project = Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=(card_a, card_b), start_card_id="card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    loaded = store.load().card_by_id("card_a")
    assert [(c.connection_id, c.target_card_id, c.label) for c in loaded.connections] == [
        ("conn_ab", "card_b", "Next")
    ]


def test_t08_start_card_id_survives(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    assert store.load().start_card_id == "card_a"


def test_t09_independent_card_save_does_not_alter_unrelated(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    card_b_path = tmp_path / "cards" / "card_b.json"
    before = card_b_path.read_text(encoding="utf-8")
    modified_a = Card(
        card_id="card_a",
        slides=(_full_project().card_by_id("card_a").slides[0], Slide("slide_a2")),
        connections=_full_project().card_by_id("card_a").connections,
    )
    store.save_card(modified_a)
    assert card_b_path.read_text(encoding="utf-8") == before
    loaded = store.load()
    assert loaded.card_by_id("card_a").slide_ids() == ("slide_a1", "slide_a2")


def test_t10_failed_save_preserves_last_good(tmp_path):
    store = ProjectStore(tmp_path)
    good = _full_project()
    store.save(good)
    with pytest.raises(ScenarioAuthoringValidationError):
        store.save(_inconsistent_project())
    assert store.load() == good


def test_t11_missing_card_detected(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    (tmp_path / "cards" / "card_b.json").unlink()
    with pytest.raises(ScenarioAuthoringNotFoundError):
        store.load()


def test_t12_malformed_json_rejected(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    (tmp_path / "cards" / "card_a.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ScenarioAuthoringCorruptionError):
        store.load()


def test_t13_invalid_internal_paths_rejected(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    index_path = tmp_path / "project.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["cards"] = [{"card_id": "../evil", "content_hash": "0" * 64}]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ScenarioAuthoringStorageError):
        store.load()


def test_t14_corrupted_or_mismatched_content_detected(tmp_path):
    store = ProjectStore(tmp_path)
    store.save(_full_project())
    # (a) content tampered -> hash mismatch
    card_path = tmp_path / "cards" / "card_a.json"
    data = json.loads(card_path.read_text(encoding="utf-8"))
    data["slides"][0]["content_items"][0]["utterance"]["text"] = "TAMPERED"
    card_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioAuthoringCorruptionError):
        store.load()
    # (b) card file claims a different card_id -> identity mismatch
    store2 = ProjectStore(tmp_path / "b")
    store2.save(_full_project())
    path_b = tmp_path / "b" / "cards" / "card_b.json"
    data_b = json.loads(path_b.read_text(encoding="utf-8"))
    data_b["card_id"] = "card_a"
    path_b.write_text(json.dumps(data_b), encoding="utf-8")
    with pytest.raises(ScenarioAuthoringCorruptionError):
        store2.load()


def test_t15_recovery_uses_previous_good_without_inventing(tmp_path):
    store = ProjectStore(tmp_path)
    p1 = _full_project()
    store.save(p1)
    assert not store.has_recovery()

    modified = Project(
        schema_version=_SCHEMA,
        project_id="proj_alpha",
        cards=(p1.card_by_id("card_a"), Card(card_id="card_b", slides=(Slide("slide_b2"),))),
        start_card_id="card_a",
        characters=p1.characters,
    )
    store.save(modified)
    assert store.has_recovery()

    # Corrupt the main state: delete a Card file.
    (tmp_path / "cards" / "card_a.json").unlink()
    with pytest.raises(ScenarioAuthoringNotFoundError):
        store.load()

    recovered = store.recover()
    assert recovered == p1
    assert store.load() == p1


def test_t16_se11_serialization_compatible(tmp_path):
    project = _full_project()
    assert project_from_dict(project.to_dict()) == project
    store = ProjectStore(tmp_path)
    store.save(project)
    index = json.loads((tmp_path / "project.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == "scenario_authoring_storage/0.1"
    assert index["authoring_schema_version"] == _SCHEMA
    stored_card = json.loads((tmp_path / "cards" / "card_a.json").read_text(encoding="utf-8"))
    assert stored_card == project.card_by_id("card_a").to_dict()


def test_vertical_local_round_trip(tmp_path):
    # Create Project -> two connected Cards -> Slides -> complete Utterance ->
    # Display Portions.
    text = "Hello there, Kira."
    utt = Utterance(
        utterance_id="utt_hello",
        text=text,
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                "por_1", 0, 5,
                overrides=(SpeakerOverride("kira", portrait=MediaReference(asset_id="asset_portrait_kira"), emotion="neutral"),),
            ),
            DisplayPortion("por_2", 5, len(text)),
        ),
    )
    item = ContentItem(item_id="item_hello", kind=CONTENT_KIND_TEXT, utterance=utt)
    card_a = Card(
        card_id="card_a",
        slides=(Slide(slide_id="slide_a1", content_items=(item,)),),
        connections=(CardConnection("conn_ab", target_card_id="card_b", label="Next"),),
    )
    card_b = Card(card_id="card_b", slides=(Slide("slide_b1"),))
    project = Project(
        schema_version=_SCHEMA,
        project_id="proj_alpha",
        cards=(card_a, card_b),
        start_card_id="card_a",
        characters=(CharacterReference("kira", CHARACTER_PROVENANCE_MANUAL, name="Kira"),),
    )

    store = ProjectStore(tmp_path)
    store.save(project)

    # Discard the original in-memory Python objects.
    del project, card_a, card_b, utt, item

    # Reopen from disk and compare the complete model representation.
    reopened = store.load()
    assert reopened.card_ids() == ("card_a", "card_b")
    assert reopened.start_card_id == "card_a"
    card_a2 = reopened.card_by_id("card_a")
    assert card_a2.slide_ids() == ("slide_a1",)
    utt2 = card_a2.slides[0].content_items[0].utterance
    assert utt2.whole_text() == text
    assert [(p.portion_id, p.start_offset, p.end_offset) for p in utt2.portions] == [
        ("por_1", 0, 5),
        ("por_2", 5, len(text)),
    ]
    assert utt2.portions[0].overrides[0].portrait == MediaReference(asset_id="asset_portrait_kira")
    assert utt2.portions[0].overrides[0].emotion == "neutral"
    assert [(c.connection_id, c.target_card_id) for c in card_a2.connections] == [("conn_ab", "card_b")]
    assert reopened.characters == (CharacterReference("kira", CHARACTER_PROVENANCE_MANUAL, name="Kira"),)
