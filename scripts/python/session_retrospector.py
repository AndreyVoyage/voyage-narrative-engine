#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Retrospector v0.1 CLI foundation.

This module intentionally provides only a stable command-line surface for the
retrospective gate. Full session retrospective analytics are not implemented yet.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Session Retrospector v0.1 CLI foundation."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Session Retrospector v{VERSION}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the CLI without writing any files.",
    )
    parser.add_argument(
        "--output",
        help="Optional report output path. No report is written unless provided.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output report format when --output is provided.",
    )
    return parser


def render_report(output_format: str) -> str:
    if output_format == "json":
        payload = {
            "tool": "session_retrospector",
            "version": VERSION,
            "status": "cli_foundation_ready",
            "analytics_implemented": False,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    return (
        "# Session Retrospector v0.1\n\n"
        "Status: CLI foundation ready.\n\n"
        "This report is a placeholder for future session retrospective analytics.\n"
    )


def print_status(dry_run: bool) -> None:
    print("Session Retrospector v0.1")
    print("Status: CLI foundation ready")
    if dry_run:
        print("Dry run: no files written")
    else:
        print("No retrospective report generated because --output was not provided")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_report(args.format), encoding="utf-8")
        print(f"Session Retrospector v0.1 report written: {output_path}")
        return 0

    print_status(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
