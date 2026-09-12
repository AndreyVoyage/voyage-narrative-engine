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


def test_ui_mutation_calls_are_limited_to_approved_facade_methods():
    """M3-S1 firewall: validation is read-only; mutations remain bounded.

    The UI MAY call approved mutation methods on the editor_application
    facade; it MUST NOT call not-yet-approved mutations from any UI module.
    """
    repo_root = Path(__file__).resolve().parents[3]
    forbidden = {"create_scene", "accept_scene"}
    approved_mutations = {"save_draft", "fork_scene_version"}
    approved_read_actions = {"validate_scene"}
    violations: list[str] = []
    approved_calls: list[str] = []
    for path in sorted((repo_root / "ui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name in forbidden:
                    violations.append(f"{path.relative_to(repo_root)}:{node.lineno}: {name}")
                elif name in approved_mutations | approved_read_actions:
                    approved_calls.append(f"{path.relative_to(repo_root)}:{node.lineno}: {name}")
    assert violations == []
    called_methods = {call.rsplit(": ", 1)[-1] for call in approved_calls}
    assert called_methods == approved_mutations | approved_read_actions
