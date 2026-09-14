#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only management views over installed Character Package V1 releases."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from .package_importer import (
    TRUST_LOCAL_UNTRUSTED,
    CharacterPackageImportService,
    PackageImportResult,
)
from .package_v1 import (
    CharacterPackagePathError,
    CharacterPackageV1Error,
    VerifiedCharacterPackage,
)


_S6_STAGING_NAME_RE = re.compile(r"\.staging-[0-9a-f]{32}\Z")
_VALIDATION_RELEASE_ID = "management-validation"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class CharacterPackageManagementError(CharacterPackageV1Error):
    """Root of failures originating in the installed-package management layer."""


class InstalledPackageCorruptError(CharacterPackageManagementError):
    """Managed package storage contains an entry that cannot be accepted safely."""


class InstalledPackageNotFoundError(CharacterPackageManagementError):
    """A requested safe character/release coordinate is not installed."""


@dataclass(frozen=True, slots=True)
class InstalledPackageRelease:
    """Immutable management metadata derived from one S6-verified release."""

    character_id: str
    release_id: str
    display_name: str
    package_hash: str
    authority_class: str
    package_origin: str
    trust_status: str


@dataclass(frozen=True, slots=True)
class InstalledCharacter:
    """Derived grouping of verified releases for one installed character."""

    character_id: str
    releases: tuple[InstalledPackageRelease, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "releases", tuple(self.releases))


