#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP_MAINLINE_CONSOLIDATION_V1 Part 10 -- R3 relevance boundary tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.crp_authoring import (
    AMBIGUOUS_INTIMACY_SIGNAL,
    EXPLICIT_INTIMACY_BOUNDARY,
    EXPLICIT_INTIMACY_DOMAIN_INPUT,
    EXPLICIT_INTIMACY_RELATIONSHIP_CONTENT,
    EXPLICIT_OWNER_REQUEST,
    EXPLICIT_SEXUAL_TRAIT,
    EXISTING_INTIMACY_EVIDENCE,
    NO_INTIMACY_SIGNAL_FOUND,
    R3RelevanceStatus,
    SourceEvidence,
    SourceType,
    evaluate_r3_relevance,
)
from services.crp_authoring.errors import CrpValidationError

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _evidence(source_id: str, metadata: dict | None = None) -> SourceEvidence:
    return SourceEvidence(
        source_id=source_id,
        subject_id="test-subject",
        source_type=SourceType.OWNER_DIRECT,
        content_ref=f"ref/{source_id}",
        provenance="owner interview",
        intake_timestamp=_NOW,
        content_hash="a" * 64,
        evidence_snapshot_id="snap-1",
        metadata=metadata or {},
    )


class TestNotRelevantByDefault:
    def test_no_evidence_at_all_is_not_relevant(self):
        result = evaluate_r3_relevance(())
        assert result.status is R3RelevanceStatus.NOT_RELEVANT
        assert result.evidence_refs == ()
        assert NO_INTIMACY_SIGNAL_FOUND in result.reason_codes

    def test_evidence_with_no_intimacy_markers_is_not_relevant(self):
        evidence = (
            _evidence("e1", {"domain": "career"}),
            _evidence("e2", {"note": "likes hiking"}),
        )
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.NOT_RELEVANT
        assert result.evidence_refs == ()


class TestAppearanceOnlyNeverTriggersRelevance:
    def test_appearance_domain_tag_does_not_trigger(self):
        evidence = (_evidence("e1", {"domain": "appearance"}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.NOT_RELEVANT

    def test_gender_or_attractiveness_style_metadata_does_not_trigger(self):
        # SourceEvidence has no gender/attractiveness field; even if a caller
        # stuffs such notions into unrecognized metadata keys, the evaluator
        # only reads its documented explicit keys -- nothing else contributes.
        evidence = (
            _evidence(
                "e1",
                {
                    "gender": "female",
                    "attractiveness_note": "considered conventionally attractive",
                    "appearance_summary": "tall, athletic build",
                },
            ),
        )
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.NOT_RELEVANT
        assert result.reason_codes == (NO_INTIMACY_SIGNAL_FOUND,)

    def test_attachment_label_alone_does_not_trigger(self):
        evidence = (_evidence("e1", {"attachment_style": "anxious-preoccupied"}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.NOT_RELEVANT


class TestExplicitIntimacyEvidenceIsRelevant:
    def test_explicit_domain_tag(self):
        evidence = (_evidence("e1", {"domain": "intimacy"}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert result.evidence_refs == ("e1",)
        assert EXPLICIT_INTIMACY_DOMAIN_INPUT in result.reason_codes
        assert EXISTING_INTIMACY_EVIDENCE in result.reason_codes

    def test_sexuality_domain_tag_case_insensitive(self):
        evidence = (_evidence("e1", {"domains": ["Sexuality"]}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION

    def test_explicit_sexual_trait(self):
        evidence = (_evidence("e1", {"explicit_sexual_trait": True}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert EXPLICIT_SEXUAL_TRAIT in result.reason_codes

    def test_explicit_intimacy_boundary(self):
        evidence = (_evidence("e1", {"explicit_intimacy_boundary": True}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert EXPLICIT_INTIMACY_BOUNDARY in result.reason_codes

    def test_intimacy_relationship_content(self):
        evidence = (_evidence("e1", {"intimacy_relationship_content": True}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert EXPLICIT_INTIMACY_RELATIONSHIP_CONTENT in result.reason_codes

    def test_explicit_owner_request(self):
        evidence = (_evidence("e1", {"owner_requested_domains": ("intimacy",)}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert EXPLICIT_OWNER_REQUEST in result.reason_codes

    def test_only_relevant_evidence_ids_are_referenced(self):
        evidence = (
            _evidence("e1", {"domain": "career"}),
            _evidence("e2", {"explicit_sexual_trait": True}),
        )
        result = evaluate_r3_relevance(evidence)
        assert result.evidence_refs == ("e2",)


class TestInsufficientEvidence:
    def test_ambiguous_signal_without_stronger_marker(self):
        evidence = (_evidence("e1", {"intimacy_signal": "ambiguous"}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.INSUFFICIENT_EVIDENCE
        assert result.evidence_refs == ("e1",)
        assert AMBIGUOUS_INTIMACY_SIGNAL in result.reason_codes

    def test_strong_marker_wins_over_ambiguous_marker_elsewhere(self):
        evidence = (
            _evidence("e1", {"intimacy_signal": "AMBIGUOUS"}),
            _evidence("e2", {"explicit_sexual_trait": True}),
        )
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        assert result.evidence_refs == ("e2",)


class TestRelevanceNeverAuthorizes:
    def test_relevance_result_has_no_authorization_field_or_capability(self):
        evidence = (_evidence("e1", {"explicit_sexual_trait": True}),)
        result = evaluate_r3_relevance(evidence)
        assert not hasattr(result, "activation_authorization_ref")
        assert not hasattr(result, "authorization_ref")
        # frozen dataclass: exactly the three documented fields, nothing else.
        assert set(result.__dataclass_fields__) == {"status", "evidence_refs", "reason_codes"}

    def test_relevant_result_still_requires_activation_authorization_ref_downstream(self):
        from services.crp_authoring import RoleTask

        evidence = (_evidence("e1", {"explicit_sexual_trait": True}),)
        result = evaluate_r3_relevance(evidence)
        assert result.status is R3RelevanceStatus.RELEVANT_REQUIRES_AUTHORIZATION
        # A RELEVANT_REQUIRES_AUTHORIZATION verdict does not itself let an R3
        # RoleTask be constructed without an explicit authorization ref.
        with pytest.raises(CrpValidationError):
            RoleTask(
                task_id="t1",
                role_id="R3",
                role_version="v1",
                subject_id="test-subject",
                run_id="run-1",
                evidence_snapshot_id="snap-1",
                allowed_evidence_ids=("e1",),
                allowed_prior_results=(),
                knowledge_profile_ref="profile-r3",
                input_contract_version="1",
                output_contract_version="1",
                permissions=("READ_SOURCE_EVIDENCE",),
                task_goal="test",
                revision_round=0,
                activation_authorization_ref=None,
            )


class TestInputValidation:
    def test_rejects_non_source_evidence_items(self):
        with pytest.raises(CrpValidationError):
            evaluate_r3_relevance(({"not": "evidence"},))
