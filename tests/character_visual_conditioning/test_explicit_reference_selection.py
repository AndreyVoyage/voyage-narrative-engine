#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the optional explicit reference-selection contract (B4-RC4S).

Adds a generic, caller-side, provider-neutral explicit selection to the
ReferenceBundle construction layer WITHOUT changing default RC2 behavior.

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    IMAGE_GENERATION = 0
    CANON_WRITES = 0
    LIVE_CANON_REREAD_DURING_BUNDLE_BUILD = 0

Synthetic selection tests are fully hermetic (temp-dir frozen snapshots).
The real KIRA+SERGEY proof and the RC3 offline shadow are gated on
``VNE_CHARACTER_CANON_ROOT`` (they skip when the real Character Canon is not
available) and remain fully offline.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
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
    read_character_canon,
)
from services.character_visual_conditioning import (  # noqa: E402
    ReferenceBinaryError,
    ReferenceSelectionError,
    build_reference_bundle,
    build_reference_map,
    generate_conditioned_image_from_bundle,
    reference_inputs_from_bundle,
    validate_reference_bundle_integrity,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 32
_JPEG = b"\xff\xd8\xff" + b"B" * 32
_WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"C" * 32

# Owner-ratified RC5 bounded selection (B4-RC4S proof):
#   KIRA  -> 4 entries (primary_face_reference + face_canon share one path)
#   SERGEY -> 3 entries
_RC5_KIRA_KEYS = (
    "primary_face_reference",
    "face_canon",
    "body_canon_a",
    "scene:sports:0",
    "scene:sports:1",
)
_RC5_SERGEY_KEYS = (
    "primary_face_reference",
    "body_canon_a",
    "scene:sports:4",
)


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


# ---------------------------------------------------------------------------
# Synthetic explicit-selection semantics (Stage 6)
# ---------------------------------------------------------------------------


def test_explicit_single_character_subset(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    body = _write(tmp_path, "body.png", _JPEG)
    expr = _write(tmp_path, "expr.png", _WEBP)
    snap = _snapshot(
        "CHAR_A",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="body_canon_a", path=body),
            CanonReference(key="expression_canon", path=expr),
        ],
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["CHAR_A"],
        canon_root=tmp_path,
        reference_keys_by_character={"CHAR_A": ("body_canon_a",)},
    )
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [["body_canon_a"]]
    assert entries[0].payload == _JPEG
    validate_reference_bundle_integrity(bundle)


def test_explicit_two_character_different_subsets(tmp_path):
    a_face = _write(tmp_path, "a_face.png", _PNG)
    a_body = _write(tmp_path, "a_body.png", _JPEG)
    b_face = _write(tmp_path, "b_face.png", _WEBP)
    snap_a = _snapshot(
        "CHAR_A",
        [
            CanonReference(key="primary_face_reference", path=a_face),
            CanonReference(key="body_canon_a", path=a_body),
        ],
    )
    snap_b = _snapshot(
        "CHAR_B", [CanonReference(key="primary_face_reference", path=b_face)]
    )
    bundle = build_reference_bundle(
        [snap_a, snap_b],
        characters_in_frame=["CHAR_A", "CHAR_B"],
        canon_root=tmp_path,
        reference_keys_by_character={
            "CHAR_A": ("body_canon_a",),
            "CHAR_B": ("primary_face_reference",),
        },
    )
    ga, gb = bundle.character_groups
    assert [list(e.roles) for e in ga.references] == [["body_canon_a"]]
    assert [list(e.roles) for e in gb.references] == [["primary_face_reference"]]
    assert ga.references[0].payload == _JPEG
    assert gb.references[0].payload == _WEBP


