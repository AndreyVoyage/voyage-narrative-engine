#!/usr/bin/env python3
"""Standalone Player Experience V2 preview renderer."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


MODES = {"classic", "psychological", "developer"}


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


def display_name(scene: dict[str, Any], character_id: Any) -> str:
    if character_id is None:
        return "Narrator"
    for character in scene.get("characters", []):
        if isinstance(character, dict) and character.get("id") == character_id:
            name = character.get("display_name")
            if isinstance(name, str) and name.strip():
                return name
    return str(character_id)


def content_channel(beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "speech"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    return "narration"


def content_for_beat(beat: dict[str, Any]) -> str:
    value = beat.get(content_channel(beat))
    return "" if value is None else str(value)


def all_playback_beats(scene: dict[str, Any], branch: dict[str, Any]) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    beats.extend(beat for beat in scene.get("entry_beats", []) if isinstance(beat, dict))
    beats.extend(beat for beat in branch.get("beats", []) if isinstance(beat, dict))
    return beats


def thought_count(scene: dict[str, Any]) -> int:
    count = 0
    for choice_point in scene.get("choice_points", []):
        if not isinstance(choice_point, dict):
            continue
        for branch in choice_point.get("branches", []):
            if not isinstance(branch, dict):
                continue
            count += sum(
                1 for beat in branch.get("beats", [])
                if isinstance(beat, dict) and beat.get("type") == "thought"
            )
    count += sum(
        1 for beat in scene.get("entry_beats", [])
        if isinstance(beat, dict) and beat.get("type") == "thought"
    )
    return count


def is_beat_visible(beat: dict[str, Any], mode: str) -> bool:
    beat_type = beat.get("type")
    visibility = beat.get("thought_visibility")
    if beat_type != "thought":
        return True
    if mode == "classic":
        return visibility == "always"
    if mode == "psychological":
        return visibility in {"revealed", "always"}
    if mode == "developer":
        return True
    return False


def format_player_beat(scene: dict[str, Any], beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    text = content_for_beat(beat)
    speaker = display_name(scene, beat.get("speaker"))
    if beat_type == "dialogue":
        return f'{speaker}: "{text}"'
    if beat_type == "action":
        return f"*{speaker}: {text}*"
    if beat_type == "thought":
        return f"({speaker}: {text})"
    return text


def render_header(
    scene: dict[str, Any],
    scene_path: Path,
    choice_point: dict[str, Any],
    branch: dict[str, Any],
    mode: str,
) -> list[str]:
    return [
        "PX PREVIEW",
        f"Scene: {scene.get('id')} - {scene.get('name')}",
        f"Source: {scene_path.relative_to(repo_root())}",
        f"Mode: {mode}",
        f"Branch: {branch.get('id')}",
        f"Choice Point: {choice_point.get('id')}",
        f"Option: {branch.get('option_text')}",
        "",
    ]


def render_effects_preview(branch: dict[str, Any]) -> list[str]:
    effects = branch.get("effects", {})
    if not isinstance(effects, dict):
        effects = {}
    next_data = branch.get("next", {})
    if not isinstance(next_data, dict):
        next_data = {}
    return [
        "",
        "[EFFECTS PREVIEW ONLY]",
        f"flags_set: {json.dumps(effects.get('flags_set', []), ensure_ascii=False, sort_keys=True)}",
        f"flags_cleared: {json.dumps(effects.get('flags_cleared', []), ensure_ascii=False, sort_keys=True)}",
        f"level_changes: {json.dumps(effects.get('level_changes', {}), ensure_ascii=False, sort_keys=True)}",
        f"relationship_changes: {json.dumps(effects.get('relationship_changes', {}), ensure_ascii=False, sort_keys=True)}",
        f"completion_flag: {next_data.get('completion_flag')}",
    ]


def render_classic_or_psychological(
    scene: dict[str, Any],
    scene_path: Path,
    choice_point: dict[str, Any],
    branch: dict[str, Any],
    mode: str,
) -> str:
    lines = render_header(scene, scene_path, choice_point, branch, mode)
    entry_beats = [beat for beat in scene.get("entry_beats", []) if isinstance(beat, dict)]
    branch_beats = [beat for beat in branch.get("beats", []) if isinstance(beat, dict)]

    lines.append("[ENTRY]")
    for beat in entry_beats:
        if is_beat_visible(beat, mode):
            lines.append(format_player_beat(scene, beat))

    lines.extend(["", f"[BRANCH {branch.get('id')}]"])
    for beat in branch_beats:
        if is_beat_visible(beat, mode):
            lines.append(format_player_beat(scene, beat))

    if mode == "psychological" and thought_count(scene) == 0:
        lines.extend(
            [
                "",
                "[MODE NOTE]",
                "No thought beats found in this scene; psychological output does not add thoughts.",
            ]
        )

    lines.extend(render_effects_preview(branch))
    return "\n".join(lines)


def editable_hint(beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "speech"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    if beat_type == "narration":
        return "narration"
    return "none"


def render_developer(
    scene: dict[str, Any],
    scene_path: Path,
    choice_point: dict[str, Any],
    branch: dict[str, Any],
) -> str:
    lines = render_header(scene, scene_path, choice_point, branch, "developer")
    lines.extend(
        [
            "[DEVELOPER INSPECTOR - READ ONLY]",
            "Developer mode may show hidden/revealed/always thought metadata.",
            "No editing, write-back, hot-reload, or state mutation is implemented.",
            "",
            "[BEATS]",
        ]
    )

    for beat in all_playback_beats(scene, branch):
        lines.append(f"- beat_id: {beat.get('beat_id')}")
        lines.append(f"  type: {beat.get('type')}")
        lines.append(f"  speaker: {beat.get('speaker')}")
        lines.append(f"  pov: {beat.get('pov')}")
        lines.append(f"  thought_visibility: {beat.get('thought_visibility')}")
        lines.append(f"  visible_content: {content_for_beat(beat)}")
        lines.append(f"  editable_field_hint: {editable_hint(beat)}")

    lines.extend(render_effects_preview(branch))
    return "\n".join(lines)


def cmd_render(args: argparse.Namespace) -> int:
    if args.mode not in MODES:
        return fail(f"invalid mode: {args.mode}; expected one of {sorted(MODES)}")
    try:
        scene_path, scene = load_scene(args.scene)
        choice_point, branch = find_branch(scene, args.branch)
        if args.mode == "developer":
            print(render_developer(scene, scene_path, choice_point, branch))
        else:
            print(render_classic_or_psychological(scene, scene_path, choice_point, branch, args.mode))
        return 0
    except ValueError as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render Scenario Schema V2 player experience previews.")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="Render a V2 scene branch in a player experience mode")
    render.add_argument("scene")
    render.add_argument("--branch", required=True, help="Branch id (e.g. 1A)")
    render.add_argument("--mode", required=True, help="classic, psychological, or developer")
    render.set_defaults(func=cmd_render)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
