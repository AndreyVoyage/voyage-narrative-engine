#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a validated, provider-neutral ``ReferenceBundle`` from the ACTIVE
Companion local snapshot.

Bytes come ONLY from ``<snapshot_dir>/references/`` -- never Character Canon,
never a filename guess. Every selected reference is fail-closed validated:
snapshot-relative safe path that resolves under the snapshot dir, file exists,
byte length matches the manifest, SHA-256 matches, magic-byte format matches the
declared file type, PNG/JPEG/WEBP only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Sequence

from ..character_import.local_snapshot import CharacterLocalSnapshot
from ..character_import.reference_importer import sniff_image_format
from ..character_import.reference_manifest import is_valid_relative_path
from .errors import ReferenceBundleError
from .reference_model import (
    FILE_TYPE_TO_CONTENT_TYPE,
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ReferenceBundle,
    ReferenceEntry,
)
from .reference_selection import select_reference_asset_ids

_FMT_KEY_TO_FILE_TYPE = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


def build_reference_bundle(
    *,
    snapshot: CharacterLocalSnapshot,
    snapshot_dir: Path,
    explicit_asset_ids: Optional[Sequence[str]] = None,
) -> ReferenceBundle:
    snapshot_dir = Path(snapshot_dir)
    root = snapshot_dir.resolve()
    by_id = {r.asset_id: r for r in snapshot.references}

    asset_ids = select_reference_asset_ids(snapshot, explicit_asset_ids=explicit_asset_ids)

    entries: list[ReferenceEntry] = []
    for aid in asset_ids:
        ref = by_id[aid]

        if not is_valid_relative_path(ref.relative_path):
            raise ReferenceBundleError(f"unsafe reference path for {aid!r}: {ref.relative_path!r}")
        full = (snapshot_dir / ref.relative_path).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            raise ReferenceBundleError(f"reference {aid!r} escapes the snapshot directory")
        if not full.is_file():
            raise ReferenceBundleError(f"reference file missing for {aid!r}: {ref.relative_path!r}")

        payload = full.read_bytes()
        if len(payload) != ref.byte_length:
            raise ReferenceBundleError(f"byte length mismatch for {aid!r}")
        from ..character_import.hashing import compute_sha256
        if compute_sha256(payload) != ref.sha256:
            raise ReferenceBundleError(f"sha256 mismatch for {aid!r}")
        fmt_key = sniff_image_format(payload)
        if fmt_key is None or _FMT_KEY_TO_FILE_TYPE[fmt_key] != ref.file_type:
            raise ReferenceBundleError(f"format mismatch for {aid!r}")
        content_type = FILE_TYPE_TO_CONTENT_TYPE.get(ref.file_type)
        if content_type is None:
            raise ReferenceBundleError(f"unsupported file type for {aid!r}: {ref.file_type!r}")

        entries.append(
            ReferenceEntry(
                character_id=snapshot.character_id,
                asset_id=ref.asset_id,
                roles=ref.roles,
                relative_path=ref.relative_path,
                sha256=ref.sha256,
                byte_length=ref.byte_length,
                image_format=ref.file_type,
                content_type=content_type,
                payload=payload,
                source_semantic_key=ref.source_semantic_key,
            )
        )

    bundle = ReferenceBundle(
        schema_version=REFERENCE_BUNDLE_SCHEMA_VERSION,
        character_id=snapshot.character_id,
        character_snapshot_version=snapshot.snapshot_version,
        references=tuple(entries),
        content_hash="",
    )
    object.__setattr__(bundle, "content_hash", bundle.compute_hash())
    return bundle


def validate_reference_bundle_integrity(bundle: ReferenceBundle) -> None:
    """Re-hash the semantic payload and fail closed on drift."""
    if bundle.compute_hash() != bundle.content_hash:
        raise ReferenceBundleError("reference bundle content hash mismatch")
    for e in bundle.references:
        if len(e.payload) != e.byte_length:
            raise ReferenceBundleError(f"payload length drift for {e.asset_id!r}")
        from ..character_import.hashing import compute_sha256
        if compute_sha256(e.payload) != e.sha256:
            raise ReferenceBundleError(f"payload sha drift for {e.asset_id!r}")
        if os.path.isabs(e.relative_path):
            raise ReferenceBundleError(f"reference path is absolute for {e.asset_id!r}")
