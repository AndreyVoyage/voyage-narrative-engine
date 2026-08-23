#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for Generated Image Review v0 (C2).

The C2 review contract performs NO provider, LLM, or media operations. These
errors describe fail-closed validation of an explicitly caller-supplied human
review decision over a generated-image candidate.
"""

from __future__ import annotations


class GeneratedImageReviewError(Exception):
    """Root of the Generated Image Review exception hierarchy."""


class GeneratedImageReviewValidationError(GeneratedImageReviewError):
    """Raised when a candidate or review fails fail-closed validation."""


class UnsupportedImageFormatError(GeneratedImageReviewValidationError):
    """Raised when the candidate image format is not in the C2 v0 allowed set."""


class InvalidReviewDecisionError(GeneratedImageReviewValidationError):
    """Raised when the review decision is not APPROVED or REJECTED."""


class ReviewCandidateMismatchError(GeneratedImageReviewValidationError):
    """Raised when a review's candidate content hash does not match the candidate."""