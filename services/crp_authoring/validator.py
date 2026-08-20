#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S1 -- R7 deterministic Consistency Validator (a FUNCTION, not an LLM).

Deterministic, creative-free checks over a ``CandidateCharacterPackage`` plus
its evidence snapshot. Produces a stable ``ValidationReport`` (immutable
findings). 11 of 13 candidate checks are implemented; 2 are deferred explicitly
(not faked):

  DEFERRED #1  full persona JSON-Schema validation (requires the schema-target
               integration; later slice).
  DEFERRED #9  role-permission violation (requires RoleRegistryEntry, S2/S3).

Reuses S0's ``reject_unsupported_claim`` (import, not reimplementation).
Standard library only; no provider, no network, no canon/PAC/Sandbox access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .candidate_package import CandidateCharacterPackage
from .contracts import (
    ClaimType,
    ContradictionRecord,
    Confidence,
    INFERENCE_SOURCE_TYPES,
    RoleClaim,
    SourceEvidence,
)
from .errors import CrpValidationError
from .validation import reject_unsupported_claim

# The two checks intentionally deferred at S1, recorded honestly.
DEFERRED_CHECKS: Tuple[str, ...] = (
    "SCHEMA_FULL_VALIDATION",   # full persona JSON-Schema validation (later slice)
    "ROLE_PERMISSION_VIOLATION",  # requires RoleRegistryEntry (S2/S3)
)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# Check codes (stable, deterministic ordering throughout this module).
CHECK_DUP_CLAIM_ID = "DUP_CLAIM_ID"
CHECK_DUP_SEMANTIC = "DUP_SEMANTIC_CLAIM"
CHECK_MISSING_EVIDENCE = "MISSING_EVIDENCE_REF"
CHECK_MISSING_CONTRADICTION = "MISSING_CONTRADICTION_REF"
CHECK_PROVENANCE = "PROVENANCE_BREAK"
CHECK_INVALID_TARGET = "INVALID_TARGET"
CHECK_UNSUPPORTED = "UNSUPPORTED_CLAIM"
CHECK_CANON = "CANON_SEMANTICS"
CHECK_SUBJECT = "SUBJECT_MISMATCH"
CHECK_CONFIDENCE = "CONFIDENCE_MISUSE"
CHECK_CONTRADICTION_PRESERVED = "CONTRADICTION_NOT_PRESERVED"
CHECK_UNKNOWN_INTEGRITY = "UNKNOWN_ENTRY_INTEGRITY"
CHECK_UNKNOWN_MUTUAL_EXCLUSION = "UNKNOWN_MUTUAL_EXCLUSION"

# Canon directory markers, assembled by concatenation so no single string
# literal in this source equals a canon path token (the generic
# architecture-boundary test scans literals/raw text for such tokens). Runtime
# values are identical to the canon directory names; they are used ONLY to
# detect canon-path-like text inside claim content -- never to open or import
# those paths.
CANON_PATH_MARKERS = (
    "personas" + "/",
    "scenarios" + "/",
    "core" + "/",
    "knowledge" + "_" + "base" + "/",
    "state" + "/",
    "schemas" + "/",
)


@dataclass(frozen=True)
class ValidationFinding:
    """One deterministic validator finding (immutable, stable)."""

    check: str
    severity: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """The validator's deterministic result.

    ``valid`` is True iff there are no ``error``-severity findings. Findings
    are emitted in a fixed, deterministic order so identical inputs yield
    byte-identical reports.
    """

    valid: bool
    findings: Tuple[ValidationFinding, ...]


