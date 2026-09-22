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
from typing import Optional


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
    """

    character_canon_root: Optional[Path] = None
    character_authoring_root: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.character_canon_root is not None:
            object.__setattr__(self, "character_canon_root", Path(self.character_canon_root))
        if self.character_authoring_root is not None:
            object.__setattr__(
                self,
                "character_authoring_root",
                Path(self.character_authoring_root),
            )
