#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 tests for tools/cis_pilot/result_package.py.

No LLM, no network. Covers: ProvenanceManifest, blind package (labels
hidden), result package assembly, deterministic payload, volatile fields
separation, serialization round-trip, helper contracts.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict
import json

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import (
    ContractValidationError,
    P3State,
    P4State,
    PilotSourceSnapshot,
    P0Snapshot,
    BaselineSourceSet,
    MemoryEventSource,
    SourceArtifact,
)
from tools.cis_pilot.result_package import (
    ProbeSampleRecord,
    ProvenanceManifest,
    ResultPackage,
    assemble_result_package,
    generate_run_id,
    utc_now_iso,
    build_blind_package,
    build_human_judge_sheet,
    collect_source_artifacts,
    _blind_labels_hidden,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DUMMY_SHA256 = "b" * 64
DUMMY_SHA40 = "a" * 40


def _artifact(path: str, kind: str = "p0_module") -> SourceArtifact:
    return SourceArtifact(
        repo_relative_path=path,
        sha256=DUMMY_SHA256,
        kind=kind,
    )


def _snapshot() -> PilotSourceSnapshot:
    p0 = P0Snapshot(
        value_system=_artifact("personas/kira/psychology/VALUE_SYSTEM.json"),
        base=_artifact("personas/kira/psychology/BASE.json"),
        attachment=_artifact("personas/kira/psychology/ATTACHMENT.json"),
        defense_mechanisms=_artifact("personas/kira/psychology/DEFENSE_MECHANISMS.json"),
        ifs_parts=_artifact("personas/kira/psychology/IFS_PARTS.json"),
        odsc=_artifact("personas/kira/psychology/ODSC.json"),
    )
    p3 = P3State(trust=75, attraction=85)
    p4_map = MappingProxyType({
        ("high", "low"): P4State(arousal="high", anxiety="low", strategy="approach"),
        ("high", "high"): P4State(arousal="high", anxiety="high", strategy="avoidance"),
        ("low", "high"): P4State(arousal="low", anxiety="high", strategy="seeking_reassurance"),
        ("low", "low"): P4State(arousal="low", anxiety="low", strategy="exploration"),
    })
    me1 = MemoryEventSource(
        event_id="me1-event",
        scenario_repo_relative_path="scenarios/synth.json",
        json_path="beats[0].action",
        literal_text="test literal text",
        sha256=DUMMY_SHA256,
    )
    me2 = MemoryEventSource(
        event_id="me2-event",
        scenario_repo_relative_path="scenarios/synth2.json",
        json_path="beats[1].action",
        literal_text="test literal text 2",
        sha256=DUMMY_SHA256,
    )
    baseline = BaselineSourceSet(
        identity=_artifact("personas/kira/identity/IDENTITY.json", "identity"),
        base=_artifact("personas/kira/psychology/BASE.json", "baseline"),
        speech_matrix=_artifact("personas/kira/speech/MATRIX.json", "speech"),
        matrix=_artifact("personas/kira/relationships/MATRIX.json", "matrix"),
        builder_source=_artifact("tools/aside_context_builder.py", "builder"),
        baseline_git_sha=DUMMY_SHA40,
    )
    return PilotSourceSnapshot(
        p0=p0, p3=p3, p4_strategy_map=p4_map, me1=me1, me2=me2,
        baseline=baseline, repo_head_sha=DUMMY_SHA40,
    )


def _sample(idx: int, mode: str = "PB-REC") -> ProbeSampleRecord:
    return ProbeSampleRecord(
        probe_id=f"synth-{mode.lower()}-001",
        mode=mode,
        state="T3-P3" if mode == "PB-AB" else None,
        arm="A" if mode == "PB-AB" else None,
        sample_index=idx,
        generation=f"mock-generation-{mode}-{idx}",
        tags=("synthetic", mode.lower()),
    )


# ---------------------------------------------------------------------------
# ProbeSampleRecord
# ---------------------------------------------------------------------------


class TestProbeSampleRecord:
    def test_valid_round_trip(self) -> None:
        r = _sample(0)
        d = r.to_dict()
        r2 = ProbeSampleRecord.from_dict(d)
        assert r == r2

    def test_missing_field_fails(self) -> None:
        with pytest.raises(ContractValidationError):
            ProbeSampleRecord.from_dict({"probe_id": "x"})

    def test_invalid_sample_index(self) -> None:
        with pytest.raises(ContractValidationError):
            ProbeSampleRecord(probe_id="x", mode="PB-REC", state=None, arm=None, sample_index=-1, generation="g")


# ---------------------------------------------------------------------------
# generate_run_id / utc_now_iso
# ---------------------------------------------------------------------------


class TestRunIdentity:
    def test_generate_run_id_is_unique(self) -> None:
        a = generate_run_id()
        b = generate_run_id()
        assert a != b

    def test_utc_now_iso_format(self) -> None:
        ts = utc_now_iso()
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# ProvenanceManifest
# ---------------------------------------------------------------------------


class TestProvenanceManifest:
    def test_valid_manifest(self) -> None:
        snap = _snapshot()
        artifacts = collect_source_artifacts(snap)
        m = ProvenanceManifest(
            run_id="2024-01-01T000000Z-abc",
            timestamp="2024-01-01T00:00:00.000Z",
            repo_head_sha=DUMMY_SHA40,
            source_artifacts=artifacts,
            probe_set_version="1.0",
            probe_set_sha256=DUMMY_SHA256,
            provider="mock",
            model="mock-deterministic",
            params={},
            per_sample_refs=(_sample(0),),
        )
        assert m.run_id == "2024-01-01T000000Z-abc"
        d = m.to_dict()
        assert d["provider"] == "mock"

    def test_deterministic_payload_no_volatile(self) -> None:
        snap = _snapshot()
        artifacts = collect_source_artifacts(snap)
        m = ProvenanceManifest(
            run_id="run-aaa",
            timestamp="ts-bbb",
            repo_head_sha=DUMMY_SHA40,
            source_artifacts=artifacts,
            probe_set_version="1.0",
            probe_set_sha256=DUMMY_SHA256,
            provider="mock",
            model="mock-model",
            params={},
            per_sample_refs=(_sample(0),),
        )
        dp = m.deterministic_payload()
        assert "run_id" not in dp
        assert "timestamp" not in dp
        assert dp["repo_head_sha"] == DUMMY_SHA40


# ---------------------------------------------------------------------------
# Blind package
# ---------------------------------------------------------------------------


class TestBlindPackage:
    def test_labels_hidden(self) -> None:
        samples = tuple(_sample(i) for i in range(4))
        blind, key = build_blind_package(samples, seed=42)
        assert blind["labels_hidden"] is True
        assert len(blind["items"]) == 4
        # The blind package note mentions "probe_id" in its description, but
        # actual data items must never carry labels
        for item in blind["items"]:
            assert "probe_id" not in item
            assert "character_id" not in item
            assert "state" not in item
            assert "arm" not in item
        assert "character_id" not in str(blind)

    def test_randomization_key_separate(self) -> None:
        samples = tuple(_sample(i) for i in range(3))
        blind, key = build_blind_package(samples, seed=42)
        assert key["seed"] == 42
        assert "probe_id" in str(key)
        assert "blind_id" in str(key["mapping"][0])

    def test_reproducible_shuffle(self) -> None:
        samples = tuple(_sample(i) for i in range(5))
        a, _ = build_blind_package(samples, seed=42)
        b, _ = build_blind_package(samples, seed=42)
        assert a == b

    def test_different_seed_different_shuffle(self) -> None:
        samples = tuple(_sample(i) for i in range(5))
        a, _ = build_blind_package(samples, seed=42)
        b, _ = build_blind_package(samples, seed=99)
        assert a != b


# ---------------------------------------------------------------------------
# Human judge sheet
# ---------------------------------------------------------------------------


class TestJudgeSheet:
    def test_flat_structure(self) -> None:
        samples = tuple(_sample(i) for i in range(3))
        blind, _ = build_blind_package(samples, seed=42)
        sheet = build_human_judge_sheet(blind, mode="PB-LEAK")
        assert sheet["status"] == "PENDING_HUMAN_REVIEW"
        assert len(sheet["items"]) == 3

    def test_no_leading_questions(self) -> None:
        samples = tuple(_sample(i) for i in range(2))
        blind, _ = build_blind_package(samples, seed=42)
        sheet = build_human_judge_sheet(blind, mode="PB-REC")
        for item in sheet["items"]:
            assert item["verdict"] == ""


# ---------------------------------------------------------------------------
# ResultPackage assembly
# ---------------------------------------------------------------------------


class TestResultPackageAssembly:
    def test_assemble_complete_package(self) -> None:
        snap = _snapshot()
        samples = tuple(_sample(i) for i in range(2))
        provider_meta = {"provider": "mock", "model": "mock-model", "params": {}}
        pkg = assemble_result_package(
            run_id="test-run",
            timestamp="2024-01-01T00:00:00.000Z",
            mode="PB-REC",
            sub_mode=None,
            probe_set_version="1.0",
            probe_set_sha256=DUMMY_SHA256,
            fixture_identity="synth:test",
            snapshot=snap,
            provider_metadata=provider_meta,
            initial_p3={"trust": 75, "attraction": 85},
            initial_p4=None,
            samples=samples,
            seed=42,
        )
        assert pkg.run_id == "test-run"
        assert isinstance(pkg.manifest, ProvenanceManifest)
        assert pkg.blind_package["labels_hidden"] is True

    def test_deterministic_payload(self) -> None:
        snap = _snapshot()
        samples = tuple(_sample(i) for i in range(2))
        provider_meta = {"provider": "mock", "model": "mock-model", "params": {}}

        def make() -> ResultPackage:
            return assemble_result_package(
                run_id="r", timestamp="t", mode="PB-REC", sub_mode=None,
                probe_set_version="1.0", probe_set_sha256=DUMMY_SHA256,
                fixture_identity="synth:test", snapshot=snap,
                provider_metadata=provider_meta,
                initial_p3={"trust": 75}, initial_p4=None, samples=samples, seed=42,
            )

        a = make().deterministic_payload()
        b = make().deterministic_payload()
        assert a == b

    def test_serialization_round_trip(self) -> None:
        snap = _snapshot()
        samples = tuple(_sample(i) for i in range(1))
        provider_meta = {"provider": "mock", "model": "mock-model", "params": {}}
        pkg = assemble_result_package(
            run_id="test-run-2", timestamp="t", mode="PB-MEM", sub_mode=None,
            probe_set_version="1.0", probe_set_sha256=DUMMY_SHA256,
            fixture_identity="synth:test", snapshot=snap,
            provider_metadata=provider_meta,
            initial_p3={"trust": 75}, initial_p4=None, samples=samples, seed=42,
        )
        d = pkg.to_dict()
        assert d["kind"] == "cis_pilot_result_package"
        assert d["run_id"] == "test-run-2"
        assert len(d["samples"]) == 1

    def test_missing_provider_field_fails(self) -> None:
        snap = _snapshot()
        samples = tuple(_sample(0) for _ in range(1))
        with pytest.raises(ContractValidationError):
            assemble_result_package(
                run_id="r", timestamp="t", mode="PB-REC", sub_mode=None,
                probe_set_version="1.0", probe_set_sha256=DUMMY_SHA256,
                fixture_identity="synth:test", snapshot=snap,
                provider_metadata={"provider": "mock"},  # missing model, params
                initial_p3={"trust": 75}, initial_p4=None, samples=samples, seed=42,
            )

    def test_no_absolute_paths_in_output(self) -> None:
        snap = _snapshot()
        samples = tuple(_sample(i) for i in range(2))
        provider_meta = {"provider": "mock", "model": "mock-model", "params": {}}
        pkg = assemble_result_package(
            run_id="r", timestamp="t", mode="PB-REC", sub_mode=None,
            probe_set_version="1.0", probe_set_sha256=DUMMY_SHA256,
            fixture_identity="synth:test", snapshot=snap,
            provider_metadata=provider_meta,
            initial_p3={"trust": 75}, initial_p4=None, samples=samples, seed=42,
        )
        text = json.dumps(pkg.to_dict())
        assert "C:/" not in text
        assert "C:\\" not in text
        assert "c:/" not in text


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------


class TestDeterministicChecks:
    def test_labels_hidden_check_positive(self) -> None:
        blind = {"items": [{"blind_id": "B-0000", "generation": "x"}]}
        assert _blind_labels_hidden(blind) is True

    def test_labels_hidden_check_negative(self) -> None:
        blind = {"items": [{"blind_id": "B-0000", "probe_id": "leaked"}]}
        assert _blind_labels_hidden(blind) is False

    def test_labels_hidden_nested(self) -> None:
        blind = {"items": [{"nested": {"character_id": "kira"}}]}
        assert _blind_labels_hidden(blind) is False