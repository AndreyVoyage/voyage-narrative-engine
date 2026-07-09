#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline, read-only Character Aside context builder for N6.

Builds chat messages from:
- compact modular persona data in personas/<character_id>/
- a caller-provided past-only canon snapshot
- isolated aside memory
- the current player message

The tool uses stdlib only, does not read .env files, does not call an LLM, does
not access the network, and does not write repository/canon files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PERSONAS_DIR = REPO_ROOT / "personas"
RECENT_LIMIT = 20

SNAPSHOT_KEYS = (
    "scene_id",
    "beat_id",
    "progress_index",
    "flags",
    "completed_scenes",
    "levels",
    "relationships",
    "content_rating",
)


class AsideContextError(RuntimeError):
    """Clean, user-facing context builder error."""


def build_context(
    character_id: str,
    canon_snapshot: dict[str, Any],
    aside_memory: dict[str, Any] | None,
    player_message: str,
) -> list[dict[str, str]]:
    """Build deterministic LLM messages for a Character Aside conversation."""
    normalized_id = _normalize_character_id(character_id)
    snapshot = _require_object(canon_snapshot, "canon_snapshot")
    memory = _require_object(aside_memory or {}, "aside_memory")
    if not isinstance(player_message, str) or not player_message.strip():
        raise AsideContextError("player_message must be a non-empty string")

    persona_dir = PERSONAS_DIR / normalized_id
    if not persona_dir.is_dir():
        raise AsideContextError(f"persona not found: personas/{normalized_id}")

    persona_block = _build_persona_block(persona_dir, normalized_id, snapshot)
    system_content = "\n\n".join(
        [
            persona_block,
            _build_safety_block(snapshot),
            _build_frame_block(),
        ]
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    messages.append({"role": "system", "content": _build_snapshot_block(snapshot)})

    summary = memory.get("summary")
    if isinstance(summary, str) and summary.strip():
        messages.append(
            {
                "role": "system",
                "content": "Aside memory summary (isolated, non-canonical):\n" + summary.strip(),
            }
        )

    messages.extend(_recent_messages(memory.get("recent")))
    messages.append({"role": "user", "content": player_message.strip()})
    return messages


def _normalize_character_id(character_id: str) -> str:
    if not isinstance(character_id, str) or not character_id.strip():
        raise AsideContextError("character_id must be a non-empty string")
    value = character_id.strip().lower().replace("\\", "/")
    if "/" in value or ".." in value:
        raise AsideContextError("character_id must be a simple persona id")
    return value


def _build_persona_block(persona_dir: Path, character_id: str, snapshot: dict[str, Any]) -> str:
    identity = _read_optional_json(persona_dir / "core" / "IDENTITY.json")
    psychology = _read_optional_json(persona_dir / "psychology" / "BASE.json")
    speech = _read_optional_json(persona_dir / "speech" / "SPEECH_MATRIX.json")
    relationships = _read_optional_json(persona_dir / "relationships" / "MATRIX.json")

    display_name = _first_text(identity, ("name", "display_name", "id")) or character_id
    current_level = _current_level(snapshot, character_id)
    speech_level = _speech_level_block(speech, current_level)

    compact = {
        "id": character_id,
        "name": display_name,
        "current_level": current_level,
        "identity": _pick(identity, ("name", "variables")),
        "psychology": _pick(
            psychology,
            (
                "core_conflict",
                "secret_desire",
                "shame_layers",
                "sensory_register",
                "desire_model",
                "attachment_response",
            ),
        ),
        "speech": {
            "description": speech.get("description") if isinstance(speech, dict) else None,
            "signature_patterns": speech.get("signature_patterns") if isinstance(speech, dict) else None,
            "current_level": speech_level,
        },
        "relationships": _pick(relationships, ("relationships",)),
    }
    return "Persona compact source (modular personas/<id>, source of truth):\n" + _stable_json(compact)


def _build_safety_block(snapshot: dict[str, Any]) -> str:
    rating = snapshot.get("content_rating") or "not specified"
    return "\n".join(
        [
            "Safety/tone: RN-SAFETY-STYLE-1 applies.",
            f"Content rating from canon snapshot: {rating}.",
            "Respect player boundaries, consent, stop words, and platform limits.",
            "Do not generate promises or claims that change canon, flags, levels, relationships, or future scenes.",
        ]
    )


def _build_frame_block() -> str:
    return "\n".join(
        [
            "In-fiction frame: вы здесь, наедине, когда время остановилось вокруг сцены.",
            "This is a private aside: canon reads nothing from this chat; this chat reads only past canon.",
            "Answer as the character in the present moment, without knowledge of future beats.",
        ]
    )


def _build_snapshot_block(snapshot: dict[str, Any]) -> str:
    past_only = {key: snapshot[key] for key in SNAPSHOT_KEYS if key in snapshot}
    return (
        "Past-only canon snapshot. Use only these supplied facts; do not infer or read future scenes/beats:\n"
        + _stable_json(past_only)
    )


def _current_level(snapshot: dict[str, Any], character_id: str) -> str | None:
    levels = snapshot.get("levels")
    if isinstance(levels, dict):
        value = levels.get(character_id)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _speech_level_block(speech: dict[str, Any], current_level: str | None) -> dict[str, Any] | None:
    if not isinstance(speech, dict) or not current_level:
        return None
    matrix = speech.get("matrix")
    if not isinstance(matrix, dict):
        return None

    candidates = [current_level]
    if "-" in current_level:
        head = current_level.split("-", 1)[0]
        candidates.extend([f"{head}-A", f"{head}-B"])
    for key in candidates:
        if key in matrix and isinstance(matrix[key], dict):
            return _pick(
                matrix[key],
                (
                    "ton",
                    "tempo",
                    "vocabulary",
                    "thought_length",
                    "action_detail",
                    "signature_phrases",
                ),
            )
    return {"level_note": f"no exact speech block for {current_level}"}


def _recent_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in value[-RECENT_LIMIT:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content.strip()})
    return cleaned


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = _read_json_file(path)
    return data if isinstance(data, dict) else {}


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AsideContextError(f"invalid JSON in {path}: {exc}") from None
    except OSError as exc:
        raise AsideContextError(f"cannot read {path}: {exc}") from None


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AsideContextError(f"{name} must be a JSON object")
    return value


def _pick(data: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in keys if key in data}


def _first_text(data: Any, keys: tuple[str, ...]) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N6 Character Aside context builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build aside LLM messages")
    build.add_argument("--character", required=True, help="persona id, e.g. kira")
    build.add_argument("--snapshot", required=True, help="canon snapshot JSON path")
    build.add_argument("--memory", required=True, help="aside memory JSON path")
    build.add_argument("--message", required=True, help="player message")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "build":
            snapshot = _read_json_file(Path(args.snapshot))
            memory = _read_json_file(Path(args.memory))
            messages = build_context(args.character, snapshot, memory, args.message)
            print(_stable_json(messages))
            return 0
        raise AsideContextError(f"unknown command: {args.command}")
    except AsideContextError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
