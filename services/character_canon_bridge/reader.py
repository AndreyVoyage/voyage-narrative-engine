#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Canon Read Bridge v0 -- read-only bridge.

Reads the authoritative per-character ``*_REFERENCE_PRESETS.json`` from an
explicitly caller-supplied Character Canon root, resolves exact stable
identity and status, and produces a deeply immutable, deterministic snapshot
with portable (repository-relative) provenance and reference paths.

Stdlib-only. This module performs ZERO writes to Character Canon.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

from .errors import (
    AmbiguousCharacterError,
    CanonFormatError,
    CanonRootMissingError,
    CanonStatusUnknownError,
    CharacterNotFoundError,
    ProductionNotAllowedError,
    ReferencePathSafetyError,
    UnsupportedUsageContextError,
)
from .hashing import compute_content_hash, compute_source_hash
from .model import CanonReference, CharacterCanonSnapshot, Provenance
from .status import is_known_canon_status, is_production_approved

SNAPSHOT_SCHEMA_VERSION = "character_canon/0.1"

# Authoritative source layout under the Character Canon root.
_PRESET_REL_DIR = ("AI_CHARACTERS",)

# Supported usage contexts.
_USAGE_CONTEXTS = frozenset({"draft", "authoring", "production"})


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise CanonFormatError(f"{field}: required non-empty string")
    return value


def _is_safe_relative(path: str) -> bool:
    """Return True if ``path`` is repo-relative, forward-slash, traversal-free."""
    if not path:
        return False
    if path.startswith("/") or path.startswith("\\"):
        return False
    if re.match(r"^[A-Za-z]:", path):
        return False
    parts = path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    if any(p in ("", ".") for p in parts):
        return False
    return True


def _collect_references(preset: dict[str, Any]) -> list[CanonReference]:
    references: list[CanonReference] = []
    seen_keys: set[str] = set()

    active_canon = preset.get("active_canon")
    if isinstance(active_canon, dict):
        for key, value in active_canon.items():
            if not isinstance(key, str):
                raise CanonFormatError("active_canon key: expected string")
            if not isinstance(value, str):
                raise CanonFormatError(f"active_canon.{key}: expected string path")
            if not _is_safe_relative(value):
                raise ReferencePathSafetyError(f"unsafe active_canon reference: {value!r}")
            if key in seen_keys:
                raise CanonFormatError(f"duplicate active_canon key: {key}")
            seen_keys.add(key)
            references.append(CanonReference(key=key, path=value))

    scene_presets = preset.get("scene_presets")
    if isinstance(scene_presets, dict):
        for key, value in scene_presets.items():
            if not isinstance(key, str):
                raise CanonFormatError("scene_presets key: expected string")
            if not isinstance(value, dict):
                raise CanonFormatError(f"scene_presets.{key}: expected object")
            images = value.get("reference_images")
            if images is None:
                continue
            if not isinstance(images, list):
                raise CanonFormatError(f"scene_presets.{key}.reference_images: expected array")
            for index, image in enumerate(images):
                if not isinstance(image, str):
                    raise CanonFormatError(
                        f"scene_presets.{key}.reference_images[{index}]: expected string path"
                    )
                if not _is_safe_relative(image):
                    raise ReferencePathSafetyError(f"unsafe scene_presets reference: {image!r}")
                ref_key = f"scene:{key}:{index}"
                if ref_key in seen_keys:
                    continue
                seen_keys.add(ref_key)
                references.append(CanonReference(key=ref_key, path=image))

    return references


def _read_preset(canon_root: Path, character_id: str) -> tuple[dict[str, Any], str]:
    """Read and parse the authoritative reference-presets JSON for a character.

    Returns ``(payload, source_ref)`` where ``source_ref`` is repository-relative
    (relative to the Character Canon root).
    """
    if not canon_root.exists():
        raise CanonRootMissingError("Character Canon root does not exist")

    # Character ID resolves exactly to the canonical uppercase folder name.
    folder = canon_root.joinpath(*_PRESET_REL_DIR).joinpath(character_id)
    preset_path = folder / "10_notes" / f"{character_id}_REFERENCE_PRESETS.json"
    source_ref = f"AI_CHARACTERS/{character_id}/10_notes/{character_id}_REFERENCE_PRESETS.json"

    if not preset_path.exists():
        raise CharacterNotFoundError(f"no authoritative Canon entry for {character_id!r}")

    try:
        payload = json.loads(preset_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CanonFormatError(f"invalid Canon JSON for {character_id!r}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CanonFormatError(f"Canon entry for {character_id!r} is not an object")
    return payload, source_ref


def read_character_canon(
    canon_root: Path,
    character_id: str,
    usage_context: str,
) -> CharacterCanonSnapshot:
    """Read one character's authoritative Canon state and return a snapshot.

    ``canon_root`` is supplied explicitly by the caller; it is never
    hard-coded. The bridge performs zero writes to Character Canon.

    ``usage_context`` gates production: ``draft``/``authoring`` are allowed
    regardless of status; ``production`` requires the canonical production
    status ``APPROVED_AS_CANON``, otherwise it fails closed.
    """
    if usage_context not in _USAGE_CONTEXTS:
        raise UnsupportedUsageContextError(
            f"usage_context must be one of {sorted(_USAGE_CONTEXTS)}"
        )

    character_id = _non_empty_string(character_id, "character_id")

    # Exact resolution: no case-folding, no alias guessing. The authoritative
    # canonical directory uses the uppercase underscore ID.
    payload, source_ref = _read_preset(canon_root, character_id)

    declared = payload.get("character")
    if declared != character_id:
        raise AmbiguousCharacterError(
            f"character_id mismatch: requested {character_id!r} but source declares {declared!r}"
        )

    status = _non_empty_string(payload.get("status"), "status")
    if not is_known_canon_status(status):
        raise CanonStatusUnknownError(f"unknown Canon status {status!r}")

    if usage_context == "production" and not is_production_approved(status):
        raise ProductionNotAllowedError(
            f"production use not allowed for {character_id!r} (status {status!r})"
        )

    references = _collect_references(payload)
    active_version = payload.get("active_version")
    if active_version is not None:
        active_version = _non_empty_string(active_version, "active_version")

    provenance = Provenance(
        source_kind="character_canon_reference_presets",
        source_ref=source_ref,
        source_hash=compute_source_hash(payload),
    )

    provisional = CharacterCanonSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        character_id=character_id,
        status=status,
        references=tuple(references),
        content_hash="",
        provenance=provenance,
        active_version=active_version,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)