#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Visual Reference Conditioning v0 (C3) -- deterministic selection.

Selects the exact ordered active visual references from a read-only
``CharacterCanonSnapshot``. The selector NEVER writes to Canon and NEVER
invents a role:

- Only the Canon ``active_canon`` references are selected. Canon exposes them
  via ``CanonReference(key, path)`` where ``key`` is the active role key
  (e.g. ``primary_face_reference``, ``face_canon``, ``expression_canon``,
  ``body_canon_a``). Scene-preset variants are exposed under ``scene:``-prefixed
  keys and are NOT active canonical references, so they are excluded.
- Duplicate paths are collapsed to the first occurrence (deterministic, keeps
  the canonical order).
- ``primary_face_reference`` is the face-identity authority and appears first
  in the Canon ``active_canon`` map.

The selection builds a provider-neutral, deeply immutable
``VisualReferenceSet`` whose semantic identity binds the reference portable
identifiers, roles, SHA-256, format, and byte length -- never an absolute
machine path.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from services.character_canon_bridge import (
    CanonReference,
    CharacterCanonSnapshot,
)

from .errors import ReferenceBinaryError, ReferenceSelectionError
from .hashing import compute_content_hash
from .model import (
    SET_SCHEMA_VERSION,
    VisualReference,
    VisualReferenceSet,
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_WEBP_PREFIX = b"RIFF"


def _format_from_bytes(payload: bytes) -> str:
    """Determine the canonical image format from magic bytes (fail closed)."""
    if payload.startswith(_PNG_SIGNATURE):
        return "PNG"
    if payload.startswith(_JPEG_SIGNATURE):
        return "JPEG"
    if len(payload) >= 12 and payload[:4] == _WEBP_PREFIX and payload[8:12] == b"WEBP":
        return "WEBP"
    raise ReferenceBinaryError("reference bytes do not match a supported image format")


def _active_references(snapshot: CharacterCanonSnapshot) -> list[CanonReference]:
    """Return the ordered active_canon references, collapsing duplicate paths."""
    result: list[CanonReference] = []
    seen_paths: set[str] = set()
    for ref in snapshot.references:
        # Scene-preset entries are operational variants, not active canonical
        # references for identity conditioning.
        if ref.key.startswith("scene:"):
            continue
        if ref.path in seen_paths:
            continue
        seen_paths.add(ref.path)
        result.append(ref)
    return result


def _read_reference_metadata(
    canon_root: Path,
    ref: CanonReference,
) -> tuple[str, str, int]:
    """Read one reference file (READ ONLY) and return (sha256, format, len)."""
    if not ref.path or ref.path.startswith("/") or ref.path.startswith("\\"):
        raise ReferenceBinaryError(f"unsafe reference path: {ref.path!r}")
    full = canon_root / ref.path
    if not full.exists():
        raise ReferenceBinaryError(f"reference file missing: {ref.path!r}")
    payload = full.read_bytes()
    if len(payload) == 0:
        raise ReferenceBinaryError(f"reference file empty: {ref.path!r}")
    fmt = _format_from_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return digest, fmt, len(payload)


def build_visual_reference_set(
    snapshot: CharacterCanonSnapshot,
    *,
    canon_root: Path,
    source_media_item_id: str,
    source_prompt_item_hash: str,
) -> VisualReferenceSet:
    """Build the immutable ordered visual-reference selection.

    ``canon_root`` is the explicit Character Canon root used to read reference
    bytes (read-only). ``source_media_item_id`` and ``source_prompt_item_hash``
    bind the selection to the exact generation input.

    The selection is deterministic: it preserves Canon ``active_canon`` order,
    drops ``scene:`` variants, and dedupes by path.
    """
    if not source_media_item_id or not source_media_item_id.strip():
        raise ReferenceSelectionError("source_media_item_id must be non-empty")
    if not source_prompt_item_hash or not source_prompt_item_hash.strip():
        raise ReferenceSelectionError("source_prompt_item_hash must be non-empty")

    active = _active_references(snapshot)
    if not active:
        raise ReferenceSelectionError(
            f"no active Canon references available for {snapshot.character_id!r}"
        )

    references: list[VisualReference] = []
    for ref in active:
        digest, fmt, length = _read_reference_metadata(canon_root, ref)
        references.append(
            VisualReference(
                reference_id=ref.key,
                role=ref.key,
                image_sha256=digest,
                image_format=fmt,
                image_byte_length=length,
                source_path=str(canon_root / ref.path),
            )
        )

    provisional = VisualReferenceSet(
        schema_version=SET_SCHEMA_VERSION,
        character_id=snapshot.character_id,
        canon_content_hash=snapshot.content_hash,
        source_media_item_id=source_media_item_id.strip(),
        source_prompt_item_hash=source_prompt_item_hash.strip(),
        references=tuple(references),
        content_hash="",
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def validate_reference_set_integrity(reference_set: VisualReferenceSet) -> None:
    """Re-hash the semantic payload and fail closed on mismatch."""
    computed = compute_content_hash(reference_set.semantic_payload())
    if computed != reference_set.content_hash:
        raise ReferenceSelectionError(
            "visual reference set content hash mismatch"
        )