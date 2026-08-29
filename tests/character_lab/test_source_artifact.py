#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical accepted-source artifact tests (offline, repo-controlled)."""

from __future__ import annotations

import json
from pathlib import Path

from services.character_lab import build_repo_source_loader
from services.character_runtime import load_accepted_character
from services.crp_authoring import PackageStatus, compute_package_hash
from services.crp_authoring.acceptance_store import load_acceptance_record
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package

_REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_ROOT = _REPO_ROOT / "accepted"
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _load_source_candidate():
    path = ACCEPTANCE_ROOT / "kira" / "source_candidate.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestCanonicalSourceArtifact:
    def test_rehydrates_exactly(self):
        package = rehydrate_candidate_package(_load_source_candidate())
        assert package.subject_id == "kira"

    def test_exact_accepted_package_hash(self):
        package = rehydrate_candidate_package(_load_source_candidate())
        assert compute_package_hash(package) == EXPECTED_HASH

    def test_status_remains_draft(self):
        package = rehydrate_candidate_package(_load_source_candidate())
        assert package.status is PackageStatus.DRAFT

    def test_acceptance_gate_works_with_repo_source(self):
        loader = build_repo_source_loader(acceptance_root=ACCEPTANCE_ROOT)
        accepted = load_accepted_character(
            "kira", acceptance_root=ACCEPTANCE_ROOT, source_loader=loader
        )
        assert accepted.source_candidate_hash == EXPECTED_HASH
        assert compute_package_hash(accepted.package) == EXPECTED_HASH
        assert accepted.package.status is PackageStatus.DRAFT

    def test_acceptance_record_unchanged(self):
        record = load_acceptance_record(ACCEPTANCE_ROOT, "kira")
        assert record.decision is PackageStatus.HUMAN_APPROVED
        assert record.package_hash == EXPECTED_HASH
        assert record.subject_id == "kira"
        assert record.package_version == 0
