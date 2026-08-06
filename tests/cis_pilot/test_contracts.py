#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 0 unit tests for tools/cis_pilot/contracts.py.

No LLM, no network, no filesystem I/O -- pure construction/validation
tests against synthetic values only.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import (
    ALLOWED_P4_STATES,
    BaselineSourceSet,
    ContractValidationError,
    MemoryEventSource,
    P0Snapshot,
    P3State,
    P4State,
    PilotSourceSnapshot,
    SourceArtifact,
)

_VALID_SHA256 = "a" * 64
_VALID_GIT_SHA = "b" * 40


def _artifact(path: str = "personas/kira/psychology/BASE.json", kind: str = "p0_module", **kwargs) -> SourceArtifact:
    return SourceArtifact(repo_relative_path=path, sha256=_VALID_SHA256, kind=kind, **kwargs)


# ---------------------------------------------------------------------------
# SourceArtifact
# ---------------------------------------------------------------------------


def test_source_artifact_is_immutable():
    artifact = _artifact()
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.sha256 = "c" * 64  # type: ignore[misc]


def test_source_artifact_rejects_absolute_path():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="/etc/passwd", sha256=_VALID_SHA256, kind="p0_module")


def test_source_artifact_rejects_backslash_path():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="personas\\kira\\BASE.json", sha256=_VALID_SHA256, kind="p0_module")


def test_source_artifact_rejects_traversal_segment():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="personas/../secret.json", sha256=_VALID_SHA256, kind="p0_module")


def test_source_artifact_rejects_bad_sha256_length():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="personas/kira/BASE.json", sha256="abc", kind="p0_module")


def test_source_artifact_rejects_uppercase_sha256():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="personas/kira/BASE.json", sha256="A" * 64, kind="p0_module")


def test_source_artifact_rejects_empty_kind():
    with pytest.raises(ContractValidationError):
        SourceArtifact(repo_relative_path="personas/kira/BASE.json", sha256=_VALID_SHA256, kind="")


# ---------------------------------------------------------------------------
# P0Snapshot
# ---------------------------------------------------------------------------


def _build_p0_snapshot() -> P0Snapshot:
    return P0Snapshot(
        value_system=_artifact("personas/kira/psychology/VALUE_SYSTEM.json"),
        base=_artifact("personas/kira/psychology/BASE.json"),
        attachment=_artifact("personas/kira/psychology/ATTACHMENT.json"),
        defense_mechanisms=_artifact("personas/kira/psychology/DEFENSE_MECHANISMS.json"),
        ifs_parts=_artifact("personas/kira/psychology/IFS_PARTS.json"),
        odsc=_artifact("personas/kira/psychology/ODSC.json"),
    )


def test_p0_snapshot_has_exactly_six_fields():
    field_names = {f.name for f in dataclasses.fields(P0Snapshot)}
    assert field_names == {
        "value_system",
        "base",
        "attachment",
        "defense_mechanisms",
        "ifs_parts",
        "odsc",
    }


def test_p0_snapshot_has_no_attachment_style_dynamic_field():
    field_names = {f.name for f in dataclasses.fields(P0Snapshot)}
    assert "attachment_style_dynamic" not in field_names
    assert not hasattr(P0Snapshot, "attachment_style_dynamic")


def test_p0_snapshot_is_immutable():
    snapshot = _build_p0_snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.base = _artifact()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P3State
# ---------------------------------------------------------------------------


def test_p3_state_accepts_boundary_values():
    assert P3State(trust=0, attraction=0).trust == 0
    assert P3State(trust=100, attraction=100).attraction == 100
    assert P3State(trust=75, attraction=85).trust == 75


@pytest.mark.parametrize("trust", [-1, 101, -100, 1000])
def test_p3_state_rejects_out_of_range_trust(trust):
    with pytest.raises(ContractValidationError):
        P3State(trust=trust, attraction=50)


@pytest.mark.parametrize("attraction", [-1, 101, -100, 1000])
def test_p3_state_rejects_out_of_range_attraction(attraction):
    with pytest.raises(ContractValidationError):
        P3State(trust=50, attraction=attraction)


