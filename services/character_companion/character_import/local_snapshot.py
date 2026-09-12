#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion-owned, versioned local visual-character snapshot.

A ``CharacterLocalSnapshot`` unifies, for ONE character and ONE version:

* the source Canon provenance + status + content hash it was imported from;
* the source reference-preset SHA-256;
* the imported reference assets (bytes copied into the snapshot ``references/``
  directory), each with role metadata, sha256, format and byte length;
* the normalized physical-identity record;
* an optional portrait / primary-identity reference pointer.

After import, normal Companion runtime reads ONLY this manifest + the local
``references/`` bytes. Character Canon is never touched again. Old versions are
never overwritten; an ``ACTIVE`` pointer selects the runtime version.

This module is Companion-owned (no VNE code copied here); it composes the
vendored canon-read / reference-import primitives.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

from .errors import (
    SnapshotNotFoundError,
    SnapshotOperationError,
    SnapshotValidationError,
)
from .hashing import compute_sha256, is_valid_sha256, sha256_hex
from .reference_importer import sniff_image_format
from .reference_manifest import is_valid_relative_path

SNAPSHOT_SCHEMA_VERSION = "companion_character_local_snapshot/0.1"
ACTIVE_FILENAME = "ACTIVE"
SNAPSHOT_MANIFEST_FILENAME = "manifest.json"
_VERSION_RE = re.compile(r"^v[1-9][0-9]*$")

_FORMAT_KEY_TO_FILE_TYPE = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}

#: bounded semantic roles derived from Canon reference keys (never from filenames)
KNOWN_ROLES = ("portrait", "face", "body", "expression", "motion")


def is_valid_version(value: Any) -> bool:
    return isinstance(value, str) and bool(_VERSION_RE.fullmatch(value))


@dataclass(frozen=True)
class SnapshotReference:
    asset_id: str
    roles: Tuple[str, ...]
    relative_path: str
    sha256: str
    file_type: str
    byte_length: int
    source_semantic_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", tuple(self.roles))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "assetId": self.asset_id,
            "roles": list(self.roles),
            "relativePath": self.relative_path,
            "sha256": self.sha256,
            "fileType": self.file_type,
            "byteLength": self.byte_length,
        }
        if self.source_semantic_key is not None:
            out["sourceSemanticKey"] = self.source_semantic_key
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "SnapshotReference":
        if not isinstance(data, dict):
            raise SnapshotValidationError("reference entry must be an object")
        try:
            return cls(
                asset_id=str(data["assetId"]),
                roles=tuple(str(r) for r in (data.get("roles") or ())),
                relative_path=str(data["relativePath"]),
                sha256=str(data["sha256"]),
                file_type=str(data["fileType"]),
                byte_length=int(data["byteLength"]),
                source_semantic_key=(
                    str(data["sourceSemanticKey"]) if data.get("sourceSemanticKey") is not None else None
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotValidationError(f"malformed reference entry: {exc}") from exc


@dataclass(frozen=True)
class PortraitRef:
    asset_id: str
    relative_path: str
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"assetId": self.asset_id, "relativePath": self.relative_path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, data: Any) -> "PortraitRef":
        if not isinstance(data, dict):
            raise SnapshotValidationError("portrait must be an object")
        try:
            return cls(str(data["assetId"]), str(data["relativePath"]), str(data["sha256"]))
        except (KeyError, TypeError) as exc:
            raise SnapshotValidationError(f"malformed portrait: {exc}") from exc


# ======================================================================
# Standing identity (V1F): optional, character-generic, whole-file Canon
# ``standing_identity`` sources pinned onto the local snapshot. Each source
# carries its exact decoded text plus the SHA-256 of that exact text (never a
# separately-normalized copy) so downstream consumers (prompt assembly,
# PinnedGenerationSpec) can verify nothing drifted since import.
# ======================================================================
#: bounded standing-identity categories, mirroring the Canon preset shape.
STANDING_IDENTITY_CATEGORIES = ("preservationRules", "negativeConstraints")


@dataclass(frozen=True)
class StandingIdentitySource:
    source_ref: str
    text: str
    text_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"sourceRef": self.source_ref, "text": self.text, "textSha256": self.text_sha256}

    @classmethod
    def from_dict(cls, data: Any) -> "StandingIdentitySource":
        if not isinstance(data, dict):
            raise SnapshotValidationError("standing identity source entry must be an object")
        try:
            return cls(
                source_ref=str(data["sourceRef"]),
                text=str(data["text"]),
                text_sha256=str(data["textSha256"]),
            )
        except (KeyError, TypeError) as exc:
            raise SnapshotValidationError(f"malformed standing identity source: {exc}") from exc