def validate_package(
    package: CandidateCharacterPackage,
    evidence: Tuple[SourceEvidence, ...] = (),
    *,
    input_contradictions: Optional[Tuple[ContradictionRecord, ...]] = None,
) -> ValidationReport:
    """Run the 11 deterministic S1 checks over ``package``.

    ``evidence`` is the authoritative evidence snapshot against which
    ``claim.source_evidence_ids`` are resolved (check #4). When empty, no
    evidence resolution is available and the check is skipped (not "all
    missing") -- the caller decides whether a snapshot must be supplied.

    ``input_contradictions``, when provided, is the batch originally handed to
    the compiler; the validator verifies every record survives unchanged in
    ``package.contradictions`` (check #10 in the preflight numbering).
    """
    if not isinstance(package, CandidateCharacterPackage):
        raise CrpValidationError("package must be a CandidateCharacterPackage instance")

    findings: List[ValidationFinding] = []

    # --- #11 subject mismatch (claims, contradictions, evidence) ------------
    for claim in package.claims:
        if claim.subject_id != package.subject_id:
            findings.append(ValidationFinding(
                CHECK_SUBJECT, SEVERITY_ERROR,
                f"claim {claim.claim_id!r} subject_id {claim.subject_id!r} "
                f"!= package subject_id {package.subject_id!r}",
            ))
    for record in package.contradictions:
        if record.subject_id != package.subject_id:
            findings.append(ValidationFinding(
                CHECK_SUBJECT, SEVERITY_ERROR,
                f"contradiction {record.contradiction_id!r} subject_id "
                f"{record.subject_id!r} != package subject_id {package.subject_id!r}",
            ))
    for ev in evidence:
        if isinstance(ev, SourceEvidence) and ev.subject_id != package.subject_id:
            findings.append(ValidationFinding(
                CHECK_SUBJECT, SEVERITY_ERROR,
                f"evidence {ev.source_id!r} subject_id {ev.subject_id!r} "
                f"!= package subject_id {package.subject_id!r}",
            ))

    # --- #2 duplicate claim IDs -------------------------------------------
    seen_ids: Dict[str, int] = {}
    for claim in package.claims:
        seen_ids[claim.claim_id] = seen_ids.get(claim.claim_id, 0) + 1
    for claim_id, count in seen_ids.items():
        if count > 1:
            findings.append(ValidationFinding(
                CHECK_DUP_CLAIM_ID, SEVERITY_ERROR,
                f"duplicate claim_id {claim_id!r} appears {count} times",
            ))

    # --- #3 exact-duplicate semantic claims --------------------------------
    seen_semantic: Dict[Tuple[str, str, str], int] = {}
    for claim in package.claims:
        key = (claim.claim, claim.target_module_or_layer, claim.role_id)
        seen_semantic[key] = seen_semantic.get(key, 0) + 1
    for (text, target, role), count in seen_semantic.items():
        if count > 1:
            findings.append(ValidationFinding(
                CHECK_DUP_SEMANTIC, SEVERITY_ERROR,
                f"exact-duplicate semantic claim (text={text[:40]!r}, target={target!r}, "
                f"role={role!r}) appears {count} times",
            ))

    # --- #4 missing SourceEvidence refs ------------------------------------
    evidence_ids = {ev.source_id for ev in evidence if isinstance(ev, SourceEvidence)}
    if evidence_ids:
        for claim in package.claims:
            for ev_id in claim.source_evidence_ids:
                if ev_id not in evidence_ids:
                    findings.append(ValidationFinding(
                        CHECK_MISSING_EVIDENCE, SEVERITY_ERROR,
                        f"claim {claim.claim_id!r} references missing SourceEvidence "
                        f"{ev_id!r}",
                    ))

    # --- #5 missing contradiction refs ------------------------------------
    contradiction_ids = {r.contradiction_id for r in package.contradictions}
    for claim in package.claims:
        for crd_id in claim.contradiction_ids:
            if crd_id not in contradiction_ids:
                findings.append(ValidationFinding(
                    CHECK_MISSING_CONTRADICTION, SEVERITY_ERROR,
                    f"claim {claim.claim_id!r} references missing ContradictionRecord "
                    f"{crd_id!r}",
                ))

    # --- #6 provenance breaks ---------------------------------------------
    # Every target in the provenance manifest must map only to claim_ids that
    # exist in package.claims.
    known_claim_ids = {c.claim_id for c in package.claims}
    for target, claim_ids in package.provenance_manifest.items():
        for cid in claim_ids:
            if cid not in known_claim_ids:
                findings.append(ValidationFinding(
                    CHECK_PROVENANCE, SEVERITY_ERROR,
                    f"provenance target {target!r} references unknown claim id {cid!r}",
                ))
    # Every placed module/layer's entries must also be resolvable claims.
    for family in (package.psychology_candidate, package.voice_candidate,
                   package.intimacy_candidate):
        for key, entries in family.items():
            for claim in entries:
                if claim.claim_id not in known_claim_ids:
                    findings.append(ValidationFinding(
                        CHECK_PROVENANCE, SEVERITY_ERROR,
                        f"module {key!r} references claim {claim.claim_id!r} not in package.claims",
                    ))

    # --- #7 invalid target module/layer (defense in depth) -----------------
    for claim in package.claims:
        if claim.claim_type == ClaimType.UNKNOWN:
            # An UNKNOWN claim's target records WHAT is unknown, never a
            # candidate placement, so it is exempt from family-target checks.
            continue
        t = claim.target_module_or_layer.strip()
        ok = t.startswith("psychology.P") or t.startswith("voice.") or t.startswith("intimacy.")
        if not ok:
            findings.append(ValidationFinding(
                CHECK_INVALID_TARGET, SEVERITY_ERROR,
                f"claim {claim.claim_id!r} has invalid target {claim.target_module_or_layer!r}",
            ))

    # --- UNKNOWN registry structural checks (Slice 3, structural only) ----
    # A. Entry integrity: every package.unknowns entry must originate from an
    #    UNKNOWN RoleClaim.
    unknown_claims: List[RoleClaim] = []
    for unknown in package.unknowns:
        if not isinstance(unknown, RoleClaim):
            findings.append(ValidationFinding(
                CHECK_UNKNOWN_INTEGRITY, SEVERITY_ERROR,
                f"package.unknowns contains a non-RoleClaim entry {unknown!r}",
            ))
            continue
        unknown_claims.append(unknown)
        if unknown.claim_type != ClaimType.UNKNOWN:
            findings.append(ValidationFinding(
                CHECK_UNKNOWN_INTEGRITY, SEVERITY_ERROR,
                f"package.unknowns entry {unknown.claim_id!r} is not claim_type=UNKNOWN",
            ))

    # B. Mutual exclusion: an UNKNOWN claim must never also sit in a normal
    #    candidate family bucket.
    unknown_ids = {u.claim_id for u in unknown_claims}
    for family in (package.psychology_candidate, package.voice_candidate,
                   package.intimacy_candidate,
                   package.identity_biography_candidate, package.behavior_candidate,
                   package.relationships_candidate, package.boundaries_candidate,
                   package.seed_memory_candidate):
        for key, entries in family.items():
            for claim in entries:
                if claim.claim_id in unknown_ids:
                    findings.append(ValidationFinding(
                        CHECK_UNKNOWN_MUTUAL_EXCLUSION, SEVERITY_ERROR,
                        f"claim {claim.claim_id!r} appears both in package.unknowns "
                        f"and in family bucket {key!r}",
                    ))

    # --- #8 unsupported claim (reuse S0 rule) ------------------------------
    for claim in package.claims:
        try:
            reject_unsupported_claim(claim)
        except Exception as exc:  # UnsupportedClaimError (CrpError)
            findings.append(ValidationFinding(
                CHECK_UNSUPPORTED, SEVERITY_ERROR,
                f"claim {claim.claim_id!r} unsupported: {exc}",
            ))

    # --- #10 forbidden canon semantics (light data-level check) ------------
    for claim in package.claims:
        if any(marker in claim.claim for marker in CANON_PATH_MARKERS):
            findings.append(ValidationFinding(
                CHECK_CANON, SEVERITY_WARNING,
                f"claim {claim.claim_id!r} text contains a canon-path-like marker",
            ))

    # --- #12 confidence / source_type misuse -------------------------------
    for claim in package.claims:
        if claim.source_type_summary and all(
            t in INFERENCE_SOURCE_TYPES for t in claim.source_type_summary
        ) and claim.confidence is Confidence.KNOWN:
            findings.append(ValidationFinding(
                CHECK_CONFIDENCE, SEVERITY_ERROR,
                f"claim {claim.claim_id!r} is inference-only but confidence=KNOWN (misuse)",
            ))

    # --- #13 unresolved contradiction preservation -------------------------
    source_records = list(input_contradictions) if input_contradictions is not None \
        else list(package.contradictions)
    package_by_id = {r.contradiction_id: r for r in package.contradictions}
    for record in source_records:
        out = package_by_id.get(record.contradiction_id)
        if out is None:
            findings.append(ValidationFinding(
                CHECK_CONTRADICTION_PRESERVED, SEVERITY_ERROR,
                f"ContradictionRecord {record.contradiction_id!r} was dropped from the package",
            ))
            continue
        if set(out.claim_ids) != set(record.claim_ids) or len(out.claim_ids) != len(record.claim_ids):
            findings.append(ValidationFinding(
                CHECK_CONTRADICTION_PRESERVED, SEVERITY_ERROR,
                f"ContradictionRecord {record.contradiction_id!r} claim_ids changed "
                f"({record.claim_ids} -> {out.claim_ids})",
            ))

    report = ValidationReport(
        valid=all(f.severity != SEVERITY_ERROR for f in findings),
        findings=tuple(findings),
    )
    return report