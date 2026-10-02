#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scenario Authoring foundation (SE-1.4) -- portable ``.vscenario`` Project container.

This module implements the P1 technical candidate: a UI-independent, stdlib-only
portable package that captures one validated current logical Project snapshot and
round-trips it into a fresh W1 destination through the existing
``services.scenario_authoring`` ``ProjectStore``.

Container: a standard ZIP archive using the working extension ``.vscenario``.

Logical layout::

    manifest.json              # versioned P1 manifest (itself NOT a listed entry)
    project.json               # the authoritative W1 Project INDEX (on-disk bytes)
    cards/<card_id>.json       # one independent W1 Card snapshot per card
    media/<relative_path>      # authored local media bytes (one entry per path)

The manifest lists every content member (``project.json``, ``cards/*``, ``media/*``)
with its canonical relative path, byte size and SHA-256 hash, plus a
``media_mapping`` that records the authored ``relative_path`` -> package path
association so import writes media back to the authored location without
rewriting any authored data.

Media portability rules (no contract blocker):

- ``MediaReference.relative_path`` is a portable, project-relative path. Such
  media is resolved against the project root, its bytes are packaged, and on
  import it is written back to the same authored relative path under the fresh
  destination. The authored ``relative_path`` (and therefore
  ``Project.to_dict()``) is never mutated.
- ``MediaReference.asset_id`` is a stable external Visual Asset Registry
  reference, not a local file. It is preserved verbatim as authored metadata and
  is NOT copied (there are no local bytes to copy). Resolving it to bytes belongs
  to a later slice; this module never downloads media and never synthesizes
  substitutes.

Round-trip invariant: ``import_project(...).to_dict() == source_project.to_dict()``
and packaged ``relative_path`` media bytes equal the original bytes.

Archive security: imported packages are treated as untrusted input. Absolute
paths, drive-qualified paths, UNC paths, ``..`` traversal, backslash paths,
symlink members, duplicate (case-insensitive) members, unexpected members,
malformed JSON, unsupported versions, and hash/size mismatches are all rejected.
Extraction is streaming with finite limits on member count, per-member size,
total size and compression ratio; ``extractall`` is never used.

P1 is a TECHNICAL CANDIDATE pending Owner review; this is not a ratified
canonical acceptance schema.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from .errors import ScenarioAuthoringError
from .model import SCENARIO_AUTHORING_SCHEMA_VERSION, MediaReference, Project
from .persistence import (
    STORAGE_SCHEMA_VERSION,
    ProjectStore,
    ScenarioAuthoringStorageError,
)

# ---------------------------------------------------------------------------
# Format identity (TECHNICAL CANDIDATE -- not a ratified acceptance schema).
# ---------------------------------------------------------------------------

PACKAGE_EXTENSION = ".vscenario"
PACKAGE_FORMAT_NAMESPACE = "voyage.scenario_editor.scenario_project"
PACKAGE_FORMAT_VERSION = 1
PACKAGE_MANIFEST_SCHEMA_VERSION = "scenario_project_portable/0.1"

MANIFEST_ENTRY = "manifest.json"
PROJECT_ENTRY = "project.json"
CARDS_DIR = "cards"
MEDIA_DIR = "media"

# ---------------------------------------------------------------------------
# Archive security limits (documented, finite).
# ---------------------------------------------------------------------------

MAX_MEMBER_COUNT = 1024
MAX_MEMBER_SIZE = 64 * 1024 * 1024  # 64 MiB per uncompressed member
MAX_TOTAL_SIZE = 256 * 1024 * 1024  # 256 MiB total uncompressed content
MAX_COMPRESSION_RATIO = 1000  # reject pathological "zip bombs"

# Fixed, reproducible ZIP entry metadata (best-effort reproducibility; this does
# not promise byte-identical archives across compression-library versions).
_FIXED_ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_ZIP_READ_CHUNK = 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Exceptions (kept local so the ratified error hierarchy is not modified).
# ---------------------------------------------------------------------------


class PortableProjectError(ScenarioAuthoringError):
    """Root of the portable-project (``.vscenario``) error hierarchy."""


class PortableProjectExportError(PortableProjectError):
    """Export failed; no portable package was published."""


class PortableProjectValidationError(PortableProjectError):
    """A ``.vscenario`` package failed validation (untrusted input rejected)."""


class PortableProjectImportError(PortableProjectError):
    """Import failed; no Project was published to the destination."""


# ---------------------------------------------------------------------------
# Deterministic hashing / JSON (mirrors services/ass + scenario persistence).
# ---------------------------------------------------------------------------


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _canonical_json_bytes(payload: Any) -> bytes:
    return _canonical_json(payload).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_hash(payload: Any) -> str:
    return _sha256_hex(_canonical_json(payload).encode("utf-8"))


def _reject_duplicate_key(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PortableProjectValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PortableProjectValidationError(f"non-finite JSON number {value!r}")


def _parse_json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PortableProjectValidationError(f"{label} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_key,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise PortableProjectValidationError(f"{label} is not valid JSON") from exc


# ---------------------------------------------------------------------------
# Path safety (archive member names and authored relative paths).
# ---------------------------------------------------------------------------


def _is_safe_archive_path(value: Any) -> bool:
    """True for a portable, forward-slash, traversal-free relative archive path."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    if "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _is_safe_relative_path(value: Any) -> bool:
    """Mirror the model's portable relative-path rule for manifest validation."""
    return _is_safe_archive_path(value) if isinstance(value, str) else False


def _is_reserved_media_path(relative_path: str) -> bool:
    return (
        relative_path == PROJECT_ENTRY
        or relative_path == MANIFEST_ENTRY
        or relative_path.startswith(CARDS_DIR + "/")
    )


def _ensure_within(root: Path, path: Path) -> Path:
    resolved_root = os.path.abspath(os.path.normpath(str(root)))
    resolved_path = os.path.abspath(os.path.normpath(str(path)))
    if os.path.commonpath([resolved_root, resolved_path]) != resolved_root:
        raise PortableProjectImportError("derived path escapes the destination root")
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


# ---------------------------------------------------------------------------
# Media discovery (deterministic, ordered traversal of the authoring model).
# ---------------------------------------------------------------------------


def _iter_media_references(project: Project) -> Iterator[MediaReference]:
    for card in project.cards:
        for slide in card.slides:
            if slide.background is not None:
                yield slide.background
            for item in slide.content_items:
                if item.media is not None:
                    yield item.media
                if item.utterance is not None:
                    for portion in item.utterance.portions:
                        for override in portion.overrides:
                            if override.portrait is not None:
                                yield override.portrait


def _collect_relative_paths(project: Project) -> List[str]:
    seen: Dict[str, None] = {}
    for ref in _iter_media_references(project):
        if ref.relative_path is not None:
            seen[ref.relative_path] = None
    return sorted(seen)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportReport:
    """Result of a successful ``export_project`` call."""

    path: Path
    project_id: str
    project_hash: str
    entry_count: int
    media_count: int
    manifest: Dict[str, Any]


def _read_required_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PortableProjectExportError(f"{label} is missing or unreadable") from exc


def _read_media_bytes(path: Path, relative_path: str) -> bytes:
    if path.is_symlink():
        raise PortableProjectExportError(f"media {relative_path!r} is a symlink (rejected)")
    if not path.is_file():
        raise PortableProjectExportError(f"required media {relative_path!r} is missing")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PortableProjectExportError(f"required media {relative_path!r} is unreadable") from exc
    if size > MAX_MEMBER_SIZE:
        raise PortableProjectExportError(
            f"media {relative_path!r} exceeds {MAX_MEMBER_SIZE} bytes"
        )
    return _read_required_bytes(path, f"media {relative_path!r}")


def _write_zip_member(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def _build_archive(path: Path, manifest: Dict[str, Any], payloads: Dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_zip_member(zf, MANIFEST_ENTRY, _canonical_json_bytes(manifest))
        for entry in manifest["entries"]:
            _write_zip_member(zf, entry["path"], payloads[entry["path"]])


def _publish_archive(tmp_path: Path, destination_path: Path, *, overwrite: bool) -> None:
    """Publish the validated temporary archive to its final destination.

    Create-only (``overwrite=False``) uses an atomic hard-link as a no-clobber
    primitive: ``os.link`` fails with ``FileExistsError`` if the destination
    exists (including a destination that appears after validation), so no
    existing file is ever silently replaced and there is no check-then-replace
    race. ``overwrite=True`` explicitly authorizes atomic replacement via
    ``os.replace``.
    """
    if overwrite:
        os.replace(tmp_path, destination_path)
        return
    try:
        os.link(tmp_path, destination_path)
    except FileExistsError:
        raise PortableProjectExportError(
            "destination already exists (create-only export refused); "
            "pass overwrite=True to replace an existing destination"
        ) from None
    except OSError as exc:
        raise PortableProjectExportError(
            "cannot publish to destination (no-clobber publication failed)"
        ) from exc
    else:
        os.unlink(tmp_path)


def export_project(
    source_root: Any,
    destination_path: Any,
    *,
    media_source_root: Any = None,
    overwrite: bool = False,
) -> ExportReport:
    """Export one validated current W1 Project into a portable ``.vscenario``.

    ``source_root`` must contain a saved W1 Project (``ProjectStore.load()``).
    ``media_source_root`` defaults to ``source_root``; authored ``relative_path``
    media are resolved against it. The archive is written to a temporary sibling,
    validated, then published to ``destination_path``.

    Publication is CREATE-ONLY by default (``overwrite=False``): if
    ``destination_path`` already exists, export raises
    :class:`PortableProjectExportError` and leaves the existing file untouched.
    Publication uses a no-clobber primitive (an atomic hard-link), so a
    destination that appears after validation but before publication is still
    rejected rather than overwritten. Passing ``overwrite=True`` explicitly
    authorizes atomically replacing an existing regular destination file.
    """
    source_root = Path(source_root)
    destination_path = Path(destination_path)
    media_root = Path(media_source_root) if media_source_root is not None else source_root

    # 1. Load the complete, validated source Project via W1 persistence.
    try:
        project = ProjectStore(source_root).load()
    except ScenarioAuthoringStorageError as exc:
        raise PortableProjectExportError(f"cannot load source W1 project: {exc}") from exc

    # 2. Snapshot the authoritative W1 files (guaranteed consistent after load).
    payloads: Dict[str, bytes] = {
        PROJECT_ENTRY: _read_required_bytes(source_root / PROJECT_ENTRY, "project index")
    }
    for card in project.cards:
        payloads[f"{CARDS_DIR}/{card.card_id}.json"] = _read_required_bytes(
            source_root / CARDS_DIR / f"{card.card_id}.json", f"card {card.card_id!r}"
        )

    # 3. Resolve required local media safely (relative_path -> bytes).
    media_mapping: List[Dict[str, Any]] = []
    for relative_path in _collect_relative_paths(project):
        if _is_reserved_media_path(relative_path):
            raise PortableProjectExportError(
                f"media relative_path {relative_path!r} is reserved"
            )
        data = _read_media_bytes(media_root / Path(relative_path), relative_path)
        package_path = f"{MEDIA_DIR}/{relative_path}"
        payloads[package_path] = data
        media_mapping.append({"relative_path": relative_path, "package_path": package_path})

    # 4. Build the deterministic content inventory.
    entries: List[Dict[str, Any]] = [
        {
            "path": PROJECT_ENTRY,
            "size": len(payloads[PROJECT_ENTRY]),
            "sha256": _sha256_hex(payloads[PROJECT_ENTRY]),
        }
    ]
    for card in project.cards:
        path = f"{CARDS_DIR}/{card.card_id}.json"
        entries.append({"path": path, "size": len(payloads[path]), "sha256": _sha256_hex(payloads[path])})
    for mapping in media_mapping:
        path = mapping["package_path"]
        entries.append({"path": path, "size": len(payloads[path]), "sha256": _sha256_hex(payloads[path])})

    manifest: Dict[str, Any] = {
        "format_namespace": PACKAGE_FORMAT_NAMESPACE,
        "format_version": PACKAGE_FORMAT_VERSION,
        "manifest_schema_version": PACKAGE_MANIFEST_SCHEMA_VERSION,
        "project_id": project.project_id,
        "project_schema_version": project.schema_version,
        "storage_schema_version": STORAGE_SCHEMA_VERSION,
        "start_card_id": project.start_card_id,
        "project_hash": _content_hash(project.to_dict()),
        "entries": entries,
        "media_mapping": media_mapping,
    }

    # 5. Build to a temporary output, validate, then publish atomically.
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(destination_path.parent), prefix=".vscenario_", suffix=".tmp")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        _build_archive(tmp_path, manifest, payloads)
        validate_package(tmp_path)
        _publish_archive(tmp_path, destination_path, overwrite=overwrite)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return ExportReport(
        path=destination_path,
        project_id=manifest["project_id"],
        project_hash=manifest["project_hash"],
        entry_count=len(entries),
        media_count=len(media_mapping),
        manifest=manifest,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageSummary:
    """Result of a successful ``validate_package`` call."""

    manifest: Dict[str, Any]
    project_id: str
    project_hash: str
    entry_count: int
    total_uncompressed_size: int


def _require_entry_path_valid(path: str) -> None:
    if not _is_safe_archive_path(path):
        raise PortableProjectValidationError(f"unsafe manifest entry path {path!r}")
    if path == MANIFEST_ENTRY:
        raise PortableProjectValidationError("manifest must not list manifest.json as an entry")
    if path == PROJECT_ENTRY or path.startswith(CARDS_DIR + "/") or path.startswith(MEDIA_DIR + "/"):
        return
    raise PortableProjectValidationError(f"unrecognized manifest entry path {path!r}")


def _validate_manifest(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise PortableProjectValidationError("manifest must be a JSON object")
    if manifest.get("format_namespace") != PACKAGE_FORMAT_NAMESPACE:
        raise PortableProjectValidationError(
            f"unsupported format namespace {manifest.get('format_namespace')!r}"
        )
    if manifest.get("format_version") != PACKAGE_FORMAT_VERSION:
        raise PortableProjectValidationError(
            f"unsupported format version {manifest.get('format_version')!r}"
        )
    if manifest.get("manifest_schema_version") != PACKAGE_MANIFEST_SCHEMA_VERSION:
        raise PortableProjectValidationError(
            f"unsupported manifest schema version {manifest.get('manifest_schema_version')!r}"
        )
    for key in ("project_id", "project_schema_version", "storage_schema_version", "start_card_id", "project_hash"):
        if not isinstance(manifest.get(key), str) or manifest.get(key) == "":
            raise PortableProjectValidationError(f"manifest missing or invalid {key!r}")
    if manifest["project_schema_version"] != SCENARIO_AUTHORING_SCHEMA_VERSION:
        raise PortableProjectValidationError(
            f"unsupported project schema version {manifest['project_schema_version']!r}"
        )
    if manifest["storage_schema_version"] != STORAGE_SCHEMA_VERSION:
        raise PortableProjectValidationError(
            f"unsupported storage schema version {manifest['storage_schema_version']!r}"
        )
    if _SHA256_RE.fullmatch(manifest["project_hash"]) is None:
        raise PortableProjectValidationError("manifest project_hash is not a valid SHA-256 hex digest")

    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PortableProjectValidationError("manifest entries must be a non-empty array")
    if len(entries) > MAX_MEMBER_COUNT:
        raise PortableProjectValidationError(f"manifest declares too many entries ({len(entries)})")

    entry_by_path: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PortableProjectValidationError("manifest entry must be an object")
        path = entry.get("path")
        if not isinstance(path, str):
            raise PortableProjectValidationError("manifest entry missing path")
        _require_entry_path_valid(path)
        folded = path.casefold()
        if folded in entry_by_path:
            raise PortableProjectValidationError(f"duplicate manifest entry path {path!r}")
        size = entry.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise PortableProjectValidationError(f"manifest entry {path!r} has invalid size")
        if size > MAX_MEMBER_SIZE:
            raise PortableProjectValidationError(f"manifest entry {path!r} exceeds max member size")
        sha = entry.get("sha256")
        if not isinstance(sha, str) or _SHA256_RE.fullmatch(sha) is None:
            raise PortableProjectValidationError(f"manifest entry {path!r} has invalid sha256")
        entry_by_path[folded] = entry

    if PROJECT_ENTRY not in entry_by_path:
        raise PortableProjectValidationError("manifest is missing the project index entry")

    media = manifest.get("media_mapping", [])
    if not isinstance(media, list):
        raise PortableProjectValidationError("manifest media_mapping must be an array")

    mapping_rels: Dict[str, str] = {}
    mapping_pkgs: Dict[str, str] = {}
    for item in media:
        if not isinstance(item, dict):
            raise PortableProjectValidationError("media_mapping entry must be an object")
        rel = item.get("relative_path")
        pkg = item.get("package_path")
        if not _is_safe_relative_path(rel):
            raise PortableProjectValidationError(f"media_mapping has unsafe relative_path {rel!r}")
        if _is_reserved_media_path(rel):
            raise PortableProjectValidationError(f"media_mapping relative_path {rel!r} is reserved")
        if not isinstance(pkg, str) or not pkg.startswith(MEDIA_DIR + "/"):
            raise PortableProjectValidationError(f"media_mapping has invalid package_path {pkg!r}")
        folded_pkg = pkg.casefold()
        if folded_pkg not in entry_by_path:
            raise PortableProjectValidationError(f"media_mapping package_path {pkg!r} is not a declared entry")
        if rel in mapping_rels or folded_pkg in mapping_pkgs:
            raise PortableProjectValidationError("media_mapping has duplicate relative_path or package_path")
        mapping_rels[rel] = folded_pkg
        mapping_pkgs[folded_pkg] = rel

    media_entries = {p for p in entry_by_path if p.startswith(MEDIA_DIR + "/")}
    if media_entries != set(mapping_pkgs):
        raise PortableProjectValidationError(
            "media entries and media_mapping package paths do not correspond 1:1"
        )


def _read_member_bytes(zf: zipfile.ZipFile, info: zipfile.ZipInfo, max_bytes: int) -> bytes:
    chunks: List[bytes] = []
    total = 0
    with zf.open(info, "r") as fp:
        while True:
            chunk = fp.read(_ZIP_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise PortableProjectValidationError(
                    f"member {info.filename!r} decompresses beyond its declared size"
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _read_and_validate_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    try:
        info = zf.getinfo(MANIFEST_ENTRY)
    except KeyError:
        raise PortableProjectValidationError(f"missing {MANIFEST_ENTRY}") from None
    if _is_symlink(info):
        raise PortableProjectValidationError("manifest.json is a symlink (rejected)")
    if info.file_size > MAX_MEMBER_SIZE:
        raise PortableProjectValidationError("manifest.json exceeds max member size")
    data = _read_member_bytes(zf, info, MAX_MEMBER_SIZE)
    manifest = _parse_json_bytes(data, "manifest.json")
    _validate_manifest(manifest)
    return manifest


def _write_extracted(root: Path, name: str, data: bytes) -> None:
    target = _ensure_within(root, root / name)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".vscenario_extract_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, str(target))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _verify_zip(
    zf: zipfile.ZipFile,
    manifest: Dict[str, Any],
    extract_root: Optional[Path] = None,
) -> int:
    """Validate every member against the manifest (and optionally extract).

    Returns the total uncompressed size of the listed content entries.
    """
    infos = zf.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise PortableProjectValidationError(f"archive has too many members ({len(infos)})")

    entry_by_path: Dict[str, Dict[str, Any]] = {
        e["path"].casefold(): e for e in manifest["entries"]
    }
    remaining = set(entry_by_path)
    seen: set[str] = set()
    total_size = 0

    for info in infos:
        name = info.filename
        if not _is_safe_archive_path(name):
            raise PortableProjectValidationError(f"unsafe archive member path {name!r}")
        folded = name.casefold()
        if folded in seen:
            raise PortableProjectValidationError(f"duplicate archive member {name!r}")
        seen.add(folded)

        if name == MANIFEST_ENTRY:
            continue

        entry = entry_by_path.get(folded)
        if entry is None:
            raise PortableProjectValidationError(f"unexpected package member {name!r}")
        if _is_symlink(info):
            raise PortableProjectValidationError(f"symlink member {name!r} (rejected)")

        uncompressed = info.file_size
        if uncompressed > MAX_MEMBER_SIZE:
            raise PortableProjectValidationError(f"member {name!r} exceeds max member size")
        if info.compress_size > 0 and uncompressed > info.compress_size * MAX_COMPRESSION_RATIO:
            raise PortableProjectValidationError(f"member {name!r} exceeds max compression ratio")
        total_size += uncompressed
        if total_size > MAX_TOTAL_SIZE:
            raise PortableProjectValidationError("archive exceeds max total uncompressed size")

        if uncompressed != entry["size"]:
            raise PortableProjectValidationError(f"member {name!r} size does not match manifest")

        data = _read_member_bytes(zf, info, uncompressed)
        if _sha256_hex(data) != entry["sha256"]:
            raise PortableProjectValidationError(f"member {name!r} SHA-256 does not match manifest")

        if extract_root is not None:
            _write_extracted(extract_root, name, data)

        remaining.discard(folded)

    if remaining:
        raise PortableProjectValidationError(
            f"package is missing declared members: {sorted(remaining)}"
        )

    return total_size


def validate_package(package_path: Any) -> PackageSummary:
    """Validate a ``.vscenario`` package in full, without extracting to a destination."""
    package_path = Path(package_path)
    if not package_path.is_file():
        raise PortableProjectValidationError("package does not exist or is not a file")
    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            manifest = _read_and_validate_manifest(zf)
            total_size = _verify_zip(zf, manifest)
    except zipfile.BadZipFile as exc:
        raise PortableProjectValidationError("not a valid ZIP container") from exc
    return PackageSummary(
        manifest=manifest,
        project_id=manifest["project_id"],
        project_hash=manifest["project_hash"],
        entry_count=len(manifest["entries"]),
        total_uncompressed_size=total_size,
    )


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _require_fresh_destination(destination_root: Path) -> None:
    if destination_root.exists():
        if not destination_root.is_dir():
            raise PortableProjectImportError("destination exists and is not a directory")
        if any(destination_root.iterdir()):
            raise PortableProjectImportError(
                "destination directory is not empty (refusing to overwrite an existing project)"
            )


def _reconstruct(temp_root: Path, manifest: Dict[str, Any]) -> Project:
    try:
        project = ProjectStore(temp_root).load()
    except ScenarioAuthoringStorageError as exc:
        raise PortableProjectImportError(
            f"package does not reconstruct a valid W1 project: {exc}"
        ) from exc
    if _content_hash(project.to_dict()) != manifest["project_hash"]:
        raise PortableProjectImportError("package project content does not match manifest project_hash")
    return project


def _atomic_copy_file(root: Path, src: Path, dst: Path) -> None:
    _ensure_within(root, dst)
    data = src.read_bytes()
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), prefix=".vscenario_publish_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, str(dst))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _remove_empty_dirs(root: Path) -> None:
    for dirpath, dirnames, _ in os.walk(str(root), topdown=False):
        for d in dirnames:
            try:
                (Path(dirpath) / d).rmdir()
            except OSError:
                pass


def _publish(temp_root: Path, manifest: Dict[str, Any], destination_root: Path) -> None:
    created: List[Path] = []
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
        # Cards first, then media, then the authoritative index last (mirrors W1).
        for entry in manifest["entries"]:
            if entry["path"].startswith(CARDS_DIR + "/"):
                dst = destination_root / entry["path"]
                _atomic_copy_file(destination_root, temp_root / entry["path"], dst)
                created.append(dst)
        for item in manifest.get("media_mapping", []):
            dst = destination_root / item["relative_path"]
            _atomic_copy_file(destination_root, temp_root / item["package_path"], dst)
            created.append(dst)
        _atomic_copy_file(destination_root, temp_root / PROJECT_ENTRY, destination_root / PROJECT_ENTRY)
        created.append(destination_root / PROJECT_ENTRY)
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        _remove_empty_dirs(destination_root)
        raise


def import_project(package_path: Any, destination_root: Any) -> Project:
    """Import a validated ``.vscenario`` into a fresh destination and reopen it.

    Returns the reopened ``Project`` (equal to the original ``to_dict()``). The
    destination must be nonexistent or empty; an existing project is never
    overwritten. On any failure no partial project is left in the destination.
    """
    package_path = Path(package_path)
    destination_root = Path(destination_root)

    _require_fresh_destination(destination_root)

    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            manifest = _read_and_validate_manifest(zf)
            with tempfile.TemporaryDirectory(prefix=".vscenario_import_") as td:
                temp_root = Path(td)
                _verify_zip(zf, manifest, extract_root=temp_root)
                project = _reconstruct(temp_root, manifest)
                _publish(temp_root, manifest, destination_root)
    except zipfile.BadZipFile as exc:
        raise PortableProjectImportError("not a valid ZIP container") from exc

    reopened = ProjectStore(destination_root).load()
    if reopened.to_dict() != project.to_dict():
        raise PortableProjectImportError("published project does not match the reconstructed project")
    return reopened


__all__ = [
    "PACKAGE_EXTENSION",
    "PACKAGE_FORMAT_NAMESPACE",
    "PACKAGE_FORMAT_VERSION",
    "PACKAGE_MANIFEST_SCHEMA_VERSION",
    "ExportReport",
    "PackageSummary",
    "PortableProjectError",
    "PortableProjectExportError",
    "PortableProjectValidationError",
    "PortableProjectImportError",
    "export_project",
    "validate_package",
    "import_project",
]
