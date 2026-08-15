#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S5 — Runner-level resume and storage continuation tests.

Verifies: partial run creation, resume of missing samples, completed-sample
skip, second resume zero-work, duplicate prevention, existing evidence
preservation, mismatch fail-close, deterministic continuation, JSONL
append/read semantics, and TD-24 per-probe evidence segregation.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

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
from tools.cis_pilot.storage import CisPilotStorage, CisPilotStorageConflictError
from tools.cis_pilot.probe_runner import (
    ProbeRunner,
    ProbeRunConfig,
    ProbeDefinition,
    ProbeRunnerError,
    default_boundary,
)
from tools.cis_pilot.result_package import (
    ProbeSampleRecord,
    generate_run_id,
)

DUMMY_SHA256 = "b" * 64
DUMMY_SHA40 = "a" * 40

_AB_PROBE_ID = "synth-pb-ab-001"


def _ab_evidence(run_id: str) -> str:
    """TD-24 per-probe evidence path for the AB test probe."""
    return f"evidence/{run_id}/{_AB_PROBE_ID}/samples.jsonl"


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


def _ab_probe() -> ProbeDefinition:
    return ProbeDefinition(
        probe_id=_AB_PROBE_ID, mode="PB-AB",
        scene_question="Resume test PB-AB.",
        sub_modes=("T3-P3",),
    )


def _counting_boundary():
    """Return (boundary, calls) where ``calls`` records every provider invocation.

    Provider-agnostic and offline: keeps the existing deterministic mock
    boundary while counting how many times ``complete`` is actually reached.
    """
    boundary = default_boundary()
    calls: list = []
    real = boundary.complete

    def counted(messages, usage_sink=None):
        calls.append(messages)
        return real(messages, usage_sink=usage_sink)

    boundary.complete = counted
    return boundary, calls


# ---------------------------------------------------------------------------
# Resume: partial run creation
# ---------------------------------------------------------------------------

class TestPartialRunCreation:
    """Create a partial evidence set, verify resume completes the remainder."""

    def test_create_partial_evidence_then_resume(self, storage: CisPilotStorage) -> None:
        """Write half the expected samples, then resume fills the rest."""
        run_id = generate_run_id()
        config = ProbeRunConfig(probe=_ab_probe(), samples_per_arm=3)
        snapshot = _snapshot()
        runner = ProbeRunner(snapshot, storage)

        # First: create partial evidence by persisting only CIS A samples
        evidence_path = _ab_evidence(run_id)
        for idx in range(3):
            record = {
                "probe_id": _AB_PROBE_ID,
                "mode": "PB-AB",
                "state": "T3-P3",
                "arm": "A",
                "sample_index": idx,
                "generation": f"[pre-seeded] A-{idx}",
                "tags": ["synthetic", "pb-ab"],
            }
            storage.append_jsonl(evidence_path, record)

        # Resume with same run_id
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        assert pkg.run_id == run_id

        # All 4 arms × 3 samples should be represented in the result package
        arms = {s.arm for s in pkg.samples}
        assert arms == {"A", "B", "BASELINE_A", "BASELINE_B"}

        # After resume: verify prior evidence is preserved (A samples reused)
        persisted = storage.read_jsonl(evidence_path)
        a_records = [r for r in persisted if r["arm"] == "A"]
        assert len(a_records) == 3, "Pre-seeded A evidence must still exist unchanged"

    def test_full_run_then_resume_zero_new(self, storage: CisPilotStorage) -> None:
        """A completed resume run is idempotent: the second resume makes zero
        provider calls and leaves persisted evidence byte-identical."""
        run_id = generate_run_id()
        boundary = default_boundary()
        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=2)
        snapshot = _snapshot()
        runner = ProbeRunner(snapshot, storage)

        # First run: generates and auto-persists every sample (resume path)
        pkg1 = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        evidence_path = _ab_evidence(run_id)
        persisted_before = storage.read_jsonl(evidence_path)
        assert len(persisted_before) == len(pkg1.samples)

        # Second resume must not invoke the provider at all.
        calls: list = []

        def fail_if_called(messages, usage_sink=None):
            calls.append(messages)
            raise AssertionError("provider must not be invoked on a completed resume")

        boundary.complete = fail_if_called

        pkg2 = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        assert calls == [], "zero-work resume must make zero provider calls"
        assert pkg2.deterministic_payload() == pkg1.deterministic_payload()

        persisted_after = storage.read_jsonl(evidence_path)
        assert persisted_after == persisted_before, "resume must not mutate existing evidence"


# ---------------------------------------------------------------------------
# Resume: JSONL append/read semantics
# ---------------------------------------------------------------------------

