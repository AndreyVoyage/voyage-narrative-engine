"""
VNE monolithic scenario JSON → RenPy .rpy preview exporter.

Reads a monolithic scenario JSON with a top-level choice_points list and
generates a skeletal RenPy script for preview / comparison purposes.

Output is written to reports/renpy/ and is gitignored.
It does NOT touch novel/game/ or any canonical VNE source file.

CLI:
    python tools/vne_to_renpy/exporter.py <scenario.json> --output <out.rpy>
"""

import argparse
import json
import sys
from pathlib import Path

# Display names for known character IDs.
DISPLAY_NAMES = {
    "kira": "Кира",
    "sergey": "Сергей",
    "yakov": "Яков",
    "marina": "Марина",
    "andrey": "Андрей",
    "olga": "Ольга",
    "egor": "Егор",
    "maksim": "Максим",
}

# Branch ID suffix → label suffix mapping (1A → 1a).
def _branch_label(branch_id: str) -> str:
    return "branch_" + branch_id.replace("-", "_").lower()


def _escape_rpy(text: str) -> str:
    """Escape a string for use inside RenPy double-quoted say/menu text."""
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", " ")
    return text


def _infer_characters(data: dict) -> dict[str, str]:
    """
    Return {char_id: display_name} for all characters detectable in the scenario.

    Detection sources (in priority order):
      1. Keys ending in _level_start (e.g. kira_level_start → kira)
      2. Branch reaction keys ending in _reaction (e.g. sergey_reaction → sergey)

    SC_008-013 anomaly: sergey_level_start exists but branches use yakov_reaction.
    Both are collected so neither is lost.
    """
    char_ids: set[str] = set()

    for key in data:
        if key.endswith("_level_start"):
            char_ids.add(key[: -len("_level_start")])

    for cp in data.get("choice_points", []):
        for branch in cp.get("branches", []):
            for key in branch:
                if key.endswith("_reaction"):
                    char_ids.add(key[: -len("_reaction")])

    result: dict[str, str] = {}
    for cid in sorted(char_ids):
        result[cid] = DISPLAY_NAMES.get(cid, cid.title())
    return result


def _generate_rpy(data: dict, source_path: str) -> str:
    """Build the full .rpy preview string from parsed scenario data."""
    scenario_id = data.get("id") or data.get("scenario_id") or "UNKNOWN"
    location = data.get("location", "")
    time_of_day = data.get("time", "")
    name = data.get("name", "")

    choice_points = data["choice_points"]
    cp = choice_points[0]
    branches = cp.get("branches", [])

    characters = _infer_characters(data)

    lines: list[str] = []

    # Header comment
    lines.append("# Auto-generated preview from VNE scenario JSON.")
    lines.append(f"# Source: {source_path}")
    lines.append("# Do not edit manually.")
    lines.append("")

    # Character defines
    for char_id, display_name in characters.items():
        lines.append(f'define {char_id} = Character("{display_name}")')
    lines.append("")

    # label start
    lines.append("label start:")
    lines.append("")

    # Opening narrator lines from scenario metadata
    if name:
        lines.append(f'    narrator "{_escape_rpy(name)}"')
    if location and time_of_day:
        lines.append(f'    narrator "{_escape_rpy(location.capitalize())}. {_escape_rpy(time_of_day.capitalize())}."')
    elif location:
        lines.append(f'    narrator "{_escape_rpy(location.capitalize())}."')

    # Question narrator line from CP
    question = cp.get("question", "")
    if question:
        lines.append(f'    narrator "{_escape_rpy(question)}"')

    lines.append("")
    lines.append("    menu:")

    # Menu choices
    for branch in branches:
        action = _escape_rpy(branch.get("action", branch["id"]))
        label = _branch_label(branch["id"])
        lines.append(f'        "{action}":')
        lines.append(f"            jump {label}")

    # Branch labels
    for branch in branches:
        label = _branch_label(branch["id"])
        lines.append("")
        lines.append("")
        lines.append(f"label {label}:")
        lines.append("")

        # Emit flags as comments
        flags = branch.get("flags", [])
        if flags:
            lines.append(f"    # flags: {', '.join(flags)}")

        # Emit reaction fields as narrator prose with TODO markers
        for key, value in branch.items():
            if not key.endswith("_reaction"):
                continue
            char_id = key[: -len("_reaction")]
            escaped = _escape_rpy(str(value))
            lines.append(f"    # [{char_id}_reaction] TODO: convert prose to authored dialogue")
            lines.append(f'    narrator "{escaped}"')

        lines.append("    jump scene_end")

    # scene_end label
    lines.append("")
    lines.append("")
    lines.append("label scene_end:")
    lines.append("")
    lines.append('    narrator "Конец preview-сцены."')
    lines.append("    return")
    lines.append("")

    return "\n".join(lines)


def export(scenario_path: Path, output_path: Path) -> None:
    # Read and parse source JSON
    try:
        raw = scenario_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"ERROR: scenario file not found: {scenario_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {scenario_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate choice_points
    choice_points = data.get("choice_points")
    if not isinstance(choice_points, list) or len(choice_points) == 0:
        print(
            f"ERROR: {scenario_path} has no 'choice_points' list. "
            "Modular scenarios and library/matrix files are not supported.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate output
    source_label = scenario_path.as_posix()
    content = _generate_rpy(data, source_label)

    # Write UTF-8 without BOM
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    chars = len(content)
    byt = len(content.encode("utf-8"))
    print(f"OK: wrote {output_path}  ({chars} chars, {byt} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a VNE monolithic scenario JSON to a RenPy .rpy preview."
    )
    parser.add_argument("scenario", type=Path, help="Path to monolithic scenario JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output .rpy path")
    args = parser.parse_args()

    export(args.scenario, args.output)


if __name__ == "__main__":
    main()
