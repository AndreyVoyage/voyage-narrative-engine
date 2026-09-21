"""NFC-normalized semantic hashing for Character Authoring snapshots."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping
from typing import Any

from .errors import CharacterAuthoringValidationError

SEMANTIC_SCHEMA_VERSION = "character_authoring_semantic/0.1"


def normalize_json_value(value: Any) -> Any:
    """Recursively validate JSON compatibility and NFC-normalize text.

    Dictionary keys are normalized as well as values. A normalization-induced
    key collision is rejected instead of silently discarding one value.
    """
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CharacterAuthoringValidationError(
                "semantic JSON cannot contain NaN or infinity"
            )
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CharacterAuthoringValidationError(
                    "semantic JSON object keys must be strings"
                )
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise CharacterAuthoringValidationError(
                    f"NFC normalization creates duplicate key {normalized_key!r}"
                )
            normalized[normalized_key] = normalize_json_value(item)
        return normalized
    raise CharacterAuthoringValidationError(
        f"value of type {type(value).__name__} is not JSON-compatible"
    )


def _as_semantic_dict(semantic: Any) -> dict[str, Any]:
    if hasattr(semantic, "to_dict"):
        semantic = semantic.to_dict()
    normalized = normalize_json_value(semantic)
    if not isinstance(normalized, dict):
        raise CharacterAuthoringValidationError("semantic snapshot must be an object")
    return normalized


def canonical_semantic_payload(semantic: Any) -> dict[str, Any]:
    """Return the exact conceptual object used as the snapshot hash input."""
    return {
        "semantic_schema_version": SEMANTIC_SCHEMA_VERSION,
        "semantic": _as_semantic_dict(semantic),
    }


def canonical_semantic_json(semantic: Any) -> str:
    """Serialize the hash payload exactly as ratified, with no final newline."""
    return json.dumps(
        canonical_semantic_payload(semantic),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
    )


def compute_snapshot_hash(semantic: Any) -> str:
    return hashlib.sha256(canonical_semantic_json(semantic).encode("utf-8")).hexdigest()
