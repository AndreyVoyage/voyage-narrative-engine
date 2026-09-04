#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the scene-aware reference selector (SARS v0)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.reference_selector as rs  # noqa: E402
from tools.reference_selector import (  # noqa: E402
    CATALOG_SCHEMA_VERSION,
    ROLE_BODY,
    ROLE_EXPRESSION,
    ROLE_FACE,
    ROLE_MOTION,
    CatalogEntry,
    CatalogError,
    SelectionError,
    load_semantic_catalog,
    select_references,
)
from services.reference_library import ReferenceRecord  # noqa: E402


def _sha(tag: str) -> str:
    return hashlib.sha256(tag.encode("utf-8")).hexdigest()


def _rec(asset_id: str, character_id: str, sha256: str | None = None) -> ReferenceRecord:
    return ReferenceRecord(
        asset_id=asset_id,
        character_id=character_id,
        relative_path=(
            f"authoring/reference_library/assets/characters/{character_id}/{asset_id}.png"
        ),
        filename=f"{asset_id}.png",
        sha256=sha256 or _sha(asset_id),
        file_type="PNG",
    )


def _entry(asset_id, character_id, roles, tags=(), priority=10, key=None) -> CatalogEntry:
    return CatalogEntry(
        asset_id=asset_id,
        character_id=character_id,
        semantic_roles=tuple(roles),
        scene_tags=tuple(tags),
        priority=priority,
        source_semantic_key=key,
    )


def _write_catalog(tmp_path, entries) -> Path:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {"schema_version": CATALOG_SCHEMA_VERSION, "entries": entries}
        ),
        encoding="utf-8",
    )
    return path


def _cat_dict(asset_id, character_id, roles, tags=(), priority=10, key=None):
    data = {
        "asset_id": asset_id,
        "character_id": character_id,
        "semantic_roles": list(roles),
        "scene_tags": list(tags),
        "priority": priority,
    }
    if key is not None:
        data["source_semantic_key"] = key
    return data


# ---------------------------------------------------------------------------
# Catalog integrity (items 1-6)
# ---------------------------------------------------------------------------


def test_valid_sparse_catalog_loads(tmp_path):
    records = [_rec("a_face", "A"), _rec("a_body", "A"), _rec("orphan", "A")]
    path = _write_catalog(
        tmp_path,
        [
            _cat_dict("a_face", "A", ["face", "identity"]),
            _cat_dict("a_body", "A", ["body", "identity"]),
        ],
    )
    catalog = load_semantic_catalog(path, records)
    assert {e.asset_id for e in catalog} == {"a_face", "a_body"}
    # "orphan" is in the manifest but not the catalog -> simply not eligible.
    assert "orphan" not in {e.asset_id for e in catalog}


def test_duplicate_asset_id_fails(tmp_path):
    records = [_rec("a_face", "A")]
    path = _write_catalog(
        tmp_path,
        [
            _cat_dict("a_face", "A", ["face"]),
            _cat_dict("a_face", "A", ["face"]),
        ],
    )
    with pytest.raises(CatalogError):
        load_semantic_catalog(path, records)


def test_missing_manifest_target_fails(tmp_path):
    records = [_rec("a_face", "A")]
    path = _write_catalog(tmp_path, [_cat_dict("not_in_manifest", "A", ["face"])])
    with pytest.raises(CatalogError):
        load_semantic_catalog(path, records)


def test_ownership_mismatch_fails(tmp_path):
    records = [_rec("a_face", "A")]
    path = _write_catalog(tmp_path, [_cat_dict("a_face", "B", ["face"])])
    with pytest.raises(CatalogError):
        load_semantic_catalog(path, records)


def test_unknown_semantic_role_preserved(tmp_path):
    records = [_rec("a_face", "A")]
    path = _write_catalog(
        tmp_path, [_cat_dict("a_face", "A", ["face", "physique_ref"])]
    )
    catalog = load_semantic_catalog(path, records)
    assert "physique_ref" in catalog[0].semantic_roles


