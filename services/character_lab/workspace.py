#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab V1 workspace model (separate data roots, no DB column).

Two kinds:

- ``NORMAL``      -- one stable, long-lived personal KIRA history. Explicit
                     operator switch required; never the fresh-launch default.
- ``CLEAN_TEST``  -- an isolated workspace with its own memory DB, turn
                     artifacts and scenes. The default on launch.

Isolation is purely by directory:

    <data_root>/workspaces/
        normal/
            runtime_memory.sqlite3
            turns/<turn_id>/...
            scenes/<session_id>.json
        tests/<workspace_id>/
            runtime_memory.sqlite3
            turns/<turn_id>/...
            scenes/<session_id>.json

The manager resolves every path itself from a validated id. It never joins an
arbitrary caller-supplied path fragment, so a frontend can only ever send an id.
"""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List

NORMAL_ID = "normal"
CLEAN_TEST_PREFIX = "test-"
WORKSPACE_KIND_NORMAL = "NORMAL"
WORKSPACE_KIND_CLEAN_TEST = "CLEAN_TEST"

_CLEAN_TEST_ID_RE = re.compile(r"^test-[0-9a-f]{12,32}$")


class WorkspaceError(ValueError):
    """Fail-closed workspace-resolution error (invalid or unsafe id)."""


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    workspace_kind: str
    display_name: str
    root: Path

    @property
    def memory_root(self) -> Path:
        return self.root

    @property
    def turn_capture_root(self) -> Path:
        return self.root

    @property
    def scenes_dir(self) -> Path:
        return self.root / "scenes"


class WorkspaceManager:
    """Creates / lists / resolves workspace directories under one data root."""

    def __init__(self, data_root: Path) -> None:
        self._workspaces_root = Path(data_root) / "workspaces"

    # ------------------------------------------------------------- resolution
    def _normal_dir(self) -> Path:
        return self._workspaces_root / "normal"

    def _tests_dir(self) -> Path:
        return self._workspaces_root / "tests"

    def _validate_id(self, workspace_id: str) -> str:
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise WorkspaceError("workspace_id must be a non-empty string")
        workspace_id = workspace_id.strip()
        if workspace_id == NORMAL_ID:
            return workspace_id
        if _CLEAN_TEST_ID_RE.match(workspace_id):
            return workspace_id
        raise WorkspaceError(f"invalid workspace_id {workspace_id!r}")

    def normal(self) -> Workspace:
        root = self._normal_dir()
        root.mkdir(parents=True, exist_ok=True)
        return Workspace(
            workspace_id=NORMAL_ID,
            workspace_kind=WORKSPACE_KIND_NORMAL,
            display_name="Normal / long-lived",
            root=root,
        )

    def new_clean_test(self) -> Workspace:
        workspace_id = f"{CLEAN_TEST_PREFIX}{uuid.uuid4().hex[:16]}"
        root = self._tests_dir() / workspace_id
        root.mkdir(parents=True, exist_ok=True)
        return Workspace(
            workspace_id=workspace_id,
            workspace_kind=WORKSPACE_KIND_CLEAN_TEST,
            display_name=f"Clean Test {workspace_id[len(CLEAN_TEST_PREFIX):][:8]}",
            root=root,
        )

    def get(self, workspace_id: str) -> Workspace:
        workspace_id = self._validate_id(workspace_id)
        if workspace_id == NORMAL_ID:
            return self.normal()
        root = self._tests_dir() / workspace_id
        if not root.exists():
            raise WorkspaceError(f"unknown workspace {workspace_id!r}")
        return Workspace(
            workspace_id=workspace_id,
            workspace_kind=WORKSPACE_KIND_CLEAN_TEST,
            display_name=f"Clean Test {workspace_id[len(CLEAN_TEST_PREFIX):][:8]}",
            root=root,
        )

    def list(self) -> List[Workspace]:
        result = [self.normal()]
        tests_dir = self._tests_dir()
        if tests_dir.exists():
            for child in sorted(tests_dir.iterdir()):
                if child.is_dir() and _CLEAN_TEST_ID_RE.match(child.name):
                    result.append(self.get(child.name))
        return result

    def reset_clean_test(self, workspace_id: str) -> Workspace:
        """Delete and recreate one CLEAN_TEST workspace directory.

        Refuses NORMAL and any id that is not a well-formed clean-test id, so a
        traversal / arbitrary-path delete is impossible.
        """
        workspace_id = self._validate_id(workspace_id)
        if workspace_id == NORMAL_ID:
            raise WorkspaceError("the NORMAL workspace cannot be reset or deleted")
        root = self._tests_dir() / workspace_id
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        return self.get(workspace_id)
