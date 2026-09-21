#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP application-facing adapter -- Lab-independent facade.

This is the intended single import surface for a future
``services.character_lab_application`` layer to reach the CRP reconstruction
engine. It imports ONLY from within ``services.crp_authoring``; it never
imports ``services.character_lab_application``, ``ui.character_lab``, or any
Character Companion/Studio module, so it can exist and be tested before the
Character Lab Foundation is published (see
CRP_MAINLINE_CONSOLIDATION_V1, Part 5 Case B).

Exposes exactly four conceptual operations (CRP_MAINLINE_CONSOLIDATION_V1
Part 11), each a thin wrapper over the existing, already-tested engine --
this module adds no new orchestration model, no persistence layer, and no
async infrastructure:

- ``evaluate_specialist_relevance`` -- wraps ``relevance.evaluate_r3_relevance``.
- ``prepare_reconstruction`` -- validates and bundles a caller-supplied plan
  (identity consistency across role tasks) WITHOUT executing it and WITHOUT
  requiring a provider_callable.
- ``start_reconstruction`` -- a single synchronous call into the existing
  ``orchestrator.run_reconstruction`` entrypoint. The provider_callable
  boundary is unchanged and always caller-supplied.
- ``get_reconstruction_result`` -- read-only load of a previously accepted
  ``CandidateCharacterPackage`` + its ``AcceptanceRecord`` from disk (e.g. the
  KIRA reference fixture). Never mutates, never promotes to Canon.

No provider construction and no network I/O occur anywhere in this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Tuple

from .acceptance_store import AcceptanceRecord, load_acceptance_record
from .candidate_package import CandidateCharacterPackage
from .candidate_rehydration import rehydrate_candidate_package
from .contracts import SourceEvidence
from .errors import CrpValidationError
from .knowledge_profile import KnowledgeProfile
from .orchestrator import run_reconstruction
from .registry import RoleRegistry
from .relevance import R3RelevanceResult, evaluate_r3_relevance
from .role_task import RoleResult, RoleTask
from .validator import ValidationReport
from .reconstruction_audit import ReconstructionAudit


def evaluate_specialist_relevance(evidence: Iterable[SourceEvidence]) -> R3RelevanceResult:
    """Application-facing wrapper for R3 relevance detection.

    Relevance alone NEVER authorizes execution -- see ``relevance`` module.
    """
    return evaluate_r3_relevance(evidence)


@dataclass(frozen=True)
class ReconstructionPlan:
    """A validated, not-yet-executed reconstruction plan.

    Immutable bundle of the exact arguments ``start_reconstruction`` will
    pass to the existing orchestrator. Produced only by
    ``prepare_reconstruction``, which enforces identity consistency across
    the supplied role tasks before any provider call is possible.
    """

    subject_id: str
    run_id: str
    evidence_snapshot_id: str
    evidence: Tuple[SourceEvidence, ...]
    registry: RoleRegistry
    profiles: Mapping[str, KnowledgeProfile]
    role_tasks: Tuple[RoleTask, ...]
    compile_context: Any
    audit_policy: Any
    evidence_payloads: Mapping[str, Mapping[str, Any]]