def test_explicit_three_character_generic_selection(tmp_path):
    ids = ["TEST_ALPHA_1", "ZZ-999_UNUSUAL", "CHAR_C"]
    snaps = []
    for cid in ids:
        face = _write(tmp_path, f"{cid}/face.png", _PNG)
        body = _write(tmp_path, f"{cid}/body.png", _JPEG)
        snaps.append(
            _snapshot(
                cid,
                [
                    CanonReference(key="face_canon", path=face),
                    CanonReference(key="body_canon_a", path=body),
                ],
            )
        )
    bundle = build_reference_bundle(
        snaps,
        characters_in_frame=ids,
        canon_root=tmp_path,
        reference_keys_by_character={
            ids[0]: ("body_canon_a",),
            ids[1]: ("face_canon",),
            ids[2]: ("face_canon", "body_canon_a"),
        },
    )
    assert [g.character_id for g in bundle.character_groups] == ids
    assert [len(g.references) for g in bundle.character_groups] == [1, 1, 2]


def test_explicit_future_arbitrary_character_id(tmp_path):
    face = _write(tmp_path, "future/face.png", _PNG)
    snap = _snapshot(
        "TEST_NEW_CHARACTER_9000", [CanonReference(key="face_canon", path=face)]
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["TEST_NEW_CHARACTER_9000"],
        canon_root=tmp_path,
        reference_keys_by_character={"TEST_NEW_CHARACTER_9000": ("face_canon",)},
    )
    group = bundle.character_groups[0]
    assert group.character_id == "TEST_NEW_CHARACTER_9000"
    assert [list(e.roles) for e in group.references] == [["face_canon"]]


def test_explicit_unknown_key_fails_closed(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=face)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap],
            characters_in_frame=["CHAR_A"],
            canon_root=tmp_path,
            reference_keys_by_character={"CHAR_A": ("nonexistent_key",)},
        )


def test_explicit_key_for_other_character_fails_closed(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    b = _write(tmp_path, "b.png", _JPEG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon_a", path=a)])
    snap_b = _snapshot("CHAR_B", [CanonReference(key="face_canon_b", path=b)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap_a, snap_b],
            characters_in_frame=["CHAR_A", "CHAR_B"],
            canon_root=tmp_path,
            reference_keys_by_character={
                "CHAR_A": ("face_canon_b",),  # belongs to CHAR_B only
                "CHAR_B": ("face_canon_b",),
            },
        )


def test_explicit_empty_selection_fails_closed(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=face)])
    with pytest.raises(ReferenceSelectionError):
        build_reference_bundle(
            [snap],
            characters_in_frame=["CHAR_A"],
            canon_root=tmp_path,
            reference_keys_by_character={"CHAR_A": ()},
        )


def test_explicit_one_broken_character_fails_all(tmp_path):
    a = _write(tmp_path, "a.png", _PNG)
    snap_a = _snapshot("CHAR_A", [CanonReference(key="face_canon", path=a)])
    snap_b = _snapshot("CHAR_B", [CanonReference(key="face_canon", path="missing.png")])
    with pytest.raises(ReferenceBinaryError):
        build_reference_bundle(
            [snap_a, snap_b],
            characters_in_frame=["CHAR_A", "CHAR_B"],
            canon_root=tmp_path,
            reference_keys_by_character={
                "CHAR_A": ("face_canon",),
                "CHAR_B": ("face_canon",),
            },
        )


def test_explicit_duplicate_path_two_roles_single_entry(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    body = _write(tmp_path, "body.png", _JPEG)
    snap = _snapshot(
        "CHAR_X",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="face_canon", path=face),  # same path
            CanonReference(key="body_canon_a", path=body),
        ],
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["CHAR_X"],
        canon_root=tmp_path,
        reference_keys_by_character={
            "CHAR_X": ("primary_face_reference", "face_canon", "body_canon_a"),
        },
    )
    entries = bundle.character_groups[0].references
    assert len(entries) == 2
    assert entries[0].roles == ("primary_face_reference", "face_canon")
    assert entries[1].roles == ("body_canon_a",)
    assert entries[0].payload == _PNG


