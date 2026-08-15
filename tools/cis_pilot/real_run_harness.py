#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TD-24/26A bounded real-run harness + usage accounting (offline-safe scaffold).

Loads the frozen real probe set, verifies its SHA-256 before anything else,
builds the exact real-capable plan (PB-REC 30 + PB-MEM 20 + PB-AB 120 +
PB-LEAK 10 = 180); PB-MEM delegates to ``ProbeRunner.run_pb_mem_real`` (two
provider calls per sample), PB-LEAK uses the approved direct render, PB-REC and
PB-AB delegate to ``ProbeRunner.run_pb_rec`` / ``run_pb_ab``.

This module performs NO judge logic and no real network I/O by itself: it only
delegates to the approved provider boundary and storage. A real run requires an
owner-supplied tariff table + budget ceiling; until then the tariff defaults to
``UNSET`` and every provider call is refused BEFORE network (fail closed). No
retries, no fallback (the 120s transport timeout is bound by provider_boundary
via TD-22A).

TD-26A adds a ``DurableUsageSink``: per-call usage is accounted immediately
(including a succeeded PB-MEM call #1 when call #2 later fails) and durably
appended to the run artifact namespace before semantic sample completion, so
usage is not lost on process interruption or explicit resume.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .context_assembler import assemble_cis_context, render_cis_messages
from .probe_runner import (
    ProbeDefinition,
    ProbeRunner,
    ProbeRunConfig,
)
from .provider_boundary import (
    PilotProviderBoundary,
)
from .result_package import generate_run_id
from .storage import CisPilotStorage

# Frozen real probe set (owner-approved, TD-20).
FROZEN_PROBE_SET_REL = "local_runs/cis_pilot/probe_sets/CIS_KIRA_S6_REAL_PROBE_SET_v1.json"
FROZEN_PROBE_SET_SHA256 = "d5bc4fff53954de791050cd8d1b91ce50142343bc14d310e912ef195bbe477e1"

# Real-capable family mapping (TD-26A: PB-MEM included).
REAL_FAMILIES = ("PB-REC", "PB-MEM", "PB-AB", "PB-LEAK")
N_PER_ARM = 10
EXPECTED_REAL_CALLS = 180

# Tariff sentinel: the production cost table is NOT hard-coded and defaults to
# UNSET; any real call is refused until an owner tariff table is supplied.
TARIFF_UNSET = "UNSET"


class RealRunError(RuntimeError):
    """Fail-closed real-run harness error."""


class TariffUnsetError(RealRunError):
    """Raised when a real provider call is attempted with no tariff table."""


@dataclass(frozen=True)
class TariffTable:
    """Frozen per-1M-token USD rates. ``None`` values => not defined.

    ``reasoning_per_mtok`` is optional (only relevant if the provider prices
    reasoning tokens separately). No value may be fabricated here.
    """

    input_per_mtok: Optional[float] = None
    output_per_mtok: Optional[float] = None
    reasoning_per_mtok: Optional[float] = None

    @property
    def defined(self) -> bool:
        return self.input_per_mtok is not None and self.output_per_mtok is not None


@dataclass
class UsageLedger:
    """Cumulative provider usage for one run (TD-24)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    events: int = 0

    def record(self, usage: Optional[Dict[str, Any]]) -> None:
        if not isinstance(usage, dict):
            return
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.reasoning_tokens += int(usage.get("reasoning_tokens") or 0)
        self.total_tokens += int(usage.get("total_tokens") or 0)
        self.events += 1


class DurableUsageSink:
    """Per-call usage capture with immediate durable accounting (TD-26A).

    ``llm_provider._complete_cloud`` appends each provider ``usage`` dict via
    ``.append(...)`` immediately after a successful HTTP response -- BEFORE any
    parsing. This sink records the dict in-memory AND (when a run_id + storage
    are available) durably appends a ``{"phase", "usage"}`` record to
    ``usage/{run_id}/usage.jsonl`` so a succeeded PB-MEM call #1 is not lost if
    call #2 fails or the process resumes.
    """

    def __init__(
        self,
        storage: Optional[CisPilotStorage] = None,
        run_id: Optional[str] = None,
        phase: str = "unknown",
    ) -> None:
        self.entries: List[Dict[str, Any]] = []
        self._storage = storage
        self._run_id = run_id
        self._phase = phase

    def append(self, usage: Dict[str, Any]) -> None:
        if not isinstance(usage, dict):
            return
        self.entries.append(dict(usage))
        if self._storage is not None and self._run_id:
            self._storage.append_jsonl(
                f"usage/{self._run_id}/usage.jsonl",
                {"phase": self._phase, "usage": dict(usage)},
            )

    def __iter__(self):
        return iter(self.entries)


def load_cumulative_usage(storage: CisPilotStorage, run_id: str) -> UsageLedger:
    """Reconstruct the cumulative ledger from durable per-call usage records."""
    ledger = UsageLedger()
    for record in storage.read_jsonl(f"usage/{run_id}/usage.jsonl"):
        usage = record.get("usage") if isinstance(record, dict) else None
        if isinstance(usage, dict):
            ledger.record(usage)
    return ledger


def estimate_cost_usd(tariff: Optional[TariffTable], ledger: UsageLedger) -> Optional[float]:
    """Parameterized cost estimate under a frozen tariff table (TD-24).

    Returns ``None`` when the tariff is unset (no dollar figure is fabricated).
    """
    if tariff is None or not tariff.defined:
        return None
    reasoning_rate = tariff.reasoning_per_mtok or 0.0
    cost = (
        ledger.prompt_tokens * (tariff.input_per_mtok or 0.0)
        + ledger.completion_tokens * (tariff.output_per_mtok or 0.0)
        + ledger.reasoning_tokens * reasoning_rate
    )
    return round(cost / 1_000_000.0, 8)


class RealRunHarness:
    """Bounded real-run driver: SHA-gated loader, plan, resume, usage, budget."""

    def __init__(
        self,
        snapshot: Any,
        storage: CisPilotStorage,
        boundary: PilotProviderBoundary,
        *,
        run_id: Optional[str] = None,
        tariff: Optional[TariffTable] = None,
        budget_usd: Optional[float] = None,
    ) -> None:
        if not isinstance(boundary, PilotProviderBoundary):
            raise RealRunError("boundary must be a PilotProviderBoundary")
        if not isinstance(storage, CisPilotStorage):
            raise RealRunError("storage must be a CisPilotStorage")
        self._snapshot = snapshot
        self._storage = storage
        self._boundary = boundary
        self._run_id = run_id or generate_run_id()
        self._tariff = tariff
        self._budget_usd = budget_usd
        self._ledger = UsageLedger()

    # ------------------------------------------------------------------
    # Loading / planning
    # ------------------------------------------------------------------

    @staticmethod
    def load_frozen_probe_set(repo_root: str) -> Dict[str, Any]:
        """Read the frozen probe set and fail closed unless its SHA-256 matches.

        This is the FIRST gate before any planning or call: a mismatch stops
        before network (TD-20/TD-24).
        """
        path = f"{repo_root}/{FROZEN_PROBE_SET_REL}"
        with open(path, "rb") as fh:
            raw = fh.read()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != FROZEN_PROBE_SET_SHA256:
            raise RealRunError(
                f"frozen probe set SHA mismatch: got {actual!r}, "
                f"expected {FROZEN_PROBE_SET_SHA256!r}"
            )
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def build_real_plan(probe_set: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build the exact real-capable plan = 180 PROVIDER-CALL entries.

        Each PB-REC/PB-AB/PB-LEAK sample contributes one call; each PB-MEM
        sample contributes TWO calls (interpretation + gist).
        """
        n = probe_set.get("sample_count_per_arm_state", N_PER_ARM)
        plan: List[Dict[str, Any]] = []
        for probe in probe_set.get("probes", []):
            family = probe.get("probe_family")
            if family not in REAL_FAMILIES:
                continue
            probe_id = probe.get("probe_id")
            if family == "PB-REC":
                for arm in ("KIRA_CANDIDATE", "OTHER_CHARACTER_DECOY", "GENERIC_DECOY"):
                    for idx in range(n):
                        plan.append({
                            "probe_id": probe_id, "family": family,
                            "sub_mode": None, "arm": arm, "sample_index": idx,
                        })
            elif family == "PB-LEAK":
                for idx in range(n):
                    plan.append({
                        "probe_id": probe_id, "family": family,
                        "sub_mode": None, "arm": None, "sample_index": idx,
                    })
            elif family == "PB-MEM":
                for idx in range(n):
                    for phase in ("interpretation", "gist"):
                        plan.append({
                            "probe_id": probe_id, "family": family,
                            "sub_mode": None, "arm": None, "sample_index": idx,
                            "call_phase": phase,
                        })
            elif family == "PB-AB":
                sub_mode = probe.get("sub_mode")
                for arm in ("A", "B", "BASELINE_A", "BASELINE_B"):
                    for idx in range(n):
                        plan.append({
                            "probe_id": probe_id, "family": family,
                            "sub_mode": sub_mode, "arm": arm, "sample_index": idx,
                        })
        return plan

    @staticmethod
    def _probe_by_id(probe_set: Dict[str, Any], probe_id: str) -> Dict[str, Any]:
        for probe in probe_set.get("probes", []):
            if probe.get("probe_id") == probe_id:
                return probe
        raise RealRunError(f"probe_id {probe_id!r} not found in frozen probe set")

    @staticmethod
    def _to_probe_definition(probe: Dict[str, Any]) -> ProbeDefinition:
        family = probe.get("probe_family")
        return ProbeDefinition(
            probe_id=probe.get("probe_id"),
            mode=family,
            scene_question=probe.get("visible_input") or "",
            sub_modes=(probe.get("sub_mode"),) if probe.get("sub_mode") else (),
            objective_event=probe.get("objective_event"),
            perception_hint=probe.get("perception_hint"),
        )

    # ------------------------------------------------------------------
    # Budget / tariff hard stop
    # ------------------------------------------------------------------

    def _assert_tariff_ready(self) -> None:
        """Refuse every real provider call BEFORE network if tariff is unset."""
        if self._tariff is None or not self._tariff.defined:
            raise TariffUnsetError(
                "tariff table is UNSET: refusing real provider call before network; "
                "supply an owner-approved tariff table for this run_id"
            )
        if self._budget_usd is not None:
            spent = estimate_cost_usd(self._tariff, self._ledger) or 0.0
            if spent >= self._budget_usd:
                raise RealRunError(
                    f"budget ceiling {self._budget_usd!r} already reached "
                    f"(spent {spent!r}); refusing further real calls"
                )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_pb_mem_delegated(self, probe_definition: ProbeDefinition) -> None:
        """Delegate real PB-MEM to ProbeRunner (2 calls/sample, gate, resume).

        Two durable, phase-tagged usage sinks so a succeeded call #1 is
        accounted even when call #2 fails; transactional sample resume means no
        completed semantic evidence is written for an incomplete sample.
        """
        self._assert_tariff_ready()
        runner = ProbeRunner(self._snapshot, self._storage)
        config = ProbeRunConfig(
            probe=probe_definition,
            boundary=self._boundary,
            samples_per_arm=N_PER_ARM,
        )
        interp_sink = DurableUsageSink(
            self._storage, self._run_id, phase="interpretation"
        )
        gist_sink = DurableUsageSink(
            self._storage, self._run_id, phase="gist"
        )
        runner.run_pb_mem_real(
            config,
            resume_run_id=self._run_id,
            interpretation_usage_sink=interp_sink,
            gist_usage_sink=gist_sink,
        )
        for usage in interp_sink:
            self._ledger.record(usage)
        for usage in gist_sink:
            self._ledger.record(usage)

    def run_delegated(self, probe_definition: ProbeDefinition) -> None:
        """Delegate PB-REC / PB-AB to ProbeRunner (TD-21/usage-aware)."""
        self._assert_tariff_ready()
        runner = ProbeRunner(self._snapshot, self._storage)
        config = ProbeRunConfig(
            probe=probe_definition,
            boundary=self._boundary,
            samples_per_arm=N_PER_ARM,
        )
        usage_sink: List[Dict[str, Any]] = []
        family = probe_definition.mode
        if family == "PB-REC":
            runner.run_pb_rec(
                config, resume_run_id=self._run_id, usage_sink=usage_sink
            )
        elif family == "PB-AB":
            sub_mode = probe_definition.sub_modes[0]
            runner.run_pb_ab(
                config, sub_mode=sub_mode, resume_run_id=self._run_id,
                usage_sink=usage_sink,
            )
        else:
            raise RealRunError(f"unsupported delegated family: {family!r}")
        for usage in usage_sink:
            self._ledger.record(usage)

    def run_pb_leak_direct(self, probe: Dict[str, Any]) -> None:
        """PB-LEAK direct render (TD-24 owner decision).

        One approved provider call per sample with the exact frozen
        ``visible_input`` unchanged, no synthetic marker injection, no inline
        leak scan, no verdict -- the forbidden meta is persisted verbatim for a
        SEPARATE judge stage.
        """
        self._assert_tariff_ready()
        probe_id = probe.get("probe_id")
        visible_input = probe.get("visible_input")
        if not visible_input:
            raise RealRunError("PB-LEAK probe missing visible_input")
        p4 = self._snapshot_runner_p4()
        ctx = assemble_cis_context(
            p0=self._snapshot.p0,
            p3=self._snapshot.p3,
            p4=p4,
            scene_question=visible_input,
        )
        messages = render_cis_messages(ctx)
        runner = ProbeRunner(self._snapshot, self._storage)
        already = runner._load_completed_records(self._run_id, probe_id)

        for idx in range(N_PER_ARM):
            key = (probe_id, None, None, idx)
            if key in already:
                continue
            usage_sink: List[Dict[str, Any]] = []
            gen = self._boundary.complete(messages, usage_sink=usage_sink)
            for usage in usage_sink:
                self._ledger.record(usage)
            record = {
                "probe_id": probe_id,
                "mode": "PB-LEAK",
                "state": None,
                "arm": None,
                "sample_index": idx,
                "generation": gen.strip(),
                "tags": ["frozen", "pb-leak"],
                "forbidden_marker_categories": list(probe.get("forbidden_marker_categories") or []),
                "leakage_forbidden": list(probe.get("leakage_forbidden") or []),
            }
            self._storage.append_jsonl(
                f"evidence/{self._run_id}/{probe_id}/samples.jsonl", record
            )

    def _snapshot_runner_p4(self) -> Any:
        """Return the canonical exploration P4 state (low arousal, low anxiety).

        Mirrors ProbeRunner's exploration selection without duplicating policy
        constants beyond this single lookup."""
        runner = ProbeRunner(self._snapshot, self._storage)
        return runner._p4_exploration

    # -- Accounting helpers -------------------------------------------------

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def ledger(self) -> UsageLedger:
        return self._ledger

    def estimated_cost_usd(self) -> Optional[float]:
        return estimate_cost_usd(self._tariff, self._ledger)


def load_snapshot() -> Any:
    """Load the pilot source snapshot (used by the real runner exclusively)."""
    from .source_loader import load_pilot_source_snapshot

    return load_pilot_source_snapshot()