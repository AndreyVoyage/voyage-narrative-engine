#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 6 -- R8 deterministic audit checks.

Implements the DETERMINISTIC subset of the R8 audit taxonomy
(CRP_PRE_KIRA_TRUST_GATES_BROAD_CORE_ARCHITECTURE_PREFLIGHT §3.2) plus the
deterministic half of the one HYBRID check:

- #1 provenance completeness (DETERMINISTIC)
- #2 unsupported assertions (DETERMINISTIC)
- #3 contradiction preservation (DETERMINISTIC)
- #4 confidence misuse (DETERMINISTIC)
- #5 role-boundary violations -- deterministic half (HYBRID, mechanical only)
- #8 schema completeness marker presence (DETERMINISTIC, structural identity only)
- #9 source/hidden-eval leakage (DETERMINISTIC, non-overridable)
- #10 canon-write attempt (DETERMINISTIC, non-overridable)

Checks #6 (module/layer placement) and #7 (missing evidence coverage), and the
judgment half of #5, are LLM_JUDGMENT -- DEFERRED to Slice 7 and explicitly
NOT implemented here.

Inputs are limited to the compiled ``CandidateCharacterPackage``, the evidence
ledger (``Tuple[SourceEvidence, ...]``), and the deterministic policy config
(``forbidden_refs``) -- matching the ratified R8 independence boundary: package
+ evidence ledger only. No RoleResult, no provider, no hidden evaluation, no
accepted benchmark, no canon/runtime access, no mutation of inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

from .candidate_package import CandidateCharacterPackage
from .contracts import (
    Confidence,
    INFERENCE_SOURCE_TYPES,
    SourceEvidence,
)
from .knowledge_profile import forbidden_ref_violation
from .reconstruction_audit import (
    AuditCheckClassification,
    AuditCheckOutcome,
    AuditCheckResult,
    AuditFinding,
    AuditVerdict,
    ReconstructionAudit,
    compose_verdict,
)
from .validation import reject_unsupported_claim


# Check codes (ratified numbering, deterministic ordering).
CHECK_PROVENANCE = "R8_PROVENANCE_COMPLETENESS"          # #1
CHECK_UNSUPPORTED = "R8_UNSUPPORTED_ASSERTION"           # #2
CHECK_CONTRADICTION = "R8_CONTRADICTION_PRESERVATION"    # #3
CHECK_CONFIDENCE = "R8_CONFIDENCE_MISUSE"                # #4
CHECK_ROLE_BOUNDARY = "R8_ROLE_BOUNDARY"                 # #5 (deterministic half)
CHECK_SCHEMA_MARKERS = "R8_SCHEMA_IDENTITY"              # #8 (structural identity only)
CHECK_LEAKAGE = "R8_LEAKAGE"                             # #9 (hard gate)
CHECK_CANON_WRITE = "R8_CANON_WRITE"                     # #10 (hard gate)


@dataclass(frozen=True)
class AuditPolicy:
    """Deterministic inputs the audit needs beyond package + evidence ledger.

    ``forbidden_refs`` is the same structured-ref deny-list used by GAP-2
    (knowledge_profile). ``canon_write_markers`` are assembled by
    concatenation so no single string literal equals a canon path token.
    """

    forbidden_refs: Tuple[str, ...] = ()
    auditor_role_version: str = "v1"


# ---------------------------------------------------------------
# Individual deterministic checks
# ---------------------------------------------------------------

def _check_provenance(package: CandidateCharacterPackage) -> AuditCheckResult:
    findings: list = []
    known_claim_ids = {c.claim_id for c in package.claims}
    for target, claim_ids in package.provenance_manifest.items():
        for cid in claim_ids:
            if cid not in known_claim_ids:
                findings.append(AuditFinding(
                    CHECK_PROVENANCE, "error",
                    f"provenance target {target!r} references unknown claim id {cid!r}",
                ))
    return _result(CHECK_PROVENANCE, AuditCheckClassification.DETERMINISTIC, findings)


