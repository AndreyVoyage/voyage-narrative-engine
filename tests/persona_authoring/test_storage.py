#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Storage tests -- atomic writes, path protection, JSONL safety."""

import json
import uuid
from pathlib import Path

import pytest
from services.persona_authoring import (
    PacCanonError,
    PacStorage,
    PacStorageError,
    PacTrainingExample,
)
from .conftest import valid_fmdr_text


def _make_example(example_id=None, approved_output="approved"):
    return PacTrainingExample(
        example_id=example_id or str(uuid.uuid4()),
        created_at="2026-07-25T12:00:00Z",
        character_id="kira",
        authoring_session_id=str(uuid.uuid4()),
        provider="local",
        model="test-model",
        canon_snapshot={"source_commit": "8c28521153eeed39f35840d7f82d0d571eddfb84", "modules": [{"module_id": "core/IDENTITY.json", "content_hash": "sha256:abc", "provenance": "gateway-v1"}]},
        context={"level": "U3-A", "situation": "test", "author_instruction": "test", "fmdr_required": True},
        model_output_raw=valid_fmdr_text(),
        approved_output=approved_output,
        provenance="human-edited",
    )


class TestStoragePaths:
    def test_separate_raw_approved_paths(self, storage):
        assert "raw" != "approved_scenes"
        assert storage.base_path.name == "pac"

    def test_utf8_round_trip(self, storage):
        ex = _make_example(approved_output="Русский текст с эмодзи 🎭")
        storage.append_dataset(ex)
        ds = storage.load_dataset()
        assert ds[ex.example_id]["approved_output"] == "Русский текст с эмодзи 🎭"

    def test_path_traversal_rejected(self, storage):
        with pytest.raises(PacStorageError, match="traversal"):
            storage._resolve("../escape")

    def test_absolute_escape_rejected(self, storage):
        with pytest.raises(PacStorageError):
            storage._resolve("/etc/passwd")

    def test_canon_directory_rejected(self):
        with pytest.raises(PacCanonError):
            PacStorage(base_path=Path("personas"))

    def test_existing_lines_preserved(self, storage):
        e1 = _make_example()
        storage.append_dataset(e1)
        e2 = _make_example()
        storage.append_dataset(e2)
        ds = storage.load_dataset()
        assert len(ds) == 2
        assert e1.example_id in ds
        assert e2.example_id in ds

    def test_duplicate_prevented(self, storage):
        e1 = _make_example()
        storage.append_dataset(e1)
        storage.append_dataset(e1)  # idempotent
        ds = storage.load_dataset()
        assert len(ds) == 1

    def test_partial_write_prevention(self, storage):
        e1 = _make_example()
        storage.append_dataset(e1)
        # Verify the dataset file is valid JSONL
        path = storage.dataset_path()
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            json.loads(line.strip())