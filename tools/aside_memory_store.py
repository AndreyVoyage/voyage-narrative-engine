#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Persistent isolated memory store for N6 Character Aside.

Writes only under:
  <root>/private_chats/<save_slot>/<character_id>/

The default root is the OS temp directory, not the repository. This tool does
not read .env files, does not call an LLM or network, and never writes canon
paths such as scenarios/, personas/, novel/, or RenPy v2_* state.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(tempfile.gettempdir()) / "vne_private_chats"
RECENT_LIMIT = 20
SUMMARY_LIMIT = 4000
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class AsideMemoryError(RuntimeError):
    """Clean, user-facing memory store error."""


def append_session(
    *,
    root: Path,
    slot: str,
    character: str,
    session: dict[str, Any],
) -> dict[str, Any]:
    """Append one aside session and update memory_summary.json."""
    base = _character_dir(root, slot, character)
    sessions_dir = base / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_session(session)
    target = sessions_dir / _next_session_filename(sessions_dir, normalized)
    _write_json(target, normalized)
    summary = summarize_memory(root=root, slot=slot, character=character)
    return {"status": "appended", "session_file": str(target), "summary": summary}


def load_memory(
    *,
    root: Path,
    slot: str,
    character: str,
    progress: int,
) -> dict[str, Any]:
    """Load summary/recent/session metadata, excluding sessions from the future."""
    base = _character_dir(root, slot, character)
    sessions = [
        session
        for session in _read_sessions(base)
        if int(session.get("progress_index", -1)) <= progress
    ]
    sessions.sort(key=_session_sort_key)

    filtered_summary = _summary_from_sessions(sessions)
    recent = _recent_from_sessions(sessions)
    sessions_meta = [
        {
            "scene_id": session["scene_id"],
            "beat_id": session["beat_id"],
            "progress_index": session["progress_index"],
            "session_id": session.get("session_id"),
            "file": session.get("_file"),
        }
        for session in sessions
    ]
    return {"summary": filtered_summary, "recent": recent, "sessions_meta": sessions_meta}


def summarize_memory(*, root: Path, slot: str, character: str) -> dict[str, Any]:
    """Deterministically rebuild memory_summary.json from stored sessions."""
    base = _character_dir(root, slot, character)
    base.mkdir(parents=True, exist_ok=True)
    sessions = _read_sessions(base)
    sessions.sort(key=_session_sort_key)
    summary = {
        "character_id": character,
        "save_slot": slot,
        "session_count": len(sessions),
        "max_progress_index": max((int(s["progress_index"]) for s in sessions), default=None),
        "summary": _summary_from_sessions(sessions),
        "sessions_meta": [
            {
                "scene_id": s["scene_id"],
                "beat_id": s["beat_id"],
                "progress_index": s["progress_index"],
                "session_id": s.get("session_id"),
                "file": s.get("_file"),
            }
            for s in sessions
        ],
    }
    _write_json(base / "memory_summary.json", summary)
    return summary


def reset_memory(*, root: Path, slot: str, character: str) -> dict[str, Any]:
    """Remove isolated aside memory for a character."""
    base = _character_dir(root, slot, character)
    if base.exists():
        shutil.rmtree(base)
    return {"status": "reset", "path": str(base)}


def _normalize_session(session: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(session, dict):
        raise AsideMemoryError("session must be a JSON object")
    scene_id = _required_text(session, "scene_id")
    beat_id = _required_text(session, "beat_id")
    progress_index = session.get("progress_index")
    if not isinstance(progress_index, int):
        raise AsideMemoryError("session.progress_index must be an integer")
    transcript = session.get("transcript", [])
    if not isinstance(transcript, list):
        raise AsideMemoryError("session.transcript must be a list")
    clean_transcript = _clean_transcript(transcript)
    summary = session.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        raise AsideMemoryError("session.summary must be a string")
    session_id = session.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise AsideMemoryError("session.session_id must be a string")

    return {
        "scene_id": scene_id,
        "beat_id": beat_id,
        "progress_index": progress_index,
        "session_id": session_id or f"{scene_id}_{beat_id}_{progress_index}",
        "summary": summary.strip(),
        "transcript": clean_transcript,
    }


def _clean_transcript(value: list[Any]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content.strip()})
    return cleaned


