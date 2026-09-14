#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-contained, fail-closed verification for Character Package V1.

Package identity is the SHA-256 of the exact ``manifest.json`` bytes.  This
module deliberately validates physical integrity only; successful verification
does not assign Registry trust or canonical status.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


RAW = "RAW"
CANONICAL_JSON_V1 = "CANONICAL_JSON_V1"
PACKAGE_SCHEMA_VERSION = "1.0"
MANIFEST_SCHEMA_VERSION = "1.0"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")
_WINDOWS_INVALID_CHARS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
        "COM¹",
        "COM²",
        "COM³",
        "LPT¹",
        "LPT²",
        "LPT³",
    }
)
_MANIFEST_FIELDS = frozenset({"manifestSchemaVersion", "files"})
_DESCRIPTOR_FIELDS = frozenset(
    {"path", "sha256", "byteLength", "semanticRole", "normalization", "required"}
)
_PACKAGE_REQUIRED_FIELDS = frozenset(
    {
        "packageSchemaVersion",
        "characterId",
        "releaseId",
        "displayName",
        "authorityClass",
        "packageOrigin",
    }
)
_PACKAGE_OPTIONAL_FIELDS = frozenset({"acceptedAggregateHash", "acceptanceRecordHash"})
_AUTHORITY_ORIGINS = {
    "ACCEPTED_RELEASE": "ACCEPTED_AGGREGATE",
    "LEGACY_COMPAT": "LEGACY_IMPORT",
    "LOCAL_USER": "LOCAL_USER_CREATION",
}
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class CharacterPackageV1Error(Exception):
    """Root of Character Package V1 verification failures."""


class CharacterPackageContractError(CharacterPackageV1Error):
    """The package does not satisfy the frozen V1 structural contract."""


class CharacterPackageIntegrityError(CharacterPackageV1Error):
    """The package's physical bytes do not match its integrity metadata."""


class CharacterPackagePathError(CharacterPackageContractError):
    """A source, package-relative path, or store identity is unsafe."""


@dataclass(frozen=True, slots=True)
class PackageFileDescriptor:
    """One immutable ``manifest.files[]`` descriptor."""

    path: str
    sha256: str
    byte_length: int
    semantic_role: str
    normalization: str
    required: bool


@dataclass(frozen=True, slots=True)
class VerifiedCharacterPackage:
    """Verified immutable package identity and metadata."""

    root: Path
    character_id: str
    release_id: str
    display_name: str
    authority_class: str
    package_origin: str
    package_hash: str
    manifest: Mapping[str, Any]
    files: tuple[PackageFileDescriptor, ...]
    package_schema_version: str
    manifest_schema_version: str


class _JsonObjectError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _JsonObjectError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise _JsonObjectError(f"non-standard JSON constant {value!r}")


def _parse_json(raw: bytes, logical_name: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CharacterPackageContractError(
            f"{logical_name} is not valid UTF-8"
        ) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, _JsonObjectError) as exc:
        raise CharacterPackageContractError(
            f"{logical_name} is not valid duplicate-free JSON: {exc}"
        ) from exc


def _canonical_json_bytes(payload: Any, logical_name: str) -> bytes:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CharacterPackageContractError(
            f"{logical_name} cannot be represented as canonical JSON V1"
        ) from exc


