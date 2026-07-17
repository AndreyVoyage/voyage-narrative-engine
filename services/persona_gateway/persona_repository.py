#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PersonaRepository -- static Kira-only persona module repository
(N7 Persona Data Gateway, P1a-S1 partial runtime).

Design (per N7_P1A_CONTRACT_CORRECTION_READONLY_PREFLIGHT_2026-07-17.md):

* The caller injects an already-resolved ``persona_root`` (e.g.
  ``personas/kira``) and the ``character_id`` it represents. There is no
  directory scan of ``personas/``, no registry lookup, no hardcoded
  ``CharacterRef``.
* ``INDEX.json`` at the injected root is the sole source of the character's
  id/name and the sole allowlist of readable module ids. Module ids are the
  manifest's own relative-path keys (e.g. ``"core/IDENTITY.json"``) -- there
  is no separate ``path`` field.
* Module validation policy is JSON_PARSE_ONLY_WITH_STRUCTURAL_MANIFEST_
  VALIDATION: UTF-8 decode + JSON parse + manifest allowlist membership.
  ``schemas/persona_schema_v3_2_VOYAGE.json`` is NOT applied per-module
  (proven in the correction report to target the legacy monolith shape,
  not these modular source fragments) and ``jsonschema`` is never imported.
* Every module read passes, in order: character check, module-id shape
  validation (absolute/traversal/extension), manifest-allowlist membership,
  symlink rejection (root, and every path component down to the module
  file), resolved-path containment under ``persona_root``, existence,
  size cap, UTF-8 strict decode, JSON parse.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from .errors import (
    CharacterNotFoundError,
    ManifestIntegrityError,
    ManifestNotFoundError,
    ManifestParseError,
    ModuleEncodingError,
    ModuleParseError,
    ModuleSizeLimitError,
    PathSecurityError,
    PersonaModuleNotFoundError,
    UnsupportedExtensionError,
)
from .models import CharacterManifest, CharacterRef, ModuleMetadata, ModuleResult
from .provenance import build_module_provenance

_ALLOWED_EXTENSION = ".json"
_DRIVE_LETTER_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")

DEFAULT_MAX_MODULE_BYTES = 262144
DEFAULT_MAX_MANIFEST_ENTRIES = 128


