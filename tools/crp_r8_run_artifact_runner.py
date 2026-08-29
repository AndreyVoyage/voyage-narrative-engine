#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP R8-only run-artifact harness (OFFLINE preflight now; future live path).

Loads an already-persisted CRP RUN stdout JSON artifact, rehydrates ONLY its
``candidate_package`` back into a typed ``CandidateCharacterPackage`` via the
canonical ``candidate_rehydration`` module, re-establishes the reconstruction-
visible Partition A evidence through the canonical ``load_a_projection`` path,
and re-verifies the Candidate/evidence binding -- all before any provider
boundary.

This harness NEVER runs R1/R2/R3/R4 and NEVER performs reconstruction. Its
offline preflight mode performs every deterministic/pre-provider step (artifact
parse -> strict rehydration -> typed/hash verification -> A-evidence load ->
binding verification -> deterministic audit -> R8 message rendering) and then
stops exactly at the single R8 provider completion. No provider is constructed
or invoked in offline mode.

The future ``--live`` path reuses the existing canonical R8 provider
configuration (``crp_kira_r4_runner.build_live_provider_callable``) and the
existing ``run_r8_analysis`` entrypoint, but it is NOT executed by this task.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

# Tool bootstrap: resolve the repo root (services.crp_authoring) and the tools
# directory (crp_provider_adapter / llm_provider / sibling runner) regardless of
# how this module is imported (mirrors tools/crp_r8_smoke_runner.py).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parents[0]
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.crp_authoring.auditor_checks import (  # noqa: E402
    AuditPolicy,
    compute_package_hash,
    run_deterministic_audit,
)
from services.crp_authoring.candidate_package import CandidateCharacterPackage  # noqa: E402
from services.crp_authoring.candidate_rehydration import (  # noqa: E402
    rehydrate_candidate_package,
)
from services.crp_authoring.dataset_freeze import (  # noqa: E402
    AuthoringProjection,
    load_a_projection,
)
from services.crp_authoring.errors import CrpValidationError  # noqa: E402
from services.crp_authoring.r8_llm_judgment import (  # noqa: E402
    R8_ROLE_ID,
    R8_ROLE_VERSION,
    render_r8_messages,
    run_r8_analysis,
)
from services.crp_authoring.reconstruction_audit import AuditVerdict  # noqa: E402
from crp_kira_r4_runner import build_live_provider_callable  # noqa: E402

# Canonical Kira A-only dataset freeze (the only reconstruction-visible
# partition this harness is permitted to load).
FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "crp_authoring" / "kira_dataset_freeze" / "v1"
MANIFEST_REL = "KIRA_DATASET_FREEZE.manifest.json"

# Required top-level / metadata fields this harness reads from a RUN artifact.
_ARTIFACT_REQUIRED_KEYS = frozenset({
    "candidate_package",
    "candidate_package_hash",
    "run_metadata",
})
_RUN_METADATA_REQUIRED_KEYS = frozenset({"subject_id", "evidence_snapshot_id"})

@dataclass(frozen=True)
class R8PreflightResult:
    """Deterministic offline-preflight outcome (never touches a provider)."""

    source: str
    subject_id: str
    candidate_hash: str
    candidate_hash_matches: bool
    evidence_snapshot_id: str
    evidence_snapshot_matches: bool
    candidate_type: str
    claim_count: int
    contradiction_count: int
    unknown_count: int
    active_r8_version: str
    r1_provider_calls: int
    r2_provider_calls: int
    r3_provider_calls: int
    r4_provider_calls: int
    r8_provider_calls: int
    provider_boundary_reached: bool
    preflight_result: str


@dataclass(frozen=True)
class R8LiveResult:
    """Future single-shot R8-only provider completion outcome (NOT used now)."""

    subject_id: str
    candidate_hash: str
    active_r8_version: str
    provider_attempts: int
    audit_verdict: str
    message: str