def test_p3_state_rejects_bool_trust():
    with pytest.raises(ContractValidationError):
        P3State(trust=True, attraction=50)  # type: ignore[arg-type]


def test_p3_state_rejects_bool_attraction():
    with pytest.raises(ContractValidationError):
        P3State(trust=50, attraction=False)  # type: ignore[arg-type]


def test_p3_state_exactly_two_fields_no_forbidden_ones():
    field_names = {f.name for f in dataclasses.fields(P3State)}
    assert field_names == {"trust", "attraction"}
    assert "resentment" not in field_names
    assert "session_count" not in field_names
    assert "attachment_style" not in field_names


# ---------------------------------------------------------------------------
# P4State
# ---------------------------------------------------------------------------


def test_p4_state_accepts_all_four_source_backed_states():
    assert len(ALLOWED_P4_STATES) == 4
    for (arousal, anxiety), strategy in ALLOWED_P4_STATES.items():
        state = P4State(arousal=arousal, anxiety=anxiety, strategy=strategy)
        assert state.arousal == arousal
        assert state.anxiety == anxiety
        assert state.strategy == strategy


def test_p4_state_rejects_unknown_combination():
    with pytest.raises(ContractValidationError):
        P4State(arousal="medium", anxiety="low", strategy="approach")


def test_p4_state_rejects_mismatched_strategy():
    with pytest.raises(ContractValidationError):
        P4State(arousal="high", anxiety="low", strategy="avoidance")


def test_p4_state_rejects_numeric_arousal():
    with pytest.raises(ContractValidationError):
        P4State(arousal=1, anxiety="low", strategy="approach")  # type: ignore[arg-type]


def test_p4_state_is_immutable():
    state = P4State(arousal="high", anxiety="low", strategy="approach")
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.strategy = "avoidance"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MemoryEventSource
# ---------------------------------------------------------------------------


def test_memory_event_source_requires_non_empty_literal_text():
    with pytest.raises(ContractValidationError):
        MemoryEventSource(
            event_id="SC_008",
            scenario_repo_relative_path="scenarios/SCENARIO_008_HOME_EMBRACE.json",
            json_path="choice_points[0].branches[0].action",
            literal_text="",
            sha256=_VALID_SHA256,
        )


def test_memory_event_source_normalized_text_optional():
    event = MemoryEventSource(
        event_id="SC_017",
        scenario_repo_relative_path="scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
        json_path="entry_beats[0].narration",
        literal_text="Телефон загорается новым сообщением от Сергея.",
        sha256=_VALID_SHA256,
    )
    assert event.normalized_text is None


