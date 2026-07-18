#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-character isolation tests for the N7 Persona Data Gateway (P1b
Option A).

Two halves:

1. Static repository isolation via ``PersonaCatalog`` -- proves one
   character's catalog entry can never read another's allowlisted
   modules, that lookup is exact/case-sensitive, and that a caller
   cannot substitute a new root into an already-constructed catalog.
   Uses synthetic personas built under pytest's ``tmp_path`` via
   ``build_persona_root`` -- no real persona canon is read here (real
   canon is covered by ``test_multi_character_compatibility.py``).

2. Runtime memory isolation via the existing, UNMODIFIED
   ``StateSnapshotService``/``HistoryQueryService``, proving two
   characters sharing one ``root``/``slot`` never cross-read each
   other's saved aside/session memory. Per this task's constraints,
   this file never imports ``summarize_memory``, ``append_session``, or
   ``reset_memory`` -- session fixture files are written directly as
   plain JSON, bypassing the write-capable store API entirely (no
   memory write API is invoked anywhere in this file).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.persona_gateway.errors import (
    CharacterNotFoundError,
    ManifestIntegrityError,
    PersonaModuleNotFoundError,
    SnapshotUnavailableError,
)
from services.persona_gateway.history_query_service import HistoryQueryService
from services.persona_gateway.persona_catalog import PersonaCatalog
from services.persona_gateway.state_snapshot_service import StateSnapshotService


# ---------------------------------------------------------------------
# Static repository isolation (PersonaCatalog / PersonaRepository)
# ---------------------------------------------------------------------

def _build_two_character_catalog(build_persona_root):
    root_kira = build_persona_root(
        character_id="kira",
        character_name="Кира",
        root_name="kira_root",
        modules={
            "core/IDENTITY.json": {"version": "1.0.0"},
            "secret/ONLY_KIRA.json": {"version": "1.0.0"},
        },
        module_content={
            "core/IDENTITY.json": {"owner": "kira"},
            "secret/ONLY_KIRA.json": {"secret": "kira-only"},
        },
    )
    root_marina = build_persona_root(
        character_id="marina",
        character_name="Марина",
        root_name="marina_root",
        modules={
            "core/IDENTITY.json": {"version": "1.0.0"},
            "secret/ONLY_MARINA.json": {"version": "1.0.0"},
        },
        module_content={
            "core/IDENTITY.json": {"owner": "marina"},
            "secret/ONLY_MARINA.json": {"secret": "marina-only"},
        },
    )
    catalog = PersonaCatalog({"kira": root_kira, "marina": root_marina})
    return catalog, root_kira, root_marina


def test_character_a_cannot_read_module_only_allowlisted_by_b(build_persona_root):
    catalog, _, _ = _build_two_character_catalog(build_persona_root)
    with pytest.raises(PersonaModuleNotFoundError):
        catalog.read_module("kira", "secret/ONLY_MARINA.json")
    with pytest.raises(PersonaModuleNotFoundError):
        catalog.read_module("marina", "secret/ONLY_KIRA.json")


def test_identical_module_id_resolves_under_each_characters_own_root(build_persona_root):
    catalog, _, _ = _build_two_character_catalog(build_persona_root)
    kira_result = catalog.read_module("kira", "core/IDENTITY.json")
    marina_result = catalog.read_module("marina", "core/IDENTITY.json")

    assert kira_result.data == {"owner": "kira"}
    assert marina_result.data == {"owner": "marina"}
    assert kira_result.data != marina_result.data
    assert kira_result.provenance.content_hash != marina_result.provenance.content_hash


def test_wrong_character_id_never_selects_another_repository(build_persona_root):
    catalog, _, _ = _build_two_character_catalog(build_persona_root)
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("kira_typo")
    with pytest.raises(CharacterNotFoundError):
        catalog.read_module("kira_typo", "core/IDENTITY.json")
    # Confirm the real repositories are unaffected and still independently
    # reachable under their exact ids.
    assert catalog.get_repository("kira") is not catalog.get_repository("marina")


def test_caller_cannot_substitute_root_after_construction(build_persona_root, tmp_path):
    root_kira = build_persona_root(
        character_id="kira",
        root_name="kira_root",
        modules={"core/IDENTITY.json": {"version": "1.0.0"}},
        module_content={"core/IDENTITY.json": {"owner": "kira-original"}},
    )
    entries = {"kira": root_kira}
    catalog = PersonaCatalog(entries)

    # Build a second, different persona root for the same id and try to
    # substitute it into the *original* mapping after construction.
    substitute_root = build_persona_root(
        character_id="kira",
        root_name="kira_substitute_root",
        modules={"core/IDENTITY.json": {"version": "1.0.0"}},
        module_content={"core/IDENTITY.json": {"owner": "kira-substituted"}},
    )
    entries["kira"] = substitute_root

    result = catalog.read_module("kira", "core/IDENTITY.json")
    assert result.data == {"owner": "kira-original"}


