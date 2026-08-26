#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Approved Generated Image Asset Gate v0 (C4) -- deterministic gate.

Evaluates whether an already-human-APPROVED generated-image candidate may
proceed to production asset handling (Safe Import / Asset Registry).

Human APPROVED is necessary but NOT sufficient for production import. The
gate evaluates, in deterministic order:

  1. review decision must be APPROVED
  2. review must be bound to the candidate's exact content hash
  3. candidate image format must be supported (PNG/JPEG/WEBP)
  4. the actual source binary SHA-256 must match the candidate image SHA-256
  5. current upstream production eligibility must be True (never promoted here)

The gate performs NO mutation, NO provider/LLM/media I/O, NO Canon write,
and NO import/registry write. It returns a deterministic AssetGateResult.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from services.generated_image_review import (
    GeneratedImageCandidate,
    GeneratedImageReview,
    ReviewDecision,
    SUPPORTED_IMAGE_FORMATS,
)

from .errors import AssetGateConfigurationError
from .model import (
    AssetGateResult,
    BlockReason,
    GateVerdict,
)


def _actual_sha256_of_path(path: Path) -> str:
    if not path.exists():
        raise AssetGateConfigurationError(f"source file missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_asset_gate(
    candidate: GeneratedImageCandidate,
    review: GeneratedImageReview,
    *,
    current_upstream_production_eligible: bool,
    actual_source_sha256: str | None = None,
    actual_source_path: Path | None = None,
) -> AssetGateResult:
    """Evaluate the C4 production asset gate for a reviewed candidate.

    Exactly one of ``actual_source_sha256`` / ``actual_source_path`` must be
    provided to prove the real source binary matches the candidate. The source
    is only READ for hashing; it is never modified, copied, or imported.

    ``current_upstream_production_eligible`` is the CURRENT upstream production
    eligibility, passed independently at gate time (required, fail-closed). The
    candidate's own ``production_eligible`` field is historical generation-time
    provenance and is neither used as the current decision source nor promoted.
    """
    verdict = GateVerdict.ELIGIBLE
    reason: BlockReason | None = None

    if review.decision is not ReviewDecision.APPROVED:
        verdict = GateVerdict.BLOCKED
        reason = BlockReason.REVIEW_NOT_APPROVED

    elif review.candidate_content_hash != candidate.content_hash:
        verdict = GateVerdict.BLOCKED
        reason = BlockReason.REVIEW_CANDIDATE_MISMATCH

    elif candidate.image_format not in SUPPORTED_IMAGE_FORMATS:
        verdict = GateVerdict.BLOCKED
        reason = BlockReason.UNSUPPORTED_FORMAT

    else:
        if bool(actual_source_sha256) == bool(actual_source_path):
            raise AssetGateConfigurationError(
                "provide exactly one of actual_source_sha256 or actual_source_path"
            )
        if actual_source_sha256 is not None:
            actual = actual_source_sha256.strip().lower()
        else:
            actual = _actual_sha256_of_path(actual_source_path)

        if actual != candidate.image_sha256:
            verdict = GateVerdict.BLOCKED
            reason = BlockReason.SOURCE_BINARY_MISMATCH

        elif current_upstream_production_eligible is not True:
            verdict = GateVerdict.BLOCKED
            reason = BlockReason.UPSTREAM_PRODUCTION_INELIGIBLE

        # else remain ELIGIBLE

    return AssetGateResult(
        verdict=verdict,
        reason=reason,
        candidate_content_hash=candidate.content_hash,
        review_content_hash=review.content_hash,
    )