def test_manifest_asset_without_catalog_entry_allowed(tmp_path):
    # Manifest has an extra asset that the catalog does not mention.
    records = [_rec("a_face", "A"), _rec("a_body", "A"), _rec("extra", "A")]
    path = _write_catalog(
        tmp_path,
        [
            _cat_dict("a_face", "A", ["face", "identity"]),
            _cat_dict("a_body", "A", ["body", "identity"]),
        ],
    )
    catalog = load_semantic_catalog(path, records)
    assert len(catalog) == 2


# ---------------------------------------------------------------------------
# Required selection (items 7-11)
# ---------------------------------------------------------------------------


def _select(records, catalog, character_ids=("A",), location_id="gym", scene_tags=()):
    return select_references(character_ids, location_id, scene_tags, records, catalog)


def _face_body_catalog():
    return [
        _entry("a_face", "A", ["face", "identity"]),
        _entry("a_body", "A", ["body", "identity"]),
    ]


def test_face_and_body_selected():
    records = [_rec("a_face", "A"), _rec("a_body", "A")]
    selected, roles = _select(records, _face_body_catalog())
    assert [r.asset_id for r in selected["A"]] == ["a_face", "a_body"]
    assert roles == {"a_face": ("face",), "a_body": ("body",)}


def test_no_face_fails():
    records = [_rec("a_body", "A")]
    catalog = [_entry("a_body", "A", ["body", "identity"])]
    with pytest.raises(SelectionError):
        _select(records, catalog)


def test_no_body_fails():
    records = [_rec("a_face", "A")]
    catalog = [_entry("a_face", "A", ["face", "identity"])]
    with pytest.raises(SelectionError):
        _select(records, catalog)


def test_character_with_zero_eligible_records_fails():
    records = [_rec("a_face", "A"), _rec("a_body", "A")]
    catalog = _face_body_catalog()
    with pytest.raises(SelectionError):
        _select(records, catalog, character_ids=("Z",))


# ---------------------------------------------------------------------------
# Determinism (items 12-15)
# ---------------------------------------------------------------------------


def test_priority_wins():
    records = [_rec("f_low", "A"), _rec("f_high", "A"), _rec("a_body", "A")]
    catalog = [
        _entry("f_low", "A", ["face", "identity"], priority=10),
        _entry("f_high", "A", ["face", "identity"], priority=50),
        _entry("a_body", "A", ["body", "identity"]),
    ]
    selected, _ = _select(records, catalog)
    assert selected["A"][0].asset_id == "f_low"


def test_identity_tie_preference():
    records = [_rec("f_plain", "A"), _rec("f_id", "A"), _rec("a_body", "A")]
    catalog = [
        _entry("f_plain", "A", ["face"], priority=10),
        _entry("f_id", "A", ["face", "identity"], priority=10),
        _entry("a_body", "A", ["body", "identity"]),
    ]
    selected, _ = _select(records, catalog)
    assert selected["A"][0].asset_id == "f_id"


def test_lexical_final_tie():
    records = [_rec("f_b", "A"), _rec("f_a", "A"), _rec("a_body", "A")]
    catalog = [
        _entry("f_b", "A", ["face"], priority=10),
        _entry("f_a", "A", ["face"], priority=10),
        _entry("a_body", "A", ["body", "identity"]),
    ]
    selected, _ = _select(records, catalog)
    assert selected["A"][0].asset_id == "f_a"


