"""Immutable local store and fail-closed verifier for runtime packages."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from services.character_authoring import compute_snapshot_hash
from services.character_authoring.validation import (
    validate_identifier,
    validate_snapshot_hash,
)

from .errors import (
    CharacterPublicationError,
    PublicationPackageCollisionError,
    PublicationStorageError,
    PublicationValidationError,
)
from .hashing import canonical_runtime_package_bytes
from .model import (
    AuthoringRuntimePackage,
    RUNTIME_PACKAGE_SCHEMA_VERSION,
    VerifiedRuntimePackage,
)

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def default_publication_root(repo_root: Path | str) -> Path:
    return Path(repo_root) / "local_runs" / "character_authoring_publication"


def _containment_key(path: Path) -> str:
    """Return a comparable absolute Windows path without a device prefix."""

    value = os.path.normcase(str(path.resolve(strict=False)))
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


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


def _read_regular_file(path: Path) -> bytes:
    try:
        status = path.lstat()
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise PublicationStorageError("runtime package does not exist") from exc
    except OSError as exc:
        raise PublicationStorageError("runtime package cannot be inspected") from exc
    if stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise PublicationValidationError("runtime package must not be a link")
    if not stat.S_ISREG(status.st_mode):
        raise PublicationValidationError("runtime package must be a regular file")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PublicationStorageError("runtime package cannot be read") from exc


def _parse_canonical_package(raw: bytes) -> AuthoringRuntimePackage:
    try:
        text = raw.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _JsonObjectError) as exc:
        raise PublicationValidationError(
            "runtime package is not valid duplicate-free UTF-8 JSON"
        ) from exc
    package = AuthoringRuntimePackage.from_dict(payload)
    if canonical_runtime_package_bytes(package) != raw:
        raise PublicationValidationError(
            "runtime package bytes are not canonical Publication V1 JSON"
        )
    if (
        compute_snapshot_hash(package.semantic)
        != package.provenance.source_snapshot_hash
    ):
        raise PublicationValidationError(
            "runtime package semantic does not match source_snapshot_hash"
        )
    return package


def _verify_runtime_package(
    path: Path | str, *, expected_package_hash: str
) -> tuple[VerifiedRuntimePackage, bytes]:
    package_path = Path(path)
    try:
        expected = validate_snapshot_hash(
            expected_package_hash, field="expected_package_hash"
        )
    except Exception as exc:
        raise PublicationValidationError(str(exc)) from exc
    if package_path.name != expected:
        raise PublicationValidationError(
            "runtime package filename does not equal expected package_hash"
        )
    raw = _read_regular_file(package_path)
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected:
        raise PublicationValidationError(
            "runtime package bytes do not match expected package_hash"
        )
    package = _parse_canonical_package(raw)
    return (
        VerifiedRuntimePackage(
            runtime_package_schema_version=RUNTIME_PACKAGE_SCHEMA_VERSION,
            compiler_profile=package.to_dict()["compiler_profile"],
            package_hash=actual_hash,
            provenance=package.provenance,
            semantic=package.semantic,
        ),
        raw,
    )


def verify_runtime_package(
    path: Path | str, *, expected_package_hash: str
) -> VerifiedRuntimePackage:
    """Verify exact bytes, schema, provenance, semantic, and content identity."""

    verified, _raw = _verify_runtime_package(
        path, expected_package_hash=expected_package_hash
    )
    return verified


class CharacterPublicationStore:
    """Content-addressed immutable store with no active/latest pointer."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()
        if self._root.exists() and not self._root.is_dir():
            raise PublicationStorageError("publication root is not a directory")

    @classmethod
    def for_repository(cls, repo_root: Path | str) -> "CharacterPublicationStore":
        return cls(default_publication_root(repo_root))

    @property
    def root(self) -> Path:
        return self._root

    def package_path(self, character_id: str, package_hash: str) -> Path:
        try:
            character = validate_identifier(character_id, field="character_id")
            digest = validate_snapshot_hash(package_hash, field="package_hash")
        except Exception as exc:
            raise PublicationValidationError(str(exc)) from exc
        candidate = self._root / character / digest
        try:
            if os.path.commonpath(
                [_containment_key(self._root), _containment_key(candidate)]
            ) != _containment_key(self._root):
                raise ValueError
        except (OSError, ValueError) as exc:
            raise PublicationStorageError(
                "resolved package path escapes publication root"
            ) from exc
        return candidate

    def verify(
        self, character_id: str, package_hash: str
    ) -> VerifiedRuntimePackage:
        path = self.package_path(character_id, package_hash)
        verified = verify_runtime_package(path, expected_package_hash=package_hash)
        if verified.provenance.source_character_id != character_id:
            raise PublicationValidationError(
                "runtime package character provenance does not match storage path"
            )
        return verified

    def publish(
        self,
        *,
        character_id: str,
        package_hash: str,
        canonical_bytes: bytes,
    ) -> VerifiedRuntimePackage:
        """Exclusively publish or idempotently accept identical valid bytes."""

        target = self.package_path(character_id, package_hash)
        if hashlib.sha256(canonical_bytes).hexdigest() != package_hash:
            raise PublicationValidationError(
                "canonical bytes do not match supplied package_hash"
            )

        def verify_existing() -> VerifiedRuntimePackage:
            try:
                verified, existing_bytes = _verify_runtime_package(
                    target, expected_package_hash=package_hash
                )
                if verified.provenance.source_character_id != character_id:
                    raise PublicationValidationError(
                        "package character does not match storage partition"
                    )
                if existing_bytes != canonical_bytes:
                    raise PublicationValidationError(
                        "existing package bytes differ from publication bytes"
                    )
                return verified
            except CharacterPublicationError as exc:
                raise PublicationPackageCollisionError(
                    "immutable runtime package target is not the identical valid artifact"
                ) from exc

        if os.path.lexists(target):
            return verify_existing()

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PublicationStorageError(
                "failed to create publication character directory"
            ) from exc

        try:
            fd, temp_name = tempfile.mkstemp(
                dir=str(target.parent),
                prefix=".tmp_character_publication_",
                suffix=".tmp",
            )
        except OSError as exc:
            raise PublicationStorageError(
                "failed to create publication temporary file"
            ) from exc

        try:
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(canonical_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise PublicationStorageError(
                    "failed to durably write publication temporary file"
                ) from exc

            try:
                os.link(temp_name, target)
            except FileExistsError:
                return verify_existing()
            except OSError as exc:
                raise PublicationStorageError(
                    "exclusive immutable package publication failed"
                ) from exc
        finally:
            try:
                os.unlink(temp_name)
            except OSError:
                pass

        try:
            return verify_existing()
        except PublicationPackageCollisionError:
            raise
        except CharacterPublicationError as exc:
            raise PublicationStorageError(
                "published package could not be verified"
            ) from exc


__all__ = [
    "CharacterPublicationStore",
    "default_publication_root",
    "verify_runtime_package",
]
