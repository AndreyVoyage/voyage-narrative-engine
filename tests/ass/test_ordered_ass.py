#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OrderedASS (ass/0.2) model + builder + hash tests."""

from __future__ import annotations

import pytest

from services.ass import (
    ASS,
    ASSInvariantError,
    LEGACY_ASS_SCHEMA_VERSION,
    ORDERED_ASS_SCHEMA_VERSION,
    OrderedASS,
    Participant as AssParticipant,
    Provenance,
    build_ordered_ass,
)
from services.scene_body import (
    AUTHORING_SCHEMA_VERSION,
    ChoiceEntry,
    ChoiceOption,
    ChoiceTarget,
    Participant,
    SceneBody,
    TextEntry,
    VisualChangeEvent,
)

SOURCE_HASH = "0" * 64


def _narrative(entry_id="e1", text="Kira enters.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="NARRATIVE", text=text)


def _choice(entry_id="c1", options=("o1", "o2")) -> ChoiceEntry:
    return ChoiceEntry(
        entry_id=entry_id,
        prompt="What next?",
        options=tuple(
            ChoiceOption(option_id=oid, display_text=f"Option {oid}",
                         target=ChoiceTarget(target_kind="SCENE", target_id=f"SC_90{oid[-1]}"))
            for oid in options
        ),
    )


def _visual(entry_id="v1") -> VisualChangeEvent:
    return VisualChangeEvent(entry_id=entry_id, operation="SET", asset_id="kira_yoga_hall")


def _body(**overrides) -> SceneBody:
    fields = dict(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id="SC_900",
        scene_title="Yoga warm-up",
        location_id="yoga_hall",
        participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
        content_rating="PG",
        entries=(_narrative(), _choice(), _visual()),
    )
    fields.update(overrides)
    return SceneBody(**fields)


def _build(body=None, **kwargs) -> OrderedASS:
    kwargs.setdefault("ass_id", "ass_sc900_1")
    kwargs.setdefault("version", 1)
    kwargs.setdefault("source_ref", "scenes/SC_900.json")
    kwargs.setdefault("source_hash", SOURCE_HASH)
    return build_ordered_ass(body if body is not None else _body(), **kwargs)


def _legacy_ass(schema_version="ass/0.1") -> ASS:
    return ASS(
        schema_version=schema_version,
        ass_id="ass_x",
        version=1,
        scene_id="SC_900",
        location_id="yoga_hall",
        participants=(AssParticipant("KIRA", "protagonist", True),),
        ordered_beats=(),
        content_rating="PG",
        provenance=Provenance(
            source_kind="scenario_json_v2_import",
            source_ref="scenarios/x.v2.json",
            source_hash=SOURCE_HASH,
            source_schema_version="2.0",
        ),
        content_hash=SOURCE_HASH,
    )


# ---------------------------------------------------------------------------
# Projection / envelope
# ---------------------------------------------------------------------------

def test_build_ordered_ass_schema() -> None:
    ass = _build()
    assert ass.schema_version == "ass/0.2"
    assert isinstance(ass, OrderedASS)


def test_scene_id_and_version_preserved() -> None:
    ass = _build(version=7)
    assert ass.scene_id == "SC_900"
    assert ass.version == 7


def test_location_comes_from_body() -> None:
    ass = _build(_body(location_id="gym_night"))
    assert ass.location_id == "gym_night"


def test_participants_normalized() -> None:
    ass = _build()
    assert [(p.character_id, p.role, p.present) for p in ass.participants] == [
        ("KIRA", "protagonist", True)
    ]


def test_ordered_flow_reuses_entries_in_order() -> None:
    ass = _build(_body(entries=(_narrative("e1"), _choice("c1"), _visual("v1"))))
    assert [e.entry_id for e in ass.ordered_flow] == ["e1", "c1", "v1"]


def test_no_parallel_ordered_beats_payload() -> None:
    ass = _build()
    assert "ordered_beats" not in ass.to_dict()
    assert "ordered_flow" in ass.to_dict()


def test_provenance_binds_source_schema_and_hash() -> None:
    ass = _build()
    assert ass.provenance.source_schema_version == AUTHORING_SCHEMA_VERSION
    assert ass.provenance.source_hash == SOURCE_HASH


def test_deterministic_projection() -> None:
    a = _build()
    b = _build()
    assert a.content_hash == b.content_hash
    assert a.to_dict() == b.to_dict()


def test_no_semantic_loss() -> None:
    body = _body(entries=(_narrative(), _choice(), _visual()))
    ass = _build(body)
    assert ass.scene_title == "Yoga warm-up"
    assert ass.content_rating == "PG"
    assert ass.location_id == "yoga_hall"
    assert len(ass.ordered_flow) == 3


# ---------------------------------------------------------------------------
# Completeness gates
# ---------------------------------------------------------------------------

def test_incomplete_body_rejected() -> None:
    with pytest.raises(ASSInvariantError):
        _build(_body(location_id=None))


def test_empty_ordered_flow_impossible() -> None:
    body = _body(entries=())
    with pytest.raises(ASSInvariantError):
        build_ordered_ass(
            body,
            ass_id="ass_x",
            version=1,
            source_ref="x",
            source_hash=SOURCE_HASH,
        )


# ---------------------------------------------------------------------------
# Schema isolation (legacy vs ordered)
# ---------------------------------------------------------------------------

def test_legacy_ass_cannot_claim_ass_0_2() -> None:
    with pytest.raises(ASSInvariantError):
        _legacy_ass("ass/0.2")


def test_legacy_ass_defaults_to_ass_0_1() -> None:
    assert _legacy_ass().schema_version == "ass/0.1"
    assert LEGACY_ASS_SCHEMA_VERSION == "ass/0.1"
    assert ORDERED_ASS_SCHEMA_VERSION == "ass/0.2"


# ---------------------------------------------------------------------------
# Hash semantics
# ---------------------------------------------------------------------------

def test_hash_covers_schema_version() -> None:
    a = _build()
    body = _body()
    ass = build_ordered_ass(body, ass_id="ass_x", version=1, source_ref="x", source_hash=SOURCE_HASH)
    assert a.content_hash == ass.content_hash


def test_reordering_entries_changes_hash() -> None:
    a = _build(_body(entries=(_narrative("e1"), _choice("c1"))))
    b = _build(_body(entries=(_choice("c1"), _narrative("e1"))))
    assert a.content_hash != b.content_hash


def test_reordering_options_changes_hash() -> None:
    a = _build(_body(entries=(_choice("c1", options=("o1", "o2")),)))
    b = _build(_body(entries=(_choice("c1", options=("o2", "o1")),)))
    assert a.content_hash != b.content_hash


def test_text_change_changes_hash() -> None:
    a = _build(_body(entries=(_narrative("e1", "Hello."),)))
    b = _build(_body(entries=(_narrative("e1", "Goodbye."),)))
    assert a.content_hash != b.content_hash


def test_visual_change_changes_hash() -> None:
    a = _build(_body(entries=(VisualChangeEvent(entry_id="v1", operation="SET", asset_id="kira_yoga_hall"),)))
    b = _build(_body(entries=(VisualChangeEvent(entry_id="v1", operation="CLEAR", asset_id=None),)))
    assert a.content_hash != b.content_hash


def test_hash_excludes_envelope_fields() -> None:
    a = _build(ass_id="ass_a", version=1, author="alice", created_at="2020-01-01T00:00:00Z")
    b = _build(ass_id="ass_b", version=99, author="bob", created_at="2099-01-01T00:00:00Z", supersedes="ass_a")
    assert a.content_hash == b.content_hash


def test_choice_prompt_change_changes_hash() -> None:
    a = _build(_body(entries=(ChoiceEntry(entry_id="c1", prompt="A", options=(_opt("o1"),)),)))
    b = _build(_body(entries=(ChoiceEntry(entry_id="c1", prompt="B", options=(_opt("o1"),)),)))
    assert a.content_hash != b.content_hash


def test_option_text_change_changes_hash() -> None:
    a = _build(_body(entries=(ChoiceEntry(entry_id="c1", options=(_opt("o1", "Alpha"),)),)))
    b = _build(_body(entries=(ChoiceEntry(entry_id="c1", options=(_opt("o1", "Beta"),)),)))
    assert a.content_hash != b.content_hash


def test_option_target_change_changes_hash() -> None:
    a = _build(_body(entries=(ChoiceEntry(entry_id="c1", options=(_opt("o1", target_id="SC_901"),)),)))
    b = _build(_body(entries=(ChoiceEntry(entry_id="c1", options=(_opt("o1", target_id="SC_902"),)),)))
    assert a.content_hash != b.content_hash


def test_transition_change_changes_hash() -> None:
    a = _build(_body(entries=(VisualChangeEvent(entry_id="v1", operation="SET", asset_id="kira_yoga_hall", transition="fade"),)))
    b = _build(_body(entries=(VisualChangeEvent(entry_id="v1", operation="SET", asset_id="kira_yoga_hall", transition="cut"),)))
    assert a.content_hash != b.content_hash


def _opt(option_id, display_text="Continue", target_id="SC_901") -> ChoiceOption:
    return ChoiceOption(
        option_id=option_id,
        display_text=display_text,
        target=ChoiceTarget(target_kind="SCENE", target_id=target_id),
    )