@dataclass(frozen=True)
class StandingIdentityCategory:
    """Ordered, non-empty tuple of pinned sources for one standing-identity
    category (``preservationRules`` or ``negativeConstraints``). Order is the
    Canon preset's ``source_refs`` list order -- never reordered."""

    sources: Tuple[StandingIdentitySource, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))

    def to_dict(self) -> dict[str, Any]:
        return {"sources": [s.to_dict() for s in self.sources]}

    @classmethod
    def from_dict(cls, data: Any) -> "StandingIdentityCategory":
        if not isinstance(data, dict):
            raise SnapshotValidationError("standing identity category must be an object")
        sources = data.get("sources")
        if not isinstance(sources, list):
            raise SnapshotValidationError("standing identity category sources must be an array")
        return cls(sources=tuple(StandingIdentitySource.from_dict(s) for s in sources))


@dataclass(frozen=True)
class StandingIdentity:
    """Character-generic container: either category may be absent (a Canon
    preset need not declare both). Never fabricated when the Canon preset
    omits a category -- absence here always means the preset omitted it."""

    preservation_rules: Optional[StandingIdentityCategory] = None
    negative_constraints: Optional[StandingIdentityCategory] = None

    def is_empty(self) -> bool:
        return self.preservation_rules is None and self.negative_constraints is None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.preservation_rules is not None:
            out["preservationRules"] = self.preservation_rules.to_dict()
        if self.negative_constraints is not None:
            out["negativeConstraints"] = self.negative_constraints.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "StandingIdentity":
        if not isinstance(data, dict):
            raise SnapshotValidationError("standingIdentity must be an object")
        pr = data.get("preservationRules")
        nc = data.get("negativeConstraints")
        return cls(
            preservation_rules=StandingIdentityCategory.from_dict(pr) if pr is not None else None,
            negative_constraints=StandingIdentityCategory.from_dict(nc) if nc is not None else None,
        )


