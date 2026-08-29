#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNE Reference Library -- controlled import CLI (SVA-RL2).

A thin wrapper over ``services.reference_library.import_reference``. It contains
no import logic of its own. Only the ``import`` command exists: no directory
scan, no update, and no remove.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``services`` importable when this script is run directly from tools/.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
from typing import Optional, Sequence

from services.reference_library import (
    ReferenceLibraryError,
    default_manifest_path,
    import_reference,
)


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="VNE Reference Library controlled import (SVA-RL2)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="Import one explicit source image")
    p_import.add_argument("--source", required=True, help="Path to the source image")
    p_import.add_argument("--asset-id", required=True, dest="asset_id")
    p_import.add_argument("--character-id", required=True, dest="character_id")
    p_import.add_argument("--collection", default=None)
    p_import.add_argument("--source-filename", default=None, dest="source_filename")
    p_import.add_argument("--notes", default=None)
    p_import.set_defaults(func="import")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    repo_root: Optional[Path] = None,
    manifest_path: Optional[Path] = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(repo_root) if repo_root is not None else _default_repo_root()
    manifest = (
        Path(manifest_path)
        if manifest_path is not None
        else default_manifest_path(root)
    )

    try:
        result = import_reference(
            args.source,
            repo_root=root,
            manifest_path=manifest,
            asset_id=args.asset_id,
            character_id=args.character_id,
            collection=args.collection,
            source_filename=args.source_filename,
            notes=args.notes,
        )
    except ReferenceLibraryError as exc:
        print(f"REJECT: {exc}", file=sys.stderr)
        return 1

    print(f"{result.status}: {result.record.asset_id} -> {result.record.relative_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