def test_repository_lookup_is_exact_and_case_sensitive(build_persona_root):
    catalog, _, _ = _build_two_character_catalog(build_persona_root)
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("Kira")
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("KIRA")
    # Exact original spelling still resolves.
    assert catalog.get_repository("kira") is catalog.get_repository("kira")


def test_case_insensitive_collision_rejected_at_construction(build_persona_root):
    root_lower = build_persona_root(character_id="kira", root_name="lower_root")
    root_upper = build_persona_root(character_id="KIRA", root_name="upper_root")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira": root_lower, "KIRA": root_upper})


def test_provenance_paths_remain_character_specific(build_persona_root):
    catalog, _, _ = _build_two_character_catalog(build_persona_root)
    kira_result = catalog.read_module("kira", "core/IDENTITY.json")
    marina_result = catalog.read_module("marina", "core/IDENTITY.json")

    assert kira_result.provenance.source == "personas/kira/core/IDENTITY.json"
    assert marina_result.provenance.source == "personas/marina/core/IDENTITY.json"
    assert kira_result.provenance.source != marina_result.provenance.source


# ---------------------------------------------------------------------
# Runtime memory isolation (existing StateSnapshotService/HistoryQueryService,
# unmodified) -- fixture session files are written directly, never via
# append_session/summarize_memory/reset_memory.
# ---------------------------------------------------------------------

def _write_raw_session(root: Path, slot: str, character: str, filename: str, session: dict) -> None:
    sessions_dir = root / "private_chats" / slot / character / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / filename).write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_snapshot_service_does_not_cross_read_between_characters(tmp_path):
    root = tmp_path / "aside_root"
    _write_raw_session(
        root, "slot1", "kira", "s1.json",
        {"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1,
         "summary": "kira-private-summary", "transcript": [{"role": "user", "content": "kira secret"}]},
    )
    _write_raw_session(
        root, "slot1", "marina", "s1.json",
        {"scene_id": "SC_2", "beat_id": "b2", "progress_index": 1,
         "summary": "marina-private-summary", "transcript": [{"role": "user", "content": "marina secret"}]},
    )

    service = StateSnapshotService(root, "slot1")

    kira_snapshot = service.get_state_snapshot("kira", progress=10)
    marina_snapshot = service.get_state_snapshot("marina", progress=10)

    assert "kira-private-summary" in kira_snapshot.summary
    assert "marina-private-summary" not in kira_snapshot.summary
    assert kira_snapshot.recent[-1].content == "kira secret"

    assert "marina-private-summary" in marina_snapshot.summary
    assert "kira-private-summary" not in marina_snapshot.summary
    assert marina_snapshot.recent[-1].content == "marina secret"


def test_history_query_service_does_not_cross_read_between_characters(tmp_path):
    root = tmp_path / "aside_root"
    _write_raw_session(
        root, "slot1", "kira", "s1.json",
        {"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1,
         "summary": "talked about the lighthouse", "transcript": []},
    )
    _write_raw_session(
        root, "slot1", "marina", "s1.json",
        {"scene_id": "SC_2", "beat_id": "b2", "progress_index": 1,
         "summary": "talked about the harbor", "transcript": []},
    )

    service = HistoryQueryService(root, "slot1")

    kira_result = service.search_history("kira", query="lighthouse", limit=10, progress=10)
    marina_result = service.search_history("marina", query="lighthouse", limit=10, progress=10)

    assert len(kira_result.records) == 1
    assert "lighthouse" in kira_result.records[0].snippet
    assert len(marina_result.records) == 0


def test_wrong_character_session_pairing_never_cross_reads(tmp_path):
    root = tmp_path / "aside_root"
    _write_raw_session(
        root, "slot1", "kira", "s1.json",
        {"scene_id": "SC_1", "beat_id": "b1", "progress_index": 1,
         "summary": "kira only", "transcript": []},
    )

    service = StateSnapshotService(root, "slot1")
    # A character with no written sessions of its own must never see
    # kira's saved memory just because it shares root/slot.
    with pytest.raises(SnapshotUnavailableError):
        service.get_state_snapshot("andrey_junior", progress=10)


def test_no_memory_write_api_imported_or_referenced():
    import ast

    # Parse this file's own source directly (rather than importing it as a
    # dotted module -- this test directory has no __init__.py, so plain
    # package-style self-import would be fragile).
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
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
