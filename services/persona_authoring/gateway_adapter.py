#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin Gateway adapter for PAC v0.

Wraps the existing ``PersonaCatalog`` read-only API and exposes
PAC-specific convenience methods for assembling authoring context.
Does NOT reimplement Gateway business logic, path confinement, or
allowlist validation.  Does NOT read ``personas/**`` directly.

All returned data is detached plain data from Gateway models.

PAC-Side Context Projection (added 2026-08-02):
    When a ``level`` is provided, ``get_authoring_context`` applies
    deterministic projection:
    * Only the requested ``levels/<level>.json`` is included.
    * ``speech/SPEECH_MATRIX.json`` is projected to keep only the
      requested level's matrix entry (deep-copied, no mutation).
    * Category prefixes ``visual/``, ``physiology/``, ``sexology/``,
      ``sexual_scripts/``, ``memory/`` are excluded.
    * Common text modules (psychology, relationships, safety, meta, ...)
      are preserved.
    * Fail-closed: missing requested level raises ``PacGatewayError``.
    * ``level=None`` preserves the legacy unfiltered behavior.
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.persona_gateway import PersonaCatalog
from services.persona_gateway.models import CharacterManifest, ModuleResult

from .errors import PacGatewayError

# ------------------------------------------------------------------
# PAC-side context projection constants
# ------------------------------------------------------------------

# Prefixes excluded from text authoring context for ALL levels.
_EXCLUDED_CATEGORY_PREFIXES: tuple[str, ...] = (
    "visual/",
    "physiology/",
    "sexology/",
    "sexual_scripts/",
    "memory/",
)

# Module id that receives speech-matrix projection.
_SPEECH_MATRIX_MODULE_ID = "speech/SPEECH_MATRIX.json"


class GatewayAdapter:
    """Read-only PAC facade over the existing Persona Gateway.

    Constructor accepts an already-constructed ``PersonaCatalog``.
    PAC never constructs a catalog itself -- the caller injects it.
    """

    def __init__(self, catalog: PersonaCatalog) -> None:
        self._catalog: PersonaCatalog = catalog

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_characters(self) -> list[dict[str, str]]:
        """Return all available character ids and display names."""
        refs = self._catalog.list_characters()
        return [{"id": ref.id, "name": ref.name} for ref in refs]

    def get_character_manifest(self, character_id: str) -> CharacterManifest:
        """Return the validated manifest for one character."""
        try:
            return self._catalog.get_character_manifest(character_id)
        except Exception as exc:
            raise PacGatewayError(
                f"failed to get manifest for {character_id!r}: {exc}"
            ) from exc

    def read_module(self, character_id: str, module_id: str) -> ModuleResult:
        """Read one allowlisted module with provenance."""
        try:
            return self._catalog.read_module(character_id, module_id)
        except Exception as exc:
            raise PacGatewayError(
                f"failed to read module {module_id!r} for {character_id!r}: {exc}"
            ) from exc

    def get_authoring_context(self, character_id: str, level: str) -> dict:
        """Assemble the authoring context for one character at a given level.

        Reads relevant modules from the manifest and returns their data
        as a plain ``dict`` keyed by module id.  Only required modules
        that exist on disk are included; optional/missing modules are
        silently skipped.

        When ``level`` is not ``None``, PAC-side context projection is
        applied (see module docstring).

        Returns a dict with keys:
            ``manifest``, ``modules``, ``source_commit``
        """
        manifest = self.get_character_manifest(character_id)
        modules: Dict[str, dict] = {}

        for module_meta in manifest.modules:
            try:
                result = self.read_module(character_id, module_meta.module_id)
                modules[module_meta.module_id] = result.data
            except PacGatewayError:
                # Optional modules that are missing are gracefully skipped.
                if module_meta.required:
                    raise

        # Apply PAC-side context projection when a level is requested.
        if level is not None:
            modules = _project_context(
                character_id=character_id,
                level=level,
                modules=modules,
                manifest=manifest,
            )

        source_commit = _get_git_head()

        return {
            "manifest": {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "schema_version": manifest.schema_version,
                "default_level": manifest.default_level,
                "default_ag_level": manifest.default_ag_level,
            },
            "modules": modules,
            "source_commit": source_commit,
        }

    def build_canon_snapshot(
        self, character_id: str, level: str
    ) -> dict:
        """Build the ``canon_snapshot`` object required by ``pac-training-example-v1``.

        Returns a dict with ``source_commit`` and ``modules[]`` where each
        module entry contains ``module_id``, ``content_hash``, and ``provenance``
        sourced from the Gateway.
        """
        manifest = self.get_character_manifest(character_id)
        source_commit = _get_git_head()
        snapshot_modules: List[Dict[str, str]] = []

        for module_meta in manifest.modules:
            try:
                result = self.read_module(character_id, module_meta.module_id)
                snapshot_modules.append(
                    {
                        "module_id": module_meta.module_id,
                        "content_hash": result.provenance.content_hash,
                        "provenance": "gateway-v1",
                    }
                )
            except PacGatewayError:
                if module_meta.required:
                    raise

        return {
            "source_commit": source_commit,
            "modules": snapshot_modules,
        }


# ------------------------------------------------------------------
# PAC-side context projection (private)
# ------------------------------------------------------------------


def _project_context(
    *,
    character_id: str,
    level: str,
    modules: Dict[str, dict],
    manifest: CharacterManifest,
) -> Dict[str, dict]:
    """Apply deterministic level-aware context projection.

    Rules (applied in order):
    1. Level modules: keep only ``levels/<level>.json`` (exact match).
       Fail-closed if missing.
    2. Speech matrix: projected to keep only the requested level's
       matrix entry.
    3. Excluded category prefixes: removed unconditionally.
    4. All other modules: preserved as-is.
    """
    projected: Dict[str, dict] = {}
    expected_level_module = f"levels/{level}.json"
    level_module_found = False

    for module_id, module_data in modules.items():
        # -- rule 1: level modules ----------------------------------
        if module_id.startswith("levels/"):
            if module_id == expected_level_module:
                projected[module_id] = module_data
                level_module_found = True
            # else: skip — not the requested level
            continue

        # -- rule 2: speech matrix projection -----------------------
        if module_id == _SPEECH_MATRIX_MODULE_ID:
            projected[module_id] = _project_speech_matrix(
                character_id=character_id,
                level=level,
                module_data=module_data,
            )
            continue

        # -- rule 3: excluded category prefixes ---------------------
        if _is_excluded_category(module_id):
            continue

        # -- rule 4: preserve everything else -----------------------
        projected[module_id] = module_data

    # Fail-closed: requested level must have a corresponding module.
    if not level_module_found:
        raise PacGatewayError(
            f"context projection failed for {character_id!r} level {level!r}: "
            f"required level module {expected_level_module!r} not found in loaded modules"
        )

    return projected


def _is_excluded_category(module_id: str) -> bool:
    """Return ``True`` if *module_id* belongs to an excluded category."""
    for prefix in _EXCLUDED_CATEGORY_PREFIXES:
        if module_id.startswith(prefix):
            return True
    return False


def _project_speech_matrix(
    *,
    character_id: str,
    level: str,
    module_data: dict,
) -> dict:
    """Return a deep-copied, projected speech matrix containing only
    the requested level's entry.

    The original *module_data* is never mutated.

    Fail-closed: if ``matrix`` is present but does not contain the
    requested *level* key, a ``PacGatewayError`` is raised.
    """
    matrix: Optional[dict] = module_data.get("matrix")
    if matrix is None:
        # No matrix to project — return unmodified deep copy.
        return copy.deepcopy(module_data)

    if not isinstance(matrix, dict):
        raise PacGatewayError(
            f"speech matrix for {character_id!r} has non-dict 'matrix' field; "
            f"cannot project for level {level!r}"
        )

    if level not in matrix:
        raise PacGatewayError(
            f"context projection failed for {character_id!r} level {level!r}: "
            f"speech matrix does not contain entry for {level!r}"
        )

    projected = copy.deepcopy(module_data)
    projected["matrix"] = {level: matrix[level]}
    return projected


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------


def _get_git_head() -> str:
    """Return ``git rev-parse HEAD`` as a 40-char hex string.

    Falls back to ``"unknown"`` when git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
                return sha
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return "unknown"