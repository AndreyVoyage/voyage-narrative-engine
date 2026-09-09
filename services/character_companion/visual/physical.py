#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure physical-identity prompt rendering.

Extracted from ``tools/scene_image_test_app.py`` in the VNE repo -- the
``_gender_label`` / ``_format_weight`` / ``_height_line`` / ``_render_relative_scale``
/ ``_render_physical_block`` helpers, verbatim in behaviour. The ``orchestrate``
harness, fixtures, forbidden-token scanning and physical-profiles file loader
are NOT carried over.

Companion extension: after the VNE role/height/weight/body lines the renderer
also emits ``face`` / ``hair`` / ``confirmed traits`` when present (these are in
the imported snapshot but the VNE block omitted them). ``style_direction`` and
``safety_rules`` are still deliberately NOT sent to a provider, and no
scenario-specific forbidden-token logic is copied.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def gender_label(role: str) -> str:
    r = (role or "").lower()
    if "female" in r or "woman" in r:
        base = "woman"
    elif "male" in r or "man" in r:
        base = "man"
    else:
        return role
    if "mature" in r:
        return f"mature adult {base}"
    return f"adult {base}"


def format_weight(weight_kg: Any) -> str:
    if weight_kg is None:
        return ""
    if float(weight_kg).is_integer():
        return f"{int(weight_kg)} kg"
    return f"{weight_kg} kg"


def height_line(prof: Mapping[str, Any]) -> str:
    height_cm = prof.get("height_cm")
    if height_cm is not None:
        prefix = "approximately " if bool(prof.get("height_is_approx", False)) else ""
        return f"{prefix}{height_cm} cm"
    return prof.get("height_direction") or ""


def render_relative_scale(
    aliases: Sequence[str], physical_by_alias: Mapping[str, Mapping[str, Any]]
) -> str:
    """RELATIVE SCALE section (never invents numbers). Empty for < 2 characters,
    i.e. always empty for Companion V1."""
    infos = []
    for alias in aliases:
        prof = physical_by_alias.get(alias) or {}
        infos.append((alias, prof.get("height_cm"), prof.get("height_direction")))
    if len(infos) < 2:
        return ""

    lines = ["RELATIVE SCALE", ""]
    (a_alias, a_h, a_dir), (b_alias, b_h, b_dir) = infos[0], infos[1]
    if a_h is not None and b_h is not None:
        taller, shorter = (a_alias, b_alias) if a_h >= b_h else (b_alias, a_alias)
        diff = abs(a_h - b_h)
        if diff >= 8:
            lines.append(f"{taller} is visibly taller than {shorter}.")
        elif diff >= 3:
            lines.append(f"{taller} is somewhat taller than {shorter}.")
        else:
            lines.append(f"{taller} and {shorter} are of comparable height.")
    else:
        lines.append("Relative height is not numerically specified for these characters.")
    return "\n".join(lines)


def _trait_line(profile: Mapping[str, Any]) -> str:
    traits = [str(t).strip() for t in (profile.get("confirmed_traits") or []) if str(t).strip()]
    return ", ".join(traits)


def render_physical_block(profile: Mapping[str, Any], alias: str = "the character") -> str:
    """Provider-facing physical identity block for ONE character.

    Renders only facts present in the snapshot. Never emits ``style_direction``,
    ``safety_rules``, paths, or SHAs.
    """
    if not profile:
        return ""

    lines = ["CHARACTER PHYSICAL IDENTITY", "", f"{alias}:"]

    role = profile.get("role") or ""
    if role:
        lines.append(f"- {gender_label(role)}")

    hl = height_line(profile)
    if hl:
        lines.append(f"- {hl}")

    weight_kg = profile.get("weight_kg")
    weight_direction = profile.get("weight_direction")
    if weight_kg is not None:
        lines.append(f"- {format_weight(weight_kg)}")
    elif weight_direction:
        lines.append(f"- {weight_direction}")

    body = (profile.get("body_direction") or "").strip()
    if body:
        lines.append(f"- {body}")

    face = (profile.get("face_direction") or "").strip()
    if face:
        lines.append(f"- face: {face}")

    hair = (profile.get("hair_direction") or "").strip()
    if hair:
        lines.append(f"- hair: {hair}")

    traits = _trait_line(profile)
    if traits:
        lines.append(f"- confirmed traits: {traits}")

    return "\n".join(lines).rstrip("\n")
