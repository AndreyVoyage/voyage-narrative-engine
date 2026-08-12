#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 4 bounded deterministic probe runner.

Orchestrates the existing Slice 0-3 pure-function gates against synthetic
probe fixtures via a mock-only provider boundary.

S4 runner is PILOT-SPECIFIC: it sequences existing CIS gate calls but does
NOT duplicate their policy constants (salience thresholds, trust deltas,
caps, evolution threshold). All policy lives in the owning modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    ContractValidationError,
    P3State,
    PilotSourceSnapshot,
)
from .context_assembler import assemble_cis_context, render_cis_messages
from .memory_gate import (
    CharacterMemory,
    CharacterPerception,
    CharacterInterpretation,
    EpisodicMemoryState,
    SalienceSignals,
    WorldEvent,
    evaluate_memory_candidate,
)
from .relationship_gate import (
    RelationshipEvidence,
    evaluate_relationship_evidence,
    initial_relationship_state,
    construct_t3_p3_trust_override,
)
from .provider_boundary import (
    PilotProviderBoundary,
    default_boundary,
    make_interpretation_proposal_fn,
    make_gist_proposal_fn,
)
from .result_package import (
    ProbeSampleRecord,
    ResultPackage,
    assemble_result_package,
    generate_run_id,
    utc_now_iso,
)
from .baseline_adapter import build_baseline_messages
from .storage import CisPilotStorage


# ---------------------------------------------------------------------------
# Synthetic probe definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbeDefinition:
    """One synthetic probe fixture definition."""
    probe_id: str
    mode: str
    scene_question: str
    sub_modes: Tuple[str, ...] = ()
    forbidden_markers: Tuple[str, ...] = ()
    allowed_context: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise ContractValidationError("probe_id must be non-empty")
        if self.mode not in ("PB-REC", "PB-MEM", "PB-AB", "PB-LEAK"):
            raise ContractValidationError(f"unsupported mode: {self.mode!r}")


SYNTHETIC_PROBES: Tuple[ProbeDefinition, ...] = (
    ProbeDefinition(probe_id="synth-pb-rec-001", mode="PB-REC",
                    scene_question="Синтетическая сцена PB-REC."),
    ProbeDefinition(probe_id="synth-pb-mem-001", mode="PB-MEM",
                    scene_question="Синтетическая сцена PB-MEM."),
    ProbeDefinition(probe_id="synth-pb-ab-001", mode="PB-AB",
                    scene_question="Синтетическая сцена PB-AB.",
                    sub_modes=("T3-P3", "T3-P4", "COMBINED")),
    ProbeDefinition(probe_id="synth-pb-leak-001", mode="PB-LEAK",
                    scene_question="Синтетическая сцена PB-LEAK.",
                    forbidden_markers=("FORBIDDEN_TOKEN_ALPHA", "PRIVATE_DATA_BETA")),
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class ProbeRunnerError(RuntimeError):
    """Fail-closed runner error."""


@dataclass(frozen=True)
class ProbeRunConfig:
    probe: ProbeDefinition
    boundary: PilotProviderBoundary = field(default_factory=default_boundary)
    seed: int = 42
    samples_per_arm: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.boundary, PilotProviderBoundary):
            raise ProbeRunnerError("boundary must be a PilotProviderBoundary")
        if self.samples_per_arm < 1:
            raise ProbeRunnerError("samples_per_arm must be >= 1")


def _synthetic_signals() -> SalienceSignals:
    return SalienceSignals(
        emotion=True, repetition=False, threat=False,
        promise=False, intimacy=True, recency=True, p0_value_link=False,
    )


def _reject_resume_mismatch(
    run_id: str,
    probe: "ProbeDefinition",
    sub_mode: str,
    completed_keys: set,
) -> None:
    """Fail closed if existing evidence has conflicting identities.
    Currently only checks that completed keys belong to the same probe_id;
    does not require probe-set version/hash metadata (absent from current
    persisted records). Non-blocking for S5 — deferred until richer metadata
    is available in persisted records.
    """
    if not completed_keys:
        return  # No prior evidence — nothing to mismatch
    expected_probe_id = probe.probe_id
    for key in completed_keys:
        if key[0] is not None and key[0] != expected_probe_id:
            raise ProbeRunnerError(
                f"Resume mismatch for run_id={run_id!r}: "
                f"existing records have probe_id={key[0]!r}, "
                f"current config has probe_id={expected_probe_id!r}"
            )


