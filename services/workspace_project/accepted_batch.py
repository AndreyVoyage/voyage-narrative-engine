#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workspace / Domain Foundation v0 -- Accepted OrderedASS batch (references-only).

An ``AcceptedOrderedASSBatch`` is a small, frozen project production-selection
boundary: it pins exactly which already-accepted scenes are in the production
set for one project. It is REFERENCES ONLY -- it carries no OrderedASS body,
no ordered flow, no SceneBody, no character mappings, no Story Graph, and no
provider data. Canonical accepted-scene content remains owned by
``services.ass``; acceptance lifecycle remains owned by ``services.scene_draft``.

Resolution turns a batch plus a ``ProjectManifest``, an ``OrderedASSStore``, and
a ``SceneDraftStore`` into a ``tuple[OrderedASS, ...]`` in ascending raw
``scene_id``. It is strict, all-or-nothing, and read-only: it performs no
writes to the manifest, the ASS store, or the SceneDraft store.

This batch is replaceable PROJECT CONFIGURATION (not immutable canonical ASS
content), so its persistence uses the same explicit-path, sibling-temp,
``os.replace`` atomic-write house style as ``services/workspace_project/manifest.py``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.ass import OrderedASS, OrderedASSStore
from services.scene_draft import LIFECYCLE_ACCEPTED, SceneDraftStore

from .errors import WorkspaceProjectError
from .model import SCENE, PROJECT_ID_RE, ProjectManifest

ACCEPTED_BATCH_SCHEMA_VERSION = "vne_project_accepted_orderedass_batch/0.1"

_CONTENT_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


class AcceptedBatchError(WorkspaceProjectError):
    """Root of the accepted-batch exception hierarchy."""


class AcceptedBatchValidationError(AcceptedBatchError):
    """Raised when a batch or one of its refs is structurally unsound: a wrong
    schema, bad ``project_id``/``scene_id``/``version``/``ass_id``/``ass_content_hash``,
    a duplicate ``scene_id``/``ass_id``, an empty batch, or an unknown field."""


class AcceptedBatchNotFoundError(AcceptedBatchError):
    """Raised when the batch file does not exist at the requested path."""


class AcceptedBatchResolutionError(AcceptedBatchError):
    """Raised when a batch cannot be resolved: project mismatch, a selected
    scene is not a SCENE member of the project, or the accepted lifecycle /
    AcceptanceLink does not exactly agree with the pinned ref."""


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value == "":
        raise AcceptedBatchValidationError(f"{field}: required non-empty string")
    if value.strip() != value:
        raise AcceptedBatchValidationError(
            f"{field}: must not have leading/trailing whitespace"
        )
    return value


