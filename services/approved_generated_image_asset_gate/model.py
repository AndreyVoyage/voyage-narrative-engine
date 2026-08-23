#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Approved Generated Image Asset Gate v0 (C4) -- plain-data models.

Deeply immutable, stdlib-only. The gate yields a deterministic
``AssetGateResult`` that answers: may this already-human-APPROVED
generated-image candidate proceed to production asset handling?

It NEVER mutates the candidate or review, NEVER promotes production
eligibility, and NEVER performs import/registry writes on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GateVerdict(Enum):
    """The two possible gate outcomes."""

    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


class BlockReason(Enum):
    """Concrete, deterministic block reasons (no invented future states)."""

    REVIEW_NOT_APPROVED = "REVIEW_NOT_APPROVED"
    REVIEW_CANDIDATE_MISMATCH = "REVIEW_CANDIDATE_MISMATCH"
    SOURCE_BINARY_MISMATCH = "SOURCE_BINARY_MISMATCH"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    UPSTREAM_PRODUCTION_INELIGIBLE = "UPSTREAM_PRODUCTION_INELIGIBLE"


SCHEMA_VERSION = "approved_generated_image_asset_gate/0.1"


@dataclass(frozen=True)
class AssetGateResult:
    """Immutable, deterministic gate evaluation result.

    ``reason`` is present only when ``verdict == BLOCKED``.
    """

    verdict: GateVerdict
    reason: Optional[BlockReason]
    candidate_content_hash: str
    review_content_hash: str

    def to_dict(self) -> dict:
        data = {
            "verdict": self.verdict.value,
            "reason": self.reason.value if self.reason is not None else None,
            "candidate_content_hash": self.candidate_content_hash,
            "review_content_hash": self.review_content_hash,
        }
        return data