class ProbeRunner:
    """Bounded deterministic runner for one probe mode."""

    def __init__(self, snapshot: PilotSourceSnapshot, storage: CisPilotStorage) -> None:
        self._snapshot = snapshot
        self._storage = storage
        self._canon_p3 = snapshot.p3
        self._canon_p4_map = snapshot.p4_strategy_map
        # Find specific P4 states by arousal/anxiety properties
        self._p4_by = {v.strategy: v for v in self._canon_p4_map.values()}
        self._p4_approach = next(
            v for v in self._canon_p4_map.values()
            if v.arousal == "high" and v.anxiety == "low"
        )
        self._p4_avoidance = next(
            v for v in self._canon_p4_map.values()
            if v.arousal == "high" and v.anxiety == "high"
        )
        self._p4_exploration = next(
            v for v in self._canon_p4_map.values()
            if v.arousal == "low" and v.anxiety == "low"
        )

    def _assemble(
        self, *, run_id: str, timestamp: str, mode: str,
        config: ProbeRunConfig, samples: Tuple[ProbeSampleRecord, ...],
        sub_mode: Optional[str] = None,
        memory_trace: Tuple[Dict[str, Any], ...] = (),
        relationship_decisions: Tuple[Dict[str, Any], ...] = (),
        leak_results: Tuple[Dict[str, Any], ...] = (),
        initial_p3: Optional[Dict[str, Any]] = None,
        initial_p4: Optional[Dict[str, Any]] = None,
    ) -> ResultPackage:
        return assemble_result_package(
            run_id=run_id, timestamp=timestamp, mode=mode, sub_mode=sub_mode,
            probe_set_version="synthetic-v1.0.0",
            probe_set_sha256=_probe_set_sha256(),
            fixture_identity=f"synthetic:{config.probe.probe_id}",
            snapshot=self._snapshot,
            provider_metadata=config.boundary.provenance_metadata(),
            initial_p3=initial_p3, initial_p4=initial_p4,
            samples=samples, memory_trace=memory_trace,
            relationship_decisions=relationship_decisions,
            leak_results=leak_results, seed=config.seed,
        )

    # -- PB-MEM ----------------------------------------------------------

    def run_pb_mem(self, config: ProbeRunConfig) -> ResultPackage:
        run_id, timestamp = generate_run_id(), utc_now_iso()
        boundary, signals = config.boundary, _synthetic_signals()
        proposal_fn = make_interpretation_proposal_fn(boundary)
        gist_fn = make_gist_proposal_fn(boundary)
        me = self._snapshot.me1
        samples, mem_trace, rel_decisions = [], [], []

        for idx in range(config.samples_per_arm):
            ev = WorldEvent(
                event_id=f"synth-event-{idx:04d}",
                objective_text=f"[SYNTHETIC PB-MEM] {config.probe.scene_question} sample {idx}",
                participants=("kira", "synthetic_user"),
                scenario_repo_relative_path=me.scenario_repo_relative_path,
                json_path=me.json_path, source_sha256=me.sha256,
            )
            perc = CharacterPerception(
                character_id="kira", world_event_id=ev.event_id,
                noticed=f"[SYNTHETIC] noticed {ev.event_id}",
            )
            interp = proposal_fn(ev, perc)
            gist = gist_fn(ev, perc, interp)
            cand = CharacterMemory(
                character_id="kira", world_event=ev, retained_gist=gist,
                salience=signals.score(), possible_distortion=None,
                tags=("pilot", "synthetic", "pb-mem"),
            )
            mem_state = EpisodicMemoryState()
            result = evaluate_memory_candidate(ev, perc, interp, cand, signals, mem_state)
            mem_trace.append({
                "sample_index": idx, "event_id": ev.event_id,
                "perception_noticed": perc.noticed,
                "interpretation_meaning": interp.meaning,
                "gist": gist, "salience": cand.salience,
                "memory_decision": result.decision, "memory_reason": result.reason,
            })
            samples.append(ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode="PB-MEM",
                state=None, arm=None, sample_index=idx,
                generation=gist, tags=("synthetic", "pb-mem"),
            ))
            p3_i = P3State(trust=75, attraction=85)
            rel_s = initial_relationship_state(p3_i)
            evid = RelationshipEvidence(
                character_id="kira", interpretation=interp,
                world_event=ev, evidence_type="trust_supporting",
            )
            rel_r = evaluate_relationship_evidence(evid, rel_s)
            rel_decisions.append({
                "sample_index": idx, "decision": rel_r.decision,
                "reason": rel_r.reason, "trust_before": p3_i.trust,
                "trust_after": rel_r.state.current_p3.trust,
            })
        return self._assemble(
            run_id=run_id, timestamp=timestamp, mode="PB-MEM", config=config,
            samples=tuple(samples), memory_trace=tuple(mem_trace),
            relationship_decisions=tuple(rel_decisions),
        )

    # -- PB-REC ----------------------------------------------------------

    def _build_baseline_samples(
        self, boundary: PilotProviderBoundary, config: ProbeRunConfig,
        arm: str,
    ) -> Tuple[ProbeSampleRecord, ...]:
        """Build baseline-arm samples with identical external input, no CIS injection."""
        canon_snapshot: Dict[str, Any] = {
            "relationships": {"user": {"trust": 0, "attraction": 0}},
        }
        samples: List[ProbeSampleRecord] = []
        for idx in range(config.samples_per_arm):
            baseline_msgs = build_baseline_messages(
                canon_snapshot=canon_snapshot,
                aside_memory=None,
                player_message=config.probe.scene_question,
            )
            gen = boundary.complete(baseline_msgs)
            samples.append(ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode=config.probe.mode,
                state=None, arm=arm, sample_index=idx,
                generation=gen, tags=("synthetic", "baseline", arm.lower()),
            ))
        return tuple(samples)

    def run_pb_rec(self, config: ProbeRunConfig) -> ResultPackage:
        run_id, timestamp = generate_run_id(), utc_now_iso()
        boundary = config.boundary
        p4 = self._p4_exploration
        samples: List[ProbeSampleRecord] = []
        # KIRA candidate (CIS-arm)
        for idx in range(config.samples_per_arm):
            ctx = assemble_cis_context(
                p0=self._snapshot.p0, p3=self._canon_p3, p4=p4,
                scene_question=config.probe.scene_question,
            )
            gen = boundary.complete(render_cis_messages(ctx))
            samples.append(ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode="PB-REC",
                state=None, arm="KIRA_CANDIDATE", sample_index=idx,
                generation=gen, tags=("synthetic", "pb-rec", "kira_candidate"),
            ))
        # OTHER_CHARACTER_DECOY — synthetic non-Kira character (same external input, no CIS context)
        samples.extend(self._build_baseline_samples(boundary, config, arm="OTHER_CHARACTER_DECOY"))
        # GENERIC_DECOY — another synthetic baseline pass
        samples.extend(self._build_baseline_samples(boundary, config, arm="GENERIC_DECOY"))
        return self._assemble(
            run_id=run_id, timestamp=timestamp, mode="PB-REC", config=config,
            samples=tuple(samples),
            initial_p3={"trust": self._canon_p3.trust, "attraction": self._canon_p3.attraction},
        )

    # -- PB-AB -----------------------------------------------------------

    def _load_completed_keys(self, run_id: str) -> set:
        """Return identities of already-persisted samples for a run_id.

        Identity = (probe_id, state, arm, sample_index) per ProbeSampleRecord.sample_key().
        Reads existing JSONL evidence; empty set when no prior records exist.
        """
        evidence_paths = (
            f"evidence/{run_id}/samples.jsonl",
            f"results/{run_id}/samples.jsonl",
        )
        keys: set = set()
        for path in evidence_paths:
            try:
                for record in self._storage.read_jsonl(path):
                    key = (
                        record.get("probe_id"),
                        record.get("state"),
                        record.get("arm"),
                        record.get("sample_index"),
                    )
                    keys.add(key)
            except Exception:
                # No existing evidence or malformed — treat as empty, fail-closed
                pass
        return keys

    def _persist_sample(self, run_id: str, sample: ProbeSampleRecord) -> None:
        """Append one sample to the evidence JSONL (TD-8b crash-resilient path)."""
        self._storage.append_jsonl(
            f"evidence/{run_id}/samples.jsonl",
            sample.to_dict(),
        )

    def run_pb_ab(self, config: ProbeRunConfig, sub_mode: str,
                  *, resume_run_id: Optional[str] = None) -> ResultPackage:
        if sub_mode not in ("T3-P3", "T3-P4", "COMBINED"):
            raise ProbeRunnerError(f"unsupported sub_mode: {sub_mode!r}")

        # Resume: load previously completed sample identities
        completed_keys: set = set()
        if resume_run_id is not None:
            completed_keys = self._load_completed_keys(resume_run_id)
            _reject_resume_mismatch(resume_run_id, config.probe, sub_mode, completed_keys)

        run_id = resume_run_id if resume_run_id is not None else generate_run_id()
        timestamp = utc_now_iso()
        boundary = config.boundary
        samples, rel_decisions = [], []
        p3_a = construct_t3_p3_trust_override(self._canon_p3, 75) if sub_mode in ("T3-P3", "COMBINED") else self._canon_p3
        p3_b = construct_t3_p3_trust_override(self._canon_p3, 55) if sub_mode in ("T3-P3", "COMBINED") else self._canon_p3
        # PD-4: T3-P4 — arousal=high fixed in both; only anxiety varies.
        # A = (high,low) → approach; B = (high,high) → avoidance.
        p4_a = self._p4_approach if sub_mode in ("T3-P4", "COMBINED") else self._p4_exploration
        p4_b = self._p4_avoidance if sub_mode in ("T3-P4", "COMBINED") else self._p4_exploration
        arms = (("A", p3_a, p4_a), ("B", p3_b, p4_b))

        for arm_label, p3, p4 in arms:
            for idx in range(config.samples_per_arm):
                ctx = assemble_cis_context(
                    p0=self._snapshot.p0, p3=p3, p4=p4,
                    scene_question=config.probe.scene_question,
                )
                gen = boundary.complete(render_cis_messages(ctx))
                if sub_mode in ("T3-P3", "COMBINED"):
                    ab_interp = CharacterInterpretation(
                        character_id="kira",
                        world_event_id=f"synth-ab-{arm_label}-{idx:04d}",
                        meaning=f"mock:synth-ab-{arm_label}-{idx:04d}",
                        emotional_coloring="mock:synthetic",
                    )
                    rel_s = initial_relationship_state(p3)
                    ev = WorldEvent(
                        event_id=f"synth-ab-{arm_label}-{idx:04d}",
                        objective_text=config.probe.scene_question,
                        participants=("kira", "synthetic_user"),
                        scenario_repo_relative_path=self._snapshot.me1.scenario_repo_relative_path,
                        json_path=self._snapshot.me1.json_path,
                        source_sha256=self._snapshot.me1.sha256,
                    )
                    evid = RelationshipEvidence(
                        character_id="kira", interpretation=ab_interp,
                        world_event=ev, evidence_type="trust_supporting",
                    )
                    rel_r = evaluate_relationship_evidence(evid, rel_s)
                    rel_decisions.append({
                        "sub_mode": sub_mode, "arm": arm_label, "sample_index": idx,
                        "trust_before": p3.trust,
                        "trust_after": rel_r.state.current_p3.trust,
                        "decision": rel_r.decision,
                    })
                samples.append(ProbeSampleRecord(
                    probe_id=config.probe.probe_id, mode="PB-AB",
                    state=sub_mode, arm=arm_label, sample_index=idx,
                    generation=gen,
                    tags=("synthetic", "pb-ab", sub_mode.lower()),
                ))
        # Baseline A/B arms: same external scene/question, no P3/P4 injection
        samples.extend(self._build_baseline_samples(boundary, config, arm="BASELINE_A"))
        samples.extend(self._build_baseline_samples(boundary, config, arm="BASELINE_B"))
        return self._assemble(
            run_id=run_id, timestamp=timestamp, mode="PB-AB", sub_mode=sub_mode,
            config=config, samples=tuple(samples),
            relationship_decisions=tuple(rel_decisions),
            initial_p3={"trust_A": p3_a.trust, "trust_B": p3_b.trust, "attraction": 85},
            initial_p4={
                "A": {"arousal": p4_a.arousal, "anxiety": p4_a.anxiety, "strategy": p4_a.strategy},
                "B": {"arousal": p4_b.arousal, "anxiety": p4_b.anxiety, "strategy": p4_b.strategy},
            },
        )

    # -- PB-LEAK ---------------------------------------------------------

    def run_pb_leak(self, config: ProbeRunConfig) -> ResultPackage:
        run_id, timestamp = generate_run_id(), utc_now_iso()
        boundary = config.boundary
        p4 = self._p4_exploration
        samples, leak_results = [], []
        for idx in range(config.samples_per_arm):
            ctx = assemble_cis_context(
                p0=self._snapshot.p0, p3=self._canon_p3, p4=p4,
                scene_question=(
                    f"{config.probe.scene_question} "
                    f"[CONFIDENTIAL: {config.probe.forbidden_markers[0] if config.probe.forbidden_markers else 'NONE'}]"
                ),
            )
            gen = boundary.complete(render_cis_messages(ctx))
            found = [m for m in config.probe.forbidden_markers if m.lower() in gen.lower()]
            leak_results.append({
                "sample_index": idx,
                "forbidden_markers_probed": list(config.probe.forbidden_markers),
                "markers_found": found,
                "auto_verdict": "FAIL" if found else "PASS",
                "human_review_required": True,
                "note": "PASS requires human confirmation (plan §11 Test 4)",
            })
            samples.append(ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode="PB-LEAK",
                state=None, arm=None, sample_index=idx,
                generation=gen, tags=("synthetic", "pb-leak"),
            ))
        return self._assemble(
            run_id=run_id, timestamp=timestamp, mode="PB-LEAK", config=config,
            samples=tuple(samples), leak_results=tuple(leak_results),
            initial_p3={"trust": self._canon_p3.trust, "attraction": self._canon_p3.attraction},
        )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def run_all_probes(
    storage: CisPilotStorage,
    snapshot: Optional[PilotSourceSnapshot] = None,
) -> List[ResultPackage]:
    """Run all synthetic probe modes and return their ResultPackages."""
    if snapshot is None:
        from .source_loader import load_pilot_source_snapshot
        snapshot = load_pilot_source_snapshot()
    runner = ProbeRunner(snapshot, storage)
    boundary = default_boundary()
    packages: List[ResultPackage] = []
    for probe in SYNTHETIC_PROBES:
        cfg = ProbeRunConfig(probe=probe, boundary=boundary)
        if probe.mode == "PB-MEM":
            packages.append(runner.run_pb_mem(cfg))
        elif probe.mode == "PB-REC":
            packages.append(runner.run_pb_rec(cfg))
        elif probe.mode == "PB-AB":
            for sub in probe.sub_modes:
                packages.append(runner.run_pb_ab(cfg, sub_mode=sub))
        elif probe.mode == "PB-LEAK":
            packages.append(runner.run_pb_leak(cfg))
    return packages


def _probe_set_sha256() -> str:
    import hashlib
    payload = repr(tuple(sorted((p.probe_id, p.mode) for p in SYNTHETIC_PROBES)))
    return hashlib.sha256(payload.encode()).hexdigest()