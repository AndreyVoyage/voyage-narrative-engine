#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated Image Review v0 (C2) -- public API.

Exposes the deeply immutable ``GeneratedImageCandidate`` and
``GeneratedImageReview`` models plus the deterministic builders. This package
performs NO provider call, NO LLM call, NO media generation, never accesses
OPENAI_API_KEY, never writes Canon, never mutates any upstream artifact, and
never promotes production eligibility.

Approval is human-only: the review decision is supplied explicitly by the
caller and only validated/frozen by this package.
"""

from __future__ import annotations

from .builder import (
    build_generated_image_candidate,
    build_generated_image_review,
    verify_review_matches_candidate,
)
from .errors import (
    GeneratedImageReviewError,
    GeneratedImageReviewValidationError,
    InvalidReviewDecisionError,
    ReviewCandidateMismatchError,
    UnsupportedImageFormatError,
)
from .hashing import compute_content_hash
from .model import (
    CANDIDATE_SCHEMA_VERSION,
    REVIEW_SCHEMA_VERSION,
    SUPPORTED_IMAGE_FORMATS,
    GeneratedImageCandidate,
    GeneratedImageReview,
    ReviewDecision,
)

__all__ = [
    "build_generated_image_candidate",
    "build_generated_image_review",
    "verify_review_matches_candidate",
    "compute_content_hash",
    "GeneratedImageCandidate",
    "GeneratedImageReview",
    "ReviewDecision",
    "SUPPORTED_IMAGE_FORMATS",
    "CANDIDATE_SCHEMA_VERSION",
    "REVIEW_SCHEMA_VERSION",
    "GeneratedImageReviewError",
    "GeneratedImageReviewValidationError",
    "InvalidReviewDecisionError",
    "UnsupportedImageFormatError",
    "ReviewCandidateMismatchError",
]