def test_result_stable_across_input_ordering():
    records = [
        _rec("f_a", "A"), _rec("f_b", "A"), _rec("f_expr", "A"),
        _rec("a_body", "A"), _rec("motion", "A"),
    ]
    catalog = [
        _entry("f_a", "A", ["face"], priority=10),
        _entry("f_b", "A", ["face"], priority=10),
        _entry("f_expr", "A", ["face", "expression"], priority=20),
        _entry("a_body", "A", ["body", "identity"], priority=10),
        _entry("motion", "A", ["motion"], tags=("gym",), priority=20),
    ]
    s1, _ = _select(records, catalog)
    s2, _ = _select(list(reversed(records)), list(reversed(catalog)))
    assert [r.asset_id for r in s1["A"]] == [r.asset_id for r in s2["A"]]


# ---------------------------------------------------------------------------
# Optional support (items 16-18)
# ---------------------------------------------------------------------------


def test_expression_preferred_for_face_support():
    records = [_rec("f", "A"), _rec("f_expr", "A"), _rec("f_plain", "A"), _rec("b", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"], priority=10),
        _entry("f_expr", "A", ["face", "expression"], priority=30),
        _entry("f_plain", "A", ["face"], priority=20),
        _entry("b", "A", ["body", "identity"]),
    ]
    selected, roles = _select(records, catalog)
    ids = [r.asset_id for r in selected["A"]]
    assert ids == ["f", "b", "f_expr"]
    assert roles["f_expr"] == ("expression",)


def test_no_face_support_proceeds():
    records = [_rec("f", "A"), _rec("b", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"]),
        _entry("b", "A", ["body", "identity"]),
    ]
    selected, _ = _select(records, catalog)
    assert [r.asset_id for r in selected["A"]] == ["f", "b"]


def test_no_scene_support_proceeds():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("f_expr", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"]),
        _entry("b", "A", ["body", "identity"]),
        _entry("f_expr", "A", ["face", "expression"]),
    ]
    selected, _ = _select(records, catalog)
    assert [r.asset_id for r in selected["A"]] == ["f", "b", "f_expr"]


# ---------------------------------------------------------------------------
# Scene tags (items 19-22)
# ---------------------------------------------------------------------------


def _motion_catalog(motion_tags):
    return [
        _entry("f", "A", ["face", "identity"]),
        _entry("b", "A", ["body", "identity"]),
        _entry("m", "A", ["motion"], tags=motion_tags, priority=20),
    ]


def test_location_id_participates():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("m", "A")]
    catalog = _motion_catalog(("gym", "neutral"))
    selected, _ = _select(records, catalog, location_id="gym", scene_tags=())
    assert "m" in [r.asset_id for r in selected["A"]]


def test_explicit_scene_tags_participate():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("m", "A")]
    catalog = _motion_catalog(("stretching",))
    selected, _ = _select(records, catalog, location_id="other", scene_tags=("stretching",))
    assert "m" in [r.asset_id for r in selected["A"]]


def test_no_prose_parsing():
    # Selector only uses location_id + scene_tags; a "pool" motion is not pulled
    # in for a gym scene even though nothing else matches.
    records = [_rec("f", "A"), _rec("b", "A"), _rec("m", "A")]
    catalog = _motion_catalog(("pool", "sunset"))
    selected, _ = _select(records, catalog, location_id="gym", scene_tags=("neutral", "stretching"))
    assert [r.asset_id for r in selected["A"]] == ["f", "b"]


def test_tag_intersection_controls_motion():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("m_gym", "A"), _rec("m_pool", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"]),
        _entry("b", "A", ["body", "identity"]),
        _entry("m_gym", "A", ["motion"], tags=("gym", "neutral"), priority=20),
        _entry("m_pool", "A", ["motion"], tags=("pool", "sunset"), priority=20),
    ]
    selected, _ = _select(records, catalog, location_id="gym", scene_tags=("neutral", "stretching"))
    ids = [r.asset_id for r in selected["A"]]
    assert "m_gym" in ids
    assert "m_pool" not in ids


# ---------------------------------------------------------------------------
# MARINA / MAKSIM exact selection (items 23-27)
# ---------------------------------------------------------------------------


