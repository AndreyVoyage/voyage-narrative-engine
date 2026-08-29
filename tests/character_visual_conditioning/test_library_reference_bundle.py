#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the Library -> ReferenceBundle adapter (RBA v0).

The provider-neutral bridge resolves already-resolved Reference Library records
into the existing provider-neutral ReferenceBundle, then feeds the existing RC3
provider attachment. Fully offline and hermetic:

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    IMAGE_GENERATION = 0
    REAL_IMPORTS = 0
    NCC_READS = 0
    NCC_WRITES = 0

Library assets are synthetic files under a per-test tmp_path; no real Reference
Library manifest is loaded and no real asset is imported.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.character_canon_bridge import (  # noqa: E402
    CanonReference,
    CharacterCanonSnapshot,
    Provenance,
)
from services.character_visual_conditioning import (  # noqa: E402
    DEFAULT_LIBRARY_ROLE,
    ReferenceBinaryError,
    ReferenceCharacterGroup,
    ReferenceEntry,
    ReferenceImageInput,
    ReferenceSelectionError,
    build_reference_bundle,
    build_reference_bundle_from_library,
    build_reference_map,
    compute_content_hash,
    reference_inputs_from_bundle,
    validate_reference_bundle_integrity,
)
from services.reference_library import ReferenceRecord  # noqa: E402

_PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 32
_JPEG = b"\xff\xd8\xff" + b"B" * 32
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"C" * 32

_FMT_EXT = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}

# Stage 1 pre-edit Canon hash baseline (must remain identical after edit).
_CANON_ENTRY_HASH_BEFORE = "b60094e87e9df13c4ca9cc6e4b6f23920bfbab87cbaf301ccd1f1dc368387d8c"
_CANON_GROUP_HASH_BEFORE = "fb27f7c7267e9ad6b956fd7f9e6810c56a9e5f8fce40ac753b7936995a0cc429"
_CANON_BUNDLE_HASH_BEFORE = "27e387468a43ea67b3a31cc7c78865c3a7a5c6177d1d3be11324148bddd01737"


def _detect(payload):
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if payload.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "WEBP"
    raise AssertionError("unsupported test payload")


def _default_rel(character_id, asset_id, payload=_PNG):
    ext = _FMT_EXT[_detect(payload)]
    return (
        f"authoring/reference_library/assets/characters/"
        f"{character_id}/{asset_id}.{ext}"
    )


def _library_record(character_id, asset_id, *, payload=_PNG, file_type=None,
                    sha256=None, relative_path=None):
    fmt = file_type or _detect(payload)
    rel = relative_path if relative_path is not None else _default_rel(
        character_id, asset_id, payload
    )
    filename = rel.split("/")[-1]
    if sha256 is None:
        sha256 = hashlib.sha256(payload).hexdigest()
    return ReferenceRecord(
        asset_id=asset_id,
        character_id=character_id,
        relative_path=rel,
        filename=filename,
        sha256=sha256,
        file_type=fmt,
    )


def _write_asset(tmp_path, character_id, asset_id, payload=_PNG):
    rel = _default_rel(character_id, asset_id, payload)
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(payload)
    return rel


def _build(tmp_path, selected, frame, roles_by_asset_id=None):
    return build_reference_bundle_from_library(
        selected,
        characters_in_frame=frame,
        repo_root=tmp_path,
        roles_by_asset_id=roles_by_asset_id,
    )


def _canon_snapshot():
    return CharacterCanonSnapshot(
        schema_version="character_canon/0.1",
        character_id="BASELINE_CANON_CHAR",
        status="PENDING_APPROVAL",
        references=(
            CanonReference(key="primary_face_reference", path="03_face_sheet/face.png"),
            CanonReference(key="expression_canon", path="03_face_sheet/expressions/expr.png"),
        ),
        content_hash="canon_hash_baseline_canon_char",
        provenance=Provenance(
            source_kind="character_canon_reference_presets",
            source_ref=(
                "AI_CHARACTERS/BASELINE_CANON_CHAR/10_notes/"
                "BASELINE_CANON_CHAR_REFERENCE_PRESETS.json"
            ),
            source_hash="src_hash",
        ),
        active_version="base",
    )


