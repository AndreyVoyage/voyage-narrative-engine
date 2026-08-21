#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 9 -- Candidate lifecycle + explicit human acceptance.

This is the ONLY place a ``CandidateCharacterPackage`` may transition to the
terminal human states ``HUMAN_APPROVED`` and ``REJECTED``. All transitions here
are explicit, provider-free, persistence-free, and immutable.

OD-S9 policy (owner-ratified, not changeable here):

- OD-S9-01: ``accept_candidate`` may approve only ``audit.verdict == PASS``.
  FAIL / INCONCLUSIVE / BLOCKED are never acceptable; BLOCKED is non-overridable.
  There is no non-PASS human override path.
- OD-S9-02: ``REJECTED`` is an explicit human decision, terminal for the exact
  package version. It is never produced automatically from R7/R8 outcomes.
- OD-S9-03: acceptance/rejection never changes package_id / package_version /
  lineage; it changes lifecycle state, not reconstructed facts.
- OD-S9-04: no resubmission/editing-after-accept workflow in v0; accepted
  objects are immutable; future correction is a later/new candidate revision.
- OD-S9-05: non-empty unknowns/contradictions do NOT block HUMAN_APPROVED; they
  are preserved exactly.
- OD-S9-06: accepting an already HUMAN_APPROVED (or REJECTED) package hard-fails.

The lifecycle must re-use the single public source of truth for package hashing
(``auditor_checks.compute_package_hash``); a stale audit (hash mismatch) can
never authorize transition. No provider, no network, no canon/persistence.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from .auditor_checks import compute_package_hash
from .candidate_package import CandidateCharacterPackage, PackageStatus
from .errors import CrpValidationError
from .reconstruction_audit import AuditVerdict, ReconstructionAudit
from .validator import ValidationReport


# ---------------------------------------------------------------------------
# Acceptance record (frozen, detached, no provider/credential material)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AcceptanceRecord:
    """Immutable record of one explicit human lifecycle decision.

    ``decision`` is closed to ``HUMAN_APPROVED`` / ``REJECTED`` (the two
    terminal human states). ``decided_by`` is the human-authority reference
    (neutral naming so a single schema serves both acceptance and rejection).
    ``reason`` is optional for a normal PASS acceptance, required for rejection.
    """

    acceptance_id: str
    package_id: str
    package_version: int
    subject_id: str
    package_hash: str
    audit_id: Optional[str]
    decision: PackageStatus
    decided_by: str
    decided_at: str
    reason: Optional[str]
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        _req(self.acceptance_id, "acceptance_id")
        _req(self.package_id, "package_id")
        if isinstance(self.package_version, bool) or not isinstance(self.package_version, int) \
                or self.package_version < 0:
            raise CrpValidationError("package_version must be an int >= 0")
        _req(self.subject_id, "subject_id")
        _req(self.package_hash, "package_hash")
        if self.audit_id is not None:
            _req(self.audit_id, "audit_id")
        if self.decision is not PackageStatus.HUMAN_APPROVED \
                and self.decision is not PackageStatus.REJECTED:
            raise CrpValidationError(
                f"decision must be HUMAN_APPROVED or REJECTED, got {self.decision!r}"
            )
        _req(self.decided_by, "decided_by")
        _req(self.decided_at, "decided_at")
        if self.reason is not None:
            _req(self.reason, "reason")
        if self.supersedes is not None:
            _req(self.supersedes, "supersedes")


# ---------------------------------------------------------------------------
# Mechanical lifecycle advancement
# ---------------------------------------------------------------------------

