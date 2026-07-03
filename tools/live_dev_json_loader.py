#!/usr/bin/env python3
"""External mock/dev loader for Voyage Scenario Schema V2 scenes (N5H).

This tool is read-only. It does not load JSON inside RenPy, does not write
back to source files, and does not implement hot-reload. It builds the
beat/branch address map and reload-safety classification required by the
N5G Live/Dev JSON Contract.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


# Ensure sibling tool import works regardless of invocation directory.
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import narrative_schema_v2  # noqa: E402


SCENE_ID_RE = re.compile(r"^SC_[0-9]{3}$")

SAFE_TEXT_FIELDS = {"narration", "speech", "action", "thought", "emotion"}

FORBIDDEN_FIELDS = {
    "beat_id",
    "type",
    "speaker",
    "pov",
    "thought_visibility",
    "option_text",
    "effects",
    "next",
    "prerequisites",
    "flags_required",
    "completion_flag",
    "branch structure",
    "choice point ids",
    "relationship/effect mutations",
}

STATE_MAPPING = [
    ("completed_scenes", "v2_completed_scenes"),
    ("flags", "v2_flags"),
    ("character_states", "v2_levels"),
    ("relationships", "v2_relationships"),
    ("settings", "v2_settings"),
    ("history", "v2_history"),
]


def configure_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def scenarios_dir() -> Path:
    return repo_root() / "scenarios"


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def scene_code_num(scene_arg: str) -> int | None:
    text = scene_arg.strip().upper()
    if text.startswith("SC_"):
        text = text[3:]
    elif text.startswith("SC"):
        text = text[2:]
    try:
        return int(text)
    except ValueError:
        return None


def resolve_scene_path(scene_arg: str) -> Path:
    candidate = Path(scene_arg)
    if candidate.suffix == ".json":
        path = candidate if candidate.is_absolute() else repo_root() / candidate
        if not path.exists():
            raise ValueError(f"scene file not found: {candidate}")
        if not path.name.endswith(".v2.json"):
            raise ValueError(f"scene file is not a .v2.json source: {candidate}")
        return path

    scene_num = scene_code_num(scene_arg)
    if scene_num is None:
        raise ValueError(f"cannot parse scene identifier: {scene_arg}")

    matches = sorted(scenarios_dir().glob(f"SCENARIO_{scene_num:03d}*.v2.json"))
    if not matches:
        raise ValueError(f"no V2 scene file found for SC_{scene_num:03d}")
    if len(matches) > 1:
        rel = [str(path.relative_to(repo_root())) for path in matches]
        raise ValueError(f"multiple V2 scene files found for SC_{scene_num:03d}: {rel}")
    return matches[0]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"could not read JSON {path}: {exc}") from exc


def validate_scene_data(path: Path, data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"scene root must be object: {path}")
    schema_version = data.get("schema_version")
    if schema_version != "2.0":
        raise ValueError(f"scene is not V2 (schema_version={schema_version!r}): {path}")
    errors, warnings = narrative_schema_v2.validate_scene(data)
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise ValueError(f"scene validation failed: {path}")


def load_scene(scene_arg: str) -> tuple[Path, dict[str, Any]]:
    scene_path = resolve_scene_path(scene_arg)
    scene = load_json(scene_path)
    validate_scene_data(scene_path, scene)
    return scene_path, scene


def collect_address_map(scene: dict[str, Any]) -> list[dict[str, str]]:
    """Return stable address entries for every beat in the scene."""
    scene_id = str(scene.get("id", "unknown"))
    entries: list[dict[str, str]] = []

    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict):
            entries.append(
                {
                    "scene_id": scene_id,
                    "choice_point": "ENTRY",
                    "branch": "ENTRY",
                    "beat_id": str(beat.get("beat_id", "-")),
                    "type": str(beat.get("type", "-")),
                }
            )

    for choice_point in scene.get("choice_points", []):
        if not isinstance(choice_point, dict):
            continue
        cp_id = str(choice_point.get("id", "-"))
        for branch in choice_point.get("branches", []):
            if not isinstance(branch, dict):
                continue
            branch_id = str(branch.get("id", "-"))
            for beat in branch.get("beats", []):
                if isinstance(beat, dict):
                    entries.append(
                        {
                            "scene_id": scene_id,
                            "choice_point": cp_id,
                            "branch": branch_id,
                            "beat_id": str(beat.get("beat_id", "-")),
                            "type": str(beat.get("type", "-")),
                        }
                    )

    return entries


def collect_choice_point_ids(scene: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for cp in scene.get("choice_points", []):
        if isinstance(cp, dict) and cp.get("id"):
            ids.append(str(cp["id"]))
    return ids


def collect_branch_ids(scene: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for cp in scene.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if isinstance(branch, dict) and branch.get("id"):
                ids.append(str(branch["id"]))
    return ids


def collect_beat_ids(scene: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict) and beat.get("beat_id"):
            ids.append(str(beat["beat_id"]))
    for cp in scene.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if not isinstance(branch, dict):
                continue
            for beat in branch.get("beats", []):
                if isinstance(beat, dict) and beat.get("beat_id"):
                    ids.append(str(beat["beat_id"]))
    return ids


def collect_beat_types(scene: dict[str, Any]) -> list[str]:
    types: set[str] = set()
    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict) and beat.get("type"):
            types.add(str(beat["type"]))
    for cp in scene.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if not isinstance(branch, dict):
                continue
            for beat in branch.get("beats", []):
                if isinstance(beat, dict) and beat.get("type"):
                    types.add(str(beat["type"]))
    return sorted(types)


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        scene_path, scene = load_scene(args.scene)
        address_map = collect_address_map(scene)
        choice_point_ids = collect_choice_point_ids(scene)
        branch_ids = collect_branch_ids(scene)
        beat_ids = collect_beat_ids(scene)
        beat_types = collect_beat_types(scene)

        print("PASS live-dev-inspect")
        print(f"scene: {scene.get('id')} — {scene.get('name', '')}")
        print(f"source: {scene_path.relative_to(repo_root())}")
        print(f"choice_points: {len(choice_point_ids)}")
        print(f"branches: {len(branch_ids)}")
        print(f"beats: {len(beat_ids)}")
        print(f"beat_types: {', '.join(beat_types) if beat_types else '-'}")
        print("")
        print("address_map:")
        for entry in address_map:
            print(
                f"scene_id={entry['scene_id']} "
                f"choice_point={entry['choice_point']} "
                f"branch={entry['branch']} "
                f"beat_id={entry['beat_id']} "
                f"type={entry['type']}"
            )

        print("")
        print("safe_editable_fields:")
        for field in sorted(SAFE_TEXT_FIELDS):
            print(f"- {field}")

        print("")
        print("forbidden_fields:")
        for field in sorted(FORBIDDEN_FIELDS):
            print(f"- {field}")

        print("")
        print("state_mapping:")
        for python_name, renpy_name in STATE_MAPPING:
            print(f"{python_name} -> {renpy_name}")

        print("")
        print("status:")
        print("write-back: NOT IMPLEMENTED")
        print("hot-reload: NOT IMPLEMENTED")
        print("RenPy runtime loader: NOT IMPLEMENTED")
        print("release path affected: NO")

        return 0
    except ValueError as exc:
        return fail(str(exc))


def _compare_values(
    base: Any,
    candidate: Any,
    path: str,
    changed_paths: list[str],
) -> None:
    """Recursively compare base and candidate, recording unsafe structural changes."""
    if type(base) is not type(candidate):
        changed_paths.append(path)
        return

    if isinstance(base, dict):
        base_keys = set(base.keys())
        candidate_keys = set(candidate.keys())
        if base_keys != candidate_keys:
            changed_paths.append(path)
            return
        for key in sorted(base_keys):
            # Text-only edits are allowed only for designated safe fields.
            if key in SAFE_TEXT_FIELDS:
                if base[key] != candidate[key]:
                    # Safe text change — do not record as unsafe.
                    continue
            child_path = f"{path}.{key}" if path else key
            _compare_values(base[key], candidate[key], child_path, changed_paths)
        return

    if isinstance(base, list):
        if len(base) != len(candidate):
            changed_paths.append(path)
            return
        for index, (b_item, c_item) in enumerate(zip(base, candidate)):
            child_path = f"{path}[{index}]"
            _compare_values(b_item, c_item, child_path, changed_paths)
        return

    if base != candidate:
        changed_paths.append(path)


def classify_reload_safety(
    base: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[str, list[str]]:
    """Return (safety_label, unsafe_paths)."""
    changed_paths: list[str] = []
    _compare_values(base, candidate, "", changed_paths)
    if changed_paths:
        return "UNSAFE_STRUCTURAL", changed_paths
    return "SAFE_TEXT_ONLY", []


def cmd_reload_check(args: argparse.Namespace) -> int:
    try:
        base_path = Path(args.base)
        candidate_path = Path(args.candidate)

        if not base_path.is_absolute():
            base_path = repo_root() / base_path
        if not candidate_path.is_absolute():
            candidate_path = repo_root() / candidate_path

        if not base_path.name.endswith(".v2.json"):
            return fail(f"base file is not a .v2.json source: {args.base}")
        if not candidate_path.name.endswith(".v2.json"):
            return fail(f"candidate file is not a .v2.json source: {args.candidate}")

        base = load_json(base_path)
        candidate = load_json(candidate_path)

        validate_scene_data(base_path, base)
        validate_scene_data(candidate_path, candidate)

        if not isinstance(base, dict) or not isinstance(candidate, dict):
            return fail("base or candidate scene root is not an object")

        safety, unsafe_paths = classify_reload_safety(base, candidate)

        print("PASS reload-check")
        print(f"reload_safety: {safety}")
        if safety == "UNSAFE_STRUCTURAL":
            print("unsafe_paths:")
            for unsafe_path in unsafe_paths:
                print(f"- {unsafe_path}")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mock/dev loader for Voyage Scenario Schema V2 scenes (read-only)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser(
        "inspect",
        help="Load, validate, and inspect a V2 scene address map and boundaries",
    )
    p_inspect.add_argument(
        "scene",
        help="Scene identifier (SC_017) or path to a .v2.json source",
    )
    p_inspect.set_defaults(func=cmd_inspect)

    p_reload = sub.add_parser(
        "reload-check",
        help="Compare two V2 JSON files and classify reload safety (read-only)",
    )
    p_reload.add_argument("--base", required=True, help="Base .v2.json scene file")
    p_reload.add_argument(
        "--candidate", required=True, help="Candidate .v2.json scene file"
    )
    p_reload.set_defaults(func=cmd_reload_check)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        return fail(f"unexpected error: {exc}")


if __name__ == "__main__":
    sys.exit(main())
