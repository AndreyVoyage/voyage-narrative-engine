#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 8 -- Reconstruction Orchestrator (composition only, NON-CREATIVE).

The orchestrator is a thin, deterministic coordinator that composes already-
built and already-tested stage functions. It does NOT reimplement any stage
logic, does NOT own provider transport, does NOT construct provider configs,
and does NOT perform lifecycle transitions beyond what the pre-acceptance
``CandidateCharacterPackage`` already represents.

Stage order (fixed, fail-closed):

    role execution (caller-supplied ``role_tasks``, deterministic tuple order)
    -> aggregate RoleResult claims + contradiction records (verbatim, ordered)
    -> R6 ``compile_candidate_package`` (exactly once)
    -> R7 ``validate_package`` (fail-closed: invalid package stops BEFORE R8)
    -> R8 ``run_r8_analysis`` (single R8 entrypoint; deterministic hard
       blockers fail-fast internally and are non-overridable)

R8 is reached ONLY through ``run_r8_analysis``; this module never imports or
calls the deterministic-audit / message-render / parse / compose helpers
directly, and never imports the validation-only smoke runner.

Dependency injection only: the exact injected provider callable shape matches
the existing executor/R8 contracts (``Callable[[list], str]``). No provider
factory, no retry, no fallback, no alternate model/provider.

Package lifecycle: the compiled package stays pre-acceptance (DRAFT). This
module never assigns HUMAN_APPROVED / REJECTED, and does not introduce a new
persistent result schema -- it returns the four existing contract types.

