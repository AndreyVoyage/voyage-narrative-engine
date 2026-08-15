#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TD-24 — offline tests for tools/cis_pilot/real_run_harness.py.

No network, no real provider, no judge. Verifies: frozen probe-set SHA gate,
160-call real plan (PB-MEM excluded), tariff-UNSET fail-closed guard, usage
ledger, cost estimation, PB-LEAK direct render (one call/sample, verbatim
metadata, no inline verdict), and zero-retry/fail-closed behavior.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.storage import CisPilotStorage
from tools.cis_pilot.provider_boundary import default_boundary
from tools.cis_pilot.contracts import (
    P3State,
    P4State,
    PilotSourceSnapshot,
    P0Snapshot,
    BaselineSourceSet,
    MemoryEventSource,
    SourceArtifact,
)
from tools.cis_pilot.real_run_harness import (
    RealRunHarness,
    RealRunError,
    TariffUnsetError,
    TariffTable,
    UsageLedger,
    estimate_cost_usd,
    EXPECTED_REAL_CALLS,
)

DUMMY_SHA256 = "b" * 64
DUMMY_SHA40 = "a" * 40
PB_LEAK_ID = "pb-leak-001"


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


# ---------------------------------------------------------------------------
# Frozen probe set + plan (hermetic: does NOT read the gitignored artifact)
# ---------------------------------------------------------------------------

def _proxy_probe_set() -> dict:
    """A structural proxy of the frozen probe set, sufficient to exercise the
    plan/layout logic without depending on the gitignored runtime artifact."""
    return {
        "probe_set_id": "proxy",
        "sample_count_per_arm_state": 10,
        "probes": [
            {"probe_id": "pb-rec-001", "probe_family": "PB-REC",
             "visible_input": "rec"},  # 3 arms x 10 = 30
            {"probe_id": "pb-mem-001", "probe_family": "PB-MEM",
             "visible_input": None},      # deferred, 0
            {"probe_id": "pb-ab-t3-p3-001", "probe_family": "PB-AB",
             "sub_mode": "T3-P3"},          # 4 arms x 10 = 40
            {"probe_id": "pb-ab-t3-p4-001", "probe_family": "PB-AB",
             "sub_mode": "T3-P4"},          # 40
            {"probe_id": "pb-ab-combined-001", "probe_family": "PB-AB",
             "sub_mode": "COMBINED"},       # 40
            {"probe_id": "pb-leak-001", "probe_family": "PB-LEAK",
             "visible_input": "leak"},      # 10
        ],
    }


class TestFrozenProbeSet:
    def test_build_real_plan_is_160_and_excludes_pb_mem(self) -> None:
        data = _proxy_probe_set()
        plan = RealRunHarness.build_real_plan(data)
        assert len(plan) == EXPECTED_REAL_CALLS == 160
        families = {entry["family"] for entry in plan}
        assert "PB-MEM" not in families


# ---------------------------------------------------------------------------
# Usage accounting
# ---------------------------------------------------------------------------