def _marina_records():
    return [
        _rec("marina_face_01", "MARINA"),
        _rec("marina_face_support_01", "MARINA"),
        _rec("marina_body_01", "MARINA"),
        _rec("marina_sports_01", "MARINA"),
    ]


def _marina_catalog():
    return [
        _entry("marina_face_01", "MARINA", ["face", "identity"], priority=10),
        _entry("marina_face_support_01", "MARINA", ["face", "expression"], priority=20),
        _entry("marina_body_01", "MARINA", ["body", "identity"], priority=10),
        _entry("marina_sports_01", "MARINA", ["scene_support"], tags=("pool", "sunset"), priority=20),
    ]


def _maksim_records():
    return [
        _rec("maksim_face_01", "MAKSIM"),
        _rec("maksim_face_support_01", "MAKSIM"),
        _rec("maksim_body_01", "MAKSIM"),
        _rec("maksim_gym_01", "MAKSIM"),
    ]


def _maksim_catalog():
    return [
        _entry("maksim_face_01", "MAKSIM", ["face", "identity"], priority=10),
        _entry("maksim_face_support_01", "MAKSIM", ["face", "expression"], priority=20),
        _entry("maksim_body_01", "MAKSIM", ["body", "identity"], priority=10),
        _entry("maksim_gym_01", "MAKSIM", ["motion", "body_support"], tags=("gym", "neutral", "motion"), priority=20),
    ]


def test_marina_pool_asset_excluded_from_gym():
    selected, _ = select_references(
        ("MARINA",), "gym", ("neutral", "stretching"), _marina_records(), _marina_catalog()
    )
    ids = [r.asset_id for r in selected["MARINA"]]
    assert "marina_sports_01" not in ids


def test_marina_no_fallback_to_pool():
    selected, _ = select_references(
        ("MARINA",), "gym", ("neutral", "stretching"), _marina_records(), _marina_catalog()
    )
    assert [r.asset_id for r in selected["MARINA"]] == [
        "marina_face_01", "marina_body_01", "marina_face_support_01",
    ]


def test_marina_exact_result():
    selected, roles = select_references(
        ("MARINA",), "gym", ("neutral", "stretching"), _marina_records(), _marina_catalog()
    )
    assert [r.asset_id for r in selected["MARINA"]] == [
        "marina_face_01", "marina_body_01", "marina_face_support_01",
    ]
    assert roles == {
        "marina_face_01": ("face",),
        "marina_body_01": ("body",),
        "marina_face_support_01": ("expression",),
    }


def test_maksim_natural_motion_selected_in_gym():
    selected, _ = select_references(
        ("MAKSIM",), "gym", ("neutral", "stretching"), _maksim_records(), _maksim_catalog()
    )
    ids = [r.asset_id for r in selected["MAKSIM"]]
    assert "maksim_gym_01" in ids


def test_maksim_exact_result():
    selected, _ = select_references(
        ("MAKSIM",), "gym", ("neutral", "stretching"), _maksim_records(), _maksim_catalog()
    )
    assert [r.asset_id for r in selected["MAKSIM"]] == [
        "maksim_face_01", "maksim_body_01", "maksim_face_support_01", "maksim_gym_01",
    ]


# ---------------------------------------------------------------------------
# Stage / SHA / multi-role (items 28-31)
# ---------------------------------------------------------------------------


def test_stage_candidate_not_selected_for_gym():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("stage", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"]),
        _entry("b", "A", ["body", "identity"]),
        _entry("stage", "A", ["motion", "physique"], tags=("stage", "competition"), priority=20),
    ]
    selected, _ = select_references(("A",), "gym", ("neutral",), records, catalog)
    assert "stage" not in [r.asset_id for r in selected["A"]]


