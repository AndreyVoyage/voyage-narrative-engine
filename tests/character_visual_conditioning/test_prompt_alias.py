#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for ReferenceBundle prompt_alias propagation (SVA-PA v0).

Provider-facing character aliases flow through the provider-neutral bundle and
into the RC3 reference map + multipart filenames WITHOUT mutating the internal
stable ``character_id``. Fully offline and hermetic:

    NETWORK_CALLS = 0
    PROVIDER_CALLS = 0
    IMAGE_GENERATION = 0
    REAL_IMPORTS = 0
    NCC_READS = 0
    NCC_WRITES = 0
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
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ReferenceCharacterGroup,
    ReferenceSelectionError,
    build_reference_bundle,
    build_reference_bundle_from_library,
    build_reference_map,
    compute_content_hash,
    reference_inputs_from_bundle,
)
from services.reference_library import ReferenceRecord  # noqa: E402

_PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 32
_JPEG = b"\xff\xd8\xff" + b"B" * 32

_FMT_EXT = {"PNG": "png", "JPEG": "jpg"}

# Frozen Canon baseline (unchanged by prompt_alias).
_CANON_ENTRY_HASH = "b60094e87e9df13c4ca9cc6e4b6f23920bfbab87cbaf301ccd1f1dc368387d8c"
_CANON_GROUP_HASH = "fb27f7c7267e9ad6b956fd7f9e6810c56a9e5f8fce40ac753b7936995a0cc429"
_CANON_BUNDLE_HASH = "27e387468a43ea67b3a31cc7c78865c3a7a5c6177d1d3be11324148bddd01737"

# Frozen no-alias Library baseline (ANDREY_JUNIOR + OLGA, default roles).
_LIBRARY_NO_ALIAS_HASH = "7b86334dd19812d860260c1a1e4ba9e0cbc8327cba56686883ebbd4d52f5b5db"
_NO_ALIAS_MAP = (
    "[REFERENCE MAP]\n"
    "image[0]:\n"
    "character_id=ANDREY_JUNIOR\n"
    "roles=reference\n"
    "source=authoring/reference_library/assets/characters/ANDREY_JUNIOR/aj_face_01.png\n"
    "\n"
    "image[1]:\n"
    "character_id=OLGA\n"
    "roles=reference\n"
    "source=authoring/reference_library/assets/characters/OLGA/olga_body_01.jpg"
)
_NO_ALIAS_FILENAMES = ["ref_000_ANDREY_JUNIOR.png", "ref_001_OLGA.jpg"]


def _detect(payload):
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if payload.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    raise AssertionError("unsupported test payload")


def _default_rel(character_id, asset_id, payload):
    ext = _FMT_EXT[_detect(payload)]
    return (
        f"authoring/reference_library/assets/characters/"
        f"{character_id}/{asset_id}.{ext}"
    )


def _library_record(character_id, asset_id, *, payload):
    rel = _default_rel(character_id, asset_id, payload)
    fmt = _detect(payload)
    return ReferenceRecord(
        asset_id=asset_id,
        character_id=character_id,
        relative_path=rel,
        filename=f"{asset_id}.{_FMT_EXT[fmt]}",
        sha256=hashlib.sha256(payload).hexdigest(),
        file_type=fmt,
    )


def _write_asset(tmp_path, character_id, asset_id, payload):
    rel = _default_rel(character_id, asset_id, payload)
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(payload)
    return rel


def _build_library(tmp_path, selected, frame, prompt_alias_by_character=None):
    return build_reference_bundle_from_library(
        selected,
        characters_in_frame=frame,
        repo_root=tmp_path,
        prompt_alias_by_character=prompt_alias_by_character,
    )


def _two_char_bundle(tmp_path, aliases=None):
    """Deterministic ANDREY_JUNIOR + OLGA Library bundle (no-alias by default)."""
    _write_asset(tmp_path, "ANDREY_JUNIOR", "aj_face_01", _PNG)
    _write_asset(tmp_path, "OLGA", "olga_body_01", _JPEG)
    selected = {
        "ANDREY_JUNIOR": [_library_record("ANDREY_JUNIOR", "aj_face_01", payload=_PNG)],
        "OLGA": [_library_record("OLGA", "olga_body_01", payload=_JPEG)],
    }
    return _build_library(
        tmp_path, selected, ["ANDREY_JUNIOR", "OLGA"],
        prompt_alias_by_character=aliases,
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
# Model: prompt_alias field semantics
# ---------------------------------------------------------------------------


def test_group_prompt_alias_defaults_none():
    group = ReferenceCharacterGroup(character_id="C", references=())
    assert group.prompt_alias is None


def test_none_alias_omitted_from_semantic_payload():
    group = ReferenceCharacterGroup(character_id="C", references=())
    assert "prompt_alias" not in group.semantic_payload()


def test_none_alias_omitted_from_to_dict():
    group = ReferenceCharacterGroup(character_id="C", references=())
    assert "prompt_alias" not in group.to_dict()


def test_non_empty_alias_accepted():
    group = ReferenceCharacterGroup(character_id="C", references=(), prompt_alias="Andrey")
    assert group.prompt_alias == "Andrey"
    assert group.semantic_payload()["prompt_alias"] == "Andrey"


def test_empty_alias_rejected():
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), prompt_alias="")


