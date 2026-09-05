#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workspace / Domain Foundation v0 -- ProjectManifest load/save boundary.

Deterministic serialize/parse/load/save of one ``ProjectManifest`` JSON
file, using the same atomic-write and fail-closed-validation house style as
``services/reference_library/manifest.py``. This module is read/validate/
serialize only: it never scans a directory for entities and never reads or
writes any of the domain artifacts an entity references (ASS, Location
Canon, Character Canon, the Visual Asset Registry).

There is no ratified canonical location for a ``ProjectManifest`` file yet,
so callers always supply an explicit path; this module invents no directory
convention.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .errors import (
    ProjectManifestError,
    ProjectManifestNotFoundError,
    ProjectManifestValidationError,
)
from .model import ProjectManifest

PROJECT_MANIFEST_SCHEMA_VERSION = "vne_workspace_project_manifest/0.1"


def serialize_manifest(manifest: ProjectManifest) -> str:
    """Return deterministic UTF-8 JSON: fixed key order, sorted entities, LF."""
    return json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n"


def parse_manifest(text: str) -> ProjectManifest:
    """Parse manifest JSON text into a validated ``ProjectManifest``."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ProjectManifestValidationError("manifest root must be an object")
    if data.get("schema_version") != PROJECT_MANIFEST_SCHEMA_VERSION:
        raise ProjectManifestValidationError(
            f"schema_version: expected {PROJECT_MANIFEST_SCHEMA_VERSION!r}"
        )
    return ProjectManifest.from_dict(data)


def load_manifest(manifest_path: Path) -> ProjectManifest:
    """Load and validate the ``ProjectManifest`` at ``manifest_path``."""
    path = Path(manifest_path)
    if not path.exists():
        raise ProjectManifestNotFoundError(f"manifest does not exist: {path.name}")
    return parse_manifest(path.read_text(encoding="utf-8"))


def save_manifest(manifest_path: Path, manifest: ProjectManifest) -> None:
    """Atomically write the deterministic serialization to ``manifest_path``.

    Uses the established VNE house style: write to a sibling temp file, then
    ``os.replace`` into place, so a reader never observes a partial write.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".workspace_project_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(serialize_manifest(manifest))
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def validate_manifest(manifest_path: Path) -> list[str]:
    """Read-only structural validation; returns a list of error strings ([] = valid).

    Mirrors ``services.reference_library.manifest.validate_manifest``: never
    reads or resolves any referenced entity, only checks manifest shape.
    """
    path = Path(manifest_path)
    if not path.exists():
        return ["manifest does not exist"]
    try:
        load_manifest(path)
    except ProjectManifestError as exc:
        return [str(exc)]
    return []
