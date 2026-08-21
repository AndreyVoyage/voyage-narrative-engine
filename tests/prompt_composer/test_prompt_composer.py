#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prompt Composer v0 tests -- deterministic composition, anchors, character
selection, no-inference, hashing, immutability, serialization, boundary."""

from __future__ import annotations

import dataclasses
import json

import pytest

from services.mediaplan import MediaKind, MediaItem, MediaPlan
from services.prompt_composer import (
    PromptComposerValidationError,
    build_prompt_package,
)
from services.scene_interpretation import (
    AssAnchor,
    CharacterAnchor,
    LocationAnchor,
    SceneInterpretationArtifact,
)

SCENE_ID = "SC_TEST"
INTER_HASH = "inter_hash_000"
MEDIA_HASH = "media_hash_000"


def _artifact(production_eligible=True, character_ids=("KIRA", "SERGEY")):
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
                serialized_snapshot={"character_id": cid, "note": f"visual_{cid}"},
            )
            for cid in character_ids
        ),
        interpretation_payload={"mood": "warm"},
        content_hash=INTER_HASH,
        production_eligible=production_eligible,
    )


def _mediaplan(production_eligible=True, items=None, inter_hash=None, scene_id=None):
    if items is None:
        items = [_image(), _video(), _audio()]
    return MediaPlan(
        schema_version="mediaplan/0.1",
        scene_id=scene_id if scene_id is not None else SCENE_ID,
        scene_interpretation_content_hash=inter_hash if inter_hash is not None else INTER_HASH,
        media_items=tuple(items),
        content_hash=MEDIA_HASH,
        production_eligible=production_eligible,
    )


def _image(item_id="IMG_1", frame=("KIRA",), payload=None):
    return MediaItem(item_id, MediaKind.IMAGE, tuple(frame), payload or {"note": "img"})


def _video(item_id="VID_1", frame=("KIRA", "SERGEY"), payload=None):
    return MediaItem(item_id, MediaKind.VIDEO, tuple(frame), payload or {"note": "vid"})


def _audio(item_id="AUD_1", payload=None):
    return MediaItem(item_id, MediaKind.AUDIO, (), payload or {"note": "aud"})


# ---------------------------------------------------------------------------
# A. Basic composition
# ---------------------------------------------------------------------------


def test_basic_composition():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert pkg.scene_id == SCENE_ID
    assert len(pkg.prompt_items) == 3
    assert [i.media_item_id for i in pkg.prompt_items] == ["IMG_1", "VID_1", "AUD_1"]


# ---------------------------------------------------------------------------
# B. Source anchors
# ---------------------------------------------------------------------------


def test_source_anchors_preserved():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert pkg.scene_interpretation_content_hash == INTER_HASH
    assert pkg.mediaplan_content_hash == MEDIA_HASH


def test_upstream_unchanged():
    art = _artifact()
    plan = _mediaplan()
    art_d = art.to_dict()
    plan_d = plan.to_dict()
    build_prompt_package(scene_interpretation=art, mediaplan=plan)
    assert art.to_dict() == art_d
    assert plan.to_dict() == plan_d


# ---------------------------------------------------------------------------
# C. Compatibility validation
# ---------------------------------------------------------------------------


def test_scene_id_mismatch_rejected():
    with pytest.raises(PromptComposerValidationError):
        build_prompt_package(
            scene_interpretation=_artifact(),
            mediaplan=_mediaplan(scene_id="SC_OTHER"),
        )


def test_interpretation_hash_mismatch_rejected():
    with pytest.raises(PromptComposerValidationError):
        build_prompt_package(
            scene_interpretation=_artifact(),
            mediaplan=_mediaplan(inter_hash="bad_hash"),
        )


def test_production_contradiction_rejected():
    with pytest.raises(PromptComposerValidationError):
        build_prompt_package(
            scene_interpretation=_artifact(production_eligible=False),
            mediaplan=_mediaplan(production_eligible=True),
        )


def test_unknown_frame_character_rejected():
    with pytest.raises(PromptComposerValidationError):
        build_prompt_package(
            scene_interpretation=_artifact(),
            mediaplan=_mediaplan(items=[_image(frame=("UNKNOWN",))]),
        )


# ---------------------------------------------------------------------------
# D. Item identity
# ---------------------------------------------------------------------------


def test_item_identity_preserved():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image("IMG_9")]))
    assert pkg.prompt_items[0].media_item_id == "IMG_9"


# ---------------------------------------------------------------------------
# E. Characters in frame / character selection
# ---------------------------------------------------------------------------


def test_visual_item_includes_only_selected_snapshot():
    pkg = build_prompt_package(
        scene_interpretation=_artifact(character_ids=("KIRA", "SERGEY")),
        mediaplan=_mediaplan(items=[_image("IMG_1", frame=("KIRA",))]),
    )
    text = pkg.prompt_items[0].prompt_text
    assert "visual_KIRA" in text
    assert "visual_SERGEY" not in text


def test_video_includes_both_selected():
    pkg = build_prompt_package(
        scene_interpretation=_artifact(character_ids=("KIRA", "SERGEY")),
        mediaplan=_mediaplan(items=[_video("VID_1", frame=("KIRA", "SERGEY"))]),
    )
    text = pkg.prompt_items[0].prompt_text
    assert "visual_KIRA" in text
    assert "visual_SERGEY" in text


def test_audio_has_no_character_snapshot():
    pkg = build_prompt_package(
        scene_interpretation=_artifact(character_ids=("KIRA", "SERGEY")),
        mediaplan=_mediaplan(items=[_audio()]),
    )
    text = pkg.prompt_items[0].prompt_text
    assert "visual_KIRA" not in text
    assert "visual_SERGEY" not in text
    assert "CHARACTERS IN FRAME" not in text


def test_audio_characters_in_frame_empty():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_audio()]))
    assert pkg.prompt_items[0].characters_in_frame == ()


# ---------------------------------------------------------------------------
# F. Deterministic text
# ---------------------------------------------------------------------------


def test_same_inputs_same_prompt_text():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert a.prompt_items[0].prompt_text == b.prompt_items[0].prompt_text


def test_mapping_key_order_irrelevant():
    art_a = _artifact()
    art_a = dataclasses.replace(art_a, interpretation_payload={"a": 1, "b": 2})
    art_b = _artifact()
    art_b = dataclasses.replace(art_b, interpretation_payload={"b": 2, "a": 1})
    pkg_a = build_prompt_package(scene_interpretation=art_a, mediaplan=_mediaplan())
    pkg_b = build_prompt_package(scene_interpretation=art_b, mediaplan=_mediaplan())
    assert pkg_a.prompt_items[0].prompt_text == pkg_b.prompt_items[0].prompt_text


# ---------------------------------------------------------------------------
# G. No creative inference
# ---------------------------------------------------------------------------


def test_no_creative_inference_sentinels():
    pkg = build_prompt_package(
        scene_interpretation=_artifact(),
        mediaplan=_mediaplan(items=[_image("IMG_1", payload={"note": "img"})]),
    )
    text = pkg.prompt_items[0].prompt_text
    for sentinel in ("camera", "lighting", "pose", "clothing", "duration", "dialogue"):
        assert sentinel not in text.lower()


def test_no_provider_parameters():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    d = pkg.to_dict()
    for forbidden in ("provider", "model", "temperature", "seed", "negative_prompt", "max_tokens"):
        assert forbidden not in d


# ---------------------------------------------------------------------------
# H. Hash
# ---------------------------------------------------------------------------


def test_same_sources_same_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert a.content_hash == b.content_hash
    assert a.prompt_items[0].content_hash == b.prompt_items[0].content_hash


def test_mediaplan_hash_change_changes_package_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    plan = _mediaplan()
    plan = dataclasses.replace(plan, content_hash="other_media_hash")
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=plan)
    assert a.content_hash != b.content_hash


def test_interpretation_change_changes_package_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    art = _artifact()
    art = dataclasses.replace(art, content_hash="other_inter")
    # keep mediaplan anchor consistent so only interpretation changed
    plan = _mediaplan(inter_hash="other_inter")
    b = build_prompt_package(scene_interpretation=art, mediaplan=plan)
    assert a.content_hash != b.content_hash


def test_planning_payload_change_changes_item_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image(payload={"note": "x"})]))
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image(payload={"note": "y"})]))
    assert a.prompt_items[0].content_hash != b.prompt_items[0].content_hash


def test_frame_change_changes_item_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image(frame=("KIRA",))]))
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image(frame=("SERGEY",))]))
    assert a.prompt_items[0].content_hash != b.prompt_items[0].content_hash


def test_item_order_change_changes_package_hash():
    a = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_image("A"), _audio("B")]))
    b = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan(items=[_audio("B"), _image("A")]))
    assert a.content_hash != b.content_hash


# ---------------------------------------------------------------------------
# I. Production eligibility
# ---------------------------------------------------------------------------


def test_production_false_propagates():
    pkg = build_prompt_package(
        scene_interpretation=_artifact(production_eligible=False),
        mediaplan=_mediaplan(production_eligible=False),
    )
    assert pkg.production_eligible is False


def test_production_true_preserved():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert pkg.production_eligible is True


# ---------------------------------------------------------------------------
# J. Deep immutability
# ---------------------------------------------------------------------------


def test_package_prompt_items_tuple():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    assert isinstance(pkg.prompt_items, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        pkg.prompt_items = ()  # type: ignore[misc]


def test_serialization_mutation_does_not_affect_package():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    stored = pkg.content_hash
    d = pkg.to_dict()
    d["prompt_items"][0]["prompt_text"] = "hacked"
    assert pkg.prompt_items[0].prompt_text != "hacked"
    assert pkg.content_hash == stored


# ---------------------------------------------------------------------------
# K. Serialization
# ---------------------------------------------------------------------------


def test_serialization_portable():
    pkg = build_prompt_package(scene_interpretation=_artifact(), mediaplan=_mediaplan())
    blob = json.dumps(pkg.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "C:" not in blob.upper()
    assert "MappingProxyType" not in blob


# ---------------------------------------------------------------------------
# L. Boundary
# ---------------------------------------------------------------------------


def test_no_live_canon_reread_marker():
    # The composer should only use frozen anchor.to_dict() data; there is no
    # live-canon import/read in services/prompt_composer.
    import services.prompt_composer.builder as b

    src = inspect_source(b)
    assert "narrative-character-canon" not in src


def inspect_source(module) -> str:
    import inspect as _inspect

    return _inspect.getsource(module)