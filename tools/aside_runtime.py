#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Offline Character Aside orchestrator for N6.

Runs one aside turn: builds a past-only context, calls the LLM provider,
and appends the turn to isolated aside memory. This tool never writes to
canon paths (scenarios/, personas/, novel/, RenPy v2_* state).

Provider is hardcoded to "mock" via the CLI; the API accepts a provider
argument for symmetry, but N6e uses mock only, so no network is required.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure sibling tools in this directory are importable regardless of CWD.
_TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOLS_DIR))

import aside_context_builder
import aside_memory_store
import llm_provider


class AsideRuntimeError(RuntimeError):
    """Clean, user-facing runtime error."""


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def run_aside_turn(
    character_id: str,
    canon_snapshot: dict[str, Any],
    player_message: str,
    memory_root: Path,
    save_slot: str,
    provider: str = "mock",
) -> dict[str, Any]:
    """Run one Character Aside turn and append it to isolated memory.

    Returns {"reply": str, "appended": bool}.
    """
    if not isinstance(character_id, str) or not character_id.strip():
        raise AsideRuntimeError("character_id must be a non-empty string")
    if not isinstance(canon_snapshot, dict):
        raise AsideRuntimeError("canon_snapshot must be a JSON object")
    if not isinstance(player_message, str) or not player_message.strip():
        raise AsideRuntimeError("player_message must be a non-empty string")

    character = character_id.strip().lower()
    progress = canon_snapshot.get("progress_index", 0)
    if not isinstance(progress, int):
        raise AsideRuntimeError("canon_snapshot.progress_index must be an integer")

    root = Path(memory_root)

    # Load isolated aside memory (past-only relative to current progress).
    memory = aside_memory_store.load_memory(
        root=root,
        slot=save_slot,
        character=character,
        progress=progress,
    )

    # Build LLM messages from persona + past canon + aside memory.
    messages = aside_context_builder.build_context(
        character_id=character,
        canon_snapshot=canon_snapshot,
        aside_memory=memory,
        player_message=player_message.strip(),
    )

    # N6e: mock provider only, deterministic, no network.
    selected_provider = provider if provider else "mock"
    if selected_provider != "mock":
        raise AsideRuntimeError("N6e supports only the mock provider")
    reply = llm_provider.complete(messages, provider="mock")

    # Append turn to isolated aside memory.
    session = {
        "scene_id": canon_snapshot.get("scene_id", "unknown"),
        "beat_id": canon_snapshot.get("beat_id", "unknown"),
        "progress_index": progress,
        "summary": f"Player: {player_message.strip()}",
        "transcript": [
            {"role": "user", "content": player_message.strip()},
            {"role": "assistant", "content": reply},
        ],
    }
    aside_memory_store.append_session(
        root=root,
        slot=save_slot,
        character=character,
        session=session,
    )

    return {"reply": reply, "appended": True}


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AsideRuntimeError(f"invalid JSON in {path}: {exc}") from None
    except OSError as exc:
        raise AsideRuntimeError(f"cannot read {path}: {exc}") from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="N6 Character Aside runtime (mock LLM, isolated memory)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    turn = sub.add_parser("turn", help="run one aside turn")
    turn.add_argument("--character", required=True, help="persona id, e.g. kira")
    turn.add_argument(
        "--snapshot", required=True, help="path to canon snapshot JSON file"
    )
    turn.add_argument("--message", required=True, help="player message")
    turn.add_argument(
        "--root", required=True, help="isolated aside memory root directory"
    )
    turn.add_argument("--slot", required=True, help="save slot id")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "turn":
            snapshot = _read_json_file(Path(args.snapshot))
            result = run_aside_turn(
                character_id=args.character,
                canon_snapshot=snapshot,
                player_message=args.message,
                memory_root=Path(args.root),
                save_slot=args.slot,
                provider="mock",
            )
            print(result["reply"])
            return 0
        raise AsideRuntimeError(f"unknown command: {args.command}")
    except AsideRuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
