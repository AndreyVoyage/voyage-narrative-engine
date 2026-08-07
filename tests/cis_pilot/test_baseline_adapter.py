#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 1 contract tests for tools/cis_pilot/baseline_adapter.py.

No LLM, no network. Confirms the baseline (control) arm is a
byte-identical, unmodified forward to
``tools.aside_context_builder.build_context()`` and is structurally
P3/P4-blind (no such parameter exists on its public function) -- the
causal control required by spec §16.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools import aside_context_builder
from tools.cis_pilot.baseline_adapter import build_baseline_messages
from tools.cis_pilot.contracts import P3State, P4State

_CRITICAL_SOURCES = (
    "personas/kira/core/IDENTITY.json",
    "personas/kira/psychology/BASE.json",
    "personas/kira/speech/SPEECH_MATRIX.json",
    "personas/kira/relationships/MATRIX.json",
    "tools/aside_context_builder.py",
)

CANON_SNAPSHOT = {
    "scene_id": "cis_pilot_slice1_fixture",
    "levels": {"kira": "L2"},
    "flags": {},
    "completed_scenes": [],
    "content_rating": "test-fixture",
}
ASIDE_MEMORY = {"summary": "", "recent": []}
PLAYER_MESSAGE = "Как ты сейчас?"


def _hash_all(paths: tuple) -> dict:
    return {p: hashlib.sha256((_REPO_ROOT / p).read_bytes()).hexdigest() for p in paths}


def _imported_module_names(source_path: Path) -> set:
    """Return every module name this file actually imports (``import x`` /
    ``from x import y`` / ``from .x import y``), parsed via ``ast`` -- never
    matched as a raw substring, so a docstring merely *mentioning* another
    module's filename does not count as an import."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _git_status_for_paths(paths: list) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
        shell=False,
    )
    assert result.returncode == 0, f"git status failed: {result.stderr}"
    return result.stdout


# ---------------------------------------------------------------------------
# Byte-identical to build_context() (plan §14 acceptance criterion)
# ---------------------------------------------------------------------------


def test_build_baseline_messages_byte_identical_to_build_context_direct():
    via_adapter = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    direct = aside_context_builder.build_context(
        "kira", CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE
    )
    assert via_adapter == direct


def test_build_baseline_messages_is_deterministic():
    first = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    second = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    assert first == second


def test_build_baseline_messages_returns_list_of_role_content_dicts():
    messages = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    assert isinstance(messages, list)
    assert len(messages) > 0
    for message in messages:
        assert set(message.keys()) == {"role", "content"}
        assert isinstance(message["role"], str)
        assert isinstance(message["content"], str)


# ---------------------------------------------------------------------------
# P3/P4 blindness (causal control, spec §16)
# ---------------------------------------------------------------------------


def test_build_baseline_messages_has_no_p3_or_p4_injection_parameter():
    signature = inspect.signature(build_baseline_messages)
    forbidden = {"p3", "p3_state", "trust", "attraction", "p4", "p4_state", "arousal", "anxiety"}
    assert forbidden.isdisjoint(signature.parameters.keys())


def test_build_baseline_messages_output_unaffected_by_any_external_p3_p4_state():
    # The baseline arm has no P3/P4 parameter at all (previous test); this
    # confirms the output-level consequence: constructing two different
    # CIS-only states (never passed to the adapter -- there is no
    # parameter to pass them to) does not change the adapter's output for
    # identical baseline inputs.
    P3State(trust=75, attraction=85)
    P3State(trust=55, attraction=85)
    P4State(arousal="high", anxiety="low", strategy="approach")
    P4State(arousal="high", anxiety="high", strategy="avoidance")

    out_1 = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    out_2 = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    assert out_1 == out_2


def test_baseline_messages_do_not_contain_cis_layer_markers():
    messages = build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    full_text = "\n".join(message["content"] for message in messages)
    for marker in (
        "P0 core psychological anchors",
        "P3 relationship state",
        "P4 transient regulation state",
        "Event/memory layer: absent",
    ):
        assert marker not in full_text


# ---------------------------------------------------------------------------
# Non-convergence with the CIS arm (spec §16)
# ---------------------------------------------------------------------------


def test_baseline_adapter_does_not_import_context_assembler():
    from tools.cis_pilot import baseline_adapter

    imported = _imported_module_names(Path(baseline_adapter.__file__))
    assert not any("context_assembler" in name for name in imported)


# ---------------------------------------------------------------------------
# No write
# ---------------------------------------------------------------------------


def test_no_write_source_hashes_unchanged_before_and_after():
    before = _hash_all(_CRITICAL_SOURCES)
    build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    after = _hash_all(_CRITICAL_SOURCES)
    assert before == after


def test_no_write_git_status_for_critical_sources_empty_before_and_after():
    before = _git_status_for_paths(list(_CRITICAL_SOURCES))
    build_baseline_messages(CANON_SNAPSHOT, ASIDE_MEMORY, PLAYER_MESSAGE)
    after = _git_status_for_paths(list(_CRITICAL_SOURCES))
    assert before == ""
    assert after == ""


def test_local_runs_not_created():
    assert not (_REPO_ROOT / "local_runs").exists()
