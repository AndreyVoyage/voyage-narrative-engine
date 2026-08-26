#!/usr/bin/env python3
"""Visual Asset Registry + Safe Import v0.

Stock-first, stdlib-only foundation for importing externally-authored
runtime-ready images into a controlled VNE asset tree and recording
deterministic metadata in a manifest.

Responsibilities (first slice only):
  - validate an external source image (existence, regular file, non-symlink,
    allowlisted extension, magic-byte signature, non-zero/bounded size)
  - validate asset_id / category / character_id
  - compute a controlled destination under novel/game/images/story/
  - COPY (never move) the source, verify SHA-256 integrity, register metadata
  - validate the registry (including orphan detection)
  - explicit update / re-import with failure-safe staged replacement and
    compensating rollback; no automatic synchronization

No Pillow, no scene JSON, no exporter, no Ren'Py runtime loader, no
character-canon dependency. Ren'Py remains responsible for actual runtime
image display in a later slice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ^[a-z][a-z0-9_]{2,63}$ — lowercase, starts with a letter, '_' separator,
# 3..64 characters, globally unique. Mirrors the existing lowercase
# character-id convention already present in scenario JSON ("kira", "sergey").
ASSET_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

V0_CATEGORIES = ("background", "character", "cg")
SOURCE_KINDS = ("character_canon", "manual", "unknown")

# v0 allowlist: PNG, WEBP, JPG/JPEG. jpg/jpeg canonicalise to a single
# destination extension ("jpg") so identical bytes always land on one path.
_EXT_ALIASES = {
    "png": "png",
    "webp": "webp",
    "jpg": "jpg",
    "jpeg": "jpg",
}
_MIME_BY_EXT = {
    "png": "image/png",
    "webp": "image/webp",
    "jpg": "image/jpeg",
}

# The approved controlled asset root, repo-root-relative, forward slashes.
STORY_ROOT = "novel/game/images/story"

# Generous but bounded max import size; adjustable without schema impact.
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MiB

# Fixed key order used for deterministic record serialization.
RECORD_KEY_ORDER = (
    "asset_id",
    "type",
    "relative_path",
    "source_kind",
    "source_character_id",
    "source_original_name",
    "source_hash",
    "imported_hash",
    "format",
    "mime_type",
    "created",
    "notes",
)

# Magic-byte signatures (stdlib sniffing only, no decode).
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8\xff"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _configure_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extension_of(name: str) -> str:
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def _canonical_ext(raw_ext: str) -> Optional[str]:
    return _EXT_ALIASES.get(raw_ext.lower())


def sniff_format(header: bytes) -> Optional[str]:
    """Return the canonical format of `header` (png/webp/jpg) or None."""
    if header.startswith(_PNG_SIG):
        return "png"
    if header.startswith(_JPEG_SIG):
        return "jpg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def _hash_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _safe_unlink(path: Optional[os.PathLike | str]) -> None:
    """Best-effort unlink; never raises. `None` is a no-op."""
    if path is None:
        return
    try:
        os.unlink(str(path))
    except OSError:
        pass


def _is_supported_asset_filename(name: str) -> bool:
    """True for a production asset filename (supported ext, not a staging
    artifact). Dot-prefixed temp/backup files are never asset files."""
    if name.startswith("."):
        return False
    return _canonical_ext(_extension_of(name)) is not None


def _is_safe_relative(relative_path: str) -> bool:
    """True if `relative_path` is relative, forward-slash, traversal-free."""
    if not relative_path:
        return False
    if relative_path.startswith("/") or relative_path.startswith("\\"):
        return False
    if re.match(r"^[A-Za-z]:", relative_path):
        return False
    parts = relative_path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if any(p in ("", ".") for p in parts):
        return False
    return True


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _ordered_record(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in RECORD_KEY_ORDER:
        value = record.get(key)
        if value is not None:
            out[key] = value
    return out


def serialize_registry(records: list[dict[str, Any]]) -> str:
    """Deterministic UTF-8 JSON: sorted by asset_id, fixed key order, LF+newline."""
    ordered = [
        _ordered_record(r)
        for r in sorted(records, key=lambda r: str(r.get("asset_id", "")))
    ]
    return json.dumps({"assets": ordered}, indent=2, ensure_ascii=False) + "\n"


def load_registry(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        raise ValueError("registry root must be an object with an 'assets' array")
    return data["assets"]


def lookup_asset(records: list[dict[str, Any]], asset_id: str) -> dict[str, Any]:
    """Read-only lookup of exactly one Registry record by ``asset_id``.

    Accepts already-loaded records and never loads, writes, or mutates the
    registry. Fails closed:

    - invalid asset_id per the v0 asset-id contract -> ValueError
    - zero matches -> ValueError (missing)
    - multiple matches -> ValueError (ambiguous)

    This is the generic Registry-side lookup helper used by integration-layer
    callers; the pure domain resolver performs its own selection with domain
    errors.
    """
    if not ASSET_ID_RE.match(asset_id or ""):
        raise ValueError("invalid asset_id {!r}".format(asset_id))
    matches = [r for r in records if r.get("asset_id") == asset_id]
    if not matches:
        raise ValueError("asset_id {} not found in registry".format(asset_id))
    if len(matches) > 1:
        raise ValueError(
            "asset_id {} has {} registry records (ambiguous)".format(asset_id, len(matches))
        )
    return matches[0]


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".reg_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(tmp, str(path))
    except BaseException:
        _safe_unlink(tmp)
        raise


def save_registry(registry_path: Path, records: list[dict[str, Any]]) -> None:
    _atomic_write_text(registry_path, serialize_registry(records))


def _stage_bytes(dest_dir: Path, data: bytes, prefix: str) -> str:
    """Write `data` to a controlled temp file in `dest_dir`; returns the temp
    path. Cleans up after itself and re-raises on failure."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest_dir), prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
    except BaseException:
        _safe_unlink(tmp)
        raise
    return tmp


