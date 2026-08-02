#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N9 PAC v0 -- thin CLI adapter.

All business logic resides in ``services/persona_authoring/``.
This module only parses arguments and calls the domain service.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Bootstrap: ensure the repo root is on sys.path so that
# `py .\\tools\\pac_cli.py` and `py -m tools.pac_cli` both work.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Ensure stdout uses UTF-8 on Windows so Cyrillic help text renders.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except (AttributeError, OSError):
    pass

from services.persona_authoring import (
    GatewayAdapter,
    PacApprovalError,
    PacError,
    PacRequest,
    PacService,
    PacStorage,
    validate_fmdr,
)
from services.persona_gateway import PersonaCatalog


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pac",
        description="N9 Persona Authoring Companion v0",
        epilog=(
            "Environment:\n"
            "  PERSONA_ROOTS       JSON mapping character_id -> persona_dir.\n"
            "                      Required for real persona loading.\n"
            "                      Example: '{\"kira\":\"personas/kira\"}'\n"
            "  OPENAI_API_KEY      Required for --provider cloud.\n"
            "\n"
            "Providers:\n"
            "  mock                Offline, deterministic. No credentials.\n"
            "  local               Ollama-compatible, default http://localhost:11434.\n"
            "                      Requires explicit --model.\n"
            "  cloud               OpenAI-compatible, default https://api.openai.com.\n"
            "                      Requires --model and OPENAI_API_KEY.\n"
            "\n"
            "Output: All files are written under local_runs/pac/ (gitignored).\n"
            "Canon: personas/, scenarios/, knowledge_base/ are read-only.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate 2-3 ФМДР variants")
    gen.add_argument("--character", required=True, help="Target character_id")
    gen.add_argument("--level", required=True, help="Scene level (e.g. U3-A)")
    gen.add_argument("--situation", required=True, help="Situation description")
    gen.add_argument("--instruction", default="", help="Author instruction")
    gen.add_argument("--provider", required=True, help="mock, local, or cloud")
    gen.add_argument("--model", required=True, help="Model identifier")
    gen.add_argument("--variant-count", type=int, default=2, help="2 or 3 (default 2)")

    # accept-draft
    draft = sub.add_parser("accept-draft", help="Accept a variant as draft")
    draft.add_argument("--run-id", required=True, help="Run ID from generate")
    draft.add_argument("--variant", type=int, required=True, help="Variant index (0-based)")
    draft.add_argument("--output", default=None, help="Approved output text (or read from stdin)")

    # approve-scene
    scene = sub.add_parser("approve-scene", help="Approve scene")
    scene.add_argument("--run-id", required=True, help="Run ID")

    # approve-dataset
    ds = sub.add_parser("approve-dataset", help="Approve for dataset")
    ds.add_argument("--run-id", required=True, help="Run ID")
    ds.add_argument("--provenance", default="human-edited", help="human-written, human-edited, or model-raw-approved")
    ds.add_argument("--session-id", default=None, help="Authoring session UUID")

    # validate
    val = sub.add_parser("validate-fmdr", help="Validate ФМДР text")
    val.add_argument("--text", default=None, help="Text to validate (or read from stdin)")

    # inspect
    insp = sub.add_parser("inspect", help="Inspect a run")
    insp.add_argument("--run-id", required=True, help="Run ID")

    # list-characters
    sub.add_parser("list-characters", help="List available characters")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Build service with real Gateway (needs persona paths).
    # For CLI use we accept an env-style mapping.
    # In practice the user provides paths; for the mock smoke test
    # we don't construct a real catalog.
    service = _build_service_from_env()

    try:
        if args.command == "generate":
            return _cmd_generate(service, args)
        elif args.command == "accept-draft":
            return _cmd_accept_draft(service, args)
        elif args.command == "approve-scene":
            return _cmd_approve_scene(service, args)
        elif args.command == "approve-dataset":
            return _cmd_approve_dataset(service, args)
        elif args.command == "validate-fmdr":
            return _cmd_validate_fmdr(args)
        elif args.command == "inspect":
            return _cmd_inspect(service, args)
        elif args.command == "list-characters":
            return _cmd_list_characters(service)
        else:
            print(f"ERROR: unknown command {args.command}", file=sys.stderr)
            return 1
    except PacError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected error: {exc}", file=sys.stderr)
        return 1