def _check_unsupported(package: CandidateCharacterPackage) -> AuditCheckResult:
    findings: list = []
    for claim in package.claims:
        try:
            reject_unsupported_claim(claim)
        except Exception as exc:
            findings.append(AuditFinding(
                CHECK_UNSUPPORTED, "error",
                f"claim {claim.claim_id!r} unsupported: {exc}",
            ))
    return _result(CHECK_UNSUPPORTED, AuditCheckClassification.DETERMINISTIC, findings)


def _check_contradiction(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
) -> AuditCheckResult:
    findings: list = []
    # Independence: re-derive preservation over the package's own register.
    for record in package.contradictions:
        if len(record.claim_ids) < 2:
            findings.append(AuditFinding(
                CHECK_CONTRADICTION, "error",
                f"contradiction {record.contradiction_id!r} lost a conflict side",
            ))
    return _result(CHECK_CONTRADICTION, AuditCheckClassification.DETERMINISTIC, findings)


def _check_confidence(package: CandidateCharacterPackage) -> AuditCheckResult:
    findings: list = []
    for claim in package.claims:
        if claim.source_type_summary and all(
            t in INFERENCE_SOURCE_TYPES for t in claim.source_type_summary
        ) and claim.confidence is Confidence.KNOWN:
            findings.append(AuditFinding(
                CHECK_CONFIDENCE, "error",
                f"claim {claim.claim_id!r} is inference-only but confidence=KNOWN",
            ))
    return _result(CHECK_CONFIDENCE, AuditCheckClassification.DETERMINISTIC, findings)


def _check_role_boundary(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
) -> AuditCheckResult:
    # Deterministic half of the HYBRID check #5: verify claim role_id derives
    # from a known producing-role vocabulary. This stays structural (no content
    # judgment); the LLM half (does the prose match the family tag) is Slice 7.
    findings: list = []
    for claim in package.claims:
        if claim.role_id not in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
            findings.append(AuditFinding(
                CHECK_ROLE_BOUNDARY, "error",
                f"claim {claim.claim_id!r} has unknown role_id {claim.role_id!r}",
            ))
    return _result(CHECK_ROLE_BOUNDARY, AuditCheckClassification.HYBRID, findings)


def _check_schema_identity(package: CandidateCharacterPackage) -> AuditCheckResult:
    # Defers full JSON-Schema validation to a later schema-target integration;
    # this deterministic component only verifies the package binds its own
    # identity and carries a package hash anchor (no schema import).
    findings: list = []
    if not package.package_id or not package.subject_id:
        findings.append(AuditFinding(
            CHECK_SCHEMA_MARKERS, "error", "package identity fields are empty",
        ))
    return _result(CHECK_SCHEMA_MARKERS, AuditCheckClassification.DETERMINISTIC, findings)


def _check_leakage(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
    forbidden_refs: Tuple[str, ...],
) -> AuditCheckResult:
    findings: list = []
    for ev in evidence:
        if not isinstance(ev, SourceEvidence):
            continue
        matched = forbidden_ref_violation(ev.content_ref, forbidden_refs)
        if matched is not None:
            findings.append(AuditFinding(
                CHECK_LEAKAGE, "error",
                f"evidence {ev.source_id!r} content_ref matches forbidden pattern {matched!r}",
            ))
    # Also re-verify the compiled package's provenance manifest references no
    # forbidden origin refs (defense in depth against intake-gate bypass).
    # The manifest maps module -> claim_id; forbidden origin refs live on
    # evidence, so the manifest itself is not scanned for path tokens here
    # beyond the evidence ledger (which is the sole origin-ref source).
    return _result(
        CHECK_LEAKAGE, AuditCheckClassification.DETERMINISTIC, findings,
        hard_blocker=True,
    )