def test_no_selection_reproduces_existing_full_behavior(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    body = _write(tmp_path, "body.png", _JPEG)
    scene = _write(tmp_path, "sports.png", _WEBP)
    snap = _snapshot(
        "CHAR_A",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="body_canon_a", path=body),
            CanonReference(key="scene:sports:0", path=scene),
        ],
    )
    default = build_reference_bundle(
        [snap], characters_in_frame=["CHAR_A"], canon_root=tmp_path
    )
    explicit_none = build_reference_bundle(
        [snap],
        characters_in_frame=["CHAR_A"],
        canon_root=tmp_path,
        reference_keys_by_character=None,
    )
    roles = [list(e.roles) for e in default.character_groups[0].references]
    assert roles == [["primary_face_reference"], ["body_canon_a"]]
    assert default.content_hash == explicit_none.content_hash


def test_explicit_ordering_preserves_caller_order(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    body = _write(tmp_path, "body.png", _JPEG)
    expr = _write(tmp_path, "expr.png", _PNG)
    snap = _snapshot(
        "CHAR_A",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="body_canon_a", path=body),
            CanonReference(key="expression_canon", path=expr),
        ],
    )
    # caller order intentionally differs from frozen order
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["CHAR_A"],
        canon_root=tmp_path,
        reference_keys_by_character={
            "CHAR_A": ("body_canon_a", "primary_face_reference"),
        },
    )
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [
        ["body_canon_a"],
        ["primary_face_reference"],
    ]


def test_explicit_scene_key_selectable(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    sports0 = _write(tmp_path, "sports0.png", _JPEG)
    sports1 = _write(tmp_path, "sports1.png", _WEBP)
    snap = _snapshot(
        "CHAR_A",
        [
            CanonReference(key="primary_face_reference", path=face),
            CanonReference(key="scene:sports:0", path=sports0),
            CanonReference(key="scene:sports:1", path=sports1),
        ],
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["CHAR_A"],
        canon_root=tmp_path,
        reference_keys_by_character={
            "CHAR_A": ("scene:sports:1", "primary_face_reference"),
        },
    )
    entries = bundle.character_groups[0].references
    assert [list(e.roles) for e in entries] == [
        ["scene:sports:1"],
        ["primary_face_reference"],
    ]
    assert entries[0].image_format == "WEBP"


def test_explicit_selection_preserves_status_and_canon_hash(tmp_path):
    face = _write(tmp_path, "face.png", _PNG)
    snap = _snapshot(
        "KIRA",
        [CanonReference(key="primary_face_reference", path=face)],
        status="APPROVED_AS_TEST",
    )
    bundle = build_reference_bundle(
        [snap],
        characters_in_frame=["KIRA"],
        canon_root=tmp_path,
        reference_keys_by_character={"KIRA": ("primary_face_reference",)},
    )
    group = bundle.character_groups[0]
    assert group.status == "APPROVED_AS_TEST"
    assert group.canon_content_hash == "canon_hash_kira"
    assert not hasattr(bundle, "production_eligible")


# ---------------------------------------------------------------------------
# Real KIRA+SERGEY proof + RC3 offline shadow (Stage 7 / Stage 8)
# ---------------------------------------------------------------------------


def _canon_root_or_skip():
    root = os.environ.get("VNE_CHARACTER_CANON_ROOT")
    if not root:
        pytest.skip("VNE_CHARACTER_CANON_ROOT not set; real NCC proof skipped")
    path = Path(root)
    if not (path / "AI_CHARACTERS").exists():
        pytest.skip(f"canon root missing AI_CHARACTERS: {root}")
    return path


def _load_real_bundle():
    canon_root = _canon_root_or_skip()
    kira = read_character_canon(canon_root, "KIRA", usage_context="authoring")
    sergey = read_character_canon(canon_root, "SERGEY", usage_context="authoring")
    assert kira.status == "APPROVED_AS_CANON"
    assert sergey.status == "APPROVED_AS_TEST"
    bundle = build_reference_bundle(
        [kira, sergey],
        characters_in_frame=["KIRA", "SERGEY"],
        canon_root=canon_root,
        reference_keys_by_character={
            "KIRA": _RC5_KIRA_KEYS,
            "SERGEY": _RC5_SERGEY_KEYS,
        },
    )
    return canon_root, bundle


class _FakeResponse:
    def __init__(self, raw):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._raw


def _b64_response(payload=_PNG):
    return json.dumps(
        {"data": [{"b64_json": base64.b64encode(payload).decode("ascii")}]}
    ).encode("utf-8")


def _patch_transport(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider._get_ssl_context",
        lambda: None,
    )

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request)
        return _FakeResponse(_b64_response())

    monkeypatch.setattr(
        "services.character_visual_conditioning.provider.urllib.request.urlopen",
        fake_urlopen,
    )
    return calls


