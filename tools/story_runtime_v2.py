#!/usr/bin/env python3
"""Standalone Story Runtime V2 preview for Scenario Schema V2 scenes."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


STATE_DEFAULTS: dict[str, Any] = {
    "completed_scenes": [],
    "flags": [],
    "character_states": {},
    "relationships": {},
    "settings": {},
    "history": [],
}


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


def validator_path() -> Path:
    return repo_root() / "tools" / "narrative_schema_v2.py"


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


def run_scene_validation(scene_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(validator_path()), "validate", str(scene_path)],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
        raise ValueError(f"scene validation failed: {scene_path}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"could not read JSON {path}: {exc}") from exc


def load_scene(scene_arg: str) -> tuple[Path, dict[str, Any]]:
    scene_path = resolve_scene_path(scene_arg)
    run_scene_validation(scene_path)
    scene = load_json(scene_path)
    if not isinstance(scene, dict):
        raise ValueError(f"scene root must be object: {scene_path}")
    return scene_path, scene


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str)})


def normalize_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(sorted(value.items(), key=lambda item: item[0]))


def normalize_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalize_state(obj: Any) -> dict[str, Any]:
    source = obj if isinstance(obj, dict) else {}
    state = copy.deepcopy(STATE_DEFAULTS)
    state.update(
        {
            "completed_scenes": normalize_string_list(source.get("completed_scenes")),
            "flags": normalize_string_list(source.get("flags")),
            "character_states": normalize_mapping(source.get("character_states")),
            "relationships": normalize_mapping(source.get("relationships")),
            "settings": normalize_mapping(source.get("settings")),
            "history": normalize_history(source.get("history")),
        }
    )
    return state


def load_state(path: Path) -> dict[str, Any]:
    return normalize_state(load_json(path))


def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def is_scene_available(scene: dict[str, Any], state: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    completed = set(state["completed_scenes"])
    flags = set(state["flags"])
    missing_prerequisites = [
        item for item in scene.get("prerequisites", [])
        if isinstance(item, str) and item not in completed
    ]
    missing_flags = [
        item for item in scene.get("flags_required", [])
        if isinstance(item, str) and item not in flags
    ]
    return not missing_prerequisites and not missing_flags, missing_prerequisites, missing_flags


def first_choice_point(scene: dict[str, Any]) -> dict[str, Any]:
    choice_points = scene.get("choice_points", [])
    if not choice_points:
        raise ValueError("scene has no choice_points")
    first = choice_points[0]
    if not isinstance(first, dict):
        raise ValueError("first choice_point is not an object")
    return first


def find_branch(scene: dict[str, Any], branch_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    choice_point = first_choice_point(scene)
    for branch in choice_point.get("branches", []):
        if isinstance(branch, dict) and branch.get("id") == branch_id:
            return choice_point, branch
    raise ValueError(f"branch not found in first choice point: {branch_id}")


def beat_channel(beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "speech"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    return "narration"


def format_beat(beat: dict[str, Any]) -> str:
    channel = beat_channel(beat)
    text = beat.get(channel)
    speaker = beat.get("speaker")
    speaker_text = speaker if speaker is not None else "narrator"
    return (
        f"- {beat.get('beat_id')} [{beat.get('type')}] "
        f"{speaker_text} pov={beat.get('pov')}: {text}"
    )


def iter_playback_beats(scene: dict[str, Any], branch: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return list(scene.get("entry_beats", [])), list(branch.get("beats", []))


def apply_effects(
    scene: dict[str, Any],
    choice_point: dict[str, Any],
    branch: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    next_state = normalize_state(state)
    flags = set(next_state["flags"])
    completed = set(next_state["completed_scenes"])
    effects = branch.get("effects", {})
    if not isinstance(effects, dict):
        effects = {}

    for flag in effects.get("flags_cleared", []):
        if isinstance(flag, str):
            flags.discard(flag)
    for flag in effects.get("flags_set", []):
        if isinstance(flag, str):
            flags.add(flag)

    level_changes = effects.get("level_changes", {})
    if isinstance(level_changes, dict):
        for key, value in level_changes.items():
            if isinstance(key, str) and isinstance(value, str):
                next_state["character_states"][key] = value

    relationship_changes = effects.get("relationship_changes", {})
    if isinstance(relationship_changes, dict):
        for key, value in relationship_changes.items():
            if isinstance(key, str) and isinstance(value, str):
                next_state["relationships"][key] = value

    next_data = branch.get("next", {})
    completion_flag = next_data.get("completion_flag") if isinstance(next_data, dict) else None
    if isinstance(completion_flag, str) and completion_flag:
        completed.add(completion_flag)
        flags.add(completion_flag)

    next_state["completed_scenes"] = sorted(completed)
    next_state["flags"] = sorted(flags)
    next_state["character_states"] = normalize_mapping(next_state["character_states"])
    next_state["relationships"] = normalize_mapping(next_state["relationships"])
    next_state["history"].append(
        {
            "scene": scene.get("id"),
            "choice_point": choice_point.get("id"),
            "branch": branch.get("id"),
        }
    )
    return next_state


def print_scene_summary(scene_path: Path, scene: dict[str, Any]) -> None:
    print(f"PASS: {scene.get('id')} {scene.get('name')}")
    print(f"path: {scene_path.relative_to(repo_root())}")
    print(f"location/time: {scene.get('location')}/{scene.get('time')}")
    print(f"prerequisites: {scene.get('prerequisites', [])}")
    print(f"flags_required: {scene.get('flags_required', [])}")
    print(f"entry_beats: {len(scene.get('entry_beats', []))}")
    choice_points = scene.get("choice_points", [])
    print(f"choice_points: {len(choice_points)}")
    for choice_point in choice_points:
        branches = choice_point.get("branches", []) if isinstance(choice_point, dict) else []
        branch_ids = [branch.get("id") for branch in branches if isinstance(branch, dict)]
        print(f"- {choice_point.get('id')}: branches={branch_ids}")


def cmd_inspect(args: argparse.Namespace) -> int:
    try:
        scene_path, scene = load_scene(args.scene)
        print_scene_summary(scene_path, scene)
        return 0
    except ValueError as exc:
        return fail(str(exc))


def cmd_play(args: argparse.Namespace) -> int:
    try:
        scene_path, scene = load_scene(args.scene)
        choice_point, branch = find_branch(scene, args.branch)
        entry_beats, branch_beats = iter_playback_beats(scene, branch)

        print(f"PASS: play {scene.get('id')} branch {branch.get('id')}")
        print(f"scene: {scene.get('id')} {scene.get('name')}")
        print(f"path: {scene_path.relative_to(repo_root())}")
        print("entry_beats:")
        for beat in entry_beats:
            print(format_beat(beat))
        print(f"choice_point: {choice_point.get('id')}")
        print(f"selected: {branch.get('id')} {branch.get('option_text')}")
        print("branch_beats:")
        for beat in branch_beats:
            print(format_beat(beat))
        effects = branch.get("effects", {})
        next_data = branch.get("next", {})
        print("effects:")
        print(f"- flags_cleared: {effects.get('flags_cleared', [])}")
        print(f"- flags_set: {effects.get('flags_set', [])}")
        print(f"- level_changes: {effects.get('level_changes', {})}")
        print(f"- relationship_changes: {effects.get('relationship_changes', {})}")
        print(f"completion_flag: {next_data.get('completion_flag')}")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def cmd_state_after(args: argparse.Namespace) -> int:
    try:
        state = load_state(Path(args.state))
        scene_path, scene = load_scene(args.scene)
        available, missing_prerequisites, missing_flags = is_scene_available(scene, state)
        if not available:
            print(f"scene: {scene_path.relative_to(repo_root())}")
            print(f"missing_prerequisites: {missing_prerequisites}")
            print(f"missing_flags: {missing_flags}")
            return fail(f"{scene.get('id')} is not available")
        choice_point, branch = find_branch(scene, args.branch)
        next_state = apply_effects(scene, choice_point, branch, state)
        print(f"PASS: state-after {scene.get('id')} branch {branch.get('id')}")
        print(dump_json(next_state))
        return 0
    except ValueError as exc:
        return fail(str(exc))


def cmd_available(args: argparse.Namespace) -> int:
    try:
        state = load_state(Path(args.state))
        files = sorted(scenarios_dir().glob("SCENARIO_*.v2.json"))
        if not files:
            return fail("no V2 scene files found")
        for scene_path in files:
            run_scene_validation(scene_path)
            scene = load_json(scene_path)
            available, missing_prerequisites, missing_flags = is_scene_available(scene, state)
            status = "YES" if available else "NO"
            print(f"{scene.get('id')} available: {status}")
            if not available:
                print(f"  missing_prerequisites: {missing_prerequisites}")
                print(f"  missing_flags: {missing_flags}")
        print("PASS: availability check complete")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def is_inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root().resolve())
        return True
    except ValueError:
        return False


def cmd_save(args: argparse.Namespace) -> int:
    try:
        state = load_state(Path(args.state))
        output = Path(args.output)
        output = output if output.is_absolute() else repo_root() / output
        parent = output.parent
        if not parent.exists():
            if is_inside_repo(output):
                return fail(f"refusing to create missing parent inside repo: {parent}")
            parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dump_json(state) + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: saved state to {output}")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def cmd_load(args: argparse.Namespace) -> int:
    try:
        state = load_state(Path(args.input))
        print("PASS: load")
        print(dump_json(state))
        return 0
    except ValueError as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone Scenario Schema V2 story runtime.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="Load, validate, and summarize a V2 scene")
    p_inspect.add_argument("scene")
    p_inspect.set_defaults(func=cmd_inspect)

    p_play = sub.add_parser("play", help="Print ordered beats for a selected branch")
    p_play.add_argument("scene")
    p_play.add_argument("--branch", required=True)
    p_play.set_defaults(func=cmd_play)

    p_state = sub.add_parser("state-after", help="Apply selected branch effects to a state file")
    p_state.add_argument("scene")
    p_state.add_argument("--branch", required=True)
    p_state.add_argument("--state", required=True)
    p_state.set_defaults(func=cmd_state_after)

    p_available = sub.add_parser("available", help="Check V2 scene availability for a state file")
    p_available.add_argument("--state", required=True)
    p_available.set_defaults(func=cmd_available)

    p_save = sub.add_parser("save", help="Normalize and save state to an explicit output path")
    p_save.add_argument("--state", required=True)
    p_save.add_argument("--output", required=True)
    p_save.set_defaults(func=cmd_save)

    p_load = sub.add_parser("load", help="Load and print normalized state")
    p_load.add_argument("--input", required=True)
    p_load.set_defaults(func=cmd_load)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