def _write_canon_assets(tmp_path):
    for rel, data in (
        ("03_face_sheet/face.png", _PNG),
        ("03_face_sheet/expressions/expr.png", _JPEG),
    ):
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)


# ---------------------------------------------------------------------------
# Library-origin bundle: structure, ordering, metadata
# ---------------------------------------------------------------------------


def test_single_character_library_bundle(tmp_path):
    rel = _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    rec = _library_record("CHAR_A", "a1", payload=_PNG)
    bundle = _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])
    assert [g.character_id for g in bundle.character_groups] == ["CHAR_A"]
    group = bundle.character_groups[0]
    assert group.status is None
    assert group.canon_content_hash is None
    entry = group.references[0]
    assert entry.source_asset_id == "a1"
    assert entry.roles == ("reference",)
    assert entry.payload == _PNG
    assert entry.path == rel


def test_two_character_library_bundle(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_B", "b1", _JPEG)
    rec_a = _library_record("CHAR_A", "a1", payload=_PNG)
    rec_b = _library_record("CHAR_B", "b1", payload=_JPEG)
    bundle = _build(
        tmp_path,
        {"CHAR_A": [rec_a], "CHAR_B": [rec_b]},
        ["CHAR_A", "CHAR_B"],
    )
    assert [g.character_id for g in bundle.character_groups] == ["CHAR_A", "CHAR_B"]
    assert bundle.character_groups[1].references[0].image_format == "JPEG"


def test_arbitrary_future_character_ids(tmp_path):
    ids = ["ZZ-999_UNUSUAL", "TEST_FUTURE_9000"]
    selected = {}
    for cid in ids:
        _write_asset(tmp_path, cid, f"{cid}_a", _PNG)
        selected[cid] = [_library_record(cid, f"{cid}_a", payload=_PNG)]
    bundle = _build(tmp_path, selected, ids)
    assert [g.character_id for g in bundle.character_groups] == ids


def test_character_group_order_follows_frame(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_B", "b1", _PNG)
    rec_a = _library_record("CHAR_A", "a1")
    rec_b = _library_record("CHAR_B", "b1")
    bundle = _build(
        tmp_path,
        {"CHAR_A": [rec_a], "CHAR_B": [rec_b]},
        ["CHAR_B", "CHAR_A"],  # non-alphabetical
    )
    assert [g.character_id for g in bundle.character_groups] == ["CHAR_B", "CHAR_A"]


def test_selected_asset_order_preserved(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_A", "a2", _JPEG)
    _write_asset(tmp_path, "CHAR_A", "a3", _WEBP)
    recs = [
        _library_record("CHAR_A", "a1", payload=_PNG),
        _library_record("CHAR_A", "a2", payload=_JPEG),
        _library_record("CHAR_A", "a3", payload=_WEBP),
    ]
    bundle = _build(tmp_path, {"CHAR_A": recs}, ["CHAR_A"])
    entries = bundle.character_groups[0].references
    assert [e.source_asset_id for e in entries] == ["a1", "a2", "a3"]
    assert [e.image_format for e in entries] == ["PNG", "JPEG", "WEBP"]


def test_source_asset_id_populated(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "asset_42", _PNG)
    rec = _library_record("CHAR_A", "asset_42")
    bundle = _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])
    assert bundle.character_groups[0].references[0].source_asset_id == "asset_42"


def test_library_group_status_is_none(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    assert bundle.character_groups[0].status is None


def test_library_group_canon_content_hash_is_none(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    assert bundle.character_groups[0].canon_content_hash is None


def test_library_semantic_payload_omits_canon_only_keys(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    payload = bundle.character_groups[0].semantic_payload()
    assert "status" not in payload
    assert "canon_content_hash" not in payload
    assert payload["character_id"] == "CHAR_A"
    assert "references" in payload


def test_library_to_dict_omits_canon_only_keys(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    d = bundle.character_groups[0].to_dict()
    assert "status" not in d
    assert "canon_content_hash" not in d


def test_default_role_is_reference(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    assert bundle.character_groups[0].references[0].roles == ("reference",)
    assert DEFAULT_LIBRARY_ROLE == "reference"


def test_explicit_roles_accepted(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    bundle = _build(
        tmp_path,
        {"CHAR_A": [rec]},
        ["CHAR_A"],
        roles_by_asset_id={"a1": ("outfit", "face")},
    )
    assert bundle.character_groups[0].references[0].roles == ("outfit", "face")


# ---------------------------------------------------------------------------
# Fail-closed: roles, coverage, ownership, paths, bytes
# ---------------------------------------------------------------------------


def test_empty_explicit_role_sequence_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"], roles_by_asset_id={"a1": ()})


def test_empty_role_string_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"], roles_by_asset_id={"a1": ("ok", "")})


def test_unknown_role_map_asset_id_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"], roles_by_asset_id={"nope": ("reference",)})


def test_missing_character_selection_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A", "CHAR_B"])


def test_empty_selection_rejected(tmp_path):
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": []}, ["CHAR_A"])


def test_duplicate_frame_character_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A", "CHAR_A"])


def test_extra_selected_character_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    _write_asset(tmp_path, "CHAR_B", "b1")
    rec_a = _library_record("CHAR_A", "a1")
    rec_b = _library_record("CHAR_B", "b1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec_a], "CHAR_B": [rec_b]}, ["CHAR_A"])


def test_ownership_mismatch_rejected(tmp_path):
    # Record claims CHAR_B while selected under CHAR_A's group key.
    rec = _library_record("CHAR_B", "a1")
    with pytest.raises(ReferenceSelectionError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_absolute_path_rejected(tmp_path):
    rec = _library_record("CHAR_A", "a1", relative_path="/etc/passwd.png")
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_unsafe_traversal_path_rejected(tmp_path):
    rec = _library_record("CHAR_A", "a1", relative_path="../outside.png")
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_path_outside_asset_root_rejected(tmp_path):
    rec = _library_record(
        "CHAR_A", "a1", relative_path="authoring/other/thing.png"
    )
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_path_under_another_character_rejected(tmp_path):
    rec = _library_record(
        "CHAR_A", "a1",
        relative_path="authoring/reference_library/assets/characters/CHAR_B/a1.png",
    )
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_missing_file_rejected(tmp_path):
    rec = _library_record("CHAR_A", "a1")  # file never written
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_directory_instead_of_file_rejected(tmp_path):
    rel = _default_rel("CHAR_A", "a1")
    full = tmp_path / rel
    full.mkdir(parents=True, exist_ok=True)
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_empty_file_rejected(tmp_path):
    rel = _default_rel("CHAR_A", "a1")
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(b"")
    rec = _library_record("CHAR_A", "a1")
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_file_type_magic_mismatch_rejected(tmp_path):
    # Write PNG bytes but declare JPEG.
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    rec = _library_record("CHAR_A", "a1", payload=_PNG, file_type="JPEG")
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


def test_manifest_sha_mismatch_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    rec = _library_record("CHAR_A", "a1", payload=_PNG, sha256="0" * 64)
    with pytest.raises(ReferenceBinaryError):
        _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])


# ---------------------------------------------------------------------------
# Ordering, dedupe, determinism, integrity
# ---------------------------------------------------------------------------


def test_duplicate_path_collapse_deterministic(tmp_path):
    shared_rel = _default_rel("CHAR_A", "shared")
    full = tmp_path / shared_rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(_PNG)
    rec1 = _library_record("CHAR_A", "a1", relative_path=shared_rel)
    rec2 = _library_record("CHAR_A", "a2", relative_path=shared_rel)
    roles = {"a1": ("r1",), "a2": ("r2",)}
    b1 = _build(tmp_path, {"CHAR_A": [rec1, rec2]}, ["CHAR_A"], roles_by_asset_id=roles)
    b2 = _build(tmp_path, {"CHAR_A": [rec1, rec2]}, ["CHAR_A"], roles_by_asset_id=roles)
    entries = b1.character_groups[0].references
    assert len(entries) == 1
    assert entries[0].roles == ("r1", "r2")
    assert entries[0].source_asset_id == "a1"  # first occurrence wins
    assert b1.content_hash == b2.content_hash


def test_no_cross_character_dedupe(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_B", "b1", _PNG)  # identical bytes
    rec_a = _library_record("CHAR_A", "a1", payload=_PNG)
    rec_b = _library_record("CHAR_B", "b1", payload=_PNG)
    bundle = _build(tmp_path, {"CHAR_A": [rec_a], "CHAR_B": [rec_b]}, ["CHAR_A", "CHAR_B"])
    assert len(bundle.character_groups) == 2
    assert len(bundle.character_groups[0].references) == 1
    assert len(bundle.character_groups[1].references) == 1
    assert bundle.character_groups[0].references[0].character_id == "CHAR_A"
    assert bundle.character_groups[1].references[0].character_id == "CHAR_B"


def test_bundle_integrity_validation_passes(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    bundle = _build(tmp_path, {"CHAR_A": [_library_record("CHAR_A", "a1")]}, ["CHAR_A"])
    validate_reference_bundle_integrity(bundle)  # should not raise


def test_content_hash_deterministic(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1")
    rec = _library_record("CHAR_A", "a1")
    b1 = _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])
    b2 = _build(tmp_path, {"CHAR_A": [rec]}, ["CHAR_A"])
    assert b1.content_hash == b2.content_hash
    assert b1.content_hash != ""


def _plain_entry(source_asset_id=None):
    return ReferenceEntry(
        character_id="CHAR_A",
        roles=("reference",),
        path="authoring/reference_library/assets/characters/CHAR_A/a1.png",
        image_format="PNG",
        content_type="image/png",
        sha256=hashlib.sha256(_PNG).hexdigest(),
        byte_length=len(_PNG),
        payload=_PNG,
        source_asset_id=source_asset_id,
    )


def test_source_asset_id_changes_library_semantic_hash():
    e_none = _plain_entry(source_asset_id=None)
    e_a1 = _plain_entry(source_asset_id="a1")
    assert "source_asset_id" not in e_none.semantic_payload()
    assert e_a1.semantic_payload()["source_asset_id"] == "a1"
    assert compute_content_hash(e_none.semantic_payload()) != compute_content_hash(
        e_a1.semantic_payload()
    )


# ---------------------------------------------------------------------------
# Model pair invariant + Canon metadata
# ---------------------------------------------------------------------------


def test_canon_group_both_metadata_present_passes():
    group = ReferenceCharacterGroup(
        character_id="C",
        references=(),
        status="APPROVED",
        canon_content_hash="abc123",
    )
    assert group.status == "APPROVED"
    assert "status" in group.semantic_payload()
    assert "canon_content_hash" in group.semantic_payload()


def test_library_group_both_metadata_none_passes():
    group = ReferenceCharacterGroup(character_id="C", references=())
    assert group.status is None
    assert group.canon_content_hash is None
    assert "status" not in group.semantic_payload()
    assert "canon_content_hash" not in group.semantic_payload()


def test_half_present_canon_metadata_fails():
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), status="APPROVED")
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), canon_content_hash="abc")


def test_empty_canon_metadata_field_fails():
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), status="", canon_content_hash="")
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), status="X", canon_content_hash="")


