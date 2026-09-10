"""Canonical immutable OrderedASS files; explicit root and identity, no discovery.

Полный envelope сохраняется один раз. Hard link публикует готовый sibling temp
атомарно и без замены существующего destination, в том числе при гонке writers.
Файловая система без hard links отклоняется; небезопасного fallback нет.
Store не устанавливает lifecycle и не определяет project authority.
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from services.scene_body import AUTHORING_SCHEMA_VERSION, SceneBody, SceneBodyError
from services.scene_body import validate_acceptance_complete

from .errors import (
    OrderedASSConflictError,
    OrderedASSIntegrityError,
    OrderedASSNotFoundError,
    OrderedASSStoreError,
)
from .hashing import compute_content_hash
from .model import LocationStateOverride, Participant, Provenance
from .ordered import ORDERED_ASS_SCHEMA_VERSION, SOURCE_KIND_ORDERED_ACCEPT, OrderedASS

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED = frozenset((
    "schema_version", "ass_id", "version", "scene_id", "location_id",
    "participants", "ordered_flow", "content_rating", "provenance", "content_hash",
))
_OPTIONAL = frozenset((
    "scene_title", "character_state_overrides", "location_state_overrides",
    "supersedes", "created_at", "author",
))


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrderedASSIntegrityError("expected non-blank string")
    return value


def _version(value: object) -> int:
    if type(value) is not int or value < 1:
        raise OrderedASSIntegrityError("version must be a positive integer")
    return value


def _hash(value: object) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise OrderedASSIntegrityError("expected lowercase SHA-256")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OrderedASSIntegrityError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise OrderedASSIntegrityError("non-finite JSON number")


def parse_ordered_ass(data: bytes) -> OrderedASS:
    """Строго разобрать полный envelope без потери неизвестных структурных полей.

    SceneBody используется только как временная проверка существующего словаря
    entry/value types. Round-trip полного envelope запрещает default-coercion,
    пропущенные structural keys и молчаливое отбрасывание данных.
    """
    try:
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
        if not isinstance(raw, dict) or not _REQUIRED <= raw.keys():
            raise OrderedASSIntegrityError("complete OrderedASS object required")
        if raw.keys() - (_REQUIRED | _OPTIONAL):
            raise OrderedASSIntegrityError("unknown OrderedASS fields")
        if raw["schema_version"] != ORDERED_ASS_SCHEMA_VERSION:
            raise OrderedASSIntegrityError("expected ass/0.2")
        provenance = raw["provenance"]
        if not isinstance(provenance, dict) or set(provenance) != {
            "source_kind", "source_ref", "source_hash", "source_schema_version"
        }:
            raise OrderedASSIntegrityError("invalid provenance structure")
        if (provenance["source_kind"] != SOURCE_KIND_ORDERED_ACCEPT
                or provenance["source_schema_version"] != AUTHORING_SCHEMA_VERSION):
            raise OrderedASSIntegrityError("unsupported acceptance provenance")
        for key in ("supersedes", "created_at", "author"):
            if key in raw and not isinstance(raw[key], str):
                raise OrderedASSIntegrityError("invalid optional envelope string")

        body = SceneBody.from_dict({
            "authoring_schema_version": AUTHORING_SCHEMA_VERSION,
            "scene_id": raw["scene_id"],
            "location_id": raw["location_id"],
            "participants": raw["participants"],
            "entries": raw["ordered_flow"],
            "content_rating": raw["content_rating"],
            "scene_title": raw.get("scene_title"),
            "character_state_overrides": raw.get("character_state_overrides"),
            "location_state_overrides": raw.get("location_state_overrides"),
        })
        if validate_acceptance_complete(body):
            raise OrderedASSIntegrityError("incomplete accepted content")
        overrides = body.character_state_overrides
        if overrides is not None:
            if any(not isinstance(value, Mapping) for value in overrides.values()):
                raise OrderedASSIntegrityError("invalid character override structure")

        result = OrderedASS(
            schema_version=ORDERED_ASS_SCHEMA_VERSION,
            ass_id=_text(raw["ass_id"]), version=_version(raw["version"]),
            scene_id=_text(body.scene_id), location_id=body.location_id,
            participants=tuple(Participant(p.character_id, p.role, p.present)
                               for p in body.participants),
            ordered_flow=body.entries, content_rating=body.content_rating,
            provenance=Provenance(
                source_kind=provenance["source_kind"],
                source_ref=_text(provenance["source_ref"]),
                source_hash=_hash(provenance["source_hash"]),
                source_schema_version=provenance["source_schema_version"],
            ),
            content_hash=_hash(raw["content_hash"]), scene_title=body.scene_title,
            character_state_overrides=body.character_state_overrides,
            location_state_overrides=(None if body.location_state_overrides is None else
                tuple(LocationStateOverride(o.predicate, o.value)
                      for o in body.location_state_overrides)),
            supersedes=raw.get("supersedes"), created_at=raw.get("created_at"),
            author=raw.get("author"),
        )
        # Сравнение JSON различает bool/int и пропущенные structural keys.
        if _json_bytes(result.to_dict()) != _json_bytes(raw):
            raise OrderedASSIntegrityError("non-exact OrderedASS structure")
        if compute_content_hash(result.semantic_payload()) != result.content_hash:
            raise OrderedASSIntegrityError("semantic content_hash mismatch")
        return result
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError,
            RecursionError, SceneBodyError):
        raise OrderedASSIntegrityError("invalid OrderedASS envelope") from None


def serialize_ordered_ass(scene: OrderedASS) -> bytes:
    """Полный проверенный envelope: UTF-8, sorted keys, indent=2, один LF."""
    if not isinstance(scene, OrderedASS):
        raise OrderedASSIntegrityError("expected OrderedASS")
    try:
        data = _json_bytes(scene.to_dict())
    except (ValueError, TypeError, AttributeError, UnicodeError, RecursionError):
        raise OrderedASSIntegrityError("invalid OrderedASS envelope") from None
    parse_ordered_ass(data)
    return data


class OrderedASSStore:
    """Immutable storage с явным абсолютным root; без latest и сканирования.

    Гарантии относятся к операциям store в принадлежащем приложению root.
    Прямая внешняя запись в canonical files не является разрешённой операцией.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        if not self._root.is_absolute():
            raise OrderedASSStoreError("explicit absolute store root required")

    def path_for(self, *, scene_id: str, version: int) -> Path:
        try:
            token = base64.b32encode(_text(scene_id).encode("utf-8"))
        except UnicodeError:
            raise OrderedASSIntegrityError("scene_id must be UTF-8 encodable") from None
        return (self._root / "scenes" / token.decode("ascii").lower().rstrip("=")
                / "versions" / f"{_version(version)}.json")

    def _read(self, *, scene_id: str, version: int) -> tuple[OrderedASS, bytes]:
        path = self.path_for(scene_id=scene_id, version=version)
        try:
            if path.is_symlink():
                raise OrderedASSIntegrityError("canonical file must not be a symlink")
            data = path.read_bytes()
        except FileNotFoundError:
            raise OrderedASSNotFoundError("OrderedASS scene/version not found") from None
        except OSError:
            raise OrderedASSStoreError("cannot read canonical ASS") from None
        result = parse_ordered_ass(data)
        if result.scene_id != scene_id or result.version != version:
            raise OrderedASSIntegrityError("stored scene_id/version mismatch")
        if data != _json_bytes(result.to_dict()):
            raise OrderedASSIntegrityError("non-canonical file bytes")
        return result, data

    def load(
        self, *, scene_id: str, version: int,
        expected_ass_id: str | None = None,
        expected_content_hash: str | None = None,
    ) -> OrderedASS:
        result, _ = self._read(scene_id=scene_id, version=version)
        if expected_ass_id is not None and result.ass_id != expected_ass_id:
            raise OrderedASSIntegrityError("ass_id mismatch")
        if expected_content_hash is not None and result.content_hash != expected_content_hash:
            raise OrderedASSIntegrityError("expected content_hash mismatch")
        return result

    def _existing(self, scene: OrderedASS, data: bytes) -> OrderedASS:
        result, existing = self._read(scene_id=scene.scene_id, version=scene.version)
        if existing != data:
            raise OrderedASSConflictError("scene/version has a different complete envelope")
        return result

    def save(self, scene: OrderedASS) -> OrderedASS:
        data = serialize_ordered_ass(scene)
        path = self.path_for(scene_id=scene.scene_id, version=scene.version)
        tmp: str | None = None
        try:
            if path.exists() or path.is_symlink():
                return self._existing(scene, data)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ordered_ass_", suffix=".tmp")
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if Path(tmp).read_bytes() != data:
                raise OrderedASSIntegrityError("staged ASS bytes mismatch")
            try:
                # Атомарная публикация без замены файла победившего writer.
                os.link(tmp, path)
            except FileExistsError:
                return self._existing(scene, data)
            return self.load(scene_id=scene.scene_id, version=scene.version,
                             expected_ass_id=scene.ass_id,
                             expected_content_hash=scene.content_hash)
        except OSError:
            raise OrderedASSStoreError("cannot publish canonical ASS") from None
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