# -------------------------------------------------------------------
# Command handlers
# -------------------------------------------------------------------


def _cmd_generate(service: PacService, args: Any) -> int:
    if args.variant_count not in (2, 3):
        print("ERROR: variant-count must be 2 or 3", file=sys.stderr)
        return 1

    request = PacRequest(
        character_id=args.character,
        level=args.level,
        situation=args.situation,
        author_instruction=args.instruction,
        provider=args.provider,
        model=args.model,
        variant_count=args.variant_count,
    )
    generation = service.generate(request)
    print(json.dumps({
        "run_id": generation.run_id,
        "variant_count": len(generation.variants),
        "variants": [
            {
                "index": v.index,
                "fmdr_valid": v.fmdr_valid,
                "thoughts": v.thoughts,
                "actions": v.actions,
                "speech": v.speech,
                "error": v.fmdr_error,
            }
            for v in generation.variants
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_accept_draft(service: PacService, args: Any) -> int:
    # Get approved output from argument or stdin.
    approved = args.output
    if approved is None:
        approved = sys.stdin.read().strip()
    if not approved:
        print("ERROR: approved output text is required", file=sys.stderr)
        return 1

    event = service.accept_draft(args.run_id, args.variant, approved)
    print(json.dumps({
        "run_id": event.run_id,
        "level": event.level.value,
        "variant_index": event.variant_index,
        "approved_at": event.approved_at,
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_approve_scene(service: PacService, args: Any) -> int:
    event = service.approve_scene(args.run_id)
    print(json.dumps({
        "run_id": event.run_id,
        "level": event.level.value,
        "approved_at": event.approved_at,
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_approve_dataset(service: PacService, args: Any) -> int:
    event = service.approve_dataset(
        args.run_id,
        provenance=args.provenance,
        authoring_session_id=args.session_id,
    )
    print(json.dumps({
        "run_id": event.run_id,
        "level": event.level.value,
        "example_id": event.example_id,
        "approved_at": event.approved_at,
    }, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate_fmdr(args: Any) -> int:
    text = args.text
    if text is None:
        text = sys.stdin.read().strip()
    valid, thoughts, actions, speech, error = validate_fmdr(text)
    result = {
        "valid": valid,
        "thoughts": thoughts,
        "actions": actions,
        "speech": speech,
        "error": error,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


def _cmd_inspect(service: PacService, args: Any) -> int:
    state = service.get_approval_state(args.run_id)
    print(json.dumps({"run_id": args.run_id, "approval_state": state}, ensure_ascii=False, indent=2))
    return 0


def _cmd_list_characters(service: PacService) -> int:
    chars = service.list_characters()
    print(json.dumps(chars, ensure_ascii=False, indent=2))
    return 0


# -------------------------------------------------------------------
# Service factory (for real CLI use; tests inject their own service)
# -------------------------------------------------------------------


def _build_service_from_env() -> PacService:
    """Build a PacService with a real PersonaCatalog from environment paths.

    Reads PERSONA_ROOTS env var as JSON mapping character_id -> root_path.
    Falls back to an empty catalog when the env var is absent (useful for
    tests that inject their own service).
    """
    import os

    roots_json = os.environ.get("PERSONA_ROOTS", "{}")
    try:
        roots: dict[str, str] = json.loads(roots_json)
    except json.JSONDecodeError:
        roots = {}

    entries: dict[str, Path] = {}
    for cid, root_path in roots.items():
        entries[cid] = Path(root_path)

    if entries:
        catalog = PersonaCatalog(entries)
        gateway = GatewayAdapter(catalog)
        return PacService(gateway=gateway)

    # No configured personas -- return service with empty adapter.
    # The real Gateway is not constructable without entries, so for
    # testability we allow a None-gateway service that will fail
    # gracefully on generate.
    return PacService(
        gateway=None,  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    sys.exit(main())