#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the StorySequence load/save boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.story_sequence import (  # noqa: E402
    STORY_SEQUENCE_SCHEMA_VERSION,
    StorySequence,
    StorySequenceError,
    StorySequenceNotFoundError,
    StorySequenceValidationError,
    load_story_sequence,
    parse_story_sequence,
    save_story_sequence,
    serialize_story_sequence,
    validate_story_sequence,
)


def _ss(ids=("sc_a", "sc_b"), start="sc_a") -> StorySequence:
    return StorySequence(
        schema_version=STORY_SEQUENCE_SCHEMA_VERSION,
        ordered_scene_ids=ids,
        start_scene_id=start,
    )


def test_serialize_is_stable_and_deterministic():
    a = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    b = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    assert serialize_story_sequence(a) == serialize_story_sequence(b)


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    ss = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    save_story_sequence(path, ss)
    loaded = load_story_sequence(path)
    assert loaded == ss
    # bytes are canonical and byte-identical to the serializer output
    assert path.read_bytes() == serialize_story_sequence(ss)


def test_load_missing_fails_closed(tmp_path):
    with pytest.raises(StorySequenceNotFoundError):
        load_story_sequence(tmp_path / "missing.json")


def test_malformed_json_fails_closed(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(StorySequenceError):
        load_story_sequence(path)


def test_unknown_field_fails_closed(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": STORY_SEQUENCE_SCHEMA_VERSION,
                "ordered_scene_ids": ["sc_a"],
                "start_scene_id": "sc_a",
                "extra": 1,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StorySequenceValidationError):
        load_story_sequence(path)


def test_duplicate_json_key_fails_closed(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    path.write_text(
        '{"schema_version": "vne_story_sequence/0.1", '
        '"schema_version": "vne_story_sequence/0.1", '
        '"ordered_scene_ids": ["sc_a"], "start_scene_id": "sc_a"}',
        encoding="utf-8",
    )
    with pytest.raises(StorySequenceValidationError):
        load_story_sequence(path)


def test_wrong_schema_version_fails_closed(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "wrong/0.1",
                "ordered_scene_ids": ["sc_a"],
                "start_scene_id": "sc_a",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(StorySequenceValidationError):
        load_story_sequence(path)


def test_parse_roundtrip_bytes():
    ss = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    assert parse_story_sequence(serialize_story_sequence(ss)) == ss


def test_validate_story_sequence(tmp_path):
    path = tmp_path / "STORY_SEQUENCE.json"
    assert validate_story_sequence(path) == ["story sequence does not exist"]
    save_story_sequence(path, _ss())
    assert validate_story_sequence(path) == []