def test_whitespace_only_alias_rejected():
    with pytest.raises(ValueError):
        ReferenceCharacterGroup(character_id="C", references=(), prompt_alias="   ")


def test_alias_changes_library_bundle_semantic_hash(tmp_path):
    plain = _two_char_bundle(tmp_path)
    aliased = _two_char_bundle(tmp_path, {"ANDREY_JUNIOR": "Andrey", "OLGA": "Olga"})
    assert plain.content_hash != aliased.content_hash
    assert compute_content_hash(plain.semantic_payload()) != compute_content_hash(
        aliased.semantic_payload()
    )


def test_alias_mapping_reaches_correct_group(tmp_path):
    bundle = _two_char_bundle(tmp_path, {"ANDREY_JUNIOR": "Andrey", "OLGA": "Olga"})
    by_id = {g.character_id: g for g in bundle.character_groups}
    assert by_id["ANDREY_JUNIOR"].prompt_alias == "Andrey"
    assert by_id["OLGA"].prompt_alias == "Olga"


def test_unknown_alias_map_character_rejected(tmp_path):
    with pytest.raises(ReferenceSelectionError):
        _two_char_bundle(tmp_path, {"UNKNOWN": "X"})


def test_partial_alias_mapping_allowed(tmp_path):
    bundle = _two_char_bundle(tmp_path, {"ANDREY_JUNIOR": "Andrey"})
    by_id = {g.character_id: g for g in bundle.character_groups}
    assert by_id["ANDREY_JUNIOR"].prompt_alias == "Andrey"
    assert by_id["OLGA"].prompt_alias is None


def test_duplicate_effective_aliases_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_B", "b1", _PNG)
    selected = {
        "CHAR_A": [_library_record("CHAR_A", "a1", payload=_PNG)],
        "CHAR_B": [_library_record("CHAR_B", "b1", payload=_PNG)],
    }
    with pytest.raises(ReferenceSelectionError):
        _build_library(
            tmp_path, selected, ["CHAR_A", "CHAR_B"],
            prompt_alias_by_character={"CHAR_A": "Alex", "CHAR_B": "Alex"},
        )


def test_alias_equal_to_other_unaliased_character_id_rejected(tmp_path):
    _write_asset(tmp_path, "CHAR_A", "a1", _PNG)
    _write_asset(tmp_path, "CHAR_B", "b1", _PNG)
    selected = {
        "CHAR_A": [_library_record("CHAR_A", "a1", payload=_PNG)],
        "CHAR_B": [_library_record("CHAR_B", "b1", payload=_PNG)],
    }
    # CHAR_A aliases to CHAR_B while CHAR_B stays unaliased -> duplicate label.
    with pytest.raises(ReferenceSelectionError):
        _build_library(
            tmp_path, selected, ["CHAR_A", "CHAR_B"],
            prompt_alias_by_character={"CHAR_A": "CHAR_B"},
        )


def test_canon_builder_leaves_prompt_alias_none(tmp_path):
    _write_canon_assets(tmp_path)
    bundle = build_reference_bundle(
        [_canon_snapshot()], characters_in_frame=["BASELINE_CANON_CHAR"], canon_root=tmp_path
    )
    assert bundle.character_groups[0].prompt_alias is None


def test_canon_frozen_hashes_unchanged(tmp_path):
    _write_canon_assets(tmp_path)
    bundle = build_reference_bundle(
        [_canon_snapshot()], characters_in_frame=["BASELINE_CANON_CHAR"], canon_root=tmp_path
    )
    group = bundle.character_groups[0]
    entry = group.references[0]
    assert compute_content_hash(entry.semantic_payload()) == _CANON_ENTRY_HASH
    assert compute_content_hash(group.semantic_payload()) == _CANON_GROUP_HASH
    assert bundle.content_hash == _CANON_BUNDLE_HASH


# ---------------------------------------------------------------------------
# No-alias freeze: Library behavior remains byte-for-byte unchanged
# ---------------------------------------------------------------------------


def test_no_alias_library_hash_unchanged(tmp_path):
    bundle = _two_char_bundle(tmp_path)
    assert bundle.content_hash == _LIBRARY_NO_ALIAS_HASH