def _reject_duplicate_keys(pairs: list[tuple[Any, Any]]) -> Dict[Any, Any]:
    """``object_pairs_hook`` that raises on any duplicate JSON object key.

    A plain ``dict`` produced by ``json.loads`` can never expose duplicate
    keys (later keys silently win) -- this hook makes duplicate-key manifest
    JSON an explicit, detectable ``ManifestIntegrityError`` instead of a
    silent overwrite.
    """
    seen: set[Any] = set()
    result: Dict[Any, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ManifestIntegrityError(f"duplicate key in manifest JSON: {key!r}")
        seen.add(key)
        result[key] = value
    return result


class PersonaRepository:
    """Static, single-character persona module repository.

    Constructor is intentionally eager: the manifest is loaded and fully
    validated once, at construction time, and cached. There is no lazy
    re-read and no filesystem write of any kind.
    """

    def __init__(
        self,
        persona_root: Path,
        character_id: str,
        *,
        max_module_bytes: int = DEFAULT_MAX_MODULE_BYTES,
        max_manifest_entries: int = DEFAULT_MAX_MANIFEST_ENTRIES,
    ) -> None:
        self._persona_root = Path(persona_root)
        self._max_module_bytes = max_module_bytes
        self._max_manifest_entries = max_manifest_entries

        self._check_root_not_symlink()

        manifest_path = self._persona_root / "INDEX.json"
        self._check_no_symlink_in_relative_chain(("INDEX.json",))

        if not manifest_path.is_file():
            raise ManifestNotFoundError(
                f"manifest not found for injected persona_root (character_id={character_id!r})"
            )

        raw = manifest_path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ManifestParseError("manifest is not valid UTF-8") from None

        try:
            payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as exc:
            raise ManifestParseError(f"manifest is not valid JSON: {exc}") from None

        if not isinstance(payload, dict):
            raise ManifestIntegrityError("manifest root must be a JSON object")

        manifest_id = payload.get("id")
        manifest_name = payload.get("name")
        if not isinstance(manifest_id, str) or not manifest_id:
            raise ManifestIntegrityError("manifest.id missing or not a non-empty string")
        if not isinstance(manifest_name, str) or not manifest_name:
            raise ManifestIntegrityError("manifest.name missing or not a non-empty string")

        if character_id != manifest_id:
            raise CharacterNotFoundError(
                f"character_id {character_id!r} does not match injected persona root"
            )

        modules_raw = payload.get("modules")
        if not isinstance(modules_raw, dict):
            raise ManifestIntegrityError("manifest.modules missing or not a JSON object")

        if len(modules_raw) > self._max_manifest_entries:
            raise ManifestIntegrityError(
                f"manifest has {len(modules_raw)} entries, exceeds cap of "
                f"{self._max_manifest_entries}"
            )

        root_resolved = self._persona_root.resolve()
        seen_ids: set[str] = set()
        seen_resolved: set[Path] = set()
        modules: list[ModuleMetadata] = []
        lookup: Dict[str, ModuleMetadata] = {}

        for module_id, meta in modules_raw.items():
            if not isinstance(module_id, str) or not module_id:
                raise ManifestIntegrityError("module id must be a non-empty string")
            if module_id in seen_ids:
                raise ManifestIntegrityError(f"duplicate module id: {module_id!r}")
            seen_ids.add(module_id)

            self._validate_module_id_shape(module_id)

            relative_parts = tuple(module_id.split("/"))
            candidate = self._persona_root.joinpath(*relative_parts)
            resolved = candidate.resolve()

            if resolved in seen_resolved:
                raise ManifestIntegrityError(
                    f"duplicate resolved module path for id: {module_id!r}"
                )
            seen_resolved.add(resolved)

            if resolved != root_resolved and root_resolved not in resolved.parents:
                raise PathSecurityError(
                    f"manifest module path escapes persona root: {module_id!r}"
                )

            if not isinstance(meta, dict):
                raise ManifestIntegrityError(
                    f"module metadata must be a JSON object: {module_id!r}"
                )
            version = meta.get("version")
            if version is not None and not isinstance(version, str):
                raise ManifestIntegrityError(
                    f"module.version must be a string: {module_id!r}"
                )
            required = meta.get("required")
            if required is not None and not isinstance(required, bool):
                raise ManifestIntegrityError(
                    f"module.required must be a bool: {module_id!r}"
                )
            description = meta.get("description")
            if description is not None and not isinstance(description, str):
                raise ManifestIntegrityError(
                    f"module.description must be a string: {module_id!r}"
                )

            entry = ModuleMetadata(
                module_id=module_id,
                version=version,
                required=required,
                description=description,
            )
            modules.append(entry)
            lookup[module_id] = entry

        version = payload.get("version")
        schema_version = payload.get("schema_version")
        default_level = payload.get("default_level")
        default_ag_level = payload.get("default_ag_level")
        compatible_scenarios = payload.get("compatible_scenarios")

        self._character_id = manifest_id
        self._character_name = manifest_name
        self._module_lookup = lookup
        self._root_resolved = root_resolved
        self._manifest = CharacterManifest(
            id=manifest_id,
            name=manifest_name,
            version=version if isinstance(version, str) else None,
            schema_version=schema_version if isinstance(schema_version, str) else None,
            default_level=default_level if isinstance(default_level, str) else None,
            default_ag_level=(
                default_ag_level if isinstance(default_ag_level, int) else None
            ),
            compatible_scenarios=tuple(compatible_scenarios)
            if isinstance(compatible_scenarios, list)
            else (),
            modules=tuple(modules),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_characters(self) -> Tuple[CharacterRef, ...]:
        """Return the single injected character, derived from INDEX.json.

        No directory scan. No registry lookup. Exactly one entry.
        """
        return (CharacterRef(id=self._character_id, name=self._character_name),)

    def get_character_manifest(self, character_id: str) -> CharacterManifest:
        if character_id != self._character_id:
            raise CharacterNotFoundError(f"unknown character_id: {character_id!r}")
        return self._manifest

    def read_module(self, character_id: str, module_id: str) -> ModuleResult:
        if character_id != self._character_id:
            raise CharacterNotFoundError(f"unknown character_id: {character_id!r}")

        self._validate_module_id_shape(module_id)

        metadata = self._module_lookup.get(module_id)
        if metadata is None:
            raise PersonaModuleNotFoundError(
                f"module_id not allowlisted: {module_id!r}"
            )

        relative_parts = tuple(module_id.split("/"))
        self._check_no_symlink_in_relative_chain(relative_parts)

        candidate = self._persona_root.joinpath(*relative_parts)
        resolved = candidate.resolve()
        if resolved != self._root_resolved and self._root_resolved not in resolved.parents:
            raise PathSecurityError(
                f"module path escapes persona root: {module_id!r}"
            )

        if not resolved.is_file():
            raise PersonaModuleNotFoundError(
                f"allowlisted module file missing on disk: {module_id!r}"
            )

        size = resolved.stat().st_size
        if size > self._max_module_bytes:
            raise ModuleSizeLimitError(
                f"module exceeds max size of {self._max_module_bytes} bytes: {module_id!r}"
            )

        raw = resolved.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ModuleEncodingError(
                f"module is not valid UTF-8: {module_id!r}"
            ) from None

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModuleParseError(
                f"module is not valid JSON: {module_id!r} ({exc.msg})"
            ) from None

        provenance = build_module_provenance(
            character_id=self._character_id,
            module_id=module_id,
            raw_bytes=raw,
            version=metadata.version,
        )
        return ModuleResult(module_id=module_id, data=data, provenance=provenance)

    # ------------------------------------------------------------------
    # Internal security helpers
    # ------------------------------------------------------------------

    def _check_root_not_symlink(self) -> None:
        if self._persona_root.is_symlink():
            raise PathSecurityError("persona_root is a symlink")

    def _check_no_symlink_in_relative_chain(self, relative_parts: Tuple[str, ...]) -> None:
        """Reject a symlink at any path component between persona_root and
        the target (catches symlinked intermediate directories, not just a
        symlinked leaf file)."""
        current = self._persona_root
        for part in relative_parts:
            current = current / part
            if current.is_symlink():
                raise PathSecurityError(f"symlink detected in path component: {part!r}")

    @staticmethod
    def _validate_module_id_shape(module_id: str) -> None:
        if not isinstance(module_id, str) or not module_id or module_id.strip() != module_id:
            raise PathSecurityError("invalid module id")

        normalized = module_id.replace("\\", "/")

        if normalized.startswith("/"):
            raise PathSecurityError("absolute module id rejected")
        if _DRIVE_LETTER_ABS_RE.match(module_id):
            raise PathSecurityError("absolute module id rejected")

        parts = normalized.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise PathSecurityError("path traversal rejected")

        if not normalized.endswith(_ALLOWED_EXTENSION):
            raise UnsupportedExtensionError(
                f"unsupported extension for module id: {module_id!r}"
            )