class TestJsonlAppendRead:
    """Verify JSONL append creates new records without overwriting existing ones."""

    def test_jsonl_append_preserves_existing(self, storage: CisPilotStorage) -> None:
        path = "evidence/test-001/samples.jsonl"
        record_a = {"probe_id": "x", "arm": "A", "sample_index": 0}
        storage.append_jsonl(path, record_a)
        first = storage.read_jsonl(path)
        assert len(first) == 1

        record_b = {"probe_id": "x", "arm": "B", "sample_index": 1}
        storage.append_jsonl(path, record_b)
        second = storage.read_jsonl(path)
        assert len(second) == 2
        assert second[0] == record_a
        assert second[1] == record_b

    def test_jsonl_empty_file_returns_empty(self, storage: CisPilotStorage) -> None:
        records = storage.read_jsonl("evidence/nonexistent/samples.jsonl")
        assert records == []


# ---------------------------------------------------------------------------
# Resume: identity rule
# ---------------------------------------------------------------------------

class TestResumeIdentity:
    """Sample identity = (probe_id, state, arm, sample_index)."""

    def test_sample_key_composition(self) -> None:
        s = ProbeSampleRecord(
            probe_id=_AB_PROBE_ID,
            mode="PB-AB",
            state="T3-P3",
            arm="A",
            sample_index=5,
            generation="test",
        )
        assert s.sample_key() == (_AB_PROBE_ID, "T3-P3", "A", 5)

    def test_load_completed_keys(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        snapshot = _snapshot()
        runner = ProbeRunner(snapshot, storage)

        # Pre-seed two records in the per-probe evidence file
        evidence_path = _ab_evidence(run_id)
        storage.append_jsonl(evidence_path, {
            "probe_id": _AB_PROBE_ID, "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "x",
        })
        storage.append_jsonl(evidence_path, {
            "probe_id": _AB_PROBE_ID, "state": "T3-P3",
            "arm": "B", "sample_index": 7, "generation": "y",
        })

        keys = runner._load_completed_keys(run_id, _AB_PROBE_ID)
        assert (_AB_PROBE_ID, "T3-P3", "A", 0) in keys
        assert (_AB_PROBE_ID, "T3-P3", "B", 7) in keys
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# Resume: mismatch fail-close
# ---------------------------------------------------------------------------

class TestResumeMismatch:
    """Resume must fail closed when existing evidence conflicts."""

    def test_different_probe_id_fails(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        snapshot = _snapshot()
        runner = ProbeRunner(snapshot, storage)

        # Seed the AB probe's evidence file with a wrong probe_id record
        evidence_path = _ab_evidence(run_id)
        storage.append_jsonl(evidence_path, {
            "probe_id": "WRONG_PROBE", "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "x",
        })

        config = ProbeRunConfig(probe=_ab_probe(), samples_per_arm=1)
        with pytest.raises(ProbeRunnerError, match="mismatch"):
            runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)


# ---------------------------------------------------------------------------
# Storage root protection
# ---------------------------------------------------------------------------

class TestStorageRootProtection:
    """Storage base path must not be a canon directory."""

    def test_canon_personas_rejected(self) -> None:
        with pytest.raises(Exception):
            CisPilotStorage("personas")

    def test_canon_scenarios_rejected(self) -> None:
        with pytest.raises(Exception):
            CisPilotStorage("scenarios")

    def test_canon_governance_rejected(self) -> None:
        with pytest.raises(Exception):
            CisPilotStorage("governance")


# ---------------------------------------------------------------------------
# No overwrite of existing evidence
# ---------------------------------------------------------------------------

class TestNoOverwrite:
    """JSONL append never overwrites existing records."""

    def test_append_does_not_truncate(self, storage: CisPilotStorage) -> None:
        path = "evidence/test-no-overwrite/samples.jsonl"
        storage.append_jsonl(path, {"a": 1, "b": 2})
        storage.append_jsonl(path, {"c": 3, "d": 4})
        records = storage.read_jsonl(path)
        assert len(records) == 2
        assert records[0] == {"a": 1, "b": 2}
        assert records[1] == {"c": 3, "d": 4}

    def test_json_write_fail_if_exists(self, storage: CisPilotStorage) -> None:
        path = "results/test-conflict/data.json"
        storage.write_json(path, {"v": 1})
        with pytest.raises(CisPilotStorageConflictError):
            storage.write_json(path, {"v": 2})


# ---------------------------------------------------------------------------
# Deterministic continuation
# ---------------------------------------------------------------------------

class TestDeterministicContinuation:
    """Same config + same resume_run_id = same deterministic results."""

    def test_resume_idempotent_output(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        snapshot = _snapshot()
        runner = ProbeRunner(snapshot, storage)
        config = ProbeRunConfig(probe=_ab_probe(), samples_per_arm=2)

        pkg1 = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        payload1 = pkg1.deterministic_payload()

        pkg2 = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        payload2 = pkg2.deterministic_payload()

        assert payload1 == payload2


# ---------------------------------------------------------------------------
# TD-21 — bounded real-run resume completion (skip / no-overwrite / fail-closed)
# ---------------------------------------------------------------------------

class TestTd21ResumeSkip:
    """Completed identities are skipped before any provider call; missing
    identities execute exactly once."""

    def test_completed_identity_skipped_before_provider_call(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary, calls = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)

        evidence_path = _ab_evidence(run_id)
        storage.append_jsonl(evidence_path, {
            "probe_id": _AB_PROBE_ID, "mode": "PB-AB", "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "[pre-completed] A-0",
            "tags": ["synthetic", "pb-ab", "t3-p3"],
        })

        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        # A-0 reused without a provider call; B-0 + BASELINE_A-0 + BASELINE_B-0 fresh
        assert len(calls) == 3
        a0 = next(s for s in pkg.samples if s.arm == "A" and s.sample_index == 0)
        assert a0.generation == "[pre-completed] A-0"

        persisted = storage.read_jsonl(evidence_path)
        identities = [(r["probe_id"], r["state"], r["arm"], r["sample_index"]) for r in persisted]
        assert len(identities) == 4
        assert len(set(identities)) == 4, "no duplicate identities after resume"

    def test_incomplete_identity_executes(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary, calls = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)

        storage.append_jsonl(_ab_evidence(run_id), {
            "probe_id": _AB_PROBE_ID, "mode": "PB-AB", "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "[seeded]", "tags": [],
        })

        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=1)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        b0 = next(s for s in pkg.samples if s.arm == "B" and s.sample_index == 0)
        assert b0.generation != "[seeded]"
        assert len(calls) == 3, "missing B + baselines must each execute once"


class TestTd21EvidenceImmutability:
    def test_existing_evidence_not_overwritten(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary, _ = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)

        evidence_path = _ab_evidence(run_id)
        storage.append_jsonl(evidence_path, {
            "probe_id": _AB_PROBE_ID, "mode": "PB-AB", "state": "T3-P3",
            "arm": "A", "sample_index": 1, "generation": "ORIGINAL-EVIDENCE",
            "tags": ["synthetic", "pb-ab"],
        })

        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=2)
        pkg = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        a1 = next(s for s in pkg.samples if s.arm == "A" and s.sample_index == 1)
        assert a1.generation == "ORIGINAL-EVIDENCE"

        persisted = storage.read_jsonl(evidence_path)
        a1_records = [r for r in persisted if r["arm"] == "A" and r["sample_index"] == 1]
        assert len(a1_records) == 1
        assert a1_records[0]["generation"] == "ORIGINAL-EVIDENCE"


