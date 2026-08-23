#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for Generated Image Review v0 (C2).

Deterministic, hermetic, and fully offline:

    NETWORK_CALLS = 0
    PROVIDER_CALLS  = 0
    LLM_CALLS       = 0
    MEDIA_GENERATION = 0
    CANON_WRITES     = 0
    ASSET_REGISTRY_WRITES = 0
    OPENAI_API_KEY_ACCESS = NO

These tests verify the human-only review/approval contract: candidate
identity, deterministic content hash, deep immutability, portable
serialization, production-eligibility non-promotion, and review-decision
semantics. They never import generated image bytes and never depend on the
machine-local C1 PNG.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.generated_image_review import (  # noqa: E402
    CANDIDATE_SCHEMA_VERSION,
    REVIEW_SCHEMA_VERSION,
    SUPPORTED_IMAGE_FORMATS,
    GeneratedImageCandidate,
    GeneratedImageReview,
    GeneratedImageReviewValidationError,
    InvalidReviewDecisionError,
    ReviewCandidateMismatchError,
    ReviewDecision,
    UnsupportedImageFormatError,
    build_generated_image_candidate,
    build_generated_image_review,
    verify_review_matches_candidate,
)

# Hermetic C1-like metadata (matches the real C1 image identity, but no
# machine-local binary is read or required).
C1_MEDIA_ITEM_ID = "kira_yoga_hall_pilot_image_01"
C1_IMAGE_SHA256 = "1491fdf3341009898e33e6f903ab0d1b03451f613bdf396922d587a231318ec5"
C1_IMAGE_BYTE_LENGTH = 1_419_457
C1_IMAGE_FORMAT = "PNG"
PROMPT_ITEM_HASH = "prompt_item_hash_c1_0001"


def _candidate(**overrides):
    kwargs = dict(
        source_media_item_id=C1_MEDIA_ITEM_ID,
        image_sha256=C1_IMAGE_SHA256,
        image_format=C1_IMAGE_FORMAT,
        image_byte_length=C1_IMAGE_BYTE_LENGTH,
        production_eligible=False,
        source_prompt_item_hash=PROMPT_ITEM_HASH,
        provider="openai",
        provider_model_or_operation="gpt-image-2",
    )
    kwargs.update(overrides)
    return build_generated_image_candidate(**kwargs)


# ---------------------------------------------------------------------------
# Candidate: construction + identity
# ---------------------------------------------------------------------------


def test_valid_candidate_construction():
    c = _candidate()
    assert isinstance(c, GeneratedImageCandidate)
    assert c.source_media_item_id == C1_MEDIA_ITEM_ID
    assert c.image_sha256 == C1_IMAGE_SHA256
    assert c.image_format == "PNG"
    assert c.image_byte_length == C1_IMAGE_BYTE_LENGTH
    assert c.source_prompt_item_hash == PROMPT_ITEM_HASH
    assert c.provider == "openai"
    assert c.provider_model_or_operation == "gpt-image-2"
    assert c.production_eligible is False
    assert len(c.content_hash) == 64


def test_sha256_normalized_to_lowercase():
    c = _candidate(image_sha256=C1_IMAGE_SHA256.upper())
    assert c.image_sha256 == C1_IMAGE_SHA256


def test_empty_media_item_id_rejected():
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(source_media_item_id="   ")


def test_invalid_sha256_rejected():
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(image_sha256="not-hex")
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(image_sha256="abc123")


def test_non_positive_byte_length_rejected():
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(image_byte_length=0)
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(image_byte_length=-5)


def test_unsupported_format_rejected():
    with pytest.raises(UnsupportedImageFormatError):
        _candidate(image_format="GIF")


def test_jpeg_and_jpg_normalize():
    c = _candidate(image_format="jpeg")
    assert c.image_format == "JPEG"
    c2 = _candidate(image_format="JPG")
    assert c2.image_format == "JPEG"
    assert c.content_hash == c2.content_hash


def test_optional_provider_fields_none_by_default():
    c = build_generated_image_candidate(
        source_media_item_id=C1_MEDIA_ITEM_ID,
        image_sha256=C1_IMAGE_SHA256,
        image_format="PNG",
        image_byte_length=C1_IMAGE_BYTE_LENGTH,
        production_eligible=False,
    )
    assert c.source_prompt_item_hash is None
    assert c.provider is None
    assert c.provider_model_or_operation is None


def test_empty_optional_string_rejected():
    with pytest.raises(GeneratedImageReviewValidationError):
        _candidate(source_prompt_item_hash="  ")


# ---------------------------------------------------------------------------
# Candidate: hash determinism
# ---------------------------------------------------------------------------


def test_candidate_hash_deterministic():
    a = _candidate()
    b = _candidate()
    assert a.content_hash == b.content_hash


def test_candidate_hash_changes_with_metadata():
    base = _candidate()
    assert _candidate(image_sha256=("0" * 64)).content_hash != base.content_hash
    assert _candidate(image_byte_length=123).content_hash != base.content_hash
    assert _candidate(source_media_item_id="other_item").content_hash != base.content_hash
    assert _candidate(provider="other").content_hash != base.content_hash


# ---------------------------------------------------------------------------
# Candidate: deep immutability + serialization portability
# ---------------------------------------------------------------------------


def test_candidate_is_frozen():
    c = _candidate()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.image_sha256 = "0" * 64  # type: ignore[misc]