def load_run_artifact(path: Path) -> dict:
    """Parse a persisted RUN stdout JSON artifact and validate the fields this
    harness requires (candidate_package + hash + run metadata)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CrpValidationError(f"run artifact is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CrpValidationError("run artifact must be a JSON object")
    missing = _ARTIFACT_REQUIRED_KEYS - set(data.keys())
    if missing:
        raise CrpValidationError(
            f"run artifact is missing required field(s): {sorted(missing)}"
        )
    metadata = data["run_metadata"]
    if not isinstance(metadata, dict):
        raise CrpValidationError("run_metadata must be an object")
    meta_missing = _RUN_METADATA_REQUIRED_KEYS - set(metadata.keys())
    if meta_missing:
        raise CrpValidationError(
            f"run_metadata is missing required field(s): {sorted(meta_missing)}"
        )
    if not isinstance(data["candidate_package_hash"], str):
        raise CrpValidationError("candidate_package_hash must be a string")
    return data


def rehydrate_candidate_from_artifact(artifact: dict) -> CandidateCharacterPackage:
    """Strictly rehydrate the persisted Candidate and verify its canonical hash.

    Returns a real ``CandidateCharacterPackage``; raises if the persisted data is
    not faithfully rehydratable or if ``compute_package_hash`` no longer matches
    the persisted ``candidate_package_hash``.
    """
    candidate = rehydrate_candidate_package(artifact["candidate_package"])
    if not isinstance(candidate, CandidateCharacterPackage):
        raise CrpValidationError("rehydrated candidate is not a CandidateCharacterPackage")
    persisted_hash = artifact["candidate_package_hash"]
    recomputed = compute_package_hash(candidate)
    if recomputed != persisted_hash:
        raise CrpValidationError(
            f"candidate package hash mismatch: recomputed {recomputed!r} "
            f"!= persisted {persisted_hash!r}"
        )
    return candidate


def _verify_evidence_binding(
    candidate: CandidateCharacterPackage,
    artifact: dict,
    projection: AuthoringProjection,
) -> None:
    """Fail-closed Candidate/evidence binding before any provider boundary."""
    metadata = artifact["run_metadata"]
    subject_id = metadata["subject_id"]
    evidence_snapshot_id = metadata["evidence_snapshot_id"]
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise CrpValidationError("run_metadata.subject_id must be a non-empty string")
    if not isinstance(evidence_snapshot_id, str) or not evidence_snapshot_id.strip():
        raise CrpValidationError("run_metadata.evidence_snapshot_id must be a non-empty string")

    if projection.evidence_snapshot_id != evidence_snapshot_id:
        raise CrpValidationError(
            f"evidence snapshot mismatch: artifact {evidence_snapshot_id!r} "
            f"!= A-only projection {projection.evidence_snapshot_id!r}"
        )
    if candidate.source_snapshot_id != evidence_snapshot_id:
        raise CrpValidationError(
            f"candidate.source_snapshot_id {candidate.source_snapshot_id!r} "
            f"!= artifact evidence snapshot {evidence_snapshot_id!r}"
        )
    if candidate.subject_id != subject_id:
        raise CrpValidationError(
            f"candidate.subject_id {candidate.subject_id!r} != artifact subject {subject_id!r}"
        )
    if projection.subject_id != subject_id:
        raise CrpValidationError(
            f"A-only projection subject {projection.subject_id!r} != artifact subject {subject_id!r}"
        )


def run_r8_offline_preflight(
    artifact_path: Path,
    projection: AuthoringProjection,
    *,
    forbidden_refs: Tuple[str, ...] = (),
) -> R8PreflightResult:
    """Perform every deterministic/pre-provider R8 step WITHOUT a provider.

    Replicates exactly the pre-provider portion of ``run_r8_analysis`` (strict
    rehydration -> binding -> deterministic audit -> message rendering) and then
    stops at the single R8 provider completion. ``provider_boundary_reached`` is
    True only when the deterministic audit is not BLOCKED and the R8 input
    messages were successfully constructed; the provider is never invoked.
    """
    artifact = load_run_artifact(artifact_path)
    candidate = rehydrate_candidate_from_artifact(artifact)
    _verify_evidence_binding(candidate, artifact, projection)

    if R8_ROLE_VERSION != "v2":
        raise CrpValidationError(f"active dedicated R8 version is {R8_ROLE_VERSION!r}, expected v2")

    # Exact same deterministic audit policy as run_r8_analysis uses (no provider).
    deterministic_audit = run_deterministic_audit(
        candidate, projection.evidence, AuditPolicy(forbidden_refs=tuple(forbidden_refs)),
    )
    provider_boundary_reached = deterministic_audit.verdict is not AuditVerdict.BLOCKED
    if provider_boundary_reached:
        # Construct the exact R8 input messages; the next operation would be the
        # single provider completion. No provider is called here.
        render_r8_messages(candidate, projection.evidence, deterministic_audit, projection.payloads)

    metadata = artifact["run_metadata"]
    return R8PreflightResult(
        source=str(artifact_path),
        subject_id=metadata["subject_id"],
        candidate_hash=artifact["candidate_package_hash"],
        candidate_hash_matches=True,
        evidence_snapshot_id=metadata["evidence_snapshot_id"],
        evidence_snapshot_matches=True,
        candidate_type=type(candidate).__name__,
        claim_count=len(candidate.claims),
        contradiction_count=len(candidate.contradictions),
        unknown_count=len(candidate.unknowns),
        active_r8_version=R8_ROLE_VERSION,
        r1_provider_calls=0,
        r2_provider_calls=0,
        r3_provider_calls=0,
        r4_provider_calls=0,
        r8_provider_calls=0,
        provider_boundary_reached=provider_boundary_reached,
        preflight_result=(
            "PREFLIGHT_OK_AT_R8_PROVIDER_BOUNDARY"
            if provider_boundary_reached
            else "PREFLIGHT_DETERMINISTIC_BLOCK_BEFORE_PROVIDER"
        ),
    )


def run_r8_offline_preflight_kira(
    artifact_path: Path,
    *,
    forbidden_refs: Tuple[str, ...] = (),
) -> R8PreflightResult:
    """Canonical Kira A-only offline preflight (loads the frozen A projection)."""
    projection = load_a_projection(FIXTURE_ROOT, MANIFEST_REL)
    return run_r8_offline_preflight(
        artifact_path, projection, forbidden_refs=forbidden_refs,
    )


class _OneShotGuard:
    """Wrap a provider callable so at most one invocation is possible.

    Mirrors the existing R8 smoke runner guard: a second invocation fails closed
    locally (never reaches the underlying provider). ``attempts`` is observable.
    """

    def __init__(self, provider_callable: Callable[[list], str]) -> None:
        self.provider_callable = provider_callable
        self.attempts = 0

    def __call__(self, messages: list) -> str:
        if self.attempts >= 1:
            raise CrpValidationError(
                "one-shot R8 provider guard: a second provider invocation is forbidden"
            )
        self.attempts += 1
        return self.provider_callable(messages)


def run_r8_live_artifact(
    artifact_path: Path,
    projection: AuthoringProjection,
    *,
    forbidden_refs: Tuple[str, ...] = (),
) -> R8LiveResult:
    """Future single-shot R8-only provider completion (NOT executed by this task).

    Reuses the existing canonical R8 provider configuration via
    ``crp_kira_r4_runner.build_live_provider_callable`` and the existing
    ``run_r8_analysis`` entrypoint. This performs a REAL provider call and must
    only ever be invoked under explicit, separately authorized live execution.
    """
    artifact = load_run_artifact(artifact_path)
    candidate = rehydrate_candidate_from_artifact(artifact)
    _verify_evidence_binding(candidate, artifact, projection)

    provider_callable = build_live_provider_callable()
    guard = _OneShotGuard(provider_callable)
    audit = run_r8_analysis(
        candidate,
        projection.evidence,
        guard,
        forbidden_refs=tuple(forbidden_refs),
        evidence_payloads=projection.payloads,
    )
    return R8LiveResult(
        subject_id=artifact["run_metadata"]["subject_id"],
        candidate_hash=artifact["candidate_package_hash"],
        active_r8_version=R8_ROLE_VERSION,
        provider_attempts=guard.attempts,
        audit_verdict=audit.verdict.value,
        message="R8-only live completion finished",
    )


def _preflight_payload(result: R8PreflightResult) -> dict:
    return {
        "status": result.preflight_result,
        "source": result.source,
        "subject_id": result.subject_id,
        "candidate_hash": result.candidate_hash,
        "candidate_hash_matches": result.candidate_hash_matches,
        "evidence_snapshot_id": result.evidence_snapshot_id,
        "evidence_snapshot_matches": result.evidence_snapshot_matches,
        "candidate_type": result.candidate_type,
        "claim_count": result.claim_count,
        "contradiction_count": result.contradiction_count,
        "unknown_count": result.unknown_count,
        "active_r8_version": result.active_r8_version,
        "r1_provider_calls": result.r1_provider_calls,
        "r2_provider_calls": result.r2_provider_calls,
        "r3_provider_calls": result.r3_provider_calls,
        "r4_provider_calls": result.r4_provider_calls,
        "r8_provider_calls": result.r8_provider_calls,
        "provider_boundary_reached": result.provider_boundary_reached,
        "preflight_result": result.preflight_result,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crp_r8_run_artifact_runner",
        description=(
            "R8-only run-artifact harness. Offline preflight by default; "
            "requires an explicit --live for the future provider completion."
        ),
    )
    parser.add_argument("artifact", type=Path, help="Path to a persisted RUN stdout JSON artifact.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--offline-preflight",
        action="store_true",
        help="Run the offline preflight (no provider call).",
    )
    group.add_argument(
        "--live",
        action="store_true",
        help="Execute the future R8-only provider completion (requires authorization).",
    )
    args = parser.parse_args(argv)

    if args.live:
        # Structural future path; explicitly NOT authorized in this task.
        print(
            "Refusing to run --live: R8-only live execution is not authorized in "
            "this task. Use --offline-preflight.",
            file=sys.stderr,
        )
        return 1

    try:
        result = run_r8_offline_preflight_kira(args.artifact)
    except CrpValidationError as exc:
        print(f"OFFLINE PREFLIGHT FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(_preflight_payload(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
