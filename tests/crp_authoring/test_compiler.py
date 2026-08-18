#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S1 -- R6 deterministic compiler tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import (
    ClaimType,
    CompilerError,
    Confidence,
    PackageStatus,
    SourceType,
    UnsupportedClaimError,
)
from services.crp_authoring.compiler import classify_target, compile_candidate_package

from tests.crp_authoring.conftest import (
    make_claim,
    make_compile_context,
    make_contradiction,
)


class TestCompiler:
    def test_valid_claims_placed_by_prefix(self) -> None:
        ctx = make_compile_context()
        p_claim = make_claim(claim_id="c1", target_module_or_layer="psychology.P2")
        v_claim = make_claim(claim_id="c2", target_module_or_layer="voice.lexicon")
        pkg = compile_candidate_package(ctx, (p_claim, v_claim), ())
        assert pkg.status is PackageStatus.DRAFT
        assert pkg.psychology_candidate["P2"] == (p_claim,)
        assert pkg.voice_candidate["lexicon"] == (v_claim,)

    def test_cannot_invent_claims(self) -> None:
        # The compiler has no text-generation path: every output claim must be
        # one of the input claims, verbatim.
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="psychology.P0",
                       claim="the original text")
        pkg = compile_candidate_package(ctx, (c,), ())
        all_texts = {cl.claim for cl in pkg.claims}
        assert all_texts == {"the original text"}

    def test_unmapped_target_fail_closed(self) -> None:
        ctx = make_compile_context()
        bad = make_claim(claim_id="c1", target_module_or_layer="no_prefix_here")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (bad,), ())

    def test_invalid_psychology_tag_fail_closed(self) -> None:
        ctx = make_compile_context()
        bad = make_claim(claim_id="c1", target_module_or_layer="psychology.P9")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (bad,), ())

    def test_unsupported_fact_claim_rejected(self) -> None:
        ctx = make_compile_context()
        bad_fact = make_claim(
            claim_id="c1", claim_type=ClaimType.FACT,
            source_type_summary=(SourceType.MODEL_INFERENCE,),
        )
        with pytest.raises(UnsupportedClaimError):
            compile_candidate_package(ctx, (bad_fact,), ())

    def test_provenance_manifest_resolves(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="psychology.P3")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert "psychology.P3" in pkg.provenance_manifest
        assert "c1" in pkg.provenance_manifest["psychology.P3"]

    def test_confidence_preserved_unchanged(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="psychology.P1",
                       confidence=Confidence.PROBABLE)
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.claims[0].confidence is Confidence.PROBABLE

    def test_conflicting_claims_both_survive(self) -> None:
        ctx = make_compile_context()
        owner = make_claim(claim_id="owner-fact", target_module_or_layer="psychology.P3",
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           confidence=Confidence.KNOWN, claim="color is blue")
        model = make_claim(claim_id="model-inf", target_module_or_layer="voice.lexicon",
                           claim_type=ClaimType.INFERENCE,
                           source_type_summary=(SourceType.MODEL_INFERENCE,),
                           confidence=Confidence.POSSIBLE, claim="color is green")
        pkg = compile_candidate_package(ctx, (owner, model), ())
        ids = {c.claim_id for c in pkg.claims}
        assert ids == {"owner-fact", "model-inf"}
        # no averaging: confidence values untouched
        confidences = {c.claim_id: c.confidence for c in pkg.claims}
        assert confidences["owner-fact"] is Confidence.KNOWN
        assert confidences["model-inf"] is Confidence.POSSIBLE

    def test_contradiction_record_preserved_verbatim(self) -> None:
        ctx = make_compile_context()
        c1 = make_claim(claim_id="c1", target_module_or_layer="psychology.P3")
        c2 = make_claim(claim_id="c2", target_module_or_layer="psychology.P3")
        record = make_contradiction(contradiction_id="crd-1", claim_ids=("c1", "c2"),
                                    preferred_for_promotion="c1")
        pkg = compile_candidate_package(ctx, (c1, c2), (record,))
        assert pkg.contradictions == (record,)
        assert set(record.claim_ids) == {"c1", "c2"}

    def test_role_result_refs_and_audit_result_empty(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="psychology.P0")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.role_result_refs == ()
        assert pkg.audit_result is None


class TestIntimacyTargetFamily:
    def test_classify_target_intimacy(self) -> None:
        assert classify_target("intimacy.boundaries") == ("intimacy", "boundaries")

    def test_intimacy_placement_not_wired_fail_closed(self) -> None:
        # The R3a slice establishes the "intimacy" target family for future R3
        # claims, but CandidateCharacterPackage has no intimacy bucket yet.
        # R6 must fail closed rather than silently misplace an intimacy claim.
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="intimacy.boundaries")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (c,), ())
