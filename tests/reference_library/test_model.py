#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reference Library v0 tests -- model, fields, file_type, character_id,
collection semantics, and deterministic serialize/load/serialize."""

from __future__ import annotations

import dataclasses
import json

import pytest

from services.reference_library import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    SUPPORTED_FILE_TYPES,
    ReferenceLibraryFileTypeError,
    ReferenceLibrarySha256Error,
    ReferenceLibraryValidationError,
    ReferenceRecord,
    canonical_file_type,
    compute_sha256,
    is_valid_sha256,
    parse_manifest,
    serialize_manifest,
)

from .conftest import make_record, sha256_of


# ---------------------------------------------------------------------------
# Deterministic serialization / round-trip
# ---------------------------------------------------------------------------


def test_valid_empty_manifest_serializes_to_schema_only():
    assert json.loads(serialize_manifest([])) == {
        "schema_version": "vne_reference_library/0.1",
        "references": [],
    }


def test_serialize_parse_reserialize_is_byte_identical():
    records = [
        ReferenceRecord.from_dict(
            make_record(asset_id="z_last", collection="outfit", notes="hi")
        ),
        ReferenceRecord.from_dict(
            make_record(asset_id="a_first", character_id="ZZ-999_UNUSUAL")
        ),
    ]
    text = serialize_manifest(records)
    assert serialize_manifest(parse_manifest(text)) == text


def test_serialize_sorts_by_asset_id():
    records = [
        ReferenceRecord.from_dict(make_record(asset_id="zeta")),
        ReferenceRecord.from_dict(make_record(asset_id="alpha")),
        ReferenceRecord.from_dict(make_record(asset_id="mike")),
    ]
    data = json.loads(serialize_manifest(records))
    ids = [r["asset_id"] for r in data["references"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Required / optional fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_required_field_missing_rejected(field):
    data = make_record()
    del data[field]
    with pytest.raises(ReferenceLibraryValidationError):
        ReferenceRecord.from_dict(data)


def test_optional_fields_default_to_absent():
    rec = ReferenceRecord.from_dict(make_record())
    d = rec.to_dict()
    for field in OPTIONAL_FIELDS:
        assert field not in d


def test_optional_fields_preserved():
    data = make_record(
        collection="pilot outfit",
        mime_type="image/png",
        source_filename="source.png",
        created="2026-08-29T00:00:00Z",
        notes="hello",
    )
    rec = ReferenceRecord.from_dict(data)
    assert rec.collection == "pilot outfit"
    assert rec.mime_type == "image/png"
    assert rec.source_filename == "source.png"
    assert rec.created == "2026-08-29T00:00:00Z"
    assert rec.notes == "hello"


def test_model_is_frozen():
    rec = ReferenceRecord.from_dict(make_record())
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.asset_id = "other"


# ---------------------------------------------------------------------------
# file_type: supported set + JPG -> JPEG normalization
# ---------------------------------------------------------------------------


def test_supported_file_types():
    assert SUPPORTED_FILE_TYPES == ("PNG", "JPEG", "WEBP")


def test_unsupported_file_type_rejected():
    with pytest.raises(ReferenceLibraryFileTypeError):
        ReferenceRecord.from_dict(make_record(file_type="GIF"))


def test_canonical_file_type_unsupported_is_none():
    assert canonical_file_type("GIF") is None
    assert canonical_file_type(123) is None


@pytest.mark.parametrize("value,expected", [
    ("JPG", "JPEG"),
    ("jpeg", "JPEG"),
    ("jpg", "JPEG"),
    ("PNG", "PNG"),
    ("webp", "WEBP"),
])
def test_file_type_normalization(value, expected):
    assert canonical_file_type(value) == expected
    rec = ReferenceRecord.from_dict(make_record(file_type=value))
    assert rec.file_type == expected


# ---------------------------------------------------------------------------
# character_id: required, opaque, generic, non-empty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("character_id", ["TEST_NEW_CHARACTER", "ZZ-999_UNUSUAL", "kira"])
def test_arbitrary_future_character_ids_accepted(character_id):
    rec = ReferenceRecord.from_dict(make_record(character_id=character_id))
    assert rec.character_id == character_id


def test_character_id_required_and_non_empty():
    with pytest.raises(ReferenceLibraryValidationError):
        ReferenceRecord.from_dict(make_record(character_id=""))


# ---------------------------------------------------------------------------
# collection: optional free-string metadata (never a path segment)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("collection", ["pilot outfit 2026", "Summer/Beach", "UPPER CASE"])
def test_collection_free_string_metadata(collection):
    rec = ReferenceRecord.from_dict(make_record(collection=collection))
    assert rec.collection == collection


def test_collection_may_be_absent():
    rec = ReferenceRecord.from_dict(make_record())
    assert rec.collection is None
    assert "collection" not in rec.to_dict()


def test_collection_empty_string_treated_as_absent():
    rec = ReferenceRecord.from_dict(make_record(collection=""))
    assert rec.collection is None
    assert "collection" not in rec.to_dict()


def test_collection_non_string_rejected():
    with pytest.raises(ReferenceLibraryValidationError):
        ReferenceRecord.from_dict(make_record(collection=123))


# ---------------------------------------------------------------------------
# sha256 validation primitives
# ---------------------------------------------------------------------------


def test_compute_sha256_primitive():
    assert compute_sha256(b"x") == sha256_of(b"x")
    assert is_valid_sha256(compute_sha256(b"x"))


@pytest.mark.parametrize("bad", ["not-a-sha", "A" * 64, "a" * 63, "", 12345, None])
def test_invalid_sha256_rejected(bad):
    assert not is_valid_sha256(bad)


def test_invalid_sha256_rejected_on_construction():
    with pytest.raises(ReferenceLibrarySha256Error):
        ReferenceRecord.from_dict(make_record(sha256="not-a-sha"))
