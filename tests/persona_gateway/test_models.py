#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for services/persona_gateway/models.py."""

from __future__ import annotations

import dataclasses

import pytest

from services.persona_gateway.models import (
    CharacterManifest,
    CharacterRef,
    HistoryRecord,
    HistorySearchResult,
    MessageEntry,
    ModuleMetadata,
    ModuleResult,
    Provenance,
    SessionMeta,
    StateSnapshot,
)


def test_character_ref_is_frozen():
    ref = CharacterRef(id="kira", name="Кира")
    assert ref.id == "kira"
    assert ref.name == "Кира"
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.id = "other"  # type: ignore[misc]


def test_module_metadata_fields():
    meta = ModuleMetadata(module_id="core/IDENTITY.json", version="1.0.0", required=True, description=None)
    assert meta.module_id == "core/IDENTITY.json"
    assert meta.required is True
    assert meta.description is None


def test_character_manifest_holds_tuple_of_modules():
    meta = ModuleMetadata(module_id="core/IDENTITY.json", version="1.0.0", required=True, description=None)
    manifest = CharacterManifest(
        id="kira",
        name="Кира",
        version="2.2.0",
        schema_version="1.0.0",
        default_level="U2-A",
        default_ag_level=1,
        compatible_scenarios=("sauna_extended",),
        modules=(meta,),
    )
    assert isinstance(manifest.modules, tuple)
    assert manifest.modules[0] is meta
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.id = "other"  # type: ignore[misc]


def test_provenance_read_only_and_schema_none_for_modular_files():
    prov = Provenance(
        source="personas/kira/core/IDENTITY.json",
        schema=None,
        content_hash="a" * 64,
        version="1.0.0",
        read_only=True,
    )
    assert prov.schema is None
    assert prov.read_only is True
    assert prov.source == "personas/kira/core/IDENTITY.json"


def test_module_result_wraps_data_and_provenance():
    prov = Provenance(source="personas/kira/core/IDENTITY.json", schema=None, content_hash="a" * 64, version="1.0.0", read_only=True)
    result = ModuleResult(module_id="core/IDENTITY.json", data={"id": "kira"}, provenance=prov)
    assert result.data == {"id": "kira"}
    assert result.provenance.read_only is True


def test_state_snapshot_plain_data_only():
    snapshot = StateSnapshot(
        character_id="kira",
        summary="hello",
        recent=(MessageEntry(role="user", content="hi"),),
        session_count=1,
        max_progress_index=3,
        sessions=(SessionMeta(session_id="s1", scene_id="SC_1", beat_id="b1", progress_index=3),),
    )
    assert snapshot.recent[0].role == "user"
    assert snapshot.sessions[0].progress_index == 3
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.summary = "changed"  # type: ignore[misc]


def test_history_record_and_search_result():
    record = HistoryRecord(
        session_id="s1",
        scene_id="SC_1",
        beat_id="b1",
        progress_index=2,
        match_type="literal",
        snippet="matched text",
    )
    result = HistorySearchResult(character_id="kira", query="matched", limit=10, records=(record,))
    assert result.records[0].match_type == "literal"
    assert result.limit == 10
    assert isinstance(result.records, tuple)
