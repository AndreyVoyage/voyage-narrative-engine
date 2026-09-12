#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion-owned controlled Character Canon import.

    Character Canon  --(explicit, read-only)-->  CharacterImportService
        -> Companion-owned versioned local snapshot  (<data_root>/characters/...)
        -> future generation reads ONLY the local snapshot

No automatic sync. Import and update are explicit operations. Canon is never
written. Old snapshot versions are retained; ``ADD`` activates v1, ``UPDATE``
creates the next version WITHOUT flipping ``ACTIVE`` (activation is explicit).

This module is Companion-owned orchestration; it composes the vendored
canon-read / physical-normalize / reference-import primitives in this package.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .canon_model import CanonReference, CharacterCanonSnapshot
from .canon_reader import read_character_canon, read_standing_identity
from .errors import CanonFormatError, SnapshotError, SnapshotOperationError
from .hashing import compute_sha256
from .local_snapshot import (
    KNOWN_ROLES,
    SNAPSHOT_SCHEMA_VERSION,
    CharacterLocalSnapshot,
    PortraitRef,
    SnapshotReference,
    SnapshotStore,
    is_valid_version,
)
from .physical import physical_profile_from_preset
from .reference_importer import import_reference

# import outcome statuses
IMPORTED = "IMPORTED"
UPDATED_NEW_VERSION = "UPDATED_NEW_VERSION"
NO_OP_UNCHANGED = "NO_OP_UNCHANGED"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _asset_id_from_key(key: str) -> str:
    """Deterministic safe path-segment asset id from a Canon reference key."""
    slug = _SLUG_RE.sub("_", key.strip().lower()).strip("_")
    return slug or "ref"


def _roles_for_key(key: str) -> Tuple[str, ...]:
    """Map a Canon reference KEY (never a filename) to bounded semantic roles."""
    k = key.lower()
    roles: set[str] = set()
    if "primary_face" in k or k == "primary_face_reference":
        roles.update({"portrait", "face"})
    elif "face" in k:
        roles.add("face")
    if "expression" in k:
        roles.add("expression")
    if "body" in k:
        roles.add("body")
    if "motion" in k:
        roles.add("motion")
    return tuple(r for r in KNOWN_ROLES if r in roles)


def _active_canon_references(snapshot: CharacterCanonSnapshot) -> list[CanonReference]:
    """The ordered ``active_canon`` references, dropping ``scene:`` variants and
    collapsing duplicate paths (first occurrence wins). Matches the proven VNE
    ``character_visual_conditioning`` selection rule."""
    out: list[CanonReference] = []
    seen: set[str] = set()
    for ref in snapshot.references:
        if ref.key.startswith("scene:"):
            continue
        if ref.path in seen:
            continue
        seen.add(ref.path)
        out.append(ref)
    return out


@dataclass(frozen=True)
class ImportResult:
    status: str                      # IMPORTED | UPDATED_NEW_VERSION | NO_OP_UNCHANGED
    character_id: str
    snapshot_version: str
    active_version: Optional[str]
    snapshot_hash: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "characterId": self.character_id,
            "snapshotVersion": self.snapshot_version,
            "activeVersion": self.active_version,
            "snapshotHash": self.snapshot_hash,
        }


