#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Lab Application Service v1 -- bounded configuration.

Mirrors ``services.editor_application.config``: storage locations are
resolved once at construction; UI callers pass only stable IDs into service
operations and never touch filesystem paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from services.character_authoring import default_store_root


@dataclass(frozen=True)
class CharacterLabApplicationConfig:
    """Immutable, bounded configuration for one Character Lab instance.

    Fields
    ------
    character_canon_root:
        Optional Character Canon root (external NCC repository). When
        ``None``, character discovery is unavailable and ``list_characters``
        returns empty -- the same graceful-degradation contract as
        ``services.editor_application``.
    character_authoring_root:
        Optional local Character Authoring S1 store root. Mutation use-cases
        fail with a structured application error when it is not configured.
    character_release_store_root:
        Optional local LAB-L4 Character Release Store root. Release mutation
        use-cases (publish/designate/export) fail with a structured
        application error when it is not configured; release read use-cases
        degrade to empty.
    """

    character_canon_root: Optional[Path] = None
    character_authoring_root: Optional[Path] = None
    character_release_store_root: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.character_canon_root is not None:
            object.__setattr__(self, "character_canon_root", Path(self.character_canon_root))
        if self.character_authoring_root is not None:
            object.__setattr__(
                self,
                "character_authoring_root",
                Path(self.character_authoring_root),
            )
        if self.character_release_store_root is not None:
            object.__setattr__(
                self,
                "character_release_store_root",
                Path(self.character_release_store_root),
            )


def resolve_character_lab_roots(
    repo_root: Path | str,
    *,
    character_authoring_root: Path | str | None = None,
    character_release_store_root: Path | str | None = None,
) -> Tuple[Path, Path]:
    """Resolve the desktop application's authoring and release store roots.

    Character Authoring defaults to the authoritative
    ``default_store_root(repo_root)`` (``<repo>/local_runs/character_authoring``);
    the Character Release Store defaults to the authoring root's sibling
    ``character_releases`` directory (``<repo>/local_runs/character_releases``).
    Explicitly supplied values take precedence over the defaults.
    """

    authoring = (
        Path(character_authoring_root)
        if character_authoring_root is not None
        else default_store_root(repo_root)
    )
    release = (
        Path(character_release_store_root)
        if character_release_store_root is not None
        else authoring.parent / "character_releases"
    )
    return authoring, release
