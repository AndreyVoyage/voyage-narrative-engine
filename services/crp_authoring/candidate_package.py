#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S1 -- CandidateCharacterPackage contract.

The central MVP artifact (CRP_MVP_CONTRACTS_v1.md §H): output of the whole
pipeline, NEVER canon. In S1 only the ``DRAFT``->``VALIDATED`` segment is
reachable; ``AUDITED``/``HUMAN_APPROVED``/``REJECTED`` are reserved for later
slices (R8/human). ``HUMAN_APPROVED`` is explicitly NOT canon promotion.

Immutable, detached plain data: frozen dataclass, no provider, no network, no
canon access, no PAC/Sandbox access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .contracts import ContradictionRecord, RoleClaim
from .errors import CrpValidationError


class PackageStatus(Enum):
    """Candidate package lifecycle (CRP_MVP_CONTRACTS_v1.md §H.1)."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AUDITED = "AUDITED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CandidateCharacterPackage:
    """The central, immutable candidate artifact -- never canon.

    Required fields per CRP_MVP_CONTRACTS_v1.md §H. In S1 ``role_result_refs``
    is legitimately ``()`` (no RoleResult until S2) and ``audit_result`` is
    ``None`` (R8 is S3) -- internally consistent, not an error.
    """

    package_id: str
    subject_id: str
    package_version: int
    source_snapshot_id: str
    role_result_refs: Tuple[str, ...]
    claims: Tuple[RoleClaim, ...]
    contradictions: Tuple[ContradictionRecord, ...]
    unknowns: Tuple[Any, ...]
    psychology_candidate: Mapping[str, Tuple[RoleClaim, ...]]
    voice_candidate: Mapping[str, Tuple[RoleClaim, ...]]
    validation_results: Mapping[str, Any]
    audit_result: Optional[Any]
    provenance_manifest: Mapping[str, Tuple[str, ...]]
    created_at: datetime
    status: PackageStatus

    lineage: Optional[str] = None
    behavioral_validation_refs: Tuple[str, ...] = ()
    intimacy_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)
    identity_biography_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)
    behavior_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)
    relationships_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)
    boundaries_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)
    seed_memory_candidate: Mapping[str, Tuple[RoleClaim, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.package_id, "package_id")
        _require_non_empty(self.subject_id, "subject_id")
        if isinstance(self.package_version, bool) or not isinstance(self.package_version, int) \
                or self.package_version < 0:
            raise CrpValidationError("package_version must be an int >= 0")
        _require_non_empty(self.source_snapshot_id, "source_snapshot_id")
        if not isinstance(self.role_result_refs, tuple):
            raise CrpValidationError("role_result_refs must be a tuple")
        if not isinstance(self.claims, tuple):
            raise CrpValidationError("claims must be a tuple of RoleClaim")
        for claim in self.claims:
            if not isinstance(claim, RoleClaim):
                raise CrpValidationError("claims must contain RoleClaim instances")
        if not isinstance(self.contradictions, tuple):
            raise CrpValidationError("contradictions must be a tuple of ContradictionRecord")
        for record in self.contradictions:
            if not isinstance(record, ContradictionRecord):
                raise CrpValidationError("contradictions must contain ContradictionRecord instances")
        if not isinstance(self.unknowns, tuple):
            raise CrpValidationError("unknowns must be a tuple")
        if not isinstance(self.psychology_candidate, Mapping):
            raise CrpValidationError("psychology_candidate must be a mapping")
        if not isinstance(self.voice_candidate, Mapping):
            raise CrpValidationError("voice_candidate must be a mapping")
        if not isinstance(self.validation_results, Mapping):
            raise CrpValidationError("validation_results must be a mapping")
        if not isinstance(self.provenance_manifest, Mapping):
            raise CrpValidationError("provenance_manifest must be a mapping")
        if not isinstance(self.created_at, datetime):
            raise CrpValidationError("created_at must be a datetime")
        if not isinstance(self.status, PackageStatus):
            raise CrpValidationError("status must be a PackageStatus")
        if self.lineage is not None:
            _require_non_empty(self.lineage, "lineage")
        if not isinstance(self.behavioral_validation_refs, tuple):
            raise CrpValidationError("behavioral_validation_refs must be a tuple")
        if not isinstance(self.intimacy_candidate, Mapping):
            raise CrpValidationError("intimacy_candidate must be a mapping")
        if not isinstance(self.identity_biography_candidate, Mapping):
            raise CrpValidationError("identity_biography_candidate must be a mapping")
        if not isinstance(self.behavior_candidate, Mapping):
            raise CrpValidationError("behavior_candidate must be a mapping")
        if not isinstance(self.relationships_candidate, Mapping):
            raise CrpValidationError("relationships_candidate must be a mapping")
        if not isinstance(self.boundaries_candidate, Mapping):
            raise CrpValidationError("boundaries_candidate must be a mapping")
        if not isinstance(self.seed_memory_candidate, Mapping):
            raise CrpValidationError("seed_memory_candidate must be a mapping")

        # Freeze contained mutable structures in place (immutable value type).
        object.__setattr__(self, "role_result_refs", tuple(self.role_result_refs))
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "unknowns", tuple(self.unknowns))
        object.__setattr__(self, "behavioral_validation_refs", tuple(self.behavioral_validation_refs))
        object.__setattr__(
            self, "psychology_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.psychology_candidate.items()
            }),
        )
        object.__setattr__(
            self, "voice_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.voice_candidate.items()
            }),
        )
        object.__setattr__(
            self, "intimacy_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.intimacy_candidate.items()
            }),
        )
        object.__setattr__(
            self, "identity_biography_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.identity_biography_candidate.items()
            }),
        )
        object.__setattr__(
            self, "behavior_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.behavior_candidate.items()
            }),
        )
        object.__setattr__(
            self, "relationships_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.relationships_candidate.items()
            }),
        )
        object.__setattr__(
            self, "boundaries_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.boundaries_candidate.items()
            }),
        )
        object.__setattr__(
            self, "seed_memory_candidate",
            MappingProxyType({
                k: tuple(v) for k, v in self.seed_memory_candidate.items()
            }),
        )
        object.__setattr__(
            self, "provenance_manifest",
            MappingProxyType({
                k: tuple(v) for k, v in self.provenance_manifest.items()
            }),
        )
        object.__setattr__(
            self, "validation_results",
            MappingProxyType(dict(self.validation_results)),
        )


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")