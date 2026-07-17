#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for services/persona_gateway/history_query_service.py.

Most cases use an injected fake ``load_memory_fn`` for isolation and
determinism. A small number of integration tests exercise the real
``tools.aside_memory_store`` functions against a pytest ``tmp_path`` root
(never the real repository).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import services.persona_gateway.history_query_service as history_module
from services.persona_gateway.errors import HistoryNotFoundError, HistoryRecordError
from services.persona_gateway.history_query_service import HistoryQueryService
from tools.aside_memory_store import append_session


def _fake_payload(*, summary_lines, recent, sessions_meta):
    return {
        "summary": "\n".join(summary_lines),
        "recent": recent,
        "sessions_meta": sessions_meta,
    }


def test_literal_matching():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=["[1 SC_1/b1] the sauna was very hot today"],
            recent=[{"role": "user", "content": "let's go to the sauna"}],
            sessions_meta=[{"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1"}],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    result = service.search_history("kira", query="sauna", limit=10, progress=5)

    assert result.query == "sauna"
    assert len(result.records) == 2
    assert result.records[0].match_type == "literal"
    assert result.records[0].scene_id == "SC_1"
    assert result.records[0].session_id == "s1"
    assert result.records[1].match_type == "literal"
    assert result.records[1].scene_id is None  # transcript-sourced match, no attribution


def test_normalized_token_matching():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=["[1 SC_1/b1] They discussed saunas, and the quartet."],
            recent=[],
            sessions_meta=[{"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1"}],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    # "sauna" is a substring token-match of "saunas" via normalized tokens,
    # but not a literal substring match of "saunas," (with trailing comma
    # in the raw text) when queried as "sauna quartet" (multi-token).
    result = service.search_history("kira", query="quartet sauna", limit=10, progress=5)

    assert len(result.records) == 1
    assert result.records[0].match_type == "token"


def test_deterministic_original_past_only_order():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=[
                "[1 SC_1/b1] alpha beta",
                "[2 SC_2/b2] alpha gamma",
                "[3 SC_3/b3] alpha delta",
            ],
            recent=[],
            sessions_meta=[
                {"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1"},
                {"scene_id": "SC_2", "beat_id": "b2", "progress_index": 2, "session_id": "s2"},
                {"scene_id": "SC_3", "beat_id": "b3", "progress_index": 3, "session_id": "s3"},
            ],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    result = service.search_history("kira", query="alpha", limit=10, progress=5)

    progress_indices = [r.progress_index for r in result.records]
    assert progress_indices == [1, 2, 3]


def test_limit_enforcement_never_exceeded():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=[f"[{i} SC_{i}/b{i}] alpha match {i}" for i in range(1, 11)],
            recent=[],
            sessions_meta=[
                {"scene_id": f"SC_{i}", "beat_id": f"b{i}", "progress_index": i, "session_id": f"s{i}"}
                for i in range(1, 11)
            ],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    result = service.search_history("kira", query="alpha", limit=3, progress=20)

    assert len(result.records) == 3
    assert result.limit == 3


def test_invalid_limit_raises_value_error():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(summary_lines=[], recent=[], sessions_meta=[])

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(ValueError):
        service.search_history("kira", query="x", limit=0, progress=5)
    with pytest.raises(ValueError):
        service.search_history("kira", query="x", limit=-1, progress=5)


def test_missing_memory_raises_history_not_found():
    def fake_load_memory(*, root, slot, character, progress):
        return {"summary": "", "recent": [], "sessions_meta": []}

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(HistoryNotFoundError):
        service.search_history("kira", query="anything", limit=5, progress=0)


def test_zero_matches_returns_empty_list_not_error():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=["[1 SC_1/b1] nothing relevant here"],
            recent=[],
            sessions_meta=[{"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1, "session_id": "s1"}],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    result = service.search_history("kira", query="nonexistent_keyword_xyz", limit=5, progress=5)
    assert result.records == ()


def test_malformed_session_metadata_raises_history_record_error():
    def fake_load_memory(*, root, slot, character, progress):
        return {
            "summary": "x",
            "recent": [],
            "sessions_meta": [{"scene_id": "SC_1"}],  # missing beat_id/progress_index
        }

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(HistoryRecordError):
        service.search_history("kira", query="x", limit=5, progress=5)


def test_malformed_transcript_entry_raises_history_record_error():
    def fake_load_memory(*, root, slot, character, progress):
        return _fake_payload(
            summary_lines=[],
            recent=[{"role": "user"}],  # missing content
            sessions_meta=[],
        )

    service = HistoryQueryService(Path("unused"), "slot1", load_memory_fn=fake_load_memory)
    with pytest.raises(HistoryRecordError):
        service.search_history("kira", query="x", limit=5, progress=5)


def test_no_write_capable_function_referenced_in_module_source():
    tree = ast.parse(inspect.getsource(history_module))
    forbidden_names = {"append_session", "reset_memory", "summarize_memory"}

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)
    assert imported_names.isdisjoint(forbidden_names)

    referenced_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            referenced_names.add(node.id)
        if isinstance(node, ast.Attribute):
            referenced_names.add(node.attr)
    assert referenced_names.isdisjoint(forbidden_names)


# ---------------------------------------------------------------------
# Integration tests against the real tools.aside_memory_store, scoped to
# tmp_path (never the real repository).
# ---------------------------------------------------------------------

def test_integration_real_store_literal_search(tmp_path):
    root = tmp_path / "aside_root"
    append_session(
        root=root,
        slot="slot1",
        character="kira",
        session={
            "scene_id": "SC_1",
            "beat_id": "b1",
            "progress_index": 1,
            "summary": "we talked about the sauna quartet plan",
            "transcript": [{"role": "user", "content": "let's do the sauna quartet"}],
        },
    )

    service = HistoryQueryService(root, "slot1")
    result = service.search_history("kira", query="sauna quartet", limit=5, progress=10)
    assert len(result.records) >= 1
    assert any(r.match_type in ("literal", "token") for r in result.records)


def test_integration_no_write_operation_performed(tmp_path):
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
    service = HistoryQueryService(root, "slot1")
    service.search_history("kira", query="s", limit=5, progress=5)
    after = snapshot_tree()

    assert before == after
