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

    def test_intimacy_claim_compiles_into_intimacy_candidate(self) -> None:
        # ERC-1 (GAP-B): intimacy.* claims now compile into
        # package.intimacy_candidate, grouped by dimension.
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="intimacy.boundaries")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.intimacy_candidate["boundaries"] == (c,)

    def test_intimacy_provenance_manifest_includes_target(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="c1", target_module_or_layer="intimacy.preferences")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert "intimacy.preferences" in pkg.provenance_manifest
        assert "c1" in pkg.provenance_manifest["intimacy.preferences"]

    def test_zero_intimacy_claims_package_still_valid(self) -> None:
        # R3 is optional; a package compiled with only psychology/voice claims
        # has intimacy_candidate == {} and is valid.
        ctx = make_compile_context()
        p = make_claim(claim_id="p1", target_module_or_layer="psychology.P2")
        v = make_claim(claim_id="v1", target_module_or_layer="voice.lexicon")
        pkg = compile_candidate_package(ctx, (p, v), ())
        assert pkg.intimacy_candidate == {}
        assert pkg.psychology_candidate["P2"] == (p,)
        assert pkg.voice_candidate["lexicon"] == (v,)


class TestBroadCoreTargetFamilies:
    """Slice 2: five broad-core families compile into dedicated candidate fields."""

    def test_classify_target_identity_biography(self) -> None:
        assert classify_target("identity_biography.name") == ("identity_biography", "name")

    def test_identity_biography_routes_to_own_field(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="ib1", target_module_or_layer="identity_biography.name")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.identity_biography_candidate["name"] == (c,)
        assert pkg.psychology_candidate == {}
        assert pkg.behavior_candidate == {}

    def test_behavior_routes_to_own_field_not_psychology(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="b1", target_module_or_layer="behavior.social")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.behavior_candidate["social"] == (c,)
        assert pkg.psychology_candidate == {}

    def test_relationships_routes_to_own_field(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="r1", target_module_or_layer="relationships.counterpart")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.relationships_candidate["counterpart"] == (c,)

    def test_boundaries_routes_to_own_field_not_intimacy(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="g1", target_module_or_layer="boundaries.general")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.boundaries_candidate["general"] == (c,)
        assert pkg.intimacy_candidate == {}

    def test_seed_memory_routes_to_own_field(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="sm1", target_module_or_layer="seed_memory.event1")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.seed_memory_candidate["event1"] == (c,)

    def test_broad_core_claim_in_provenance_manifest(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="ib1", target_module_or_layer="identity_biography.name")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert "identity_biography.name" in pkg.provenance_manifest
        assert "ib1" in pkg.provenance_manifest["identity_biography.name"]

    def test_unknown_family_still_fail_closed(self) -> None:
        ctx = make_compile_context()
        bad = make_claim(claim_id="c1", target_module_or_layer="unknown_family.xyz")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (bad,), ())

    def test_empty_broad_core_dimension_fail_closed(self) -> None:
        ctx = make_compile_context()
        bad = make_claim(claim_id="c1", target_module_or_layer="behavior.")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (bad,), ())

    def test_near_miss_prefix_fail_closed(self) -> None:
        ctx = make_compile_context()
        bad = make_claim(claim_id="c1", target_module_or_layer="behaviors.social")
        with pytest.raises(CompilerError):
            compile_candidate_package(ctx, (bad,), ())


class TestExistingFamiliesRegression:
    """Slice 2: existing psychology/voice/intimacy routing unchanged."""

    def test_psychology_still_routes(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="p1", target_module_or_layer="psychology.P3")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.psychology_candidate["P3"] == (c,)

    def test_voice_still_routes(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="v1", target_module_or_layer="voice.lexicon")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.voice_candidate["lexicon"] == (c,)

    def test_intimacy_still_routes(self) -> None:
        ctx = make_compile_context()
        c = make_claim(claim_id="i1", target_module_or_layer="intimacy.boundaries")
        pkg = compile_candidate_package(ctx, (c,), ())
        assert pkg.intimacy_candidate["boundaries"] == (c,)


class TestUnknownRouting:
    """Slice 3: UNKNOWN claims route to package.unknowns, never a family bucket."""

    def _unknown(self, claim_id, target):
        return make_claim(
            claim_id=claim_id, claim_type=ClaimType.UNKNOWN,
            target_module_or_layer=target,
            source_evidence_ids=(),
            confidence=Confidence.UNKNOWN,
        )

    def test_unknown_routes_to_package_unknowns(self) -> None:
        ctx = make_compile_context()
        u = self._unknown("u1", "psychology.P2")
        pkg = compile_candidate_package(ctx, (u,), ())
        assert pkg.unknowns == (u,)

    def test_unknown_excluded_from_all_normal_buckets(self) -> None:
        ctx = make_compile_context()
        u = make_claim(claim_id="u1", claim_type=ClaimType.UNKNOWN,
                       target_module_or_layer="identity_biography.birthplace",
                       source_evidence_ids=(), confidence=Confidence.UNKNOWN)
        pkg = compile_candidate_package(ctx, (u,), ())
        assert pkg.unknowns == (u,)
        assert pkg.psychology_candidate == {}
        assert pkg.voice_candidate == {}
        assert pkg.intimacy_candidate == {}
        assert pkg.identity_biography_candidate == {}
        assert pkg.behavior_candidate == {}
        assert pkg.relationships_candidate == {}
        assert pkg.boundaries_candidate == {}
        assert pkg.seed_memory_candidate == {}

    def test_free_form_unknown_target_not_fail_closed(self) -> None:
        # An UNKNOWN claim's target identifies WHAT is unknown; it is not a
        # candidate family prefix and must not trigger CompilerError.
        ctx = make_compile_context()
        u = self._unknown("u1", "free.form.gap.target")
        pkg = compile_candidate_package(ctx, (u,), ())
        assert pkg.unknowns == (u,)

    def test_distinct_unknowns_coexist(self) -> None:
        ctx = make_compile_context()
        u1 = self._unknown("u1", "psychology.P2")
        u2 = self._unknown("u2", "behavior.conflict_style")
        u3 = self._unknown("u3", "identity_biography.birthplace")
        pkg = compile_candidate_package(ctx, (u1, u2, u3), ())
        assert pkg.unknowns == (u1, u2, u3)

    def test_mixed_unknown_and_normal_claims(self) -> None:
        ctx = make_compile_context()
        u = self._unknown("u1", "psychology.P2")
        p = make_claim(claim_id="p1", target_module_or_layer="psychology.P3")
        pkg = compile_candidate_package(ctx, (u, p), ())
        assert pkg.unknowns == (u,)
        assert pkg.psychology_candidate["P3"] == (p,)
        assert pkg.psychology_candidate.get("P2") is None
