#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- VNE-owned alias resolution (deterministic).

Loads the two VNE-owned data files:

    authoring/scene_image_test_profiles/CHARACTER_NAME_ALIASES.json
    authoring/scene_image_test_profiles/LOCATION_ALIASES.json

and validates them fail-closed:

- character ids must exist in the VNE-owned roster
  (``authoring/scene_image_test_profiles/physical_profiles.json``);
- location ids must resolve against Location Canon
  (``scenarios/locations/<id>.json`` via ``services.location_canon``);
- no surface alias may map to more than one id (ambiguous alias => fail closed);
- provider aliases must be Latin-only and must not equal the internal id.

No live NCC read. No filename inference. Stdlib + Location Canon loader only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from services.location_canon import LocationCanonError, load_location

from .errors import AliasDataError, LocationResolutionError
from .hashing import match_key
from .model import AllowedCharacter, AllowedLocation

CHARACTER_ALIASES_REL = "authoring/scene_image_test_profiles/CHARACTER_NAME_ALIASES.json"
LOCATION_ALIASES_REL = "authoring/scene_image_test_profiles/LOCATION_ALIASES.json"
PHYSICAL_PROFILES_REL = "authoring/scene_image_test_profiles/physical_profiles.json"

CHARACTER_ALIASES_SCHEMA_VERSION = "vne_character_name_aliases/0.1"
LOCATION_ALIASES_SCHEMA_VERSION = "vne_location_aliases/0.1"


