#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHORING_MEDIA_REAL_E2E_PILOT_V0 (Phase B3)

One bounded local pilot proving the real A1→A6 chain end-to-end using:

- real committed Location Canon ``yoga_hall`` (via A2 public API)
- real KIRA Character Canon snapshot, read-only, ``authoring`` context
  (via A3 public API, root supplied by ``NARRATIVE_CHARACTER_CANON_ROOT``)
- an in-memory schema-v2-valid ASS (via A1 public API)
- the exact owner-ratified narrative fact only

NO provider/LLM/media generation. NO production service changes.
"""

from __future__ import annotations

import os
from pathlib import Path

from services.ass import import_scene
from services.character_canon_bridge import read_character_canon
from services.location_canon import load_location
from services.mediaplan import MediaItem, MediaKind, build_mediaplan
from services.prompt_composer import build_prompt_package
from services.scene_interpretation import build_scene_interpretation_artifact

OWNER_RATIFIED_FACT = "KIRA находится в yoga_hall и разминается на беговой дорожке."

REPO_ROOT_TEST = Path(__file__).resolve().parents[2]

PILOT_MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"


def _canon_root() -> Path:
    raw = os.environ.get("NARRATIVE_CHARACTER_CANON_ROOT")
    assert raw, "NARRATIVE_CHARACTER_CANON_ROOT environment variable is required"
    return Path(raw)


def _source_dict() -> dict:
    """Schema-v2-valid in-memory ASS source carrying ONLY the ratified fact."""
    return {
        "schema_version": "2.0",
        "id": "SC_030",
        "name": "Yoga hall treadmill warm-up (pilot)",
        "version": "1.0",
        "location": "yoga_hall",
        "time": "day",
        "intensity": 1,
        "risk": 0,
        "prerequisites": [],
        "flags_required": [],
        "characters": [
            {
                "id": "KIRA",
                "display_name": "Kira",
                "role": "protagonist",
                "present": True,
                "state_start": None,
                "state_end": None,
            }
        ],
        "pov_default": "KIRA",
        "entry_beats": [
            {
                "beat_id": "b1",
                "type": "action",
                "speaker": "KIRA",
                "pov": "KIRA",
                "speech": None,
                "action": OWNER_RATIFIED_FACT,
                "thought": None,
                "thought_visibility": None,
                "narration": None,
                "emotion": None,
                "visual_cue": None,
            }
        ],
        "choice_points": [
            {
                "id": "CP_1",
                "timing": "warmup_done",
                "pov_default": "KIRA",
                "prompt": "How does the warm-up continue?",
                "branches": [
                    {
                        "id": "1A",
                        "option_text": "Continue.",
                        "beats": [
                            {
                                "beat_id": "1A-b1",
                                "type": "narration",
                                "speaker": None,
                                "pov": None,
                                "speech": None,
                                "action": None,
                                "thought": None,
                                "thought_visibility": None,
                                "narration": "Scene ends.",
                                "emotion": None,
                                "visual_cue": None,
                            }
                        ],
                        "effects": {
                            "flags_set": ["sc_030_1a"],
                            "flags_cleared": [],
                        },
                        "next": {
                            "on_complete": "scene_end",
                            "next_scene": None,
                            "completion_flag": "sc_030_complete",
                        },
                    }
                ],
            }
        ],
        "visual": {"scene_id": "VS_030", "stills": []},
        "safety": {
            "content_rating": "PG",
            "stop_words_enabled": True,
            "present_constraints": "",
            "notes": "",
        },
    }


def _run_once(ass, location, kira_snapshot):
    interpretation = build_scene_interpretation_artifact(
        ass=ass,
        location=location,
        character_snapshots=(kira_snapshot,),
        interpretation_payload={"accepted_situation": OWNER_RATIFIED_FACT},
    )
    media_item = MediaItem(
        media_item_id=PILOT_MEDIA_ITEM_ID,
        media_kind=MediaKind.IMAGE,
        characters_in_frame=("KIRA",),
        planning_payload={"visual_goal": OWNER_RATIFIED_FACT},
    )
    mediaplan = build_mediaplan(
        scene_interpretation=interpretation,
        media_items=(media_item,),
    )
    package = build_prompt_package(
        scene_interpretation=interpretation,
        mediaplan=mediaplan,
    )
    return interpretation, mediaplan, package


def test_authoring_media_real_e2e_pilot_v0():
    # ---- A2: real Location Canon ----
    location = load_location(REPO_ROOT_TEST, "yoga_hall")
    assert location.location_id == "yoga_hall"
    assert location.treadmill_count >= 1
    assert any(f.feature_id == "treadmills" for f in location.fixed_features)

    # ---- A3: real KIRA Character Canon (read-only) ----
    canon_root = _canon_root()
    kira_snapshot = read_character_canon(canon_root, "KIRA", usage_context="authoring")
    assert kira_snapshot.character_id == "KIRA"
    assert kira_snapshot.status in ("PENDING_APPROVAL", "APPROVED")

    # ---- A1: in-memory ASS ----
    ass = import_scene(
        _source_dict(),
        ass_id="pilot_yoga_hall_treadmill_v1",
        version=1,
        location_id="yoga_hall",
        source_ref="tests/e2e/SC_030_pilot.v2.json",
    )
    assert ass.scene_id == "SC_030"
    assert ass.location_id == "yoga_hall"
    assert {p.character_id for p in ass.participants} == {"KIRA"}

    # ---- A4 → A5 → A6 ----
    interpretation, mediaplan, package = _run_once(ass, location, kira_snapshot)

    # A4
    assert len(interpretation.character_anchors) == 1
    assert interpretation.character_anchors[0].character_id == "KIRA"
    # expected eligibility derived from real snapshot status (never hard-coded)
    expected_eligible = all(a.status == "APPROVED" for a in interpretation.character_anchors)
    assert interpretation.production_eligible is expected_eligible

    # A5
    assert len(mediaplan.media_items) == 1
    item = mediaplan.media_items[0]
    assert item.media_item_id == PILOT_MEDIA_ITEM_ID
    assert item.media_kind is MediaKind.IMAGE
    assert item.characters_in_frame == ("KIRA",)
    assert mediaplan.scene_interpretation_content_hash == interpretation.content_hash
    assert mediaplan.production_eligible == interpretation.production_eligible

    # A6
    assert len(package.prompt_items) == 1
    prompt_item = package.prompt_items[0]
    assert prompt_item.media_item_id == PILOT_MEDIA_ITEM_ID
    assert prompt_item.media_kind == "IMAGE"
    assert prompt_item.characters_in_frame == ("KIRA",)
    assert package.scene_interpretation_content_hash == interpretation.content_hash
    assert package.mediaplan_content_hash == mediaplan.content_hash
    assert package.production_eligible == mediaplan.production_eligible

    # Prompt content gates: the ratified fact is present; no second character
    # frame identity is introduced.
    assert OWNER_RATIFIED_FACT in prompt_item.prompt_text
    assert "CHARACTERS IN FRAME" in prompt_item.prompt_text
    assert "CHARACTER CANON SNAPSHOTS" in prompt_item.prompt_text

    # ---- determinism over the SAME real frozen inputs (no Canon re-read) ----
    interp2, plan2, pkg2 = _run_once(ass, location, kira_snapshot)
    assert interp2.content_hash == interpretation.content_hash
    assert plan2.content_hash == mediaplan.content_hash
    assert pkg2.content_hash == package.content_hash
    assert pkg2.prompt_items[0].content_hash == prompt_item.content_hash
    assert pkg2.prompt_items[0].prompt_text == prompt_item.prompt_text