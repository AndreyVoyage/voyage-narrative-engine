#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP vNext MVP authoring domain (S0 foundation).

S0 provides only the evidence-ledger foundation: immutable value contracts
(``SourceEvidence``, ``RoleClaim``, ``ContradictionRecord``) and deterministic
validation. No role execution, no compiler, no registry, no CLI, no provider,
no canon access, no PAC/Sandbox access.
"""

from .candidate_package import CandidateCharacterPackage, PackageStatus
from .compiler import CompileContext, CompilerError, compile_candidate_package
from .executor import ExecutorError, execute_role_task
from .knowledge_profile import KnowledgeProfile, RetrievalPolicy
from .orchestrator import run_reconstruction
from .permissions import PERMISSIONS_BY_ROLE, Permission, permission_violations
from .registry import (
    ExecutionType,
    RoleRegistry,
    RoleRegistryEntry,
    RoleStatus,
)
from .role_task import CompletionStatus, RoleResult, RoleTask
from .contracts import (
    ClaimStatus,
    ClaimType,
    Confidence,
    ContradictionRecord,
    ResolutionStatus,
    RoleClaim,
    Severity,
    SourceEvidence,
    SourceType,
)
from .errors import CrpError, CrpValidationError, UnsupportedClaimError
from .validation import check_contradiction_integrity, reject_unsupported_claim
from .validator import ValidationFinding, ValidationReport, validate_package

__all__ = [
    "SourceEvidence",
    "RoleClaim",
    "ContradictionRecord",
    "SourceType",
    "Confidence",
    "ClaimType",
    "ClaimStatus",
    "Severity",
    "ResolutionStatus",
    "CandidateCharacterPackage",
    "PackageStatus",
    "CompileContext",
    "CompilerError",
    "compile_candidate_package",
    "ValidationFinding",
    "ValidationReport",
    "validate_package",
    "CrpError",
    "CrpValidationError",
    "UnsupportedClaimError",
    "RoleTask",
    "RoleResult",
    "CompletionStatus",
    "RoleRegistryEntry",
    "RoleRegistry",
    "RoleStatus",
    "ExecutionType",
    "KnowledgeProfile",
    "RetrievalPolicy",
    "Permission",
    "PERMISSIONS_BY_ROLE",
    "permission_violations",
    "ExecutorError",
    "execute_role_task",
    "run_reconstruction",
    "reject_unsupported_claim",
    "check_contradiction_integrity",
]
