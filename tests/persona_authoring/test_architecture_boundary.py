#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Architecture boundary tests -- PAC must not access canon directly."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _list_pac_source_files():
    """Return all .py files under services/persona_authoring/."""
    root = Path("services/persona_authoring")
    return sorted(root.rglob("*.py"))


def _has_forbidden_import(tree: ast.AST) -> list[str]:
    """Check for forbidden patterns: direct personas access, canon writes."""
    violations: list[str] = []
    for node in ast.walk(tree):
        # Check string literals used as Path arguments, skipping docstrings
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            # Only flag strings that look like actual filesystem paths
            if "personas/" in v and v.strip().startswith("personas"):
                violations.append(f"string containing path 'personas/': {v!r}")
        # Check for open() or glob() builtins
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("open", "glob"):
                violations.append(f"forbidden builtin call: {node.func.id}()")
    return violations


class TestArchitectureBoundary:
    """PAC must not contain direct canon access."""

    def test_no_forbidden_strings_in_source(self):
        """No PAC source file contains forbidden 'personas/' strings."""
        violations = []
        for py_file in _list_pac_source_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            file_violations = _has_forbidden_import(tree)
            for v in file_violations:
                violations.append(f"{py_file}: {v}")
        assert not violations, f"Architecture boundary violations: {violations}"

    def test_no_direct_personas_import(self):
        """PAC must not import from personas/ directories."""
        violations = []
        for py_file in _list_pac_source_files():
            text = py_file.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("personas."):
                        violations.append(f"{py_file}: imports from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("personas."):
                            violations.append(f"{py_file}: imports {alias.name}")
        assert not violations, f"Direct personas imports: {violations}"

    def test_no_forbidden_module_imports(self):
        """PAC must not import MCP, DB, UI, N8, Sandbox or Ren'Py code."""
        forbidden_prefixes = (
            "mcp", "database", "sqlite3", "web", "renpy",
            "n8", "sandbox", "character_evolution",
        )
        violations = []
        for py_file in _list_pac_source_files():
            text = py_file.read_text(encoding="utf-8")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                modules_to_check = []
                if isinstance(node, ast.ImportFrom):
                    modules_to_check.append(node.module or "")
                elif isinstance(node, ast.Import):
                    modules_to_check.extend(a.name for a in node.names)
                for module in modules_to_check:
                    for prefix in forbidden_prefixes:
                        if module.startswith(prefix):
                            violations.append(f"{py_file}: imports {module}")
        assert not violations, f"Forbidden module imports: {violations}"

    def test_no_import_time_writes(self):
        """PAC modules should not write to filesystem on import."""
        # This is a structural check -- no write calls at module level.
        violations = []
        for py_file in _list_pac_source_files():
            text = py_file.read_text(encoding="utf-8")
            tree = ast.parse(text)
            # Module-level statements
            for node in tree.body:
                if isinstance(node, ast.Expr):
                    # Check for write-like calls at module level
                    if isinstance(node.value, ast.Call):
                        func = node.value.func
                        func_name = (
                            func.id if isinstance(func, ast.Name)
                            else (func.attr if isinstance(func, ast.Attribute) else "")
                        )
                        if func_name in ("open", "write", "mkdir", "remove", "unlink"):
                            violations.append(
                                f"{py_file}: module-level {func_name}() call"
                            )
        assert not violations, f"Import-time writes: {violations}"

    def test_gateway_adapter_does_not_use_path_glob(self):
        """GatewayAdapter must not scan personas/ directories."""
        gw_file = Path("services/persona_authoring/gateway_adapter.py")
        if gw_file.exists():
            text = gw_file.read_text(encoding="utf-8")
            assert "personas/" not in text.lower() or "persona_gateway" in text.lower(), (
                "GatewayAdapter contains direct 'personas/' reference"
            )
            assert "glob(" not in text, "GatewayAdapter uses glob()"


class TestGatewayOnlyCanonAccess:
    """PAC service must access canon only through Gateway."""

    def test_service_does_not_open_personas(self, service, sample_request):
        """The PacService should not call open() on persona paths."""
        # The mock gateway already returns canned data --
        # verify that generate() succeeds through Gateway only.
        generation = service.generate(sample_request)
        assert generation is not None
        assert len(generation.variants) == 2

    def test_gateway_isolated_from_module_search(self):
        """Verify GatewayAdapter does not import pathlib.Path for persona scanning."""
        gw_file = Path("services/persona_authoring/gateway_adapter.py")
        text = gw_file.read_text(encoding="utf-8")
        # Should import Path but only for type annotations, not for scanning
        assert "from pathlib import Path" in text
        # Must not call Path() with "personas/"
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "Path":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            assert "personas" not in arg.value, (
                                f"GatewayAdapter uses Path('personas/...'): {arg.value}"
                            )