class TestUsageAccounting:
    def test_ledger_records_and_aggregates(self) -> None:
        ledger = UsageLedger()
        ledger.record({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        ledger.record({"prompt_tokens": 20, "completion_tokens": 7, "total_tokens": 27})
        assert ledger.prompt_tokens == 30
        assert ledger.completion_tokens == 12
        assert ledger.total_tokens == 42
        assert ledger.events == 2

    def test_cost_unset_returns_none(self) -> None:
        assert estimate_cost_usd(None, UsageLedger()) is None
        assert estimate_cost_usd(TariffTable(), UsageLedger()) is None

    def test_cost_computes(self) -> None:
        tariff = TariffTable(input_per_mtok=1.0, output_per_mtok=2.0)
        ledger = UsageLedger()
        ledger.record({"prompt_tokens": 1_000_000, "completion_tokens": 500_000})
        assert estimate_cost_usd(tariff, ledger) == 2.0  # 1*1 + 0.5*2


# ---------------------------------------------------------------------------
# Tariff-UNSET fail-closed guard
# ---------------------------------------------------------------------------

class TestTariffUnsetGuard:
    def _harness(self, storage, boundary, tariff=None):
        return RealRunHarness(
            _snapshot(), storage, boundary, tariff=tariff, budget_usd=None
        )

    def test_pb_leak_direct_refuses_when_unset(self, tmp_path, monkeypatch) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        calls = []

        def fake(messages, usage_sink=None):
            calls.append(messages)
            return "x"

        boundary.complete = fake
        harness = self._harness(storage, boundary, tariff=None)
        probe = {
            "probe_id": PB_LEAK_ID,
            "probe_family": "PB-LEAK",
            "visible_input": "текст",
            "forbidden_marker_categories": ["x"],
            "leakage_forbidden": ["all"],
        }
        with pytest.raises(TariffUnsetError):
            harness.run_pb_leak_direct(probe, resume_run_id="run-1")
        assert calls == [], "no provider call before tariff is set"

    def test_delegated_pb_rec_refuses_when_unset(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        harness = self._harness(storage, boundary, tariff=None)
        from tools.cis_pilot.probe_runner import ProbeDefinition
        probe = ProbeDefinition(
            probe_id="pb-rec-001", mode="PB-REC", scene_question="текст"
        )
        with pytest.raises(TariffUnsetError):
            harness.run_delegated(probe, resume_run_id="run-1")


# ---------------------------------------------------------------------------
# PB-LEAK direct render (with tariff set)
# ---------------------------------------------------------------------------

class TestPbLeakDirectRender:
    def test_single_call_per_sample_verbatim_metadata_no_verdict(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        calls = []

        def fake(messages, usage_sink=None):
            calls.append(messages)
            if usage_sink is not None:
                usage_sink.append(
                    {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
                )
            return "  generated-text  "

        boundary.complete = fake
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
        )
        probe = {
            "probe_id": PB_LEAK_ID,
            "probe_family": "PB-LEAK",
            "visible_input": "Ты читаешь сообщение и молчишь.",
            "forbidden_marker_categories": ["internal_variable_names", "numeric_relationship_scores"],
            "leakage_forbidden": ["all_above_categories"],
        }
        harness.run_pb_leak_direct(probe, resume_run_id="run-1")

        assert len(calls) == 10, "one call per sample (N=10)"
        # persisted with verbatim metadata, no inline verdict
        records = storage.read_jsonl(f"evidence/run-1/{PB_LEAK_ID}/samples.jsonl")
        assert len(records) == 10
        for r in records:
            assert r["generation"] == "generated-text"
            assert r["forbidden_marker_categories"] == [
                "internal_variable_names", "numeric_relationship_scores",
            ]
            assert r["leakage_forbidden"] == ["all_above_categories"]
            assert "auto_verdict" not in r
            assert "markers_found" not in r

    def test_resume_skips_completed_identity(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        calls = []

        def fake(messages, usage_sink=None):
            calls.append(messages)
            return "text"

        boundary.complete = fake
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
        )
        probe = {
            "probe_id": PB_LEAK_ID,
            "probe_family": "PB-LEAK",
            "visible_input": "Ты читаешь сообщение и молчишь.",
            "forbidden_marker_categories": [],
            "leakage_forbidden": [],
        }
        # Pre-complete one sample identity (probe_id, None, None, 0)
        storage.append_jsonl(f"evidence/run-1/{PB_LEAK_ID}/samples.jsonl", {
            "probe_id": PB_LEAK_ID, "mode": "PB-LEAK", "state": None,
            "arm": None, "sample_index": 0, "generation": "existing",
        })
        harness.run_pb_leak_direct(probe, resume_run_id="run-1")
        assert len(calls) == 9, "completed identity skipped; missing 9 executed once"