def test_canon_source_asset_id_none_omitted():
    entry = _plain_entry(source_asset_id=None)
    assert "source_asset_id" not in entry.semantic_payload()
    assert "source_asset_id" not in entry.to_dict()


# ---------------------------------------------------------------------------
# Canon builder freeze: exact pre-edit hash baseline
# ---------------------------------------------------------------------------


def test_canon_builder_semantic_payload_unchanged(tmp_path):
    _write_canon_assets(tmp_path)
    snap = _canon_snapshot()
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["BASELINE_CANON_CHAR"], canon_root=tmp_path
    )
    group = bundle.character_groups[0]
    entry = group.references[0]
    assert entry.semantic_payload() == {
        "character_id": "BASELINE_CANON_CHAR",
        "roles": ["primary_face_reference"],
        "path": "03_face_sheet/face.png",
        "image_format": "PNG",
        "content_type": "image/png",
        "sha256": "5893dd1dfe88511ecfbeb6140a8d09b2103d13602fb6dce15875173dcb37bb99",
        "byte_length": 40,
    }
    assert "source_asset_id" not in entry.semantic_payload()
    assert group.semantic_payload() == {
        "character_id": "BASELINE_CANON_CHAR",
        "status": "PENDING_APPROVAL",
        "canon_content_hash": "canon_hash_baseline_canon_char",
        "references": [
            {
                "character_id": "BASELINE_CANON_CHAR",
                "roles": ["primary_face_reference"],
                "path": "03_face_sheet/face.png",
                "image_format": "PNG",
                "content_type": "image/png",
                "sha256": "5893dd1dfe88511ecfbeb6140a8d09b2103d13602fb6dce15875173dcb37bb99",
                "byte_length": 40,
            },
            {
                "character_id": "BASELINE_CANON_CHAR",
                "roles": ["expression_canon"],
                "path": "03_face_sheet/expressions/expr.png",
                "image_format": "JPEG",
                "content_type": "image/jpeg",
                "sha256": "4cec41c68f3aec6c309869cf155533d431a9d3434c7a84b2ee000ffb2e2137ee",
                "byte_length": 35,
            },
        ],
    }


