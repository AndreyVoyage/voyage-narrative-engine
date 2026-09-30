#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Media v0 -- bounded managed storage for Primary Portrait bytes.

Content-addressed, immutable, no-clobber, git-ignored local store:

    local_runs/character_media/<character_id>/<sha256>.<ext>

Import flow: validate source -> sniff format -> deterministic dimension/static
checks -> exact-bytes SHA-256 -> atomic COPY (never move) with post-write
verification -> reuse identical bytes. The original external source path is
never authority and may disappear after import.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from services.reference_library.hashing import compute_sha256

from .errors import (
    AssetCollisionError,
    AssetNotFoundError,
    CharacterMediaStorageError,
    OversizedAssetError,
    Sha256MismatchError,
    SourceValidationError,
    UnsupportedFormatError,
)
from .model import MAX_ASSET_BYTES, ManagedPortraitRecord, format_extension
from .validation import (
    FORMAT_JPEG,
    FORMAT_PNG,
    FORMAT_WEBP,
    ValidatedImage,
    inspect_image,
)

# Mirrors the Character Authoring machine-identifier convention (lowercase ASCII).
_CHARACTER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")

_EXT_ALIASES = {
    "png": FORMAT_PNG,
    "jpg": FORMAT_JPEG,
    "jpeg": FORMAT_JPEG,
    "webp": FORMAT_WEBP,
}


def default_media_root(repo_root: Path | str) -> Path:
    """Return the ratified managed-media root for a repository root."""
    return Path(repo_root) / "local_runs" / "character_media"


def media_root_next_to(authoring_root: Path | str) -> Path:
    """Return the media root sibling of a Character Authoring store root."""
    return Path(authoring_root).resolve().parent / "character_media"


def _safe_character_id(character_id: str) -> str:
    if (
        not isinstance(character_id, str)
        or _CHARACTER_ID_RE.fullmatch(character_id) is None
    ):
        raise SourceValidationError(
            f"character_id is not a safe machine identifier: {character_id!r}"
        )
    return character_id


def _source_extension_format(name: str) -> Optional[str]:
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    return _EXT_ALIASES.get(ext)


def _read_and_validate_source(source_path: Path) -> Tuple[bytes, ValidatedImage]:
    """Return (data, validated_facts); raise on any source/format failure.

    Enforces a PRE-READ size guard (stat before read) so an oversized source is
    rejected before its bytes are fully allocated, plus the POST-READ size
    check inside ``inspect_image`` (guards against a source changing size
    between stat() and read()).
    """
    if not source_path.exists():
        raise SourceValidationError("source does not exist")
    if source_path.is_symlink():
        raise SourceValidationError("symlinked sources are rejected")
    if not source_path.is_file():
        raise SourceValidationError("source is not a regular file")
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise SourceValidationError(f"source is unreadable: {exc}") from exc
    if size <= 0:
        raise SourceValidationError("source file is empty")
    if size > MAX_ASSET_BYTES:
        raise OversizedAssetError(
            f"source exceeds {MAX_ASSET_BYTES} bytes ({size})"
        )
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise SourceValidationError(f"source is unreadable: {exc}") from exc

    info = inspect_image(data)  # sniffs + validates size/static/dimensions

    declared = _source_extension_format(source_path.name)
    if declared is not None and declared != info.format:
        raise UnsupportedFormatError(
            f"extension/signature mismatch: bytes are {info.format!r}"
        )

    return data, info



class CharacterMediaStore:
    """Content-addressed managed store for immutable character media bytes."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    @classmethod
    def for_repository(cls, repo_root: Path | str) -> "CharacterMediaStore":
        return cls(default_media_root(repo_root))

    @property
    def root(self) -> Path:
        return self._root

    def _managed_path(self, character_id: str, asset_sha256: str, fmt: str) -> Path:
        _safe_character_id(character_id)
        ext = format_extension(fmt)
        candidate = (self._root / character_id / f"{asset_sha256}.{ext}").resolve(
            strict=False
        )
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise CharacterMediaStorageError(
                "resolved managed path escapes the media store root"
            ) from exc
        return candidate

    def _publish_bytes_no_clobber(
        self, target: Path, data: bytes, expected_sha: str
    ) -> None:
        """Atomically publish bytes at ``target`` without clobbering.

        Reuses the repository's proven immutable/no-clobber idiom: stage a temp
        file, verify the exact SHA-256, then hard-link into place. Identical
        existing bytes are reused; different bytes at the same content address
        fail closed.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_bytes()
            if compute_sha256(existing) != expected_sha:
                raise AssetCollisionError(
                    f"content-addressed path already holds different bytes: "
                    f"{target.name!r}"
                )
            return  # identical bytes: reuse the managed asset

        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".character_media_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if compute_sha256(Path(tmp).read_bytes()) != expected_sha:
                raise Sha256MismatchError("staged managed bytes SHA mismatch")
            try:
                os.link(tmp, target)
            except FileExistsError:
                existing = target.read_bytes()
                if compute_sha256(existing) != expected_sha:
                    raise AssetCollisionError(
                        "content-addressed path already holds different bytes"
                    )
        except OSError as exc:
            raise CharacterMediaStorageError(
                "failed to publish managed bytes"
            ) from exc
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def import_portrait(
        self, source_path: Path | str, character_id: str
    ) -> ManagedPortraitRecord:
        """Validate and import exactly one source image as a managed portrait.

        COPY-only (never moves/deletes the source). Content-addressed by exact
        SHA-256, so identical bytes reuse the same physical managed asset.
        """
        character_id = _safe_character_id(character_id)
        source = Path(source_path)
        data, info = _read_and_validate_source(source)
        asset_sha256 = info.sha256

        target = self._managed_path(character_id, asset_sha256, info.format)
        self._publish_bytes_no_clobber(target, data, asset_sha256)

        relative_path = target.relative_to(self._root).as_posix()
        return ManagedPortraitRecord(
            character_id=character_id,
            asset_sha256=asset_sha256,
            format=info.format,
            mime_type=info.mime_type,
            byte_length=info.byte_length,
            relative_path=relative_path,
        )

    def managed_path(
        self, character_id: str, asset_sha256: str, fmt: str
    ) -> Path:
        """Return the exact managed content path for a known asset."""
        return self._managed_path(character_id, asset_sha256, fmt)

    def read_portrait_bytes(
        self, character_id: str, asset_sha256: str, fmt: str
    ) -> bytes:
        """Read managed bytes and fail closed on size/SHA violations."""
        path = self._managed_path(character_id, asset_sha256, fmt)
        if not path.is_file():
            raise AssetNotFoundError(
                f"managed asset {asset_sha256!r} not found for {character_id!r}"
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise CharacterMediaStorageError(
                "managed bytes cannot be inspected"
            ) from exc
        if size > MAX_ASSET_BYTES:
            raise CharacterMediaStorageError(
                "managed asset exceeds maxSingleFileBytes"
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CharacterMediaStorageError("managed bytes cannot be read") from exc
        if len(data) > MAX_ASSET_BYTES:  # post-read race guard
            raise CharacterMediaStorageError(
                "managed asset exceeds maxSingleFileBytes"
            )
        if compute_sha256(data) != asset_sha256:
            raise Sha256MismatchError("managed bytes SHA mismatch")
        return data
