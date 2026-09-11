"""Automated UI → editor_application import firewall."""

from __future__ import annotations

import ast
from pathlib import Path


def test_ui_imports_only_editor_application_from_services():
    repo_root = Path(__file__).resolve().parents[3]
    violations: list[str] = []
    for path in sorted((repo_root / "ui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                if module == "services" or (
                    module.startswith("services.")
                    and not module.startswith("services.editor_application")
                ):
                    violations.append(f"{path.relative_to(repo_root)}:{node.lineno}: {module}")
    assert violations == []


def test_main_window_contains_no_mutation_facade_calls():
    repo_root = Path(__file__).resolve().parents[3]
    tree = ast.parse(
        (repo_root / "ui" / "editor_desktop" / "main_window.py").read_text(encoding="utf-8")
    )
    forbidden = {"create_scene", "save_draft", "fork_scene_version", "accept_scene"}
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls.isdisjoint(forbidden)
