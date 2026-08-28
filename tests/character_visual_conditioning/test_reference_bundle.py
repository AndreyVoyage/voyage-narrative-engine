#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the generic provider-neutral ReferenceBundle layer.

Deterministic, hermetic, fully offline:

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    MEDIA_GENERATION = 0
    CANON_WRITES = 0
    LIVE_CANON_REREAD_DURING_BUNDLE_BUILD = 0

The bundle is exercised against synthetic in-memory frozen snapshots written to
a temp directory (never the real Character Canon).
"""

from __future__ import annotations

import dataclasses
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
    ReferenceBinaryError,
    ReferenceSelectionError,
    build_reference_bundle,
    snapshot_from_serialized,
    validate_reference_bundle_integrity,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 32
_JPEG = b"\xff\xd8\xff" + b"B" * 32
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"C" * 32


def _snapshot(character_id, references, status="PENDING_APPROVAL"):
    return CharacterCanonSnapshot(
        schema_version="character_canon/0.1",
        character_id=character_id,
        status=status,
        references=tuple(references),
        content_hash=f"canon_hash_{character_id.lower()}",
        provenance=Provenance(
            source_kind="character_canon_reference_presets",
            source_ref=(
                f"AI_CHARACTERS/{character_id}/10_notes/"
                f"{character_id}_REFERENCE_PRESETS.json"
            ),
            source_hash="src_hash",
        ),
        active_version="base",
    )


def _write(tmp_path, rel, payload=_PNG):
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(payload)
    return rel


def test_single_character_bundle_binds_bytes_and_roles(tmp_path):
    face = _write(tmp_path, "03_face_sheet/face.png", _PNG)
    expr = _write(tmp_path, "03_face_sheet/expressions/expr.png", _JPEG)
    snap = _snapshot(
        "KIRA",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="expression_canon", path=expr),
        ],
    )
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["KIRA"], canon_root=tmp_path
    )
    assert [g.character_id for g in bundle.character_groups] == ["KIRA"]
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [
        ["primary_face_reference"],
        ["expression_canon"],
    ]
    assert entries[0].payload == _PNG
    assert entries[0].sha256 == hashlib.sha256(_PNG).hexdigest()
    assert entries[0].byte_length == len(_PNG)
    assert entries[0].image_format == "PNG"
    assert entries[0].content_type == "image/png"
    assert entries[1].image_format == "JPEG"
    assert entries[1].content_type == "image/jpeg"
    assert entries[1].character_id == "KIRA"
    validate_reference_bundle_integrity(bundle)  # should not raise


def test_within_character_duplicate_path_carries_all_roles(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot(
        "CHAR_X",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="face_canon", path=face),
        ],
    )
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["CHAR_X"], canon_root=tmp_path
    )
    entries = bundle.character_groups[0].references
    assert len(entries) == 1
    assert entries[0].roles == ("primary_face_reference", "face_canon")
    assert entries[0].payload == _PNG


def test_no_cross_character_dedupe_even_with_equal_bytes(tmp_path):
    a = _write(tmp_path, "char_a/ref.png", _PNG)
    b = _write(tmp_path, "char_b/ref.png", _PNG)  # identical bytes
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    snap_b = _snapshot("CHAR_B", [CanonReference(key="face_canon", path=b)])
    bundle = build_reference_bundle(
        [snap_a, snap_b],
        characters_in_frame=["CHAR_A", "CHAR_B"],
        canon_root=tmp_path,
    )
    assert [g.character_id for g in bundle.character_groups] == ["CHAR_A", "CHAR_B"]
    assert len(bundle.character_groups[0].references) == 1
    assert len(bundle.character_groups[1].references) == 1
    assert bundle.character_groups[0].references[0].character_id == "CHAR_A"
    assert bundle.character_groups[1].references[0].character_id == "CHAR_B"



def test_two_character_ownership_distinct_bytes(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    b = _write(tmp_path, "b.png", _JPEG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="primary_face_reference", path=a)])
    snap_b = _snapshot(
        "CHAR_B",
        [
            CanonReference(key="primary_face_reference", path=b),
            CanonReference(key="expression_canon", path=b),
        ],
    )
    bundle = build_reference_bundle(
        [snap_a, snap_b],
        characters_in_frame=["CHAR_A", "CHAR_B"],
        canon_root=tmp_path,
    )
    ga, gb = bundle.character_groups
    assert ga.character_id == "CHAR_A"
    assert gb.character_id == "CHAR_B"
    assert ga.references[0].character_id == "CHAR_A"
    assert ga.references[0].payload == _PNG
    assert ga.references[0].sha256 == hashlib.sha256(_PNG).hexdigest()
    assert gb.references[0].character_id == "CHAR_B"
    assert gb.references[0].payload == _JPEG
    assert gb.references[0].roles == ("primary_face_reference", "expression_canon")
    assert gb.references[0].sha256 == hashlib.sha256(_JPEG).hexdigest()


def test_three_character_generic_bundle(tmp_path):
    ids = ["TEST_ALPHA_1", "ZZ-999_UNUSUAL", "CHAR_C"]
    snaps = []
    for cid in ids:
        p = _write(tmp_path, f"{cid}/face.png", _PNG)
        snaps.append(_snapshot(cid, [CanonReference(key="face_canon", path=p)]))
    bundle = build_reference_bundle(
        snaps, characters_in_frame=ids, canon_root=tmp_path
    )
    assert [g.character_id for g in bundle.character_groups] == ids


def test_synthetic_future_character_no_production_branch(tmp_path):
    p = _write(tmp_path, "future/face.png", _PNG)
    snap = _snapshot("TEST_NEW_CHARACTER", [CanonReference(key="face_canon", path=p)])
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["TEST_NEW_CHARACTER"], canon_root=tmp_path
    )
    assert bundle.character_groups[0].character_id == "TEST_NEW_CHARACTER"
    assert bundle.character_groups[0].references[0].payload == _PNG



def test_explicit_scene_preset_selection_keeps_frozen_order(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    outfit_0 = _write(tmp_path, "outfits/sports_0.png", _JPEG)
    outfit_1 = _write(tmp_path, "outfits/sports_1.png", _WEBP)
    formal = _write(tmp_path, "outfits/formal_0.png", _PNG)
    snap = _snapshot(
        "KIRA",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="scene:sports:0", path=outfit_0),
            CanonReference(key="scene:sports:1", path=outfit_1),
            CanonReference(key="scene:formal:0", path=formal),
        ],
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["KIRA"],
        canon_root=tmp_path,
        scene_preset_by_character={"KIRA": "sports"},
    )
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [
        ["primary_face_reference"],
        ["scene:sports:0"],
        ["scene:sports:1"],
    ]
    assert entries[1].image_format == "JPEG"
    assert entries[2].image_format == "WEBP"


def test_no_preset_inferred_from_anything(tmp_path):
    # Without an explicit preset, scene refs are excluded and are NOT inferred.
    face = _write(tmp_path, "face.png", _PNG)
    outfit = _write(tmp_path, "outfits/sports.png", _JPEG)
    snap = _snapshot(
        "KIRA",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="scene:sports:0", path=outfit),
        ],
    )
    bundle = build_reference_bundle(
        [snap], characters_in_frame=["KIRA"], canon_root=tmp_path
    )
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [["primary_face_reference"]]


def test_missing_preset_fails_closed(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=face)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap],
            characters_in_frame=["KIRA"],
            canon_root=tmp_path,
            scene_preset_by_character={"KIRA": "nonexistent"},
        )


def test_frame_order_preserved_exactly_not_alphabetical(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    b = _write(tmp_path, "b.png", _PNG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    snap_b = _snapshot("CHAR_B", [CanonReference(key="face_canon", path=b)])
    bundle = build_reference_bundle(
        [snap_a, snap_b],
        characters_in_frame=["CHAR_B", "CHAR_A"],
        canon_root=tmp_path,
    )
    assert [g.character_id for g in bundle.character_groups] == ["CHAR_B", "CHAR_A"]


def test_bundle_from_frozen_serialized_snapshot(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("TEST_NEW_CHARACTER", [CanonReference(key="face_canon", path=face)])
    serialized = snap.to_dict()  # equivalent to CharacterAnchor.serialized_snapshot
    reconstructed = snapshot_from_serialized(serialized)
    assert reconstructed.character_id == "TEST_NEW_CHARACTER"
    assert reconstructed.references == snap.references
    bundle = build_reference_bundle(
        [reconstructed],
        characters_in_frame=["TEST_NEW_CHARACTER"],
        canon_root=tmp_path,
    )
    assert bundle.character_groups[0].character_id == "TEST_NEW_CHARACTER"
    assert bundle.character_groups[0].references[0].payload == _PNG



# ---------------------------------------------------------------------------
# Fail-closed: the entire bundle fails, never a partial bundle
# ---------------------------------------------------------------------------


def test_missing_file_fails_closed(tmp_path):
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path="missing.png")])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)


def test_empty_file_fails_closed(tmp_path):
    p = _write(tmp_path, "empty.png", b"")
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=p)])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)


def test_bad_format_fails_closed(tmp_path):
    p = _write(tmp_path, "bad.bin", b"not-an-image")
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=p)])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)


@pytest.mark.parametrize(
    "bad_path",
    ["../outside.png", "/etc/passwd", "C:/abs.png", "a//b.png", "a/./b.png"],
)
def test_unsafe_path_fails_closed(tmp_path, bad_path):
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=bad_path)])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)


def test_zero_usable_refs_fails_closed(tmp_path):
    outfit = _write(tmp_path, "outfits/sports.png", _PNG)
    snap = _snapshot("KIRA", [CanonReference(key="scene:sports:0", path=outfit)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)


def test_broken_one_of_two_fails_entire_bundle(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    snap_b = _snapshot("CHAR_B", [CanonReference(key="face_canon", path="missing.png")])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle(
            [snap_a, snap_b],
            characters_in_frame=["CHAR_A", "CHAR_B"],
            canon_root=tmp_path,
        )


def test_duplicate_frame_character_fails_closed(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap_a], characters_in_frame=["CHAR_A", "CHAR_A"], canon_root=tmp_path
        )


def test_missing_snapshot_for_frame_character_fails_closed(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap_a], characters_in_frame=["CHAR_A", "CHAR_UNKNOWN"], canon_root=tmp_path
        )


# ---------------------------------------------------------------------------
# Integrity, determinism, status preservation
# ---------------------------------------------------------------------------


def test_bundle_content_hash_deterministic(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=face)])
    b1 = build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)
    b2 = build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)
    assert b1.content_hash == b2.content_hash
    assert b1.content_hash != ""


def test_bundle_integrity_detects_tamper(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("KIRA", [CanonReference(key="face_canon", path=face)])
    bundle = build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)
    validate_reference_bundle_integrity(bundle)
    tampered = dataclasses.replace(bundle, content_hash="deadbeef")
    with pytest.raises(ReferenceSelectionError):
        validate_reference_bundle_integrity(tampered)


def test_status_carried_verbatim_not_promoted(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot(
        "KIRA",
        [CanonReference(key="face_canon", path=face)],
        status="APPROVED_AS_TEST",
    )
    bundle = build_reference_bundle([snap], characters_in_frame=["KIRA"], canon_root=tmp_path)
    assert bundle.character_groups[0].status == "APPROVED_AS_TEST"
    # The bundle never derives or exposes production eligibility.
    assert not hasattr(bundle, "production_eligible")
