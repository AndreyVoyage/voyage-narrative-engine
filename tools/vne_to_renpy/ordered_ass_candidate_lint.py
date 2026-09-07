#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderedASS project-candidate lint helper v1 (isolated temp copy).

Lints an already-built ``OrderedProjectCandidate`` against the REAL local Ren'Py
SDK inside a TEMP copy of the source Ren'Py project. The source worktree is
NEVER written; the candidate is injected only into the temp copy, under the
reserved TEMP filename (``vne_ordered_ass_candidate.rpy``).

The existing V2 generated file (``scenes_v2_generated.rpy``) is retained inside
the temp copy so the candidate coexists with the current project exactly as it
would in production. No assets are copied or mutated (the full ``novel/`` copy
already includes ``game/images/``). The reserved candidate name is checked in
the SOURCE project first and fails closed if it already exists.

Reuses ``tools.renpy_static_validator.find_renpy_command`` (unchanged) and the
existing dummy-SDL / temp-save environment convention. No shell=True, no
arbitrary command interpolation, no network, no provider calls.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tools.renpy_static_validator import find_renpy_command

from .ordered_ass_project_exporter import (
    ORDERED_ASS_CANDIDATE_FILENAME,
    OrderedProjectCandidate,
)

__all__ = [
    "lint_ordered_ass_candidate",
    "CandidateLintResult",
    "OrderedCandidateLintError",
]

_GAME_DIRNAME = "game"
_DEFAULT_TIMEOUT_SECONDS = 120

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _candidate_sha256(candidate: OrderedProjectCandidate) -> str:
    """Validate and recompute the candidate self-hash (fail closed)."""
    if not isinstance(candidate.source_sha256, str) or _SHA256_RE.fullmatch(candidate.source_sha256) is None:
        raise OrderedCandidateLintError("candidate.source_sha256 must be 64 lowercase hex")
    recomputed = hashlib.sha256(candidate.source.encode("utf-8")).hexdigest()
    if recomputed != candidate.source_sha256:
        raise OrderedCandidateLintError("candidate source hash does not match its bytes")
    return recomputed


class OrderedCandidateLintError(Exception):
    """Raised on any candidate lint failure. Carries the completed failed result
    when a nonzero lint run completed (result is the single positional arg)."""

    def __init__(self, message_or_result: object) -> None:
        if isinstance(message_or_result, CandidateLintResult):
            super().__init__(
                "Ren'Py candidate lint failed with returncode {}".format(
                    message_or_result.returncode
                )
            )
            self.result = message_or_result
        else:
            super().__init__(str(message_or_result))
            self.result = None


@dataclass(frozen=True)
class CandidateLintResult:
    """Immutable result of a candidate lint run.

    ``candidate_source_sha256`` binds the result to the exact candidate bytes
    that were linted, so a lint proof can never authorize a different candidate.
    """

    candidate_filename: str
    candidate_source_sha256: str
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    passed: bool
    temp_cleaned: bool


def _require_absolute_directory(path: Path, name: str) -> None:
    if not isinstance(path, Path):
        raise OrderedCandidateLintError("{} must be a Path".format(name))
    if not path.is_absolute():
        raise OrderedCandidateLintError("{} must be absolute: {!r}".format(name, path))
    if not path.exists():
        raise OrderedCandidateLintError("{} does not exist: {!r}".format(name, path))
    if not path.is_dir():
        raise OrderedCandidateLintError("{} is not a directory: {!r}".format(name, path))


def _build_command(python_exe: Path, renpy_entry: Path, temp_novel: Path) -> list[str]:
    if renpy_entry == python_exe:
        # exe mode: renpy.exe <basedir> lint --error-code
        return [str(python_exe), str(temp_novel), "lint", "--error-code"]
    # python mode: python.exe renpy.py <basedir> lint --error-code
    return [str(python_exe), str(renpy_entry), str(temp_novel), "lint", "--error-code"]


def lint_ordered_ass_candidate(
    candidate: OrderedProjectCandidate,
    *,
    source_novel_path: Path,
    sdk_path: Path,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> CandidateLintResult:
    """Lint a candidate in a temp copy of the source Ren'Py project.

    Validates source/sdk paths (explicit absolute directories), resolves the SDK
    command via ``find_renpy_command`` (unchanged), fails closed if the reserved
    candidate filename already exists in SOURCE, copies the full
    ``source_novel_path`` into a fresh temp dir, writes the candidate ONLY there,
    and runs ``<sdk> <temp>/novel lint --error-code`` with dummy-SDL / temp-save
    env. Guarantees temp cleanup before returning PASS or raising the failure.
    """
    if not isinstance(candidate, OrderedProjectCandidate):
        raise OrderedCandidateLintError("candidate must be an OrderedProjectCandidate")
    if candidate.candidate_filename != ORDERED_ASS_CANDIDATE_FILENAME:
        raise OrderedCandidateLintError("candidate has an unexpected candidate_filename")
    candidate_sha = _candidate_sha256(candidate)
    _require_absolute_directory(source_novel_path, "source_novel_path")
    _require_absolute_directory(sdk_path, "sdk_path")

    command_info = find_renpy_command(sdk_path)
    if command_info is None:
        raise OrderedCandidateLintError("could not find Ren'Py executable in SDK")

    reserved = source_novel_path / _GAME_DIRNAME / ORDERED_ASS_CANDIDATE_FILENAME
    if reserved.exists():
        raise OrderedCandidateLintError(
            "reserved candidate file already exists in source project: {}".format(reserved)
        )

    python_exe, renpy_entry = command_info
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    command: tuple[str, ...] = ()

    try:
        with tempfile.TemporaryDirectory(prefix="vne_ordered_ass_lint_") as tmp:
            temp_novel = Path(tmp) / "novel"
            shutil.copytree(source_novel_path, temp_novel, dirs_exist_ok=True)

            candidate_path = temp_novel / _GAME_DIRNAME / ORDERED_ASS_CANDIDATE_FILENAME
            candidate_path.write_text(candidate.source, encoding="utf-8", newline="\n")

            env = os.environ.copy()
            env["SDL_VIDEODRIVER"] = "dummy"
            env["SDL_AUDIODRIVER"] = "dummy"
            env["RENPY_PATH_TO_SAVES"] = str(Path(tmp) / "saves")

            cmd = _build_command(python_exe, renpy_entry, temp_novel)
            command = tuple(cmd)
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout_seconds,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        raise OrderedCandidateLintError("Ren'Py candidate lint timed out") from exc
    except OSError as exc:
        raise OrderedCandidateLintError(
            "temp construction or subprocess failed: {}".format(exc)
        ) from exc

    result = CandidateLintResult(
        candidate_filename=ORDERED_ASS_CANDIDATE_FILENAME,
        candidate_source_sha256=candidate_sha,
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        passed=(returncode == 0),
        temp_cleaned=True,
    )

    if returncode != 0:
        raise OrderedCandidateLintError(result)
    return result
