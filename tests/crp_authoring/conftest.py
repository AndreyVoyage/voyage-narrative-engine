#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S0 -- hermetic synthetic fixtures (no Kira, no canon, no provider)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from services.crp_authoring import (
    CandidateCharacterPackage,
    ClaimStatus,
    ClaimType,
    CompileContext,
    Confidence,
    ContradictionRecord,
    PackageStatus,
    ResolutionStatus,
    RoleClaim,
    Severity,
    SourceEvidence,
    SourceType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def make_source(
    source_id: str = "se-001",
    source_type: SourceType = SourceType.OWNER_DIRECT,
    subject_id: str = "char-subject-1",
    **overrides,
) -> SourceEvidence:
    """A minimal valid SourceEvidence with sensible defaults."""
    kwargs = dict(
        source_id=source_id,
        subject_id=subject_id,
        source_type=source_type,
        content_ref="ref://raw/001",
        provenance="synthetic-fixture",
        intake_timestamp=utc_now(),
        content_hash="a" * 64,
        evidence_snapshot_id="snapshot-1",
    )
    kwargs.update(overrides)
    return SourceEvidence(**kwargs)


def make_claim(
    claim_id: str = "claim-001",
    claim_type: ClaimType = ClaimType.FACT,
    role_id: str = "R1",
    source_type_summary=(SourceType.OWNER_DIRECT,),
    **overrides,
) -> RoleClaim:
    """A minimal valid RoleClaim with sensible defaults."""
    kwargs = dict(
        claim_id=claim_id,
        subject_id="char-subject-1",
        role_id=role_id,
        claim="subject stated their favorite color is blue",
        claim_type=claim_type,
        source_evidence_ids=("se-001",),
        source_type_summary=tuple(source_type_summary),
        confidence=Confidence.KNOWN,
        rationale_summary="Owner stated it directly.",
        status=ClaimStatus.PROPOSED,
        target_module_or_layer="identity.base",
    )
    kwargs.update(overrides)
    return RoleClaim(**kwargs)


def make_contradiction(
    contradiction_id: str = "crd-001",
    claim_ids=("claim-001", "claim-002"),
    **overrides,
) -> ContradictionRecord:
    """A minimal valid ContradictionRecord with sensible defaults."""
    kwargs = dict(
        contradiction_id=contradiction_id,
        subject_id="char-subject-1",
        claim_ids=tuple(claim_ids),
        source_evidence_ids=("se-001", "se-002"),
        description="source A says X, source B says not-X",
        severity=Severity.MATERIAL,
        resolution_status=ResolutionStatus.OPEN,
        requires_human=False,
        created_by="system",
    )
    kwargs.update(overrides)
    return ContradictionRecord(**kwargs)


@pytest.fixture
def source_factory():
    return make_source


@pytest.fixture
def claim_factory():
    return make_claim


@pytest.fixture
def contradiction_factory():
    return make_contradiction


def make_compile_context(
    subject_id: str = "char-subject-1",
    package_id: str = "pkg-001",
    **overrides,
) -> CompileContext:
    """A minimal valid CompileContext with sensible defaults."""
    kwargs = dict(
        package_id=package_id,
        subject_id=subject_id,
        package_version=0,
        source_snapshot_id="snapshot-1",
        created_at=utc_now(),
    )
    kwargs.update(overrides)
    return CompileContext(**kwargs)


def make_package(
    package_id: str = "pkg-001",
    subject_id: str = "char-subject-1",
    claims=(),
    contradictions=(),
    **overrides,
) -> CandidateCharacterPackage:
    """A minimal valid CandidateCharacterPackage with sensible defaults."""
    kwargs = dict(
        package_id=package_id,
        subject_id=subject_id,
        package_version=0,
        source_snapshot_id="snapshot-1",
        role_result_refs=(),
        claims=tuple(claims),
        contradictions=tuple(contradictions),
        unknowns=(),
        psychology_candidate={},
        voice_candidate={},
        validation_results={},
        audit_result=None,
        provenance_manifest={},
        created_at=utc_now(),
        status=PackageStatus.DRAFT,
    )
    kwargs.update(overrides)
    return CandidateCharacterPackage(**kwargs)


@pytest.fixture
def compile_context_factory():
    return make_compile_context


@pytest.fixture
def package_factory():
    return make_package
