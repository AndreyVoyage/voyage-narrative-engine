#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S0 -- evidence-ledger domain contracts.

Immutable, detached plain-data value types for the three foundation contracts
(``SourceEvidence``, ``RoleClaim``, ``ContradictionRecord``) and their frozen
enum vocabularies, per ``CRP_MVP_CONTRACTS_v1.md`` (OWNER_RATIFIED_SPECIFICATION_CONTRACTS).

All models are ``@dataclass(frozen=True)`` containing only detached plain data,
never mutable state, live references, open handles, canon state, or provider
objects. S0 models only; no later-slice contracts (RoleTask/RoleResult/
RoleRegistryEntry/KnowledgeProfile/CandidateCharacterPackage/ReconstructionAudit/
BehavioralValidation*) are defined here.

Standard library only. No provider, no network, no canon import, no PAC/Sandbox
access, no legacy-KB import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Tuple

from .errors import CrpValidationError


# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------


class SourceType(Enum):
    """MVP ``source_type`` vocabulary (CRP_MVP_CONTRACTS_v1.md §A.1).

    Provenance axis only -- never used to express confidence.
    """

    OWNER_DIRECT = "OWNER_DIRECT"
    DIRECT_QUOTE = "DIRECT_QUOTE"
    OBSERVATION = "OBSERVATION"
    SELF_REPORT = "SELF_REPORT"
    THIRD_PARTY_REPORT = "THIRD_PARTY_REPORT"
    SCENARIO_EVIDENCE = "SCENARIO_EVIDENCE"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    MODEL_EXAMPLE = "MODEL_EXAMPLE"
    PAC_EXPORTED = "PAC_EXPORTED"
    SANDBOX_SNAPSHOT = "SANDBOX_SNAPSHOT"
    OTHER = "OTHER"


# Direct-evidence source classes (CRP_MVP_CONTRACTS_v1.md §B invariant): a
# FACT claim requires at least one of these, never solely
# MODEL_INFERENCE/MODEL_EXAMPLE.
DIRECT_SOURCE_TYPES: Tuple[SourceType, ...] = (
    SourceType.OWNER_DIRECT,
    SourceType.DIRECT_QUOTE,
    SourceType.OBSERVATION,
    SourceType.SELF_REPORT,
    SourceType.THIRD_PARTY_REPORT,
    SourceType.SCENARIO_EVIDENCE,
)

INFERENCE_SOURCE_TYPES: Tuple[SourceType, ...] = (
    SourceType.MODEL_INFERENCE,
    SourceType.MODEL_EXAMPLE,
)


class Confidence(Enum):
    """MVP confidence axis (CRP_MVP_CONTRACTS_v1.md §B.1) -- no numeric values."""

    KNOWN = "KNOWN"
    PROBABLE = "PROBABLE"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"
    CONTRADICTORY = "CONTRADICTORY"


class ClaimType(Enum):
    """MVP ``claim_type`` vocabulary (CRP_MVP_CONTRACTS_v1.md §B)."""

    FACT = "FACT"
    OBSERVATION = "OBSERVATION"
    SELF_REPORT = "SELF_REPORT"
    THIRD_PARTY_REPORT = "THIRD_PARTY_REPORT"
    BEHAVIORAL_EVIDENCE = "BEHAVIORAL_EVIDENCE"
    HYPOTHESIS = "HYPOTHESIS"
    INFERENCE = "INFERENCE"
    CONTRADICTION = "CONTRADICTION"
    UNKNOWN = "UNKNOWN"


class ClaimStatus(Enum):
    """MVP claim lifecycle status (CRP_MVP_CONTRACTS_v1.md §B)."""

    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED_BY_AUDIT = "REJECTED_BY_AUDIT"
    OWNER_RESOLVED = "OWNER_RESOLVED"