def _atomic_copy_bytes(data: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".asset_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, str(dest))
    except BaseException:
        _safe_unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_source(source: Path):
    """Return (bytes, canonical_ext, mime, error). Error None on success."""
    if not source.exists():
        return None, None, None, "source does not exist"
    if not source.is_file():
        return None, None, None, "source is not a regular file"
    if source.is_symlink():
        return None, None, None, "symlinked source files are rejected"
    raw_ext = _extension_of(source.name)
    ext = _canonical_ext(raw_ext)
    if ext is None:
        return None, None, None, "unsupported extension {!r}".format(raw_ext)
    size = source.stat().st_size
    if size <= 0:
        return None, None, None, "source file is empty"
    if size > MAX_FILE_SIZE:
        return None, None, None, "source file exceeds maximum size"
    data = source.read_bytes()
    sniffed = sniff_format(data[:12])
    if sniffed != ext:
        return (
            None,
            None,
            None,
            "extension/signature mismatch: .{} but bytes are {}".format(
                raw_ext, sniffed or "unknown"
            ),
        )
    return data, ext, _MIME_BY_EXT[ext], None


def compute_relative_path(
    asset_id: str,
    asset_type: str,
    ext: str,
    character_id: Optional[str] = None,
) -> str:
    if asset_type == "background":
        return "{}/backgrounds/{}.{}".format(STORY_ROOT, asset_id, ext)
    if asset_type == "character":
        return "{}/characters/{}/{}.{}".format(STORY_ROOT, character_id, asset_id, ext)
    if asset_type == "cg":
        return "{}/cg/{}.{}".format(STORY_ROOT, asset_id, ext)
    raise ValueError("unknown asset type {!r}".format(asset_type))


def _classify_import(
    records: list[dict[str, Any]],
    asset_id: str,
    dest: Path,
    source_sha: str,
):
    """Classify an import against the existing registry and filesystem.

    Returns (action, message) where action is one of "IMPORT", "NO-OP",
    "REJECT" (message is the reason), or "IMPORT" with an alias warning.
    """
    by_id = {r.get("asset_id"): r for r in records}
    existing = by_id.get(asset_id)

    if existing is not None:
        if existing.get("imported_hash") == source_sha:
            return "NO-OP", "asset_id {} already registered with identical bytes".format(
                asset_id
            )
        return (
            "REJECT",
            "asset_id {} already exists with different bytes; use 'update'".format(
                asset_id
            ),
        )

    # Different-ID identical-bytes aliasing (case D) -> allowed with warning.
    alias = next(
        (r["asset_id"] for r in records if r.get("imported_hash") == source_sha),
        None,
    )

    if dest.exists():
        # Case E: physical destination exists but registry has no entry.
        return (
            "REJECT",
            "destination {} exists but registry has no entry".format(dest),
        )

    return "IMPORT", alias


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def import_asset(
    repo_root: Path,
    registry_path: Path,
    *,
    source_path: str,
    asset_id: str,
    asset_type: str,
    character_id: Optional[str] = None,
    source_kind: str = "unknown",
    notes: str = "",
    dry_run: bool = False,
) -> tuple[int, str]:
    if not ASSET_ID_RE.match(asset_id or ""):
        return 1, "invalid asset_id {!r}".format(asset_id)

    if asset_type not in V0_CATEGORIES:
        return 1, "invalid type {!r}".format(asset_type)

    if source_kind not in SOURCE_KINDS:
        return 1, "invalid source-kind {!r}".format(source_kind)

    if asset_type == "character":
        if not ASSET_ID_RE.match(character_id or ""):
            return 1, "type=character requires a valid --character-id"
    else:
        character_id = None

    source = Path(source_path)
    data, ext, mime, error = validate_source(source)
    if error:
        return 1, error
    source_sha = _sha256(data)

    rel = compute_relative_path(asset_id, asset_type, ext, character_id)
    if not _is_safe_relative(rel):
        return 1, "computed destination is not a safe relative path"
    dest = repo_root / rel
    if not _is_under(dest, repo_root / STORY_ROOT):
        return 1, "computed destination escapes the approved asset root"

    try:
        records = load_registry(registry_path)
    except Exception as exc:
        return 1, "failed to load registry: {}".format(exc)

    action, alias = _classify_import(records, asset_id, dest, source_sha)

    if action == "NO-OP":
        return 0, "NO-OP: {}".format(
            "asset_id {} unchanged (identical bytes)".format(asset_id)
        )
    if action == "REJECT":
        return 1, alias

    warning = None
    if alias is not None:
        warning = "WARN: {} has identical bytes to existing {} (aliasing)".format(
            asset_id, alias
        )

    if dry_run:
        if warning:
            print(warning)
        return 0, "DRY-RUN: would IMPORT {} -> {}".format(asset_id, rel)

    try:
        _atomic_copy_bytes(data, dest)
    except Exception as exc:
        return 1, "copy failed: {}".format(exc)

    dest_sha = _hash_file(dest)
    if dest_sha != source_sha:
        return 1, "hash mismatch after copy; import aborted"

    record: dict[str, Any] = {
        "asset_id": asset_id,
        "type": asset_type,
        "relative_path": rel,
        "source_kind": source_kind,
        "source_character_id": character_id,
        "source_original_name": source.name,
        "source_hash": source_sha,
        "imported_hash": dest_sha,
        "format": ext,
        "mime_type": mime,
        "created": _utcnow(),
        "notes": notes,
    }
    records.append(record)
    try:
        save_registry(registry_path, records)
    except Exception as exc:
        # Failure safety: remove only the destination this operation just
        # created (case E already guaranteed it did not pre-exist).
        _safe_unlink(dest)
        return 1, "registry write failed; newly copied asset removed: {}".format(exc)

    if warning:
        print(warning)
    return 0, "IMPORT {} -> {}".format(asset_id, rel)


def update_asset(
    repo_root: Path,
    registry_path: Path,
    *,
    asset_id: str,
    source_path: str,
    notes: Optional[str] = None,
    dry_run: bool = False,
) -> tuple[int, str]:
    if not ASSET_ID_RE.match(asset_id or ""):
        return 1, "invalid asset_id {!r}".format(asset_id)

    source = Path(source_path)
    data, ext, mime, error = validate_source(source)
    if error:
        return 1, error
    source_sha = _sha256(data)

    try:
        records = load_registry(registry_path)
    except Exception as exc:
        return 1, "failed to load registry: {}".format(exc)

    by_id = {r.get("asset_id"): r for r in records}
    existing = by_id.get(asset_id)
    if existing is None:
        return 1, "asset_id {} not found; use 'import'".format(asset_id)

    if existing.get("format") != ext:
        return 1, (
            "update source format ({}) differs from registered ({}); "
            "format changes require a new asset_id".format(ext, existing.get("format"))
        )

    if existing.get("imported_hash") == source_sha:
        return 0, "NO-OP: {} already has identical bytes".format(asset_id)

    dest = repo_root / existing["relative_path"]

    if dry_run:
        return 0, "DRY-RUN: would UPDATE {} from {}".format(
            asset_id, existing["relative_path"]
        )

    # Prepare the intended next registry state in memory and serialise it now,
    # so a serialization failure surfaces BEFORE any destination mutation.
    updated_record = dict(existing)
    updated_record["source_original_name"] = source.name
    updated_record["source_hash"] = source_sha
    updated_record["imported_hash"] = source_sha  # verified against dest below
    updated_record["format"] = ext
    updated_record["mime_type"] = mime
    updated_record["created"] = _utcnow()
    if notes is not None:
        updated_record["notes"] = notes
    next_records = [
        updated_record if r.get("asset_id") == asset_id else r for r in records
    ]
    try:
        serialize_registry(next_records)
    except Exception as exc:
        return 1, "failed to prepare intended registry state: {}".format(exc)

    # Failure-safe staged replacement with compensating rollback.
    stage_path: Optional[str] = None
    backup_path: Optional[str] = None
    try:
        stage_path = _stage_bytes(dest.parent, data, ".asset_new_")
        if _hash_file(Path(stage_path)) != source_sha:
            _safe_unlink(stage_path)
            stage_path = None
            return 1, "hash mismatch after staging new bytes; update aborted"

        # Recoverable backup of the existing LOCAL asset bytes (not the source).
        backup_path = _stage_bytes(dest.parent, dest.read_bytes(), ".asset_bak_")

        # Replace destination with the validated new bytes.
        os.replace(stage_path, str(dest))
        stage_path = None  # consumed

        try:
            save_registry(registry_path, next_records)
        except Exception as reg_exc:
            # Compensating rollback: restore the previous destination bytes.
            rollback_error: Optional[Exception] = None
            try:
                os.replace(backup_path, str(dest))
                backup_path = None  # consumed by restore
            except Exception as rb_exc:
                rollback_error = rb_exc

            _safe_unlink(stage_path)
            if rollback_error is None:
                _safe_unlink(backup_path)
                return 1, "registry write failed; update rolled back: {}".format(reg_exc)

            # Rollback failed: do not destroy the only recoverable copy.
            return 1, (
                "CRITICAL: registry write failed and rollback failed; "
                "registry error: {}; rollback error: {}; "
                "recovery backup retained at {}".format(reg_exc, rollback_error, backup_path)
            )
    except Exception as exc:
        # Destination was not yet committed (or forward replace failed before it
        # succeeded); destination still holds the old bytes.
        _safe_unlink(stage_path)
        _safe_unlink(backup_path)
        return 1, "update staging failed: {}".format(exc)

    _safe_unlink(backup_path)
    return 0, "UPDATE {} <- {}".format(asset_id, existing["relative_path"])


# ---------------------------------------------------------------------------
# Registry validation (read-only)
# ---------------------------------------------------------------------------

def validate_registry(
    registry_path: Path,
    repo_root: Path,
) -> tuple[list[str], list[str]]:
    """Read-only registry validation. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not registry_path.exists():
        return ["registry not found: {}".format(registry_path)], []

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ["registry parse error: {}".format(exc)], []

    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        return ["registry root must be an object with an 'assets' array"], []

    records = data["assets"]
    story_root = (repo_root / STORY_ROOT).resolve()
    repo_root_resolved = repo_root.resolve()
    seen_ids: dict[str, int] = {}
    seen_paths: dict[str, int] = {}

    for idx, rec in enumerate(records):
        prefix = "assets[{}]".format(idx)
        if not isinstance(rec, dict):
            errors.append("{}: not an object".format(prefix))
            continue

        asset_id = rec.get("asset_id")
        if not isinstance(asset_id, str) or not ASSET_ID_RE.match(asset_id):
            errors.append("{}.asset_id: invalid".format(prefix))
        elif asset_id in seen_ids:
            errors.append(
                "{}.asset_id: duplicate {} (also at {})".format(
                    prefix, asset_id, seen_ids[asset_id]
                )
            )
        else:
            seen_ids[asset_id] = idx

        atype = rec.get("type")
        if atype not in V0_CATEGORIES:
            errors.append("{}.type: unknown category {!r}".format(prefix, atype))

        if atype == "character" and not rec.get("source_character_id"):
            errors.append("{}: type=character requires source_character_id".format(prefix))

        if rec.get("source_kind") not in SOURCE_KINDS:
            errors.append("{}.source_kind: invalid".format(prefix))

        rel = rec.get("relative_path")
        if not isinstance(rel, str) or not rel:
            errors.append("{}.relative_path: missing".format(prefix))
            continue

        if not _is_safe_relative(rel):
            errors.append("{}.relative_path: absolute or contains '..'".format(prefix))
            continue
        if not rel.startswith(STORY_ROOT + "/"):
            errors.append("{}.relative_path: outside approved story root".format(prefix))
            continue

        if rel in seen_paths:
            errors.append(
                "{}.relative_path: duplicate physical path {} (also at {})".format(
                    prefix, rel, seen_paths[rel]
                )
            )
        else:
            seen_paths[rel] = idx

        abs_path = repo_root / rel
        if not _is_under(abs_path, story_root):
            errors.append("{}.relative_path: escapes asset root".format(prefix))
            continue

        if not abs_path.is_file():
            errors.append("{}.relative_path: file missing".format(prefix))
            continue

        ext = _canonical_ext(_extension_of(rel))
        if ext is None:
            errors.append("{}.relative_path: unsupported extension".format(prefix))
            continue

        actual_hash = _hash_file(abs_path)
        imported = rec.get("imported_hash")
        if imported != actual_hash:
            errors.append(
                "{}.imported_hash: mismatch (recorded {}, actual {})".format(
                    prefix, imported, actual_hash
                )
            )

    # Orphan detection: files under STORY_ROOT not referenced by any record.
    registered_paths = {
        rec.get("relative_path")
        for rec in records
        if isinstance(rec, dict) and isinstance(rec.get("relative_path"), str)
    }
    actual_files: set[str] = set()
    if story_root.exists():
        for p in story_root.rglob("*"):
            if not p.is_file():
                continue
            if not _is_supported_asset_filename(p.name):
                continue
            try:
                rel = p.resolve().relative_to(repo_root_resolved).as_posix()
            except ValueError:
                continue
            actual_files.add(rel)

    for rel in sorted(actual_files - registered_paths):
        errors.append("orphaned asset file not in registry: {}".format(rel))

    return errors, warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_registry(repo_root: Path) -> Path:
    return repo_root / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"


def cmd_import(args: argparse.Namespace) -> int:
    root = _default_repo_root()
    registry = _default_registry(root)
    code, message = import_asset(
        root,
        registry,
        source_path=args.source,
        asset_id=args.asset_id,
        asset_type=args.asset_type,
        character_id=args.character_id,
        source_kind=args.source_kind,
        notes=args.notes,
        dry_run=args.dry_run,
    )
    print(message)
    return code


def cmd_update(args: argparse.Namespace) -> int:
    root = _default_repo_root()
    registry = _default_registry(root)
    code, message = update_asset(
        root,
        registry,
        asset_id=args.asset_id,
        source_path=args.source,
        notes=args.notes,
        dry_run=args.dry_run,
    )
    print(message)
    return code


def cmd_validate(args: argparse.Namespace) -> int:
    root = _default_repo_root()
    registry = Path(args.registry) if args.registry else _default_registry(root)
    errors, warnings = validate_registry(registry, root)
    for warning in warnings:
        print("WARN: {}".format(warning))
    if errors:
        for error in errors:
            print("FAIL: {}".format(error))
        return 1
    print("PASS: {}".format(registry))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visual Asset Registry + Safe Import v0."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="Validate and import one external image")
    p_import.add_argument("--source", required=True, help="Path to the external image")
    p_import.add_argument("--asset-id", required=True, dest="asset_id")
    p_import.add_argument(
        "--type", required=True, choices=sorted(V0_CATEGORIES), dest="asset_type"
    )
    p_import.add_argument("--character-id", dest="character_id")
    p_import.add_argument(
        "--source-kind", default="unknown", choices=sorted(SOURCE_KINDS)
    )
    p_import.add_argument("--notes", default="")
    p_import.add_argument("--dry-run", action="store_true")
    p_import.set_defaults(func=cmd_import)

    p_update = sub.add_parser("update", help="Explicit re-import for an existing asset_id")
    p_update.add_argument("--asset-id", required=True, dest="asset_id")
    p_update.add_argument("--source", required=True)
    p_update.add_argument("--notes", default=None)
    p_update.add_argument("--dry-run", action="store_true")
    p_update.set_defaults(func=cmd_update)

    p_validate = sub.add_parser("validate", help="Read-only registry validation")
    p_validate.add_argument("--registry", default=None)
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main() -> int:
    _configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())