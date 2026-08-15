#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TD-24/26A — offline tests for tools/cis_pilot/real_run_harness.py.

No network, no real provider, no judge. Verifies: 180-call real plan (PB-MEM
included at 2 calls/sample), tariff-UNSET fail-closed guard, durable usage
accounting (PB-MEM call #1 survives call #2 failure), PB-LEAK direct render
(verbatim metadata, no inline verdict), and zero-retry/fail-closed behavior.
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
    DurableUsageSink,
    load_cumulative_usage,
    estimate_cost_usd,
    EXPECTED_REAL_CALLS,
)

DUMMY_SHA256 = "b" * 64
DUMMY_SHA40 = "a" * 40
PB_LEAK_ID = "pb-leak-001"
PB_MEM_ID = "pb-mem-001"


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


def _proxy_probe_set() -> dict:
    """Structural proxy of the frozen probe set (hermetic; no gitignored I/O)."""
    return {
        "probe_set_id": "proxy",
        "sample_count_per_arm_state": 10,
        "probes": [
            {"probe_id": "pb-rec-001", "probe_family": "PB-REC",
             "visible_input": "rec"},  # 30
            {"probe_id": "pb-mem-001", "probe_family": "PB-MEM",        # 20 (2/sample)
             "objective_event": "Падает ему на грудь. Плачет.",
             "perception_hint": "Кто-то рядом понял её без слов."},
            {"probe_id": "pb-ab-t3-p3-001", "probe_family": "PB-AB",
             "sub_mode": "T3-P3"},                                     # 40
            {"probe_id": "pb-ab-t3-p4-001", "probe_family": "PB-AB",
             "sub_mode": "T3-P4"},                                     # 40
            {"probe_id": "pb-ab-combined-001", "probe_family": "PB-AB",
             "sub_mode": "COMBINED"},                                  # 40
            {"probe_id": "pb-leak-001", "probe_family": "PB-LEAK",
             "visible_input": "leak"},                                 # 10
        ],
    }


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

