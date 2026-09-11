"""Application bootstrap and the single real-project configuration boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtWidgets import QApplication

from services.editor_application import EditorApplicationConfig, EditorApplicationService

from .main_window import EditorMainWindow

PROJECT_ID = "narrative_game"


def create_editor_config(
    repo_root: Path | None = None,
    *,
    character_canon_root: Path | None = None,
) -> EditorApplicationConfig:
    """Build the application facade configuration for one repository checkout.

    The repository root defaults to the checkout containing this package.
    Character Canon stays unavailable until an explicit external root is supplied.
    No widget sees any of these storage paths.
    """

    root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[2]
    )
    return EditorApplicationConfig(
        project_id=PROJECT_ID,
        scene_drafts_root=root / "authoring" / "scene_drafts",
        accepted_ass_root=root / "authoring" / "accepted_ordered_ass",
        manifest_path=root / "authoring" / "project" / "PROJECT_MANIFEST.json",
        batch_path=root / "authoring" / "project" / "ACCEPTED_ORDEREDASS_BATCH.json",
        repo_root=root,
        character_canon_root=(
            Path(character_canon_root).resolve()
            if character_canon_root is not None
            else None
        ),
    )


def create_editor_service(
    repo_root: Path | None = None,
    *,
    character_canon_root: Path | None = None,
) -> EditorApplicationService:
    """Construct the same-process application facade used by the desktop UI."""

    return EditorApplicationService(
        create_editor_config(
            repo_root,
            character_canon_root=character_canon_root,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the read-only editor shell for the current repository project."""

    arguments = list(sys.argv if argv is None else argv)
    app = QApplication(arguments)
    window = EditorMainWindow(create_editor_service())
    window.show()
    return app.exec()