def prepare_reconstruction(
    *,
    subject_id: str,
    run_id: str,
    evidence_snapshot_id: str,
    evidence: Tuple[SourceEvidence, ...],
    registry: RoleRegistry,
    profiles: Mapping[str, KnowledgeProfile],
    role_tasks: Tuple[RoleTask, ...],
    compile_context: Any,
    audit_policy: Any,
    evidence_payloads: Mapping[str, Mapping[str, Any]],
) -> ReconstructionPlan:
    """Validate identity consistency and bundle a plan. No provider call.

    Fail-closed: every ``role_tasks`` entry must agree with the supplied
    ``subject_id``/``run_id``/``evidence_snapshot_id`` (the same cross-stage
    identity invariant the orchestrator itself enforces at execution time --
    checked here early, before any provider construction is even possible).
    Does not re-check or weaken the R3 authorization gate: that gate is
    already enforced, unconditionally, by ``RoleTask.__post_init__`` at
    task-construction time, before this function ever sees the task.
    """
    if not subject_id or not subject_id.strip():
        raise CrpValidationError("subject_id must be a non-empty string")
    if not run_id or not run_id.strip():
        raise CrpValidationError("run_id must be a non-empty string")
    if not evidence_snapshot_id or not evidence_snapshot_id.strip():
        raise CrpValidationError("evidence_snapshot_id must be a non-empty string")
    if not isinstance(role_tasks, tuple) or not role_tasks:
        raise CrpValidationError("role_tasks must be a non-empty tuple")

    for task in role_tasks:
        if not isinstance(task, RoleTask):
            raise CrpValidationError("every role_tasks entry must be a RoleTask")
        if task.subject_id != subject_id:
            raise CrpValidationError(
                f"role task {task.task_id!r} subject_id {task.subject_id!r} "
                f"!= plan subject_id {subject_id!r}"
            )
        if task.run_id != run_id:
            raise CrpValidationError(
                f"role task {task.task_id!r} run_id {task.run_id!r} "
                f"!= plan run_id {run_id!r}"
            )
        if task.evidence_snapshot_id != evidence_snapshot_id:
            raise CrpValidationError(
                f"role task {task.task_id!r} evidence_snapshot_id "
                f"{task.evidence_snapshot_id!r} != plan evidence_snapshot_id "
                f"{evidence_snapshot_id!r}"
            )

    return ReconstructionPlan(
        subject_id=subject_id,
        run_id=run_id,
        evidence_snapshot_id=evidence_snapshot_id,
        evidence=tuple(evidence),
        registry=registry,
        profiles=profiles,
        role_tasks=role_tasks,
        compile_context=compile_context,
        audit_policy=audit_policy,
        evidence_payloads=evidence_payloads,
    )


def start_reconstruction(
    plan: ReconstructionPlan,
    provider_callable: Any,
) -> Tuple[CandidateCharacterPackage, ReconstructionAudit, ValidationReport, Tuple[RoleResult, ...]]:
    """Execute a prepared plan through the existing orchestrator, once.

    This is the existing synchronous execution model (``orchestrator.
    run_reconstruction``) -- no new orchestration/async infrastructure is
    introduced. ``provider_callable`` remains entirely caller-supplied; this
    function never constructs a provider and never touches the network.
    """
    if not isinstance(plan, ReconstructionPlan):
        raise CrpValidationError("start_reconstruction requires a ReconstructionPlan")
    return run_reconstruction(
        subject_id=plan.subject_id,
        run_id=plan.run_id,
        evidence_snapshot_id=plan.evidence_snapshot_id,
        evidence=plan.evidence,
        registry=plan.registry,
        profiles=plan.profiles,
        role_tasks=plan.role_tasks,
        provider_callable=provider_callable,
        compile_context=plan.compile_context,
        audit_policy=plan.audit_policy,
        evidence_payloads=plan.evidence_payloads,
    )


@dataclass(frozen=True)
class AcceptedReconstructionResult:
    """A previously accepted package, loaded read-only from disk."""

    subject_id: str
    package: CandidateCharacterPackage
    acceptance: AcceptanceRecord


def get_reconstruction_result(root: Path, subject_id: str) -> AcceptedReconstructionResult:
    """Load a previously ACCEPTED reconstruction result, read-only.

    Reads exactly ``<root>/<subject_id>/ACCEPTANCE.json`` and
    ``<root>/<subject_id>/source_candidate.json`` (the same layout as
    ``accepted/kira/``). Never writes, never mutates Character Canon, never
    calls a provider. Fail-closed if no acceptance record exists yet
    (``acceptance_store.load_acceptance_record`` already raises in that
    case) -- this function never invents a placeholder result.
    """
    acceptance = load_acceptance_record(root, subject_id)
    candidate_path = Path(root) / subject_id / "source_candidate.json"
    if not candidate_path.exists():
        raise CrpValidationError(
            f"acceptance record exists for {subject_id!r} but source_candidate.json is missing "
            f"at {candidate_path}"
        )
    data = json.loads(candidate_path.read_text(encoding="utf-8"))
    package = rehydrate_candidate_package(data)
    return AcceptedReconstructionResult(subject_id=subject_id, package=package, acceptance=acceptance)
