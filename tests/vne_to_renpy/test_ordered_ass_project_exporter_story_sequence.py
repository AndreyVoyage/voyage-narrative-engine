#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for StorySequence-driven OrderedASS project export."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import build_ordered_ass  # noqa: E402
from services.scene_body import (  # noqa: E402
    AUTHORING_SCHEMA_VERSION,
    Participant,
    SceneBody,
    TextEntry,
)
from services.story_sequence import (  # noqa: E402
    STORY_SEQUENCE_SCHEMA_VERSION,
    StorySequence,
    StorySequenceValidationError,
)
from tools.vne_to_renpy import (  # noqa: E402
    OrderedProjectExportError,
    build_ordered_project_candidate,
)
from tools.vne_to_renpy.ordered_ass_exporter import scene_start_label  # noqa: E402
from tools.vne_to_renpy.ordered_ass_project_exporter import STORY_ENTRY_LABEL  # noqa: E402

SCENE_A = "SC_900"
SCENE_B = "SC_901"
SCENE_C = "SC_902"


def _narrative(entry_id="e1", text="Hello.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="NARRATIVE", text=text)


def _ass(scene_id, ass_id=None):
    body = SceneBody(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id=scene_id,
        location_id="yoga_hall",
        participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
        content_rating="PG",
        entries=(_narrative(),),
    )
    return build_ordered_ass(
        body, ass_id=ass_id or "ass_{}".format(scene_id), version=1,
        source_ref="x.json", source_hash="0" * 64,
    )


def _ss(ids, start) -> StorySequence:
    return StorySequence(
        schema_version=STORY_SEQUENCE_SCHEMA_VERSION,
        ordered_scene_ids=ids,
        start_scene_id=start,
    )


@pytest.fixture
def resolver_calls(monkeypatch):
    def fake(asset_ids, *, registry_path, repo_root):
        return {}

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake,
    )


def _build(scenes, story_sequence=None):
    return build_ordered_project_candidate(
        scenes,
        reading_mode="classic_vn",
        character_symbols={"KIRA": "kira"},
        registry_path=Path("dummy_reg.json"),
        repo_root=Path("dummy_repo"),
        story_sequence=story_sequence,
    )


def _label_position(source: str, scene_id: str) -> int:
    return source.index("label {}:".format(scene_start_label(scene_id)))


def test_scene_blocks_follow_declared_order(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B), _ass(SCENE_C))
    ss = _ss((SCENE_C, SCENE_A, SCENE_B), SCENE_C)
    c = _build(scenes, story_sequence=ss)
    assert c.scene_ids == (SCENE_C, SCENE_A, SCENE_B)
    assert _label_position(c.source, SCENE_C) < _label_position(c.source, SCENE_A)
    assert _label_position(c.source, SCENE_A) < _label_position(c.source, SCENE_B)


def test_output_differs_from_alphabetical(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B), _ass(SCENE_C))
    ss = _ss((SCENE_C, SCENE_A, SCENE_B), SCENE_C)
    alphabetical = _build(scenes, story_sequence=None)
    declared = _build(scenes, story_sequence=ss)
    assert alphabetical.scene_ids == (SCENE_A, SCENE_B, SCENE_C)
    assert declared.scene_ids == (SCENE_C, SCENE_A, SCENE_B)
    assert declared.source != alphabetical.source


def test_exactly_one_story_entry_label(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_B, SCENE_A), SCENE_B)
    c = _build(scenes, story_sequence=ss)
    assert c.source.count("label {}:".format(STORY_ENTRY_LABEL)) == 1


def test_story_entry_jumps_to_start_scene_start_label(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_B, SCENE_A), SCENE_B)
    c = _build(scenes, story_sequence=ss)
    assert "jump {}".format(scene_start_label(SCENE_B)) in c.source


def test_no_global_start_label_added(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_B, SCENE_A), SCENE_B)
    c = _build(scenes, story_sequence=ss)
    assert "label start:" not in c.source


def test_deterministic_bytes(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_B, SCENE_A), SCENE_B)
    c1 = _build(scenes, story_sequence=ss)
    c2 = _build(scenes, story_sequence=ss)
    assert c1.source == c2.source
    assert c1.source_sha256 == c2.source_sha256
    assert c1.source_sha256 == hashlib.sha256(c1.source.encode("utf-8")).hexdigest()


def test_invalid_story_sequence_produces_no_candidate(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    # start scene absent from sequence -> domain invalid, before export
    with pytest.raises(StorySequenceValidationError):
        _ss((SCENE_A, SCENE_B), SCENE_C)


def test_story_sequence_not_covering_batch_fails_closed(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_A,), SCENE_A)  # SCENE_B missing -> exact coverage violation
    with pytest.raises(OrderedProjectExportError):
        _build(scenes, story_sequence=ss)


def test_story_sequence_with_unknown_scene_fails_closed(resolver_calls):
    scenes = (_ass(SCENE_A), _ass(SCENE_B))
    ss = _ss((SCENE_A, SCENE_B, "SC_999"), SCENE_A)
    with pytest.raises(OrderedProjectExportError):
        _build(scenes, story_sequence=ss)
