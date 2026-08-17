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