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
import hashlib
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

    # v0 Scene Context Bridge: inject static scene metadata when available.
    # This is a detached plain-data snapshot captured on the Ren'Py main thread
    # before the worker starts. When absent, the message is simply skipped.
    scene_context = snapshot.get("scene_context")
    if isinstance(scene_context, dict):
        messages.append(
            {"role": "system", "content": _build_scene_context_block(scene_context)}
        )

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


def _build_scene_context_block(scene_context: dict) -> str:
    """Render the [CURRENT STORY CONTEXT] system message from a bridge snapshot.

    When context is unavailable, returns a brief unavailability note so the
    model knows it is operating without concrete scene awareness.
    """
    if not isinstance(scene_context, dict):
        return "[CONTEXT UNAVAILABLE] Scene context bridge did not return a valid snapshot."

    available = scene_context.get("context_available")
    if not available:
        reason = scene_context.get("reason", "unknown reason")
        return (
            "[CONTEXT UNAVAILABLE]\n"
            "The Character Aside cannot determine the current narrative situation.\n"
            f"Reason: {reason}\n"
            "Respond as Kira in a neutral conversational mode. "
            "Do not invent a scene, location, or recent events."
        )

    lines = ["[CURRENT STORY CONTEXT]"]

    title = scene_context.get("scene_title")
    scene_id = scene_context.get("scene_id")
    if title and scene_id:
        lines.append(f"Scene: «{title}» ({scene_id})")
    elif title:
        lines.append(f"Scene: «{title}»")
    elif scene_id:
        lines.append(f"Scene: {scene_id}")

    beat_id = scene_context.get("beat_id")
    if beat_id:
        lines.append(f"Current beat: {beat_id}")

    location = scene_context.get("location")
    time_or_phase = scene_context.get("time_or_phase")
    if location and time_or_phase:
        lines.append(f"Location: {location} — {time_or_phase}")
    elif location:
        lines.append(f"Location: {location}")
    elif time_or_phase:
        lines.append(f"Time/phase: {time_or_phase}")

    active_chars = scene_context.get("active_characters")
    if isinstance(active_chars, list) and active_chars:
        names = ", ".join(
            entry["name"] for entry in active_chars
            if isinstance(entry, dict) and "name" in entry
        )
        if names:
            lines.append(f"Characters present: {names}")

    rating = scene_context.get("content_rating", "not specified")
    lines.append(f"Content rating: {rating}")

    # Already played section — derived ONLY from runtime played events.
    played = scene_context.get("played_events")
    if isinstance(played, list) and played:
        lines.append("")
        lines.append("Already played:")
        for event in played:
            if isinstance(event, dict):
                summary = event.get("summary", "")
                kind = event.get("kind", "")
                speaker = event.get("speaker", "")
                if speaker:
                    entry = f"- [{kind}] {speaker}: {summary}"
                else:
                    entry = f"- [{kind}] {summary}"
                lines.append(entry)

    lines.append("")
    lines.append(
        "Instructions: "
        "only Already played entries are completed events; "
        "do not infer unlisted events; "
        "do not assume unselected choices occurred; "
        "do not expose future branches; "
        "do not modify game state."
    )

    return "\n".join(lines)


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


# ---------------------------------------------------------------------------
# QA Gap 01 diagnostics — pure, testable helpers
# ---------------------------------------------------------------------------

# Whitelist of keys permitted in the fingerprint payload.
_FINGERPRINT_KEYS = frozenset({
    "scene_id",
    "beat_id",
    "progress_index",
    "flags",
    "completed_scenes",
    "levels",
    "relationships",
    "content_rating",
})

# Allowed scene-context keys for fingerprinting (static framing only).
_FINGERPRINT_SCENE_CTX_KEYS = frozenset({
    "scene_id",
    "scene_title",
    "location",
    "time_or_phase",
    "active_characters",
    "content_rating",
    "beat_id",
    "played_events",
})


