#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reference Library v0 tests -- manifest validation, path safety, SHA query,
and deterministic round-trip against the seeded manifest."""

from __future__ import annotations

import json

import pytest

from services.reference_library import (
    ASSET_ROOT,
    LIBRARY_ROOT,
    MANIFEST_FILENAME,
    MANIFEST_RELATIVE_PATH,
    MANIFEST_SCHEMA_VERSION,
    ReferenceLibraryManifestError,
    ReferenceLibraryNotFoundError,
    ReferenceLibraryValidationError,
    ReferenceRecord,
    default_manifest_path,
    find_records_by_sha256,
    is_safe_relative_path,
    is_under_asset_root,
    is_valid_relative_path,
    load_manifest,
    lookup_record,
    parse_manifest,
    save_manifest,
    serialize_manifest,
    validate_manifest,
)

from .conftest import REPO_ROOT, SEEDED_MANIFEST, make_record, sha256_of


def write_manifest(tmp_path, references, schema=MANIFEST_SCHEMA_VERSION):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"schema_version": schema, "references": references}, indent=2),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Seeded empty manifest + path constants
# ---------------------------------------------------------------------------


def test_seeded_manifest_is_valid_empty():
    assert SEEDED_MANIFEST.is_file()
    assert load_manifest(SEEDED_MANIFEST) == []
    assert validate_manifest(SEEDED_MANIFEST) == []


def test_seeded_manifest_matches_deterministic_empty_serialization():
    assert SEEDED_MANIFEST.read_text(encoding="utf-8") == serialize_manifest([])


def test_manifest_path_constants():
    assert MANIFEST_FILENAME == "REFERENCE_LIBRARY_MANIFEST.json"
    assert MANIFEST_RELATIVE_PATH == "authoring/reference_library/REFERENCE_LIBRARY_MANIFEST.json"
    assert LIBRARY_ROOT == "authoring/reference_library"
    assert ASSET_ROOT == "authoring/reference_library/assets"
    assert default_manifest_path(REPO_ROOT) == REPO_ROOT / MANIFEST_RELATIVE_PATH


# ---------------------------------------------------------------------------
# Duplicate asset_id / duplicate sha / sha rejection
# ---------------------------------------------------------------------------


def test_duplicate_asset_id_rejected(tmp_path):
    rec = make_record()
    errors = validate_manifest(write_manifest(tmp_path, [rec, rec]))
    assert any("duplicate" in e and "asset_id" in e for e in errors)


def test_duplicate_sha_query_returns_all_matches():
    digest = sha256_of(b"same-bytes")
    a = ReferenceRecord.from_dict(make_record(asset_id="a_one", sha256=digest))
    b = ReferenceRecord.from_dict(make_record(asset_id="b_two", sha256=digest))
    c = ReferenceRecord.from_dict(make_record(asset_id="c_three"))
    matches = find_records_by_sha256([a, b, c], digest)
    assert {r.asset_id for r in matches} == {"a_one", "b_two"}


def test_invalid_sha_query_rejected():
    rec = ReferenceRecord.from_dict(make_record())
    with pytest.raises(ReferenceLibraryValidationError):
        find_records_by_sha256([rec], "not-a-sha")


def test_invalid_sha_in_manifest_rejected(tmp_path):
    errors = validate_manifest(write_manifest(tmp_path, [make_record(sha256="bad")]))
    assert any("sha256" in e for e in errors)


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/etc/passwd.png", "\\absolute\\path.png"])
def test_absolute_path_rejected(path):
    assert not is_safe_relative_path(path)
    assert not is_valid_relative_path(path)


@pytest.mark.parametrize("path", ["C:/foo/bar.png", "c:\\foo\\bar.png", "D:/x.png"])
def test_drive_qualified_path_rejected(path):
    assert not is_safe_relative_path(path)
    assert not is_valid_relative_path(path)


@pytest.mark.parametrize("path", ["//server/share/x.png", "\\\\server\\share\\x.png"])
def test_unc_path_rejected(path):
    assert not is_safe_relative_path(path)
    assert not is_valid_relative_path(path)


@pytest.mark.parametrize("path", [
    "../evil.png",
    "authoring/reference_library/assets/../../evil.png",
])
def test_parent_traversal_rejected(path):
    assert not is_safe_relative_path(path)
    assert not is_valid_relative_path(path)


def test_safe_nested_relative_path_accepted():
    path = "authoring/reference_library/assets/characters/kira/outfits/casual/kira_casual.png"
    assert is_safe_relative_path(path)
    assert is_under_asset_root(path)
    assert is_valid_relative_path(path)


@pytest.mark.parametrize("bad", [
    "../evil.png",
    "C:/evil.png",
    "//server/x.png",
    "authoring/reference_library/evil.png",
])
def test_unsafe_relative_path_in_manifest_rejected(tmp_path, bad):
    errors = validate_manifest(write_manifest(tmp_path, [make_record(relative_path=bad)]))
    assert any("relative_path" in e for e in errors)


# ---------------------------------------------------------------------------
# file_type in manifest
# ---------------------------------------------------------------------------


def test_unsupported_file_type_in_manifest_rejected(tmp_path):
    errors = validate_manifest(write_manifest(tmp_path, [make_record(file_type="GIF")]))
    assert any("file_type" in e for e in errors)


# ---------------------------------------------------------------------------
# filename / relative_path consistency
# ---------------------------------------------------------------------------


def test_filename_must_match_relative_path_basename(tmp_path):
    errors = validate_manifest(write_manifest(tmp_path, [make_record(filename="wrong.png")]))
    assert any("filename" in e for e in errors)


def test_filename_matching_is_accepted(tmp_path):
    assert validate_manifest(write_manifest(tmp_path, [make_record()])) == []


# ---------------------------------------------------------------------------
# save/load round-trip + parse/load error cases
# ---------------------------------------------------------------------------


def test_save_then_load_is_round_trip(tmp_path):
    records = [ReferenceRecord.from_dict(make_record(asset_id="a"))]
    out = tmp_path / "out.json"
    save_manifest(out, records)
    loaded = load_manifest(out)
    assert [r.to_dict() for r in loaded] == [r.to_dict() for r in records]


def test_parse_manifest_rejects_wrong_schema(tmp_path):
    with pytest.raises(ReferenceLibraryManifestError):
        load_manifest(write_manifest(tmp_path, [], schema="other/0.1"))


def test_load_missing_manifest_raises(tmp_path):
    with pytest.raises(ReferenceLibraryManifestError):
        load_manifest(tmp_path / "missing.json")


def test_validate_missing_manifest(tmp_path):
    assert validate_manifest(tmp_path / "missing.json") == ["manifest does not exist"]


def test_validate_manifest_reports_schema_mismatch(tmp_path):
    errors = validate_manifest(write_manifest(tmp_path, [], schema="wrong/0.1"))
    assert any("schema_version" in e for e in errors)


# ---------------------------------------------------------------------------
# lookup fail-closed
# ---------------------------------------------------------------------------


def test_lookup_record_exact():
    a = ReferenceRecord.from_dict(make_record(asset_id="kira_neutral"))
    assert lookup_record([a], "kira_neutral") is a


def test_lookup_record_missing_fails_closed():
    with pytest.raises(ReferenceLibraryNotFoundError):
        lookup_record([], "missing")


def test_lookup_record_ambiguous_fails_closed():
    a = ReferenceRecord.from_dict(make_record(asset_id="dup"))
    b = ReferenceRecord.from_dict(make_record(asset_id="dup"))
    with pytest.raises(ReferenceLibraryValidationError):
        lookup_record([a, b], "dup")