def _read_sessions(base: Path) -> list[dict[str, Any]]:
    sessions_dir = base / "sessions"
    if not sessions_dir.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.name):
        data = _read_json(path)
        session = _normalize_session(data)
        session["_file"] = str(path)
        sessions.append(session)
    return sessions


def _summary_from_sessions(sessions: list[dict[str, Any]]) -> str:
    parts = []
    for session in sessions:
        summary = session.get("summary", "")
        if summary:
            parts.append(f"[{session['progress_index']} {session['scene_id']}/{session['beat_id']}] {summary}")
    text = "\n".join(parts)
    return _truncate(text, SUMMARY_LIMIT)


def _recent_from_sessions(sessions: list[dict[str, Any]]) -> list[dict[str, str]]:
    recent: list[dict[str, str]] = []
    for session in sessions:
        recent.extend(session.get("transcript", []))
    return recent[-RECENT_LIMIT:]


def _next_session_filename(sessions_dir: Path, session: dict[str, Any]) -> str:
    prefix = f"{_safe_filename_part(session['scene_id'])}_{_safe_filename_part(session['beat_id'])}"
    index = 1
    while True:
        name = f"{prefix}_{index:03d}.json"
        if not (sessions_dir / name).exists():
            return name
        index += 1


def _character_dir(root: Path, slot: str, character: str) -> Path:
    safe_slot = _safe_id(slot, "slot")
    safe_character = _safe_id(character, "character")
    root_path = Path(root).expanduser().resolve()
    base = (root_path / "private_chats" / safe_slot / safe_character).resolve()
    private_root = (root_path / "private_chats").resolve()
    if private_root != base and private_root not in base.parents:
        raise AsideMemoryError("resolved memory path escapes private_chats root")
    return base


def _safe_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AsideMemoryError(f"{name} must be a non-empty string")
    cleaned = value.strip()
    if not SAFE_ID_RE.match(cleaned) or ".." in cleaned:
        raise AsideMemoryError(f"{name} contains unsafe characters")
    return cleaned


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "item"


def _session_sort_key(session: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        int(session.get("progress_index", -1)),
        str(session.get("scene_id", "")),
        str(session.get("beat_id", "")),
        str(session.get("_file", "")),
    )


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AsideMemoryError(f"session.{key} must be a non-empty string")
    return value.strip()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AsideMemoryError(f"invalid JSON in {path}: {exc}") from None
    except OSError as exc:
        raise AsideMemoryError(f"cannot read {path}: {exc}") from None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(_stable_json(data) + "\n", encoding="utf-8")
    tmp.replace(path)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N6 Character Aside memory store")
    parser.add_argument("command", choices=["append", "load", "summarize", "reset"])
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="isolated memory root")
    parser.add_argument("--slot", required=True, help="save slot id")
    parser.add_argument("--character", required=True, help="character id")
    parser.add_argument("--progress", type=int, help="current canon progress index for load")
    parser.add_argument("--session", help="session JSON file for append")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        root = Path(args.root)
        if args.command == "append":
            if not args.session:
                raise AsideMemoryError("--session is required for append")
            result = append_session(
                root=root,
                slot=args.slot,
                character=args.character,
                session=_read_json(Path(args.session)),
            )
        elif args.command == "load":
            if args.progress is None:
                raise AsideMemoryError("--progress is required for load")
            result = load_memory(root=root, slot=args.slot, character=args.character, progress=args.progress)
        elif args.command == "summarize":
            result = summarize_memory(root=root, slot=args.slot, character=args.character)
        elif args.command == "reset":
            result = reset_memory(root=root, slot=args.slot, character=args.character)
        else:
            raise AsideMemoryError(f"unknown command: {args.command}")
        print(_stable_json(result))
        return 0
    except AsideMemoryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
