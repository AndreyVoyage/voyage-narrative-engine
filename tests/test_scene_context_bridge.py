#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for Scene Context Bridge v1."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import scene_context_bridge as scb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_scenarios_dir():
    """Create a temporary scenarios/ directory with a minimal SC_017 V2 JSON."""
    with tempfile.TemporaryDirectory(prefix="vne_scb_test_") as tmp:
        scenarios = Path(tmp) / "scenarios"
        scenarios.mkdir()
        scene_json = {
            "schema_version": "2.0",
            "id": "SC_017",
            "name": "Сергей пишет снова",
            "version": "2.0",
            "location": "home",
            "time": "day",
            "characters": [
                {
                    "id": "kira",
                    "display_name": "Кира",
                    "role": "protagonist",
                    "present": True,
                },
                {
                    "id": "yakov",
                    "display_name": "Яков",
                    "role": "partner",
                    "present": True,
                },
                {
                    "id": "sergey",
                    "display_name": "Сергей",
                    "role": "third",
                    "present": False,
                },
            ],
            "entry_beats": [
                {
                    "beat_id": "e1",
                    "type": "narration",
                    "narration": (
                        "Телефон загорается новым сообщением от Сергея. "
                        "Утренний разговор с Яковым ещё не успел стать привычкой."
                    ),
                }
            ],
            "safety": {"content_rating": "PG-13"},
        }
        (scenarios / "SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json").write_text(
            json.dumps(scene_json, ensure_ascii=False), encoding="utf-8"
        )
        yield Path(tmp)


@pytest.fixture
def temp_scenarios_dir_empty():
    """A temp dir without any V2 JSON files."""
    with tempfile.TemporaryDirectory(prefix="vne_scb_test_empty_") as tmp:
        yield Path(tmp)


# ---------------------------------------------------------------------------
# Test 1: context available
# ---------------------------------------------------------------------------


def test_context_available(temp_scenarios_dir):
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    assert result["context_available"] is True
    assert result["scene_id"] == "SC_017"
    assert result["scene_title"] == "Сергей пишет снова"
    assert result["location"] == "home"
    assert result["time_or_phase"] == "day"
    assert result["content_rating"] == "PG-13"

    active = result["active_characters"]
    assert isinstance(active, list)
    active_ids = {entry["id"] for entry in active}
    assert active_ids == {"kira", "yakov"}
    # sergey is present=False, must not appear
    assert "sergey" not in active_ids

    # static_scene_description removed (future-content prevention).
    # played_events not passed → should be absent or empty.
    played = result.get("played_events")
    assert played is None or played == []


# ---------------------------------------------------------------------------
# Test 2: context unavailable — invalid scene_id
# ---------------------------------------------------------------------------


def test_context_unavailable_invalid_id(temp_scenarios_dir):
    result = scb.build_scene_context_snapshot(
        scene_id="SC_999",
        repo_root=temp_scenarios_dir,
    )
    assert result["context_available"] is False
    assert "reason" in result
    assert "no v2 json" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Test 3: context unavailable — empty scene_id
# ---------------------------------------------------------------------------


def test_context_unavailable_empty_id():
    result = scb.build_scene_context_snapshot(scene_id="")
    assert result["context_available"] is False
    assert "reason" in result


# ---------------------------------------------------------------------------
# Test 4: context unavailable — no scenarios directory
# ---------------------------------------------------------------------------


def test_context_unavailable_no_scenarios_dir(temp_scenarios_dir_empty):
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir_empty,
    )
    assert result["context_available"] is False
    assert "no v2 json" in result["reason"].lower()


# ---------------------------------------------------------------------------
# Test 5: detached deep copy — mutations don't affect later calls
# ---------------------------------------------------------------------------


def test_detached_deep_copy(temp_scenarios_dir):
    result1 = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    assert result1["context_available"] is True

    # Mutate the returned dict aggressively.
    result1["scene_title"] = "MUTATED"
    result1["location"] = "EVIL"
    result1["active_characters"].append({"id": "hacker", "name": "Hacker"})
    result1["NEW_FIELD"] = "INJECTED"

    # Second call must return clean data, unaffected by first call's mutations.
    result2 = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    assert result2["scene_title"] == "Сергей пишет снова"
    assert result2["location"] == "home"
    assert len(result2["active_characters"]) == 2  # kira + yakov only
    assert "NEW_FIELD" not in result2


# ---------------------------------------------------------------------------
# Test 6: deterministic serialization
# ---------------------------------------------------------------------------


def test_deterministic_serialization(temp_scenarios_dir):
    result1 = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    result2 = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    # JSON round-trip ensures identical serialization.
    assert json.dumps(result1, sort_keys=True, ensure_ascii=False) == json.dumps(
        result2, sort_keys=True, ensure_ascii=False
    )


# ---------------------------------------------------------------------------
# Test 7: no sensitive data in output
# ---------------------------------------------------------------------------


