#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP vNext MVP authoring domain (S0 foundation).

S0 provides only the evidence-ledger foundation: immutable value contracts
(``SourceEvidence``, ``RoleClaim``, ``ContradictionRecord``) and deterministic
validation. No role execution, no compiler, no registry, no CLI, no provider,
no canon access, no PAC/Sandbox access.
"""

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
    "CrpError",
    "CrpValidationError",
    "UnsupportedClaimError",
    "reject_unsupported_claim",
    "check_contradiction_integrity",
]