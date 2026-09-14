#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled immutable Character Package V1 import into Companion storage."""

from __future__ import annotations

import os
import shutil
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from .package_v1 import (
    CharacterPackageIntegrityError,
    CharacterPackageV1Error,
    CharacterPackagePathError,
    VerifiedCharacterPackage,
    validate_safe_store_segment,
    verify_character_package_v1,
)


PACKAGE_IMPORTED = "IMPORTED"
PACKAGE_NO_OP_ALREADY_INSTALLED = "NO_OP_ALREADY_INSTALLED"
TRUST_LOCAL_UNTRUSTED = "LOCAL_UNTRUSTED"

_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class CharacterPackageImportError(CharacterPackageV1Error):
    """A package could not be safely installed in the local package store."""


class CharacterPackageCollisionError(CharacterPackageImportError):
    """A character/release identity is occupied by another valid packageHash."""


@dataclass(frozen=True, slots=True)
class PackageImportResult:
    status: str
    character_id: str
    release_id: str
    package_hash: str
    installed_path: Path
    trust_status: str

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "characterId": self.character_id,
            "releaseId": self.release_id,
            "packageHash": self.package_hash,
            "installedPath": str(self.installed_path),
            "trustStatus": self.trust_status,
        }


def _is_link_or_reparse(path: Path) -> bool:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _prepare_directory(path: Path, logical_name: str) -> None:
    if _is_link_or_reparse(path):
        raise CharacterPackagePathError(f"{logical_name} must not be a symbolic link")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CharacterPackageImportError(f"cannot create {logical_name}: {exc}") from exc
    if _is_link_or_reparse(path):
        raise CharacterPackagePathError(f"{logical_name} must not be a symbolic link")
    if not path.is_dir():
        raise CharacterPackageImportError(f"{logical_name} is not a directory")


class CharacterPackageImportService:
    """Verify, copy, re-verify, and atomically publish immutable V1 packages."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._package_store = self._data_root / "character_packages"

    def installed_path(self, character_id: str, release_id: str) -> Path:
        character = validate_safe_store_segment(character_id, "characterId")
        release = validate_safe_store_segment(release_id, "releaseId")
        return self._package_store / character / release

    def verify_source(
        self,
        package_root: Path,
        *,
        expected_package_hash: str | None = None,
    ) -> VerifiedCharacterPackage:
        return verify_character_package_v1(
            package_root, expected_package_hash=expected_package_hash
        )

    def load_installed(
        self,
        character_id: str,
        release_id: str,
        *,
        expected_package_hash: str | None = None,
    ) -> VerifiedCharacterPackage:
        character = validate_safe_store_segment(character_id, "characterId")
        release = validate_safe_store_segment(release_id, "releaseId")
        verified = verify_character_package_v1(
            self.installed_path(character, release),
            expected_package_hash=expected_package_hash,
        )
        if verified.character_id != character or verified.release_id != release:
            raise CharacterPackageIntegrityError(
                "installed package metadata does not match its store path"
            )
        return verified

    @staticmethod
    def _result(
        status: str, verified: VerifiedCharacterPackage, installed_path: Path
    ) -> PackageImportResult:
        return PackageImportResult(
            status=status,
            character_id=verified.character_id,
            release_id=verified.release_id,
            package_hash=verified.package_hash,
            installed_path=installed_path,
            trust_status=TRUST_LOCAL_UNTRUSTED,
        )

    def import_package(
        self,
        package_root: Path,
        *,
        expected_package_hash: str | None = None,
    ) -> PackageImportResult:
        # Source is completely verified before the package store is touched.
        source = self.verify_source(
            package_root, expected_package_hash=expected_package_hash
        )
        final_path = self.installed_path(source.character_id, source.release_id)

        if os.path.lexists(final_path):
            installed = self.load_installed(source.character_id, source.release_id)
            if installed.package_hash != source.package_hash:
                raise CharacterPackageCollisionError(
                    "characterId/releaseId is already installed with a different packageHash"
                )
            return self._result(PACKAGE_NO_OP_ALREADY_INSTALLED, installed, final_path)

        _prepare_directory(self._package_store, "character package store")
        staging = self._package_store / f".staging-{uuid.uuid4().hex}"
        published = False
        try:
            # symlinks=True preserves a raced-in link as a link.  Staged
            # verification then rejects it instead of following it.
            shutil.copytree(source.root, staging, symlinks=True)
            staged = verify_character_package_v1(
                staging, expected_package_hash=source.package_hash
            )
            if staged.package_hash != source.package_hash:  # defensive clarity
                raise CharacterPackageImportError("staged packageHash differs from source")

            character_dir = self._package_store / source.character_id
            _prepare_directory(character_dir, "character package directory")
            if os.path.lexists(final_path):
                installed = self.load_installed(source.character_id, source.release_id)
                if installed.package_hash != source.package_hash:
                    raise CharacterPackageCollisionError(
                        "characterId/releaseId is already installed with a different packageHash"
                    )
                shutil.rmtree(staging, ignore_errors=True)
                return self._result(
                    PACKAGE_NO_OP_ALREADY_INSTALLED, installed, final_path
                )
            try:
                os.rename(staging, final_path)
            except FileExistsError:
                installed = self.load_installed(source.character_id, source.release_id)
                if installed.package_hash != source.package_hash:
                    raise CharacterPackageCollisionError(
                        "characterId/releaseId is already installed with a different packageHash"
                    )
                shutil.rmtree(staging, ignore_errors=True)
                return self._result(
                    PACKAGE_NO_OP_ALREADY_INSTALLED, installed, final_path
                )
            except OSError as exc:
                raise CharacterPackageImportError(
                    f"cannot atomically publish staged package: {exc}"
                ) from exc
            published = True

            installed = self.load_installed(
                source.character_id,
                source.release_id,
                expected_package_hash=source.package_hash,
            )
            return self._result(PACKAGE_IMPORTED, installed, final_path)
        except BaseException:
            if not published:
                shutil.rmtree(staging, ignore_errors=True)
            raise


__all__ = [
    "PACKAGE_IMPORTED",
    "PACKAGE_NO_OP_ALREADY_INSTALLED",
    "TRUST_LOCAL_UNTRUSTED",
    "CharacterPackageImportError",
    "CharacterPackageCollisionError",
    "PackageImportResult",
    "CharacterPackageImportService",
]
