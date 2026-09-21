#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S0 -- deterministic validation over the evidence-ledger contracts.

Pure, side-effect-free functions. No provider, no network, no canon access,
no PAC/Sandbox import. Enforces the two load-bearing S0 invariants:

1. Unsupported-claim rejection: a ``FACT`` claim must draw from at least one
   direct-evidence source type (never solely ``MODEL_INFERENCE``/``MODEL_EXAMPLE``).
2. Contradiction preservation: a contrast record must keep both sides; a
   ``RESOLVED_BY_EVIDENCE`` resolution must cite an explicit evidence basis.
"""

from __future__ import annotations

from .contracts import (
    ContradictionRecord,
    DIRECT_SOURCE_TYPES,
    ClaimType,
    ResolutionStatus,
    RoleClaim,
)
from .errors import CrpValidationError, UnsupportedClaimError


def reject_unsupported_claim(claim: RoleClaim, *, resolve_evidence=None) -> RoleClaim:
    """Reject a claim whose evidence chain cannot legitimately support it.

    ``resolve_evidence`` is an optional callable ``(evidence_id) ->
    SourceEvidence`` (or ``None``) enabling, in later slices, resolution of each
    ``source_evidence_ids`` back to concrete evidence. In S0 it is unused and
    may be ``None``: the legitimacy rule is evaluated against the claim's
    already-populated ``source_type_summary`` (inherited/aggregated from
    ``source_evidence_ids`` by the producing role).

    Returns ``claim`` unchanged on success; raises ``UnsupportedClaimError`` on
    failure (fail-closed, never silent downgrade).
    """
    if not isinstance(claim, RoleClaim):
        raise CrpValidationError("claim must be a RoleClaim instance")

    if claim.claim_type == ClaimType.UNKNOWN:
        # An UNKNOWN claim documents an evidence gap, not an assertion; it is
        # not an "unsupported assertion" (CRP_MVP_CONTRACTS_v1.md §B).
        return claim

    # FACT claims require direct evidence. For non-FACT claims the invariant is
    # weaker (a non-empty evidence chain is still required, already enforced at
    # construction), so only the FACT direct-evidence rule is load-bearing here.
    if claim.claim_type == ClaimType.FACT:
        if not any(t in DIRECT_SOURCE_TYPES for t in claim.source_type_summary):
            raise UnsupportedClaimError(
                f"claim {claim.claim_id!r} is claim_type=FACT but its "
                "source_type_summary contains no direct-evidence source type "
                f"(got {[t.value for t in claim.source_type_summary]}); "
                "a FACT claim must draw from OWNER_DIRECT/DIRECT_QUOTE/"
                "OBSERVATION/SELF_REPORT/THIRD_PARTY_REPORT/SCENARIO_EVIDENCE, "
                "never solely MODEL_INFERENCE/MODEL_EXAMPLE"
            )
    return claim


def check_contradiction_integrity(record: ContradictionRecord) -> ContradictionRecord:
    """Validate a ContradictionRecord's preservation invariants.

    - Both conflicting sides remain linked (``claim_ids`` length >= 2, enforced
      at construction -- re-verified defensively here).
    - ``preferred_for_promotion``, when set, never removes the losing side.
    - ``RESOLVED_BY_EVIDENCE`` must cite an explicit ``resolution_basis``.

    Returns ``record`` unchanged on success; raises ``CrpValidationError`` on
    violation (fail-closed, no silent collapse).
    """
    if not isinstance(record, ContradictionRecord):
        raise CrpValidationError("record must be a ContradictionRecord instance")

    if len(record.claim_ids) < 2:
        raise CrpValidationError(
            f"contradiction {record.contradiction_id!r} must retain both "
            "conflicting claims"
        )

    if record.resolution_status == ResolutionStatus.RESOLVED_BY_EVIDENCE:
        if not record.resolution_basis or not record.resolution_basis.strip():
            raise CrpValidationError(
                f"contradiction {record.contradiction_id!r} is "
                "RESOLVED_BY_EVIDENCE but has no resolution_basis citation"
            )

    return record