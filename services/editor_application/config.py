#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor Application Service v1 -- bounded project configuration.

All storage locations are resolved once at construction; UI callers then pass
only stable IDs / versions into service operations and never touch filesystem
paths or base32 storage encoding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class EditorApplicationConfig:
    """Immutable, bounded configuration for one editor project.

    Fields
    ------
    project_id:
        Stable project identity shared by the manifest and accepted batch.
    scene_drafts_root:
        Root of the ``SceneDraftStore``
        (``<root>/<scene_id>/pointer.json`` and ``<root>/<scene_id>/versions/<n>.json``).
    accepted_ass_root:
        Root of the ``OrderedASSStore``
        (base32-encoded ``scenes/<token>/versions/<n>.json``). Must be absolute.
    manifest_path:
        Absolute path of the ``ProjectManifest`` JSON file.
    batch_path:
        Absolute path of the ``AcceptedOrderedASSBatch`` JSON file.
    repo_root:
        Repository root, used only to resolve Location Canon
        (``scenarios/locations/*.json``).
    character_canon_root:
        Optional Character Canon root (external NCC repository). When ``None``,
        character discovery is unavailable and ``list_characters`` returns empty.
    scene_drafts_source_ref:
        Repository-relative prefix used to generate provenance ``source_ref``
        strings and manifest SCENE ``source_ref`` locators (must match the
        repo-relative location of ``scene_drafts_root``).
    """

    project_id: str
    scene_drafts_root: Path
    accepted_ass_root: Path
    manifest_path: Path
    batch_path: Path
    repo_root: Path
    character_canon_root: Optional[Path] = None
    scene_drafts_source_ref: str = "authoring/scene_drafts"

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", str(self.project_id))
        object.__setattr__(self, "scene_drafts_root", Path(self.scene_drafts_root))
        object.__setattr__(self, "accepted_ass_root", Path(self.accepted_ass_root))
        object.__setattr__(self, "manifest_path", Path(self.manifest_path))
        object.__setattr__(self, "batch_path", Path(self.batch_path))
        object.__setattr__(self, "repo_root", Path(self.repo_root))
        if self.character_canon_root is not None:
            object.__setattr__(self, "character_canon_root", Path(self.character_canon_root))
        source_ref = self.scene_drafts_source_ref
        if (
            not isinstance(source_ref, str)
            or not source_ref
            or source_ref.startswith(("/", "\\"))
            or "\\" in source_ref
        ):
            raise ValueError(
                "scene_drafts_source_ref must be a non-empty repo-relative forward-slash path"
            )
        object.__setattr__(self, "scene_drafts_source_ref", source_ref.rstrip("/"))