def test_memory_event_source_is_immutable():
    event = MemoryEventSource(
        event_id="SC_008",
        scenario_repo_relative_path="scenarios/SCENARIO_008_HOME_EMBRACE.json",
        json_path="choice_points[0].branches[0].action",
        literal_text="Падает ему на грудь. Плачет. Не объясняет.",
        sha256=_VALID_SHA256,
        normalized_text="Кира падает ему на грудь. Плачет. Не объясняет.",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.literal_text = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BaselineSourceSet
# ---------------------------------------------------------------------------


def _build_baseline() -> BaselineSourceSet:
    return BaselineSourceSet(
        identity=_artifact("personas/kira/core/IDENTITY.json"),
        base=_artifact("personas/kira/psychology/BASE.json"),
        speech_matrix=_artifact("personas/kira/speech/SPEECH_MATRIX.json"),
        matrix=_artifact("personas/kira/relationships/MATRIX.json"),
        builder_source=_artifact("tools/aside_context_builder.py", kind="builder_source"),
        baseline_git_sha=_VALID_GIT_SHA,
    )


def test_baseline_source_set_rejects_bad_git_sha():
    with pytest.raises(ContractValidationError):
        BaselineSourceSet(
            identity=_artifact("personas/kira/core/IDENTITY.json"),
            base=_artifact("personas/kira/psychology/BASE.json"),
            speech_matrix=_artifact("personas/kira/speech/SPEECH_MATRIX.json"),
            matrix=_artifact("personas/kira/relationships/MATRIX.json"),
            builder_source=_artifact("tools/aside_context_builder.py", kind="builder_source"),
            baseline_git_sha="not-a-sha",
        )


def test_baseline_source_set_accepts_valid_git_sha():
    baseline = _build_baseline()
    assert baseline.baseline_git_sha == _VALID_GIT_SHA


# ---------------------------------------------------------------------------
# PilotSourceSnapshot
# ---------------------------------------------------------------------------


def _build_full_p4_map() -> MappingProxyType:
    return MappingProxyType(
        {
            "high_arousal_low_anxiety": P4State(arousal="high", anxiety="low", strategy="approach"),
            "high_arousal_high_anxiety": P4State(arousal="high", anxiety="high", strategy="avoidance"),
            "low_arousal_high_anxiety": P4State(arousal="low", anxiety="high", strategy="seeking_reassurance"),
            "low_arousal_low_anxiety": P4State(arousal="low", anxiety="low", strategy="exploration"),
        }
    )


def _build_me1() -> MemoryEventSource:
    return MemoryEventSource(
        event_id="SC_008",
        scenario_repo_relative_path="scenarios/SCENARIO_008_HOME_EMBRACE.json",
        json_path="choice_points[0].branches[0].action",
        literal_text="Падает ему на грудь. Плачет. Не объясняет.",
        sha256=_VALID_SHA256,
        normalized_text="Кира падает ему на грудь. Плачет. Не объясняет.",
    )


def _build_me2() -> MemoryEventSource:
    return MemoryEventSource(
        event_id="SC_017",
        scenario_repo_relative_path="scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
        json_path="entry_beats[0].narration",
        literal_text="Телефон загорается новым сообщением от Сергея.",
        sha256=_VALID_SHA256,
    )


def test_pilot_source_snapshot_rejects_plain_dict_p4_map():
    with pytest.raises(ContractValidationError):
        PilotSourceSnapshot(
            p0=_build_p0_snapshot(),
            p3=P3State(trust=75, attraction=85),
            p4_strategy_map={
                "high_arousal_low_anxiety": P4State(arousal="high", anxiety="low", strategy="approach")
            },
            me1=_build_me1(),
            me2=_build_me2(),
            baseline=_build_baseline(),
            repo_head_sha=_VALID_GIT_SHA,
        )


def test_pilot_source_snapshot_rejects_incomplete_p4_map():
    incomplete = MappingProxyType(
        {"high_arousal_low_anxiety": P4State(arousal="high", anxiety="low", strategy="approach")}
    )
    with pytest.raises(ContractValidationError):
        PilotSourceSnapshot(
            p0=_build_p0_snapshot(),
            p3=P3State(trust=75, attraction=85),
            p4_strategy_map=incomplete,
            me1=_build_me1(),
            me2=_build_me2(),
            baseline=_build_baseline(),
            repo_head_sha=_VALID_GIT_SHA,
        )


def test_pilot_source_snapshot_accepts_fully_valid_construction():
    snapshot = PilotSourceSnapshot(
        p0=_build_p0_snapshot(),
        p3=P3State(trust=75, attraction=85),
        p4_strategy_map=_build_full_p4_map(),
        me1=_build_me1(),
        me2=_build_me2(),
        baseline=_build_baseline(),
        repo_head_sha=_VALID_GIT_SHA,
    )
    assert snapshot.p3.trust == 75
    assert snapshot.p3.attraction == 85
    assert len(snapshot.p4_strategy_map) == 4


def test_pilot_source_snapshot_is_immutable():
    snapshot = PilotSourceSnapshot(
        p0=_build_p0_snapshot(),
        p3=P3State(trust=75, attraction=85),
        p4_strategy_map=_build_full_p4_map(),
        me1=_build_me1(),
        me2=_build_me2(),
        baseline=_build_baseline(),
        repo_head_sha=_VALID_GIT_SHA,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.repo_head_sha = "c" * 40  # type: ignore[misc]
