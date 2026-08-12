#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5 — Baseline A/B arm isolation tests for PB-AB.

Verifies: BASELINE_A and BASELINE_B arms in T3-P3, T3-P4, and COMBINED
modes; static baseline context identical for both arms; baseline arms
receive no P3/P4 injection; CIS arms maintain correct causal isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.contracts import (
    P3State,
    P4State,
    PilotSourceSnapshot,
    P0Snapshot,
    BaselineSourceSet,
    MemoryEventSource,
    SourceArtifact,
)
from tools.cis_pilot.storage import CisPilotStorage
from tools.cis_pilot.probe_runner import (
    ProbeRunner,
    ProbeRunConfig,
    ProbeDefinition,
    ProbeRunnerError,
    default_boundary,
)

DUMMY_SHA256 = "b" * 64
DUMMY_SHA40 = "a" * 40


def _artifact(path: str, kind: str = "p0_module") -> SourceArtifact:
    return SourceArtifact(repo_relative_path=path, sha256=DUMMY_SHA256, kind=kind)


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
        event_id="me1",
        scenario_repo_relative_path="scenarios/synth.json",
        json_path="beats[0].action",
        literal_text="synthetic event text",
        sha256=DUMMY_SHA256,
    )
    me2 = MemoryEventSource(
        event_id="me2",
        scenario_repo_relative_path="scenarios/synth2.json",
        json_path="beats[1].action",
        literal_text="synthetic event text 2",
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


@pytest.fixture
def storage(tmp_path: Path) -> CisPilotStorage:
    return CisPilotStorage(tmp_path)


@pytest.fixture
def runner(storage: CisPilotStorage) -> ProbeRunner:
    return ProbeRunner(_snapshot(), storage)


def _ab_probe(sub_modes=("T3-P3",)) -> ProbeDefinition:
    return ProbeDefinition(
        probe_id="synth-pb-ab-001", mode="PB-AB",
        scene_question="Baseline isolation test.",
        sub_modes=sub_modes,
    )


# ---------------------------------------------------------------------------
# Baseline arm existence — T3-P3
# ---------------------------------------------------------------------------

class TestBaselineArmsT3P3:
    """S5: T3-P3 produces 4 arm classes: CIS A, CIS B, BASELINE_A, BASELINE_B."""

    def test_t3_p3_has_four_arm_classes(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=2)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        arms = {s.arm for s in pkg.samples}
        assert arms == {"A", "B", "BASELINE_A", "BASELINE_B"}

    def test_t3_p3_baseline_arms_have_tags(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        for arm_name in ("BASELINE_A", "BASELINE_B"):
            baseline_samples = [s for s in pkg.samples if s.arm == arm_name]
            assert len(baseline_samples) >= 1, f"No samples for {arm_name}"
            for s in baseline_samples:
                assert "baseline" in s.tags
                assert arm_name.lower() in s.tags

    def test_t3_p3_n10_per_baseline_arm(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        for arm_name in ("BASELINE_A", "BASELINE_B"):
            baseline_samples = [s for s in pkg.samples if s.arm == arm_name]
            assert len(baseline_samples) == 10, f"Expected N=10 for {arm_name}, got {len(baseline_samples)}"

    def test_t3_p3_total_sample_count_n10(self, runner: ProbeRunner) -> None:
        """T3-P3 N=10: 4 arms × 10 = 40 samples total."""
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        assert len(pkg.samples) == 40, f"Expected 40 samples, got {len(pkg.samples)}"

    def test_t3_p3_sample_indices_complete(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=5)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        for arm_name in ("A", "B", "BASELINE_A", "BASELINE_B"):
            indices = sorted(s.sample_index for s in pkg.samples if s.arm == arm_name)
            assert indices == list(range(5)), f"{arm_name}: expected 0..4, got {indices}"


# ---------------------------------------------------------------------------
# Baseline arm existence — T3-P4
# ---------------------------------------------------------------------------

class TestBaselineArmsT3P4:
    """S5: T3-P4 produces 4 arm classes: CIS A, CIS B, BASELINE_A, BASELINE_B."""

    def test_t3_p4_has_four_arm_classes(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=2)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        arms = {s.arm for s in pkg.samples}
        assert arms == {"A", "B", "BASELINE_A", "BASELINE_B"}

    def test_t3_p4_baseline_arms_exist(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        baseline_arms = {s.arm for s in pkg.samples if s.arm in ("BASELINE_A", "BASELINE_B")}
        assert baseline_arms == {"BASELINE_A", "BASELINE_B"}

    def test_t3_p4_total_sample_count_n10(self, runner: ProbeRunner) -> None:
        """T3-P4 N=10: 4 arms × 10 = 40 samples total."""
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        assert len(pkg.samples) == 40, f"Expected 40 samples, got {len(pkg.samples)}"

    def test_t3_p4_no_duplicate_identities(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=3)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        keys = [s.sample_key() for s in pkg.samples]
        assert len(keys) == len(set(keys)), "Duplicate sample identities detected"


# ---------------------------------------------------------------------------
# Baseline arm existence — COMBINED
# ---------------------------------------------------------------------------

class TestBaselineArmsCombined:
    """S5: COMBINED also produces BASELINE_A/B arms."""

    def test_combined_has_baseline_arms(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("COMBINED",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="COMBINED")
        arms = {s.arm for s in pkg.samples}
        assert "BASELINE_A" in arms
        assert "BASELINE_B" in arms


# ---------------------------------------------------------------------------
# Baseline A/B static context invariant
# ---------------------------------------------------------------------------

class TestBaselineABStaticInvariant:
    """BASELINE_A and BASELINE_B must receive identical static input."""

    def test_baseline_a_b_same_input_t3_p3(self, runner: ProbeRunner) -> None:
        """BASELINE_A and BASELINE_B use the same external input and baseline context."""
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=3)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        a_gens = [s.generation for s in pkg.samples if s.arm == "BASELINE_A"]
        b_gens = [s.generation for s in pkg.samples if s.arm == "BASELINE_B"]
        assert a_gens == b_gens, (
            "BASELINE_A and BASELINE_B must produce identical output "
            "(same input, same static baseline context)"
        )

    def test_baseline_a_b_same_input_t3_p4(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=2)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        a_gens = [s.generation for s in pkg.samples if s.arm == "BASELINE_A"]
        b_gens = [s.generation for s in pkg.samples if s.arm == "BASELINE_B"]
        assert a_gens == b_gens, (
            "BASELINE_A and BASELINE_B must produce identical output for T3-P4"
        )

    def test_baseline_arm_has_no_cis_tags(self, runner: ProbeRunner) -> None:
        """BASELINE_A/B must NOT be tagged with CIS-specific markers."""
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        for s in pkg.samples:
            if s.arm in ("BASELINE_A", "BASELINE_B"):
                assert "pb-ab" not in s.tags, f"{s.arm} incorrectly tagged pb-ab"


# ---------------------------------------------------------------------------
# CIS arm isolation — T3-P3
# ---------------------------------------------------------------------------

class TestCisArmIsolationT3P3:
    """PD-3: T3-P3 — only trust varies; CIS arms correct even with baseline present."""

    def test_t3_p3_trust_differs(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        ip3 = pkg.initial_p3
        assert ip3 is not None
        assert ip3["trust_A"] == 75
        assert ip3["trust_B"] == 55
        assert ip3["trust_A"] != ip3["trust_B"]
        assert ip3["attraction"] == 85

    def test_t3_p3_cis_arms_present(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        cis_arms = {s.arm for s in pkg.samples if s.arm in ("A", "B")}
        assert cis_arms == {"A", "B"}


# ---------------------------------------------------------------------------
# CIS arm isolation — T3-P4
# ---------------------------------------------------------------------------

class TestCisArmIsolationT3P4:
    """PD-4: T3-P4 — arousal=high fixed in both; only anxiety varies."""

    def test_t3_p4_only_anxiety_varies(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        assert ip4["A"]["arousal"] == ip4["B"]["arousal"] == "high"
        assert ip4["A"]["anxiety"] == "low"
        assert ip4["B"]["anxiety"] == "high"
        assert ip4["A"]["anxiety"] != ip4["B"]["anxiety"]

    def test_t3_p4_p3_fixed(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip3 = pkg.initial_p3
        assert ip3 is not None
        assert ip3["trust_A"] == 75
        assert ip3["trust_B"] == 75
        assert ip3["attraction"] == 85


# ---------------------------------------------------------------------------
# N=10 full matrix validation
# ---------------------------------------------------------------------------

class TestN10FullMatrix:
    """S5: N=10 sample matrix validation for all PB-AB sub-modes."""

    @pytest.mark.parametrize("sub_mode", ["T3-P3", "T3-P4", "COMBINED"])
    def test_n10_total_samples(self, runner: ProbeRunner, sub_mode: str) -> None:
        """Each sub-mode at N=10 produces 40 samples (4 arms × 10)."""
        config = ProbeRunConfig(probe=_ab_probe((sub_mode,)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode=sub_mode)
        assert len(pkg.samples) == 40

    @pytest.mark.parametrize("sub_mode", ["T3-P3", "T3-P4", "COMBINED"])
    def test_n10_all_arms_represented(self, runner: ProbeRunner, sub_mode: str) -> None:
        expected = {"A", "B", "BASELINE_A", "BASELINE_B"}
        config = ProbeRunConfig(probe=_ab_probe((sub_mode,)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode=sub_mode)
        arms = {s.arm for s in pkg.samples}
        assert arms == expected

    @pytest.mark.parametrize("sub_mode", ["T3-P3", "T3-P4", "COMBINED"])
    def test_n10_complete_indices_per_arm(self, runner: ProbeRunner, sub_mode: str) -> None:
        config = ProbeRunConfig(probe=_ab_probe((sub_mode,)), samples_per_arm=10)
        pkg = runner.run_pb_ab(config, sub_mode=sub_mode)
        for arm_name in ("A", "B", "BASELINE_A", "BASELINE_B"):
            indices = sorted(s.sample_index for s in pkg.samples if s.arm == arm_name)
            assert indices == list(range(10)), f"{arm_name}: expected 0..9, got {indices}"


# ---------------------------------------------------------------------------
# Deterministic reproducibility with baseline arms
# ---------------------------------------------------------------------------

class TestDeterministicReproducibility:
    """Same config + same mock provider -> same deterministic payload with baseline."""

    def test_t3_p3_deterministic(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=2)
        a = runner.run_pb_ab(config, sub_mode="T3-P3").deterministic_payload()
        b = runner.run_pb_ab(config, sub_mode="T3-P3").deterministic_payload()
        assert a == b

    def test_t3_p4_deterministic(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P4",)), samples_per_arm=2)
        a = runner.run_pb_ab(config, sub_mode="T3-P4").deterministic_payload()
        b = runner.run_pb_ab(config, sub_mode="T3-P4").deterministic_payload()
        assert a == b


# ---------------------------------------------------------------------------
# Arm identity metadata
# ---------------------------------------------------------------------------

class TestArmIdentity:
    """Every sample must carry explicit arm metadata."""

    def test_cis_arms_identified(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        for s in pkg.samples:
            assert s.arm is not None, f"Sample missing arm identity: {s!r}"
            assert isinstance(s.arm, str)

    def test_baseline_arms_explicit(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_ab_probe(("T3-P3",)), samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        baseline = [s for s in pkg.samples if s.arm in ("BASELINE_A", "BASELINE_B")]
        assert len(baseline) >= 2
        for s in baseline:
            assert "BASELINE_" in s.arm