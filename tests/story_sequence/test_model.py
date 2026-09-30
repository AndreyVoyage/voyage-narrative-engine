#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the StorySequence domain model."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.story_sequence import (  # noqa: E402
    STORY_SEQUENCE_SCHEMA_VERSION,
    StorySequence,
    StorySequenceValidationError,
)


def _ss(ids=("sc_a", "sc_b"), start="sc_a") -> StorySequence:
    return StorySequence(
        schema_version=STORY_SEQUENCE_SCHEMA_VERSION,
        ordered_scene_ids=ids,
        start_scene_id=start,
    )


def test_valid_immutable_sequence():
    ss = _ss()
    assert ss.ordered_scene_ids == ("sc_a", "sc_b")
    assert ss.start_scene_id == "sc_a"
    # deep immutability: sequence is a tuple
    with pytest.raises(TypeError):
        ss.ordered_scene_ids[0] = "x"  # type: ignore[index]
    # frozen dataclass: field assignment is blocked
    with pytest.raises(FrozenInstanceError):
        ss.start_scene_id = "sc_b"  # type: ignore[misc]


def test_empty_sequence_rejected():
    with pytest.raises(StorySequenceValidationError):
        _ss(ids=())


def test_duplicate_scene_rejected():
    with pytest.raises(StorySequenceValidationError):
        _ss(ids=("sc_a", "sc_a"))


def test_start_not_in_sequence_rejected():
    with pytest.raises(StorySequenceValidationError):
        _ss(ids=("sc_a", "sc_b"), start="sc_z")


def test_wrong_schema_rejected():
    with pytest.raises(StorySequenceValidationError):
        StorySequence(
            schema_version="nope/0.1",
            ordered_scene_ids=("sc_a",),
            start_scene_id="sc_a",
        )


def test_blank_scene_id_rejected():
    with pytest.raises(StorySequenceValidationError):
        _ss(ids=("sc_a", ""))


def test_whitespace_padded_scene_id_rejected():
    with pytest.raises(StorySequenceValidationError):
        _ss(ids=("sc_a ", "sc_b"))


def test_deterministic_serialization():
    a = _ss()
    b = _ss()
    assert a.to_dict() == b.to_dict()
    assert a.to_dict() == {
        "schema_version": STORY_SEQUENCE_SCHEMA_VERSION,
        "ordered_scene_ids": ["sc_a", "sc_b"],
        "start_scene_id": "sc_a",
    }


def test_to_dict_preserves_order():
    ss = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    assert ss.to_dict()["ordered_scene_ids"] == ["sc_b", "sc_a"]


def test_from_dict_roundtrip():
    ss = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    assert StorySequence.from_dict(ss.to_dict()) == ss


def test_from_dict_unknown_field_rejected():
    with pytest.raises(StorySequenceValidationError):
        StorySequence.from_dict(
            {
                "schema_version": STORY_SEQUENCE_SCHEMA_VERSION,
                "ordered_scene_ids": ["sc_a"],
                "start_scene_id": "sc_a",
                "extra": 1,
            }
        )
