#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic Reference Bundle v0 (provider-neutral, N-character).

Builds an immutable, ordered ``ReferenceBundle`` from already frozen
``CharacterCanonSnapshot`` objects (or their serialized snapshot form, e.g.
``CharacterAnchor.serialized_snapshot``), the ordered ``characters_in_frame``
list, an optional explicit scene-preset mapping, and an explicit
``canon_root``.

The builder NEVER re-reads Character Canon: it never calls
``read_character_canon`` and never re-opens ``*_REFERENCE_PRESETS.json``.
It performs ZERO provider calls and ZERO media generation.

Every resolved reference retains character ownership, its role(s), a safe
repo-relative canonical path, the detected image format/content-type, the
SHA-256 digest, the byte length, and the actual validated binary payload.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from services.character_canon_bridge import (
    CanonReference,
    CharacterCanonSnapshot,
    Provenance,
    SNAPSHOT_SCHEMA_VERSION,
)

from .errors import ReferenceBinaryError, ReferenceSelectionError
from .hashing import compute_content_hash
from .model import (
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ReferenceBundle,
    ReferenceCharacterGroup,
    ReferenceEntry,
)
from .selection import _format_from_bytes

_FORMAT_TO_CONTENT_TYPE = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}

_SCENE_KEY_PREFIX = "scene:"


def _validate_safe_relative_path(path: str) -> str:
    """Return the validated safe repo-relative path (fail closed).

    Accepts relative, forward-slash, traversal-free paths only. Backslashes are
    treated as separators (matching the existing Canon bridge semantics) and
    normalized to forward slashes for the canonical form.
    """
    if not isinstance(path, str) or not path:
        raise ReferenceBinaryError("reference path must be a non-empty string")
    if path.startswith("/") or path.startswith("\\"):
        raise ReferenceBinaryError(f"absolute reference path forbidden: {path!r}")
    if re.match(r"^[A-Za-z]:", path):
        raise ReferenceBinaryError(f"drive-qualified reference path forbidden: {path!r}")
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if any(p == ".." for p in parts):
        raise ReferenceBinaryError(f"traversing reference path forbidden: {path!r}")
    if any(p in ("", ".") for p in parts):
        raise ReferenceBinaryError(f"invalid reference path component in: {path!r}")
    return normalized


def snapshot_from_serialized(serialized: Mapping[str, Any]) -> CharacterCanonSnapshot:
    """Reconstruct a frozen snapshot from its serialized form (in-memory only).

    This is a pure deserialization of an already-frozen snapshot envelope (for
    example ``CharacterAnchor.serialized_snapshot``). It NEVER re-reads
    Character Canon and NEVER re-opens ``*_REFERENCE_PRESETS.json``.
    """
    raw_references = serialized.get("references", ())
    references = tuple(
        CanonReference(key=item["key"], path=item["path"]) for item in raw_references
    )

    provenance_raw = serialized.get("provenance") or {}
    provenance = Provenance(
        source_kind=provenance_raw.get(
            "source_kind", "character_canon_reference_presets"
        ),
        source_ref=provenance_raw.get("source_ref", ""),
        source_hash=provenance_raw.get("source_hash", ""),
    )

    return CharacterCanonSnapshot(
        schema_version=serialized.get("schema_version", SNAPSHOT_SCHEMA_VERSION),
        character_id=serialized["character_id"],
        status=serialized["status"],
        references=references,
        content_hash=serialized["content_hash"],
        provenance=provenance,
        active_version=serialized.get("active_version"),
    )


def _select_character_references(
    snapshot: CharacterCanonSnapshot,
    scene_preset: Optional[str],
) -> list[CanonReference]:
    """Select core (non-scene) refs, then requested scene-preset refs.

    Core references keep frozen canonical order. Scene-preset references are
    included only when an explicit preset is requested and keep frozen order.
    A requested preset that has no matching ``scene:<preset>:*`` key fails
    closed (no silent fallback).
    """
    selected: list[CanonReference] = []
    for ref in snapshot.references:
        if ref.key.startswith(_SCENE_KEY_PREFIX):
            continue
        selected.append(ref)

    if scene_preset is not None:
        prefix = f"{_SCENE_KEY_PREFIX}{scene_preset}:"
        scene_refs = [r for r in snapshot.references if r.key.startswith(prefix)]
        if not scene_refs:
            raise ReferenceSelectionError(
                f"requested scene preset {scene_preset!r} not present for "
                f"{snapshot.character_id!r}"
            )
        selected.extend(scene_refs)

    return selected


def _read_reference_bytes(
    canon_root: Path,
    character_id: str,
    path: str,
) -> tuple[str, str, str, int, bytes]:
    """Read one validated safe-relative file (READ ONLY).

    Returns ``(format, content_type, sha256, byte_length, payload)``.
    Fails closed on missing, non-file, empty, or unsupported-magic-byte input.
    """
    full = canon_root / path
    if not full.exists():
        raise ReferenceBinaryError(
            f"reference file missing for {character_id!r}: {path!r}"
        )
    if not full.is_file():
        raise ReferenceBinaryError(
            f"reference path is not a file for {character_id!r}: {path!r}"
        )
    payload = full.read_bytes()
    if len(payload) == 0:
        raise ReferenceBinaryError(
            f"reference file empty for {character_id!r}: {path!r}"
        )
    fmt = _format_from_bytes(payload)
    content_type = _FORMAT_TO_CONTENT_TYPE[fmt]
    digest = hashlib.sha256(payload).hexdigest()
    return fmt, content_type, digest, len(payload), payload


