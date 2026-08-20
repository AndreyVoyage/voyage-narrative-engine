#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Location Canon v0 -- deterministic loader.

Loads a canonical location JSON file from the repository-local,
explicitly-controlled ``scenarios/locations/`` directory, validates it, and
produces a deeply immutable ``LocationCanon`` with a deterministic semantic
``content_hash`` and portable (repository-relative) provenance.

Stdlib-only, no network, no caching, no persistence, no database.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

from .errors import (
    LocationCanonSourceError,
    LocationCanonValidationError,
    LocationNotFoundError,
)
from .hashing import compute_content_hash, compute_source_hash
from .model import FixedFeature, LocationCanon, Provenance

# The Location Canon envelope's own contract/format version.
LOCATION_CANON_SCHEMA_VERSION = "location/0.1"

# Lowercase slug, mirrors the existing lowercase-id convention in scenario
# JSON ("kira", "sergey") and ``visual_asset_registry.ASSET_ID_RE``.
LOCATION_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

_CANONICAL_DIR = ("scenarios", "locations")

_REQUIRED_SOURCE_FIELDS = (
    "schema_version",
    "location_id",
    "tier",
    "scale",
    "identity",
    "palette",
    "fixed_features",
)


def default_locations_dir(repo_root: Path) -> Path:
    """Return the canonical locations directory for a repo root."""
    return Path(repo_root).joinpath(*_CANONICAL_DIR)


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise LocationCanonValidationError(f"{field}: required non-empty string")
    return value


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise LocationCanonValidationError(f"{field}: expected array of strings")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_require_non_empty_string(item, f"{field}[{index}]"))
    return result


def _parse_fixed_features(value: Any) -> list[FixedFeature]:
    if not isinstance(value, list) or not value:
        raise LocationCanonValidationError("fixed_features: expected non-empty array")

    features: list[FixedFeature] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"fixed_features[{index}]"
        if not isinstance(item, dict):
            raise LocationCanonValidationError(f"{prefix}: expected object")

        feature_id = _require_non_empty_string(item.get("feature_id"), f"{prefix}.feature_id")
        label = _require_non_empty_string(item.get("label"), f"{prefix}.label")
        if feature_id in seen:
            raise LocationCanonValidationError(f"duplicate fixed feature id: {feature_id}")
        seen.add(feature_id)

        count = item.get("count")
        if count is not None:
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise LocationCanonValidationError(f"{prefix}.count: expected positive integer")
        features.append(FixedFeature(feature_id=feature_id, label=label, count=count))
    return features


def _load_source_json(source_path: Path) -> dict[str, Any]:
    if not source_path.exists():
        raise LocationNotFoundError(f"location source not found: {source_path.name}")
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LocationCanonSourceError(f"invalid JSON in {source_path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise LocationCanonSourceError(f"location source root must be an object: {source_path.name}")
    return data


def _build_from_payload(
    payload: dict[str, Any],
    *,
    source_ref: str,
) -> LocationCanon:
    """Validate a parsed canonical location JSON and build a LocationCanon."""
    for field in _REQUIRED_SOURCE_FIELDS:
        if field not in payload:
            raise LocationCanonValidationError(f"{field}: required field missing")

    schema_version = _require_non_empty_string(payload.get("schema_version"), "schema_version")
    if schema_version != LOCATION_CANON_SCHEMA_VERSION:
        raise LocationCanonValidationError(
            f"schema_version: expected {LOCATION_CANON_SCHEMA_VERSION!r}"
        )

    location_id = _require_non_empty_string(payload.get("location_id"), "location_id")
    if not LOCATION_ID_RE.match(location_id):
        raise LocationCanonValidationError(
            "location_id: expected lowercase slug [a-z][a-z0-9_]{2,63}"
        )

    tier = _require_non_empty_string(payload.get("tier"), "tier")
    scale = _require_string_list(payload.get("scale"), "scale")
    identity = _require_string_list(payload.get("identity"), "identity")
    palette = _require_string_list(payload.get("palette"), "palette")
    fixed_features = _parse_fixed_features(payload.get("fixed_features"))

    provenance = Provenance(
        source_kind="location_canon_v0_json",
        source_ref=source_ref,
        source_hash=compute_source_hash(payload),
        source_schema_version=schema_version,
    )

    provisional = LocationCanon(
        schema_version=schema_version,
        location_id=location_id,
        tier=tier,
        scale=tuple(scale),
        identity=tuple(identity),
        palette=tuple(palette),
        fixed_features=tuple(fixed_features),
        content_hash="",
        provenance=provenance,
    )
    content_hash = compute_content_hash(provisional.semantic_payload())
    return dataclasses.replace(provisional, content_hash=content_hash)


def load_location(
    repo_root: Path,
    location_id: str,
) -> LocationCanon:
    """Load one canonical location by stable ``location_id``.

    ``source_ref`` is constructed repository-relative and never contains an
    absolute machine path.
    """
    locations_dir = default_locations_dir(repo_root)
    source_path = locations_dir / f"{location_id}.json"
    source_ref = f"scenarios/locations/{location_id}.json"
    payload = _load_source_json(source_path)

    declared_id = payload.get("location_id")
    if declared_id != location_id:
        raise LocationCanonValidationError(
            f"location_id mismatch: requested {location_id!r} but file declares {declared_id!r}"
        )

    return _build_from_payload(payload, source_ref=source_ref)