class CharacterImportService:
    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._store = SnapshotStore(self._data_root)

    # ---- bounded reads --------------------------------------------
    def list_snapshot_versions(self, character_id: str) -> Tuple[str, ...]:
        return self._store.list_versions(character_id)

    def load_snapshot(self, character_id: str, version: str) -> CharacterLocalSnapshot:
        return self._store.load_snapshot(character_id, version)

    def load_active_snapshot(self, character_id: str) -> CharacterLocalSnapshot:
        return self._store.load_active_snapshot(character_id)

    def active_version(self, character_id: str) -> Optional[str]:
        return self._store.read_active_version(character_id)

    def activate_snapshot(self, character_id: str, version: str) -> str:
        """Explicitly make ``version`` the active runtime snapshot. Fails closed
        if the version does not exist or is invalid."""
        if not is_valid_version(version):
            raise SnapshotOperationError(f"invalid snapshot version {version!r}")
        # load_snapshot re-validates the whole version before we point ACTIVE at it
        try:
            self._store.load_snapshot(character_id, version)
        except SnapshotError as exc:
            raise SnapshotOperationError(
                f"cannot activate {version!r} for {character_id!r}: {exc}"
            ) from exc
        self._store.write_active_version(character_id, version)
        return version

    # ---- controlled import --------------------------------------
    def import_character(
        self,
        canon_root: Path,
        character_id: str,
        operation: str = "add",
        *,
        source_character_id: Optional[str] = None,
    ) -> ImportResult:
        """Import one character from Character Canon into a Companion-owned
        versioned local snapshot.

        ``character_id`` is the **Companion-local** stable identity: it alone
        controls the storage path ``<data_root>/characters/<character_id>/``,
        the persisted ``manifest.characterId`` / ``ReferenceRecord.character_id``,
        the ``SnapshotStore`` lookup key, and catalog discovery.

        ``source_character_id`` is the **exact Character Canon identity** used
        ONLY at the source boundary (``read_character_canon`` folder / preset
        filename / ``payload["character"]`` production gate). It is never derived
        by case-folding -- when omitted it defaults to ``character_id`` (the
        pre-mapping same-id behaviour). Pass e.g. ``character_id="kira",
        source_character_id="KIRA"`` for real KIRA.
        """
        if operation not in ("add", "update"):
            raise SnapshotOperationError("operation must be 'add' or 'update'")
        if source_character_id is None:
            source_character_id = character_id

        active = self._store.read_active_version(character_id)
        if operation == "add" and active is not None:
            raise SnapshotOperationError(
                "character already has an active local snapshot; use operation='update'"
            )
        if operation == "update" and active is None:
            raise SnapshotOperationError(
                "no existing local snapshot to update; use operation='add'"
            )

        canon_root = Path(canon_root)

        # 1. read Canon (production gate: APPROVED_AS_CANON only) -- READ ONLY.
        #    ONLY source_character_id crosses this boundary: exact folder, exact
        #    preset filename, exact payload["character"] check, no case folding.
        canon_snapshot = read_character_canon(canon_root, source_character_id, "production")

        preset_path = (
            canon_root / "AI_CHARACTERS" / source_character_id / "10_notes"
            / f"{source_character_id}_REFERENCE_PRESETS.json"
        )
        try:
            preset_bytes = preset_path.read_bytes()
        except OSError as exc:  # pragma: no cover - reader already proved it exists
            raise CanonFormatError(f"preset unreadable: {exc}") from exc
        source_preset_sha256 = compute_sha256(preset_bytes)
        preset_json = json.loads(preset_bytes.decode("utf-8"))
        physical = physical_profile_from_preset(
            preset_json, source_character_id, source_preset_sha256=source_preset_sha256
        )
        # V1F: optional, character-generic standing-identity bridge -- reads
        # ONLY the explicit source_refs the Canon preset declares; None when
        # the preset has no standing_identity section at all.
        standing_identity = read_standing_identity(canon_root, preset_json)

        # 2. NO-OP identity check for UPDATE (hashes, never timestamps)
        if operation == "update":
            current = self._store.load_snapshot(character_id, active)  # type: ignore[arg-type]
            if (
                current.source_canon.get("contentHash") == canon_snapshot.content_hash
                and current.source_preset_sha256 == source_preset_sha256
            ):
                return ImportResult(
                    status=NO_OP_UNCHANGED,
                    character_id=character_id,
                    snapshot_version=active,  # type: ignore[arg-type]
                    active_version=active,
                    snapshot_hash=current.snapshot_hash or current.compute_hash(),
                )

        # 3. stage the new version in an isolated dir, then atomic-rename it in
        version = self._store.next_version(character_id)
        snapshots_dir = self._store.snapshots_dir(character_id)
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        staging = snapshots_dir / f".staging-{uuid.uuid4().hex}"
        try:
            (staging / "references").mkdir(parents=True)
            ref_manifest = staging / "references.manifest.json"

            snap_refs: list[SnapshotReference] = []
            portrait: Optional[PortraitRef] = None
            for cref in _active_canon_references(canon_snapshot):
                asset_id = _asset_id_from_key(cref.key)
                res = import_reference(
                    canon_root / cref.path,
                    snapshot_dir=staging,
                    asset_id=asset_id,
                    character_id=character_id,
                    manifest_path=ref_manifest,
                    source_filename=Path(cref.path).name,
                )
                rec = res.record
                byte_length = (staging / rec.relative_path).stat().st_size
                roles = _roles_for_key(cref.key)
                snap_refs.append(
                    SnapshotReference(
                        asset_id=rec.asset_id,
                        roles=roles,
                        relative_path=rec.relative_path,
                        sha256=rec.sha256,
                        file_type=rec.file_type,
                        byte_length=byte_length,
                        source_semantic_key=cref.key,
                    )
                )
                if portrait is None and "portrait" in roles:
                    portrait = PortraitRef(rec.asset_id, rec.relative_path, rec.sha256)

            if portrait is None:
                for sr in snap_refs:
                    if "face" in sr.roles:
                        portrait = PortraitRef(sr.asset_id, sr.relative_path, sr.sha256)
                        break

            source_canon = {
                "sourceKind": canon_snapshot.provenance.source_kind,
                "sourceRef": canon_snapshot.provenance.source_ref,
                "sourceHash": canon_snapshot.provenance.source_hash,
                "contentHash": canon_snapshot.content_hash,
                "status": canon_snapshot.status,
                # exact Canon identity this snapshot was imported from; the
                # Companion-local characterId above may differ (e.g. "kira").
                "sourceCharacterId": source_character_id,
            }
            if canon_snapshot.active_version is not None:
                source_canon["activeVersion"] = canon_snapshot.active_version

            snap = CharacterLocalSnapshot(
                schema_version=SNAPSHOT_SCHEMA_VERSION,
                character_id=character_id,
                snapshot_version=version,
                source_canon=source_canon,
                source_preset_sha256=source_preset_sha256,
                imported_at=_utcnow(),
                references=tuple(snap_refs),
                physical=physical,
                portrait=portrait,
                standing_identity=standing_identity,
            )
            snap = dataclasses.replace(snap, snapshot_hash=snap.compute_hash())
            (staging / "manifest.json").write_text(
                json.dumps(snap.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            # atomic: staging dir -> snapshots/vN (target does not exist yet)
            os.replace(str(staging), str(self._store.version_dir(character_id, version)))
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        # 4. re-validate the sealed (not-yet-active) version, fail closed
        sealed = self._store.load_snapshot(character_id, version)

        # 5. activation policy
        if operation == "add":
            self._store.write_active_version(character_id, version)
            status = IMPORTED
        else:
            status = UPDATED_NEW_VERSION  # ACTIVE deliberately unchanged

        return ImportResult(
            status=status,
            character_id=character_id,
            snapshot_version=version,
            active_version=self._store.read_active_version(character_id),
            snapshot_hash=sealed.snapshot_hash or sealed.compute_hash(),
        )