class TestTd21FailClosed:
    def test_duplicate_identity_fail_closed(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary, calls = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)

        evidence_path = _ab_evidence(run_id)
        record = {
            "probe_id": _AB_PROBE_ID, "mode": "PB-AB", "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "dup", "tags": [],
        }
        storage.append_jsonl(evidence_path, record)
        storage.append_jsonl(evidence_path, record)

        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=1)
        with pytest.raises(ProbeRunnerError, match="duplicate"):
            runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        assert calls == [], "duplicate evidence must fail closed before any provider call"
        assert len(storage.read_jsonl(evidence_path)) == 2, "no new evidence appended"

    def test_malformed_evidence_fail_closed(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary, calls = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)

        evidence_path = storage.base_path / _ab_evidence(run_id)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("{ this is not valid json\n", encoding="utf-8")

        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=1)
        with pytest.raises(ProbeRunnerError, match="malformed"):
            runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        assert calls == []


class TestTd21ProviderFailure:
    def test_provider_failure_persists_only_completed_evidence(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        boundary = default_boundary()
        real = boundary.complete
        call_count = [0]

        def flaky(messages, usage_sink=None):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise RuntimeError("simulated provider failure")
            return real(messages, usage_sink=usage_sink)

        boundary.complete = flaky
        runner = ProbeRunner(_snapshot(), storage)
        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=2)

        with pytest.raises(RuntimeError, match="simulated provider failure"):
            runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)

        persisted = storage.read_jsonl(_ab_evidence(run_id))
        assert len(persisted) == 1
        assert persisted[0]["arm"] == "A" and persisted[0]["sample_index"] == 0
        assert call_count[0] == 2, "no hidden automatic retry after failure"

    def test_resume_after_failure_skips_completed_retries_missing_once(self, storage: CisPilotStorage) -> None:
        run_id = generate_run_id()
        storage.append_jsonl(_ab_evidence(run_id), {
            "probe_id": _AB_PROBE_ID, "mode": "PB-AB", "state": "T3-P3",
            "arm": "A", "sample_index": 0, "generation": "[survived]", "tags": [],
        })
        boundary, calls = _counting_boundary()
        runner = ProbeRunner(_snapshot(), storage)
        config = ProbeRunConfig(probe=_ab_probe(), boundary=boundary, samples_per_arm=1)

        pkg = runner.run_pb_ab(config, sub_mode="T3-P3", resume_run_id=run_id)
        a0 = next(s for s in pkg.samples if s.arm == "A" and s.sample_index == 0)
        assert a0.generation == "[survived]"
        assert len(calls) == 3, "completed A-0 skipped; missing B + baselines executed once each"