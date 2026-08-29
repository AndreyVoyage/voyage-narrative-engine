#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Physical Profiles offline snapshot generator (SITA-PHYS v0).

Reads machine-readable NCC reference-preset JSON only, from:

    AI_CHARACTERS/*/10_notes/*_REFERENCE_PRESETS.json

and emits a deterministic, VNE-owned physical identity snapshot:

    authoring/scene_image_test_profiles/physical_profiles.json

The runner reads ONLY this snapshot at preview/generation time. NCC remains
read-only; nothing is written back into NCC. No prompt docs / markdown / notes
are read. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

SNAPSHOT_SCHEMA_VERSION = "vne_physical_profiles/0.1"

_CM_RE = re.compile(r"(\d+)\s*cm", re.IGNORECASE)
_APPROX_RE = re.compile(r"around|approximately", re.IGNORECASE)

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    _REPO_ROOT / "authoring" / "scene_image_test_profiles" / "physical_profiles.json"
)


class CharacterMismatchError(ValueError):
    """The preset's declared ``character`` does not match its directory name."""


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
    """Return ``(height_cm, height_is_approx)`` per OD-SITA-PHYS-03.

    1. Use numeric ``height_cm`` when present (exact).
    2. Else parse an explicit ``NNN cm`` token from ``height`` or
       ``height_direction``.
    3. ``around``/``approximately`` wording -> approximate.
    4. Otherwise a prose-derived number is approximate unless an owner-approved
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
    """Return ``(weight_kg, weight_direction)`` per OD-SITA-PHYS-04.

    Numeric ``weight_kg`` is used only when explicitly present;
    ``weight_direction`` is preserved verbatim only when explicitly present.
    Body-direction prose is never mined for a synthetic weight in v0.
    """
    weight_kg = identity.get("weight_kg")
    if isinstance(weight_kg, (int, float)) and not isinstance(weight_kg, bool):
        weight_kg = float(weight_kg)
    else:
        weight_kg = None
    weight_direction = _opt_str(identity.get("weight_direction"))
    return weight_kg, weight_direction


def normalize_preset(
    preset: dict, char_id: str, *, source_sha: str, source_path: str
) -> dict:
    """Normalize one preset JSON into a physical profile record."""
    declared = preset.get("character")
    if declared != char_id:
        raise CharacterMismatchError(
            f"character mismatch: directory {char_id!r} but preset declares {declared!r}"
        )

    identity = preset.get("identity_summary")
    if not isinstance(identity, dict):
        identity = {}

    height_cm, height_is_approx = _normalize_height(identity)
    weight_kg, weight_direction = _normalize_weight(identity)

    return {
        "character_id": char_id,
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
        "source_preset_sha256": source_sha,
        "source_preset_path": source_path,
    }


def discover_preset_paths(canon_root: Path) -> dict[str, Path]:
    """Return ``{character_id: preset_path}`` discovered from AI_CHARACTERS.

    Discovery is authoritative (no hardcoded character list). Only the direct
    ``AI_CHARACTERS/<CHARACTER>/10_notes/*_REFERENCE_PRESETS.json`` layout is
    read; underscore-prefixed meta directories (joint scenes) are skipped.
    """
    result: dict[str, Path] = {}
    ai_chars = canon_root / "AI_CHARACTERS"
    if not ai_chars.is_dir():
        return result
    for preset_path in sorted(ai_chars.glob("*/10_notes/*_REFERENCE_PRESETS.json")):
        char_id = preset_path.parent.parent.name
        if char_id.startswith("_"):
            continue
        result[char_id] = preset_path
    return result


def build_snapshot(canon_root: Path) -> dict:
    """Build the full deterministic snapshot from a canon root."""
    presets = discover_preset_paths(canon_root)
    characters: dict[str, dict] = {}
    for char_id in sorted(presets):
        preset_path = presets[char_id]
        raw = preset_path.read_bytes()
        source_sha = hashlib.sha256(raw).hexdigest()
        source_path = preset_path.relative_to(canon_root).as_posix()
        try:
            data = json.loads(preset_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"invalid preset JSON {source_path!r}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"preset root is not an object: {source_path!r}")
        characters[char_id] = normalize_preset(
            data, char_id, source_sha=source_sha, source_path=source_path
        )
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "characters": characters,
    }


def serialize_snapshot(snapshot: dict) -> str:
    """Deterministic UTF-8 JSON (sorted keys, LF)."""
    return json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the VNE physical profiles snapshot from NCC presets."
    )
    parser.add_argument("--canon-root", required=True, dest="canon_root")
    parser.add_argument("--output", default=None, dest="output")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    canon_root = Path(args.canon_root)
    output = Path(args.output) if args.output else DEFAULT_OUTPUT

    try:
        snapshot = build_snapshot(canon_root)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_snapshot(snapshot), encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    characters = snapshot["characters"]
    print(f"WROTE {output}")
    print(f"CHARACTERS {len(characters)}")
    for cid in sorted(characters):
        print(f"  {cid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