def test_no_alias_provider_map_unchanged(tmp_path):
    bundle = _two_char_bundle(tmp_path)
    assert build_reference_map(bundle) == _NO_ALIAS_MAP


def test_no_alias_multipart_filenames_unchanged(tmp_path):
    bundle = _two_char_bundle(tmp_path)
    assert [i.filename for i in reference_inputs_from_bundle(bundle)] == _NO_ALIAS_FILENAMES


# ---------------------------------------------------------------------------
# Aliased provider-facing map + multipart filenames
# ---------------------------------------------------------------------------


def _aliased_two_char_bundle(tmp_path):
    return _two_char_bundle(tmp_path, {"ANDREY_JUNIOR": "Andrey", "OLGA": "Olga"})


def test_aliased_provider_map_contains_andrey_and_olga(tmp_path):
    refmap = build_reference_map(_aliased_two_char_bundle(tmp_path))
    assert "Andrey" in refmap
    assert "Olga" in refmap


def test_aliased_provider_map_does_not_contain_raw_internal_ids(tmp_path):
    refmap = build_reference_map(_aliased_two_char_bundle(tmp_path))
    assert "ANDREY_JUNIOR" not in refmap
    assert "OLGA" not in refmap
    assert "andrey_junior" not in refmap.lower()


def test_aliased_source_label_uses_safe_attachment_filename(tmp_path):
    """An asset_id embedding the raw internal id must not leak via ``source=``."""
    _write_asset(tmp_path, "ANDREY_JUNIOR", "andrey_junior_face_01", _PNG)
    selected = {
        "ANDREY_JUNIOR": [
            _library_record("ANDREY_JUNIOR", "andrey_junior_face_01", payload=_PNG)
        ],
    }
    bundle = _build_library(
        tmp_path,
        selected,
        ["ANDREY_JUNIOR"],
        prompt_alias_by_character={"ANDREY_JUNIOR": "Andrey"},
    )
    refmap = build_reference_map(bundle)
    # Provider-facing source label is the safe multipart filename, not the
    # raw asset basename.
    assert "source=ref_000_Andrey.png" in refmap
    assert "andrey_junior_face_01" not in refmap
    assert "andrey_junior" not in refmap.lower()
    assert "ANDREY_JUNIOR" not in refmap
    # Internal identity/ownership remain unchanged.
    group = bundle.character_groups[0]
    assert group.character_id == "ANDREY_JUNIOR"
    assert group.references[0].source_asset_id == "andrey_junior_face_01"


def test_aliased_multipart_filename_contains_sanitized_andrey(tmp_path):
    filenames = [i.filename for i in reference_inputs_from_bundle(_aliased_two_char_bundle(tmp_path))]
    assert "Andrey" in filenames[0]
    assert "andrey" in filenames[0].lower()


def test_aliased_multipart_filename_does_not_contain_andrey_junior(tmp_path):
    filenames = [i.filename for i in reference_inputs_from_bundle(_aliased_two_char_bundle(tmp_path))]
    assert "andrey_junior" not in filenames[0].lower()
    assert "ANDREY_JUNIOR" not in filenames[0]


def test_payload_bytes_unchanged_by_alias(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    entry = bundle.character_groups[0].references[0]
    assert entry.payload == _PNG


def test_attachment_count_unchanged(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    assert len(reference_inputs_from_bundle(bundle)) == 2


def test_attachment_order_unchanged(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    filenames = [i.filename for i in reference_inputs_from_bundle(bundle)]
    assert filenames == ["ref_000_Andrey.png", "ref_001_Olga.jpg"]


def test_two_aliases_produce_deterministic_mapping(tmp_path):
    m1 = build_reference_map(_aliased_two_char_bundle(tmp_path))
    m2 = build_reference_map(_aliased_two_char_bundle(tmp_path))
    assert m1 == m2


def test_internal_character_id_remains_andrey_junior(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    by_id = {g.character_id: g for g in bundle.character_groups}
    assert "ANDREY_JUNIOR" in by_id
    assert by_id["ANDREY_JUNIOR"].prompt_alias == "Andrey"


def test_internal_olga_character_id_remains_olga(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    by_id = {g.character_id: g for g in bundle.character_groups}
    assert "OLGA" in by_id
    assert by_id["OLGA"].prompt_alias == "Olga"


def test_reference_bundle_schema_remains_reference_bundle_0_1(tmp_path):
    bundle = _aliased_two_char_bundle(tmp_path)
    assert bundle.schema_version == REFERENCE_BUNDLE_SCHEMA_VERSION
    assert REFERENCE_BUNDLE_SCHEMA_VERSION == "reference_bundle/0.1"
