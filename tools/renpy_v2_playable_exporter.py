#!/usr/bin/env python3
"""Standalone RenPy playable exporter for Scenario Schema V2 scenes (N5A proof)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


KNOWN_RENPY_CHARACTERS = {"kira", "yakov", "sergey"}

# N5A: only this explicit output path inside novel/game is allowed.
ALLOWED_PLAYABLE_OUTPUT = Path("novel/game/scenes_v2_generated.rpy")


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


def script_rpy_path() -> Path:
    return repo_root() / "novel" / "game" / "script.rpy"


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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


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
    return f"{text}_v2"


def branch_label_id(scene_id: Any, branch_id: Any) -> str:
    scene_text = safe_label_id(scene_id)
    branch_text = str(branch_id or "branch").lower()
    branch_text = re.sub(r"[^a-z0-9_]+", "_", branch_text)
    branch_text = re.sub(r"_+", "_", branch_text).strip("_")
    if not branch_text:
        branch_text = "branch"
    return f"{scene_text}_{branch_text}"


def existing_script_labels() -> set[str]:
    text = script_rpy_path().read_text(encoding="utf-8")
    return set(re.findall(r"^label\s+([A-Za-z0-9_]+)\s*:", text, flags=re.M))


def assert_no_label_collision(generated_labels: set[str]) -> None:
    collisions = generated_labels & existing_script_labels()
    if collisions:
        raise ValueError(f"generated labels collide with script.rpy: {sorted(collisions)}")


def assert_safe_output_path(output_path: Path) -> None:
    resolved = output_path if output_path.is_absolute() else repo_root() / output_path
    allowed = repo_root() / ALLOWED_PLAYABLE_OUTPUT
    if resolved.resolve() != allowed.resolve():
        raise ValueError(
            f"refusing unsafe output path: {output_path}; "
            f"N5A only allows: {ALLOWED_PLAYABLE_OUTPUT}"
        )


def beat_channel(beat: dict[str, Any]) -> str:
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "speech"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    return "narration"


def display_name(scene: dict[str, Any], character_id: Any) -> str:
    if character_id is None:
        return "Narrator"
    for character in scene.get("characters", []):
        if isinstance(character, dict) and character.get("id") == character_id:
            name = character.get("display_name")
            if isinstance(name, str) and name.strip():
                return name
    return str(character_id)


def render_beat(scene: dict[str, Any], beat: dict[str, Any]) -> list[str]:
    beat_id = beat.get("beat_id")
    beat_type = beat.get("type")
    speaker = beat.get("speaker")
    channel = beat_channel(beat)
    text = beat.get(channel)
    lines: list[str] = []

    if beat_id:
        lines.append(f"    # beat_id: {beat_id}")

    if beat_type == "dialogue":
        name = display_name(scene, speaker)
        lines.append(f'    narrator "{renpy_escape(name)}: {renpy_escape(text)}"')
        return lines

    if beat_type == "action":
        name = display_name(scene, speaker)
        lines.append(f'    narrator "[{renpy_escape(name)} action] {renpy_escape(text)}"')
        return lines

    if beat_type == "thought":
        visibility = beat.get("thought_visibility")
        name = display_name(scene, speaker)
        marker = f"thought:{name}; visibility={visibility}"
        lines.append(f'    narrator "[{renpy_escape(marker)}] {renpy_escape(text)}"')
        return lines

    lines.append(f'    narrator "{renpy_escape(text)}"')
    return lines


def render_effect_statements(branch: dict[str, Any]) -> list[str]:
    effects = branch.get("effects", {})
    if not isinstance(effects, dict):
        effects = {}
    next_data = branch.get("next", {})
    if not isinstance(next_data, dict):
        next_data = {}
    completion_flag = next_data.get("completion_flag")
    scene_id = branch.get("_scene_id")

    lines: list[str] = []
    lines.append("    # effects")

    for flag in effects.get("flags_cleared", []):
        if isinstance(flag, str):
            lines.append(f'    $ v2_flags.discard("{renpy_escape(flag)}")')

    for flag in effects.get("flags_set", []):
        if isinstance(flag, str):
            lines.append(f'    $ v2_flags.add("{renpy_escape(flag)}")')

    level_changes = effects.get("level_changes", {})
    if isinstance(level_changes, dict):
        for key, value in level_changes.items():
            if isinstance(key, str) and isinstance(value, str):
                lines.append(f'    $ v2_levels["{renpy_escape(key)}"] = "{renpy_escape(value)}"')

    relationship_changes = effects.get("relationship_changes", {})
    if isinstance(relationship_changes, dict):
        for key, value in relationship_changes.items():
            if isinstance(key, str) and isinstance(value, str):
                lines.append(f'    $ v2_relationships["{renpy_escape(key)}"] = "{renpy_escape(value)}"')

    if isinstance(scene_id, str) and scene_id:
        lines.append(f'    $ v2_completed_scenes.add("{renpy_escape(scene_id)}")')

    if isinstance(completion_flag, str) and completion_flag:
        lines.append(f'    $ v2_flags.add("{renpy_escape(completion_flag)}")')
        lines.append(f'    $ v2_completed_scenes.add("{renpy_escape(completion_flag)}")')

    return lines


def render_branch(scene: dict[str, Any], choice_point: dict[str, Any], branch: dict[str, Any]) -> list[str]:
    branch_id = branch.get("id")
    label = branch_label_id(scene.get("id"), branch_id)
    lines = ["", f"label {label}:", ""]
    for beat in branch.get("beats", []):
        if isinstance(beat, dict):
            lines.extend(render_beat(scene, beat))
    lines.append("")
    branch["_scene_id"] = scene.get("id")
    lines.extend(render_effect_statements(branch))
    del branch["_scene_id"]
    lines.append("")
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

    source_rel = scene_path.relative_to(repo_root()).as_posix()
    source_sha = file_sha256(scene_path)

    lines: list[str] = [
        "# AUTO-GENERATED playable RenPy scene from VNE Scenario Schema V2 JSON.",
        "# generated by tools/renpy_v2_playable_exporter.py",
        f"# source scene id: {scene_id}",
        f"# source: {source_rel}",
        f"# source SHA256: {source_sha}",
        "# do not edit manually; regenerate from JSON source.",
        "",
        "default v2_flags = set()",
        "default v2_completed_scenes = set()",
        "default v2_levels = {}",
        "default v2_relationships = {}",
        "",
        f"label {label}_start:",
        "",
    ]

    if scene_name:
        lines.append(f'    narrator "{renpy_escape(scene_name)}"')

    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict):
            lines.extend(render_beat(scene, beat))

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

    lines.extend(["", f"label {label}_end:", "", "    return", ""])
    return "\n".join(lines)


def collect_generated_labels(scene: dict[str, Any]) -> set[str]:
    scene_id = scene.get("id")
    labels: set[str] = {
        f"{safe_label_id(scene_id)}_start",
        f"{safe_label_id(scene_id)}_end",
    }
    for cp in scene.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if isinstance(branch, dict):
                labels.add(branch_label_id(scene_id, branch.get("id")))
    return labels


def cmd_build(args: argparse.Namespace) -> int:
    if not args.output:
        return fail("build requires explicit --output")

    output = Path(args.output)
    try:
        assert_safe_output_path(output)
        scene_path, scene = load_scene(args.scene)
        generated_labels = collect_generated_labels(scene)
        assert_no_label_collision(generated_labels)
        text = render_scene(scene, scene_path)
        resolved = output if output.is_absolute() else repo_root() / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text, encoding="utf-8", newline="\n")
        print(f"PASS: wrote playable RenPy V2 scene to {resolved}")
        return 0
    except ValueError as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Scenario Schema V2 scenes to playable RenPy (.rpy)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a playable RenPy scene from V2 JSON")
    p_build.add_argument("scene")
    p_build.add_argument("--output", required=True, help="Output .rpy path")
    p_build.set_defaults(func=cmd_build)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
