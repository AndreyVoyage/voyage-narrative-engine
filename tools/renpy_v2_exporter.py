#!/usr/bin/env python3
"""Standalone RenPy preview exporter for Scenario Schema V2 scenes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


KNOWN_RENPY_CHARACTERS = {"kira", "yakov", "sergey"}


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


def renpy_escape(text: Any) -> str:
    value = "" if text is None else str(text)
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(value.splitlines())


def safe_label_id(scene_id: Any) -> str:
    text = str(scene_id or "unknown").lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = "unknown"
    return f"{text}_v2_preview"


def branch_label_id(scene_id: Any, branch_id: Any) -> str:
    scene_text = safe_label_id(scene_id)
    branch_text = str(branch_id or "branch").lower()
    branch_text = re.sub(r"[^a-z0-9_]+", "_", branch_text)
    branch_text = re.sub(r"_+", "_", branch_text).strip("_")
    if not branch_text:
        branch_text = "branch"
    return f"{scene_text}_{branch_text}"


def render_comment_json(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return f"    # {prefix}: {payload}"


def beat_channel(beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "speech"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    return "narration"


def render_beat(beat: dict[str, Any]) -> list[str]:
    beat_id = beat.get("beat_id")
    beat_type = beat.get("type")
    speaker = beat.get("speaker")
    channel = beat_channel(beat)
    text = renpy_escape(beat.get(channel))
    lines: list[str] = []

    if beat_id:
        lines.append(f"    # beat_id: {beat_id}")

    if beat_type == "dialogue":
        if speaker in KNOWN_RENPY_CHARACTERS:
            lines.append(f'    {speaker} "{text}"')
        else:
            lines.append(f"    # Unknown speaker for dialogue: {speaker}")
            lines.append(f'    narrator "[{renpy_escape(speaker)}] {text}"')
        return lines

    if beat_type == "action":
        marker = f"[action:{speaker}]" if speaker else "[action]"
        lines.append(f'    narrator "{renpy_escape(marker)} {text}"')
        return lines

    if beat_type == "thought":
        visibility = beat.get("thought_visibility")
        marker = f"[thought:{speaker}; visibility={visibility}]"
        lines.append("    # Thought preview only; final visibility belongs to UX/runtime.")
        lines.append(f'    narrator "{renpy_escape(marker)} {text}"')
        return lines

    lines.append(f'    narrator "{text}"')
    return lines


def render_effect_comments(branch: dict[str, Any]) -> list[str]:
    effects = branch.get("effects", {})
    if not isinstance(effects, dict):
        effects = {}
    next_data = branch.get("next", {})
    completion_flag = next_data.get("completion_flag") if isinstance(next_data, dict) else None
    return [
        "    # Effects preview only:",
        render_comment_json("flags_set", effects.get("flags_set", [])),
        render_comment_json("flags_cleared", effects.get("flags_cleared", [])),
        render_comment_json("level_changes", effects.get("level_changes", {})),
        render_comment_json("relationship_changes", effects.get("relationship_changes", {})),
        f"    # completion_flag: {completion_flag}",
    ]


def render_branch(scene: dict[str, Any], _choice_point: dict[str, Any], branch: dict[str, Any]) -> list[str]:
    lines = ["", "", f"label {branch_label_id(scene.get('id'), branch.get('id'))}:", ""]
    for beat in branch.get("beats", []):
        if isinstance(beat, dict):
            lines.extend(render_beat(beat))
    lines.append("")
    lines.extend(render_effect_comments(branch))
    lines.append(f"    jump {safe_label_id(scene.get('id'))}_end")
    return lines


def render_scene(scene: dict[str, Any], scene_path: Path) -> str:
    scene_id = scene.get("id")
    scene_name = scene.get("name", "")
    label = safe_label_id(scene_id)
    choice_points = scene.get("choice_points", [])
    if not choice_points or not isinstance(choice_points[0], dict):
        raise ValueError("scene has no first choice_point")
    choice_point = choice_points[0]
    branches = choice_point.get("branches", [])
    if not isinstance(branches, list) or not branches:
        raise ValueError("first choice_point has no branches")

    lines: list[str] = [
        "# Auto-generated RenPy preview from VNE Scenario Schema V2 JSON.",
        f"# Source: {scene_path.relative_to(repo_root())}",
        "# Preview only: do not edit manually; do not treat effects as executable state.",
        "",
        f"label {label}:",
        "",
    ]
    if scene_name:
        lines.append(f'    narrator "{renpy_escape(scene_name)}"')
    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict):
            lines.extend(render_beat(beat))

    prompt = choice_point.get("prompt")
    if prompt:
        lines.append("")
        lines.append(f'    narrator "{renpy_escape(prompt)}"')

    lines.append("")
    lines.append("    menu:")
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        option = renpy_escape(branch.get("option_text") or branch.get("id"))
        target = branch_label_id(scene_id, branch.get("id"))
        lines.append(f'        "{option}":')
        lines.append(f"            jump {target}")

    for branch in branches:
        if isinstance(branch, dict):
            lines.extend(render_branch(scene, choice_point, branch))

    lines.extend(["", "", f"label {label}_end:", "", "    return", ""])
    return "\n".join(lines)


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def write_output(text: str, output_path: Path) -> None:
    output = output_path if output_path.is_absolute() else repo_root() / output_path
    if is_inside(output, repo_root() / "novel" / "game"):
        raise ValueError(f"refusing to write preview into novel/game: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8", newline="\n")


def cmd_preview(args: argparse.Namespace) -> int:
    try:
        scene_path, scene = load_scene(args.scene)
        print(render_scene(scene, scene_path))
        return 0
    except ValueError as exc:
        return fail(str(exc))


def cmd_export(args: argparse.Namespace) -> int:
    if not args.output:
        return fail("export requires explicit --output")
    try:
        scene_path, scene = load_scene(args.scene)
        output = Path(args.output)
        text = render_scene(scene, scene_path)
        write_output(text, output)
        resolved = output if output.is_absolute() else repo_root() / output
        print(f"PASS: wrote RenPy V2 preview to {resolved}")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Scenario Schema V2 scenes to RenPy preview text.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_preview = sub.add_parser("preview", help="Print RenPy preview text to stdout")
    p_preview.add_argument("scene")
    p_preview.set_defaults(func=cmd_preview)

    p_export = sub.add_parser("export", help="Write RenPy preview text to an explicit output path")
    p_export.add_argument("scene")
    p_export.add_argument("--output")
    p_export.set_defaults(func=cmd_export)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
