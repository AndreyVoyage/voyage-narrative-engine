#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2A -- RoleTask and RoleResult contracts.

Immutable, detached plain-data value types. Least privilege is enforceable by
construction: ``allowed_evidence_ids`` and ``allowed_prior_results`` are
explicit, required allowlists (never "all"). No hidden chain-of-thought, no
unrestricted persona blob.

``RoleResult`` adds one OPTIONAL, additive field ``new_source_evidence``
(SAFE_SPECIFICATION_CHOICE; default empty) so R1 can return clarification-
derived evidence, per CRP_MVP_SPEC_v1.md §10 -- every other role leaves it
empty.

No provider, no network, no canon/PAC/Sandbox access, no legacy-KB import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from .contracts import ContradictionRecord, RoleClaim, SourceEvidence
from .errors import CrpValidationError


class CompletionStatus(Enum):
    """RoleResult completion status (CRP_MVP_CONTRACTS_v1.md §E)."""

    COMPLETE = "COMPLETE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


# Roles that are optional and gated: a RoleTask for one of these requires a
# non-empty ``activation_authorization_ref`` (human-driven authorization) and
# can never be self-activated by any role's own output (CRP-OD-9). Initially
# only R3.
GATED_OPTIONAL_ROLES = frozenset({"R3"})


@dataclass(frozen=True)
class RoleTask:
    """Bounded, least-privilege-enforcing unit of work (CRP_MVP_CONTRACTS_v1.md §D)."""

    task_id: str
    role_id: str
    role_version: str
    subject_id: str
    run_id: str
    evidence_snapshot_id: str
    allowed_evidence_ids: Tuple[str, ...]
    allowed_prior_results: Tuple[str, ...]
    knowledge_profile_ref: str
    input_contract_version: str
    output_contract_version: str
    permissions: Tuple[str, ...]
    task_goal: str
    revision_round: int
    activation_authorization_ref: Optional[str] = None

    stop_conditions: Optional[Any] = None
    deadline_policy: Optional[str] = None

    def __post_init__(self) -> None:
        _req(self.task_id, "task_id")
        _req(self.role_id, "role_id")
        _req(self.role_version, "role_version")
        _req(self.subject_id, "subject_id")
        _req(self.run_id, "run_id")
        _req(self.evidence_snapshot_id, "evidence_snapshot_id")
        if not isinstance(self.allowed_evidence_ids, tuple):
            raise CrpValidationError("allowed_evidence_ids must be a tuple")
        if not isinstance(self.allowed_prior_results, tuple):
            raise CrpValidationError("allowed_prior_results must be a tuple")
        _req(self.knowledge_profile_ref, "knowledge_profile_ref")
        _req(self.input_contract_version, "input_contract_version")
        _req(self.output_contract_version, "output_contract_version")
        if not isinstance(self.permissions, tuple) or not self.permissions:
            raise CrpValidationError("permissions must be a non-empty tuple")
        for p in self.permissions:
            if not isinstance(p, str) or not p.strip():
                raise CrpValidationError("permissions must contain non-empty strings")
        _req(self.task_goal, "task_goal")
        if isinstance(self.revision_round, bool) or not isinstance(self.revision_round, int):
            raise CrpValidationError("revision_round must be an int")
        if self.revision_round < 0 or self.revision_round > 2:
            raise CrpValidationError("revision_round must be within 0..2")
        if self.activation_authorization_ref is not None and not isinstance(self.activation_authorization_ref, str):
            raise CrpValidationError("activation_authorization_ref must be a string or None")
        if self.role_id in GATED_OPTIONAL_ROLES:
            if not self.activation_authorization_ref or not self.activation_authorization_ref.strip():
                raise CrpValidationError(
                    f"role_id {self.role_id!r} is a gated optional role and requires "
                    "a non-empty activation_authorization_ref"
                )

        object.__setattr__(self, "allowed_evidence_ids", tuple(self.allowed_evidence_ids))
        object.__setattr__(self, "allowed_prior_results", tuple(self.allowed_prior_results))
        object.__setattr__(self, "permissions", tuple(self.permissions))


@dataclass(frozen=True)
class RoleResult:
    """What a role hands back after executing a RoleTask (CRP_MVP_CONTRACTS_v1.md §E)."""

    task_id: str
    role_id: str
    role_version: str
    completion_status: CompletionStatus
    claims: Tuple[RoleClaim, ...]
    unknowns: Tuple[Any, ...]
    contradictions: Tuple[ContradictionRecord, ...]
    provenance_summary: Any

    requests_for_more_evidence: Tuple[Any, ...] = ()
    warnings: Tuple[str, ...] = ()
    questions_for_r1: Tuple[Any, ...] = ()
    new_source_evidence: Tuple[SourceEvidence, ...] = ()

    def __post_init__(self) -> None:
        _req(self.task_id, "task_id")
        _req(self.role_id, "role_id")
        _req(self.role_version, "role_version")
        if not isinstance(self.completion_status, CompletionStatus):
            raise CrpValidationError("completion_status must be a CompletionStatus")
        if not isinstance(self.claims, tuple):
            raise CrpValidationError("claims must be a tuple of RoleClaim")
        for claim in self.claims:
            if not isinstance(claim, RoleClaim):
                raise CrpValidationError("claims must contain RoleClaim instances")
        if not isinstance(self.unknowns, tuple):
            raise CrpValidationError("unknowns must be a tuple")
        if not isinstance(self.contradictions, tuple):
            raise CrpValidationError("contradictions must be a tuple")
        for crd in self.contradictions:
            if not isinstance(crd, ContradictionRecord):
                raise CrpValidationError("contradictions must contain ContradictionRecord instances")
        if not isinstance(self.requests_for_more_evidence, tuple):
            raise CrpValidationError("requests_for_more_evidence must be a tuple")
        if not isinstance(self.questions_for_r1, tuple):
            raise CrpValidationError("questions_for_r1 must be a tuple")
        if not isinstance(self.warnings, tuple):
            raise CrpValidationError("warnings must be a tuple")
        if not isinstance(self.new_source_evidence, tuple):
            raise CrpValidationError("new_source_evidence must be a tuple")
        for ev in self.new_source_evidence:
            if not isinstance(ev, SourceEvidence):
                raise CrpValidationError("new_source_evidence must contain SourceEvidence instances")

        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "unknowns", tuple(self.unknowns))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "requests_for_more_evidence", tuple(self.requests_for_more_evidence))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "questions_for_r1", tuple(self.questions_for_r1))
        object.__setattr__(self, "new_source_evidence", tuple(self.new_source_evidence))


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")