class VoicePatternLabel(Enum):
    """R4-scoped voice-pattern semantic label (CRP_MVP_SPEC_v1.md §12).

    A fourth, INDEPENDENT axis specific to R4 voice-reconstruction output,
    resolved by CRP_MVP_S2B_PROMPT_AUTHORING_PREFLIGHT_2026-08-17.md §6.
    It is NOT a ``source_type`` (provenance/origin), NOT a ``confidence``
    (epistemic strength), and NOT a general ``claim_type`` (claim semantic
    type). It is prospective vNext vocabulary, not recovered historical
    taxonomy.
    """

    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    GENERATED_RULE = "GENERATED_RULE"
    NEGATIVE_EXAMPLE = "NEGATIVE_EXAMPLE"


class Severity(Enum):
    """Contradiction severity (CRP_MVP_CONTRACTS_v1.md §C)."""

    COSMETIC = "COSMETIC"
    MATERIAL = "MATERIAL"
    IDENTITY_CRITICAL = "IDENTITY_CRITICAL"


class ResolutionStatus(Enum):
    """Contradiction resolution status (CRP_MVP_CONTRACTS_v1.md §C)."""

    OPEN = "OPEN"
    RESOLVED_BY_EVIDENCE = "RESOLVED_BY_EVIDENCE"
    OWNER_RESOLVED = "OWNER_RESOLVED"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# SourceEvidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceEvidence:
    """Atomic, immutable record of one piece of raw evidence about a subject.

    Never mixed with role-derived inference. Corrections are NEW records with
    ``metadata["supersedes_source_id"]``, never in-place edits
    (CRP_MVP_CONTRACTS_v1.md §A).
    """

    source_id: str
    subject_id: str
    source_type: SourceType
    content_ref: str
    provenance: str
    intake_timestamp: datetime
    content_hash: str
    evidence_snapshot_id: str

    speaker_or_author: Optional[str] = None
    source_timestamp: Optional[datetime] = None
    confidence: Optional[Confidence] = None
    restrictions: Tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.source_id, "source_id")
        _require_non_empty(self.subject_id, "subject_id")
        if not isinstance(self.source_type, SourceType):
            raise CrpValidationError("source_type must be a SourceType")
        _require_non_empty(self.content_ref, "content_ref")
        _require_non_empty(self.provenance, "provenance")
        if not isinstance(self.intake_timestamp, datetime):
            raise CrpValidationError("intake_timestamp must be a datetime")
        _require_non_empty(self.content_hash, "content_hash")
        _require_non_empty(self.evidence_snapshot_id, "evidence_snapshot_id")
        if self.speaker_or_author is not None:
            _require_non_empty(self.speaker_or_author, "speaker_or_author")
        if self.source_timestamp is not None and not isinstance(self.source_timestamp, datetime):
            raise CrpValidationError("source_timestamp must be a datetime or None")
        if self.confidence is not None and not isinstance(self.confidence, Confidence):
            raise CrpValidationError("confidence must be a Confidence or None")
        if not isinstance(self.restrictions, tuple) or any(
            not isinstance(r, str) or not r.strip() for r in self.restrictions
        ):
            raise CrpValidationError("restrictions must be a tuple of non-empty strings")
        if not isinstance(self.metadata, Mapping):
            raise CrpValidationError("metadata must be a mapping")
        object.__setattr__(self, "restrictions", tuple(self.restrictions))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


