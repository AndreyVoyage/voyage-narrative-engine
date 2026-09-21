#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP -- persistence/materialization glue for explicit human acceptance.

The acceptance CONTRACT already exists: ``AcceptanceRecord`` (in ``lifecycle.py``)
plus the owner-ratified OD-S9 policy. ``lifecycle.py`` is deliberately
persistence-free and provider-free; this module adds ONLY the missing
persistence/materialization glue so an already-made owner Human ACCEPT decision
can be recorded as an immutable, JSON-persisted ``AcceptanceRecord`` bound to an
exact source candidate hash + subject_id, and resolved back for a downstream
Runtime/CIS handoff.

Boundary (do not relax):

- No quality re-evaluation -- no R1/R2/R3/R4/R8, no provider, no network.
- The source ``CandidateCharacterPackage`` is never mutated: its DRAFT status is
  preserved exactly. Acceptance is recorded as a detached wrapper/record, not as
  a package-status rewrite.
- Hidden-B is never read and never copied; the persisted artifact carries only
  acceptance metadata (identity + hash + decision), never substantive content.
- Package hashing semantics are unchanged: ``compute_package_hash`` remains the
  single public source of truth, and the record's ``package_hash`` is exactly the
  source candidate hash the owner accepted.
- The owner's ``ACCEPT`` maps to ``PackageStatus.HUMAN_APPROVED`` (the canonical
  terminal human-accept state; per the contracts, HUMAN_APPROVED is NOT canon
  promotion).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .auditor_checks import compute_package_hash
from .candidate_package import CandidateCharacterPackage, PackageStatus
from .errors import CrpValidationError
from .lifecycle import AcceptanceRecord

__all__ = [
    "ACCEPTANCE_ARTIFACT_TYPE",
    "ACCEPTANCE_SCHEMA_VERSION",
    "ACCEPTANCE_FILENAME",
    "materialize_acceptance",
    "acceptance_record_to_jsonable",
    "acceptance_record_from_jsonable",
    "acceptance_record_envelope",
    "canonical_acceptance_path",
    "write_acceptance_record",
    "load_acceptance_record",
    "resolve_accepted_source_hash",
    "is_accepted",
]

ACCEPTANCE_ARTIFACT_TYPE = "CRP_ACCEPTANCE_RECORD"
ACCEPTANCE_SCHEMA_VERSION = "1"
ACCEPTANCE_FILENAME = "ACCEPTANCE.json"

_ACCEPTANCE_FIELDS = frozenset({
    "acceptance_id",
    "package_id",
    "package_version",
    "subject_id",
    "package_hash",
    "audit_id",
    "decision",
    "decided_by",
    "decided_at",
    "reason",
    "supersedes",
})


# ---------------------------------------------------------------------------
# Fail-closed helpers
# ---------------------------------------------------------------------------

def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")
    return value


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Materialization (owner decision -> immutable AcceptanceRecord binding)
# ---------------------------------------------------------------------------

def materialize_acceptance(
    candidate: CandidateCharacterPackage,
    *,
    expected_subject_id: str,
    expected_source_hash: str,
    accepted_by: str,
    acceptance_id: str,
    reason: Optional[str] = None,
    accepted_at: Optional[str] = None,
    audit_id: Optional[str] = None,
) -> AcceptanceRecord:
    """Record an already-made owner Human ACCEPT decision for a candidate.

    Produces an immutable ``AcceptanceRecord`` (decision = HUMAN_APPROVED) bound
    to exactly ``expected_source_hash`` + ``expected_subject_id``. The source
    ``candidate`` is never mutated and its status is never changed.

    Fail-closed on:

    - ``candidate`` not a ``CandidateCharacterPackage``;
    - ``compute_package_hash(candidate) != expected_source_hash`` (wrong hash);
    - ``candidate.subject_id != expected_subject_id`` (wrong subject).

    No audit verdict is (re)computed and no quality gate is re-run here: the
    owner decision is already explicit and is the sole authority for this step.
    """
    if not isinstance(candidate, CandidateCharacterPackage):
        raise CrpValidationError("candidate must be a CandidateCharacterPackage")
    _require_non_empty(expected_subject_id, "expected_subject_id")
    _require_non_empty(expected_source_hash, "expected_source_hash")

    source_hash = compute_package_hash(candidate)
    if source_hash != expected_source_hash:
        raise CrpValidationError(
            f"source candidate hash mismatch: computed {source_hash!r} "
            f"!= expected {expected_source_hash!r}"
        )
    if candidate.subject_id != expected_subject_id:
        raise CrpValidationError(
            f"subject mismatch: {candidate.subject_id!r} != {expected_subject_id!r}"
        )

    return AcceptanceRecord(
        acceptance_id=acceptance_id,
        package_id=candidate.package_id,
        package_version=candidate.package_version,
        subject_id=candidate.subject_id,
        package_hash=source_hash,
        audit_id=audit_id,
        decision=PackageStatus.HUMAN_APPROVED,
        decided_by=accepted_by,
        decided_at=accepted_at or _now_iso(),
        reason=reason,
    )

# ---------------------------------------------------------------------------
# JSON transport (strict inverse pair, no silent defaults)
# ---------------------------------------------------------------------------

def acceptance_record_to_jsonable(record: AcceptanceRecord) -> dict:
    """Serialize an ``AcceptanceRecord`` into a JSON-safe dict (no enum/None loss)."""
    if not isinstance(record, AcceptanceRecord):
        raise CrpValidationError("record must be an AcceptanceRecord")
    return {
        "acceptance_id": record.acceptance_id,
        "package_id": record.package_id,
        "package_version": record.package_version,
        "subject_id": record.subject_id,
        "package_hash": record.package_hash,
        "audit_id": record.audit_id,
        "decision": record.decision.value,
        "decided_by": record.decided_by,
        "decided_at": record.decided_at,
        "reason": record.reason,
        "supersedes": record.supersedes,
    }