def _build_character_group(
    snapshot: CharacterCanonSnapshot,
    selected: list[CanonReference],
    canon_root: Path,
) -> ReferenceCharacterGroup:
    """Resolve selected references into an ordered, ownership-bound group.

    Duplicate paths within the same character collapse to a single binary entry
    carrying all associated roles in deterministic frozen order. Paths are never
    deduplicated across different characters.
    """
    order: list[str] = []
    roles_by_path: dict[str, list[str]] = {}
    meta_by_path: dict[str, tuple] = {}

    for ref in selected:
        path = _validate_safe_relative_path(ref.path)
        if path not in roles_by_path:
            order.append(path)
            roles_by_path[path] = []
            meta_by_path[path] = _read_reference_bytes(
                canon_root, snapshot.character_id, path
            )
        roles_by_path[path].append(ref.key)

    entries: list[ReferenceEntry] = []
    for path in order:
        fmt, content_type, digest, length, payload = meta_by_path[path]
        entries.append(
            ReferenceEntry(
                character_id=snapshot.character_id,
                roles=tuple(roles_by_path[path]),
                path=path,
                image_format=fmt,
                content_type=content_type,
                sha256=digest,
                byte_length=length,
                payload=payload,
            )
        )

    return ReferenceCharacterGroup(
        character_id=snapshot.character_id,
        status=snapshot.status,
        canon_content_hash=snapshot.content_hash,
        references=tuple(entries),
    )


def build_reference_bundle(
    character_snapshots: Sequence[CharacterCanonSnapshot],
    *,
    characters_in_frame: Sequence[str],
    canon_root: Path,
    scene_preset_by_character: Optional[Mapping[str, str]] = None,
) -> ReferenceBundle:
    """Build the immutable provider-neutral N-character ReferenceBundle.

    Ordering is deterministic and semantic:

    1. character groups follow ``characters_in_frame`` order (never re-sorted);
    2. within each character, core references keep frozen canonical order;
    3. then requested scene-preset references keep frozen order.

    Fail-closed guarantees: any missing snapshot, duplicate frame character,
    missing scene preset, zero usable references, or unsafe/missing/empty/
    bad-format file raises immediately and NO partial bundle is returned.
    """
    frame = list(characters_in_frame)
    if not frame:
        raise ReferenceSelectionError("characters_in_frame must be non-empty")

    presets = dict(scene_preset_by_character or {})

    snapshots_by_id: dict[str, CharacterCanonSnapshot] = {}
    for snapshot in character_snapshots:
        cid = snapshot.character_id
        if cid in snapshots_by_id:
            raise ReferenceSelectionError(f"duplicate frozen snapshot for {cid!r}")
        snapshots_by_id[cid] = snapshot

    seen_frame: set[str] = set()
    groups: list[ReferenceCharacterGroup] = []
    for cid in frame:
        if cid in seen_frame:
            raise ReferenceSelectionError(f"duplicate character in frame: {cid!r}")
        seen_frame.add(cid)

        snapshot = snapshots_by_id.get(cid)
        if snapshot is None:
            raise ReferenceSelectionError(
                f"no frozen snapshot for frame character {cid!r}"
            )

        scene_preset = presets.get(cid)
        selected = _select_character_references(snapshot, scene_preset)
        if not selected:
            raise ReferenceSelectionError(
                f"no usable visual references for {cid!r}"
            )
        groups.append(_build_character_group(snapshot, selected, canon_root))

    provisional = ReferenceBundle(
        schema_version=REFERENCE_BUNDLE_SCHEMA_VERSION,
        character_groups=tuple(groups),
        content_hash="",
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def validate_reference_bundle_integrity(bundle: ReferenceBundle) -> None:
    """Re-hash the semantic payload and re-verify each payload's bytes.

    Fails closed on any content-hash mismatch, ownership mismatch, role loss,
    byte-length mismatch, SHA-256 mismatch, or format mismatch.
    """
    computed = compute_content_hash(bundle.semantic_payload())
    if computed != bundle.content_hash:
        raise ReferenceSelectionError("reference bundle content hash mismatch")

    for group in bundle.character_groups:
        for entry in group.references:
            if entry.character_id != group.character_id:
                raise ReferenceSelectionError(
                    "reference entry ownership does not match its group"
                )
            if not entry.roles:
                raise ReferenceSelectionError("reference entry has no roles")
            if entry.byte_length != len(entry.payload):
                raise ReferenceBinaryError("reference byte length mismatch")
            if hashlib.sha256(entry.payload).hexdigest() != entry.sha256:
                raise ReferenceBinaryError("reference sha256 mismatch")
            if _format_from_bytes(entry.payload) != entry.image_format:
                raise ReferenceBinaryError("reference image format mismatch")