def _parse_map(refmap):
    lines = refmap.split("\n")
    assert lines[0] == "[REFERENCE MAP]"
    blocks = {}
    current = None
    for line in lines[1:]:
        if line.startswith("image["):
            current = line.rstrip(":")
            blocks[current] = {}
        elif line == "":
            continue
        elif "=" in line:
            key, value = line.split("=", 1)
            blocks[current][key] = value
    return blocks


def test_real_kira_sergey_bounded_selection_offline_proof():
    _, bundle = _load_real_bundle()
    assert [g.character_id for g in bundle.character_groups] == ["KIRA", "SERGEY"]

    kira_group = bundle.character_groups[0]
    sergey_group = bundle.character_groups[1]
    assert len(kira_group.references) == 4
    assert len(sergey_group.references) == 3

    kira_entries = kira_group.references
    assert [tuple(e.roles) for e in kira_entries] == [
        ("primary_face_reference", "face_canon"),
        ("body_canon_a",),
        ("scene:sports:0",),
        ("scene:sports:1",),
    ]
    sergey_entries = sergey_group.references
    assert [tuple(e.roles) for e in sergey_entries] == [
        ("primary_face_reference",),
        ("body_canon_a",),
        ("scene:sports:4",),
    ]

    total_bytes = 0
    for group in bundle.character_groups:
        for entry in group.references:
            assert entry.payload  # non-empty
            assert entry.byte_length == len(entry.payload)
            assert entry.sha256 == hashlib.sha256(entry.payload).hexdigest()
            assert entry.image_format in ("PNG", "JPEG", "WEBP")
            assert entry.content_type in ("image/png", "image/jpeg", "image/webp")
            total_bytes += entry.byte_length

    assert total_bytes > 0
    validate_reference_bundle_integrity(bundle)


def test_real_kira_sergey_rc3_offline_shadow(monkeypatch):
    _, bundle = _load_real_bundle()

    # Offline request-construction path (no HTTP): 7 ordered inputs.
    inputs = reference_inputs_from_bundle(bundle)
    assert len(inputs) == 7
    assert [i.filename for i in inputs] == [
        "ref_000_KIRA.png",
        "ref_001_KIRA.png",
        "ref_002_KIRA.png",
        "ref_003_KIRA.png",
        "ref_004_SERGEY.jpg",
        "ref_005_SERGEY.png",
        "ref_006_SERGEY.png",
    ]
    flat_entries = [e for g in bundle.character_groups for e in g.references]
    assert [i.payload for i in inputs] == [e.payload for e in flat_entries]

    # Reference map is complete and ownership/roles/source are correct.
    refmap = build_reference_map(bundle)
    blocks = _parse_map(refmap)
    assert len(blocks) == 7
    kira_blocks = [m for m in blocks.values() if m["character_id"] == "KIRA"]
    sergey_blocks = [m for m in blocks.values() if m["character_id"] == "SERGEY"]
    assert len(kira_blocks) == 4
    assert len(sergey_blocks) == 3
    for idx, entry in enumerate(flat_entries):
        meta = blocks[f"image[{idx}]"]
        assert meta["character_id"] == entry.character_id
        assert meta["roles"] == ",".join(entry.roles)
        assert meta["source"] == entry.path

    # Transport intercepted: exactly 7 image[] parts, one call, no real HTTP.
    calls = _patch_transport(monkeypatch)
    generate_conditioned_image_from_bundle(
        prompt="KIRA and SERGEY in the gym.",
        reference_bundle=bundle,
        model="gpt-image-2",
        api_key="sk-test",
        base_url="https://api.example.invalid",
    )
    assert len(calls) == 1
    assert calls[0].data.count(b'name="image[]"') == 7