def acceptance_record_from_jsonable(data: Any) -> AcceptanceRecord:
    """Rehydrate a persisted acceptance record, fail-closed on corruption."""
    if not isinstance(data, dict):
        raise CrpValidationError("acceptance record must be an object")
    actual = set(data.keys())
    missing = _ACCEPTANCE_FIELDS - actual
    if missing:
        raise CrpValidationError(
            f"acceptance record missing field(s): {sorted(missing)}"
        )
    unknown = actual - _ACCEPTANCE_FIELDS
    if unknown:
        raise CrpValidationError(
            f"acceptance record has unknown field(s): {sorted(unknown)}"
        )

    decision_value = data["decision"]
    if not isinstance(decision_value, str):
        raise CrpValidationError("decision must be a string enum value")
    try:
        decision = PackageStatus(decision_value)
    except ValueError as exc:
        raise CrpValidationError(
            f"decision has invalid enum value {decision_value!r}"
        ) from exc

    return AcceptanceRecord(
        acceptance_id=data["acceptance_id"],
        package_id=data["package_id"],
        package_version=data["package_version"],
        subject_id=data["subject_id"],
        package_hash=data["package_hash"],
        audit_id=data["audit_id"],
        decision=decision,
        decided_by=data["decided_by"],
        decided_at=data["decided_at"],
        reason=data["reason"],
        supersedes=data["supersedes"],
    )


def acceptance_record_envelope(record: AcceptanceRecord) -> dict:
    """Wrap a record in the minimal, type-versioned artifact envelope."""
    return {
        "artifact_type": ACCEPTANCE_ARTIFACT_TYPE,
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "acceptance_record": acceptance_record_to_jsonable(record),
    }


def _canonical_bytes(record: AcceptanceRecord) -> bytes:
    payload = acceptance_record_envelope(record)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    return (text + "\n").encode("utf-8")

# ---------------------------------------------------------------------------
# Persistence + resolution (the missing glue)
# ---------------------------------------------------------------------------

def canonical_acceptance_path(root: Path, subject_id: str) -> Path:
    """Return the canonical artifact path for one subject's accepted package."""
    _require_non_empty(subject_id, "subject_id")
    if "/" in subject_id or "\\" in subject_id or subject_id in (".", ".."):
        raise CrpValidationError("subject_id must be a plain identifier")
    return Path(root) / subject_id / ACCEPTANCE_FILENAME


def write_acceptance_record(
    record: AcceptanceRecord,
    root: Path,
    *,
    subject_id: Optional[str] = None,
) -> Path:
    """Persist an acceptance record, idempotent but fail-closed on conflict.

    - Writing the exact same record again is a no-op (returns the existing path).
    - Writing a different record for the same subject fails closed, so repeated
      acceptance can never silently produce conflicting state.
    """
    if not isinstance(record, AcceptanceRecord):
        raise CrpValidationError("record must be an AcceptanceRecord")
    resolved_subject = record.subject_id if subject_id is None else subject_id
    if resolved_subject != record.subject_id:
        raise CrpValidationError(
            f"subject_id {resolved_subject!r} != record.subject_id {record.subject_id!r}"
        )

    target = canonical_acceptance_path(root, resolved_subject)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(record)
    if target.exists():
        existing = target.read_bytes()
        if existing == payload:
            return target
        raise CrpValidationError(
            f"acceptance record already exists for subject {resolved_subject!r} "
            "with different content; refusing to overwrite (repeated acceptance "
            "cannot produce conflicting state)"
        )
    target.write_bytes(payload)
    return target


def load_acceptance_record(root: Path, subject_id: str) -> AcceptanceRecord:
    """Resolve one subject's persisted acceptance record, fail-closed."""
    target = canonical_acceptance_path(root, subject_id)
    if not target.exists():
        raise CrpValidationError(
            f"no accepted character package for subject {subject_id!r}"
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CrpValidationError(f"acceptance artifact is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CrpValidationError("acceptance artifact must be a JSON object")
    if data.get("artifact_type") != ACCEPTANCE_ARTIFACT_TYPE:
        raise CrpValidationError("acceptance artifact has wrong artifact_type")
    if data.get("schema_version") != ACCEPTANCE_SCHEMA_VERSION:
        raise CrpValidationError("acceptance artifact has wrong schema_version")
    record_data = data.get("acceptance_record")
    if not isinstance(record_data, dict):
        raise CrpValidationError("acceptance artifact missing acceptance_record object")
    record = acceptance_record_from_jsonable(record_data)
    if record.subject_id != subject_id:
        raise CrpValidationError(
            f"acceptance record subject {record.subject_id!r} != requested {subject_id!r}"
        )
    return record


def resolve_accepted_source_hash(root: Path, subject_id: str) -> str:
    """Resolve ``subject_id -> accepted source candidate hash`` (downstream handoff)."""
    return load_acceptance_record(root, subject_id).package_hash


def is_accepted(root: Path, subject_id: str) -> bool:
    """Distinguish an accepted package from a DRAFT/absent one.

    Returns ``False`` only when no acceptance record exists for the subject
    (i.e. the package is still pre-acceptance). A corrupt present record raises
    fail-closed rather than silently reading as "not accepted".
    """
    if not canonical_acceptance_path(root, subject_id).exists():
        return False
    return load_acceptance_record(root, subject_id).decision is PackageStatus.HUMAN_APPROVED
