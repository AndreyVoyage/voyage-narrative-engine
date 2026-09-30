#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for StorySequence vs. accepted batch validation (exact coverage)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.story_sequence import (  # noqa: E402
    STORY_SEQUENCE_SCHEMA_VERSION,
    StorySequence,
    StorySequenceBatchValidationError,
    validate_against_batch,
)


def _ss(ids=("sc_a", "sc_b"), start="sc_a") -> StorySequence:
    return StorySequence(
        schema_version=STORY_SEQUENCE_SCHEMA_VERSION,
        ordered_scene_ids=ids,
        start_scene_id=start,
    )


def test_valid_permutation_ok():
    assert validate_against_batch(_ss(ids=("sc_b", "sc_a"), start="sc_b"), {"sc_a", "sc_b"}) == []


def test_unknown_ordered_scene_rejected():
    errors = validate_against_batch(
        _ss(ids=("sc_a", "sc_b", "sc_z")), {"sc_a", "sc_b"}
    )
    assert any("sc_z" in e and "not an accepted scene" in e for e in errors)


def test_unknown_start_rejected():
    # start_scene_id is in the sequence but not in the batch
    errors = validate_against_batch(
        _ss(ids=("sc_a", "sc_b"), start="sc_b"), {"sc_a", "sc_c"}
    )
    assert any("start_scene_id" in e for e in errors)


def test_missing_batch_scene_rejected():
    # exact coverage: a batch scene absent from the sequence is an error
    errors = validate_against_batch(
        _ss(ids=("sc_a", "sc_b")), {"sc_a", "sc_b", "sc_c"}
    )
    assert any("sc_c" in e and "missing" in e for e in errors)


def test_authored_order_is_not_normalized():
    ss = _ss(ids=("sc_b", "sc_a"), start="sc_b")
    validate_against_batch(ss, {"sc_a", "sc_b"})
    # the domain object is immutable and its authored order is untouched
    assert ss.ordered_scene_ids == ("sc_b", "sc_a")
    assert ss.start_scene_id == "sc_b"


def test_non_story_sequence_input_fails_closed():
    with pytest.raises(StorySequenceBatchValidationError):
        validate_against_batch("not-a-story-sequence", {"sc_a"})
