#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Aside Context Diagnostics (QA Gap 01)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import aside_context_builder as acb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_snapshot(**overrides):
    """Return a minimal valid canon snapshot for testing."""
    base = {
        "scene_id": "SC_017",
        "beat_id": "sc_017_v2_1a",
        "progress_index": 0,
        "flags": ["test_flag"],
        "completed_scenes": [],
        "levels": {"kira": "L2"},
        "relationships": {},
        "content_rating": "PG-13",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fingerprint tests
# ---------------------------------------------------------------------------


def test_fingerprint_is_64_lowercase_hex():
    snap = _make_minimal_snapshot()
    fp = acb.compute_context_fingerprint(snap)
    assert len(fp) == 64
    assert fp == fp.lower()
    assert all(c in "0123456789abcdef" for c in fp)


def test_identical_snapshots_produce_identical_fingerprints():
    snap1 = _make_minimal_snapshot()
    snap2 = _make_minimal_snapshot()
    assert acb.compute_context_fingerprint(snap1) == acb.compute_context_fingerprint(snap2)


def test_changed_beat_changes_fingerprint():
    snap1 = _make_minimal_snapshot(beat_id="sc_017_v2_1a")
    snap2 = _make_minimal_snapshot(beat_id="sc_017_v2_1b")
    assert acb.compute_context_fingerprint(snap1) != acb.compute_context_fingerprint(snap2)


def test_changed_history_changes_fingerprint():
    snap1 = _make_minimal_snapshot()
    snap1["scene_context"] = {
        "context_available": True,
        "scene_id": "SC_017",
        "played_events": [
            {"scene_id": "SC_017", "beat_id": "e1", "kind": "narration", "speaker": "", "summary": "First."},
        ],
    }
    snap2 = _make_minimal_snapshot()
    snap2["scene_context"] = {
        "context_available": True,
        "scene_id": "SC_017",
        "played_events": [
            {"scene_id": "SC_017", "beat_id": "e2", "kind": "narration", "speaker": "", "summary": "Second."},
        ],
    }
    assert acb.compute_context_fingerprint(snap1) != acb.compute_context_fingerprint(snap2)


def test_dictionary_insertion_order_does_not_change_fingerprint():
    snap1 = _make_minimal_snapshot()
    snap1["levels"] = {"z_key": "Z", "a_key": "A"}
    snap2 = _make_minimal_snapshot()
    snap2["levels"] = {"a_key": "A", "z_key": "Z"}
    assert acb.compute_context_fingerprint(snap1) == acb.compute_context_fingerprint(snap2)


def test_list_order_stabilised_for_fingerprint():
    snap1 = _make_minimal_snapshot(flags=["b", "c", "a"])
    snap2 = _make_minimal_snapshot(flags=["a", "b", "c"])
    assert acb.compute_context_fingerprint(snap1) == acb.compute_context_fingerprint(snap2)


def test_fingerprint_excludes_secrets():
    snap = _make_minimal_snapshot()
    snap["api_key"] = "sk-secret-key"
    snap["OPENAI_API_KEY"] = "sk-another-key"
    snap["trace_path"] = "/home/user/secrets/.env"
    snap["memory_root"] = "/tmp/secrets"
    fp = acb.compute_context_fingerprint(snap)
    # Verify the fingerprint is stable regardless of secret fields.
    sanity = acb.compute_context_fingerprint(_make_minimal_snapshot())
    assert fp == sanity, "secret fields should not affect fingerprint"


def test_fingerprint_excludes_filesystem_paths():
    snap = _make_minimal_snapshot()
    snap["trace_path"] = "C:\\Users\\test\\trace.jsonl"
    snap["memory_root"] = "/home/user/.renpy/saves"
    fp = acb.compute_context_fingerprint(snap)
    sanity = acb.compute_context_fingerprint(_make_minimal_snapshot())
    assert fp == sanity, "filesystem paths should not affect fingerprint"


def test_fingerprint_deterministic():
    """Repeated computation on the same data yields the same fingerprint."""
    snap = _make_minimal_snapshot()
    fps = [acb.compute_context_fingerprint(snap) for _ in range(10)]
    assert all(f == fps[0] for f in fps)


def test_fingerprint_nondict_input():
    """Non-dict input returns valid 64-char fingerprint without crash."""
    fp = acb.compute_context_fingerprint(None)
    assert isinstance(fp, str)
    assert len(fp) == 64
    fp2 = acb.compute_context_fingerprint("string")
    assert isinstance(fp2, str)
    assert len(fp2) == 64


# ---------------------------------------------------------------------------
# context_block_included tests
# ---------------------------------------------------------------------------


def test_context_block_included_true_when_available():
    messages = [
        {"role": "system", "content": "Persona block"},
        {"role": "system", "content": "[CURRENT STORY CONTEXT]\nScene: Test Scene"},
        {"role": "user", "content": "Hello"},
    ]
    assert acb.detect_context_block_included(messages) is True


def test_context_block_included_true_for_unavailable():
    messages = [
        {"role": "system", "content": "Persona block"},
        {"role": "system", "content": "[CONTEXT UNAVAILABLE]\nReason: no scene data"},
        {"role": "user", "content": "Hello"},
    ]
    assert acb.detect_context_block_included(messages) is True


def test_context_block_included_false_when_absent():
    messages = [
        {"role": "system", "content": "Persona block only"},
        {"role": "user", "content": "Hello"},
    ]
    assert acb.detect_context_block_included(messages) is False


def test_context_block_included_false_empty_messages():
    assert acb.detect_context_block_included([]) is False


def test_context_block_included_false_none():
    assert acb.detect_context_block_included(None) is False


def test_context_block_included_false_non_list():
    assert acb.detect_context_block_included("not a list") is False


# ---------------------------------------------------------------------------
# played_event_count tests
# ---------------------------------------------------------------------------


def test_played_event_count_from_detached_snapshot():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {
        "context_available": True,
        "scene_id": "SC_017",
        "played_events": [
            {"scene_id": "SC_017", "beat_id": "e1", "kind": "narration"},
            {"scene_id": "SC_017", "beat_id": "e2", "kind": "action"},
            {"scene_id": "SC_017", "beat_id": "e3", "kind": "dialogue"},
        ],
    }
    assert acb.compute_played_event_count(snap) == 3


def test_played_event_count_zero_for_empty_list():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {"context_available": True, "played_events": []}
    assert acb.compute_played_event_count(snap) == 0


def test_played_event_count_zero_for_missing_history():
    snap = _make_minimal_snapshot()
    # No scene_context at all.
    assert acb.compute_played_event_count(snap) == 0


def test_played_event_count_zero_for_none_history():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {"context_available": True, "played_events": None}
    assert acb.compute_played_event_count(snap) == 0


def test_played_event_count_zero_for_nonlist_history():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {"context_available": True, "played_events": "not a list"}
    assert acb.compute_played_event_count(snap) == 0


def test_played_event_count_nondict_input():
    assert acb.compute_played_event_count(None) == 0
    assert acb.compute_played_event_count("string") == 0


# ---------------------------------------------------------------------------
# Diagnostics output security tests
# ---------------------------------------------------------------------------


def test_diagnostics_do_not_include_event_summaries():
    """The diagnostics dict itself must not contain raw event text."""
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {
        "context_available": True,
        "scene_id": "SC_017",
        "played_events": [
            {"scene_id": "SC_017", "beat_id": "e1", "kind": "narration", "summary": "Secret event detail."},
        ],
    }
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    # The diagnostics dict must NOT contain event summaries (only count).
    serialized = json.dumps(diag, ensure_ascii=False)
    assert "Secret event detail" not in serialized
    assert "played_events" not in serialized.lower()


def test_diagnostics_do_not_include_full_prompt():
    snap = _make_minimal_snapshot()
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    serialized = json.dumps(diag, ensure_ascii=False)
    assert "persona compact source" not in serialized.lower()
    assert "past-only canon snapshot" not in serialized.lower()
    assert "safety/tone" not in serialized.lower()


def test_diagnostics_do_not_include_api_key_or_env():
    snap = _make_minimal_snapshot()
    # Inject secret-like values that would be omitted from fingerprint.
    snap["_extra_nonstandard"] = "sk-secret-key"
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    serialized = json.dumps(diag, ensure_ascii=False)
    assert "sk-secret-key" not in serialized
    assert "OPENAI_API_KEY" not in serialized


# ---------------------------------------------------------------------------
# Integration: build_context_diagnostics returns all six fields
# ---------------------------------------------------------------------------


def test_build_context_diagnostics_returns_six_fields():
    snap = _make_minimal_snapshot()
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    assert "context_available" in diag
    assert "scene_id" in diag
    assert "current_beat" in diag
    assert "played_event_count" in diag
    assert "context_block_included" in diag
    assert "context_fingerprint" in diag
    assert isinstance(diag["context_available"], bool)
    assert isinstance(diag["scene_id"], str)
    assert isinstance(diag["current_beat"], str)
    assert isinstance(diag["played_event_count"], int)
    assert isinstance(diag["context_block_included"], bool)
    assert isinstance(diag["context_fingerprint"], str)
    assert len(diag["context_fingerprint"]) == 64


def test_build_context_diagnostics_same_turn_consistency():
    """All six values are generated from the same turn data."""
    snap = _make_minimal_snapshot()
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    assert diag["scene_id"] == "SC_017"
    assert diag["current_beat"] == "sc_017_v2_1a"
    assert diag["played_event_count"] == 0  # No played history in this test.
    assert diag["context_block_included"] is False  # No scene_context dict.
    assert len(diag["context_fingerprint"]) == 64


def test_build_context_diagnostics_with_unavailable_context():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {"context_available": False, "reason": "no V2 JSON found for SC_999"}
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    assert diag["context_available"] is False
    assert diag["context_block_included"] is True  # UNAVAILABLE block was added.
    assert diag["scene_id"] == "SC_017"
    assert diag["current_beat"] == "sc_017_v2_1a"


def test_build_context_diagnostics_with_available_context():
    snap = _make_minimal_snapshot()
    snap["scene_context"] = {
        "context_available": True,
        "scene_id": "SC_017",
        "scene_title": "Test Scene",
        "location": "home",
        "time_or_phase": "day",
        "active_characters": [{"id": "kira", "name": "Кира"}],
        "content_rating": "PG-13",
    }
    diag = acb.build_context_diagnostics("kira", snap, {}, "Hello")
    assert diag["context_available"] is True
    assert diag["context_block_included"] is True  # CURRENT STORY CONTEXT block was added.