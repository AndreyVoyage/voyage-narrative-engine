#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 0 read-only provenance utilities.

Every function here is read-only: no source file is ever written,
truncated, moved, or otherwise mutated, and no Git state is ever mutated.
Hashing reads files in fixed-size binary chunks. This module intentionally
uses stdlib only (``hashlib``, ``subprocess``, ``pathlib``) -- no network,
no external packages.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Optional

from .contracts import SourceArtifact

_HASH_CHUNK_SIZE = 65536
_GIT_TIMEOUT_S = 5.0
_HEX_DIGITS = frozenset("0123456789abcdef")


class ProvenanceError(RuntimeError):
    """Raised when a read-only provenance operation cannot complete safely
    (missing file, path escape, hashing failure, git failure)."""


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 digest of ``path``'s exact bytes.

    Reads ``path`` in fixed-size binary chunks; never modifies it. The same
    file content always yields the same digest.
    """
    if not path.is_file():
        raise ProvenanceError(f"cannot hash: not a regular file: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ProvenanceError(f"failed to read {path} for hashing: {exc}") from None
    return digest.hexdigest()


def to_repo_relative_posix(path: Path, repo_root: Path) -> str:
    """Resolve ``path`` and return it as a repo-relative POSIX string.

    Rejects any path that resolves outside ``repo_root`` (traversal or
    absolute escape) and rejects a symlink at any path component between
    ``repo_root`` and the target (catches a symlinked intermediate
    directory, not just a symlinked leaf file).
    """
    root_resolved = repo_root.resolve()
    if not root_resolved.is_dir():
        raise ProvenanceError(f"repo_root is not a directory: {repo_root}")

    candidate = path if path.is_absolute() else (repo_root / path)
    resolved = candidate.resolve()

    try:
        relative = resolved.relative_to(root_resolved)
    except ValueError:
        raise ProvenanceError(f"path escapes repo root: {path}") from None

    _reject_symlink_chain(root_resolved, relative.parts)

    return relative.as_posix()


def _reject_symlink_chain(root_resolved: Path, relative_parts: tuple) -> None:
    """Reject a symlink at any path component between ``root_resolved`` and
    the target described by ``relative_parts``."""
    current = root_resolved
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            raise ProvenanceError(f"symlink detected in path component: {part!r}")


def get_head_sha(repo_root: Path, *, timeout_s: float = _GIT_TIMEOUT_S) -> str:
    """Return the current ``git rev-parse HEAD`` SHA for ``repo_root``.

    Strictly read-only: never mutates the git repository (no ``shell=True``,
    no write subcommands). Raises ``ProvenanceError`` on any non-zero exit,
    timeout, or output that is not exactly a 40-char lowercase hex SHA.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProvenanceError(f"failed to run git rev-parse HEAD: {exc}") from None

    if result.returncode != 0:
        raise ProvenanceError(
            f"git rev-parse HEAD failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    sha = result.stdout.strip()
    if len(sha) != 40 or any(c not in _HEX_DIGITS for c in sha):
        raise ProvenanceError(f"unexpected git rev-parse HEAD output: {sha!r}")
    return sha


def build_source_artifact(
    repo_root: Path,
    relative_path: str,
    *,
    kind: str,
    json_path: Optional[str] = None,
    module_id: Optional[str] = None,
) -> SourceArtifact:
    """Build a hashed, path-confined ``SourceArtifact`` for one repo file.

    ``relative_path`` is resolved and confined to ``repo_root`` before
    hashing; the file is never modified.
    """
    root_resolved = repo_root.resolve()
    candidate = root_resolved / relative_path
    normalized = to_repo_relative_posix(candidate, root_resolved)
    digest = sha256_file(root_resolved / normalized)
    return SourceArtifact(
        repo_relative_path=normalized,
        sha256=digest,
        kind=kind,
        json_path=json_path,
        module_id=module_id,
    )
