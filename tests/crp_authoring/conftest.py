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
    canonical_json_sha256,
    ClaimType,
    CompileContext,
    CompletionStatus,
    Confidence,
    ContradictionRecord,
    ExecutionType,
    KnowledgeProfile,
    PackageStatus,
    Permission,
    PERMISSIONS_BY_ROLE,
    ResolutionStatus,
    RetrievalPolicy,
    RoleClaim,
    RoleRegistry,
    RoleRegistryEntry,
    RoleResult,
    RoleStatus,
    RoleTask,
    Severity,
    SourceEvidence,
    SourceType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# Canonical synthetic facts used as the default substantive payload for tests
# that must exercise the hash-bound provider path. Tests constructing evidence
# with ``make_source`` (no content_hash override) can bind it to
# ``make_payload_map(...)`` because the default content_hash below is derived
# from these exact facts via the SAME canonical hash helper used in production.
DEFAULT_EVIDENCE_FACTS = [{"fact": "synthetic evidence fact"}]


def make_payload_map(*source_ids, facts=None):
    """Build a synthetic substantive payload map whose facts hash-bind to the
    default ``make_source`` content_hash (unless explicit facts override)."""
    facts = list(facts) if facts is not None else DEFAULT_EVIDENCE_FACTS
    return {
        sid: {"section_id": "s1", "title": "synthetic section", "facts": facts}
        for sid in source_ids
    }


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
        content_hash=canonical_json_sha256(DEFAULT_EVIDENCE_FACTS),
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


def make_knowledge_profile(
    profile_id: str = "profile-r2",
    role_id: str = "R2",
    version: str = "v1",
    allowed_source_types=(SourceType.OWNER_DIRECT, SourceType.DIRECT_QUOTE,
                          SourceType.OBSERVATION, SourceType.SELF_REPORT,
                          SourceType.THIRD_PARTY_REPORT, SourceType.SCENARIO_EVIDENCE),
    **overrides,
) -> KnowledgeProfile:
    kwargs = dict(
        profile_id=profile_id,
        role_id=role_id,
        version=version,
        allowed_kb_refs=(),
        allowed_source_types=tuple(allowed_source_types),
        forbidden_refs=(),
        retrieval_policy=RetrievalPolicy.EXACT_MODULAR_ONLY,
    )
    kwargs.update(overrides)
    return KnowledgeProfile(**kwargs)


def make_registry_entry(
    role_id: str = "R2",
    version: str = "v1",
    status: RoleStatus = RoleStatus.ACTIVE,
    execution_type: ExecutionType = ExecutionType.LLM_ROLE,
    permissions: frozenset = None,
    **overrides,
) -> RoleRegistryEntry:
    kwargs = dict(
        role_id=role_id,
        display_name=f"role {role_id}",
        version=version,
        status=status,
        execution_type=execution_type,
        prompt_ref=f"roles/vnext/{role_id}_v1_PROMPT.md",
        knowledge_profile_ref=f"profile-{role_id.lower()}",
        input_contract_ref="role_task_v1",
        output_contract_ref="role_result_v1",
        permissions=permissions if permissions is not None else PERMISSIONS_BY_ROLE.get(role_id, frozenset()),
        activation_gate="synthetic-test-activation",
    )
    kwargs.update(overrides)
    return RoleRegistryEntry(**kwargs)


def make_role_task(
    task_id: str = "task-001",
    role_id: str = "R2",
    role_version: str = "v1",
    subject_id: str = "char-subject-1",
    allowed_evidence_ids=("se-001",),
    allowed_prior_results=(),
    permissions=None,
    **overrides,
) -> RoleTask:
    kwargs = dict(
        task_id=task_id,
        role_id=role_id,
        role_version=role_version,
        subject_id=subject_id,
        run_id="run-1",
        evidence_snapshot_id="snapshot-1",
        allowed_evidence_ids=tuple(allowed_evidence_ids),
        allowed_prior_results=tuple(allowed_prior_results),
        knowledge_profile_ref=f"profile-{role_id.lower()}",
        input_contract_version="role_task_v1",
        output_contract_version="role_result_v1",
        permissions=tuple(p.value for p in (permissions if permissions is not None else PERMISSIONS_BY_ROLE[role_id])),
        task_goal="test task goal",
        revision_round=0,
    )
    kwargs.update(overrides)
    return RoleTask(**kwargs)


def make_role_result(
    task_id: str = "task-001",
    role_id: str = "R2",
    role_version: str = "v1",
    completion_status: CompletionStatus = CompletionStatus.COMPLETE,
    claims=(),
    **overrides,
) -> RoleResult:
    kwargs = dict(
        task_id=task_id,
        role_id=role_id,
        role_version=role_version,
        completion_status=completion_status,
        claims=tuple(claims),
        unknowns=(),
        contradictions=(),
        provenance_summary={"used_evidence": []},
    )
    kwargs.update(overrides)
    return RoleResult(**kwargs)


def make_fake_provider(raw_payload: str):
    """Return an injected provider callable returning a fixed string."""
    def provider(messages):
        return raw_payload
    return provider


@pytest.fixture
def knowledge_profile_factory():
    return make_knowledge_profile


@pytest.fixture
def registry_entry_factory():
    return make_registry_entry


@pytest.fixture
def role_task_factory():
    return make_role_task


@pytest.fixture
def role_result_factory():
    return make_role_result


@pytest.fixture
def fake_provider_factory():
    return make_fake_provider