@dataclass(frozen=True)
class AcceptedOrderedASSRef:
    """One exact production pin: a scene, a version, and its ASS identity.

    References only -- never the OrderedASS body. ``version`` is an exact
    integer (``bool`` is rejected); ``ass_content_hash`` is an exact lowercase
    64-hex string. Caller identity values are never stripped or lowercased.
    """

    scene_id: str
    version: int
    ass_id: str
    ass_content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "scene_id", _require_non_empty_string(self.scene_id, "scene_id"))
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise AcceptedBatchValidationError("version: expected integer >= 1")
        object.__setattr__(self, "ass_id", _require_non_empty_string(self.ass_id, "ass_id"))
        hash_value = self.ass_content_hash
        if not isinstance(hash_value, str) or _CONTENT_HASH_RE.fullmatch(hash_value) is None:
            raise AcceptedBatchValidationError("ass_content_hash: expected 64 lowercase hex")
        object.__setattr__(self, "ass_content_hash", hash_value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "version": self.version,
            "ass_id": self.ass_id,
            "ass_content_hash": self.ass_content_hash,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AcceptedOrderedASSRef":
        if not isinstance(data, dict):
            raise AcceptedBatchValidationError("scene_ref must be an object")
        allowed = {"scene_id", "version", "ass_id", "ass_content_hash"}
        unknown = set(data) - allowed
        if unknown:
            raise AcceptedBatchValidationError(f"scene_ref: unknown field(s) {sorted(unknown)!r}")
        for field in ("scene_id", "version", "ass_id", "ass_content_hash"):
            if field not in data:
                raise AcceptedBatchValidationError(f"scene_ref.{field}: required field missing")
        return cls(
            scene_id=data["scene_id"],
            version=data["version"],
            ass_id=data["ass_id"],
            ass_content_hash=data["ass_content_hash"],
        )


@dataclass(frozen=True)
class AcceptedOrderedASSBatch:
    """The immutable, deterministic project production-selection boundary.

    ``scene_refs`` is non-empty, contains no duplicate ``scene_id`` or
    ``ass_id``, and is normalized to ascending raw ``scene_id`` (input order has
    no semantic meaning and the caller's tuple is never mutated).
    """

    schema_version: str
    project_id: str
    scene_refs: tuple[AcceptedOrderedASSRef, ...]

    def __post_init__(self) -> None:
        if self.schema_version != ACCEPTED_BATCH_SCHEMA_VERSION:
            raise AcceptedBatchValidationError(
                f"schema_version {self.schema_version!r} unsupported; "
                f"expected {ACCEPTED_BATCH_SCHEMA_VERSION!r}"
            )
        project_id = _require_non_empty_string(self.project_id, "project_id")
        if PROJECT_ID_RE.match(project_id) is None:
            raise AcceptedBatchValidationError(
                "project_id: expected lowercase slug [a-z][a-z0-9_]{2,63}"
            )
        object.__setattr__(self, "project_id", project_id)

        refs = tuple(self.scene_refs)
        if len(refs) == 0:
            raise AcceptedBatchValidationError("scene_refs: must be non-empty")

        seen_scene: dict[str, int] = {}
        seen_ass: dict[str, int] = {}
        for index, ref in enumerate(refs):
            if not isinstance(ref, AcceptedOrderedASSRef):
                raise AcceptedBatchValidationError(
                    f"scene_refs[{index}]: expected AcceptedOrderedASSRef"
                )
            if ref.scene_id in seen_scene:
                raise AcceptedBatchValidationError(
                    f"duplicate scene_id {ref.scene_id!r} (also at scene_refs[{seen_scene[ref.scene_id]}])"
                )
            if ref.ass_id in seen_ass:
                raise AcceptedBatchValidationError(
                    f"duplicate ass_id {ref.ass_id!r} (also at scene_refs[{seen_ass[ref.ass_id]}])"
                )
            seen_scene[ref.scene_id] = index
            seen_ass[ref.ass_id] = index

        object.__setattr__(self, "scene_refs", tuple(sorted(refs, key=lambda r: r.scene_id)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "scene_refs": [ref.to_dict() for ref in self.scene_refs],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "AcceptedOrderedASSBatch":
        if not isinstance(data, dict):
            raise AcceptedBatchValidationError("batch root must be an object")
        allowed = {"schema_version", "project_id", "scene_refs"}
        unknown = set(data) - allowed
        if unknown:
            raise AcceptedBatchValidationError(f"batch: unknown field(s) {sorted(unknown)!r}")
        for field in ("schema_version", "project_id", "scene_refs"):
            if field not in data:
                raise AcceptedBatchValidationError(f"{field}: required field missing")
        raw_refs = data["scene_refs"]
        if not isinstance(raw_refs, list):
            raise AcceptedBatchValidationError("scene_refs: expected an array")
        refs = tuple(AcceptedOrderedASSRef.from_dict(item) for item in raw_refs)
        return cls(
            schema_version=data["schema_version"],
            project_id=data["project_id"],
            scene_refs=refs,
        )


def serialize_accepted_batch(batch: AcceptedOrderedASSBatch) -> bytes:
    """Return deterministic UTF-8 JSON (fixed key order, sorted refs, one LF)."""
    if not isinstance(batch, AcceptedOrderedASSBatch):
        raise AcceptedBatchValidationError("expected AcceptedOrderedASSBatch")
    return (json.dumps(batch.to_dict(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AcceptedBatchValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise AcceptedBatchValidationError("non-finite JSON number")


def parse_accepted_batch(data: bytes) -> AcceptedOrderedASSBatch:
    """Strictly parse batch JSON bytes into a validated ``AcceptedOrderedASSBatch``.

    Rejects malformed JSON, non-object roots, wrong schema, duplicate JSON keys,
    non-finite numbers, and any unknown field. Caller identity values are never
    silently normalized.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise AcceptedBatchError("parse_accepted_batch: expected bytes")
    try:
        text = bytes(data).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AcceptedBatchError("batch is not valid UTF-8") from exc

    try:
        raw = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise AcceptedBatchError(f"batch is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise AcceptedBatchValidationError("batch root must be an object")
    if raw.get("schema_version") != ACCEPTED_BATCH_SCHEMA_VERSION:
        raise AcceptedBatchValidationError(
            f"schema_version: expected {ACCEPTED_BATCH_SCHEMA_VERSION!r}"
        )
    return AcceptedOrderedASSBatch.from_dict(raw)


def load_accepted_batch(path: Path) -> AcceptedOrderedASSBatch:
    """Load and validate the ``AcceptedOrderedASSBatch`` at the explicit ``path``."""
    path = Path(path)
    if not path.exists():
        raise AcceptedBatchNotFoundError(f"batch does not exist: {path.name}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AcceptedBatchError(f"cannot read batch: {exc}") from exc
    return parse_accepted_batch(data)


def save_accepted_batch(path: Path, batch: AcceptedOrderedASSBatch) -> None:
    """Atomically write the deterministic serialization to the explicit ``path``.

    Validates the complete batch before any filesystem mutation, then writes to a
    sibling temp file and ``os.replace``-s it into place (a reader never observes
    a partial write, and a prior valid batch is preserved byte-identically if the
    replacement fails). The existing target is trusted never and merged never: a
    malformed/old file at this path does not block a fully-valid replacement.
    """
    if not isinstance(batch, AcceptedOrderedASSBatch):
        raise AcceptedBatchValidationError("expected AcceptedOrderedASSBatch")
    data = serialize_accepted_batch(batch)
    parse_accepted_batch(data)  # validate the complete batch before mutation

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".workspace_project_batch_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def validate_accepted_batch(path: Path) -> list[str]:
    """Read-only structural validation; returns a list of error strings ([] = valid)."""
    path = Path(path)
    if not path.exists():
        return ["batch does not exist"]
    try:
        load_accepted_batch(path)
    except AcceptedBatchError as exc:
        return [str(exc)]
    return []


def resolve_accepted_ordered_ass_batch(
    batch: AcceptedOrderedASSBatch,
    *,
    project_manifest: ProjectManifest,
    ass_store: OrderedASSStore,
    scene_draft_store: SceneDraftStore,
) -> tuple[OrderedASS, ...]:
    """Resolve a batch into ``tuple[OrderedASS, ...]`` in ascending raw ``scene_id``.

    Strict and all-or-nothing: it requires an exact ``project_id`` match, exact
    SCENE membership for every ref, an exact canonical ASS load (identity +
    content hash), and an ACCEPTED SceneVersion whose AcceptanceLink exactly
    agrees with the ref and the loaded ASS. An orphan ASS (DRAFT / missing
    AcceptanceLink) is never production-authoritative. Resolution is read-only
    and mutates nothing.
    """
    if not isinstance(batch, AcceptedOrderedASSBatch):
        raise AcceptedBatchResolutionError("batch must be an AcceptedOrderedASSBatch")
    if not isinstance(project_manifest, ProjectManifest):
        raise AcceptedBatchResolutionError("project_manifest must be a ProjectManifest")
    if not isinstance(ass_store, OrderedASSStore):
        raise AcceptedBatchResolutionError("ass_store must be an OrderedASSStore")
    if not isinstance(scene_draft_store, SceneDraftStore):
        raise AcceptedBatchResolutionError("scene_draft_store must be a SceneDraftStore")

    if batch.project_id != project_manifest.project_id:
        raise AcceptedBatchResolutionError(
            f"batch project_id {batch.project_id!r} does not equal "
            f"manifest project_id {project_manifest.project_id!r}"
        )

    scene_members = {
        entity.stable_id for entity in project_manifest.entities
        if entity.entity_kind == SCENE
    }

    resolved: list[OrderedASS] = []
    for ref in batch.scene_refs:
        if ref.scene_id not in scene_members:
            raise AcceptedBatchResolutionError(
                f"scene {ref.scene_id!r} is not a SCENE member of the project"
            )

        loaded = ass_store.load(
            scene_id=ref.scene_id,
            version=ref.version,
            expected_ass_id=ref.ass_id,
            expected_content_hash=ref.ass_content_hash,
        )

        scene_version = scene_draft_store.read_version(ref.scene_id, ref.version)
        if scene_version.lifecycle != LIFECYCLE_ACCEPTED:
            raise AcceptedBatchResolutionError(
                f"scene {ref.scene_id!r} version {ref.version} is not ACCEPTED"
            )
        acceptance = scene_version.acceptance
        if acceptance is None:
            raise AcceptedBatchResolutionError(
                f"scene {ref.scene_id!r} version {ref.version} has no AcceptanceLink"
            )
        if acceptance.ass_id != ref.ass_id or acceptance.ass_id != loaded.ass_id:
            raise AcceptedBatchResolutionError(
                f"AcceptanceLink ass_id does not agree with ref/loaded ASS "
                f"for scene {ref.scene_id!r} version {ref.version}"
            )
        if (acceptance.ass_content_hash != ref.ass_content_hash
                or acceptance.ass_content_hash != loaded.content_hash):
            raise AcceptedBatchResolutionError(
                f"AcceptanceLink content hash does not agree with ref/loaded ASS "
                f"for scene {ref.scene_id!r} version {ref.version}"
            )

        resolved.append(loaded)

    return tuple(resolved)