def test_duplicate_sha_not_attached_twice():
    shared = _sha("shared-bytes")
    records = [
        _rec("f", "A", sha256=shared),
        _rec("f2", "A", sha256=shared),
        _rec("b", "A"),
    ]
    catalog = [
        _entry("f", "A", ["face", "identity"], priority=10),
        _entry("f2", "A", ["face"], priority=20),
        _entry("b", "A", ["body", "identity"]),
    ]
    selected, _ = select_references(("A",), "gym", (), records, catalog)
    ids = [r.asset_id for r in selected["A"]]
    # f2 shares the same SHA as f -> skipped; only one face is attached.
    assert ids == ["f", "b"]


def test_same_asset_does_not_count_twice():
    records = [_rec("combo", "A"), _rec("b_other", "A")]
    catalog = [
        _entry("combo", "A", ["face", "body", "identity"], priority=10),
        _entry("b_other", "A", ["body", "identity"], priority=20),
    ]
    selected, roles = select_references(("A",), "gym", (), records, catalog)
    ids = [r.asset_id for r in selected["A"]]
    assert ids.count("combo") == 1
    assert roles["combo"] == ("face",)


def test_role_accumulation_deterministic():
    records = [_rec("f", "A"), _rec("b", "A"), _rec("e", "A"), _rec("m", "A")]
    catalog = [
        _entry("f", "A", ["face", "identity"], priority=10),
        _entry("b", "A", ["body", "identity"], priority=10),
        _entry("e", "A", ["face", "expression"], priority=20),
        _entry("m", "A", ["motion", "body_support"], tags=("gym",), priority=20),
    ]
    r1, _ = select_references(("A",), "gym", (), records, catalog)
    r2, _ = select_references(("A",), "gym", (), records, catalog)
    assert [x.asset_id for x in r1["A"]] == [x.asset_id for x in r2["A"]]
    assert [x.asset_id for x in r1["A"]] == ["f", "b", "e", "m"]


# ---------------------------------------------------------------------------
# Boundary: selector -> build_reference_bundle_from_library (items 36-37)
# ---------------------------------------------------------------------------


_PNG = b"\x89PNG\r\n\x1a\n"


def test_selector_feeds_build_reference_bundle_from_library(tmp_path):
    from services.character_visual_conditioning import (
        build_reference_bundle_from_library,
        reference_inputs_from_bundle,
        validate_reference_bundle_integrity,
    )

    character = "A"

    def write_rec(asset_id, tag):
        rel = f"authoring/reference_library/assets/characters/{character}/{asset_id}.png"
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        data = _PNG + tag.encode("utf-8")
        full.write_bytes(data)
        return ReferenceRecord(
            asset_id=asset_id,
            character_id=character,
            relative_path=rel,
            filename=f"{asset_id}.png",
            sha256=hashlib.sha256(data).hexdigest(),
            file_type="PNG",
        )

    records = [
        write_rec("a_face", "face"),
        write_rec("a_body", "body"),
        write_rec("a_expr", "expr"),
        write_rec("a_motion", "motion"),
    ]
    catalog = [
        _entry("a_face", character, ["face", "identity"], priority=10),
        _entry("a_body", character, ["body", "identity"], priority=10),
        _entry("a_expr", character, ["face", "expression"], priority=20),
        _entry("a_motion", character, ["motion"], tags=("gym",), priority=20),
    ]
    selected, roles = select_references((character,), "gym", (), records, catalog)

    bundle = build_reference_bundle_from_library(
        selected,
        characters_in_frame=(character,),
        repo_root=tmp_path,
        roles_by_asset_id=roles,
    )
    validate_reference_bundle_integrity(bundle)

    # Attachment order follows selector order: face, body, expression, motion.
    inputs = reference_inputs_from_bundle(bundle)
    assert [i.filename for i in inputs] == [
        "ref_000_A.png", "ref_001_A.png", "ref_002_A.png", "ref_003_A.png",
    ]
    group = bundle.character_groups[0]
    assert [list(e.roles)[0] for e in group.references] == [
        "face", "body", "expression", "motion",
    ]