def test_no_sensitive_data(temp_scenarios_dir):
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    # No filesystem paths.
    assert "C:" not in serialized
    assert "\\\\" not in serialized
    assert "/home/" not in serialized
    assert str(temp_scenarios_dir) not in serialized

    # No API keys or secrets.
    assert "api_key" not in serialized.lower()
    assert "sk-" not in serialized.lower()
    assert "bearer" not in serialized.lower()
    assert "password" not in serialized.lower()

    # No diagnostic dumps.
    assert "traceback" not in serialized.lower()
    assert "diagnostic" not in serialized.lower()


# ---------------------------------------------------------------------------
# Test 8: scene with no characters present
# ---------------------------------------------------------------------------


def test_scene_with_no_present_characters(temp_scenarios_dir):
    scenes = temp_scenarios_dir / "scenarios"
    scenes.mkdir(exist_ok=True)
    scene_json = {
        "schema_version": "2.0",
        "id": "SC_050",
        "name": "Empty Room",
        "characters": [
            {"id": "alice", "display_name": "Alice", "present": False},
        ],
        "entry_beats": [],
        "safety": {"content_rating": "PG-13"},
    }
    (scenes / "SCENARIO_050_EMPTY.v2.json").write_text(
        json.dumps(scene_json, ensure_ascii=False), encoding="utf-8"
    )

    result = scb.build_scene_context_snapshot(
        scene_id="SC_050",
        repo_root=temp_scenarios_dir,
    )
    assert result["context_available"] is True
    assert result["active_characters"] == []


# ---------------------------------------------------------------------------
# Test 9: beat_id and current_label are attached when provided
# ---------------------------------------------------------------------------


def test_positional_tracking_fields_attached(temp_scenarios_dir):
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        beat_id="sc_017_v2_1a",
        current_label="sc_017_v2_start",
        repo_root=temp_scenarios_dir,
    )
    assert result["context_available"] is True
    assert result["beat_id"] == "sc_017_v2_1a"
    assert result["current_label"] == "sc_017_v2_start"


# ---------------------------------------------------------------------------
# Test 10: malformed JSON in scenario file degrades safely
# ---------------------------------------------------------------------------


def test_malformed_json_degrades_safely(temp_scenarios_dir):
    scenes = temp_scenarios_dir / "scenarios"
    scenes.mkdir(exist_ok=True)
    (scenes / "SCENARIO_099_BROKEN.v2.json").write_text(
        "this is not json {{{", encoding="utf-8"
    )

    result = scb.build_scene_context_snapshot(
        scene_id="SC_099",
        repo_root=temp_scenarios_dir,
    )
    assert result["context_available"] is False
    assert "reason" in result


# ---------------------------------------------------------------------------
# Test 11: scene_id format validation
# ---------------------------------------------------------------------------


def test_scene_id_format_validation():
    # "bad_format" does not match the SC_NNN pattern.
    result_bad = scb.build_scene_context_snapshot(scene_id="bad_format")
    assert result_bad["context_available"] is False
    assert "format" in result_bad["reason"].lower()

    # "SC_01" matches the SC_NNN regex but has only 2 digits — still rejected.
    result_too_short = scb.build_scene_context_snapshot(scene_id="SC_01")
    assert result_too_short["context_available"] is False
    assert "format" in result_too_short["reason"].lower()

    # Lowercase "sc_017" is normalized to "SC_017" internally and accepted.
    # This tests that the bridge normalizes input to canonical format.
    result_lower = scb.build_scene_context_snapshot(
        scene_id="sc_017",
        repo_root=scb.REPO_ROOT,
    )
    assert result_lower["context_available"] is True


# ---------------------------------------------------------------------------
# Test 12: played events are attached when provided
# ---------------------------------------------------------------------------


def test_played_events_attached(temp_scenarios_dir):
    events = [
        {"scene_id": "SC_017", "beat_id": "e1", "kind": "narration", "speaker": "", "summary": "Test event."},
    ]
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
        played_events=events,
    )
    assert result["context_available"] is True
    assert "played_events" in result
    assert len(result["played_events"]) == 1
    assert result["played_events"][0]["summary"] == "Test event."


def test_played_events_sanitised(temp_scenarios_dir):
    """Non-dict entries and non-plain values are silently dropped."""
    events = [
        "not a dict",
        {"scene_id": "SC_017", "beat_id": "e1", "kind": "narration", "speaker": "", "summary": "Valid."},
        {"scene_id": "SC_017", "beat_id": "e2", "kind": "action", "speaker": "", "summary": object()},
    ]
    result = scb.build_scene_context_snapshot(
        scene_id="SC_017",
        repo_root=temp_scenarios_dir,
        played_events=events,
    )
    assert len(result["played_events"]) == 2
    # The event with object() summary would have its value stringified.
    assert isinstance(result["played_events"][1]["summary"], str)