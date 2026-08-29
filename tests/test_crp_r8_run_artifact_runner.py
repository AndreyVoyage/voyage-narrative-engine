#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8 run-artifact harness tests (offline, character-agnostic, no provider)."""

from __future__ import annotations

import json
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
for _p in (_PROJECT_ROOT, _TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crp_r8_run_artifact_runner as runner  # noqa: E402

from crp_kira_r4_runner import _to_jsonable  # noqa: E402

from services.crp_authoring import (  # noqa: E402
    ClaimType,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.dataset_freeze import AuthoringProjection, load_a_projection  # noqa: E402
from services.crp_authoring.errors import CrpValidationError  # noqa: E402

from tests.crp_authoring.conftest import (  # noqa: E402
    make_claim,
    make_package,
    make_payload_map,
    make_source,
    utc_now,
)

SUBJECT = "char-subject-1"
SNAPSHOT = "snapshot-1"
EVIDENCE_ID = "se-001"


def _minimal_package():
    fact = make_claim(
        claim_id="claim-001", claim_type=ClaimType.FACT,
        target_module_or_layer="psychology.P0",
    )
    return make_package(
        package_id="pkg-r8-artifact-001",
        subject_id=SUBJECT,
        claims=(fact,),
        psychology_candidate={"P0": (fact,)},
        provenance_manifest={"psychology.P0": ("claim-001",)},
        created_at=utc_now(),
        status=PackageStatus.DRAFT,
    )


def _projection(snapshot_id: str = SNAPSHOT):
    evidence = (make_source(source_id=EVIDENCE_ID, subject_id=SUBJECT,
                            evidence_snapshot_id=snapshot_id),)
    return AuthoringProjection(
        subject_id=SUBJECT,
        evidence_snapshot_id=snapshot_id,
        evidence=evidence,
        payloads=make_payload_map(EVIDENCE_ID),
    )


def _artifact_dict(package) -> dict:
    return {
        "artifact_type": "CRP_KIRA_R4_LIVE_RECONSTRUCTION_RESULT",
        "schema_version": "1",
        "status": "RECONSTRUCTION_COMPLETE_PRE_ACCEPTANCE",
        "run_metadata": {"subject_id": SUBJECT, "evidence_snapshot_id": SNAPSHOT},
        "candidate_package": _to_jsonable(package),
        "candidate_package_hash": compute_package_hash(package),
    }


def _write_artifact(tmp_path, package) -> str:
    path = tmp_path / "run.stdout.json"
    path.write_text(json.dumps(_artifact_dict(package), ensure_ascii=False), encoding="utf-8")
    return str(path)


class TestRunnerArtifact:
    def test_t11_uses_persisted_candidate_not_smoke_package(self, tmp_path):
        package = _minimal_package()
        artifact = _artifact_dict(package)
        rehydrated = runner.rehydrate_candidate_from_artifact(artifact)
        # Distinct from the synthetic smoke package identity (pkg-001 / c1).
        assert rehydrated.package_id == "pkg-r8-artifact-001"
        assert rehydrated.package_id != "pkg-001"
        assert rehydrated.claims[0].claim_id == "claim-001"

    def test_t12_rejects_evidence_snapshot_mismatch(self, tmp_path):
        package = _minimal_package()
        path = _write_artifact(tmp_path, package)
        mismatched = _projection(snapshot_id="snapshot-other")
        with pytest.raises(CrpValidationError, match="evidence snapshot mismatch"):
            runner.run_r8_offline_preflight(path, mismatched)

    def test_canonical_a_loader_points_at_kira_freeze(self):
        projection = load_a_projection(runner.FIXTURE_ROOT, runner.MANIFEST_REL)
        assert projection.subject_id == "kira"
        assert projection.evidence_snapshot_id == (
            "sha256:88f9c822a9d56f7154472c0192511fdc6402c1379a4cc040df287a99f81d5386"
        )


class TestOfflinePreflight:
    def _preflight(self, tmp_path, package=None):
        path = _write_artifact(tmp_path, package or _minimal_package())
        return runner.run_r8_offline_preflight(path, _projection())

    def test_t13_reaches_provider_boundary_with_zero_calls(self, tmp_path):
        result = self._preflight(tmp_path)
        assert result.provider_boundary_reached is True
        assert result.r8_provider_calls == 0
        assert result.preflight_result == "PREFLIGHT_OK_AT_R8_PROVIDER_BOUNDARY"

    def test_t14_active_r8_version_is_v2(self, tmp_path):
        assert runner.R8_ROLE_VERSION == "v2"
        result = self._preflight(tmp_path)
        assert result.active_r8_version == "v2"

    def test_t15_r1_r4_never_invoked(self, tmp_path):
        result = self._preflight(tmp_path)
        assert result.r1_provider_calls == 0
        assert result.r2_provider_calls == 0
        assert result.r3_provider_calls == 0
        assert result.r4_provider_calls == 0
        # The harness carries no reconstruction entrypoint of its own.
        assert not hasattr(runner, "run_reconstruction")
        assert not hasattr(runner, "execute_role_task")

    def test_t16_offline_never_touches_provider_even_with_credential(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-secret-value")

        def _boom(*args, **kwargs):
            raise AssertionError("provider transport must not be touched in offline mode")

        monkeypatch.setattr("llm_provider.complete", _boom)
        monkeypatch.setattr(runner, "build_live_provider_callable", lambda: _boom)

        result = self._preflight(tmp_path)
        assert result.r8_provider_calls == 0
        assert result.provider_boundary_reached is True