# ---------------------------------------------------------------------------
# RoleClaim
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleClaim:
    """Atomic unit of role-derived inference/assertion, traceable to evidence.

    Immutable once created; a correction produces a new claim, never an edit
    (CRP_MVP_CONTRACTS_v1.md §B).
    """

    claim_id: str
    subject_id: str
    role_id: str
    claim: str
    claim_type: ClaimType
    source_evidence_ids: Tuple[str, ...]
    source_type_summary: Tuple[SourceType, ...]
    confidence: Confidence
    rationale_summary: str
    status: ClaimStatus
    target_module_or_layer: str

    counterevidence_ids: Tuple[str, ...] = ()
    contradiction_ids: Tuple[str, ...] = ()
    revision_round: int = 0
    voice_pattern_label: Optional[VoicePatternLabel] = None

    def __post_init__(self) -> None:
        _require_non_empty(self.claim_id, "claim_id")
        _require_non_empty(self.subject_id, "subject_id")
        _require_non_empty(self.role_id, "role_id")
        _require_non_empty(self.claim, "claim")
        if not isinstance(self.claim_type, ClaimType):
            raise CrpValidationError("claim_type must be a ClaimType")
        if not isinstance(self.source_evidence_ids, tuple):
            raise CrpValidationError("source_evidence_ids must be a tuple")
        if self.claim_type != ClaimType.UNKNOWN and not self.source_evidence_ids:
            raise CrpValidationError(
                "source_evidence_ids must be non-empty for a non-UNKNOWN claim"
            )
        if not isinstance(self.source_type_summary, tuple) or not self.source_type_summary:
            raise CrpValidationError("source_type_summary must be a non-empty tuple of SourceType")
        for t in self.source_type_summary:
            if not isinstance(t, SourceType):
                raise CrpValidationError("source_type_summary must contain SourceType values")
        if not isinstance(self.confidence, Confidence):
            raise CrpValidationError("confidence must be a Confidence")
        _require_non_empty(self.rationale_summary, "rationale_summary")
        if not isinstance(self.status, ClaimStatus):
            raise CrpValidationError("status must be a ClaimStatus")
        _require_non_empty(self.target_module_or_layer, "target_module_or_layer")
        if not isinstance(self.counterevidence_ids, tuple) or not isinstance(self.contradiction_ids, tuple):
            raise CrpValidationError("counterevidence_ids/contradiction_ids must be tuples")
        if isinstance(self.revision_round, bool) or not isinstance(self.revision_round, int) or self.revision_round < 0:
            raise CrpValidationError("revision_round must be an int >= 0")
        if self.voice_pattern_label is not None and not isinstance(self.voice_pattern_label, VoicePatternLabel):
            raise CrpValidationError("voice_pattern_label must be a VoicePatternLabel or None")
        object.__setattr__(self, "source_evidence_ids", tuple(self.source_evidence_ids))
        object.__setattr__(self, "source_type_summary", tuple(self.source_type_summary))
        object.__setattr__(self, "counterevidence_ids", tuple(self.counterevidence_ids))
        object.__setattr__(self, "contradiction_ids", tuple(self.contradiction_ids))


# ---------------------------------------------------------------------------
# ContradictionRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContradictionRecord:
    """Preserve, never silently resolve, material conflict (CRP-OD-10).

    ``preferred_for_promotion`` never deletes the losing side -- both
    ``claim_ids`` remain linked and visible (CRP_MVP_CONTRACTS_v1.md §C).
    """

    contradiction_id: str
    subject_id: str
    claim_ids: Tuple[str, ...]
    source_evidence_ids: Tuple[str, ...]
    description: str
    severity: Severity
    resolution_status: ResolutionStatus
    requires_human: bool
    created_by: str

    resolvable_by_role: Optional[str] = None
    needs_interview: bool = False
    preferred_for_promotion: Optional[str] = None
    resolution_basis: Optional[str] = None

    def __post_init__(self) -> None:
        _require_non_empty(self.contradiction_id, "contradiction_id")
        _require_non_empty(self.subject_id, "subject_id")
        if not isinstance(self.claim_ids, tuple) or len(self.claim_ids) < 2:
            raise CrpValidationError("claim_ids must contain at least 2 claims")
        if not isinstance(self.source_evidence_ids, tuple):
            raise CrpValidationError("source_evidence_ids must be a tuple")
        _require_non_empty(self.description, "description")
        if not isinstance(self.severity, Severity):
            raise CrpValidationError("severity must be a Severity")
        if not isinstance(self.resolution_status, ResolutionStatus):
            raise CrpValidationError("resolution_status must be a ResolutionStatus")
        if not isinstance(self.requires_human, bool):
            raise CrpValidationError("requires_human must be a bool")
        _require_non_empty(self.created_by, "created_by")
        if self.preferred_for_promotion is not None and self.preferred_for_promotion not in self.claim_ids:
            raise CrpValidationError("preferred_for_promotion must be one of claim_ids")
        object.__setattr__(self, "claim_ids", tuple(self.claim_ids))
        object.__setattr__(self, "source_evidence_ids", tuple(self.source_evidence_ids))


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")
