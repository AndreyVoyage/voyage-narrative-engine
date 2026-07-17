#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for services/persona_gateway/state_snapshot_service.py.

Most cases use an injected fake ``load_memory_fn`` for isolation and to
exercise edge cases (unsupported types, missing state) without depending
on the real store's own validation. A small number of integration tests
exercise the real ``tools.aside_memory_store`` functions against a
pytest ``tmp_path`` root (never the real repository tree) to prove the
wiring is correct end to end.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import services.persona_gateway.state_snapshot_service as state_snapshot_module
from services.persona_gateway.errors import PersonaGatewayError, SnapshotUnavailableError
from services.persona_gateway.state_snapshot_service import StateSnapshotService
from tools.aside_memory_store import append_session


# ---------------------------------------------------------------------
# Injected-fake based tests
# ---------------------------------------------------------------------

def test_valid_saved_memory_returns_snapshot():
    def fake_load_memory(*, root, slot, character, progress):
        return {
            "summary": "[1 SC_1/b1] talked about the sauna",
            "recent": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
            "sessions_meta": [
                {"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1", "file": "/x/y.json"}
            ],
        }

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    snapshot = service.get_state_snapshot("kira", progress=5)

    assert snapshot.character_id == "kira"
    assert snapshot.summary.startswith("[1 SC_1/b1]")
    assert len(snapshot.recent) == 2
    assert snapshot.recent[0].role == "user"
    assert snapshot.session_count == 1
    assert snapshot.max_progress_index == 1
    assert snapshot.sessions[0].scene_id == "SC_1"
    # The raw file path must not leak into the detached model.
    assert not hasattr(snapshot.sessions[0], "file")


def test_detached_deep_copy_source_mutation_does_not_change_snapshot():
    mutable_source = {
        "summary": "original summary",
        "recent": [{"role": "user", "content": "original"}],
        "sessions_meta": [{"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1"}],
    }

    def fake_load_memory(*, root, slot, character, progress):
        return mutable_source

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    snapshot = service.get_state_snapshot("kira", progress=5)

    # Mutate the source AFTER the snapshot was built.
    mutable_source["summary"] = "mutated"
    mutable_source["recent"][0]["content"] = "mutated"
    mutable_source["sessions_meta"][0]["scene_id"] = "MUTATED"

    assert snapshot.summary == "original summary"
    assert snapshot.recent[0].content == "original"
    assert snapshot.sessions[0].scene_id == "SC_1"


def test_missing_saved_state_raises_snapshot_unavailable():
    def fake_load_memory(*, root, slot, character, progress):
        return {"summary": "", "recent": [], "sessions_meta": []}

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(SnapshotUnavailableError):
        service.get_state_snapshot("kira", progress=0)


def test_unsupported_object_type_rejected():
    class Weird:
        pass

    def fake_load_memory(*, root, slot, character, progress):
        return {"summary": "x", "recent": [], "sessions_meta": [], "extra": Weird()}

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(PersonaGatewayError):
        service.get_state_snapshot("kira", progress=0)


def test_unsupported_object_type_set_rejected():
    def fake_load_memory(*, root, slot, character, progress):
        return {"summary": "x", "recent": [], "sessions_meta": [], "tags": {"a", "b"}}

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(PersonaGatewayError):
        service.get_state_snapshot("kira", progress=0)


def test_non_dict_payload_rejected():
    def fake_load_memory(*, root, slot, character, progress):
        return ["not", "a", "dict"]

    service = StateSnapshotService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(PersonaGatewayError):
        service.get_state_snapshot("kira", progress=0)


def test_no_write_capable_function_referenced_in_module_source():
    # Inspect the AST (not raw text) so the module's own docstring -- which
    # explains, in prose, why summarize_memory is deliberately NOT used --
    # cannot cause a false positive via substring search.
    tree = ast.parse(inspect.getsource(state_snapshot_module))
    forbidden_names = {"append_session", "reset_memory", "summarize_memory"}

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)

    assert imported_names.isdisjoint(forbidden_names)

    called_or_referenced_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            called_or_referenced_names.add(node.id)
        if isinstance(node, ast.Attribute):
            called_or_referenced_names.add(node.attr)

    assert called_or_referenced_names.isdisjoint(forbidden_names)


# ---------------------------------------------------------------------
# Integration tests against the real tools.aside_memory_store, scoped to
# tmp_path (never the real repository).
# ---------------------------------------------------------------------

def test_integration_real_load_memory_returns_snapshot(tmp_path):
    root = tmp_path / "aside_root"
    append_session(
        root=root,
        slot="slot1",
        character="kira",
        session={
            "scene_id": "SC_1",
            "beat_id": "b1",
            "progress_index": 2,
            "summary": "player and kira talked",
            "transcript": [{"role": "user", "content": "hello kira"}],
        },
    )

    service = StateSnapshotService(root, "slot1")
    snapshot = service.get_state_snapshot("kira", progress=10)

    assert snapshot.session_count == 1
    assert snapshot.max_progress_index == 2
    assert snapshot.recent[-1].content == "hello kira"


def test_integration_past_only_filtering_via_real_store(tmp_path):
    root = tmp_path / "aside_root"
    append_session(
        root=root,
        slot="slot1",
        character="kira",
        session={"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "summary": "past", "transcript": []},
    )
    append_session(
        root=root,
        slot="slot1",
        character="kira",
        session={"scene_id": "SC_2", "beat_id": "b2", "progress_index": 99, "summary": "future", "transcript": []},
    )

    service = StateSnapshotService(root, "slot1")
    snapshot = service.get_state_snapshot("kira", progress=1)

    assert snapshot.session_count == 1
    assert snapshot.max_progress_index == 1


def test_integration_missing_saved_state_raises(tmp_path):
    root = tmp_path / "aside_root_empty"
    service = StateSnapshotService(root, "slot1")
    with pytest.raises(SnapshotUnavailableError):
        service.get_state_snapshot("kira", progress=0)


def test_no_files_written_by_get_state_snapshot(tmp_path):
    root = tmp_path / "aside_root"
    append_session(
        root=root,
        slot="slot1",
        character="kira",
        session={"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "summary": "s", "transcript": []},
    )

    def snapshot_tree():
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    before = snapshot_tree()
    service = StateSnapshotService(root, "slot1")
    service.get_state_snapshot("kira", progress=5)
    after = snapshot_tree()

    assert before == after