@dataclass(frozen=True)
class CharacterLocalSnapshot:
    schema_version: str
    character_id: str
    snapshot_version: str
    source_canon: dict            # {sourceKind, sourceRef, contentHash, status, activeVersion?}
    source_preset_sha256: str
    imported_at: str
    references: Tuple[SnapshotReference, ...]
    physical: dict
    portrait: Optional[PortraitRef] = None
    snapshot_hash: str = ""
    standing_identity: Optional[StandingIdentity] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "references", tuple(self.references))

    # ---- deterministic identity (timestamp / envelope excluded) --------
    def semantic_payload(self) -> dict[str, Any]:
        refs = sorted(
            (
                {"assetId": r.asset_id, "roles": list(r.roles), "sha256": r.sha256,
                 "fileType": r.file_type, "byteLength": r.byte_length}
                for r in self.references
            ),
            key=lambda d: d["assetId"],
        )
        payload: dict[str, Any] = {
            "characterId": self.character_id,
            "sourceCanonCharacterId": self.source_canon.get("sourceCharacterId"),
            "sourceCanonContentHash": self.source_canon.get("contentHash"),
            "sourceCanonStatus": self.source_canon.get("status"),
            "sourcePresetSha256": self.source_preset_sha256,
            "references": refs,
            "physical": self.physical,
            "portraitAssetId": self.portrait.asset_id if self.portrait else None,
        }
        # Omitted entirely (not even as null) when absent, so a legacy snapshot
        # without standing_identity keeps its exact pre-V1F semantic payload and
        # therefore its exact pre-V1F hash. Only present + non-empty changes it.
        if self.standing_identity is not None and not self.standing_identity.is_empty():
            payload["standingIdentity"] = self.standing_identity.to_dict()
        return payload

    def compute_hash(self) -> str:
        return sha256_hex(self.semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "characterId": self.character_id,
            "snapshotVersion": self.snapshot_version,
            "sourceCanon": dict(self.source_canon),
            "sourcePresetSha256": self.source_preset_sha256,
            "importedAt": self.imported_at,
            "references": [r.to_dict() for r in self.references],
            "physical": self.physical,
            "portrait": self.portrait.to_dict() if self.portrait else None,
            "snapshotHash": self.snapshot_hash or self.compute_hash(),
        }
        if self.standing_identity is not None:
            out["standingIdentity"] = self.standing_identity.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "CharacterLocalSnapshot":
        if not isinstance(data, dict):
            raise SnapshotValidationError("snapshot manifest must be an object")
        try:
            portrait = data.get("portrait")
            standing_raw = data.get("standingIdentity")
            return cls(
                schema_version=str(data["schemaVersion"]),
                character_id=str(data["characterId"]),
                snapshot_version=str(data["snapshotVersion"]),
                source_canon=dict(data["sourceCanon"]),
                source_preset_sha256=str(data["sourcePresetSha256"]),
                imported_at=str(data["importedAt"]),
                references=tuple(SnapshotReference.from_dict(r) for r in data["references"]),
                physical=dict(data["physical"]),
                portrait=PortraitRef.from_dict(portrait) if portrait else None,
                snapshot_hash=str(data.get("snapshotHash") or ""),
                standing_identity=StandingIdentity.from_dict(standing_raw) if standing_raw else None,
            )
        except (KeyError, TypeError) as exc:
            raise SnapshotValidationError(f"malformed snapshot manifest: {exc}") from exc