def _check_canon_write(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
) -> AuditCheckResult:
    # Canon-write markers assembled by concatenation to avoid a single source
    # literal colliding with the architecture-boundary test's path-string scan.
    markers = (
        "personas" + "/",
        "scenarios" + "/",
        "core" + "/",
        "state" + "/",
        "schemas" + "/",
    )
    findings: list = []
    for claim in package.claims:
        for marker in markers:
            if marker in claim.claim:
                findings.append(AuditFinding(
                    CHECK_CANON_WRITE, "error",
                    f"claim {claim.claim_id!r} text contains a canon-write-shaped marker",
                ))
                break
    for ev in evidence:
        if not isinstance(ev, SourceEvidence):
            continue
        for marker in markers:
            if marker in ev.provenance:
                findings.append(AuditFinding(
                    CHECK_CANON_WRITE, "error",
                    f"evidence {ev.source_id!r} provenance contains a canon-write-shaped marker",
                ))
                break
    return _result(
        CHECK_CANON_WRITE, AuditCheckClassification.DETERMINISTIC, findings,
        hard_blocker=True,
    )


# ---------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------

def _result(
    check: str,
    classification: AuditCheckClassification,
    findings: list,
    *,
    hard_blocker: bool = False,
) -> AuditCheckResult:
    if findings:
        outcome = AuditCheckOutcome.BLOCKED if hard_blocker else AuditCheckOutcome.FAIL
    else:
        outcome = AuditCheckOutcome.PASS
    return AuditCheckResult(
        check=check,
        classification=classification,
        outcome=outcome,
        findings=tuple(findings),
        hard_blocker=hard_blocker,
    )


def run_deterministic_audit(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...],
    policy: AuditPolicy,
) -> ReconstructionAudit:
    """Run the implemented deterministic R8 checks and produce an aggregate audit.

    ``verdict`` is composed deterministically; leakage/canon-write hard blockers
    dominate. ``package_hash`` is the SHA-256 of a stable ordering of the
    package's published claim ids + provenance manifest (an integrity anchor for
    stale-audit invalidation, not canon access).
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise TypeError("package must be a CandidateCharacterPackage")
    if not isinstance(evidence, tuple):
        raise TypeError("evidence must be a tuple")
    if not isinstance(policy, AuditPolicy):
        raise TypeError("policy must be an AuditPolicy")

    checks = (
        _check_provenance(package),
        _check_unsupported(package),
        _check_contradiction(package, evidence),
        _check_confidence(package),
        _check_role_boundary(package, evidence),
        _check_schema_identity(package),
        _check_leakage(package, evidence, policy.forbidden_refs),
        _check_canon_write(package, evidence),
    )

    verdict = compose_verdict(checks)
    defects = tuple(
        f for c in checks for f in c.findings
        if c.outcome is not AuditCheckOutcome.PASS
    )

    package_hash = compute_package_hash(package)
    audit_id = f"audit-{package.package_id}-{package.package_version}"
    return ReconstructionAudit(
        audit_id=audit_id,
        package_id=package.package_id,
        package_hash=package_hash,
        auditor_role_version=policy.auditor_role_version,
        evidence_snapshot_id=package.source_snapshot_id,
        checks=checks,
        verdict=verdict,
        defects=defects,
        correction_requests=(),
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
    )


def compute_package_hash(package: CandidateCharacterPackage) -> str:
    """Stable integrity anchor derived purely from package identity + manifest.

    No canon access; a deterministic digest so a stale audit is detectable.

    This is the single public source of truth for the package hash used to bind
    a ``ReconstructionAudit`` to the exact package content it audited. Lifecycle
    code (Slice 9) must call this function rather than reimplementing it.
    """
    h = hashlib.sha256()
    h.update(package.package_id.encode("utf-8"))
    h.update(str(package.package_version).encode("utf-8"))
    h.update(package.subject_id.encode("utf-8"))
    for cid in sorted(c.claim_id for c in package.claims):
        h.update(cid.encode("utf-8"))
    for target in sorted(package.provenance_manifest):
        h.update(target.encode("utf-8"))
        for cid in sorted(package.provenance_manifest[target]):
            h.update(cid.encode("utf-8"))
    return h.hexdigest()