No provider, no network, no canon/PAC/Sandbox access, no registry mutation.
"""

from __future__ import annotations

from typing import Callable, Mapping, Tuple

from .auditor_checks import AuditPolicy
from .candidate_package import CandidateCharacterPackage
from .compiler import CompileContext, compile_candidate_package
from .contracts import ContradictionRecord, RoleClaim, SourceEvidence
from .errors import CrpValidationError
from .executor import execute_role_task
from .knowledge_profile import KnowledgeProfile
from .r8_llm_judgment import run_r8_analysis
from .reconstruction_audit import ReconstructionAudit
from .registry import RoleRegistry
from .role_task import RoleResult, RoleTask
from .validator import ValidationReport, validate_package

# Injected provider callable contract (mirrors executor.ProviderCallable and
# service-free R8 provider shape; never constructed or imported from tools/).
ProviderCallable = Callable[[list], str]


def run_reconstruction(
    *,
    subject_id: str,
    run_id: str,
    evidence_snapshot_id: str,
    evidence: Tuple[SourceEvidence, ...],
    registry: RoleRegistry,
    profiles: Mapping[str, KnowledgeProfile],
    role_tasks: Tuple[RoleTask, ...],
    provider_callable: ProviderCallable,
    compile_context: CompileContext,
    audit_policy: AuditPolicy,
) -> Tuple[
    CandidateCharacterPackage,
    ReconstructionAudit,
    ValidationReport,
    Tuple[RoleResult, ...],
]:
    """Coordinate one full reconstruction run across R6/R7/R8.

    Executes the caller-supplied ``role_tasks`` in deterministic tuple order,
    aggregates their claims and contradiction records verbatim, compiles once,
    validates (fail-closed before R8), then runs R8 through its single
    existing entrypoint ``run_r8_analysis``.

    Cross-stage identity consistency (the only consistency the orchestrator
    owns -- downstream components check their own inputs) is enforced
    fail-closed: subject / run / evidence-snapshot / compile-context identity
    must all agree. Any violation raises ``CrpValidationError`` (no retry, no
    normalization, no silent continuation).
    """
    _check_inputs(
        subject_id=subject_id,
        run_id=run_id,
        evidence_snapshot_id=evidence_snapshot_id,
        evidence=evidence,
        registry=registry,
        profiles=profiles,
        role_tasks=role_tasks,
        provider_callable=provider_callable,
        compile_context=compile_context,
        audit_policy=audit_policy,
    )

    # --- 1) Execute roles in deterministic caller order -----------------
    role_results: list = []
    all_claims: list = []
    all_contradictions: list = []
    for task in role_tasks:
        result = execute_role_task(
            task,
            registry,
            profiles,
            provider_callable,
            evidence,
            tuple(role_results),
        )
        role_results.append(result)
        all_claims.extend(result.claims)
        all_contradictions.extend(result.contradictions)

    # --- 2) R6 compile exactly once ------------------------------------
    package = compile_candidate_package(
        compile_context,
        tuple(all_claims),
        tuple(all_contradictions),
    )

    # --- 3) R7 validate (fail-closed before R8) ------------------------
    validation_report = validate_package(
        package,
        evidence,
        input_contradictions=tuple(all_contradictions),
    )
    if not validation_report.valid:
        raise CrpValidationError(
            "reconstruction halted: R7 validation reported an invalid package "
            "(R8 audit was not invoked)"
        )

    # --- 4) R8 audit via the single existing entrypoint -----------------
    audit = run_r8_analysis(
        package,
        evidence,
        provider_callable,
        forbidden_refs=audit_policy.forbidden_refs,
    )

    return (
        package,
        audit,
        validation_report,
        tuple(role_results),
    )


def _check_inputs(
    *,
    subject_id: str,
    run_id: str,
    evidence_snapshot_id: str,
    evidence: Tuple[SourceEvidence, ...],
    registry: RoleRegistry,
    profiles: Mapping[str, KnowledgeProfile],
    role_tasks: Tuple[RoleTask, ...],
    provider_callable: ProviderCallable,
    compile_context: CompileContext,
    audit_policy: AuditPolicy,
) -> None:
    """Fail-closed argument + cross-stage identity checks (bounded, no repair)."""
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise CrpValidationError("subject_id must be a non-empty string")
    if not isinstance(run_id, str) or not run_id.strip():
        raise CrpValidationError("run_id must be a non-empty string")
    if not isinstance(evidence_snapshot_id, str) or not evidence_snapshot_id.strip():
        raise CrpValidationError("evidence_snapshot_id must be a non-empty string")

    if not isinstance(compile_context, CompileContext):
        raise CrpValidationError("compile_context must be a CompileContext")
    if not isinstance(registry, RoleRegistry):
        raise CrpValidationError("registry must be a RoleRegistry")
    if not isinstance(audit_policy, AuditPolicy):
        raise CrpValidationError("audit_policy must be an AuditPolicy")
    if not isinstance(profiles, Mapping):
        raise CrpValidationError("profiles must be a mapping of KnowledgeProfile")
    if not isinstance(evidence, tuple):
        raise CrpValidationError("evidence must be a tuple of SourceEvidence")
    if not callable(provider_callable):
        raise CrpValidationError("provider_callable is a required injected callable")

    if not isinstance(role_tasks, tuple) or not role_tasks:
        raise CrpValidationError("role_tasks must be a non-empty tuple of RoleTask")

    # --- cross-stage identity (subject / run / snapshot / compile context) ---
    if compile_context.subject_id != subject_id:
        raise CrpValidationError(
            f"compile_context.subject_id {compile_context.subject_id!r} != subject_id {subject_id!r}"
        )
    if compile_context.source_snapshot_id != evidence_snapshot_id:
        raise CrpValidationError(
            f"compile_context.source_snapshot_id {compile_context.source_snapshot_id!r} "
            f"!= evidence_snapshot_id {evidence_snapshot_id!r}"
        )

    for task in role_tasks:
        if not isinstance(task, RoleTask):
            raise CrpValidationError("role_tasks must contain RoleTask instances")
        if task.subject_id != subject_id:
            raise CrpValidationError(
                f"role_task {task.task_id!r} subject_id {task.subject_id!r} != subject_id {subject_id!r}"
            )
        if task.run_id != run_id:
            raise CrpValidationError(
                f"role_task {task.task_id!r} run_id {task.run_id!r} != run_id {run_id!r}"
            )
        if task.evidence_snapshot_id != evidence_snapshot_id:
            raise CrpValidationError(
                f"role_task {task.task_id!r} evidence_snapshot_id {task.evidence_snapshot_id!r} "
                f"!= evidence_snapshot_id {evidence_snapshot_id!r}"
            )