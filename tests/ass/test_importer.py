#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ASS v0 importer tests -- normalization, source mapping, provenance,
branch selection, and the AI/source-inference boundary."""

from __future__ import annotations

from typing import Any

import pytest

from services.ass import ASSNormalizationError, ASSSourceError, import_scene


def _import(
    source: dict[str, Any],
    *,
    ass_id: str = "ass_test_1",
    version: int = 1,
    location_id: str = "yoga_hall",
    source_ref: str = "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
    **kwargs,
):
    return import_scene(
        source,
        ass_id=ass_id,
        version=version,
        location_id=location_id,
        source_ref=source_ref,
        **kwargs,
    )


# --------------------------------------------------------------------------
# 1. valid V2 JSON -> valid ASS
# --------------------------------------------------------------------------


def test_valid_source_produces_ass(sc017_source):
    ass = _import(sc017_source, location_id="home")
    assert ass.schema_version == "ass/0.1"
    assert ass.version == 1
    assert ass.content_hash


# --------------------------------------------------------------------------
# 2. scene_id preserved ; 3. beat_id preserved ; 4. ordering ; 5. type preserved
# --------------------------------------------------------------------------


def test_scene_id_preserved(sc017_source):
    ass = _import(sc017_source, location_id="home")
    assert ass.scene_id == "SC_017"


def test_beat_id_type_order_preserved(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    assert [b.beat_id for b in ass.ordered_beats] == ["b1", "b2"]
    assert [b.type for b in ass.ordered_beats] == ["action", "action"]


# --------------------------------------------------------------------------
# 6. participants mapped correctly ; 7. present:false preserved
# --------------------------------------------------------------------------


def test_participants_mapped_and_present_false(sc017_source):
    ass = _import(sc017_source, location_id="home")
    by_id = {p.character_id: p for p in ass.participants}
    assert set(by_id) == {"kira", "yakov", "sergey"}
    assert by_id["kira"].role == "protagonist"
    assert by_id["kira"].present is True
    assert by_id["sergey"].present is False  # real SC_017 present:false case


# --------------------------------------------------------------------------
# 8. characters_in_frame absent ; 9. Character Canon absent ; 10. Location
#    Canon snapshot absent (structural/negative)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden",
    [
        "characters_in_frame",
        "canon_refs",
        "camera",
        "composition",
        "shot_type",
        "pose",
        "visual_summary",
        "negative_prompt",
        "visual_cue",
        "status",
        "model",
        "provider",
    ],
)
def test_downstream_fields_absent(synthetic_sc029_source, forbidden):
    ass = _import(synthetic_sc029_source)
    payload = ass.to_dict()
    assert forbidden not in payload
    # participants must not leak source display_name or state machine fields
    for participant in payload["participants"]:
        assert "display_name" not in participant
        assert "state_start" not in participant
        assert "state_end" not in participant


# --------------------------------------------------------------------------
# 11. temporary character override ; 12. temporary location override
# --------------------------------------------------------------------------


def test_character_state_override_supported(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        character_state_overrides={"alice": {"clothing": "sports top + leggings"}},
    )
    assert ass.character_state_overrides == {"alice": {"clothing": "sports top + leggings"}}


def test_character_state_override_absent_when_not_supplied(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    assert ass.character_state_overrides is None


def test_location_state_override_supported(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        location_state_overrides=[{"predicate": "lights", "value": "off"}],
    )
    assert [o.to_dict() for o in ass.location_state_overrides] == [
        {"predicate": "lights", "value": "off"}
    ]


# --------------------------------------------------------------------------
# 13. accepted emotion supported when explicitly supplied
# --------------------------------------------------------------------------


def test_accepted_state_populated_from_explicit_input(synthetic_sc029_source):
    ass = _import(
        synthetic_sc029_source,
        accepted_states={"b1": {"emotion": "focused calm"}},
    )
    b1 = next(b for b in ass.ordered_beats if b.beat_id == "b1")
    assert b1.accepted_state == {"emotion": "focused calm"}
    b2 = next(b for b in ass.ordered_beats if b.beat_id == "b2")
    assert b2.accepted_state is None


# --------------------------------------------------------------------------
# 25. source emotion is never auto-copied
# --------------------------------------------------------------------------


def test_source_emotion_never_autocopied(synthetic_sc029_source):
    # SC_029's b1 carries "emotion": "U5-выбор" (state-machine code).
    ass = _import(synthetic_sc029_source)
    b1 = next(b for b in ass.ordered_beats if b.beat_id == "b1")
    assert b1.accepted_state is None


# --------------------------------------------------------------------------
# 17. invalid scenario rejected (reuse validate_scene)
# 19. unknown/unsupported schema_version
# --------------------------------------------------------------------------


def test_invalid_source_rejected():
    with pytest.raises(ASSSourceError):
        import_scene(
            {"id": "not-a-real-scene"},
            ass_id="ass_x",
            version=1,
            location_id="x",
            source_ref="scenarios/x.v2.json",
        )


def test_bad_schema_version_rejected(synthetic_sc029_source):
    bad = dict(synthetic_sc029_source)
    bad["schema_version"] = "1.0"
    with pytest.raises(ASSSourceError):
        _import(bad)


def test_non_dict_source_rejected():
    with pytest.raises(ASSSourceError):
        _import("not a dict")  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 18. duplicate beat IDs rejected at the ASS layer (defense in depth)
# --------------------------------------------------------------------------


def test_duplicate_beat_id_rejected_at_ass_layer(synthetic_sc029_source, monkeypatch):
    # Bypass the shared source validator to prove the importer's own guard.
    import services.ass.importer as importer

    monkeypatch.setattr(importer, "validate_scene", lambda source: ([], []))
    dup = dict(synthetic_sc029_source)
    dup["entry_beats"] = list(synthetic_sc029_source["entry_beats"])
    dup["entry_beats"].append(dict(synthetic_sc029_source["entry_beats"][0]))
    with pytest.raises(ASSNormalizationError):
        _import(dup)


# --------------------------------------------------------------------------
# 20. Unicode/Russian content round-trips (real SC_017 fixture)
# --------------------------------------------------------------------------


def test_unicode_roundtrip(sc017_source):
    ass = _import(sc017_source, location_id="home")
    beat = ass.ordered_beats[0]
    expected = (
        "Телефон загорается новым сообщением от Сергея. "
        "Утренний разговор с Яковым ещё не успел стать привычкой."
    )
    assert beat.text == expected
    assert "Сергея" in beat.text


# --------------------------------------------------------------------------
# 21. source provenance is portable (repo-relative, no absolute path)
# --------------------------------------------------------------------------


def test_source_ref_is_repo_relative(sc017_source):
    ass = _import(sc017_source, location_id="home")
    assert ass.provenance.source_ref == "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json"
    assert ass.provenance.source_kind == "scenario_json_v2_import"
    assert ass.provenance.source_schema_version == "2.0"
    assert len(ass.provenance.source_hash) == 64


def test_absolute_source_ref_rejected(sc017_source):
    with pytest.raises(ASSNormalizationError):
        _import(
            sc017_source,
            location_id="home",
            source_ref="C:/DEV/scenarios/SCENARIO_017.json",
        )


# --------------------------------------------------------------------------
# 22. SC_017 import regression fixture (entry-beats-only + explicit branch)
# --------------------------------------------------------------------------


def test_sc017_entry_beats_only_default(sc017_source):
    ass = _import(sc017_source, location_id="home")
    assert [b.beat_id for b in ass.ordered_beats] == ["e1"]


def test_sc017_explicit_branch_selection(sc017_source):
    ass = _import(sc017_source, location_id="home", branch_id="1A")
    assert [b.beat_id for b in ass.ordered_beats] == [
        "e1",
        "1A-b1",
        "1A-b2",
        "1A-b3",
        "1A-b4",
        "1A-b5",
    ]


# --------------------------------------------------------------------------
# 23. pilot SC_029 works without real Canon facts
# 24. branch omission is not silently defaulted
# --------------------------------------------------------------------------


def test_sc029_synthetic_works_without_canon(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    assert ass.scene_id == "SC_029"
    assert ass.scene_title == "Yoga hall — treadmill warm-up"
    assert {p.character_id for p in ass.participants} == {"alice", "bob"}
    assert [b.beat_id for b in ass.ordered_beats] == ["b1", "b2"]


def test_branch_omission_not_defaulted(synthetic_sc029_source):
    ass = _import(synthetic_sc029_source)
    # No branch_id -> only entry_beats, never an arbitrary/first branch guess.
    assert [b.beat_id for b in ass.ordered_beats] == ["b1", "b2"]
    assert "1A-b1" not in [b.beat_id for b in ass.ordered_beats]


def test_unknown_branch_rejected(synthetic_sc029_source):
    with pytest.raises(ASSNormalizationError):
        _import(synthetic_sc029_source, branch_id="DOES_NOT_EXIST")


# --------------------------------------------------------------------------
# Required explicit inputs: location_id must be supplied
# --------------------------------------------------------------------------


def test_missing_location_id_rejected(synthetic_sc029_source):
    with pytest.raises(ASSNormalizationError):
        import_scene(
            synthetic_sc029_source,
            ass_id="ass_x",
            version=1,
            location_id="",
            source_ref="scenarios/x.v2.json",
        )