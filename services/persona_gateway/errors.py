#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exception hierarchy for the N7 Persona Data Gateway (P1a-S1 partial runtime).

All exceptions here are domain-level, transport-independent errors raised by
``services/persona_gateway``. Messages must never include raw module content,
secrets, or absolute local filesystem paths -- only relative/logical
identifiers (character_id, module_id, manifest field names) may appear.

This module intentionally does not define:
  * ``ModuleNotFoundError`` -- would collide with the Python builtin of the
    same name (raised by the import system), which could be accidentally
    caught by generic ``except ModuleNotFoundError`` handlers elsewhere.
  * ``ModuleSchemaError`` -- P1a-S1 uses JSON_PARSE_ONLY_WITH_STRUCTURAL_
    MANIFEST_VALIDATION (no per-module jsonschema validation), so this slice
    has no caller for a dedicated schema-validation error.
  * ``PolicyUnavailableError`` -- AD policy is excluded entirely from this
    slice; defining it now would be dead code with no caller.
"""

from __future__ import annotations


class PersonaGatewayError(Exception):
    """Root of the Persona Data Gateway exception hierarchy."""


class ManifestNotFoundError(PersonaGatewayError):
    """Raised when a character's INDEX.json manifest cannot be found."""


class ManifestParseError(PersonaGatewayError):
    """Raised when INDEX.json is not valid UTF-8 or not valid JSON."""


class ManifestIntegrityError(PersonaGatewayError):
    """Raised for structurally unsound manifests.

    Covers: missing/invalid required manifest fields, duplicate module ids,
    duplicate resolved module paths, manifest entries exceeding the
    configured cap, and injected character_id disagreeing with
    ``INDEX.json["id"]`` at load time.
    """


class CharacterNotFoundError(PersonaGatewayError):
    """Raised when a requested character_id is not the injected character."""


class PersonaModuleNotFoundError(PersonaGatewayError):
    """Raised when a module_id is not allowlisted, or the allowlisted file
    is missing on disk."""


class ModuleEncodingError(PersonaGatewayError):
    """Raised when a module file is not valid UTF-8."""


class ModuleParseError(PersonaGatewayError):
    """Raised when a module file is not valid JSON."""


class PathSecurityError(PersonaGatewayError):
    """Raised when a path fails a security invariant: absolute path,
    traversal, symlink, or resolved-path containment escape."""


class UnsupportedExtensionError(PersonaGatewayError):
    """Raised when a module id/path does not carry an allowlisted
    extension (``.json`` only, for this slice)."""


class ModuleSizeLimitError(PersonaGatewayError):
    """Raised when a module file exceeds the configured maximum byte size."""


class SnapshotUnavailableError(PersonaGatewayError):
    """Raised when no saved aside/session state exists for the requested
    character/slot/progress."""


class HistoryNotFoundError(PersonaGatewayError):
    """Raised when no saved aside/session history exists at all for the
    requested character/slot (distinct from a zero-match search)."""


class HistoryRecordError(PersonaGatewayError):
    """Raised when a stored session record or transcript entry returned by
    the underlying read API is malformed in a way this service cannot
    safely interpret."""
