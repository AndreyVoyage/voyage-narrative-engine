#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated Image Review v0 (C2) -- plain-data models.

Deeply immutable, stdlib-only. Reuses the proven ASS / Scene Interpretation
immutability pattern: frozen dataclasses holding only detached plain data.

Two distinct artifacts:

- ``GeneratedImageCandidate`` -- an immutable evidence/provenance record that
  identifies one exact generated-image result. It never carries image bytes,
  API keys, or absolute machine paths.
- ``GeneratedImageReview`` -- an immutable human review decision bound to the
  exact ``content_hash`` of a candidate. A change of human decision is
  represented by constructing a NEW review artifact; an existing
  APPROVED/REJECTED review is never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReviewDecision(Enum):
    """The only two C2 v0 review decisions.

    An APPROVED decision means only that a human review artifact approved this
    generated-image candidate for the next authorized workflow stage. It does
    NOT mean production asset, Asset Registry entry, runtime attachment, or
    Canon update.
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# Canonical image formats accepted by C2 v0. Aligned with the repository's
# existing safe-image policy (PNG / JPEG / WEBP). JPEG and JPG normalize to the
# identical canonical token ``JPEG``.
SUPPORTED_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})

CANDIDATE_SCHEMA_VERSION = "generated_image_candidate/0.1"
REVIEW_SCHEMA_VERSION = "generated_image_review/0.1"


@dataclass(frozen=True)
class GeneratedImageCandidate:
    """Immutable identity for one generated-image result.

    Binds the exact source media item, the source prompt-item hash (when the
    caller can supply it), the image SHA-256, format, byte length, optional
    provider/model provenance, and the upstream ``production_eligible`` value.
    ``production_eligible`` is preserved verbatim and is NEVER promoted by C2.

    No generated image bytes, API keys, or absolute machine paths are stored.
    """

    schema_version: str
    source_media_item_id: str
    image_sha256: str
    image_format: str
    image_byte_length: int
    content_hash: str
    production_eligible: bool
    source_prompt_item_hash: Optional[str] = None
    provider: Optional[str] = None
    provider_model_or_operation: Optional[str] = None

    def semantic_payload(self) -> dict:
        """Return exactly the hashed semantic payload (fresh plain data).

        The envelope fields (``schema_version`` and ``content_hash`` itself)
        are excluded. No machine-local absolute path is ever present.
        """
        return {
            "source_media_item_id": self.source_media_item_id,
            "source_prompt_item_hash": self.source_prompt_item_hash,
            "image_sha256": self.image_sha256,
            "image_format": self.image_format,
            "image_byte_length": self.image_byte_length,
            "provider": self.provider,
            "provider_model_or_operation": self.provider_model_or_operation,
            "production_eligible": self.production_eligible,
        }

    def to_dict(self) -> dict:
        """Return the full candidate envelope (fresh plain data)."""
        return {
            "schema_version": self.schema_version,
            **self.semantic_payload(),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class GeneratedImageReview:
    """Immutable human review decision over one candidate.

    The decision is an explicit caller-supplied human decision. Human-ness is
    a caller-contract / API-boundary invariant: this module refuses to invent
    reviewer identity or autonomous approval.

    A new decision over the same candidate is a NEW artifact; this dataclass is
    frozen and never mutated in place.
    """

    schema_version: str
    review_id: str
    candidate_content_hash: str
    decision: ReviewDecision
    content_hash: str
    note: Optional[str] = None
    reviewer_id: Optional[str] = None

    def semantic_payload(self) -> dict:
        """Return exactly the hashed semantic payload (fresh plain data).

        Excludes the envelope fields (``schema_version`` and ``content_hash``
        itself). ``decision`` is the canonical enum value string.
        """
        return {
            "review_id": self.review_id,
            "candidate_content_hash": self.candidate_content_hash,
            "decision": self.decision.value,
            "note": self.note,
            "reviewer_id": self.reviewer_id,
        }

    def to_dict(self) -> dict:
        """Return the full review envelope (fresh plain data)."""
        return {
            "schema_version": self.schema_version,
            **self.semantic_payload(),
            "content_hash": self.content_hash,
        }