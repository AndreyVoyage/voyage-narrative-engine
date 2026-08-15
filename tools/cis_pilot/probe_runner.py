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
    make_real_interpretation_proposal_fn,
    make_real_gist_proposal_fn,
)
from .result_package import (
    ProbeSampleRecord,
    ResultPackage,
    assemble_result_package,
    generate_run_id,
    utc_now_iso,
)
from .baseline_adapter import build_baseline_messages
from .storage import CisPilotStorage, CisPilotStorageError


# ---------------------------------------------------------------------------
# Synthetic probe definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbeDefinition:
    """One probe fixture definition.

    ``scene_question`` is the external visible input text. For the real PB-MEM
    probe, ``objective_event`` and ``perception_hint`` (TD-24 faithful mapping)
    optionally replace the synthetic memory-chain text; when both are ``None``
    the synthetic PB-MEM behavior is preserved unchanged.
    """
    probe_id: str
    mode: str
    scene_question: str
    sub_modes: Tuple[str, ...] = ()
    forbidden_markers: Tuple[str, ...] = ()
    allowed_context: Tuple[str, ...] = ()
    objective_event: Optional[str] = None
    perception_hint: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise ContractValidationError("probe_id must be non-empty")
        if self.mode not in ("PB-REC", "PB-MEM", "PB-AB", "PB-LEAK"):
            raise ContractValidationError(f"unsupported mode: {self.mode!r}")
        if self.objective_event is not None and not isinstance(self.objective_event, str):
            raise ContractValidationError("objective_event must be a string or None")
        if self.perception_hint is not None and not isinstance(self.perception_hint, str):
            raise ContractValidationError("perception_hint must be a string or None")


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
            event_id = f"synth-event-{idx:04d}"
            objective_text = (
                config.probe.objective_event
                if config.probe.objective_event is not None
                else f"[SYNTHETIC PB-MEM] {config.probe.scene_question} sample {idx}"
            )
            noticed = (
                config.probe.perception_hint
                if config.probe.perception_hint is not None
                else f"[SYNTHETIC] noticed {event_id}"
            )
            ev = WorldEvent(
                event_id=event_id,
                objective_text=objective_text,
                participants=("kira", "synthetic_user"),
                scenario_repo_relative_path=me.scenario_repo_relative_path,
                json_path=me.json_path, source_sha256=me.sha256,
            )
            perc = CharacterPerception(
                character_id="kira", world_event_id=ev.event_id,
                noticed=noticed,
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

    def run_pb_mem_real(
        self,
        config: ProbeRunConfig,
        *,
        resume_run_id: Optional[str] = None,
        interpretation_usage_sink: Optional[Any] = None,
        gist_usage_sink: Optional[Any] = None,
    ) -> ResultPackage:
        """Real-provider PB-MEM (TD-26A): two provider calls per sample.

        CALL #1 = interpretation (strict JSON), CALL #2 = retained-gist
        (plain text), then the deterministic MemoryGate always runs, then the
        completed sample is persisted exactly once under the per-probe
        evidence path. Transactional sample resume: a completed sample is
        skipped (both calls); an incomplete sample (call #1 success + call #2
        failure) writes NO semantic sample evidence and, on a later explicit
        resume, BOTH calls are re-proposed (owner-accepted re-proposal; no
        sub-call checkpoint). Zero automatic retry; zero mock fallback.
        """
        completed_records: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        if resume_run_id is not None:
            completed_records = self._load_completed_records(
                resume_run_id, config.probe.probe_id
            )
            _reject_resume_mismatch(
                resume_run_id, config.probe, "", set(completed_records.keys())
            )
        run_id = resume_run_id if resume_run_id is not None else generate_run_id()
        persist_run_id = run_id if resume_run_id is not None else None
        timestamp = utc_now_iso()
        boundary = config.boundary
        signals = _synthetic_signals()
        interp_fn = make_real_interpretation_proposal_fn(
            boundary, usage_sink=interpretation_usage_sink
        )
        gist_fn = make_real_gist_proposal_fn(
            boundary, usage_sink=gist_usage_sink
        )
        me = self._snapshot.me1
        samples, mem_trace, rel_decisions = [], [], []

        for idx in range(config.samples_per_arm):
            identity_key = (config.probe.probe_id, None, None, idx)
            completed = completed_records.get(identity_key)
            if completed is not None:
                samples.append(ProbeSampleRecord.from_dict(completed))
                continue

            event_id = f"synth-event-{idx:04d}"
            objective_text = (
                config.probe.objective_event
                if config.probe.objective_event is not None
                else f"[SYNTHETIC PB-MEM] {config.probe.scene_question} sample {idx}"
            )
            noticed = (
                config.probe.perception_hint
                if config.probe.perception_hint is not None
                else f"[SYNTHETIC] noticed {event_id}"
            )
            ev = WorldEvent(
                event_id=event_id,
                objective_text=objective_text,
                participants=("kira", "synthetic_user"),
                scenario_repo_relative_path=me.scenario_repo_relative_path,
                json_path=me.json_path, source_sha256=me.sha256,
            )
            perc = CharacterPerception(
                character_id="kira", world_event_id=ev.event_id,
                noticed=noticed,
            )
            interp = interp_fn(ev, perc)          # CALL #1
            gist = gist_fn(ev, perc, interp)      # CALL #2
            cand = CharacterMemory(
                character_id="kira", world_event=ev, retained_gist=gist,
                salience=signals.score(), possible_distortion=None,
                tags=("frozen", "pb-mem"),
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
            sample = ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode="PB-MEM",
                state=None, arm=None, sample_index=idx,
                generation=gist, tags=("frozen", "pb-mem"),
            )
            samples.append(sample)
            if persist_run_id is not None:
                self._persist_sample(persist_run_id, sample)

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
        completed_records: Optional[Dict[Tuple[Any, ...], Dict[str, Any]]] = None,
        persist_run_id: Optional[str] = None,
        usage_sink: Optional[Any] = None,
    ) -> Tuple[ProbeSampleRecord, ...]:
        """Build baseline-arm samples with identical external input, no CIS injection.

        On a resume run (``completed_records`` / ``persist_run_id`` supplied),
        a baseline identity that is already persisted is reused unchanged
        (never re-invoked, never overwritten); only missing identities are
        generated and appended once.
        """
        canon_snapshot: Dict[str, Any] = {
            "relationships": {"user": {"trust": 0, "attraction": 0}},
        }
        completed_records = completed_records or {}
        samples: List[ProbeSampleRecord] = []
        for idx in range(config.samples_per_arm):
            identity_key = (config.probe.probe_id, None, arm, idx)
            completed = completed_records.get(identity_key)
            if completed is not None:
                samples.append(ProbeSampleRecord.from_dict(completed))
                continue
            baseline_msgs = build_baseline_messages(
                canon_snapshot=canon_snapshot,
                aside_memory=None,
                player_message=config.probe.scene_question,
            )
            gen = boundary.complete(baseline_msgs, usage_sink=usage_sink)
            sample = ProbeSampleRecord(
                probe_id=config.probe.probe_id, mode=config.probe.mode,
                state=None, arm=arm, sample_index=idx,
                generation=gen, tags=("synthetic", "baseline", arm.lower()),
            )
            samples.append(sample)
            if persist_run_id is not None:
                self._persist_sample(persist_run_id, sample)
        return tuple(samples)

    def run_pb_rec(
        self,
        config: ProbeRunConfig,
        *,
        resume_run_id: Optional[str] = None,
        usage_sink: Optional[Any] = None,
    ) -> ResultPackage:
        """Run PB-REC (KIRA_CANDIDATE + OTHER_CHARACTER_DECOY + GENERIC_DECOY).

        When ``resume_run_id`` is supplied, already-completed identities are
        skipped before any provider call (TD-21) and each fresh sample is
        appended to evidence immediately. ``usage_sink`` is forwarded to the
        provider for usage capture (TD-24); it must not affect output.
        """
        completed_records: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        if resume_run_id is not None:
            completed_records = self._load_completed_records(
                resume_run_id, config.probe.probe_id
            )
            _reject_resume_mismatch(
                resume_run_id, config.probe, "", set(completed_records.keys())
            )
        run_id = resume_run_id if resume_run_id is not None else generate_run_id()
        persist_run_id = run_id if resume_run_id is not None else None
        timestamp = utc_now_iso()
        boundary = config.boundary
        p4 = self._p4_exploration
        samples: List[ProbeSampleRecord] = []
        # KIRA candidate (CIS-arm)
        for idx in range(config.samples_per_arm):
            identity_key = (config.probe.probe_id, None, "KIRA_CANDIDATE", idx)
            completed = completed_records.get(identity_key)
            if completed is not None:
                sample = ProbeSampleRecord.from_dict(completed)
            else:
                ctx = assemble_cis_context(
                    p0=self._snapshot.p0, p3=self._canon_p3, p4=p4,
                    scene_question=config.probe.scene_question,
                )
                gen = boundary.complete(render_cis_messages(ctx), usage_sink=usage_sink)
                sample = ProbeSampleRecord(
                    probe_id=config.probe.probe_id, mode="PB-REC",
                    state=None, arm="KIRA_CANDIDATE", sample_index=idx,
                    generation=gen, tags=("synthetic", "pb-rec", "kira_candidate"),
                )
                if persist_run_id is not None:
                    self._persist_sample(persist_run_id, sample)
            samples.append(sample)
        # OTHER_CHARACTER_DECOY — synthetic non-Kira character (same external input, no CIS context)
        samples.extend(self._build_baseline_samples(
            boundary, config, arm="OTHER_CHARACTER_DECOY",
            completed_records=completed_records, persist_run_id=persist_run_id,
            usage_sink=usage_sink,
        ))
        # GENERIC_DECOY — another synthetic baseline pass
        samples.extend(self._build_baseline_samples(
            boundary, config, arm="GENERIC_DECOY",
            completed_records=completed_records, persist_run_id=persist_run_id,
            usage_sink=usage_sink,
        ))
        return self._assemble(
            run_id=run_id, timestamp=timestamp, mode="PB-REC", config=config,
            samples=tuple(samples),
            initial_p3={"trust": self._canon_p3.trust, "attraction": self._canon_p3.attraction},
        )

    # -- PB-AB -----------------------------------------------------------

    def _evidence_path(self, run_id: str, probe_id: str) -> str:
        """Per-probe evidence path (TD-24): each probe family owns its own
        single-probe evidence file, so a multi-family run under one ``run_id``
        resumes each family without tripping the cross-probe mismatch guard."""
        return f"evidence/{run_id}/{probe_id}/samples.jsonl"

    def _load_completed_records(
        self, run_id: str, probe_id: str
    ) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
        """Return already-persisted sample records for ``run_id``/``probe_id``
        keyed by the resume identity ``(probe_id, state, arm, sample_index)``.

        Reads the per-probe evidence JSONL. Fails closed (``ProbeRunnerError``)
        on any malformed/corrupt line or duplicate identity -- a partially
        written or ambiguous log is never silently skipped or deduplicated
        (TD-21).
        """
        path = self._evidence_path(run_id, probe_id)
        records: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        try:
            entries = self._storage.read_jsonl(path)
        except CisPilotStorageError as exc:
            raise ProbeRunnerError(
                f"malformed persisted evidence for run_id={run_id!r} "
                f"probe_id={probe_id!r} at {path!r}: {exc}"
            ) from exc
        for record in entries:
            if not isinstance(record, dict):
                raise ProbeRunnerError(
                    f"malformed persisted evidence for run_id={run_id!r} "
                    f"probe_id={probe_id!r} at {path!r}: expected a JSON object"
                )
            key = (
                record.get("probe_id"),
                record.get("state"),
                record.get("arm"),
                record.get("sample_index"),
            )
            if key in records:
                raise ProbeRunnerError(
                    f"duplicate evidence identity {key!r} for "
                    f"run_id={run_id!r}: refusing to silently deduplicate"
                )
            records[key] = record
        return records

    def _load_completed_keys(self, run_id: str, probe_id: str) -> set:
        """Identity set of already-persisted samples for ``run_id``/``probe_id``.

        Identity = (probe_id, state, arm, sample_index) per ProbeSampleRecord.sample_key().
        Fail closed on malformed or duplicate evidence (same guarantees as
        ``_load_completed_records``); empty set when no prior records exist.
        """
        return set(self._load_completed_records(run_id, probe_id).keys())

    def _persist_sample(self, run_id: str, sample: ProbeSampleRecord) -> None:
        """Append one sample to its probe's evidence JSONL (TD-8b crash-
        resilient path)."""
        self._storage.append_jsonl(
            self._evidence_path(run_id, sample.probe_id),
            sample.to_dict(),
        )

    def run_pb_ab(self, config: ProbeRunConfig, sub_mode: str,
                  *, resume_run_id: Optional[str] = None,
                  usage_sink: Optional[Any] = None) -> ResultPackage:
        if sub_mode not in ("T3-P3", "T3-P4", "COMBINED"):
            raise ProbeRunnerError(f"unsupported sub_mode: {sub_mode!r}")

        # Resume: load previously completed sample records (fail closed on
        # malformed or duplicate evidence).
        completed_records: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        if resume_run_id is not None:
            completed_records = self._load_completed_records(
                resume_run_id, config.probe.probe_id
            )
            _reject_resume_mismatch(
                resume_run_id, config.probe, sub_mode, set(completed_records.keys())
            )

        run_id = resume_run_id if resume_run_id is not None else generate_run_id()
        persist_run_id = run_id if resume_run_id is not None else None
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
                identity_key = (config.probe.probe_id, sub_mode, arm_label, idx)
                completed = completed_records.get(identity_key)
                if completed is not None:
                    # Already completed: reuse persisted evidence unchanged,
                    # never overwrite, never invoke the provider again.
                    sample = ProbeSampleRecord.from_dict(completed)
                else:
                    ctx = assemble_cis_context(
                        p0=self._snapshot.p0, p3=p3, p4=p4,
                        scene_question=config.probe.scene_question,
                    )
                    gen = boundary.complete(render_cis_messages(ctx), usage_sink=usage_sink)
                    sample = ProbeSampleRecord(
                        probe_id=config.probe.probe_id, mode="PB-AB",
                        state=sub_mode, arm=arm_label, sample_index=idx,
                        generation=gen,
                        tags=("synthetic", "pb-ab", sub_mode.lower()),
                    )
                    if persist_run_id is not None:
                        self._persist_sample(persist_run_id, sample)

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
                samples.append(sample)
        # Baseline A/B arms: same external scene/question, no P3/P4 injection
        samples.extend(self._build_baseline_samples(
            boundary, config, arm="BASELINE_A",
            completed_records=completed_records, persist_run_id=persist_run_id,
            usage_sink=usage_sink,
        ))
        samples.extend(self._build_baseline_samples(
            boundary, config, arm="BASELINE_B",
            completed_records=completed_records, persist_run_id=persist_run_id,
            usage_sink=usage_sink,
        ))
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