# ======================================================================
# On-disk store:  <data_root>/characters/<id>/snapshots/<vN>/{manifest.json, references/}
#                 <data_root>/characters/<id>/snapshots/ACTIVE
# ======================================================================
class SnapshotStore:
    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)

    def snapshots_dir(self, character_id: str) -> Path:
        return self._data_root / "characters" / character_id / "snapshots"

    def version_dir(self, character_id: str, version: str) -> Path:
        if not is_valid_version(version):
            raise SnapshotOperationError(f"invalid snapshot version {version!r}")
        return self.snapshots_dir(character_id) / version

    def _active_path(self, character_id: str) -> Path:
        return self.snapshots_dir(character_id) / ACTIVE_FILENAME

    # ---- versions -----------------------------------------------------
    def list_versions(self, character_id: str) -> Tuple[str, ...]:
        root = self.snapshots_dir(character_id)
        if not root.is_dir():
            return ()
        versions = [p.name for p in root.iterdir() if p.is_dir() and is_valid_version(p.name)]
        return tuple(sorted(versions, key=lambda v: int(v[1:])))

    def next_version(self, character_id: str) -> str:
        existing = self.list_versions(character_id)
        return f"v{(int(existing[-1][1:]) + 1) if existing else 1}"

    # ---- ACTIVE pointer --------------------------------------------
    def read_active_version(self, character_id: str) -> Optional[str]:
        path = self._active_path(character_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SnapshotValidationError(f"ACTIVE pointer unreadable: {exc}") from exc
        if not is_valid_version(raw):
            raise SnapshotValidationError(f"ACTIVE pointer is not a valid version: {raw!r}")
        if not self.version_dir(character_id, raw).is_dir():
            raise SnapshotValidationError(f"ACTIVE points to a missing version: {raw!r}")
        return raw

    def write_active_version(self, character_id: str, version: str) -> None:
        if not self.version_dir(character_id, version).is_dir():
            raise SnapshotOperationError(f"cannot activate a missing version: {version!r}")
        path = self._active_path(character_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".active_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(version + "\n")
            os.replace(tmp, str(path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ---- read + validate ------------------------------------------
    def load_snapshot(self, character_id: str, version: str) -> CharacterLocalSnapshot:
        vdir = self.version_dir(character_id, version)
        manifest_path = vdir / SNAPSHOT_MANIFEST_FILENAME
        if not manifest_path.exists():
            raise SnapshotNotFoundError(f"no snapshot manifest for {character_id!r} {version!r}")
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SnapshotValidationError(f"snapshot manifest unreadable: {exc}") from exc
        snap = CharacterLocalSnapshot.from_dict(data)
        self._validate(character_id, version, vdir, snap)
        return snap

    def load_active_snapshot(self, character_id: str) -> CharacterLocalSnapshot:
        active = self.read_active_version(character_id)
        if active is None:
            raise SnapshotNotFoundError(f"no active local snapshot for {character_id!r}")
        return self.load_snapshot(character_id, active)

    def _validate(
        self, character_id: str, version: str, vdir: Path, snap: CharacterLocalSnapshot
    ) -> None:
        if snap.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise SnapshotValidationError(f"unexpected snapshot schema {snap.schema_version!r}")
        if snap.character_id != character_id:
            raise SnapshotValidationError("snapshot characterId does not match its directory")
        if snap.snapshot_version != version:
            raise SnapshotValidationError("snapshot snapshotVersion does not match its directory")
        if snap.snapshot_hash and snap.snapshot_hash != snap.compute_hash():
            raise SnapshotValidationError("snapshot hash does not match its content")

        by_id: dict[str, SnapshotReference] = {}
        for ref in snap.references:
            if not is_valid_relative_path(ref.relative_path):
                raise SnapshotValidationError(f"reference path escapes the snapshot: {ref.relative_path!r}")
            if not is_valid_sha256(ref.sha256):
                raise SnapshotValidationError(f"reference sha256 malformed for {ref.asset_id!r}")
            full = vdir / ref.relative_path
            if not full.is_file():
                raise SnapshotValidationError(f"referenced file missing: {ref.relative_path!r}")
            payload = full.read_bytes()
            if len(payload) != ref.byte_length:
                raise SnapshotValidationError(f"byte length mismatch for {ref.asset_id!r}")
            if compute_sha256(payload) != ref.sha256:
                raise SnapshotValidationError(f"sha256 mismatch for {ref.asset_id!r}")
            fmt = sniff_image_format(payload)
            if fmt is None or _FORMAT_KEY_TO_FILE_TYPE[fmt] != ref.file_type:
                raise SnapshotValidationError(f"format mismatch for {ref.asset_id!r}")
            for role in ref.roles:
                if role not in KNOWN_ROLES:
                    raise SnapshotValidationError(f"unknown reference role {role!r}")
            by_id[ref.asset_id] = ref

        if snap.portrait is not None:
            p = by_id.get(snap.portrait.asset_id)
            if p is None:
                raise SnapshotValidationError("portrait does not point to an imported reference")
            if p.sha256 != snap.portrait.sha256 or p.relative_path != snap.portrait.relative_path:
                raise SnapshotValidationError("portrait reference identity mismatch")

        if snap.standing_identity is not None:
            for category in (snap.standing_identity.preservation_rules, snap.standing_identity.negative_constraints):
                if category is None:
                    continue
                for source in category.sources:
                    if not is_valid_sha256(source.text_sha256):
                        raise SnapshotValidationError(
                            f"standing identity textSha256 malformed for {source.source_ref!r}"
                        )
                    if compute_sha256(source.text.encode("utf-8")) != source.text_sha256:
                        raise SnapshotValidationError(
                            f"standing identity text/hash mismatch for {source.source_ref!r}"
                        )
