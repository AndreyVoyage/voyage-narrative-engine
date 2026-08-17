#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S0 -- architecture boundary tests.

Static (AST-based) verification that ``services/crp_authoring/`` never imports
or directly accesses canon, PAC, Sandbox, provider, or legacy-KB code at S0.

Mirrors ``tests/persona_authoring/test_architecture_boundary.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PROD_ROOT = Path("services/crp_authoring")


def _list_prod_files() -> list[Path]:
    return sorted(_PROD_ROOT.rglob("*.py"))


def _modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def _string_constants(tree: ast.AST) -> list[str]:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


class TestArchitectureBoundary:
    def test_no_canon_imports(self) -> None:
        violations = []
        for py_file in _list_prod_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for m in _modules(tree):
                if m.startswith("personas.") or m.startswith("scenarios.") or m.startswith("core.") \
                        or m.startswith("knowledge_base.") or m.startswith("state.") \
                        or m.startswith("schemas."):
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"Canon imports: {violations}"

    def test_no_pac_or_sandbox_imports(self) -> None:
        violations = []
        for py_file in _list_prod_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for m in _modules(tree):
                lower = m.lower()
                if "persona_authoring" in lower or "persona_gateway" in lower \
                        or "sandbox" in lower or "character_evolution" in lower:
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"PAC/Sandbox imports: {violations}"

    def test_no_provider_or_network_imports(self) -> None:
        forbidden = (
            "tools.llm_provider", "openai", "anthropic", "requests", "httpx",
            "urllib", "socket", "http.client", "aiohttp",
        )
        violations = []
        for py_file in _list_prod_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for m in _modules(tree):
                if any(m.startswith(f) for f in forbidden):
                    violations.append(f"{py_file}: imports {m}")
        assert not violations, f"Provider/network imports: {violations}"

    def test_no_canon_path_strings(self) -> None:
        violations = []
        for py_file in _list_prod_files():
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for s in _string_constants(tree):
                stripped = s.strip()
                if stripped.startswith("personas/") or stripped.startswith("scenarios/") \
                        or stripped.startswith("core/") or stripped.startswith("knowledge_base/"):
                    violations.append(f"{py_file}: path string {s!r}")
        assert not violations, f"Canon path strings: {violations}"

    def test_no_knowledge_base_auto_inherit(self) -> None:
        # S0 must not reference legacy KB auto-inheritance.
        violations = []
        for py_file in _list_prod_files():
            text = py_file.read_text(encoding="utf-8")
            if "knowledge_base" in text:
                violations.append(str(py_file))
        assert not violations, f"Legacy KB reference in S0: {violations}"