def _is_link_or_reparse(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


class CharacterPackageManagementService:
    """Discover verified installed packages without adding management state."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._package_store = self._data_root / "character_packages"
        self._importer = CharacterPackageImportService(self._data_root)

    @staticmethod
    def _corrupt(message: str, cause: BaseException | None = None) -> NoReturn:
        error = InstalledPackageCorruptError(message)
        if cause is None:
            raise error
        raise error from cause

    def _store_exists(self) -> bool:
        try:
            status = self._package_store.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return False
        except OSError as exc:
            self._corrupt("character package store cannot be inspected", exc)

        if _is_link_or_reparse(status):
            self._corrupt("character package store must not be a symbolic link")
        if not stat.S_ISDIR(status.st_mode):
            self._corrupt("character package store is not a directory")
        return True

    @staticmethod
    def _scan_directory(
        directory: Path, logical_name: str
    ) -> tuple[tuple[str, Path, os.stat_result], ...]:
        entries: list[tuple[str, Path, os.stat_result]] = []
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    try:
                        status = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise InstalledPackageCorruptError(
                            f"{logical_name} entry {entry.name!r} cannot be inspected"
                        ) from exc
                    entries.append((entry.name, Path(entry.path), status))
        except InstalledPackageCorruptError:
            raise
        except OSError as exc:
            raise InstalledPackageCorruptError(
                f"{logical_name} cannot be scanned"
            ) from exc
        return tuple(sorted(entries, key=lambda item: item[0]))

    @classmethod
    def _require_directory_entry(
        cls, name: str, status: os.stat_result, logical_name: str
    ) -> None:
        if _is_link_or_reparse(status):
            cls._corrupt(f"{logical_name} {name!r} must not be a symbolic link")
        if not stat.S_ISDIR(status.st_mode):
            cls._corrupt(f"{logical_name} {name!r} is not a directory")

    def _validate_discovered_character_id(self, character_id: str) -> None:
        try:
            self._importer.installed_path(character_id, _VALIDATION_RELEASE_ID)
        except CharacterPackagePathError as exc:
            self._corrupt(
                f"unsafe character package store entry {character_id!r}", exc
            )

    def _validate_discovered_release_id(
        self, character_id: str, release_id: str
    ) -> None:
        try:
            self._importer.installed_path(character_id, release_id)
        except CharacterPackagePathError as exc:
            self._corrupt(
                f"unsafe release store entry {character_id!r}/{release_id!r}", exc
            )

    @staticmethod
    def _release_view(verified: VerifiedCharacterPackage) -> InstalledPackageRelease:
        return InstalledPackageRelease(
            character_id=verified.character_id,
            release_id=verified.release_id,
            display_name=verified.display_name,
            package_hash=verified.package_hash,
            authority_class=verified.authority_class,
            package_origin=verified.package_origin,
            trust_status=TRUST_LOCAL_UNTRUSTED,
        )

    def _load_release(
        self, character_id: str, release_id: str
    ) -> InstalledPackageRelease:
        try:
            verified = self._importer.load_installed(character_id, release_id)
        except CharacterPackageV1Error as exc:
            self._corrupt(
                f"installed package {character_id!r}/{release_id!r} is corrupt",
                exc,
            )
        return self._release_view(verified)

    def _discover_character_releases(
        self, character_id: str, character_directory: Path
    ) -> tuple[InstalledPackageRelease, ...]:
        releases: list[InstalledPackageRelease] = []
        for release_id, _release_path, status in self._scan_directory(
            character_directory, f"character directory {character_id!r}"
        ):
            self._validate_discovered_release_id(character_id, release_id)
            self._require_directory_entry(release_id, status, "release entry")
            releases.append(self._load_release(character_id, release_id))
        return tuple(sorted(releases, key=lambda release: release.release_id))

    def list_characters(self) -> tuple[InstalledCharacter, ...]:
        """Return all verified installed characters in deterministic ID order."""

        if not self._store_exists():
            return ()

        characters: list[InstalledCharacter] = []
        for character_id, character_path, status in self._scan_directory(
            self._package_store, "character package store"
        ):
            if _S6_STAGING_NAME_RE.fullmatch(character_id):
                self._require_directory_entry(character_id, status, "S6 staging entry")
                continue

            self._validate_discovered_character_id(character_id)
            self._require_directory_entry(character_id, status, "character entry")
            releases = self._discover_character_releases(character_id, character_path)
            if releases:
                characters.append(
                    InstalledCharacter(character_id=character_id, releases=releases)
                )

        return tuple(sorted(characters, key=lambda character: character.character_id))

    def list_releases(
        self, character_id: str
    ) -> tuple[InstalledPackageRelease, ...]:
        """Return verified releases, or an empty tuple if a safe ID is not installed."""

        self._importer.installed_path(character_id, _VALIDATION_RELEASE_ID)
        for character in self.list_characters():
            if character.character_id == character_id:
                return character.releases
        return ()

    def get_release(
        self, character_id: str, release_id: str
    ) -> InstalledPackageRelease:
        """Return one verified release, distinguishing missing from corrupt state."""

        installed_path = self._importer.installed_path(character_id, release_id)
        if not self._store_exists():
            raise InstalledPackageNotFoundError(
                f"installed package {character_id!r}/{release_id!r} was not found"
            )

        character_path = installed_path.parent
        try:
            character_status = character_path.lstat()
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise InstalledPackageNotFoundError(
                f"installed character {character_id!r} was not found"
            ) from exc
        except OSError as exc:
            self._corrupt(f"character entry {character_id!r} cannot be inspected", exc)
        self._require_directory_entry(character_id, character_status, "character entry")

        try:
            release_status = installed_path.lstat()
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise InstalledPackageNotFoundError(
                f"installed package {character_id!r}/{release_id!r} was not found"
            ) from exc
        except OSError as exc:
            self._corrupt(
                f"release entry {character_id!r}/{release_id!r} cannot be inspected",
                exc,
            )
        self._require_directory_entry(
            release_id, release_status, f"release entry for {character_id!r}"
        )
        return self._load_release(character_id, release_id)

    def import_package(
        self,
        package_root: Path,
        *,
        expected_package_hash: str | None = None,
    ) -> PackageImportResult:
        """Delegate package installation unchanged to the authoritative S6 importer."""

        return self._importer.import_package(
            package_root, expected_package_hash=expected_package_hash
        )


__all__ = [
    "CharacterPackageManagementError",
    "InstalledPackageCorruptError",
    "InstalledPackageNotFoundError",
    "InstalledPackageRelease",
    "InstalledCharacter",
    "CharacterPackageManagementService",
]