def test_canon_builder_content_hash_baseline_unchanged(tmp_path):
    _write_canon_assets(tmp_path)
    snap = _canon_snapshot()
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["BASELINE_CANON_CHAR"], canon_root=tmp_path
    )
    group = bundle.character_groups[0]
    entry = group.references[0]
    assert compute_content_hash(entry.semantic_payload()) == _CANON_ENTRY_HASH_BEFORE
    assert compute_content_hash(group.semantic_payload()) == _CANON_GROUP_HASH_BEFORE
    assert bundle.content_hash == _CANON_BUNDLE_HASH_BEFORE


# ---------------------------------------------------------------------------
# RC3 offline compatibility: Library bundle -> existing provider attachment
# ---------------------------------------------------------------------------


def _two_char_library_bundle(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_A", "a2", _JPEG)
    _write_asset(tmp_path, "CHAR_B", "b1", _WEBP)
    recs = {
        "CHAR_A": [
            _library_record("CHAR_A", "a1", payload=_PNG),
            _library_record("CHAR_A", "a2", payload=_JPEG),
        ],
        "CHAR_B": [_library_record("CHAR_B", "b1", payload=_WEBP)],
    }
    return _build(tmp_path, recs, ["CHAR_A", "CHAR_B"])


def test_reference_inputs_from_bundle_accepts_library_bundle(tmp_path):
    bundle = _two_char_library_bundle(tmp_path)
    inputs = reference_inputs_from_bundle(bundle)
    assert isinstance(inputs, list)
    assert all(isinstance(i, ReferenceImageInput) for i in inputs)


def test_attachment_count_matches_selected_entries(tmp_path):
    bundle = _two_char_library_bundle(tmp_path)
    inputs = reference_inputs_from_bundle(bundle)
    assert len(inputs) == 3


def test_attachment_order_deterministic(tmp_path):
    bundle = _two_char_library_bundle(tmp_path)
    inputs1 = reference_inputs_from_bundle(bundle)
    inputs2 = reference_inputs_from_bundle(bundle)
    assert [i.filename for i in inputs1] == [i.filename for i in inputs2]
    assert [i.filename for i in inputs1] == [
        "ref_000_CHAR_A.png",
        "ref_001_CHAR_A.jpg",
        "ref_002_CHAR_B.webp",
    ]


def test_build_reference_map_works_without_rc3_change(tmp_path):
    bundle = _two_char_library_bundle(tmp_path)
    refmap = build_reference_map(bundle)
    assert refmap.startswith("[REFERENCE MAP]")
    assert "character_id=CHAR_A" in refmap
    assert "character_id=CHAR_B" in refmap
    assert "roles=reference" in refmap
    assert "source=authoring/reference_library/assets/characters/CHAR_A/a1.png" in refmap


def test_no_provider_or_network_operation_required(tmp_path):
    # The adapter + attachment are fully offline: no monkeypatching needed.
    bundle = _two_char_library_bundle(tmp_path)
    inputs = reference_inputs_from_bundle(bundle)
    refmap = build_reference_map(bundle)
    assert len(inputs) == 3
    assert refmap.count("image[") == 3
