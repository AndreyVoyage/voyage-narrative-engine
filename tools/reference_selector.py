#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene-Aware Reference Selector v0 (SARS).

Deterministic, bounded automatic selection of already-imported VNE Reference
Library assets from a VNE-owned semantic catalog.

- No LLM, no NCC runtime read, no filename/path inference, no provider.
- The catalog is a sparse eligibility allowlist; Library assets without a
  catalog entry are simply not eligible for automatic selection.
- Unknown semantic roles are preserved and ignored unless explicitly
  recognised here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

CATALOG_SCHEMA_VERSION = "vne_reference_semantic_catalog/0.1"

# Provider-facing selection roles recognised in v0.
ROLE_FACE = "face"
ROLE_BODY = "body"
ROLE_EXPRESSION = "expression"
ROLE_MOTION = "motion"

# Missing priority sorts last (weakest).
_MISSING_PRIORITY = 1 << 30

_MAX_SELECTED_PER_CHARACTER = 4
_MIN_SELECTED_PER_CHARACTER = 2


class CatalogError(ValueError):
    """Semantic catalog is malformed or inconsistent with the Library."""


class SelectionError(ValueError):
    """Automatic selection could not satisfy a required reference."""


@dataclass(frozen=True)
class CatalogEntry:
    asset_id: str
    character_id: str
    semantic_roles: tuple[str, ...]
    scene_tags: tuple[str, ...]
    priority: int
    source_semantic_key: Optional[str] = None


def _stable_unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _required_key(entry: CatalogEntry):
    """Face/body rank: priority ASC, identity preferred, asset_id ASC."""
    return (
        entry.priority,
        0 if "identity" in entry.semantic_roles else 1,
        entry.asset_id,
    )


def _support_key(entry: CatalogEntry):
    """Face-support rank: expression preferred, priority ASC, asset_id ASC."""
    return (
        0 if ROLE_EXPRESSION in entry.semantic_roles else 1,
        entry.priority,
        entry.asset_id,
    )


def _motion_key(entry: CatalogEntry, tag_set: set[str]):
    """Motion rank: tag overlap DESC, priority ASC, asset_id ASC."""
    return (
        -len(set(entry.scene_tags) & tag_set),
        entry.priority,
        entry.asset_id,
    )


def load_semantic_catalog(
    catalog_path: Path, library_records: Sequence[Any]
) -> list[CatalogEntry]:
    """Load and validate the catalog against the Library manifest records.

    Fail closed on malformed schema, duplicate asset_id, asset_id absent from
    the manifest, ownership mismatch, empty semantic_roles, malformed
    scene_tags, or invalid priority type.
    """
    try:
        data = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise CatalogError(f"cannot read semantic catalog: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError("catalog root must be an object")
    if data.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogError(f"schema_version must be {CATALOG_SCHEMA_VERSION!r}")

    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        raise CatalogError("entries must be an array")

    lib_by_id = {record.asset_id: record for record in library_records}
    entries: list[CatalogEntry] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_entries):
        prefix = f"entries[{index}]"
        if not isinstance(raw, dict):
            raise CatalogError(f"{prefix}: expected object")

        asset_id = raw.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise CatalogError(f"{prefix}.asset_id: required non-empty string")
        if asset_id in seen_ids:
            raise CatalogError(f"duplicate catalog asset_id {asset_id!r}")
        seen_ids.add(asset_id)

        character_id = raw.get("character_id")
        if not isinstance(character_id, str) or not character_id:
            raise CatalogError(f"{prefix}.character_id: required non-empty string")

        record = lib_by_id.get(asset_id)
        if record is None:
            raise CatalogError(
                f"catalog asset_id {asset_id!r} missing from Reference Library manifest"
            )
        if record.character_id != character_id:
            raise CatalogError(
                f"catalog character_id {character_id!r} != manifest "
                f"{record.character_id!r} for {asset_id!r}"
            )

        roles = raw.get("semantic_roles")
        if (
            not isinstance(roles, list)
            or not roles
            or not all(isinstance(r, str) and r for r in roles)
        ):
            raise CatalogError(
                f"{prefix}.semantic_roles: required non-empty list of non-empty strings"
            )

        tags = raw.get("scene_tags")
        if not isinstance(tags, list) or not all(isinstance(t, str) and t for t in tags):
            raise CatalogError(
                f"{prefix}.scene_tags: required list of non-empty strings"
            )

        priority = raw.get("priority")
        if priority is None:
            priority = _MISSING_PRIORITY
        elif not isinstance(priority, int) or isinstance(priority, bool):
            raise CatalogError(f"{prefix}.priority: must be an integer")

        key = raw.get("source_semantic_key")
        if key is not None and not isinstance(key, str):
            raise CatalogError(
                f"{prefix}.source_semantic_key: must be a string when present"
            )

        entries.append(
            CatalogEntry(
                asset_id=asset_id,
                character_id=character_id,
                semantic_roles=tuple(roles),
                scene_tags=tuple(tags),
                priority=priority,
                source_semantic_key=key if key else None,
            )
        )

    return entries


