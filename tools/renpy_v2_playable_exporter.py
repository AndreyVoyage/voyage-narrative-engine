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

# Bare-CLI execution (`python tools/renpy_v2_playable_exporter.py ...`) puts
# `tools/` on sys.path, not the repository root, so the already-public
# `tools.vne_to_renpy` adapter used for optional `--visual-*` builds cannot be
# imported. Add the repo root defensively; a no-op under pytest / `-m`.
_REPO_ROOT_STR = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from services.production_media_asset_binding import (  # noqa: E402
    ProductionMediaAssetBindingError,
)

KNOWN_RENPY_CHARACTERS = {"kira", "yakov", "sergey"}

# N5A: only this explicit output path inside novel/game is allowed.
ALLOWED_PLAYABLE_OUTPUT = Path("novel/game/scenes_v2_generated.rpy")

# Canonical Visual Asset Registry, repo-root-relative. Made explicit at
# resolution time when a full --visual-* triplet is supplied without an
# explicit --visual-registry override.
DEFAULT_VISUAL_REGISTRY = Path("scenarios/visual_assets/ASSET_REGISTRY.json")


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
    # Ren'Py text-substitution / text-tag metacharacters that open a parse
    # state MUST be doubled so player-visible source text stays literal:
    # '[' → '[[' (opens interpolation) and '{' → '{{' (opens a text tag).
    # ']' and '}' close such states and are already literal in LITERAL state,
    # so they are intentionally NOT doubled (Ren'Py substitutions.py never
    # treats ']' as special; no ']]' collapse rule exists).
    value = value.replace("[", "[[")
    value = value.replace("{", "{{")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(value.splitlines())


