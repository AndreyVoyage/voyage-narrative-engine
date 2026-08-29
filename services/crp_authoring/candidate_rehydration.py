#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP -- strict ``CandidateCharacterPackage`` rehydration from persisted JSON.

``tools/crp_kira_r4_runner._to_jsonable`` persists the full candidate as a plain
JSON-safe dict (dataclasses -> objects, ``Enum`` -> its string ``.value``,
``datetime`` -> ``.isoformat()``, tuples/lists -> lists, mappings -> objects).
This module is the strict inverse of that transport form: it reconstructs a
typed ``CandidateCharacterPackage`` (and its nested ``RoleClaim`` /
``ContradictionRecord`` / ``unknowns`` records) from that persisted dict,
fail-closed on any missing/unknown field, wrong primitive or container type,
malformed datetime, or invalid enum value.

Design rules (do not relax):

- No silent defaults for corrupted data: missing required fields, unknown keys,
  invalid enum strings, malformed datetimes, and wrong container types raise
  ``CrpValidationError`` instead of being repaired.
- No migrations, no schema-version redesign, and no change to the
  ``CandidateCharacterPackage`` contract. This only inverts the existing
  ``_to_jsonable`` transport form.
- The produced object is a real ``CandidateCharacterPackage`` instance
  (``isinstance(result, CandidateCharacterPackage) is True``) with all nested
  records re-typed, so ``compute_package_hash(result)`` reproduces the canonical
  persisted package hash.

Standard library only; no provider, no network, no canon, no PAC/Sandbox access.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Tuple, Type, TypeVar

from .candidate_package import CandidateCharacterPackage, PackageStatus
from .contracts import (
    ClaimStatus,
    ClaimType,
    Confidence,
    ContradictionRecord,
    ResolutionStatus,
    RoleClaim,
    Severity,
    SourceType,
    VoicePatternLabel,
)
from .errors import CrpValidationError

__all__ = [
    "rehydrate_candidate_package",
    "rehydrate_role_claim",
    "rehydrate_contradiction_record",
]

_EnumT = TypeVar("_EnumT", bound=Enum)


# ---------------------------------------------------------------------------
# Fail-closed primitive/container coercion helpers
# ---------------------------------------------------------------------------

def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise CrpValidationError(f"{field_name} must be a string")
    return value


def _require_non_empty_str(value: Any, field_name: str) -> str:
    _require_str(value, field_name)
    if not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")
    return value


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CrpValidationError(f"{field_name} must be an int >= 0")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise CrpValidationError(f"{field_name} must be a bool")
    return value


def _require_list(value: Any, field_name: str) -> list:
    if not isinstance(value, list):
        raise CrpValidationError(f"{field_name} must be a list")
    return value