def _sha_of(lib_by_id: dict, asset_id: str) -> str:
    return lib_by_id[asset_id].sha256


def select_references(
    character_ids: Sequence[str],
    location_id: str,
    scene_tags: Sequence[str],
    library_records: Sequence[Any],
    catalog: Sequence[CatalogEntry],
) -> tuple[dict[str, list[Any]], dict[str, tuple[str, ...]]]:
    """Deterministically select references for each character.

    Returns ``(selected_records_by_character, roles_by_asset_id)`` for the
    existing Library -> ReferenceBundle adapter. Selection order per character
    is: face, body, optional face/expression support, optional motion support.
    """
    lib_by_id = {record.asset_id: record for record in library_records}
    effective_tags = _stable_unique([location_id] + list(scene_tags))
    tag_set = set(effective_tags)

    selected_records_by_character: dict[str, list[Any]] = {}
    roles_by_asset_id: dict[str, tuple[str, ...]] = {}

    for cid in character_ids:
        entries = [e for e in catalog if e.character_id == cid]
        chosen_asset_ids: list[str] = []
        chosen_shas: set[str] = set()

        def add(entry: CatalogEntry, role: str) -> None:
            if entry.asset_id in chosen_asset_ids:
                return
            record = lib_by_id[entry.asset_id]
            if record.sha256 in chosen_shas:
                return
            chosen_asset_ids.append(entry.asset_id)
            chosen_shas.add(record.sha256)
            roles_by_asset_id[entry.asset_id] = (role,)

        # STEP 1 — face (required)
        face_pool = [e for e in entries if ROLE_FACE in e.semantic_roles]
        if not face_pool:
            raise SelectionError(f"no face reference for {cid!r}")
        add(min(face_pool, key=_required_key), ROLE_FACE)

        # STEP 2 — body (required)
        body_pool = [
            e
            for e in entries
            if ROLE_BODY in e.semantic_roles and e.asset_id not in chosen_asset_ids
        ]
        if not body_pool:
            raise SelectionError(f"no body reference for {cid!r}")
        add(min(body_pool, key=_required_key), ROLE_BODY)

        # STEP 3 — face/expression support (optional)
        support_pool = [
            e
            for e in entries
            if ROLE_FACE in e.semantic_roles
            and e.asset_id not in chosen_asset_ids
            and _sha_of(lib_by_id, e.asset_id) not in chosen_shas
        ]
        if support_pool:
            support = min(support_pool, key=_support_key)
            role = (
                ROLE_EXPRESSION
                if ROLE_EXPRESSION in support.semantic_roles
                else ROLE_FACE
            )
            add(support, role)

        # STEP 4 — scene/motion support (optional, at most one)
        motion_pool = [
            e
            for e in entries
            if ROLE_MOTION in e.semantic_roles
            and e.asset_id not in chosen_asset_ids
            and e.scene_tags
            and (set(e.scene_tags) & tag_set)
            and _sha_of(lib_by_id, e.asset_id) not in chosen_shas
        ]
        if motion_pool:
            add(min(motion_pool, key=lambda e: _motion_key(e, tag_set)), ROLE_MOTION)

        # Bounds: 2..4 selected per character, stable order preserved.
        if len(chosen_asset_ids) < _MIN_SELECTED_PER_CHARACTER:
            raise SelectionError(
                f"fewer than {_MIN_SELECTED_PER_CHARACTER} references for {cid!r}"
            )
        selected = [
            lib_by_id[asset_id]
            for asset_id in chosen_asset_ids[:_MAX_SELECTED_PER_CHARACTER]
        ]
        selected_records_by_character[cid] = selected

    return selected_records_by_character, roles_by_asset_id