def advance_to_audited(
    package: CandidateCharacterPackage,
    validation_report: ValidationReport,
    audit: ReconstructionAudit,
) -> CandidateCharacterPackage:
    """Mechanically close DRAFT -> AUDITED for a successfully validated + audited
    package. Never auto-accepts; requires an explicit later human action.

    Invariants (fail-closed):
    - input package status is DRAFT;
    - ``validation_report.valid`` is True;
    - ``audit.package_id`` equals ``package.package_id``;
    - ``audit.evidence_snapshot_id`` equals ``package.source_snapshot_id``;
    - ``compute_package_hash(package)`` equals ``audit.package_hash`` (stale
      audit can never bind);

    Returns a NEW frozen package (status=AUDITED) with ``validation_results``
    and ``audit_result`` populated via the package's existing fields. The input
    object is never mutated.
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise CrpValidationError("package must be a CandidateCharacterPackage")
    if package.status is not PackageStatus.DRAFT:
        raise CrpValidationError(
            f"advance_to_audited requires status DRAFT, got {package.status.value!r}"
        )
    if not isinstance(validation_report, ValidationReport):
        raise CrpValidationError("validation_report must be a ValidationReport")
    if not validation_report.valid:
        raise CrpValidationError("cannot advance: R7 validation reported an invalid package")
    if not isinstance(audit, ReconstructionAudit):
        raise CrpValidationError("audit must be a ReconstructionAudit")
    if audit.package_id != package.package_id:
        raise CrpValidationError(
            f"audit.package_id {audit.package_id!r} != package.package_id {package.package_id!r}"
        )
    if audit.evidence_snapshot_id != package.source_snapshot_id:
        raise CrpValidationError(
            f"audit.evidence_snapshot_id {audit.evidence_snapshot_id!r} "
            f"!= package.source_snapshot_id {package.source_snapshot_id!r}"
        )
    if compute_package_hash(package) != audit.package_hash:
        raise CrpValidationError("stale audit: package hash does not match audit.package_hash")

    return dataclasses.replace(
        package,
        status=PackageStatus.AUDITED,
        validation_results={"report": validation_report},
        audit_result=audit,
    )


# ---------------------------------------------------------------------------
# Explicit human acceptance / rejection
# ---------------------------------------------------------------------------

def accept_candidate(
    package: CandidateCharacterPackage,
    audit: ReconstructionAudit,
    *,
    accepted_by: str,
    acceptance_id: str,
    reason: Optional[str] = None,
    accepted_at: Optional[str] = None,
) -> Tuple[CandidateCharacterPackage, AcceptanceRecord]:
    """Explicit human approval of an AUDITED package with verdict PASS.

    Fail-closed refusals:
    - package not AUDITED;
    - package already HUMAN_APPROVED or REJECTED (OD-S9-06);
    - audit.verdict not PASS (FAIL/INCONCLUSIVE/BLOCKED are never acceptable);
    - audit.package_id mismatch;
    - stale hash (compute_package_hash != audit.package_hash).

    Returns ``(new_package, AcceptanceRecord)`` with status HUMAN_APPROVED and
    NO reconstructed-fact change (identity/version/lineage/content preserved).
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise CrpValidationError("package must be a CandidateCharacterPackage")
    if package.status is PackageStatus.HUMAN_APPROVED:
        raise CrpValidationError("package is already HUMAN_APPROVED (repeated accept is forbidden)")
    if package.status is PackageStatus.REJECTED:
        raise CrpValidationError("a REJECTED package cannot be accepted")
    if package.status is not PackageStatus.AUDITED:
        raise CrpValidationError(
            f"accept_candidate requires status AUDITED, got {package.status.value!r}"
        )
    if not isinstance(audit, ReconstructionAudit):
        raise CrpValidationError("audit must be a ReconstructionAudit")
    if audit.verdict is not AuditVerdict.PASS:
        raise CrpValidationError(
            f"only verdict PASS may be accepted (got {audit.verdict.value!r}); "
            "FAIL/INCONCLUSIVE/BLOCKED are not acceptable"
        )
    if audit.package_id != package.package_id:
        raise CrpValidationError(
            f"audit.package_id {audit.package_id!r} != package.package_id {package.package_id!r}"
        )
    if compute_package_hash(package) != audit.package_hash:
        raise CrpValidationError("stale audit: package hash does not match audit.package_hash")

    new_package = dataclasses.replace(package, status=PackageStatus.HUMAN_APPROVED)
    record = AcceptanceRecord(
        acceptance_id=acceptance_id,
        package_id=package.package_id,
        package_version=package.package_version,
        subject_id=package.subject_id,
        package_hash=compute_package_hash(package),
        audit_id=audit.audit_id,
        decision=PackageStatus.HUMAN_APPROVED,
        decided_by=accepted_by,
        decided_at=accepted_at or _now_iso(),
        reason=reason,
    )
    return (new_package, record)


def reject_candidate(
    package: CandidateCharacterPackage,
    *,
    rejected_by: str,
    acceptance_id: str,
    reason: str,
    rejected_at: Optional[str] = None,
) -> Tuple[CandidateCharacterPackage, AcceptanceRecord]:
    """Explicit human rejection of a PRE-ACCEPTANCE package.

    Allowed source status: DRAFT / VALIDATED / AUDITED.
    Forbidden source status: HUMAN_APPROVED / REJECTED (terminal).

    ``reason`` is REQUIRED. Returns ``(new_package, AcceptanceRecord)`` with
    status REJECTED and unchanged identity/version/lineage/content. A rejection
    is terminal for this exact package version (OD-S9-02).
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise CrpValidationError("package must be a CandidateCharacterPackage")
    if package.status is PackageStatus.HUMAN_APPROVED:
        raise CrpValidationError("a HUMAN_APPROVED package cannot be rejected")
    if package.status is PackageStatus.REJECTED:
        raise CrpValidationError("package is already REJECTED (repeated reject is forbidden)")

    _req(rejected_by, "rejected_by")
    _req(reason, "reason")

    audit_id = None
    if isinstance(package.audit_result, ReconstructionAudit):
        audit_id = package.audit_result.audit_id

    new_package = dataclasses.replace(package, status=PackageStatus.REJECTED)
    record = AcceptanceRecord(
        acceptance_id=acceptance_id,
        package_id=package.package_id,
        package_version=package.package_version,
        subject_id=package.subject_id,
        package_hash=compute_package_hash(package),
        audit_id=audit_id,
        decision=PackageStatus.REJECTED,
        decided_by=rejected_by,
        decided_at=rejected_at or _now_iso(),
        reason=reason,
    )
    return (new_package, record)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")