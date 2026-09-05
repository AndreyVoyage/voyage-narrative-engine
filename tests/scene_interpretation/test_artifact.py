#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scene Interpretation Artifact v0 tests -- source compatibility, status
gating, deep immutability, hash, serialization, and boundary."""

from __future__ import annotations

import dataclasses
import json

import pytest

from services.ass import (
    ASS,
    OrderedASS,
    Participant,
    Provenance as AssProvenance,
    build_ordered_ass,
)
from services.character_canon_bridge import CharacterCanonSnapshot, Provenance as CanonProvenance
from services.location_canon import LocationCanon
from services.scene_body import (
    AUTHORING_SCHEMA_VERSION,
    Participant as BodyParticipant,
    SceneBody,
    TextEntry,
)
from services.scene_interpretation import (
    CharacterStatusUnknownError,
    SceneInterpretationValidationError,
    build_scene_interpretation_artifact,
)


def _ass(scene_id="SC_TEST", location_id="yoga_hall", participants=("KIRA",), content_hash="ass_hash_000"):
    return ASS(
        schema_version="ass/0.1",
        ass_id="ass_test",
        version=1,
        scene_id=scene_id,
        location_id=location_id,
        participants=tuple(
            Participant(character_id=cid, role="protagonist", present=True)
            for cid in participants
        ),
        ordered_beats=(),
        content_rating="PG",
        provenance=AssProvenance(
            source_kind="test",
            source_ref="scenarios/SC_TEST.json",
            source_hash="ass_source_hash",
            source_schema_version="2.0",
        ),
        content_hash=content_hash,
    )


def _snapshot(character_id="KIRA", status="APPROVED_AS_CANON"):
    return CharacterCanonSnapshot(
        schema_version="character_canon/0.1",
        character_id=character_id,
        status=status,
        references=(),
        content_hash=f"snap_{character_id}_{status}",
        provenance=CanonProvenance(
            source_kind="character_canon_reference_presets",
            source_ref=f"AI_CHARACTERS/{character_id}/10_notes/{character_id}_REFERENCE_PRESETS.json",
            source_hash="snap_source_hash",
        ),
    )


def _location(location_id="yoga_hall", content_hash="loc_hash_000"):
    return LocationCanon(
        schema_version="location/0.1",
        location_id=location_id,
        tier="premium",
        scale=("small", "intimate"),
        identity=("yoga", "wellness"),
        palette=("warm",),
        fixed_features=(),
        content_hash=content_hash,
    )


PAYLOAD = {"mood": "warm", "notes": "synthetic interpretation"}


# ---------------------------------------------------------------------------
# A. Basic artifact
# ---------------------------------------------------------------------------


def test_basic_artifact():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED_AS_CANON")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.scene_id == "SC_TEST"
    assert artifact.ass_anchor.scene_id == "SC_TEST"
    assert artifact.ass_anchor.content_hash == "ass_hash_000"
    assert artifact.production_eligible is True


# ---------------------------------------------------------------------------
# B. ASS anchor + immutability of ASS
# ---------------------------------------------------------------------------


def test_ass_unchanged():
    ass = _ass()
    original = ass.to_dict()
    build_scene_interpretation_artifact(
        ass=ass,
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")],
        interpretation_payload=PAYLOAD,
    )
    assert ass.to_dict() == original


# ---------------------------------------------------------------------------
# C. Location compatibility
# ---------------------------------------------------------------------------


def test_location_mismatch_rejected():
    with pytest.raises(SceneInterpretationValidationError):
        build_scene_interpretation_artifact(
            ass=_ass(location_id="yoga_hall"),
            location=_location(location_id="gym_night"),
            character_snapshots=[_snapshot("KIRA", "APPROVED")],
            interpretation_payload=PAYLOAD,
        )


def test_location_exact_match_accepted():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(location_id="yoga_hall"),
        location=_location(location_id="yoga_hall", content_hash="loc_hash_000"),
        character_snapshots=[],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.location_anchor.location_id == "yoga_hall"
    assert artifact.location_anchor.content_hash == "loc_hash_000"


# ---------------------------------------------------------------------------
# D. Character participant compatibility
# ---------------------------------------------------------------------------


def test_non_participant_rejected():
    with pytest.raises(SceneInterpretationValidationError):
        build_scene_interpretation_artifact(
            ass=_ass(participants=("KIRA",)),
            location=_location(),
            character_snapshots=[_snapshot("SERGEY", "APPROVED")],
            interpretation_payload=PAYLOAD,
        )


def test_duplicate_character_rejected():
    with pytest.raises(SceneInterpretationValidationError):
        build_scene_interpretation_artifact(
            ass=_ass(),
            location=_location(),
            character_snapshots=[_snapshot("KIRA", "APPROVED"), _snapshot("KIRA", "APPROVED")],
            interpretation_payload=PAYLOAD,
        )


def test_fuzzy_case_mismatch_rejected():
    # 'kira' must not match participant 'KIRA' via fuzzy matching: it simply
    # fails participant check.
    with pytest.raises(SceneInterpretationValidationError):
        build_scene_interpretation_artifact(
            ass=_ass(participants=("KIRA",)),
            location=_location(),
            character_snapshots=[_snapshot("kira", "APPROVED")],
            interpretation_payload=PAYLOAD,
        )


# ---------------------------------------------------------------------------
# E/F. Status propagation + production eligibility
# ---------------------------------------------------------------------------


def test_pending_approval_draft_allowed():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "PENDING_APPROVAL")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.production_eligible is False
    anchor = artifact.character_anchors[0]
    assert anchor.status == "PENDING_APPROVAL"


def test_approved_production_eligible():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED_AS_CANON")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.production_eligible is True


def test_bare_approved_not_production_eligible():
    # Legacy bare APPROVED is known (parses) but must NOT grant production.
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.production_eligible is False


def test_approved_as_test_not_production_eligible():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED_AS_TEST")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.production_eligible is False


def test_mixed_status_not_eligible():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(participants=("KIRA", "OLGA")),
        location=_location(),
        character_snapshots=[
            _snapshot("KIRA", "APPROVED"),
            _snapshot("OLGA", "PENDING_APPROVAL"),
        ],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.production_eligible is False


def test_unknown_status_fails_closed():
    with pytest.raises(CharacterStatusUnknownError):
        build_scene_interpretation_artifact(
            ass=_ass(),
            location=_location(),
            character_snapshots=[_snapshot("KIRA", "SOME_FUTURE_STATUS")],
            interpretation_payload=PAYLOAD,
        )


# ---------------------------------------------------------------------------
# G. Deep immutability
# ---------------------------------------------------------------------------


def test_interpretation_payload_alias_severed():
    payload = {"mood": ["warm"]}
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[],
        interpretation_payload=payload,
    )
    payload["mood"].append("cold")
    assert "cold" not in artifact.interpretation_payload["mood"]


def test_payload_plain_mutation_does_not_affect_artifact():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[],
        interpretation_payload={"mood": "warm"},
    )
    stored = artifact.content_hash
    d = artifact.to_dict()
    d["interpretation_payload"]["mood"] = "cold"
    assert artifact.interpretation_payload["mood"] == "warm"
    assert artifact.content_hash == stored


def test_character_anchor_snapshot_immutable():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "PENDING_APPROVAL")],
        interpretation_payload=PAYLOAD,
    )
    anchor = artifact.character_anchors[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        anchor.status = "APPROVED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# H. Hash determinism
# ---------------------------------------------------------------------------


def test_same_inputs_same_hash():
    a = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")],
        interpretation_payload=PAYLOAD,
    )
    b = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")],
        interpretation_payload=PAYLOAD,
    )
    assert a.content_hash == b.content_hash


def test_payload_change_changes_hash():
    a = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(), character_snapshots=[], interpretation_payload={"mood": "warm"},
    )
    b = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(), character_snapshots=[], interpretation_payload={"mood": "cold"},
    )
    assert a.content_hash != b.content_hash


def test_ass_hash_change_changes_hash():
    a = build_scene_interpretation_artifact(
        ass=_ass(content_hash="x"), location=_location(), character_snapshots=[], interpretation_payload=PAYLOAD,
    )
    b = build_scene_interpretation_artifact(
        ass=_ass(content_hash="y"), location=_location(), character_snapshots=[], interpretation_payload=PAYLOAD,
    )
    assert a.content_hash != b.content_hash


def test_location_hash_change_changes_hash():
    a = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(content_hash="x"), character_snapshots=[], interpretation_payload=PAYLOAD,
    )
    b = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(content_hash="y"), character_snapshots=[], interpretation_payload=PAYLOAD,
    )
    assert a.content_hash != b.content_hash


def test_character_status_change_changes_hash():
    a = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")], interpretation_payload=PAYLOAD,
    )
    b = build_scene_interpretation_artifact(
        ass=_ass(), location=_location(),
        character_snapshots=[_snapshot("KIRA", "PENDING_APPROVAL")], interpretation_payload=PAYLOAD,
    )
    assert a.content_hash != b.content_hash


# ---------------------------------------------------------------------------
# I. Serialization
# ---------------------------------------------------------------------------


def test_serialization_portable():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED")],
        interpretation_payload=PAYLOAD,
    )
    blob = json.dumps(artifact.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "C:" not in blob.upper()
    assert "MappingProxyType" not in blob


# ---------------------------------------------------------------------------
# J. Boundary
# ---------------------------------------------------------------------------


def test_no_characters_in_frame_field():
    artifact = build_scene_interpretation_artifact(
        ass=_ass(),
        location=_location(),
        character_snapshots=[],
        interpretation_payload=PAYLOAD,
    )
    assert "characters_in_frame" not in artifact.to_dict()
    assert "interpretation_payload" in artifact.to_dict()


# ---------------------------------------------------------------------------
# K. OrderedASS (ass/0.2) compatibility
# ---------------------------------------------------------------------------

def _ordered_ass(scene_id="SC_TEST", location_id="yoga_hall") -> OrderedASS:
    body = SceneBody(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id=scene_id,
        location_id=location_id,
        participants=(BodyParticipant(character_id="KIRA", role="protagonist", present=True),),
        content_rating="PG",
        entries=(TextEntry(entry_id="e1", presentation="NARRATIVE", text="Kira enters."),),
    )
    return build_ordered_ass(
        body,
        ass_id="ass_test",
        version=1,
        source_ref="scenes/SC_TEST.json",
        source_hash="0" * 64,
    )


def test_ordered_ass_accepted():
    ass = _ordered_ass()
    assert ass.schema_version == "ass/0.2"
    artifact = build_scene_interpretation_artifact(
        ass=ass,
        location=_location(),
        character_snapshots=[_snapshot("KIRA", "APPROVED_AS_CANON")],
        interpretation_payload=PAYLOAD,
    )
    assert artifact.scene_id == "SC_TEST"
    assert artifact.ass_anchor.ass_id == "ass_test"
    assert artifact.ass_anchor.content_hash == ass.content_hash
    assert artifact.production_eligible is True


def test_ordered_ass_location_mismatch_rejected():
    ass = _ordered_ass(location_id="yoga_hall")
    with pytest.raises(SceneInterpretationValidationError):
        build_scene_interpretation_artifact(
            ass=ass,
            location=_location(location_id="gym_night"),
            character_snapshots=[_snapshot("KIRA", "APPROVED_AS_CANON")],
            interpretation_payload=PAYLOAD,
        )