def _sanitize_plain_value(value: Any) -> Any:
    """Recursively convert a plain-data value to a canonically-sortable form."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, list):
        # Sort list-of-dict by stable JSON representation.
        items: list[Any] = []
        for item in value:
            items.append(_sanitize_plain_value(item))
        # Sort by canonical JSON to make list order stable.
        items.sort(
            key=lambda x: json.dumps(
                x, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )
        return items
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k in sorted(value.keys()):
            result[str(k)] = _sanitize_plain_value(value[k])
        return result
    return str(value)


def _sanitize_snapshot_for_fingerprint(
    canon_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Return a stable, shallow-copied subset safe for fingerprint hashing.

    Only whitelisted keys are included. Lists are sorted where order is not
    guaranteed. Uses deep-copy of plain-data values so mutations cannot
    affect the fingerprint input.
    """
    if not isinstance(canon_snapshot, dict):
        return {}

    sanitized: dict[str, Any] = {}
    for key in sorted(_FINGERPRINT_KEYS):
        value = canon_snapshot.get(key)
        if value is None:
            continue
        sanitized[key] = _sanitize_plain_value(value)

    # Include whitelisted scene-context fields when available.
    scene_ctx = canon_snapshot.get("scene_context")
    if isinstance(scene_ctx, dict):
        ctx_sanitized: dict[str, Any] = {}
        for key in _FINGERPRINT_SCENE_CTX_KEYS:
            value = scene_ctx.get(key)
            if value is None:
                continue
            ctx_sanitized[key] = _sanitize_plain_value(value)
        if ctx_sanitized:
            sanitized["scene_context"] = ctx_sanitized

    return sanitized


def compute_context_fingerprint(canon_snapshot: dict[str, Any]) -> str:
    """Return a 64-character lowercase SHA-256 hex fingerprint.

    The fingerprint is computed over a canonical JSON representation
    of a sanitized, whitelisted subset of the canon snapshot. It does
    NOT include secrets, paths, full prompts, provider responses, or
    mutable Ren'Py store references.
    """
    sanitized = _sanitize_snapshot_for_fingerprint(canon_snapshot)
    canonical_bytes = json.dumps(
        sanitized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def detect_context_block_included(messages: list[dict[str, str]]) -> bool:
    """Return True when the messages list contains a story-context block.

    Detects either the available [CURRENT STORY CONTEXT] block or the safe
    [CONTEXT UNAVAILABLE] block by checking the content of system messages
    inserted by _build_scene_context_block.  Returns True for either variant
    because the model is informed about current story context (or its absence).
    Returns False only when no such block was added.
    """
    if not isinstance(messages, list):
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "system":
            continue
        content = msg.get("content")
        if not isinstance(content, str):
            continue
        if "[CURRENT STORY CONTEXT]" in content or "[CONTEXT UNAVAILABLE]" in content:
            return True
    return False


def compute_played_event_count(canon_snapshot: dict[str, Any]) -> int:
    """Return the count of detached played events in the snapshot.

    Counts only the detached ``played_events`` list inside the
    ``scene_context`` sub-dict.  Returns 0 when the list is missing,
    None, or not a list.  Never counts future events, static scene
    metadata, or diagnostics records.
    """
    if not isinstance(canon_snapshot, dict):
        return 0
    scene_ctx = canon_snapshot.get("scene_context")
    if not isinstance(scene_ctx, dict):
        return 0
    played = scene_ctx.get("played_events")
    if isinstance(played, list):
        return len(played)
    return 0


def build_context_diagnostics(
    character_id: str,
    canon_snapshot: dict[str, Any],
    aside_memory: dict[str, Any] | None,
    player_message: str,
) -> dict[str, Any]:
    """Compute a complete diagnostics dict for one Character Aside turn.

    Returns a plain-data dict suitable for marshalling across the
    Ren'Py thread boundary.  All six required fields are generated from
    the same turn data so they are internally consistent.
    """
    messages = build_context(character_id, canon_snapshot, aside_memory, player_message)

    scene_ctx = canon_snapshot.get("scene_context") if isinstance(canon_snapshot, dict) else None
    if isinstance(scene_ctx, dict):
        context_available = bool(scene_ctx.get("context_available"))
    else:
        context_available = False

    return {
        "context_available": context_available,
        "scene_id": str(canon_snapshot.get("scene_id", "")) if isinstance(canon_snapshot, dict) else "",
        "current_beat": str(canon_snapshot.get("beat_id", "")) if isinstance(canon_snapshot, dict) else "",
        "played_event_count": compute_played_event_count(canon_snapshot),
        "context_block_included": detect_context_block_included(messages),
        "context_fingerprint": compute_context_fingerprint(canon_snapshot),
    }


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
