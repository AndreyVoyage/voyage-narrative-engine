"""Canonical byte and hash contract for Authoring Runtime Package V1."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from services.character_authoring import CharacterAuthoringValidationError
from services.character_authoring.hashing import normalize_json_value

from .errors import PublicationValidationError
from .model import AuthoringRuntimePackage


def canonical_runtime_package_bytes(
    package: AuthoringRuntimePackage | Mapping[str, Any],
) -> bytes:
    """Return exact NFC-normalized canonical UTF-8 bytes with no newline."""

    payload: Any = package.to_dict() if isinstance(package, AuthoringRuntimePackage) else package
    try:
        normalized = normalize_json_value(payload)
        if not isinstance(normalized, dict):
            raise PublicationValidationError("runtime package payload must be an object")
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        return serialized.encode("utf-8")
    except PublicationValidationError:
        raise
    except (CharacterAuthoringValidationError, TypeError, ValueError, UnicodeError) as exc:
        raise PublicationValidationError(
            "runtime package cannot be represented as canonical JSON"
        ) from exc


def compute_package_hash(
    package: AuthoringRuntimePackage | Mapping[str, Any],
) -> str:
    return hashlib.sha256(canonical_runtime_package_bytes(package)).hexdigest()


__all__ = ["canonical_runtime_package_bytes", "compute_package_hash"]
