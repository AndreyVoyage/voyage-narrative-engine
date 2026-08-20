#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MediaPlan v0 tests -- typed items, characters_in_frame, production
eligibility, deep immutability, hash, serialization, and boundary."""

from __future__ import annotations

import dataclasses
import json

import pytest

from services.mediaplan import (
    MediaKind,
    MediaPlanValidationError,
    MediaItem,
    build_mediaplan,
)
from services.scene_interpretation import (
    AssAnchor,
    CharacterAnchor,
    LocationAnchor,
    SceneInterpretationArtifact,
)

SCENE_ID = "SC_TEST"
INTER_HASH = "inter_hash_000"


def _artifact(production_eligible=True, character_ids=("KIRA", "OLGA")):
    return SceneInterpretationArtifact(
        schema_version="scene_interpretation/0.1",
        scene_id=SCENE_ID,
        ass_anchor=AssAnchor(scene_id=SCENE_ID, ass_id="ass_test", version=1, content_hash="ass_hash"),
        location_anchor=LocationAnchor(location_id="yoga_hall", content_hash="loc_hash"),
        character_anchors=tuple(
            CharacterAnchor(
                character_id=cid,
                status="APPROVED",
                snapshot_content_hash=f"snap_{cid}",
                serialized_snapshot={"character_id": cid, "status": "APPROVED"},
            )
            for cid in character_ids
        ),
        interpretation_payload={"mood": "warm"},
        content_hash=INTER_HASH,
        production_eligible=production_eligible,
    )


def _image(item_id="IMG_1", frame=("KIRA",), payload=None):
    return MediaItem(
        media_item_id=item_id,
        media_kind=MediaKind.IMAGE,
        characters_in_frame=tuple(frame),
        planning_payload=payload if payload is not None else {"note": "image"},
    )


def _audio(item_id="AUD_1", payload=None):
    return MediaItem(
        media_item_id=item_id,
        media_kind=MediaKind.AUDIO,
        characters_in_frame=(),
        planning_payload=payload if payload is not None else {"note": "audio"},
    )


# ---------------------------------------------------------------------------
# A. Basic plan
# ---------------------------------------------------------------------------


def test_basic_plan():
    plan = build_mediaplan(
        scene_interpretation=_artifact(),
        media_items=[_image(), _audio()],
    )
    assert plan.scene_id == SCENE_ID
    assert plan.production_eligible is True
    assert len(plan.media_items) == 2


# ---------------------------------------------------------------------------
# B. Interpretation anchor
# ---------------------------------------------------------------------------


def test_interpretation_anchor_preserved():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    assert plan.scene_interpretation_content_hash == INTER_HASH


def test_upstream_unchanged():
    artifact = _artifact()
    original = artifact.to_dict()
    build_mediaplan(scene_interpretation=artifact, media_items=[_image()])
    assert artifact.to_dict() == original


# ---------------------------------------------------------------------------
# C. Typed items
# ---------------------------------------------------------------------------


def test_typed_items_accepted():
    plan = build_mediaplan(
        scene_interpretation=_artifact(),
        media_items=[
            _image("IMG_1"),
            MediaItem("VID_1", MediaKind.VIDEO, ("KIRA",), {"note": "video"}),
            _audio("AUD_1"),
        ],
    )
    kinds = {i.media_kind for i in plan.media_items}
    assert kinds == {MediaKind.IMAGE, MediaKind.VIDEO, MediaKind.AUDIO}


def test_unknown_kind_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(
            scene_interpretation=_artifact(),
            media_items=[MediaItem("X_1", "HOLOGRAM", (), {"note": "x"})],  # type: ignore
        )


# ---------------------------------------------------------------------------
# D. Item identity
# ---------------------------------------------------------------------------


def test_duplicate_item_id_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("DUP"), _audio("DUP")])


def test_item_id_preserved():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("IMG_9")])
    assert plan.media_items[0].media_item_id == "IMG_9"


# ---------------------------------------------------------------------------
# E. characters_in_frame
# ---------------------------------------------------------------------------


def test_characters_in_frame_item_level():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("KIRA",))])
    assert plan.media_items[0].characters_in_frame == ("KIRA",)


def test_non_anchor_character_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("SERGEY",))])


def test_duplicate_characters_in_frame_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("KIRA", "KIRA"))])


def test_case_fuzzy_mismatch_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("kira",))])


# ---------------------------------------------------------------------------
# F. Audio boundary
# ---------------------------------------------------------------------------


def test_audio_with_frame_rejected():
    with pytest.raises(MediaPlanValidationError):
        build_mediaplan(
            scene_interpretation=_artifact(),
            media_items=[MediaItem("AUD_1", MediaKind.AUDIO, ("KIRA",), {"note": "x"})],
        )


# ---------------------------------------------------------------------------
# G. Production eligibility (monotonic)
# ---------------------------------------------------------------------------


def test_production_false_propagates():
    plan = build_mediaplan(scene_interpretation=_artifact(production_eligible=False), media_items=[_image()])
    assert plan.production_eligible is False


def test_production_true_preserved():
    plan = build_mediaplan(scene_interpretation=_artifact(production_eligible=True), media_items=[_image()])
    assert plan.production_eligible is True


# ---------------------------------------------------------------------------
# H. Deep immutability
# ---------------------------------------------------------------------------


def test_payload_alias_severed():
    payload = {"tags": ["x"]}
    item = MediaItem("IMG_1", MediaKind.IMAGE, ("KIRA",), payload)
    payload["tags"].append("y")
    assert "y" not in item.planning_payload["tags"]


def test_item_frame_immutable():
    frame = ["KIRA"]
    item = MediaItem("IMG_1", MediaKind.IMAGE, frame, {"note": "x"})
    frame.append("OLGA")
    assert item.characters_in_frame == ("KIRA",)


def test_plan_items_tuple():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    assert isinstance(plan.media_items, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.media_items = ()  # type: ignore[misc]


def test_serialization_mutation_does_not_affect_plan():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    stored = plan.content_hash
    d = plan.to_dict()
    d["media_items"][0]["planning_payload"]["note"] = "hacked"
    assert plan.media_items[0].planning_payload["note"] == "image"
    assert plan.content_hash == stored


# ---------------------------------------------------------------------------
# I. Hash
# ---------------------------------------------------------------------------


def test_same_plan_same_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    b = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    assert a.content_hash == b.content_hash


def test_interpretation_hash_change_changes_plan_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    artifact = _artifact()
    artifact = dataclasses.replace(artifact, content_hash="inter_hash_OTHER")
    b = build_mediaplan(scene_interpretation=artifact, media_items=[_image()])
    assert a.content_hash != b.content_hash


def test_item_id_change_changes_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("IMG_1")])
    b = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("IMG_2")])
    assert a.content_hash != b.content_hash


def test_media_kind_change_changes_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("M_1")])
    b = build_mediaplan(
        scene_interpretation=_artifact(),
        media_items=[MediaItem("M_1", MediaKind.VIDEO, ("KIRA",), {"note": "image"})],
    )
    assert a.content_hash != b.content_hash


def test_frame_change_changes_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("KIRA",))])
    b = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(frame=("OLGA",))])
    assert a.content_hash != b.content_hash


def test_payload_change_changes_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(payload={"note": "a"})])
    b = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image(payload={"note": "b"})])
    assert a.content_hash != b.content_hash


def test_order_change_changes_hash():
    a = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image("IMG_1"), _audio("AUD_1")])
    b = build_mediaplan(scene_interpretation=_artifact(), media_items=[_audio("AUD_1"), _image("IMG_1")])
    assert a.content_hash != b.content_hash


# ---------------------------------------------------------------------------
# J. Serialization
# ---------------------------------------------------------------------------


def test_serialization_portable():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    blob = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "MappingProxyType" not in blob
    assert "C:" not in blob.upper()


# ---------------------------------------------------------------------------
# K. Boundary
# ---------------------------------------------------------------------------


def test_no_prompt_or_generation_fields():
    plan = build_mediaplan(scene_interpretation=_artifact(), media_items=[_image()])
    d = plan.to_dict()
    for forbidden in ("prompt", "negative_prompt", "model", "seed", "temperature", "asset_path"):
        assert forbidden not in d