def _load_json_object(path: Path) -> dict:
    if not path.exists():
        raise AliasDataError(f"alias data file not found: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report cleanly, fail closed
        raise AliasDataError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise AliasDataError(f"{path.name}: root must be an object")
    return data


def _vne_roster_ids(repo_root: Path) -> set[str]:
    path = Path(repo_root) / PHYSICAL_PROFILES_REL
    data = _load_json_object(path)
    characters = data.get("characters")
    if not isinstance(characters, dict) or not characters:
        raise AliasDataError(f"{path.name}: 'characters' object missing or empty")
    return set(characters.keys())


def _is_latin(text: str) -> bool:
    return all(ord(ch) < 128 for ch in text)


def load_character_roster(
    repo_root: Path, *, path: Optional[Path] = None
) -> tuple[AllowedCharacter, ...]:
    """Load and fail-closed-validate the VNE-owned character alias table."""
    src = Path(path) if path is not None else Path(repo_root) / CHARACTER_ALIASES_REL
    data = _load_json_object(src)
    if data.get("schema_version") != CHARACTER_ALIASES_SCHEMA_VERSION:
        raise AliasDataError(
            f"{src.name}: schema_version must be {CHARACTER_ALIASES_SCHEMA_VERSION!r}"
        )
    entries = data.get("characters")
    if not isinstance(entries, list) or not entries:
        raise AliasDataError(f"{src.name}: 'characters' must be a non-empty array")

    roster_ids = _vne_roster_ids(repo_root)
    alias_owner: dict[str, str] = {}
    seen_ids: set[str] = set()
    out: list[AllowedCharacter] = []

    for i, raw in enumerate(entries):
        ctx = f"{src.name}.characters[{i}]"
        if not isinstance(raw, dict):
            raise AliasDataError(f"{ctx}: expected object")
        cid = raw.get("character_id")
        if not isinstance(cid, str) or not cid:
            raise AliasDataError(f"{ctx}.character_id: required non-empty string")
        if cid in seen_ids:
            raise AliasDataError(f"{ctx}: duplicate character_id {cid!r}")
        seen_ids.add(cid)
        if cid not in roster_ids:
            raise AliasDataError(
                f"{ctx}: character_id {cid!r} is not in the VNE roster "
                f"({PHYSICAL_PROFILES_REL})"
            )
        provider_alias = raw.get("provider_alias")
        if not isinstance(provider_alias, str) or not provider_alias.strip():
            raise AliasDataError(f"{ctx}.provider_alias: required non-empty string")
        if not _is_latin(provider_alias):
            raise AliasDataError(
                f"{ctx}.provider_alias {provider_alias!r}: must be Latin-only"
            )
        if provider_alias == cid:
            raise AliasDataError(
                f"{ctx}.provider_alias must differ from the internal character_id"
            )
        surface = raw.get("surface_aliases")
        if (
            not isinstance(surface, list)
            or not surface
            or not all(isinstance(s, str) and s.strip() for s in surface)
        ):
            raise AliasDataError(
                f"{ctx}.surface_aliases: required non-empty list of non-empty strings"
            )
        for alias in surface:
            key = match_key(alias)
            if not key:
                raise AliasDataError(f"{ctx}.surface_aliases: empty alias after normalize")
            prior = alias_owner.get(key)
            if prior is not None and prior != cid:
                raise AliasDataError(
                    f"{src.name}: ambiguous surface alias {alias!r} maps to both "
                    f"{prior!r} and {cid!r}"
                )
            alias_owner[key] = cid
        out.append(
            AllowedCharacter(
                character_id=cid,
                provider_alias=provider_alias,
                surface_aliases=tuple(surface),
            )
        )
    return tuple(out)


def load_location_roster(
    repo_root: Path, *, path: Optional[Path] = None
) -> tuple[AllowedLocation, ...]:
    """Load and fail-closed-validate the VNE-owned location alias table."""
    src = Path(path) if path is not None else Path(repo_root) / LOCATION_ALIASES_REL
    data = _load_json_object(src)
    if data.get("schema_version") != LOCATION_ALIASES_SCHEMA_VERSION:
        raise AliasDataError(
            f"{src.name}: schema_version must be {LOCATION_ALIASES_SCHEMA_VERSION!r}"
        )
    entries = data.get("locations")
    if not isinstance(entries, list) or not entries:
        raise AliasDataError(f"{src.name}: 'locations' must be a non-empty array")

    alias_owner: dict[str, str] = {}
    seen_ids: set[str] = set()
    out: list[AllowedLocation] = []

    for i, raw in enumerate(entries):
        ctx = f"{src.name}.locations[{i}]"
        if not isinstance(raw, dict):
            raise AliasDataError(f"{ctx}: expected object")
        lid = raw.get("location_id")
        if not isinstance(lid, str) or not lid:
            raise AliasDataError(f"{ctx}.location_id: required non-empty string")
        if lid in seen_ids:
            raise AliasDataError(f"{ctx}: duplicate location_id {lid!r}")
        seen_ids.add(lid)
        try:
            load_location(Path(repo_root), lid)
        except LocationCanonError as exc:
            raise AliasDataError(
                f"{ctx}: location_id {lid!r} does not resolve against Location Canon: {exc}"
            ) from exc
        surface = raw.get("surface_aliases")
        if (
            not isinstance(surface, list)
            or not surface
            or not all(isinstance(s, str) and s.strip() for s in surface)
        ):
            raise AliasDataError(
                f"{ctx}.surface_aliases: required non-empty list of non-empty strings"
            )
        for alias in surface:
            key = match_key(alias)
            if not key:
                raise AliasDataError(f"{ctx}.surface_aliases: empty alias after normalize")
            prior = alias_owner.get(key)
            if prior is not None and prior != lid:
                raise AliasDataError(
                    f"{src.name}: ambiguous surface alias {alias!r} maps to both "
                    f"{prior!r} and {lid!r}"
                )
            alias_owner[key] = lid
        out.append(AllowedLocation(location_id=lid, surface_aliases=tuple(surface)))
    return tuple(out)


# ---------------------------------------------------------------------------
# Deterministic resolution.
# ---------------------------------------------------------------------------


def resolve_character(span: str, roster: tuple[AllowedCharacter, ...]) -> Optional[str]:
    """Resolve one surface span to exactly one allowed character_id, or None.

    A span matches a character iff any of that character's surface aliases is a
    substring of the span's match key (so inflected mentions like "Марину" or a
    quoted "«Марина»" still resolve). If the span matches more than one distinct
    character, resolution is ambiguous and returns None (caller fails closed).
    """
    key = match_key(span)
    if not key:
        return None
    hits: set[str] = set()
    for entry in roster:
        for alias in entry.surface_aliases:
            if match_key(alias) in key:
                hits.add(entry.character_id)
                break
    if len(hits) == 1:
        return next(iter(hits))
    return None


def resolve_location(
    *,
    source_match_key: str,
    location_span: str,
    roster: tuple[AllowedLocation, ...],
) -> str:
    """Resolve the scene location deterministically, fail closed.

    - the proposed ``location_span`` must contain an alias of exactly one
      location;
    - the FULL source is additionally scanned: if an alias of a *different*
      location also occurs anywhere in the source, resolution is ambiguous.
    """
    span_key = match_key(location_span)
    span_hits: set[str] = set()
    source_hits: set[str] = set()
    for entry in roster:
        for alias in entry.surface_aliases:
            akey = match_key(alias)
            if akey and akey in span_key:
                span_hits.add(entry.location_id)
            if akey and akey in source_match_key:
                source_hits.add(entry.location_id)

    if not span_hits:
        raise LocationResolutionError(
            f"location span {location_span!r} does not match any known location alias"
        )
    if len(span_hits) > 1:
        raise LocationResolutionError(
            f"location span {location_span!r} is ambiguous: {sorted(span_hits)}"
        )
    resolved = next(iter(span_hits))
    other = source_hits - {resolved}
    if other:
        raise LocationResolutionError(
            f"ambiguous location: source also mentions {sorted(other)} besides "
            f"{resolved!r}"
        )
    return resolved
