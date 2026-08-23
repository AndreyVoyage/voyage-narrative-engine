#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Visual Reference Conditioning v0 (C3) -- plain-data models.

Deeply immutable, stdlib-only. Mirrors the ASS / Scene Interpretation /
Generated Image Review pattern: frozen dataclasses holding detached plain data.

Two semantic artifacts:

- ``VisualReference`` -- one selected Canon visual reference. The portable
  semantic identity binds the Canon role/identifier, the image SHA-256, the
  normalized image format, and the byte length. The operational machine path
  is kept OUT of semantic identity and OUT of portable serialization.
- ``VisualReferenceSet`` -- the exact ordered selection of visual references
  bound to a generation input (source media item + PromptItem hash + Canon
  snapshot hash). The order of references is semantic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

SET_SCHEMA_VERSION = "character_visual_reference_set/0.1"

# Canonical image formats accepted as visual references (aligned with the
# repository safe-image policy). JPEG/JPG normalize to ``JPEG``.
SUPPORTED_REFERENCE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


@dataclass(frozen=True)
class VisualReference:
    """One immutable selected Canon visual reference.

    ``reference_id`` is the portable reference identifier (equal to the Canon
    role key in C3 v0). ``source_path`` is OPERATIONAL ONLY: it tells the
    provider transport where to read the bytes at execution time, and it is
    never part of ``semantic_payload()`` or ``to_dict()``.
    """

    reference_id: str
    role: str
    image_sha256: str
    image_format: str
    image_byte_length: int
    source_path: Optional[str] = None

    def semantic_payload(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "role": self.role,
            "image_sha256": self.image_sha256,
            "image_format": self.image_format,
            "image_byte_length": self.image_byte_length,
        }

    def to_dict(self) -> dict:
        return self.semantic_payload()


@dataclass(frozen=True)
class VisualReferenceSet:
    """The exact ordered visual-reference selection for one generation input.

    Proves provenance: ``character_id``, the Character Canon snapshot content
    hash, the source media item id, and the source PromptItem content hash.
    ``references`` order is semantic and part of the content hash.
    """

    schema_version: str
    character_id: str
    canon_content_hash: str
    source_media_item_id: str
    source_prompt_item_hash: str
    references: Tuple[VisualReference, ...]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))

    def semantic_payload(self) -> dict:
        return {
            "character_id": self.character_id,
            "canon_content_hash": self.canon_content_hash,
            "source_media_item_id": self.source_media_item_id,
            "source_prompt_item_hash": self.source_prompt_item_hash,
            "references": [r.semantic_payload() for r in self.references],
        }

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            **self.semantic_payload(),
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class ConditionedImage:
    """Immutable result of exactly one reference-conditioned image call."""

    payload: bytes
    payload_sha256: str
    content_type: str
    model: str

    def to_dict(self) -> dict:
        return {
            "payload_sha256": self.payload_sha256,
            "payload_byte_length": len(self.payload),
            "content_type": self.content_type,
            "model": self.model,
        }