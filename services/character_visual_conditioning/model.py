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
from typing import Any, Optional, Tuple

SET_SCHEMA_VERSION = "character_visual_reference_set/0.1"
REFERENCE_BUNDLE_SCHEMA_VERSION = "reference_bundle/0.1"

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


@dataclass(frozen=True)
class ReferenceEntry:
    """One resolved visual reference, owned by exactly one character.

    ``character_id`` is repeated on every entry (not only on the parent group)
    so flattening a bundle can never detach ownership. ``roles`` is the
    deterministic ordered tuple of frozen Canon role keys that reference this
    exact path. ``path`` is the safe repo-relative canonical path.
    ``payload`` is the actual validated binary bytes.
    """

    character_id: str
    roles: Tuple[str, ...]
    path: str
    image_format: str
    content_type: str
    sha256: str
    byte_length: int
    payload: bytes
    source_asset_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(self.roles))
        if self.source_asset_id is not None and (
            not isinstance(self.source_asset_id, str) or not self.source_asset_id
        ):
            raise ValueError("source_asset_id must be a non-empty string when present")

    def semantic_payload(self) -> dict[str, Any]:
        # Raw payload bytes never enter the hashed semantic payload; binary
        # identity is bound by sha256 + byte_length + format/content-type.
        # ``source_asset_id`` participates ONLY when present (Library entries);
        # Canon entries keep it None and omit the key entirely.
        payload: dict[str, Any] = {
            "character_id": self.character_id,
            "roles": list(self.roles),
            "path": self.path,
            "image_format": self.image_format,
            "content_type": self.content_type,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }
        if self.source_asset_id is not None:
            payload["source_asset_id"] = self.source_asset_id
        return payload

    def to_dict(self) -> dict[str, Any]:
        return self.semantic_payload()


@dataclass(frozen=True)
class ReferenceCharacterGroup:
    """Ordered references for exactly one frame character.

    ``status`` and ``canon_content_hash`` are the verbatim source snapshot
    status/identity and are preserved WITHOUT deriving independent production
    eligibility.
    """

    character_id: str
    references: Tuple[ReferenceEntry, ...]
    status: Optional[str] = None
    canon_content_hash: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))
        status_present = self.status is not None
        hash_present = self.canon_content_hash is not None
        if status_present != hash_present:
            raise ValueError(
                "status and canon_content_hash must be both present or both None"
            )
        if status_present:
            if not isinstance(self.status, str) or not self.status:
                raise ValueError("status must be a non-empty string")
            if not isinstance(self.canon_content_hash, str) or not self.canon_content_hash:
                raise ValueError("canon_content_hash must be a non-empty string")

    def semantic_payload(self) -> dict[str, Any]:
        # Canon groups emit status + canon_content_hash (exact legacy key order);
        # Library groups omit both entirely.
        payload: dict[str, Any] = {
            "character_id": self.character_id,
        }
        if self.status is not None:
            payload["status"] = self.status
        if self.canon_content_hash is not None:
            payload["canon_content_hash"] = self.canon_content_hash
        payload["references"] = [r.semantic_payload() for r in self.references]
        return payload

    def to_dict(self) -> dict[str, Any]:
        return self.semantic_payload()


@dataclass(frozen=True)
class ReferenceBundle:
    """Immutable provider-neutral visual-reference bundle for N characters.

    ``character_groups`` order is semantic and follows the supplied
    ``characters_in_frame`` order (never alphabetically re-sorted). No
    provider-specific fields are present.
    """

    schema_version: str
    character_groups: Tuple[ReferenceCharacterGroup, ...]
    content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "character_groups", tuple(self.character_groups))

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "character_groups": [g.semantic_payload() for g in self.character_groups],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "character_groups": [g.to_dict() for g in self.character_groups],
            "content_hash": self.content_hash,
        }
