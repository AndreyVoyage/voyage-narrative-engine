#!/usr/bin/env python3
"""Stdlib validator for Voyage Scenario Schema V2 scenes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCENE_ID_RE = re.compile(r"^SC_[0-9]{3}$")
BEAT_TYPES = {"narration", "dialogue", "action", "thought"}
CHANNEL_FOR_TYPE = {
    "narration": "narration",
    "dialogue": "speech",
    "action": "action",
    "thought": "thought",
}
CONTENT_CHANNELS = ("speech", "action", "thought", "narration")
THOUGHT_VISIBILITY = {"hidden", "revealed", "always"}
KNOWN_CONTENT_RATINGS = {"G", "PG", "PG-13", "R", "NC-17"}
TOP_REQUIRED = [
    "schema_version",
    "id",
    "name",
    "version",
    "location",
    "time",
    "intensity",
    "risk",
    "prerequisites",
    "flags_required",
    "characters",
    "pov_default",
    "entry_beats",
    "choice_points",
    "visual",
    "safety",
]


def _configure_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def is_non_empty(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def require_type(errors: list[str], value: Any, expected: type, path: str) -> bool:
    if not isinstance(value, expected):
        errors.append(f"{path}: expected {expected.__name__}")
        return False
    return True


def require_string_array(errors: list[str], value: Any, path: str) -> bool:
    if not isinstance(value, list):
        errors.append(f"{path}: expected array")
        return False
    ok = True
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}]: expected string")
            ok = False
    return ok


def validate_beat(
    beat: Any,
    path: str,
    character_ids: set[str],
    beat_ids: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(beat, dict):
        errors.append(f"{path}: expected object")
        return

    beat_id = beat.get("beat_id")
    if not is_non_empty(beat_id):
        errors.append(f"{path}.beat_id: required non-empty string")
    elif beat_id in beat_ids:
        errors.append(f"{path}.beat_id: duplicate beat_id {beat_id}")
    else:
        beat_ids.add(beat_id)

    beat_type = beat.get("type")
    if beat_type not in BEAT_TYPES:
        errors.append(f"{path}.type: expected one of {sorted(BEAT_TYPES)}")

    populated = [name for name in CONTENT_CHANNELS if is_non_empty(beat.get(name))]
    if len(populated) != 1:
        errors.append(f"{path}: exactly one content channel must be non-empty, got {populated}")
    elif beat_type in CHANNEL_FOR_TYPE and populated[0] != CHANNEL_FOR_TYPE[beat_type]:
        errors.append(f"{path}: type {beat_type} must use channel {CHANNEL_FOR_TYPE[beat_type]}")

    thought_visibility = beat.get("thought_visibility")
    if beat_type == "thought":
        if thought_visibility not in THOUGHT_VISIBILITY:
            errors.append(f"{path}.thought_visibility: thought beat requires hidden/revealed/always")
    elif thought_visibility is not None:
        errors.append(f"{path}.thought_visibility: non-thought beat must use null")

    speaker = beat.get("speaker")
    if beat_type == "narration":
        if speaker is not None:
            errors.append(f"{path}.speaker: narration speaker must be null")
    elif beat_type in {"dialogue", "action", "thought"}:
        if speaker not in character_ids:
            errors.append(f"{path}.speaker: must reference character id")

    pov = beat.get("pov")
    if pov is not None and pov not in character_ids:
        errors.append(f"{path}.pov: must be null or reference character id")


def validate_scene(data: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["scene: expected object"], warnings

    for key in TOP_REQUIRED:
        if key not in data:
            errors.append(f"{key}: required top-level field missing")

    if data.get("schema_version") != "2.0":
        errors.append("schema_version: expected '2.0'")

    scene_id = data.get("id")
    if not isinstance(scene_id, str) or not SCENE_ID_RE.match(scene_id):
        errors.append("id: expected pattern SC_###")

    for key in ("intensity", "risk"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
            errors.append(f"{key}: expected integer 0..10")

    for key in ("prerequisites", "flags_required"):
        if key in data:
            require_string_array(errors, data.get(key), key)

    if "flags_set" in data:
        warnings.append("top-level flags_set is legacy V1 shape; use branch effects and next.completion_flag")

    characters = data.get("characters")
    character_ids: set[str] = set()
    present_protagonists: set[str] = set()
    if not isinstance(characters, list) or not characters:
        errors.append("characters: expected non-empty array")
    else:
        for index, char in enumerate(characters):
            path = f"characters[{index}]"
            if not isinstance(char, dict):
                errors.append(f"{path}: expected object")
                continue
            for key in ("id", "display_name", "role", "present", "state_start", "state_end"):
                if key not in char:
                    errors.append(f"{path}.{key}: required field missing")
            char_id = char.get("id")
            if not is_non_empty(char_id):
                errors.append(f"{path}.id: required non-empty string")
            elif char_id in character_ids:
                errors.append(f"{path}.id: duplicate character id {char_id}")
            else:
                character_ids.add(char_id)
            if not isinstance(char.get("present"), bool):
                errors.append(f"{path}.present: expected boolean")
            if char.get("present") is True and char.get("role") == "protagonist" and isinstance(char_id, str):
                present_protagonists.add(char_id)

    pov_default = data.get("pov_default")
    if pov_default not in character_ids:
        errors.append("pov_default: must reference character id")

    beat_ids: set[str] = set()
    protagonist_beats: dict[str, int] = {char_id: 0 for char_id in present_protagonists}

    entry_beats = data.get("entry_beats")
    if isinstance(entry_beats, list):
        for index, beat in enumerate(entry_beats):
            if isinstance(beat, dict) and beat.get("speaker") in protagonist_beats:
                protagonist_beats[beat["speaker"]] += 1
            validate_beat(beat, f"entry_beats[{index}]", character_ids, beat_ids, errors, warnings)
    else:
        errors.append("entry_beats: expected array")

    choice_points = data.get("choice_points")
    if not isinstance(choice_points, list) or not choice_points:
        errors.append("choice_points: expected non-empty array")
    else:
        for cp_index, cp in enumerate(choice_points):
            cp_path = f"choice_points[{cp_index}]"
            if not isinstance(cp, dict):
                errors.append(f"{cp_path}: expected object")
                continue
            branches = cp.get("branches")
            if not isinstance(branches, list) or not branches:
                errors.append(f"{cp_path}.branches: expected non-empty array")
                continue
            branch_ids: set[str] = set()
            for branch_index, branch in enumerate(branches):
                branch_path = f"{cp_path}.branches[{branch_index}]"
                if not isinstance(branch, dict):
                    errors.append(f"{branch_path}: expected object")
                    continue
                branch_id = branch.get("id")
                if not is_non_empty(branch_id):
                    errors.append(f"{branch_path}.id: required non-empty string")
                elif branch_id in branch_ids:
                    errors.append(f"{branch_path}.id: duplicate branch id {branch_id}")
                else:
                    branch_ids.add(branch_id)
                if not is_non_empty(branch.get("option_text")):
                    errors.append(f"{branch_path}.option_text: required non-empty string")

                beats = branch.get("beats")
                if not isinstance(beats, list) or not beats:
                    errors.append(f"{branch_path}.beats: expected non-empty array")
                else:
                    for beat_index, beat in enumerate(beats):
                        if isinstance(beat, dict) and beat.get("speaker") in protagonist_beats:
                            protagonist_beats[beat["speaker"]] += 1
                        validate_beat(
                            beat,
                            f"{branch_path}.beats[{beat_index}]",
                            character_ids,
                            beat_ids,
                            errors,
                            warnings,
                        )

                effects = branch.get("effects")
                if not isinstance(effects, dict):
                    errors.append(f"{branch_path}.effects: expected object")
                else:
                    for key in ("flags_set", "flags_cleared"):
                        if key not in effects:
                            errors.append(f"{branch_path}.effects.{key}: required field missing")
                        else:
                            require_string_array(errors, effects.get(key), f"{branch_path}.effects.{key}")

                next_data = branch.get("next")
                if not isinstance(next_data, dict):
                    errors.append(f"{branch_path}.next: expected object")
                elif not is_non_empty(next_data.get("completion_flag")):
                    errors.append(f"{branch_path}.next.completion_flag: required non-empty string")

    for char_id, count in protagonist_beats.items():
        if count == 0:
            warnings.append(f"present protagonist has no beats: {char_id}")

    safety = data.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety: expected object")
    else:
        rating = safety.get("content_rating")
        if not is_non_empty(rating):
            errors.append("safety.content_rating: required non-empty string")
        elif rating not in KNOWN_CONTENT_RATINGS:
            warnings.append(f"safety.content_rating is not in known set: {rating}")

    return errors, warnings


def cmd_schema_check(args: argparse.Namespace) -> int:
    path = Path(args.schema_file)
    data, error = load_json(path)
    if error:
        print(f"FAIL: {path}")
        print(f"FAIL: {error}")
        return 1
    if not isinstance(data, dict):
        print(f"FAIL: {path}")
        print("FAIL: schema root must be object")
        return 1
    missing = [key for key in ("$schema", "title", "type", "properties") if key not in data]
    if missing:
        print(f"FAIL: {path}")
        print(f"FAIL: missing required schema keys: {missing}")
        return 1
    print(f"PASS: {path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.scene_file)
    data, error = load_json(path)
    if error:
        print(f"FAIL: {path}")
        print(f"FAIL: {error}")
        return 1
    errors, warnings = validate_scene(data)
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        print(f"FAIL: {path}")
        for error_text in errors:
            print(f"FAIL: {error_text}")
        return 1
    print(f"PASS: {path}")
    return 0


def collect_v1_flags(data: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    required = set(data.get("flags_required", []))
    set_flags = set(data.get("flags_set", []))
    completion = {flag for flag in set_flags if re.match(r"sc_[0-9]{3}_complete$", flag)}
    for cp in data.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if isinstance(branch, dict):
                set_flags.update(branch.get("flags", []))
    return required, set_flags, completion


def collect_v2_flags(data: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    required = set(data.get("flags_required", []))
    set_flags: set[str] = set()
    completion: set[str] = set()
    for cp in data.get("choice_points", []):
        if not isinstance(cp, dict):
            continue
        for branch in cp.get("branches", []):
            if not isinstance(branch, dict):
                continue
            effects = branch.get("effects", {})
            if isinstance(effects, dict):
                set_flags.update(effects.get("flags_set", []))
                set_flags.update(effects.get("flags_cleared", []))
            next_data = branch.get("next", {})
            if isinstance(next_data, dict):
                flag = next_data.get("completion_flag")
                if isinstance(flag, str):
                    completion.add(flag)
                    set_flags.add(flag)
    return required, set_flags, completion


def iter_scenario_files(scenario_dir: Path) -> list[Path]:
    files = set(scenario_dir.glob("SCENARIO_*.json"))
    files.update(scenario_dir.glob("SCENARIO_*.v2.json"))
    return sorted(files)


def cmd_flag_lint(args: argparse.Namespace) -> int:
    scenario_dir = Path(args.scenario_dir)
    files = iter_scenario_files(scenario_dir)
    if not files:
        print(f"FAIL: no scenario files found in {scenario_dir}")
        return 1

    all_required: set[str] = set()
    all_set: set[str] = set()
    completion: set[str] = set()
    parse_errors: list[str] = []
    scanned = 0

    for path in files:
        data, error = load_json(path)
        if error:
            parse_errors.append(f"{path}: {error}")
            continue
        if not isinstance(data, dict):
            parse_errors.append(f"{path}: root is not object")
            continue
        scanned += 1
        if data.get("schema_version") == "2.0":
            required, set_flags, done = collect_v2_flags(data)
        else:
            required, set_flags, done = collect_v1_flags(data)
        all_required.update(required)
        all_set.update(set_flags)
        completion.update(done)

    if parse_errors:
        print(f"FAIL: {scenario_dir}")
        for error in parse_errors:
            print(f"FAIL: {error}")
        return 1

    required_never_set = sorted(all_required - all_set)
    set_never_required = sorted(all_set - all_required)

    print(f"PASS: {scenario_dir}")
    print(f"files scanned: {scanned}")
    print(f"WARN: flags required but never set ({len(required_never_set)}): {required_never_set}")
    print(f"WARN: flags set but never required ({len(set_never_required)}): {set_never_required}")
    print(f"completion flags ({len(completion)}): {sorted(completion)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Voyage Scenario Schema V2 files.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_schema = sub.add_parser("schema-check", help="Check that the JSON Schema artifact is parseable")
    p_schema.add_argument("schema_file")
    p_schema.set_defaults(func=cmd_schema_check)

    p_validate = sub.add_parser("validate", help="Run stdlib semantic validation on a V2 scene")
    p_validate.add_argument("scene_file")
    p_validate.set_defaults(func=cmd_validate)

    p_lint = sub.add_parser("flag-lint", help="Warn about simple flag graph issues")
    p_lint.add_argument("scenario_dir")
    p_lint.set_defaults(func=cmd_flag_lint)

    return parser


def main() -> int:
    _configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
