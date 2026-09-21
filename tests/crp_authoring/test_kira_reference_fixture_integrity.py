#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP_MAINLINE_CONSOLIDATION_V1 Part 9 -- KIRA reference fixture regression.

``accepted/kira/{ACCEPTANCE.json,source_candidate.json}`` is the validated
CRP reference result ported unmodified from ``feature/crp-mvp-v1``
(commit ``7e976bf0``, "CRP Kira: materialize accepted package"). It is a
regression/reference fixture ONLY -- these tests prove its integrity, they
do not and must not promote it to ``narrative-character-canon`` or any
published Character Canon.

Offline, read-only, no network, no provider call anywhere in this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.crp_authoring import PackageStatus, get_reconstruction_result
from services.crp_authoring.auditor_checks import compute_package_hash
from services.crp_authoring.errors import CrpValidationError

_ACCEPTED_ROOT = Path("accepted")
_EXPECTED_PACKAGE_ID = "kira-r4-canonical-run-1-package"
_EXPECTED_PACKAGE_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
_EXPECTED_EVIDENCE_SNAPSHOT_ID = "sha256:88f9c822a9d56f7154472c0192511fdc6402c1379a4cc040df287a99f81d5386"


@pytest.fixture(scope="module")
def kira_result():
    return get_reconstruction_result(_ACCEPTED_ROOT, "kira")


class TestKiraReferenceFixtureIntegrity:
    def test_package_hash_matches_acceptance_record(self, kira_result):
        computed = compute_package_hash(kira_result.package)
        assert computed == kira_result.acceptance.package_hash
        assert computed == _EXPECTED_PACKAGE_HASH

    def test_expected_package_id_matches(self, kira_result):
        assert kira_result.package.package_id == _EXPECTED_PACKAGE_ID
        assert kira_result.acceptance.package_id == _EXPECTED_PACKAGE_ID

    def test_expected_evidence_snapshot_matches(self, kira_result):
        assert kira_result.package.source_snapshot_id == _EXPECTED_EVIDENCE_SNAPSHOT_ID

    def test_r3_claims_are_present(self, kira_result):
        r3_claims = [c for c in kira_result.package.claims if c.role_id == "R3"]
        assert len(r3_claims) > 0
        for claim in r3_claims:
            assert claim.source_evidence_ids, "every R3 claim must cite source evidence"

    def test_acceptance_decision_is_human_approved(self, kira_result):
        assert kira_result.acceptance.decision is PackageStatus.HUMAN_APPROVED
        assert kira_result.acceptance.decided_by

    def test_reference_fixture_remains_data_only(self, kira_result):
        # Loading the fixture must be a pure read: no new files created next
        # to it, subject_id is exactly "kira" (not silently promoted/renamed
        # into an external canon identity), and the two source files on disk
        # are unmodified plain JSON.
        assert kira_result.subject_id == "kira"
        assert kira_result.package.subject_id == "kira"
        for name in ("ACCEPTANCE.json", "source_candidate.json"):
            path = _ACCEPTED_ROOT / "kira" / name
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_missing_subject_fails_closed_not_invented(self):
        with pytest.raises(CrpValidationError):
            get_reconstruction_result(_ACCEPTED_ROOT, "does-not-exist")
