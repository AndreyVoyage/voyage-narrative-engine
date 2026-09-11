#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backward-compatibility gate for OD-ORDEREDASS-CONTROL-FLOW-01.

The additive ``next_target`` contract (services/scene_body/model.py) must not
change the content hash of any existing real accepted authority. This test
loads the two real committed SceneVersion records and canonical OrderedASS
artifacts (read-only) and proves their content hashes are byte-for-byte
identical to the pre-change values.

No authority file is modified. No migration. No mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

from services.ass import OrderedASSStore
from services.scene_draft import SceneVersion

REPO_ROOT = Path(__file__).resolve().parents[2]

# Pre-change (frozen) hashes, captured before OD-ORDEREDASS-CONTROL-FLOW-01.
FIRST_ASS_CONTENT_HASH = "c27491900abf097a3113e6200b1d6335ea39b3b08818c5bc1533bc4784bd40e5"
SECOND_SCENEVERSION_CONTENT_HASH = "f84b8c5ef90252658e48d067bd822cce645d6cb2642b01a9a3c926c3937f0a89"
SECOND_ASS_CONTENT_HASH = "df8bc151c385a070d3b2a6636eed342b9d51e837469aebaa671d0090657f7e70"

FIRST_SCENE_ID = "sc_kira_yoga_hall_warmup_001"
SECOND_SCENE_ID = "sc_kira_hidden_problem_001"


def _load_scene_version(scene_id: str) -> SceneVersion:
    path = REPO_ROOT / "authoring" / "scene_drafts" / scene_id / "versions" / "1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return SceneVersion.from_dict(data)


def test_first_scene_ordered_ass_content_hash_unchanged() -> None:
    store = OrderedASSStore((REPO_ROOT / "authoring" / "accepted_ordered_ass").resolve())
    ass = store.load(scene_id=FIRST_SCENE_ID, version=1)
    assert ass.content_hash == FIRST_ASS_CONTENT_HASH


def test_second_scene_version_content_hash_unchanged() -> None:
    sv = _load_scene_version(SECOND_SCENE_ID)
    assert sv.content_hash == SECOND_SCENEVERSION_CONTENT_HASH


def test_second_scene_ordered_ass_content_hash_unchanged() -> None:
    store = OrderedASSStore((REPO_ROOT / "authoring" / "accepted_ordered_ass").resolve())
    ass = store.load(scene_id=SECOND_SCENE_ID, version=1)
    assert ass.content_hash == SECOND_ASS_CONTENT_HASH


def test_neither_real_scene_body_gained_a_next_target_key() -> None:
    """Loading through the extended model must not silently inject the new
    field into content that never had it."""
    for scene_id in (FIRST_SCENE_ID, SECOND_SCENE_ID):
        sv = _load_scene_version(scene_id)
        for entry in sv.body.entries:
            assert "next_target" not in entry.to_dict()
