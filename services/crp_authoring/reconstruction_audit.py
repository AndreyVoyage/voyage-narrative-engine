#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 6 -- ReconstructionAudit contract (R8 deterministic scaffolding).

Typed, immutable contract for the R8 Independent Evidence Auditor's result,
per ``CRP_MVP_CONTRACTS_v1.md`` §I. Slice 6 builds the DETERMINISTIC portion
only : the mechanical checks plus the deterministic half of the one HYBRID
check, per the authoritative R8 taxonomy in
``CRP_PRE_KIRA_TRUST_GATES_BROAD_CORE_ARCHITECTURE_PREFLIGHT`` §3.2. The LLM
judgment component (checks #6, #7 and the judgment half of #5) is DEFERRED to
Slice 7.

Verdict semantics (non-overlapping, ratified §4.2 of the preflight):

- ``PASS`` -- every implemented check ran to completion and none produced an
  error-severity finding.
- ``FAIL`` -- one or more checks ran to completion and found defects.
- ``INCONCLUSIVE`` -- one or more checks could not be fully evaluated.
- ``BLOCKED`` -- a non-overridable integrity violation (leakage #9 or
  canon-write #10).

Deterministic hard gates (#9 leak, #10 canon-write) are NON-OVERRIDABLE: a
future LLM judgment (Slice 7) may ADD findings but never convert a deterministic
``BLOCKED`` into PASS/ACCEPT/CLEAR. ``resolve_final_verdict`` is the explicit
deterministic composition rule (no implicit ordering).

No provider, no network, no canon/PAC/Sandbox access, no RoleResult dependency,
no hidden-evaluation or accepted-benchmark input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from .errors import CrpValidationError


class AuditVerdict(Enum):
    """R8 audit verdict (CRP_MVP_CONTRACTS_v1.md §I)."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class AuditCheckClassification(Enum):
    """Which component a check belongs to (R8 taxonomy, preflight §3.2)."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM_JUDGMENT = "LLM_JUDGMENT"
    HYBRID = "HYBRID"


class AuditCheckOutcome(Enum):
    """Per-check outcome of one audited check."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class AuditFinding:
    """One immutable audit finding, traceable to a specific check."""

    check: str
    severity: str
    message: str

    def __post_init__(self) -> None:
        _req(self.check, "check")
        _req(self.severity, "severity")
        _req(self.message, "message")


@dataclass(frozen=True)
class AuditCheckResult:
    """Aggregated result for one audited check.

    ``hard_blocker`` marks a NON-OVERRIDABLE gate check (leakage, canon-write).
    If such a check produces ``outcome=BLOCKED``, no future LLM judgment may
    clear it.
    """

    check: str
    classification: AuditCheckClassification
    outcome: AuditCheckOutcome
    findings: Tuple[AuditFinding, ...]
    hard_blocker: bool

    def __post_init__(self) -> None:
        _req(self.check, "check")
        if not isinstance(self.classification, AuditCheckClassification):
            raise CrpValidationError("classification must be an AuditCheckClassification")
        if not isinstance(self.outcome, AuditCheckOutcome):
            raise CrpValidationError("outcome must be an AuditCheckOutcome")
        if not isinstance(self.findings, tuple):
            raise CrpValidationError("findings must be a tuple of AuditFinding")
        for f in self.findings:
            if not isinstance(f, AuditFinding):
                raise CrpValidationError("findings must contain AuditFinding instances")
        if not isinstance(self.hard_blocker, bool):
            raise CrpValidationError("hard_blocker must be a bool")
        object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class ReconstructionAudit:
    """The aggregate R8 audit artifact (immutable; never edited after creation).

    ``judgment_provider_ref`` is reserved for the future LLM judgment component
    (Slice 7); it remains ``None`` for a deterministic-only audit so Slice 7 can
    populate it without contract redesign.
    """

    audit_id: str
    package_id: str
    package_hash: str
    auditor_role_version: str
    evidence_snapshot_id: str
    checks: Tuple[AuditCheckResult, ...]
    verdict: AuditVerdict
    defects: Tuple[AuditFinding, ...]
    correction_requests: Tuple[str, ...]
    created_at: datetime

    judgment_provider_ref: Optional[str] = None

    def __post_init__(self) -> None:
        _req(self.audit_id, "audit_id")
        _req(self.package_id, "package_id")
        _req(self.package_hash, "package_hash")
        _req(self.auditor_role_version, "auditor_role_version")
        _req(self.evidence_snapshot_id, "evidence_snapshot_id")
        if not isinstance(self.checks, tuple):
            raise CrpValidationError("checks must be a tuple of AuditCheckResult")
        for c in self.checks:
            if not isinstance(c, AuditCheckResult):
                raise CrpValidationError("checks must contain AuditCheckResult instances")
        if not isinstance(self.verdict, AuditVerdict):
            raise CrpValidationError("verdict must be an AuditVerdict")
        if not isinstance(self.defects, tuple):
            raise CrpValidationError("defects must be a tuple")
        for d in self.defects:
            if not isinstance(d, AuditFinding):
                raise CrpValidationError("defects must contain AuditFinding instances")
        if not isinstance(self.correction_requests, tuple):
            raise CrpValidationError("correction_requests must be a tuple")
        if not isinstance(self.created_at, datetime):
            raise CrpValidationError("created_at must be a datetime")
        if self.judgment_provider_ref is not None:
            _req(self.judgment_provider_ref, "judgment_provider_ref")
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "defects", tuple(self.defects))
        object.__setattr__(self, "correction_requests", tuple(self.correction_requests))


_VERDICT_RANK = {
    AuditVerdict.PASS: 0,
    AuditVerdict.INCONCLUSIVE: 1,
    AuditVerdict.FAIL: 2,
    AuditVerdict.BLOCKED: 3,
}


def compose_verdict(checks: Tuple[AuditCheckResult, ...]) -> AuditVerdict:
    """Deterministic aggregation of implemented check results.

    A hard-blocker check (leakage/canon-write) in BLOCKED state dominates
    everything. Otherwise FAIL > INCONCLUSIVE > PASS.
    """
    for c in checks:
        if c.hard_blocker and c.outcome is AuditCheckOutcome.BLOCKED:
            return AuditVerdict.BLOCKED
    if any(c.outcome is AuditCheckOutcome.FAIL for c in checks):
        return AuditVerdict.FAIL
    if any(c.outcome is AuditCheckOutcome.INCONCLUSIVE for c in checks):
        return AuditVerdict.INCONCLUSIVE
    return AuditVerdict.PASS


def resolve_final_verdict(
    deterministic_verdict: AuditVerdict,
    judgment_verdict: Optional[AuditVerdict] = None,
) -> AuditVerdict:
    """Explicit deterministic composition rule for future LLM judgment (Slice 7).

    A deterministic result may be combined with a future LLM judgment verdict;
    the most severe verdict wins, so a deterministic BLOCKED (hard gate) can
    never be overridden into PASS/ACCEPT/CLEAR, and a deterministic FAIL can
    never be upgraded to PASS by prose. The LLM may only add severity, never
    erase a deterministic blocker.
    """
    if not isinstance(deterministic_verdict, AuditVerdict):
        raise CrpValidationError("deterministic_verdict must be an AuditVerdict")
    if judgment_verdict is None:
        return deterministic_verdict
    if not isinstance(judgment_verdict, AuditVerdict):
        raise CrpValidationError("judgment_verdict must be an AuditVerdict or None")
    if deterministic_verdict is AuditVerdict.BLOCKED:
        return AuditVerdict.BLOCKED
    if _VERDICT_RANK[deterministic_verdict] >= _VERDICT_RANK[judgment_verdict]:
        return deterministic_verdict
    return judgment_verdict


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")