def _require_object(value: Any, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise CrpValidationError(f"{field_name} must be an object")
    return value


def _restore_str_tuple(value: Any, field_name: str) -> Tuple[str, ...]:
    """Restore a serialized ``Tuple[str, ...]`` (persisted as a JSON list)."""
    _require_list(value, field_name)
    out = []
    for item in value:
        if not isinstance(item, str):
            raise CrpValidationError(f"{field_name} must contain only strings")
        out.append(item)
    return tuple(out)


def _restore_enum(enum_cls: Type[_EnumT], value: Any, field_name: str) -> _EnumT:
    """Restore a serialized enum string to its exact enum instance (fail-closed)."""
    if not isinstance(value, str):
        raise CrpValidationError(f"{field_name} must be a string enum value")
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise CrpValidationError(
            f"{field_name} has invalid enum value {value!r}"
        ) from exc


def _restore_datetime(value: Any, field_name: str) -> datetime:
    """Restore a serialized ISO-8601 datetime (fail-closed on malformed input)."""
    if not isinstance(value, str):
        raise CrpValidationError(f"{field_name} must be an ISO-8601 string")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise CrpValidationError(
            f"{field_name} has malformed datetime {value!r}"
        ) from exc


def _restore_optional_str(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    return _require_non_empty_str(value, field_name)


def _restore_optional_enum(
    enum_cls: Type[_EnumT], value: Any, field_name: str
) -> Any:
    if value is None:
        return None
    return _restore_enum(enum_cls, value, field_name)


def _validate_object_keys(
    data: Any,
    cls: Type[Any],
    label: str,
) -> None:
    """Require ``data`` to be an object whose keys exactly match a frozen
    dataclass's field names (all fields are persisted by ``_to_jsonable``, so a
    missing field or an unknown key is structural corruption)."""
    if not isinstance(data, dict):
        raise CrpValidationError(f"{label} must be an object")
    canonical = {f.name for f in dataclasses.fields(cls)}
    actual = set(data.keys())
    missing = canonical - actual
    if missing:
        raise CrpValidationError(
            f"{label} is missing required field(s): {sorted(missing)}"
        )
    unknown = actual - canonical
    if unknown:
        raise CrpValidationError(
            f"{label} has unknown field(s): {sorted(unknown)}"
        )


# ---------------------------------------------------------------------------
# Nested record rehydration
# ---------------------------------------------------------------------------

def rehydrate_role_claim(data: Any) -> RoleClaim:
    """Rehydrate one persisted ``RoleClaim`` object into a typed ``RoleClaim``."""
    _validate_object_keys(data, RoleClaim, "claim")
    return RoleClaim(
        claim_id=_require_non_empty_str(data["claim_id"], "claim_id"),
        subject_id=_require_non_empty_str(data["subject_id"], "subject_id"),
        role_id=_require_non_empty_str(data["role_id"], "role_id"),
        claim=_require_non_empty_str(data["claim"], "claim"),
        claim_type=_restore_enum(ClaimType, data["claim_type"], "claim_type"),
        source_evidence_ids=_restore_str_tuple(
            data["source_evidence_ids"], "source_evidence_ids"
        ),
        source_type_summary=tuple(
            _restore_enum(SourceType, item, "source_type_summary")
            for item in _require_list(data["source_type_summary"], "source_type_summary")
        ),
        confidence=_restore_enum(Confidence, data["confidence"], "confidence"),
        rationale_summary=_require_non_empty_str(
            data["rationale_summary"], "rationale_summary"
        ),
        status=_restore_enum(ClaimStatus, data["status"], "status"),
        target_module_or_layer=_require_non_empty_str(
            data["target_module_or_layer"], "target_module_or_layer"
        ),
        counterevidence_ids=_restore_str_tuple(
            data["counterevidence_ids"], "counterevidence_ids"
        ),
        contradiction_ids=_restore_str_tuple(
            data["contradiction_ids"], "contradiction_ids"
        ),
        revision_round=_require_int(data["revision_round"], "revision_round"),
        voice_pattern_label=_restore_optional_enum(
            VoicePatternLabel, data["voice_pattern_label"], "voice_pattern_label"
        ),
    )


def rehydrate_contradiction_record(data: Any) -> ContradictionRecord:
    """Rehydrate one persisted ``ContradictionRecord`` into a typed instance."""
    _validate_object_keys(data, ContradictionRecord, "contradiction")
    return ContradictionRecord(
        contradiction_id=_require_non_empty_str(
            data["contradiction_id"], "contradiction_id"
        ),
        subject_id=_require_non_empty_str(data["subject_id"], "subject_id"),
        claim_ids=_restore_str_tuple(data["claim_ids"], "claim_ids"),
        source_evidence_ids=_restore_str_tuple(
            data["source_evidence_ids"], "source_evidence_ids"
        ),
        description=_require_non_empty_str(data["description"], "description"),
        severity=_restore_enum(Severity, data["severity"], "severity"),
        resolution_status=_restore_enum(
            ResolutionStatus, data["resolution_status"], "resolution_status"
        ),
        requires_human=_require_bool(data["requires_human"], "requires_human"),
        created_by=_require_non_empty_str(data["created_by"], "created_by"),
        resolvable_by_role=_restore_optional_str(
            data["resolvable_by_role"], "resolvable_by_role"
        ),
        needs_interview=_require_bool(data["needs_interview"], "needs_interview"),
        preferred_for_promotion=_restore_optional_str(
            data["preferred_for_promotion"], "preferred_for_promotion"
        ),
        resolution_basis=_restore_optional_str(
            data["resolution_basis"], "resolution_basis"
        ),
    )


# ---------------------------------------------------------------------------
# CandidateCharacterPackage rehydration
# ---------------------------------------------------------------------------

def _restore_claim_mapping(
    value: Any, field_name: str
) -> Mapping[str, Tuple[RoleClaim, ...]]:
    """Restore a persisted ``Mapping[str, Tuple[RoleClaim, ...]]``."""
    _require_object(value, field_name)
    out: dict[str, Tuple[RoleClaim, ...]] = {}
    for key, claims in value.items():
        if not isinstance(key, str):
            raise CrpValidationError(f"{field_name} keys must be strings")
        _require_list(claims, f"{field_name}[{key!r}]")
        out[key] = tuple(rehydrate_role_claim(c) for c in claims)
    return out


def _restore_provenance_manifest(value: Any) -> Mapping[str, Tuple[str, ...]]:
    """Restore the persisted ``Mapping[str, Tuple[str, ...]]`` provenance manifest."""
    _require_object(value, "provenance_manifest")
    out: dict[str, Tuple[str, ...]] = {}
    for key, claim_ids in value.items():
        if not isinstance(key, str):
            raise CrpValidationError("provenance_manifest keys must be strings")
        out[key] = _restore_str_tuple(claim_ids, f"provenance_manifest[{key!r}]")
    return out


def rehydrate_candidate_package(data: Any) -> CandidateCharacterPackage:
    """Rehydrate a persisted ``candidate_package`` dict into a typed package.

    Produces a real ``CandidateCharacterPackage`` instance; ``compute_package_hash``
    over the result must reproduce the persisted ``candidate_package_hash``.
    """
    _validate_object_keys(data, CandidateCharacterPackage, "candidate_package")

    return CandidateCharacterPackage(
        package_id=_require_non_empty_str(data["package_id"], "package_id"),
        subject_id=_require_non_empty_str(data["subject_id"], "subject_id"),
        package_version=_require_int(data["package_version"], "package_version"),
        source_snapshot_id=_require_non_empty_str(
            data["source_snapshot_id"], "source_snapshot_id"
        ),
        role_result_refs=_restore_str_tuple(
            data["role_result_refs"], "role_result_refs"
        ),
        claims=tuple(
            rehydrate_role_claim(c)
            for c in _require_list(data["claims"], "claims")
        ),
        contradictions=tuple(
            rehydrate_contradiction_record(c)
            for c in _require_list(data["contradictions"], "contradictions")
        ),
        # ``unknowns`` are UNKNOWN RoleClaim records (gap signals) preserved verbatim.
        unknowns=tuple(
            rehydrate_role_claim(u)
            for u in _require_list(data["unknowns"], "unknowns")
        ),
        psychology_candidate=_restore_claim_mapping(
            data["psychology_candidate"], "psychology_candidate"
        ),
        voice_candidate=_restore_claim_mapping(
            data["voice_candidate"], "voice_candidate"
        ),
        validation_results=_require_object(
            data["validation_results"], "validation_results"
        ),
        audit_result=data["audit_result"],
        provenance_manifest=_restore_provenance_manifest(data["provenance_manifest"]),
        created_at=_restore_datetime(data["created_at"], "created_at"),
        status=_restore_enum(PackageStatus, data["status"], "status"),
        lineage=_restore_optional_str(data["lineage"], "lineage"),
        behavioral_validation_refs=_restore_str_tuple(
            data["behavioral_validation_refs"], "behavioral_validation_refs"
        ),
        intimacy_candidate=_restore_claim_mapping(
            data["intimacy_candidate"], "intimacy_candidate"
        ),
        identity_biography_candidate=_restore_claim_mapping(
            data["identity_biography_candidate"], "identity_biography_candidate"
        ),
        behavior_candidate=_restore_claim_mapping(
            data["behavior_candidate"], "behavior_candidate"
        ),
        relationships_candidate=_restore_claim_mapping(
            data["relationships_candidate"], "relationships_candidate"
        ),
        boundaries_candidate=_restore_claim_mapping(
            data["boundaries_candidate"], "boundaries_candidate"
        ),
        seed_memory_candidate=_restore_claim_mapping(
            data["seed_memory_candidate"], "seed_memory_candidate"
        ),
    )
