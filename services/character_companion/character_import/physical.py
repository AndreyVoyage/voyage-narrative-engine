#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure physical-identity normalization from an NCC reference-preset payload.

Reads ONLY the machine-readable ``identity_summary`` / top-level lists of a
Character Canon ``*_REFERENCE_PRESETS.json`` payload and returns a deterministic
structured physical-profile record. No prose docs / markdown / notes are read.

Vendoring note: the normalization functions (``_normalize_height``,
``_normalize_weight``, ``normalize_preset``) are extracted VERBATIM from
``tools/build_physical_profiles.py`` in the VNE repo. Only the CLI shell
(argparse, repo globals, default output path, ``main``/``discover_preset_paths``
/``build_snapshot``/``serialize_snapshot``) was left behind -- this slice needs
only the structured data, and prompt rendering belongs to a later slice.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .errors import AmbiguousCharacterError

_CM_RE = re.compile(r"(\d+)\s*cm", re.IGNORECASE)
_APPROX_RE = re.compile(r"around|approximately", re.IGNORECASE)


def _str_or(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _opt_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _is_owner_approved_exact(identity: dict) -> bool:
    status = identity.get("height_status")
    return isinstance(status, str) and "OWNER_APPROVED" in status.upper()


def _normalize_height(identity: dict) -> tuple[Optional[int], bool]:
    """Return ``(height_cm, height_is_approx)``.

    1. numeric ``height_cm`` when present -> exact;
    2. else parse an explicit ``NNN cm`` token from ``height`` / ``height_direction``;
    3. ``around``/``approximately`` wording -> approximate;
    4. otherwise prose-derived numbers are approximate unless an owner-approved
       exact-status field proves otherwise.
    """
    height_cm = identity.get("height_cm")
    if isinstance(height_cm, (int, float)) and not isinstance(height_cm, bool):
        return int(height_cm), False

    for key in ("height", "height_direction"):
        raw = identity.get(key)
        if not isinstance(raw, str):
            continue
        match = _CM_RE.search(raw)
        if not match:
            continue
        cm = int(match.group(1))
        if _APPROX_RE.search(raw):
            return cm, True
        if _is_owner_approved_exact(identity):
            return cm, False
        return cm, True

    return None, False


def _normalize_weight(identity: dict) -> tuple[Optional[float], Optional[str]]:
    """Return ``(weight_kg, weight_direction)``.

    Numeric ``weight_kg`` is used only when explicitly present;
    ``weight_direction`` is preserved verbatim only when explicitly present.
    Body-direction prose is never mined for a synthetic weight.
    """
    weight_kg = identity.get("weight_kg")
    if isinstance(weight_kg, (int, float)) and not isinstance(weight_kg, bool):
        weight_kg = float(weight_kg)
    else:
        weight_kg = None
    weight_direction = _opt_str(identity.get("weight_direction"))
    return weight_kg, weight_direction


def physical_profile_from_preset(
    preset: dict, character_id: str, *, source_preset_sha256: str
) -> dict:
    """Normalize one preset payload into a structured physical-profile record.

    ``source_preset_sha256`` binds the record to the exact source bytes it was
    derived from. Raises :class:`AmbiguousCharacterError` on an id mismatch.
    """
    declared = preset.get("character")
    if declared != character_id:
        raise AmbiguousCharacterError(
            f"character mismatch: requested {character_id!r} but preset declares {declared!r}"
        )

    identity = preset.get("identity_summary")
    if not isinstance(identity, dict):
        identity = {}

    height_cm, height_is_approx = _normalize_height(identity)
    weight_kg, weight_direction = _normalize_weight(identity)

    return {
        "character_id": character_id,
        "role": _str_or(identity.get("role")),
        "height_cm": height_cm,
        "height_is_approx": height_is_approx,
        "height_direction": _opt_str(identity.get("height_direction")),
        "weight_kg": weight_kg,
        "weight_direction": weight_direction,
        "body_direction": _str_or(identity.get("body_direction")),
        "face_direction": _str_or(identity.get("face_direction")),
        "hair_direction": _str_or(identity.get("hair_direction")),
        "style_direction_raw": _opt_str(identity.get("style_direction")),
        "confirmed_traits": _str_list(preset.get("identity_confirmed_traits")),
        "safety_rules": _str_list(preset.get("safety_rules")),
        "source_preset_sha256": source_preset_sha256,
    }
