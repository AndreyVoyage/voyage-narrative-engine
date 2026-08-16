#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Context Bridge v1 — read-only, offline extraction of static narrative
metadata for the Character Aside.

Reads Scenario Schema V2 JSON (scenarios/SCENARIO_???_*.v2.json) and returns
a detached plain-data dict with static scene information. This bridge does NOT:
- access the network;
- read or write Ren'Py state, save files, or aside memory;
- read or write persona modules;
- interpret beats as proof of anything having occurred;
- require any files beyond the V2 JSON.

When a scene source cannot be found or parsed, the bridge returns a safe
context-unavailable sentinel instead of raising.

v0→v1: removed static_scene_description (entry-narration future content).
       Added played_events passthrough for runtime-driven already-played
       history from vne_recent_played_events.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = REPO_ROOT / "scenarios"


class SceneContextError(RuntimeError):
    """Expected, safe bridge error — never leaks secrets or paths."""


def build_scene_context_snapshot(
    scene_id: str,
    beat_id: str | None = None,
    current_label: str | None = None,
    repo_root: Path | None = None,
    played_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a detached plain-data scene context dict.

    Parameters:
        scene_id: e.g. "SC_017". Must match the V2 JSON ``id`` field.
        beat_id: optional current beat tracking value.
        current_label: optional current Ren'Py label name (e.g. "sc_017_v2_1a").
        repo_root: repo root path; defaults to this file's parent's parent.
        played_events: optional runtime played-event history (detached plain list).

    Returns a dict with at minimum:
        {"context_available": True/False, ...}
    """
    root = Path(repo_root) if repo_root is not None else REPO_ROOT

    if not isinstance(scene_id, str) or not scene_id.strip():
        return _context_unavailable("scene_id is missing or empty")

    normalized_id = scene_id.strip().upper()
    if not re.match(r"^SC_\d{3}$", normalized_id):
        return _context_unavailable(
            f"scene_id format not recognised: {scene_id!r}"
        )

    json_path = _resolve_v2_json(root, normalized_id)
    if json_path is None:
        return _context_unavailable(
            f"no V2 JSON found for {normalized_id}"
        )

    try:
        scene_data = _read_json(json_path)
    except SceneContextError as exc:
        return _context_unavailable(str(exc))

    if not isinstance(scene_data, dict):
        return _context_unavailable(
            f"V2 JSON root is not an object: {json_path}"
        )

    context: dict[str, Any] = {
        "context_available": True,
        "scene_id": _scene_string(scene_data, "id") or normalized_id,
        "scene_title": _scene_string(scene_data, "name"),
        "location": _scene_string(scene_data, "location"),
        "time_or_phase": _scene_string(scene_data, "time"),
        "active_characters": _present_characters(scene_data),
        "content_rating": _scene_string(scene_data.get("safety"), "content_rating")
        or "not specified",
    }

    # Attach current positional tracking values when available.
    if beat_id:
        context["beat_id"] = str(beat_id)
    if current_label:
        context["current_label"] = str(current_label)

    # Attach runtime played events when provided.
    # Only plain list-of-dict is accepted; invalid values are silently dropped.
    if isinstance(played_events, list):
        safe_events = []
        for ev in played_events:
            if isinstance(ev, dict):
                clean = {}
                for key, value in ev.items():
                    if isinstance(key, str) and isinstance(value, (str, int, float, bool, type(None))):
                        clean[str(key)] = value
                    elif isinstance(key, str):
                        clean[str(key)] = str(value)
                if clean:
                    safe_events.append(clean)
        context["played_events"] = safe_events

    _assert_plain_data(context)
    return context


def _context_unavailable(reason: str) -> dict[str, Any]:
    return {
        "context_available": False,
        "reason": str(reason),
    }


def _resolve_v2_json(root: Path, scene_id: str) -> Path | None:
    """Find the single .v2.json file whose ``id`` field equals *scene_id*."""
    scenarios_dir = root / "scenarios"
    if not scenarios_dir.is_dir():
        return None

    candidates: list[Path] = []
    for path in sorted(scenarios_dir.glob("*.v2.json")):
        try:
            data = _read_json(path)
        except SceneContextError:
            continue
        if isinstance(data, dict) and data.get("id") == scene_id:
            candidates.append(path)

    if len(candidates) == 1:
        return candidates[0]
    return None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SceneContextError(
            f"invalid JSON in {path.name}: {exc}"
        ) from None
    except OSError as exc:
        raise SceneContextError(
            f"cannot read {path.name}: {exc}"
        ) from None


def _scene_string(source: Any, key: str) -> str | None:
    if not isinstance(source, dict):
        return None
    value = source.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _present_characters(scene_data: dict[str, Any]) -> list[dict[str, str]]:
    characters: list[dict[str, str]] = []
    for entry in scene_data.get("characters", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("present") is not True:
            continue
        char_id = entry.get("id")
        display_name = entry.get("display_name")
        if isinstance(char_id, str) and isinstance(display_name, str):
            characters.append({"id": char_id.strip(), "name": display_name.strip()})
    return characters


def _assert_plain_data(value: Any, path: str = "context") -> None:
    """Reject non-plain types (custom classes, sets, bytes, etc.)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SceneContextError(
                    f"{path}: non-string key {key!r}"
                )
            _assert_plain_data(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_plain_data(item, f"{path}[{index}]")
        return
    raise SceneContextError(
        f"{path}: unsafe type {type(value).__name__}"
    )