#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S0 -- contract immutability and vocabulary tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ClaimStatus,
    ClaimType,
    Confidence,
    ContradictionRecord,
    CrpValidationError,
    ResolutionStatus,
    RoleClaim,
    Severity,
    SourceEvidence,
    SourceType,
)

from tests.crp_authoring.conftest import make_source, make_claim, make_contradiction


class TestSourceEvidence:
    def test_immutable_frozen(self) -> None:
        ev = make_source()
        with pytest.raises(Exception):
            ev.content_hash = "mutated"  # type: ignore[misc]

    def test_requires_provenance_and_hash(self) -> None:
        with pytest.raises(Exception):
            make_source(provenance="")
        with pytest.raises(Exception):
            make_source(content_hash="")

    def test_requires_source_type_and_snapshot_id(self) -> None:
        with pytest.raises(Exception):
            make_source(source_type="not-an-enum")  # type: ignore[arg-type]
        with pytest.raises(Exception):
            make_source(evidence_snapshot_id="")

    def test_source_type_is_provenance_not_confidence(self) -> None:
        # A single source carries both a source_type and an independent
        # optional confidence -- but S0 records them separately; the axes are
        # never collapsed into one field.
        ev = make_source(source_type=SourceType.PAC_EXPORTED, confidence=Confidence.UNKNOWN)
        assert ev.source_type is SourceType.PAC_EXPORTED
        assert ev.confidence is Confidence.UNKNOWN

    def test_pac_and_sandbox_source_types_valid(self) -> None:
        assert make_source(source_type=SourceType.PAC_EXPORTED).source_type is SourceType.PAC_EXPORTED
        assert make_source(source_type=SourceType.SANDBOX_SNAPSHOT).source_type is SourceType.SANDBOX_SNAPSHOT


class TestRoleClaim:
    def test_immutable_frozen(self) -> None:
        claim = make_claim()
        with pytest.raises(Exception):
            claim.confidence = Confidence.POSSIBLE  # type: ignore[misc]

    def test_requires_nonempty_source_evidence(self) -> None:
        with pytest.raises(Exception):
            make_claim(source_evidence_ids=())

    def test_confidence_enum_only_no_numeric(self) -> None:
        with pytest.raises(Exception):
            make_claim(confidence=0.75)  # type: ignore[arg-type]
        with pytest.raises(Exception):
            make_claim(confidence="HIGH")

    def test_role_id_typed_and_required(self) -> None:
        with pytest.raises(Exception):
            make_claim(role_id="")

    def test_source_type_confidence_independent(self) -> None:
        # OWNER_DIRECT does NOT imply KNOWN; and lower-priority inference is
        # recorded distinctly. A claim may pair OWNER_DIRECT with CONTRADICTORY
        # confidence -- proving independence, not just documenting it.
        claim = make_claim(
            source_type_summary=(SourceType.OWNER_DIRECT,),
            confidence=Confidence.CONTRADICTORY,
        )
        assert claim.confidence is Confidence.CONTRADICTORY
        assert SourceType.OWNER_DIRECT in claim.source_type_summary


class TestContradictionRecord:
    def test_requires_at_least_two_claims(self) -> None:
        with pytest.raises(Exception):
            make_contradiction(claim_ids=("claim-001",))

    def test_preserves_both_claims(self) -> None:
        rec = make_contradiction(
            claim_ids=("claim-001", "claim-002"),
            preferred_for_promotion="claim-001",
        )
        assert set(rec.claim_ids) == {"claim-001", "claim-002"}

    def test_preferred_for_promotion_must_be_member(self) -> None:
        with pytest.raises(Exception):
            make_contradiction(
                claim_ids=("claim-001", "claim-002"),
                preferred_for_promotion="claim-999",
            )