class TestPlan:
    def test_plan_is_180_and_includes_pb_mem(self) -> None:
        plan = RealRunHarness.build_real_plan(_proxy_probe_set())
        assert len(plan) == EXPECTED_REAL_CALLS == 180
        families = {entry["family"] for entry in plan}
        assert "PB-MEM" in families
        pb_mem = [e for e in plan if e["family"] == "PB-MEM"]
        assert len(pb_mem) == 20
        assert {e["call_phase"] for e in pb_mem} == {"interpretation", "gist"}


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
        assert estimate_cost_usd(tariff, ledger) == 2.0

    def test_durable_sink_and_reload(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        sink_interp = DurableUsageSink(storage, "run-1", phase="interpretation")
        sink_gist = DurableUsageSink(storage, "run-1", phase="gist")
        sink_interp.append({"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140})
        sink_gist.append({"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100})

        loaded = load_cumulative_usage(storage, "run-1")
        assert loaded.prompt_tokens == 180
        assert loaded.completion_tokens == 60
        assert loaded.total_tokens == 240
        assert loaded.events == 2


# ---------------------------------------------------------------------------
# Tariff-UNSET fail-closed guard
# ---------------------------------------------------------------------------

class TestTariffUnsetGuard:
    def _harness(self, storage, boundary, tariff=None):
        return RealRunHarness(
            _snapshot(), storage, boundary, tariff=tariff, budget_usd=None, run_id="run-1"
        )

    def test_pb_leak_direct_refuses_when_unset(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        calls = []

        def fake(messages, usage_sink=None):
            calls.append(messages)
            return "x"

        boundary.complete = fake
        harness = self._harness(storage, boundary, tariff=None)
        probe = {"probe_id": PB_LEAK_ID, "probe_family": "PB-LEAK",
                 "visible_input": "текст"}
        with pytest.raises(TariffUnsetError):
            harness.run_pb_leak_direct(probe)
        assert calls == []

    def test_delegated_pb_rec_refuses_when_unset(self, tmp_path) -> None:
        from tools.cis_pilot.probe_runner import ProbeDefinition
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        harness = self._harness(storage, boundary, tariff=None)
        probe = ProbeDefinition(probe_id="pb-rec-001", mode="PB-REC", scene_question="txt")
        with pytest.raises(TariffUnsetError):
            harness.run_delegated(probe)

    def test_pb_mem_delegated_refuses_when_unset(self, tmp_path) -> None:
        from tools.cis_pilot.probe_runner import ProbeDefinition
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        harness = self._harness(storage, boundary, tariff=None)
        probe = ProbeDefinition(probe_id=PB_MEM_ID, mode="PB-MEM",
                                scene_question="", objective_event="evt",
                                perception_hint="hint")
        with pytest.raises(TariffUnsetError):
            harness.run_pb_mem_delegated(probe)


# ---------------------------------------------------------------------------
# PB-LEAK direct render (with tariff set)
# ---------------------------------------------------------------------------

class TestPbLeakDirectRender:
    def test_one_call_per_sample_verbatim_metadata_no_verdict(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        calls = []

        def fake(messages, usage_sink=None):
            calls.append(messages)
            if usage_sink is not None:
                usage_sink.append({"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14})
            return "  generated-text  "

        boundary.complete = fake
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
            run_id="run-1",
        )
        probe = {
            "probe_id": PB_LEAK_ID, "probe_family": "PB-LEAK",
            "visible_input": "Ты читаешь сообщение и молчишь.",
            "forbidden_marker_categories": ["internal_variable_names", "numeric_relationship_scores"],
            "leakage_forbidden": ["all_above_categories"],
        }
        harness.run_pb_leak_direct(probe)

        assert len(calls) == 10
        records = storage.read_jsonl(f"evidence/run-1/{PB_LEAK_ID}/samples.jsonl")
        assert len(records) == 10
        for r in records:
            assert r["generation"] == "generated-text"
            assert r["forbidden_marker_categories"] == ["internal_variable_names", "numeric_relationship_scores"]
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
            run_id="run-1",
        )
        probe = {"probe_id": PB_LEAK_ID, "probe_family": "PB-LEAK",
                 "visible_input": "Ты читаешь сообщение и молчишь."}
        storage.append_jsonl(f"evidence/run-1/{PB_LEAK_ID}/samples.jsonl", {
            "probe_id": PB_LEAK_ID, "mode": "PB-LEAK", "state": None,
            "arm": None, "sample_index": 0, "generation": "existing",
        })
        harness.run_pb_leak_direct(probe)
        assert len(calls) == 9


# ---------------------------------------------------------------------------
# PB-MEM delegation + durable usage (TD-26A)
# ---------------------------------------------------------------------------

class TestPbMemDelegation:
    def _pb_mem_probe(self):
        from tools.cis_pilot.probe_runner import ProbeDefinition
        return ProbeDefinition(
            probe_id=PB_MEM_ID, mode="PB-MEM", scene_question="",
            objective_event="Падает ему на грудь. Плачет.",
            perception_hint="Кто-то рядом понял её без слов.",
        )

    def _fake_boundary(self, boundary, *, fail_gist=False, fail_interp_parse=False):
        """Return (boundary, calls) where calls records (content, phase)."""
        calls = []
        objective = "Падает ему на грудь. Плачет."

        def fake(messages, usage_sink=None):
            content = messages[0]["content"]
            if "interpretation-proposal" in content:
                calls.append(("interpretation", content))
                if usage_sink is not None:
                    usage_sink.append({"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30})
                if fail_interp_parse:
                    return "not-json at all"
                return '{"meaning": "она доверилась", "emotional_coloring": "ранимость"}'
            # gist-proposal
            calls.append(("gist", content))
            if fail_gist:
                # transport-level failure: no successful HTTP response, hence no usage.
                raise RuntimeError("simulated gist failure")
            if usage_sink is not None:
                usage_sink.append({"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23})
            return "она доверилась тому, кто не отстранился"

        boundary.complete = fake
        return boundary, calls

    def test_two_calls_per_sample_and_persisted_once(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        boundary, calls = self._fake_boundary(boundary)
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
            run_id="run-1",
        )
        harness.run_pb_mem_delegated(self._pb_mem_probe())

        # 10 samples x 2 calls
        assert len(calls) == 20
        assert sum(1 for c in calls if c[0] == "interpretation") == 10
        assert sum(1 for c in calls if c[0] == "gist") == 10

        records = storage.read_jsonl(f"evidence/run-1/{PB_MEM_ID}/samples.jsonl")
        assert len(records) == 10
        # usage: 20 records (interpretation + gist per sample)
        usage = storage.read_jsonl(f"usage/run-1/usage.jsonl")
        assert len(usage) == 20
        assert harness.ledger.events == 20

    def test_call1_usage_survives_call2_failure(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        boundary, calls = self._fake_boundary(boundary, fail_gist=True)
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
            run_id="run-1",
        )
        with pytest.raises(RuntimeError, match="simulated gist failure"):
            harness.run_pb_mem_delegated(self._pb_mem_probe())

        # no semantic completed evidence (first sample incomplete; later samples never ran)
        records = storage.read_jsonl(f"evidence/run-1/{PB_MEM_ID}/samples.jsonl")
        assert records == []

        # call #1 (interpretation) usage was durably captured BEFORE gist failed
        usage = storage.read_jsonl(f"usage/run-1/usage.jsonl")
        phases = [u["phase"] for u in usage]
        assert phases == ["interpretation"], "only call #1 usage recorded"
        # zero automatic retry: exactly 2 provider attempts for that sample
        assert len(calls) == 2

    def test_parse_failed_call1_keeps_usage(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()
        boundary, calls = self._fake_boundary(boundary, fail_interp_parse=True)
        harness = RealRunHarness(
            _snapshot(), storage, boundary,
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
            run_id="run-1",
        )
        with pytest.raises(Exception):
            harness.run_pb_mem_delegated(self._pb_mem_probe())

        records = storage.read_jsonl(f"evidence/run-1/{PB_MEM_ID}/samples.jsonl")
        assert records == []
        usage = storage.read_jsonl(f"usage/run-1/usage.jsonl")
        assert len(usage) == 1, "call #1 usage retained despite parse failure"

    def test_resume_reproposes_both_and_adds_usage(self, tmp_path) -> None:
        storage = CisPilotStorage(tmp_path)
        boundary = default_boundary()

        # First attempt: interpretation succeeds, gist fails on sample 0 only.
        state = {"i": 0}
        calls = []

        def fake(messages, usage_sink=None):
            content = messages[0]["content"]
            if "interpretation-proposal" in content:
                calls.append(("interpretation", content))
                if usage_sink is not None:
                    usage_sink.append({"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30})
                return '{"meaning": "она доверилась", "emotional_coloring": "ранимость"}'
            # gist: fail only the first gist
            calls.append(("gist", content))
            state["i"] += 1
            if state["i"] == 1:
                raise RuntimeError("simulated gist failure")
            if usage_sink is not None:
                usage_sink.append({"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23})
            return "она доверилась тому, кто не отстранился"

        boundary.complete = fake
        config = dict(
            tariff=TariffTable(input_per_mtok=1.0, output_per_mtok=1.0),
            run_id="run-1",
        )
        harness = RealRunHarness(_snapshot(), storage, boundary, **config)
        with pytest.raises(RuntimeError, match="simulated gist failure"):
            harness.run_pb_mem_delegated(self._pb_mem_probe())

        # First attempt consumed: interpretation + failed gist for sample 0,
        # then did NOT proceed (stop on failure). Now resume re-proposes sample 0.
        recorded_before = len(storage.read_jsonl(f"usage/run-1/usage.jsonl"))

        boundary2 = default_boundary()
        boundary2.complete = fake  # reuse same fake (fails only first gist ever)
        harness2 = RealRunHarness(_snapshot(), storage, boundary2, **config)
        # Resume: sample 0 already has an interpretation usage but NO completed evidence,
        # so both calls run again; gist now succeeds (state["i"] > 1).
        harness2.run_pb_mem_delegated(self._pb_mem_probe())

        usage_after = storage.read_jsonl(f"usage/run-1/usage.jsonl")
        assert len(usage_after) >= recorded_before + 20, "prior usage not erased; resume adds usage"
        records = storage.read_jsonl(f"evidence/run-1/{PB_MEM_ID}/samples.jsonl")
        assert len(records) == 10, "resume completes all 10 samples exactly once"