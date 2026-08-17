#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S0 -- deterministic validation tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ClaimType,
    CrpValidationError,
    ResolutionStatus,
    SourceType,
    UnsupportedClaimError,
)
from services.crp_authoring.validation import (
    check_contradiction_integrity,
    reject_unsupported_claim,
)

from tests.crp_authoring.conftest import make_claim, make_contradiction


class TestRejectUnsupportedClaim:
    def test_fact_with_direct_evidence_accepted(self) -> None:
        claim = make_claim(claim_type=ClaimType.FACT, source_type_summary=(SourceType.OWNER_DIRECT,))
        assert reject_unsupported_claim(claim) is claim

    def test_fact_with_only_inference_rejected(self) -> None:
        claim = make_claim(claim_type=ClaimType.FACT, source_type_summary=(SourceType.MODEL_INFERENCE,))
        with pytest.raises(UnsupportedClaimError):
            reject_unsupported_claim(claim)

    def test_fact_with_mixed_inference_and_example_rejected(self) -> None:
        claim = make_claim(
            claim_type=ClaimType.FACT,
            source_type_summary=(SourceType.MODEL_INFERENCE, SourceType.MODEL_EXAMPLE),
        )
        with pytest.raises(UnsupportedClaimError):
            reject_unsupported_claim(claim)

    def test_inference_claim_type_with_inference_source_ok(self) -> None:
        # Non-FACT claim with inference source is legitimate (it IS an inference).
        claim = make_claim(
            claim_type=ClaimType.INFERENCE,
            source_type_summary=(SourceType.MODEL_INFERENCE,),
        )
        assert reject_unsupported_claim(claim) is claim

    def test_unknown_claim_type_bypasses_fact_rule(self) -> None:
        claim = make_claim(claim_type=ClaimType.UNKNOWN, source_type_summary=(SourceType.MODEL_INFERENCE,))
        assert reject_unsupported_claim(claim) is claim

    def test_non_roleclaim_rejected(self) -> None:
        with pytest.raises(CrpValidationError):
            reject_unsupported_claim("not-a-claim")  # type: ignore[arg-type]


class TestCheckContradictionIntegrity:
    def test_valid_open_record_accepted(self) -> None:
        rec = make_contradiction(resolution_status=ResolutionStatus.OPEN)
        assert check_contradiction_integrity(rec) is rec

    def test_non_record_rejected(self) -> None:
        with pytest.raises(CrpValidationError):
            check_contradiction_integrity("not-a-record")  # type: ignore[arg-type]

    def test_resolved_by_evidence_requires_basis(self) -> None:
        rec = make_contradiction(
            resolution_status=ResolutionStatus.RESOLVED_BY_EVIDENCE,
            resolution_basis=None,
        )
        with pytest.raises(CrpValidationError):
            check_contradiction_integrity(rec)

    def test_resolved_by_evidence_with_basis_accepted(self) -> None:
        rec = make_contradiction(
            resolution_status=ResolutionStatus.RESOLVED_BY_EVIDENCE,
            resolution_basis="evidence se-003 confirms source A",
        )
        assert check_contradiction_integrity(rec) is rec

    def test_preserves_losing_side(self) -> None:
        # preferred_for_promotion never removes the other side.
        rec = make_contradiction(
            claim_ids=("claim-001", "claim-002"),
            preferred_for_promotion="claim-001",
        )
        assert check_contradiction_integrity(rec) is rec
        assert set(rec.claim_ids) == {"claim-001", "claim-002"}