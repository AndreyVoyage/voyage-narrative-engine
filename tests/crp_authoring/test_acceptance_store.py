#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP -- acceptance materialization/persistence tests (offline, focused).

Proves the already-made owner Human ACCEPT decision for the exact RUN_015 KIRA
Candidate is materialized as an immutable ``AcceptanceRecord`` bound to the exact
source candidate hash + subject_id, without re-evaluating quality, without
mutating the DRAFT source, and without introducing Hidden-B content.

No provider, no network, no R1/R2/R3/R4/R8 execution, no Hidden-B read.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from services.crp_authoring import (
    CrpValidationError,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import (
    is_accepted,
    load_acceptance_record,
    materialize_acceptance,
    resolve_accepted_source_hash,
    write_acceptance_record,
)
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package
from services.crp_authoring.lifecycle import AcceptanceRecord

from tests.crp_authoring.conftest import make_package

ACCEPTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
SUBJECT = "kira"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
_RUN015_DEFAULT = Path("C:/DEV/Narrative/LOCAL_STORAGE/crp_r4_live_runs/RUN_015.stdout.json")


def _run015_candidate():
    path = Path(os.environ.get("CRP_RUN_015_STDOUT", str(_RUN015_DEFAULT)))
    if not path.exists():
        pytest.skip("RUN_015.stdout.json not available")
    data = json.loads(path.read_text(encoding="utf-8"))
    return rehydrate_candidate_package(data["candidate_package"])


# ---------------------------------------------------------------------------
# T1 -- the exact RUN_015 Candidate is accepted
# ---------------------------------------------------------------------------

class TestExactRunCandidate:
    def test_run015_candidate_materializes(self):
        candidate = _run015_candidate()
        assert candidate.subject_id == SUBJECT
        assert candidate.status is PackageStatus.DRAFT
        assert compute_package_hash(candidate) == ACCEPTED_HASH

        record = materialize_acceptance(
            candidate,
            expected_subject_id=SUBJECT,
            expected_source_hash=ACCEPTED_HASH,
            accepted_by="owner",
            acceptance_id="kira-accepted-package-001",
        )
        assert isinstance(record, AcceptanceRecord)
        assert record.decision is PackageStatus.HUMAN_APPROVED
        assert record.subject_id == SUBJECT
        assert record.package_hash == ACCEPTED_HASH

# ---------------------------------------------------------------------------
# T2/T3 -- wrong hash and wrong subject fail closed
# ---------------------------------------------------------------------------

class TestFailClosedBinding:
    def test_wrong_candidate_hash_fails_closed(self):
        pkg = make_package(package_id="pkg-x", subject_id=SUBJECT)
        with pytest.raises(CrpValidationError):
            materialize_acceptance(
                pkg,
                expected_subject_id=SUBJECT,
                expected_source_hash="0" * 64,
                accepted_by="owner",
                acceptance_id="acc-x",
            )

    def test_wrong_subject_fails_closed(self):
        pkg = make_package(package_id="pkg-x", subject_id=SUBJECT)
        correct_hash = compute_package_hash(pkg)
        with pytest.raises(CrpValidationError):
            materialize_acceptance(
                pkg,
                expected_subject_id="not-kira",
                expected_source_hash=correct_hash,
                accepted_by="owner",
                acceptance_id="acc-x",
            )


# ---------------------------------------------------------------------------
# T4 -- DRAFT source remains immutable
# ---------------------------------------------------------------------------

class TestDraftSourceImmutability:
    def test_materialize_does_not_mutate_source(self):
        pkg = make_package(package_id="pkg-x", subject_id=SUBJECT)
        before_status = pkg.status
        before_hash = compute_package_hash(pkg)

        materialize_acceptance(
            pkg,
            expected_subject_id=SUBJECT,
            expected_source_hash=before_hash,
            accepted_by="owner",
            acceptance_id="acc-x",
        )

        assert pkg.status is before_status is PackageStatus.DRAFT
        assert compute_package_hash(pkg) == before_hash

    def test_run015_source_stays_draft(self):
        candidate = _run015_candidate()
        assert candidate.status is PackageStatus.DRAFT
        materialize_acceptance(
            candidate,
            expected_subject_id=SUBJECT,
            expected_source_hash=ACCEPTED_HASH,
            accepted_by="owner",
            acceptance_id="kira-accepted-package-001",
        )
        assert candidate.status is PackageStatus.DRAFT
        assert compute_package_hash(candidate) == ACCEPTED_HASH

# ---------------------------------------------------------------------------
# T5 -- accepted package/record points to the exact source hash
# ---------------------------------------------------------------------------

class TestAcceptedRecordBinding:
    def test_committed_artifact_points_to_exact_source_hash(self):
        record = load_acceptance_record(_ACCEPTED_ROOT, SUBJECT)
        assert record.subject_id == SUBJECT
        assert record.package_hash == ACCEPTED_HASH
        assert record.decision is PackageStatus.HUMAN_APPROVED
        assert resolve_accepted_source_hash(_ACCEPTED_ROOT, SUBJECT) == ACCEPTED_HASH

    def test_roundtrip_preserves_binding(self):
        record = load_acceptance_record(_ACCEPTED_ROOT, SUBJECT)
        assert record.package_hash == ACCEPTED_HASH
        assert record.package_id == "kira-r4-canonical-run-1-package"


# ---------------------------------------------------------------------------
# T6 -- no Hidden-B data is introduced
# ---------------------------------------------------------------------------

class TestNoHiddenB:
    def test_artifact_contains_no_hidden_b_content(self):
        artifact = _ACCEPTED_ROOT / SUBJECT / "ACCEPTANCE.json"
        text = artifact.read_text(encoding="utf-8")
        for marker in (
            "B_HIDDEN_EVALUATION",
            "OWNER_REFERENCE_ANSWERS",
            "b-003",
            "b-006",
            "hidden_eval",
            "hidden evaluation",
        ):
            assert marker not in text, f"Hidden-B marker {marker!r} leaked into artifact"

    def test_record_has_only_acceptance_metadata_fields(self):
        record = load_acceptance_record(_ACCEPTED_ROOT, SUBJECT)
        # The record carries identity + hash + decision metadata only, never
        # substantive reconstructed content (no claims/psychology/voice fields).
        for field in ("claims", "psychology_candidate", "voice_candidate"):
            assert not hasattr(record, field)

# ---------------------------------------------------------------------------
# T7 -- repeated acceptance cannot silently produce conflicting state
# ---------------------------------------------------------------------------

class TestRepeatedAcceptance:
    def _record(self, *, package_hash="a" * 64):
        return AcceptanceRecord(
            acceptance_id="acc-1",
            package_id="pkg-1",
            package_version=0,
            subject_id="subj",
            package_hash=package_hash,
            audit_id=None,
            decision=PackageStatus.HUMAN_APPROVED,
            decided_by="owner",
            decided_at="2026-08-29T00:00:00+00:00",
            reason=None,
        )

    def test_same_record_is_idempotent(self, tmp_path):
        record = self._record()
        p1 = write_acceptance_record(record, tmp_path)
        p2 = write_acceptance_record(record, tmp_path)
        assert p1 == p2
        assert p1.read_bytes() == p2.read_bytes()

    def test_conflicting_record_fails_closed(self, tmp_path):
        write_acceptance_record(self._record(package_hash="a" * 64), tmp_path)
        with pytest.raises(CrpValidationError):
            write_acceptance_record(self._record(package_hash="b" * 64), tmp_path)


# ---------------------------------------------------------------------------
# T8 -- accepted-vs-draft distinction (CRP-side; CIS gate is a later task)
# ---------------------------------------------------------------------------

class TestAcceptedVsDraft:
    def test_accepted_subject_distinguished_from_draft(self, tmp_path):
        # No record -> pre-acceptance/DRAFT.
        assert is_accepted(tmp_path, "subj") is False

        write_acceptance_record(
            AcceptanceRecord(
                acceptance_id="acc-1",
                package_id="pkg-1",
                package_version=0,
                subject_id="subj",
                package_hash="a" * 64,
                audit_id=None,
                decision=PackageStatus.HUMAN_APPROVED,
                decided_by="owner",
                decided_at="2026-08-29T00:00:00+00:00",
                reason=None,
            ),
            tmp_path,
        )
        assert is_accepted(tmp_path, "subj") is True

    def test_no_runtime_cis_gate_yet(self):
        # Runtime/CIS integration is the next major task, not a blocker: there is
        # currently no CIS-side loader module. The acceptance store above is the
        # CRP-side resolution surface the future gate will consume.
        cis_candidates = [
            _REPO_ROOT / "services" / "cis",
            _REPO_ROOT / "services" / "runtime",
        ]
        assert all(not p.exists() for p in cis_candidates)
