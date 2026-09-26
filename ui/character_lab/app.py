"""Application bootstrap and the single configuration boundary."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtWidgets import QApplication

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
    resolve_character_lab_roots,
)

from .main_window import CharacterLabMainWindow

_CANON_ROOT_ENV_VAR = "NARRATIVE_CHARACTER_CANON_ROOT"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def create_character_lab_config(
    *,
    character_canon_root: Path | None = None,
    character_authoring_root: Path | None = None,
    character_release_store_root: Path | None = None,
) -> CharacterLabApplicationConfig:
    """Build the application facade configuration for one Character Lab run.

    ``character_canon_root`` defaults to the ``NARRATIVE_CHARACTER_CANON_ROOT``
    environment variable (the same external Character Canon root convention
    used by the repository's real-canon e2e tests) when not supplied
    explicitly, and stays unavailable (``None``) when neither is set. No
    widget ever sees this path.

    Character Authoring and Character Release Store roots default to the
    repository-local developer-desktop locations
    (``<repo>/local_runs/character_authoring`` and
    ``<repo>/local_runs/character_releases``) and are overridden by any
    explicitly supplied value.
    """

    root = character_canon_root
    if root is None:
        env_value = os.environ.get(_CANON_ROOT_ENV_VAR)
        root = Path(env_value) if env_value else None
    authoring_root, release_root = resolve_character_lab_roots(
        _REPO_ROOT,
        character_authoring_root=character_authoring_root,
        character_release_store_root=character_release_store_root,
    )
    return CharacterLabApplicationConfig(
        character_canon_root=Path(root).resolve() if root is not None else None,
        character_authoring_root=authoring_root,
        character_release_store_root=release_root,
    )


def create_character_lab_service(
    *,
    character_canon_root: Path | None = None,
    character_authoring_root: Path | None = None,
    character_release_store_root: Path | None = None,
) -> CharacterLabApplicationService:
    """Construct the same-process application facade used by the desktop UI."""

    return CharacterLabApplicationService(
        create_character_lab_config(
            character_canon_root=character_canon_root,
            character_authoring_root=character_authoring_root,
            character_release_store_root=character_release_store_root,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the offline Character Lab shell."""

    arguments = list(sys.argv if argv is None else argv)
    app = QApplication(arguments)
    window = CharacterLabMainWindow(create_character_lab_service())
    window.show()
    return app.exec()