def test_candidate_serialization_portable_no_absolute_path():
    c = _candidate()
    blob = json.dumps(c.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "C:" not in blob.upper().replace("CONTENT_HASH", "")
    assert "C:/" not in blob
    assert "content_hash" in c.to_dict()


def test_candidate_semantic_payload_excludes_envelope():
    c = _candidate()
    sp = c.semantic_payload()
    assert "schema_version" not in sp
    assert "content_hash" not in sp
    assert "image_sha256" in sp


# ---------------------------------------------------------------------------
# Candidate: production eligibility is preserved, never promoted
# ---------------------------------------------------------------------------


def test_candidate_preserves_production_eligible_false():
    c = _candidate(production_eligible=False)
    assert c.production_eligible is False


def test_candidate_preserves_production_eligible_true():
    c = _candidate(production_eligible=True)
    assert c.production_eligible is True


# ---------------------------------------------------------------------------
# Review: human decision semantics
# ---------------------------------------------------------------------------


def test_approved_accepted_when_caller_supplied():
    c = _candidate()
    r = build_generated_image_review(
        review_id="rev-0001", candidate=c, decision="APPROVED"
    )
    assert r.decision is ReviewDecision.APPROVED
    assert r.candidate_content_hash == c.content_hash


def test_rejected_accepted_when_caller_supplied():
    c = _candidate()
    r = build_generated_image_review(
        review_id="rev-0002", candidate=c, decision=ReviewDecision.REJECTED
    )
    assert r.decision is ReviewDecision.REJECTED


def test_invalid_decision_rejected():
    c = _candidate()
    with pytest.raises(InvalidReviewDecisionError):
        build_generated_image_review(review_id="r", candidate=c, decision="PENDING")
    with pytest.raises(InvalidReviewDecisionError):
        build_generated_image_review(review_id="r", candidate=c, decision="approved")


def test_empty_review_id_rejected():
    c = _candidate()
    with pytest.raises(GeneratedImageReviewValidationError):
        build_generated_image_review(review_id="  ", candidate=c, decision="APPROVED")


def test_review_binds_candidate_content_hash():
    c = _candidate()
    r = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    assert r.candidate_content_hash == c.content_hash


def test_review_hash_deterministic():
    c = _candidate()
    r1 = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    r2 = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    assert r1.content_hash == r2.content_hash


def test_review_is_frozen():
    c = _candidate()
    r = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.decision = ReviewDecision.REJECTED  # type: ignore[misc]


def test_review_note_preserved():
    c = _candidate()
    r = build_generated_image_review(
        review_id="r", candidate=c, decision="REJECTED", note="synthetic review note"
    )
    assert r.note == "synthetic review note"


def test_review_reviewer_id_optional():
    c = _candidate()
    r = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    assert r.reviewer_id is None
    r2 = build_generated_image_review(
        review_id="r", candidate=c, decision="APPROVED", reviewer_id="owner"
    )
    assert r2.reviewer_id == "owner"


# ---------------------------------------------------------------------------
# Review: new decision over same candidate is a new artifact
# ---------------------------------------------------------------------------


def test_changed_decision_does_not_mutate_existing_review():
    c = _candidate()
    approved = build_generated_image_review(review_id="r1", candidate=c, decision="APPROVED")
    rejected = build_generated_image_review(review_id="r2", candidate=c, decision="REJECTED")
    assert approved.decision is ReviewDecision.APPROVED
    assert rejected.decision is ReviewDecision.REJECTED
    assert approved.content_hash != rejected.content_hash


def test_review_does_not_mutate_candidate():
    c = _candidate()
    before = c.to_dict()
    build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    assert c.to_dict() == before
    assert c.production_eligible is False


# ---------------------------------------------------------------------------
# Review: candidate mismatch fails closed
# ---------------------------------------------------------------------------


def test_review_mismatch_fails_closed():
    c1 = _candidate()
    c2 = _candidate(image_sha256=("1" * 64))
    r = build_generated_image_review(review_id="r", candidate=c1, decision="APPROVED")
    with pytest.raises(ReviewCandidateMismatchError):
        verify_review_matches_candidate(r, c2)


def test_review_matches_candidate_passes():
    c = _candidate()
    r = build_generated_image_review(review_id="r", candidate=c, decision="APPROVED")
    verify_review_matches_candidate(r, c)


# ---------------------------------------------------------------------------
# Contract surface invariants
# ---------------------------------------------------------------------------


def test_supported_formats_are_png_jpeg_webp():
    assert SUPPORTED_IMAGE_FORMATS == frozenset({"PNG", "JPEG", "WEBP"})


def test_only_two_decisions_supported():
    assert {d.value for d in ReviewDecision} == {"APPROVED", "REJECTED"}


def test_schema_versions_stable():
    assert CANDIDATE_SCHEMA_VERSION == "generated_image_candidate/0.1"
    assert REVIEW_SCHEMA_VERSION == "generated_image_review/0.1"


def test_review_serialization_portable():
    c = _candidate()
    r = build_generated_image_review(
        review_id="r", candidate=c, decision="APPROVED", note="n"
    )
    blob = json.dumps(r.to_dict(), ensure_ascii=False, sort_keys=True)
    assert "C:/" not in blob
    assert r.to_dict()["decision"] == "APPROVED"