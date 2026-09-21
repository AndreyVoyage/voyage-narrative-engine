#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S1 -- CandidateCharacterPackage contract tests."""

from __future__ import annotations

import pytest

from services.crp_authoring import PackageStatus
from services.crp_authoring.candidate_package import CandidateCharacterPackage

from tests.crp_authoring.conftest import make_package


class TestCandidateCharacterPackage:
    def test_immutable_frozen(self) -> None:
        pkg = make_package()
        with pytest.raises(Exception):
            pkg.status = PackageStatus.VALIDATED  # type: ignore[misc]

    def test_lifecycle_enum_order_and_values(self) -> None:
        assert [s.value for s in PackageStatus] == [
            "DRAFT", "VALIDATED", "AUDITED", "HUMAN_APPROVED", "REJECTED",
        ]

    def test_requires_all_ratified_required_fields(self) -> None:
        with pytest.raises(Exception):
            CandidateCharacterPackage(
                package_id="",  # empty required field
                subject_id="s",
                package_version=0,
                source_snapshot_id="snap",
                role_result_refs=(),
                claims=(),
                contradictions=(),
                unknowns=(),
                psychology_candidate={},
                voice_candidate={},
                validation_results={},
                audit_result=None,
                provenance_manifest={},
                created_at=None,  # type: ignore[arg-type]
                status=PackageStatus.DRAFT,
            )

    def test_not_canon(self) -> None:
        pkg = make_package()
        # A candidate package has no canon write path, no canon field, and
        # merely being DRAFT/VALIDATED does not imply anything canon-related.
        assert pkg.status in (PackageStatus.DRAFT, PackageStatus.VALIDATED)
        assert not hasattr(pkg, "canon_state")

    def test_role_result_refs_and_audit_result_legitimately_empty(self) -> None:
        pkg = make_package()
        assert pkg.role_result_refs == ()
        assert pkg.audit_result is None


class TestIntimacyCandidate:
    def test_intimacy_candidate_defaults_empty(self) -> None:
        # R3 is optional; a package constructed without intimacy_candidate
        # omits it (backward compatible) and it defaults to {}.
        pkg = make_package()
        assert pkg.intimacy_candidate == {}

    def test_intimacy_candidate_accepts_mapping(self) -> None:
        from tests.crp_authoring.conftest import make_claim
        c = make_claim(claim_id="i1", target_module_or_layer="intimacy.boundaries")
        pkg = make_package(intimacy_candidate={"boundaries": (c,)})
        assert pkg.intimacy_candidate["boundaries"] == (c,)

    def test_intimacy_candidate_immutable(self) -> None:
        pkg = make_package()
        with pytest.raises(Exception):
            pkg.intimacy_candidate["boundaries"] = ()  # type: ignore[index]


class TestBroadCoreCandidateFields:
    """Slice 2: five broad-core destination fields exist with empty defaults."""

    def test_five_broad_core_fields_exist_and_default_empty(self) -> None:
        pkg = make_package()
        assert pkg.identity_biography_candidate == {}
        assert pkg.behavior_candidate == {}
        assert pkg.relationships_candidate == {}
        assert pkg.boundaries_candidate == {}
        assert pkg.seed_memory_candidate == {}

    def test_existing_narrow_construction_still_succeeds(self) -> None:
        # Narrow psychology/voice/intimacy construction remains valid.
        from tests.crp_authoring.conftest import make_claim
        p = make_claim(claim_id="p1", target_module_or_layer="psychology.P2")
        v = make_claim(claim_id="v1", target_module_or_layer="voice.lexicon")
        pkg = make_package(
            psychology_candidate={"P2": (p,)},
            voice_candidate={"lexicon": (v,)},
        )
        assert pkg.psychology_candidate["P2"] == (p,)
        assert pkg.voice_candidate["lexicon"] == (v,)
        assert pkg.identity_biography_candidate == {}

    def test_each_broad_core_field_accepts_claim_mapping(self) -> None:
        from tests.crp_authoring.conftest import make_claim
        c = make_claim(claim_id="b1", target_module_or_layer="behavior.social")
        pkg = make_package(behavior_candidate={"social": (c,)})
        assert pkg.behavior_candidate["social"] == (c,)

    def test_broad_core_fields_immutable(self) -> None:
        pkg = make_package()
        with pytest.raises(Exception):
            pkg.behavior_candidate["social"] = ()  # type: ignore[index]
        with pytest.raises(Exception):
            pkg.seed_memory_candidate["e1"] = ()  # type: ignore[index]