def renpy_stmt_escape(text: Any) -> str:
    """Escape a string value for embedding inside a Ren'Py Python ``$`` statement.

    Produces a safe Python string literal that can contain Cyrillic, quotes,
    apostrophes, backslashes, and line breaks. Prefers single-quoted literals
    with backslash-escaped single quotes and backslashes.
    """
    if text is None:
        return "''"
    s = str(text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = " ".join(s.splitlines())
    return "'{}'".format(s)


def renpy_played_event_str(event_dict: dict[str, Any]) -> str:
    """Build a Ren'Py Python literal for a played-event record dict.

    Produces a ``{...}`` dict literal using single-quoted string values
    that are safe for Cyrillic, quotes, apostrophes, backslashes, and
    line breaks. Never uses ``repr()`` or ``json.dumps()`` for Ren'Py
    code generation — all escaping is explicit.
    """
    parts = []
    for key in ("scene_id", "beat_id", "kind", "speaker", "summary"):
        value = event_dict.get(key, "")
        parts.append("'{}': {}".format(
            str(key),
            renpy_stmt_escape(value),
        ))
    return "{ " + ", ".join(parts) + " }"


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


def beat_kind(beat: dict[str, Any]) -> str:
    """Map beat type to the compact event kind label."""
    beat_type = beat.get("type")
    if beat_type == "dialogue":
        return "dialogue"
    if beat_type == "action":
        return "action"
    if beat_type == "thought":
        return "thought"
    return "narration"


def beat_summary(beat: dict[str, Any]) -> str:
    """Extract a short, bounded summary from the beat's primary text channel."""
    channel = beat_channel(beat)
    text = beat.get(channel)
    if not isinstance(text, str) or not text.strip():
        return ""
    summary = " ".join(text.strip().splitlines()).strip()
    if len(summary) > 200:
        summary = summary[:197] + "..."
    return summary


def display_name(scene: dict[str, Any], character_id: Any) -> str:
    if character_id is None:
        return "Narrator"
    for character in scene.get("characters", []):
        if isinstance(character, dict) and character.get("id") == character_id:
            name = character.get("display_name")
            if isinstance(name, str) and name.strip():
                return name
    return str(character_id)


def beat_speaker_str(scene: dict[str, Any], beat: dict[str, Any]) -> str:
    """Return the speaker name (or empty string) for an event record."""
    speaker = beat.get("speaker")
    if speaker is None:
        return ""
    return display_name(scene, speaker)


def emit_set_scene_beat(scene_id: str, beat_id: str) -> str:
    """Generate a ``$ _vne_aside_set_scene_beat(...)`` Ren'Py statement."""
    return "$ _vne_aside_set_scene_beat({}, {})".format(
        renpy_stmt_escape(scene_id),
        renpy_stmt_escape(beat_id),
    )


def emit_note_played_event(scene_id: str, beat: dict[str, Any], speaker: str = "") -> str:
    """Generate a ``$ _vne_aside_note_played_event({...})`` Ren'Py statement."""
    beat_id = beat.get("beat_id", "")
    kind = beat_kind(beat)
    summary = beat_summary(beat)
    event = {
        "scene_id": scene_id,
        "beat_id": str(beat_id),
        "kind": kind,
        "speaker": speaker,
        "summary": summary,
    }
    return "$ _vne_aside_note_played_event({})".format(renpy_played_event_str(event))


# ---------------------------------------------------------------------------
# Render functions (with runtime-context hooks)
# ---------------------------------------------------------------------------

def render_beat(scene: dict[str, Any], beat: dict[str, Any]) -> list[str]:
    """Render a single beat with set-position-before and note-event-after hooks."""
    scene_id = scene.get("id", "")
    beat_id = beat.get("beat_id")
    beat_type = beat.get("type")
    speaker = beat.get("speaker")
    channel = beat_channel(beat)
    text = beat.get(channel)
    lines: list[str] = []

    if beat_id:
        lines.append(f"    # beat_id: {beat_id}")
        # Set current scene and beat position BEFORE rendering content.
        lines.append(f"    {emit_set_scene_beat(str(scene_id), str(beat_id))}")

    if beat_type == "dialogue":
        name = display_name(scene, speaker)
        lines.append(f'    narrator "{renpy_escape(name)}: {renpy_escape(text)}"')
    elif beat_type == "action":
        name = display_name(scene, speaker)
        # No synthetic square brackets: "[...]" would be parsed by Ren'Py as
        # interpolation. Use a plain-text label-separator form instead.
        lines.append(f'    narrator "{renpy_escape(name)} action: {renpy_escape(text)}"')
    elif beat_type == "thought":
        visibility = beat.get("thought_visibility")
        name = display_name(scene, speaker)
        marker = f"thought:{name}; visibility={visibility}"
        # No synthetic square brackets around the marker, same reason as above.
        lines.append(f'    narrator "{renpy_escape(marker)}: {renpy_escape(text)}"')
    else:
        lines.append(f'    narrator "{renpy_escape(text)}"')

    # Note the played event AFTER rendering content.
    _spk = beat_speaker_str(scene, beat)
    lines.append(f"    {emit_note_played_event(str(scene_id), beat, speaker=_spk)}")
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


def render_menu_choice_event(scene_id: str, branch_id: str, option_text: str) -> str:
    """Generate a ``$ _vne_aside_note_played_event(...)`` for the selected choice.

    This is emitted only inside the chosen branch, never for unselected choices.
    """
    event = {
        "scene_id": str(scene_id),
        "beat_id": str(branch_id),
        "kind": "choice",
        "speaker": "",
        "summary": "Choice: " + str(option_text or branch_id),
    }
    return "$ _vne_aside_note_played_event({})".format(renpy_played_event_str(event))


def render_branch(scene: dict[str, Any], choice_point: dict[str, Any], branch: dict[str, Any]) -> list[str]:
    branch_id = branch.get("id")
    label = branch_label_id(scene.get("id"), branch_id)
    scene_id = str(scene.get("id", ""))
    option_text = branch.get("option_text", "")
    lines = ["", f"label {label}:", ""]

    # Record the selected choice ONLY inside the chosen branch.
    lines.append(f"    {render_menu_choice_event(scene_id, str(branch_id), str(option_text))}")

    # Set current position to the branch entry, then render beats.
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


def render_scene(
    scene: dict[str, Any],
    scene_path: Path,
    *,
    visual_asset: Any | None = None,
    visual_statement_kind: str | None = None,
) -> str:
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

    # C4-U-EMIT v0: at most one explicit, scene-level visual statement,
    # emitted immediately after the scene label and before any position hook
    # or narrative/beat content. The visual semantics (scene vs show) are
    # supplied explicitly by the caller; this exporter never infers them from
    # scene JSON, Registry category, asset_id, media_item_id, character_id,
    # relative_path, or filename. No Registry lookup, no binding construction,
    # and no resolution happen here.
    if visual_asset is not None or visual_statement_kind is not None:
        from tools.vne_to_renpy.visual_statement_emitter import emit_visual_statement

        for _visual_line in emit_visual_statement(
            visual_asset, statement_kind=visual_statement_kind
        ):
            lines.append(f"    {_visual_line}")

    # Set scene-level position at the start label.
    lines.append(f"    {emit_set_scene_beat(str(scene_id), 'start')}")

    if scene_name:
        lines.append(f'    narrator "{renpy_escape(scene_name)}"')

    for beat in scene.get("entry_beats", []):
        if isinstance(beat, dict):
            lines.extend(render_beat(scene, beat))

    prompt = choice_point.get("prompt")
    if prompt:
        lines.append("")
        # Set position to the choice point before showing the menu.
        cp_id = choice_point.get("id", "menu")
        lines.append(f"    {emit_set_scene_beat(str(scene_id), str(cp_id))}")
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


def resolve_build_visual(
    *,
    visual_media_item_id: str | None,
    visual_asset_id: str | None,
    visual_statement_kind: str | None,
    visual_registry: str | None,
) -> tuple[Any | None, str | None]:
    """Resolve optional build-time visual inputs to ``(ResolvedAsset, kind)``.

    All-or-nothing on the core triplet (``media_item_id``, ``asset_id``,
    ``statement_kind``): returns ``(None, None)`` only when the triplet is
    entirely absent AND no ``--visual-registry`` was given. Any partial
    combination, or ``--visual-registry`` supplied without the triplet, fails
    closed with ``ValueError``. Resolution reuses the existing public adapter
    ``tools.vne_to_renpy.resolve_media_asset_for_renpy``; its own fail-closed
    errors propagate unchanged. ``media_item_id`` and ``asset_id`` are passed
    through as distinct values and never derived from one another. The
    statement kind is passed through verbatim and never inferred.
    """
    triplet = (visual_media_item_id, visual_asset_id, visual_statement_kind)
    present = [value for value in triplet if value is not None]

    if not present and visual_registry is None:
        return None, None

    if len(present) != 3:
        raise ValueError(
            "visual build inputs are all-or-nothing: --visual-media-item-id, "
            "--visual-asset-id and --visual-statement-kind must be supplied "
            "together (got media_item_id={!r}, asset_id={!r}, "
            "statement_kind={!r}, registry={!r})".format(
                visual_media_item_id,
                visual_asset_id,
                visual_statement_kind,
                visual_registry,
            )
        )

    registry_path = (
        Path(visual_registry) if visual_registry is not None else DEFAULT_VISUAL_REGISTRY
    )
    if not registry_path.is_absolute():
        registry_path = repo_root() / registry_path

    from tools.vne_to_renpy import resolve_media_asset_for_renpy

    resolved_asset = resolve_media_asset_for_renpy(
        media_item_id=visual_media_item_id,
        asset_id=visual_asset_id,
        registry_path=registry_path,
    )
    return resolved_asset, visual_statement_kind


def cmd_build(args: argparse.Namespace) -> int:
    if not args.output:
        return fail("build requires explicit --output")

    output = Path(args.output)
    try:
        assert_safe_output_path(output)
        visual_asset, visual_statement_kind = resolve_build_visual(
            visual_media_item_id=getattr(args, "visual_media_item_id", None),
            visual_asset_id=getattr(args, "visual_asset_id", None),
            visual_statement_kind=getattr(args, "visual_statement_kind", None),
            visual_registry=getattr(args, "visual_registry", None),
        )
        scene_path, scene = load_scene(args.scene)
        generated_labels = collect_generated_labels(scene)
        assert_no_label_collision(generated_labels)
        if visual_asset is None:
            text = render_scene(scene, scene_path)
        else:
            text = render_scene(
                scene,
                scene_path,
                visual_asset=visual_asset,
                visual_statement_kind=visual_statement_kind,
            )
        resolved = output if output.is_absolute() else repo_root() / output
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text, encoding="utf-8", newline="\n")
        print(f"PASS: wrote playable RenPy V2 scene to {resolved}")
        return 0
    except (ValueError, ProductionMediaAssetBindingError) as exc:
        return fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Scenario Schema V2 scenes to playable RenPy (.rpy)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a playable RenPy scene from V2 JSON")
    p_build.add_argument("scene")
    p_build.add_argument("--output", required=True, help="Output .rpy path")
    # Optional, all-or-nothing build-time visual inputs. When the triplet is
    # supplied the scene-level image is resolved via the existing adapter and
    # forwarded to render_scene's visual hook; absent -> unchanged text-only
    # build. The statement kind is always explicit (never inferred).
    p_build.add_argument(
        "--visual-media-item-id", dest="visual_media_item_id", default=None
    )
    p_build.add_argument("--visual-asset-id", dest="visual_asset_id", default=None)
    p_build.add_argument(
        "--visual-statement-kind",
        dest="visual_statement_kind",
        choices=("scene", "show"),
        default=None,
    )
    p_build.add_argument(
        "--visual-registry",
        dest="visual_registry",
        default=None,
        help=(
            "Visual Asset Registry JSON path; defaults to "
            "scenarios/visual_assets/ASSET_REGISTRY.json when a full "
            "--visual-* triplet is supplied"
        ),
    )
    p_build.set_defaults(func=cmd_build)

    return parser


def main() -> int:
    configure_encoding()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
