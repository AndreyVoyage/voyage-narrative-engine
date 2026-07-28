#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thin Gateway adapter for PAC v0.

Wraps the existing ``PersonaCatalog`` read-only API and exposes
PAC-specific convenience methods for assembling authoring context.
Does NOT reimplement Gateway business logic, path confinement, or
allowlist validation.  Does NOT read ``personas/**`` directly.

All returned data is detached plain data from Gateway models.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.persona_gateway import PersonaCatalog
from services.persona_gateway.models import CharacterManifest, ModuleResult

from .errors import PacGatewayError


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