def _parse_canonical_json(raw: bytes, logical_name: str) -> Any:
    payload = _parse_json(raw, logical_name)
    if _canonical_json_bytes(payload, logical_name) != raw:
        raise CharacterPackageContractError(
            f"{logical_name} is not canonical JSON V1 bytes"
        )
    return payload


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _is_reparse_or_symlink_status(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _lstat(path: Path, logical_name: str) -> os.stat_result:
    try:
        return path.lstat()
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise CharacterPackagePathError(f"{logical_name} does not exist") from exc
    except OSError as exc:
        raise CharacterPackagePathError(f"{logical_name} cannot be inspected: {exc}") from exc


def validate_safe_package_path(value: Any) -> str:
    """Return an unchanged canonical path or reject unsafe Windows/POSIX forms."""

    if not isinstance(value, str):
        raise CharacterPackagePathError("package path must be a string")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        raise CharacterPackagePathError("package path must already be Unicode NFC")
    if not value:
        raise CharacterPackagePathError("package path must not be empty")
    if value.startswith(("/", "\\")):
        raise CharacterPackagePathError("absolute package paths are forbidden")
    if _DRIVE_PREFIX_RE.match(value):
        raise CharacterPackagePathError("Windows drive-qualified paths are forbidden")
    if "\\" in value:
        raise CharacterPackagePathError("package paths must use forward slashes")

    for segment in value.split("/"):
        if segment == "":
            raise CharacterPackagePathError("empty package path segments are forbidden")
        if segment in (".", ".."):
            raise CharacterPackagePathError("dot path segments are forbidden")
        if segment.endswith((".", " ")):
            raise CharacterPackagePathError(
                "Windows dot/space-terminated path segments are forbidden"
            )
        if any(unicodedata.category(character) == "Cc" for character in segment):
            raise CharacterPackagePathError("control characters are forbidden in package paths")
        if any(character in _WINDOWS_INVALID_CHARS for character in segment):
            raise CharacterPackagePathError(
                "Windows-invalid and alternate-data-stream characters are forbidden"
            )
        device_stem = segment.split(".", 1)[0].upper()
        if device_stem in _WINDOWS_RESERVED_NAMES:
            raise CharacterPackagePathError("Windows reserved device names are forbidden")
    return value


def validate_safe_store_segment(value: Any, field_name: str) -> str:
    """Validate a Package V1 character/release id used as one store segment."""

    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise CharacterPackagePathError(
            f"{field_name} must contain only ASCII letters, digits, '.', '_' or '-', "
            "and must start with a letter or digit"
        )
    validate_safe_package_path(value)
    if "/" in value:
        raise CharacterPackagePathError(f"{field_name} must be one path segment")
    return value


def _read_regular_file(path: Path, logical_name: str) -> bytes:
    status = _lstat(path, logical_name)
    if _is_reparse_or_symlink_status(status):
        raise CharacterPackagePathError(f"{logical_name} must not be a symbolic link")
    if not stat.S_ISREG(status.st_mode):
        raise CharacterPackagePathError(f"{logical_name} is not a regular file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CharacterPackagePathError(f"{logical_name} cannot be read: {exc}") from exc


def _physical_files(package_root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    folded_entries: dict[str, str] = {}

    def visit(directory: Path, parent_parts: tuple[str, ...]) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError as exc:
            raise CharacterPackagePathError("package directory cannot be scanned") from exc

        for entry in entries:
            relative = "/".join(parent_parts + (entry.name,))
            normalized = validate_safe_package_path(relative)
            folded = normalized.casefold()
            previous = folded_entries.get(folded)
            if previous is not None and previous != normalized:
                raise CharacterPackagePathError(
                    f"case-fold physical path collision: {previous!r} vs {normalized!r}"
                )
            folded_entries[folded] = normalized

            try:
                status = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CharacterPackagePathError(
                    f"package entry cannot be inspected: {normalized!r}"
                ) from exc
            if _is_reparse_or_symlink_status(status):
                raise CharacterPackagePathError(
                    f"package contains a symbolic link: {normalized!r}"
                )
            if stat.S_ISDIR(status.st_mode):
                visit(Path(entry.path), parent_parts + (entry.name,))
            elif stat.S_ISREG(status.st_mode):
                files[normalized] = Path(entry.path)
            else:
                raise CharacterPackagePathError(
                    f"package contains a non-regular filesystem entry: {normalized!r}"
                )

    visit(package_root, ())
    return files


def _manifest_descriptors(payload: Any) -> tuple[str, tuple[PackageFileDescriptor, ...]]:
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
        raise CharacterPackageContractError(
            "manifest.json must contain exactly manifestSchemaVersion and files"
        )
    schema_version = payload["manifestSchemaVersion"]
    if schema_version != MANIFEST_SCHEMA_VERSION:
        raise CharacterPackageContractError(
            f"manifestSchemaVersion must be {MANIFEST_SCHEMA_VERSION!r}"
        )
    items = payload["files"]
    if not isinstance(items, list):
        raise CharacterPackageContractError("manifest files must be an array")

    descriptors: list[PackageFileDescriptor] = []
    exact_paths: set[str] = set()
    folded_paths: dict[str, str] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != _DESCRIPTOR_FIELDS:
            raise CharacterPackageContractError(
                f"manifest files[{index}] has missing or unknown fields"
            )
        path = validate_safe_package_path(item["path"])
        if path.casefold() == "manifest.json":
            raise CharacterPackageContractError("manifest.json must not list itself")
        if path in exact_paths:
            raise CharacterPackageContractError(f"duplicate descriptor path: {path!r}")
        folded = path.casefold()
        if folded in folded_paths:
            raise CharacterPackagePathError(
                f"case-fold descriptor path collision: {folded_paths[folded]!r} vs {path!r}"
            )
        exact_paths.add(path)
        folded_paths[folded] = path

        sha256 = item["sha256"]
        byte_length = item["byteLength"]
        semantic_role = item["semanticRole"]
        normalization = item["normalization"]
        required = item["required"]
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            raise CharacterPackageContractError(
                f"manifest files[{index}].sha256 is not a SHA-256 hex digest"
            )
        if (
            not isinstance(byte_length, int)
            or isinstance(byte_length, bool)
            or byte_length < 0
        ):
            raise CharacterPackageContractError(
                f"manifest files[{index}].byteLength must be a non-negative integer"
            )
        if not isinstance(semantic_role, str) or not semantic_role.strip():
            raise CharacterPackageContractError(
                f"manifest files[{index}].semanticRole must be non-empty"
            )
        if normalization not in (RAW, CANONICAL_JSON_V1):
            raise CharacterPackageContractError(
                f"manifest files[{index}].normalization is unknown"
            )
        if not isinstance(required, bool):
            raise CharacterPackageContractError(
                f"manifest files[{index}].required must be boolean"
            )
        descriptors.append(
            PackageFileDescriptor(
                path=path,
                sha256=sha256,
                byte_length=byte_length,
                semantic_role=semantic_role,
                normalization=normalization,
                required=required,
            )
        )

    paths = [descriptor.path for descriptor in descriptors]
    if paths != sorted(paths, key=lambda value: unicodedata.normalize("NFC", value)):
        raise CharacterPackageContractError("manifest descriptors are not sorted by path")
    if "package.json" not in exact_paths:
        raise CharacterPackageContractError("manifest must describe package.json")
    return schema_version, tuple(descriptors)


def _validate_package_metadata(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CharacterPackageContractError("package.json root must be an object")
    fields = set(payload)
    if not _PACKAGE_REQUIRED_FIELDS.issubset(fields):
        raise CharacterPackageContractError("package.json is missing required identity metadata")
    unknown = fields - _PACKAGE_REQUIRED_FIELDS - _PACKAGE_OPTIONAL_FIELDS
    if unknown:
        raise CharacterPackageContractError("package.json contains unknown metadata fields")
    if payload["packageSchemaVersion"] != PACKAGE_SCHEMA_VERSION:
        raise CharacterPackageContractError(
            f"packageSchemaVersion must be {PACKAGE_SCHEMA_VERSION!r}"
        )
    character_id = validate_safe_store_segment(payload["characterId"], "characterId")
    release_id = validate_safe_store_segment(payload["releaseId"], "releaseId")
    display_name = payload["displayName"]
    authority_class = payload["authorityClass"]
    package_origin = payload["packageOrigin"]
    if not isinstance(display_name, str) or not display_name.strip():
        raise CharacterPackageContractError("displayName must be a non-empty string")
    if authority_class not in _AUTHORITY_ORIGINS:
        raise CharacterPackageContractError("authorityClass is unknown")
    expected_origin = _AUTHORITY_ORIGINS[authority_class]
    if package_origin != expected_origin:
        raise CharacterPackageContractError(
            f"{authority_class} requires packageOrigin {expected_origin}"
        )

    accepted_fields = ("acceptedAggregateHash", "acceptanceRecordHash")
    if authority_class == "ACCEPTED_RELEASE":
        for field in accepted_fields:
            value = payload.get(field)
            if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
                raise CharacterPackageContractError(
                    f"ACCEPTED_RELEASE requires a valid {field}"
                )
    elif any(field in payload for field in accepted_fields):
        raise CharacterPackageContractError(
            f"{authority_class} must not contain acceptance binding metadata"
        )

    return {
        "package_schema_version": payload["packageSchemaVersion"],
        "character_id": character_id,
        "release_id": release_id,
        "display_name": display_name,
        "authority_class": authority_class,
        "package_origin": package_origin,
    }


def verify_character_package_v1(
    package_root: Path,
    *,
    expected_package_hash: str | None = None,
) -> VerifiedCharacterPackage:
    """Fully verify one installed-directory Character Package V1.

    The source directory is read only.  No identity is inferred from its name.
    """

    root = Path(package_root)
    root_status = _lstat(root, "package root")
    if _is_reparse_or_symlink_status(root_status):
        raise CharacterPackagePathError("package root must not be a symbolic link")
    if not stat.S_ISDIR(root_status.st_mode):
        raise CharacterPackagePathError("package root is not a directory")

    manifest_path = root / "manifest.json"
    manifest_bytes = _read_regular_file(manifest_path, "manifest.json")
    package_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if expected_package_hash is not None:
        if not isinstance(expected_package_hash, str) or not _SHA256_RE.fullmatch(
            expected_package_hash
        ):
            raise CharacterPackageIntegrityError(
                "expected_package_hash must be a SHA-256 hex digest"
            )
        if package_hash != expected_package_hash.lower():
            raise CharacterPackageIntegrityError("packageHash does not match expected value")

    manifest_payload = _parse_canonical_json(manifest_bytes, "manifest.json")
    manifest_schema_version, descriptors = _manifest_descriptors(manifest_payload)
    physical_files = _physical_files(root)
    expected_paths = {descriptor.path for descriptor in descriptors} | {"manifest.json"}
    actual_paths = set(physical_files)
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise CharacterPackageIntegrityError(
            f"physical file set differs from manifest; missing={missing!r}, extra={extra!r}"
        )

    package_payload: Any = None
    for descriptor in descriptors:
        content = _read_regular_file(physical_files[descriptor.path], descriptor.path)
        if len(content) != descriptor.byte_length:
            raise CharacterPackageIntegrityError(
                f"byteLength mismatch for {descriptor.path!r}"
            )
        if hashlib.sha256(content).hexdigest() != descriptor.sha256.lower():
            raise CharacterPackageIntegrityError(f"sha256 mismatch for {descriptor.path!r}")
        if descriptor.normalization == CANONICAL_JSON_V1:
            parsed = _parse_canonical_json(content, descriptor.path)
            if descriptor.path == "package.json":
                package_payload = parsed

    package_descriptor = next(
        descriptor for descriptor in descriptors if descriptor.path == "package.json"
    )
    if package_descriptor.normalization != CANONICAL_JSON_V1:
        raise CharacterPackageContractError(
            "package.json normalization must be CANONICAL_JSON_V1"
        )
    if package_payload is None:  # defensive; canonical branch above must set it
        raise CharacterPackageContractError("package.json could not be parsed")
    metadata = _validate_package_metadata(package_payload)

    return VerifiedCharacterPackage(
        root=root,
        character_id=metadata["character_id"],
        release_id=metadata["release_id"],
        display_name=metadata["display_name"],
        authority_class=metadata["authority_class"],
        package_origin=metadata["package_origin"],
        package_hash=package_hash,
        manifest=_freeze_json(manifest_payload),
        files=descriptors,
        package_schema_version=metadata["package_schema_version"],
        manifest_schema_version=manifest_schema_version,
    )


__all__ = [
    "CANONICAL_JSON_V1",
    "RAW",
    "CharacterPackageV1Error",
    "CharacterPackageContractError",
    "CharacterPackageIntegrityError",
    "CharacterPackagePathError",
    "PackageFileDescriptor",
    "VerifiedCharacterPackage",
    "verify_character_package_v1",
]
