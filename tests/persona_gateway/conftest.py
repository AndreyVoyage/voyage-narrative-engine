#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared fixtures for the N7 Persona Data Gateway (P1a-S1 partial runtime)
test suite.

All persona/manifest/module fixtures are synthetic and built inside
pytest's ``tmp_path`` -- no Kira canon is copied into tracked fixtures,
and nothing under this test suite ever writes to the real repository
(``personas/kira``, ``tools/``, etc.).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def write_json_file() -> Callable[[Path, Any], None]:
    def _write(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return _write


@pytest.fixture
def write_bytes_file() -> Callable[[Path, bytes], None]:
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    return _write


@pytest.fixture
def write_text_file() -> Callable[[Path, str], None]:
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return _write


DEFAULT_MODULES: Dict[str, Dict[str, Any]] = {
    "core/IDENTITY.json": {"version": "1.0.0", "required": True},
    "psychology/BASE.json": {"version": "1.2.0", "required": True},
    "levels/U2-A.json": {"version": "1.0.0"},
}

DEFAULT_MODULE_CONTENT: Dict[str, Dict[str, Any]] = {
    "core/IDENTITY.json": {"id": "kira_identity", "name": "Кира", "anatomic_anchor": {}},
    "psychology/BASE.json": {"module_id": "psych_base", "core_conflict": "placeholder"},
    "levels/U2-A.json": {"level_id": "U2-A", "vscno": {}},
}


@pytest.fixture
def build_persona_root(tmp_path: Path, write_json_file):
    """Factory fixture: builds a small, synthetic Kira-like persona root
    under ``tmp_path``. Returns the root ``Path``.

    Mirrors the real ``personas/kira/INDEX.json`` shape (module ids ARE
    the manifest keys, no separate ``path`` field) without copying any
    real Kira canon content.
    """

    def _build(
        *,
        character_id: str = "kira",
        character_name: str = "Кира",
        modules: Optional[Dict[str, Dict[str, Any]]] = None,
        module_content: Optional[Dict[str, Dict[str, Any]]] = None,
        unlisted_files: Optional[Dict[str, Dict[str, Any]]] = None,
        manifest_overrides: Optional[Dict[str, Any]] = None,
        root_name: str = "persona_root",
    ) -> Path:
        root = tmp_path / root_name
        effective_modules = DEFAULT_MODULES.copy() if modules is None else modules
        effective_content = (
            DEFAULT_MODULE_CONTENT.copy() if module_content is None else module_content
        )

        manifest: Dict[str, Any] = {
            "id": character_id,
            "name": character_name,
            "version": "2.2.0",
            "schema_version": "1.0.0",
            "default_level": "U2-A",
            "default_ag_level": 1,
            "compatible_scenarios": ["sauna_extended"],
            "modules": effective_modules,
        }
        if manifest_overrides:
            manifest.update(manifest_overrides)

        write_json_file(root / "INDEX.json", manifest)

        for rel_path, content in effective_content.items():
            write_json_file(root / rel_path, content)

        for rel_path, content in (unlisted_files or {}).items():
            write_json_file(root / rel_path, content)

        return root

    return _build


@pytest.fixture
def patch_is_symlink(monkeypatch):
    """Return a helper that makes ``Path.is_symlink()`` report ``True`` for
    one specific path, regardless of whether the current OS/user privilege
    level actually permits creating a real symlink (Windows commonly
    requires elevation). Falls back path for symlink invariants that
    cannot be exercised with a genuine filesystem symlink in CI/dev
    environments.
    """

    def _patch(target: Path) -> None:
        target_resolved_str = str(target)
        original_is_symlink = Path.is_symlink

        def fake_is_symlink(self: Path) -> bool:
            if str(self) == target_resolved_str:
                return True
            return original_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    return _patch


def _try_create_symlink(link_path: Path, target_path: Path, *, target_is_directory: bool) -> bool:
    """Attempt to create a real filesystem symlink. Returns True on success,
    False if the OS/privilege level refuses (common on Windows without
    Developer Mode or elevation) -- callers must fall back to
    ``patch_is_symlink`` in that case rather than silently skipping the
    invariant."""
    try:
        link_path.symlink_to(target_path, target_is_directory=target_is_directory)
        return True
    except (OSError, NotImplementedError):
        return False


@pytest.fixture
def attempt_symlink() -> Callable[..., bool]:
    """Fixture wrapper around ``_try_create_symlink`` so test files never
    need a cross-file ``import conftest`` (this test directory has no
    ``__init__.py``, so plain module import would be fragile)."""
    return _try_create_symlink
