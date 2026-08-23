#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated Image Review v0 (C2) -- deterministic builders.

Assembles a deeply immutable ``GeneratedImageCandidate`` and a
``GeneratedImageReview`` from explicitly caller-supplied inputs. This module
performs NO provider, LLM, or media operations, never accesses
OPENAI_API_KEY, never writes Canon, never mutates any upstream artifact, and
never promotes production eligibility.

Approval is human-only: the review decision is supplied explicitly by the
caller and the builder only validates and freezes it. It never scores a
visual, never approves autonomously, and never imports generated image bytes.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Union

from .errors import (
    GeneratedImageReviewValidationError,
    InvalidReviewDecisionError,
    ReviewCandidateMismatchError,
    UnsupportedImageFormatError,
)
from .hashing import compute_content_hash, validate_hex_sha256
from .model import (
    CANDIDATE_SCHEMA_VERSION,
    REVIEW_SCHEMA_VERSION,
    GeneratedImageCandidate,
    GeneratedImageReview,
    ReviewDecision,
    SUPPORTED_IMAGE_FORMATS,
)

# JPEG / JPG normalize to the identical canonical token ``JPEG``.
_IMAGE_FORMAT_NORMALIZED = {
    "PNG": "PNG",
    "JPEG": "JPEG",
    "JPG": "JPEG",
    "WEBP": "WEBP",
}

# A decision value is a ReviewDecision enum member OR its canonical string.
DecisionInput = Union[ReviewDecision, str]


def _require_non_empty(value: Optional[str], field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GeneratedImageReviewValidationError(
            f"{field} must be a non-empty string"
        )
    return value.strip()


def _coerce_decision(decision: DecisionInput) -> ReviewDecision:
    """Normalize an explicit caller-supplied decision to a canonical enum.

    Accepted inputs are a ReviewDecision member or the exact canonical string
    ("APPROVED" / "REJECTED"). Any other value fails closed.
    """
    if isinstance(decision, ReviewDecision):
        return decision
    if isinstance(decision, str):
        value = decision.strip()
        for member in ReviewDecision:
            if value == member.value:
                return member
    raise InvalidReviewDecisionError(
        f"invalid review decision {decision!r}; expected APPROVED or REJECTED"
    )


def _normalize_format(raw: str) -> str:
    if not isinstance(raw, str):
        raise UnsupportedImageFormatError(f"image_format must be a string, got {raw!r}")
    canonical = _IMAGE_FORMAT_NORMALIZED.get(raw.strip().upper())
    if canonical is None or canonical not in SUPPORTED_IMAGE_FORMATS:
        raise UnsupportedImageFormatError(
            f"unsupported image_format {raw!r}; expected one of "
            f"{sorted(SUPPORTED_IMAGE_FORMATS)}"
        )
    return canonical


def build_generated_image_candidate(
    *,
    source_media_item_id: str,
    image_sha256: str,
    image_format: str,
    image_byte_length: int,
    production_eligible: bool,
    source_prompt_item_hash: Optional[str] = None,
    provider: Optional[str] = None,
    provider_model_or_operation: Optional[str] = None,
) -> GeneratedImageCandidate:
    """Build an immutable generated-image candidate identity record.

    Fail-closed validation:
      - non-empty ``source_media_item_id``
      - valid 64-hex ``image_sha256`` (lowercased)
      - supported PNG/JPEG/WEBP format (JPEG/JPG normalize to ``JPEG``)
      - positive ``image_byte_length``
      - optional string fields are either None or non-empty strings

    ``production_eligible`` is preserved exactly as supplied and is NEVER
    promoted by C2.
    """
    source_media_item = _require_non_empty(
        source_media_item_id, "source_media_item_id"
    )
    try:
        digest = validate_hex_sha256(image_sha256)
    except ValueError as exc:
        raise GeneratedImageReviewValidationError(str(exc)) from exc
    fmt = _normalize_format(image_format)

    if isinstance(image_byte_length, bool) or not isinstance(image_byte_length, int):
        raise GeneratedImageReviewValidationError(
            f"image_byte_length must be an integer, got {image_byte_length!r}"
        )
    if image_byte_length <= 0:
        raise GeneratedImageReviewValidationError(
            f"image_byte_length must be positive, got {image_byte_length!r}"
        )

    prompt_hash = None
    if source_prompt_item_hash is not None:
        prompt_hash = _require_non_empty(
            source_prompt_item_hash, "source_prompt_item_hash"
        )

    provider_value = None
    if provider is not None:
        provider_value = _require_non_empty(provider, "provider")
    provider_model = None
    if provider_model_or_operation is not None:
        provider_model = _require_non_empty(
            provider_model_or_operation, "provider_model_or_operation"
        )

    provisional = GeneratedImageCandidate(
        schema_version=CANDIDATE_SCHEMA_VERSION,
        source_media_item_id=source_media_item,
        image_sha256=digest,
        image_format=fmt,
        image_byte_length=image_byte_length,
        content_hash="",
        production_eligible=production_eligible,
        source_prompt_item_hash=prompt_hash,
        provider=provider_value,
        provider_model_or_operation=provider_model,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def build_generated_image_review(
    *,
    review_id: str,
    candidate: GeneratedImageCandidate,
    decision: DecisionInput,
    note: Optional[str] = None,
    reviewer_id: Optional[str] = None,
) -> GeneratedImageReview:
    """Build an immutable human review decision bound to ``candidate``.

    The caller supplies the decision explicitly (human-only approval
    invariant). The builder validates that the decision is APPROVED or
    REJECTED, that ``review_id`` is non-empty, and binds the review to the
    candidate's exact ``content_hash``.

    This builder NEVER mutates the candidate, NEVER modifies production
    eligibility, NEVER creates an Asset Registry entry, and NEVER imports or
    copies image bytes.
    """
    review = _require_non_empty(review_id, "review_id")
    resolved = _coerce_decision(decision)

    note_value = None
    if note is not None:
        if not isinstance(note, str):
            raise GeneratedImageReviewValidationError("note must be a string")
        note_value = note
    reviewer_value = None
    if reviewer_id is not None:
        reviewer_value = _require_non_empty(reviewer_id, "reviewer_id")

    provisional = GeneratedImageReview(
        schema_version=REVIEW_SCHEMA_VERSION,
        review_id=review,
        candidate_content_hash=candidate.content_hash,
        decision=resolved,
        content_hash="",
        note=note_value,
        reviewer_id=reviewer_value,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def verify_review_matches_candidate(
    review: GeneratedImageReview,
    candidate: GeneratedImageCandidate,
) -> None:
    """Fail closed when a review does not bind the candidate's exact hash."""
    if review.candidate_content_hash != candidate.content_hash:
        raise ReviewCandidateMismatchError(
            f"review {review.review_id!r} candidate hash "
            f"{review.candidate_content_hash!r} does not match candidate "
            f"{candidate.content_hash!r}"
        )