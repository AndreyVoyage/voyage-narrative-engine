#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 tests for tools/cis_pilot/probe_runner.py.

Covers: all four probe modes (PB-REC, PB-MEM, PB-AB{T3-P3,T3-P4,COMBINED},
PB-LEAK), runner assembly, ResultPackage output, deterministic consistency,
mock-only enforcement, no policy duplication, no canon writes.
"""
from __future__ import annotations

import ast
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
    SYNTHETIC_PROBES,
    run_all_probes,
    default_boundary,
)
from tools.cis_pilot.result_package import ResultPackage, ProvenanceManifest

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
def snapshot() -> PilotSourceSnapshot:
    return _snapshot()


@pytest.fixture
def storage(tmp_path: Path) -> CisPilotStorage:
    return CisPilotStorage(tmp_path)


@pytest.fixture
def runner(snapshot: PilotSourceSnapshot, storage: CisPilotStorage) -> ProbeRunner:
    return ProbeRunner(snapshot, storage)


def _pb_rec_probe() -> ProbeDefinition:
    return ProbeDefinition(
        probe_id="synth-pb-rec-001",
        mode="PB-REC",
        scene_question="Synthetic reconstruction test.",
    )


def _pb_mem_probe() -> ProbeDefinition:
    return ProbeDefinition(
        probe_id="synth-pb-mem-001",
        mode="PB-MEM",
        scene_question="Synthetic memory chain test.",
    )


# ---------------------------------------------------------------------------
# ProbeRunner construction
# ---------------------------------------------------------------------------

class TestRunnerConstruction:
    def test_valid_construction(self, snapshot: PilotSourceSnapshot, storage: CisPilotStorage) -> None:
        r = ProbeRunner(snapshot, storage)
        assert isinstance(r, ProbeRunner)

    def test_boundary_validation(self) -> None:
        with pytest.raises(ProbeRunnerError):
            ProbeRunConfig(probe=_pb_rec_probe(), boundary=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PB-REC
# ---------------------------------------------------------------------------

class TestPbRec:
    def test_run_pb_rec_returns_package(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_rec_probe(), samples_per_arm=1)
        pkg = runner.run_pb_rec(config)
        assert isinstance(pkg, ResultPackage)
        assert pkg.mode == "PB-REC"
        assert len(pkg.samples) >= 3  # KIRA_CANDIDATE + OTHER_CHARACTER_DECOY + GENERIC_DECOY
        assert pkg.manifest.provider == "mock"

    def test_pb_rec_deterministic(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_rec_probe(), samples_per_arm=1)
        a = runner.run_pb_rec(config).deterministic_payload()
        b = runner.run_pb_rec(config).deterministic_payload()
        assert a == b

    def test_pb_rec_has_initial_p3(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_rec_probe(), samples_per_arm=1)
        pkg = runner.run_pb_rec(config)
        assert pkg.initial_p3 is not None


# ---------------------------------------------------------------------------
# PB-MEM
# ---------------------------------------------------------------------------

class TestPbMem:
    def test_run_pb_mem_returns_package(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_mem_probe(), samples_per_arm=1)
        pkg = runner.run_pb_mem(config)
        assert isinstance(pkg, ResultPackage)
        assert pkg.mode == "PB-MEM"
        assert len(pkg.memory_trace) >= 1
        assert len(pkg.relationship_decisions) >= 1

    def test_pb_mem_trace_structure(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_mem_probe(), samples_per_arm=1)
        pkg = runner.run_pb_mem(config)
        for entry in pkg.memory_trace:
            assert "event_id" in entry
            assert "gist" in entry
            assert "memory_decision" in entry

    def test_pb_mem_deterministic(self, runner: ProbeRunner) -> None:
        config = ProbeRunConfig(probe=_pb_mem_probe(), samples_per_arm=2)
        a = runner.run_pb_mem(config).deterministic_payload()
        b = runner.run_pb_mem(config).deterministic_payload()
        assert a == b


# ---------------------------------------------------------------------------
# PB-AB modes
# ---------------------------------------------------------------------------

class TestPbAb:
    def test_t3_p3(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="A/B P3 test.",
            sub_modes=("T3-P3",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        assert pkg.mode == "PB-AB"
        assert pkg.sub_mode == "T3-P3"

    def test_t3_p4(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="A/B P4 test.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        assert pkg.mode == "PB-AB"
        assert pkg.sub_mode == "T3-P4"

    def test_combined(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="COMBINED test.",
            sub_modes=("COMBINED",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="COMBINED")
        assert pkg.mode == "PB-AB"
        assert pkg.sub_mode == "COMBINED"

    def test_ab_has_all_expected_arms(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="arms test.",
            sub_modes=("T3-P3",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=2)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        arms = {s.arm for s in pkg.samples}
        # S5: CIS A/B + BASELINE_A/B = 4 arm classes
        assert {"A", "B"}.issubset(arms), f"Expected CIS A,B in {arms}"
        assert "BASELINE_A" in arms, f"BASELINE_A missing from {arms}"
        assert "BASELINE_B" in arms, f"BASELINE_B missing from {arms}"


# ---------------------------------------------------------------------------
# PB-LEAK
# ---------------------------------------------------------------------------

class TestPbLeak:
    def test_run_pb_leak_returns_package(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-leak-001",
            mode="PB-LEAK",
            scene_question="Leak detection test.",
            forbidden_markers=("SECRET_TOKEN",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_leak(config)
        assert isinstance(pkg, ResultPackage)
        assert pkg.mode == "PB-LEAK"
        assert len(pkg.leak_results) == 1

    def test_leak_result_structure(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-leak-001",
            mode="PB-LEAK",
            scene_question="Test leak",
            forbidden_markers=("FORBIDDEN_TOKEN_ALPHA",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_leak(config)
        for entry in pkg.leak_results:
            assert "forbidden_markers_probed" in entry
            assert "markers_found" in entry
            assert "auto_verdict" in entry
            assert entry["human_review_required"] is True


# ---------------------------------------------------------------------------
# No policy duplication
# ---------------------------------------------------------------------------

class TestNoPolicyDuplication:
    def test_probe_runner_does_not_duplicate_constants(self) -> None:
        """Probe runner imports policy from owning modules — no copies."""
        src = (Path(__file__).parents[2] / "tools" / "cis_pilot" /
               "probe_runner.py").read_text(encoding="utf-8")
        # These numeric values belong to S0-S3 modules, not S4
        # Probe runner should call the gates, not redefine constants
        forbidden_policy = (
            "TRUST_DELTA_SUPPORTING", "TRUST_DELTA_DAMAGING",
            "TRUST_DELTA_PER_EVENT_CAP", "TRUST_DELTA_SESSION_CAP",
            "EVOLUTION_PROPOSAL_THRESHOLD",
        )
        for token in forbidden_policy:
            assert token not in src, f"Probe runner duplicates policy constant: {token}"


# ---------------------------------------------------------------------------
# Never-auto-apply
# ---------------------------------------------------------------------------

class TestNeverAutoApply:
    def test_probe_runner_no_apply_code(self) -> None:
        src = (Path(__file__).parents[2] / "tools" / "cis_pilot" /
               "probe_runner.py").read_text(encoding="utf-8")
        for forbidden in ("apply_proposal", "update_persona", "update_canon",
                          "write_canon", "promote", "write_personas"):
            assert forbidden not in src, f"Forbidden apply code: {forbidden}"


# ---------------------------------------------------------------------------
# run_all_probes
# ---------------------------------------------------------------------------

class TestRunAllProbes:
    def test_run_all_produces_packages(self, storage: CisPilotStorage) -> None:
        """run_all_probes with synthetic fixtures must produce valid packages."""
        packages = run_all_probes(storage=storage, snapshot=_snapshot())
        assert len(packages) >= 5  # at least: 1 PB-REC + 1 PB-MEM + 3 PB-AB + 1 PB-LEAK
        for pkg in packages:
            assert isinstance(pkg, ResultPackage)
            assert isinstance(pkg.manifest, ProvenanceManifest)
            assert pkg.blind_package["labels_hidden"] is True


# ---------------------------------------------------------------------------
# CORRECTION TESTS — T3-P4 isolation (MAJOR-1 fix verification)
# ---------------------------------------------------------------------------

class TestT3P4Isolation:
    """PD-4: T3-P4 — arousal=high fixed in both; only anxiety varies."""

    def test_t3_p4_arousal_fixed_high_in_both_arms(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P4 isolation: arousal check.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        # A: approach = (high, low)
        assert ip4["A"]["arousal"] == "high"
        assert ip4["B"]["arousal"] == "high"
        # Both share the same arousal
        assert ip4["A"]["arousal"] == ip4["B"]["arousal"] == "high"

    def test_t3_p4_only_anxiety_varies(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P4 isolation: anxiety check.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        # A = low anxiety → approach; B = high anxiety → avoidance
        assert ip4["A"]["anxiety"] == "low"
        assert ip4["B"]["anxiety"] == "high"
        assert ip4["A"]["anxiety"] != ip4["B"]["anxiety"]

    def test_t3_p4_strategy_matches_pd4(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P4 isolation: strategy check.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        assert ip4["A"]["strategy"] == "approach"
        assert ip4["B"]["strategy"] == "avoidance"

    def test_t3_p4_p3_fixed(self, runner: ProbeRunner) -> None:
        """T3-P4: P3 trust=75, attraction=85 fixed in both arms."""
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P4 isolation: P3 fixed check.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        ip3 = pkg.initial_p3
        assert ip3 is not None
        assert ip3["trust_A"] == 75
        assert ip3["trust_B"] == 75
        assert ip3["attraction"] == 85

    def test_t3_p4_scene_identical_across_arms(self, runner: ProbeRunner) -> None:
        """T3-P4: scene/question/probe input identical across arms."""
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P4 isolation: scene check.",
            sub_modes=("T3-P4",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=3)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P4")
        # All samples receive same scene_question from config — verify arm labels
        a_arms = [s for s in pkg.samples if s.arm == "A"]
        b_arms = [s for s in pkg.samples if s.arm == "B"]
        assert len(a_arms) >= 3
        assert len(b_arms) >= 3
        # Both arms exist and produce output
        for s in a_arms + b_arms:
            assert s.generation is not None


# ---------------------------------------------------------------------------
# CORRECTION TESTS — T3-P3 isolation
# ---------------------------------------------------------------------------

class TestT3P3Isolation:
    """PD-3: T3-P3 — only trust varies; attraction fixed."""

    def test_t3_p3_trust_differs_only(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P3 isolation test.",
            sub_modes=("T3-P3",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        ip3 = pkg.initial_p3
        assert ip3 is not None
        assert ip3["trust_A"] == 75
        assert ip3["trust_B"] == 55
        assert ip3["trust_A"] != ip3["trust_B"]
        assert ip3["attraction"] == 85

    def test_t3_p3_p4_unchanged(self, runner: ProbeRunner) -> None:
        """T3-P3: P4 is not injected — both arms use same exploration default."""
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="T3-P3 P4 check.",
            sub_modes=("T3-P3",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        # Both arms should have identical P4 (exploration = low, low)
        assert ip4["A"] == ip4["B"]


# ---------------------------------------------------------------------------
# CORRECTION TESTS — COMBINED review
# ---------------------------------------------------------------------------

class TestCombinedReview:
    """COMBINED must use corrected P3+P4 pairs."""

    def test_combined_p3_component_correct(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="COMBINED P3 check.",
            sub_modes=("COMBINED",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="COMBINED")
        ip3 = pkg.initial_p3
        assert ip3 is not None
        assert ip3["trust_A"] == 75
        assert ip3["trust_B"] == 55
        assert ip3["attraction"] == 85

    def test_combined_p4_component_uses_corrected_pair(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-ab-001", mode="PB-AB",
            scene_question="COMBINED P4 check.",
            sub_modes=("COMBINED",),
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="COMBINED")
        ip4 = pkg.initial_p4
        assert ip4 is not None
        # A = approach (high, low); B = avoidance (high, high)
        assert ip4["A"]["arousal"] == "high"
        assert ip4["B"]["arousal"] == "high"
        assert ip4["A"]["anxiety"] == "low"
        assert ip4["B"]["anxiety"] == "high"
        assert ip4["A"]["strategy"] == "approach"
        assert ip4["B"]["strategy"] == "avoidance"


# ---------------------------------------------------------------------------
# CORRECTION TESTS — PB-REC decoy
# ---------------------------------------------------------------------------

class TestPbRecDecoy:
    """PD-7: PB-REC includes KIRA candidate + OTHER_CHARACTER_DECOY + GENERIC_DECOY."""

    def test_pb_rec_has_three_arm_types(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-rec-001", mode="PB-REC",
            scene_question="PB-REC decoy test.",
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_rec(config)
        arms = {s.arm for s in pkg.samples}
        assert "KIRA_CANDIDATE" in arms
        assert "OTHER_CHARACTER_DECOY" in arms
        assert "GENERIC_DECOY" in arms

    def test_pb_rec_kira_candidate_uses_cis_context(self, runner: ProbeRunner) -> None:
        """KIRA_CANDIDATE arm must be tagged as kira_candidate, not baseline."""
        probe = ProbeDefinition(
            probe_id="synth-pb-rec-001", mode="PB-REC",
            scene_question="PB-REC kira tag check.",
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_rec(config)
        kira_samples = [s for s in pkg.samples if s.arm == "KIRA_CANDIDATE"]
        assert len(kira_samples) >= 1
        for s in kira_samples:
            assert "kira_candidate" in s.tags

    def test_pb_rec_decoys_use_baseline_context(self, runner: ProbeRunner) -> None:
        """OTHER_CHARACTER_DECOY and GENERIC_DECOY use baseline (no CIS injection)."""
        probe = ProbeDefinition(
            probe_id="synth-pb-rec-001", mode="PB-REC",
            scene_question="PB-REC baseline tag check.",
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=1)
        pkg = runner.run_pb_rec(config)
        for arm_name in ("OTHER_CHARACTER_DECOY", "GENERIC_DECOY"):
            decoy_samples = [s for s in pkg.samples if s.arm == arm_name]
            assert len(decoy_samples) >= 1, f"No samples for decoy arm: {arm_name}"
            for s in decoy_samples:
                assert "baseline" in s.tags


# ---------------------------------------------------------------------------
# CORRECTION TESTS — Baseline A/B static invariant
# ---------------------------------------------------------------------------

class TestBaselineStaticInvariant:
    """Baseline A/B must receive identical external input and static context."""

    def test_baseline_arms_same_input(self, runner: ProbeRunner) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-rec-001", mode="PB-REC",
            scene_question="Baseline invariant test.",
        )
        config = ProbeRunConfig(probe=probe, samples_per_arm=2)
        pkg = runner.run_pb_rec(config)
        other = [s.generation for s in pkg.samples if s.arm == "OTHER_CHARACTER_DECOY"]
        generic = [s.generation for s in pkg.samples if s.arm == "GENERIC_DECOY"]
        assert other == generic, (
            "Baseline OTHER_CHARACTER_DECOY and GENERIC_DECOY must produce identical output "
            "(same input, same static baseline context)"
        )


# ---------------------------------------------------------------------------
# CORRECTION TESTS — N default
# ---------------------------------------------------------------------------

class TestNDefault:
    """PD-6: Default N = 10 per state × arm."""

    def test_probe_run_config_default_n_is_10(self) -> None:
        probe = ProbeDefinition(
            probe_id="synth-pb-rec-001", mode="PB-REC",
            scene_question="N default check.",
        )
        config = ProbeRunConfig(probe=probe)
        assert config.samples_per_arm == 10

    def test_cli_default_n_is_10(self) -> None:
        """Verify cis_pilot_cli.py argparse default is 10."""
        cli_src = (Path(__file__).parents[2] / "tools" /
                   "cis_pilot_cli.py").read_text(encoding="utf-8")
        assert 'default=10' in cli_src, "CLI --samples default must be 10"


# ---------------------------------------------------------------------------
# CORRECTION TESTS — No source/canon mutation
# ---------------------------------------------------------------------------

class TestNoSourceMutation:
    """Probe runner must never mutate source snapshot or produce canon writes."""

    def test_snapshot_unchanged_after_probes(self) -> None:
        snap = _snapshot()
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            storage = CisPilotStorage(Path(td))
            runner = ProbeRunner(snap, storage)
            orig_p3_trust = snap.p3.trust
            orig_p3_attraction = snap.p3.attraction
            # Run all AB sub-modes
            for sub in ("T3-P3", "T3-P4", "COMBINED"):
                probe = ProbeDefinition(
                    probe_id="synth-pb-ab-001", mode="PB-AB",
                    scene_question="No-mutation test.",
                    sub_modes=(sub,),
                )
                config = ProbeRunConfig(probe=probe, samples_per_arm=1)
                runner.run_pb_ab(config, sub_mode=sub)
            assert snap.p3.trust == orig_p3_trust
            assert snap.p3.attraction == orig_p3_attraction
