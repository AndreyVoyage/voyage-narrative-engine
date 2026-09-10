#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accepted OrderedASS batch v1 tests.

Covers the references-only model, deterministic/strict serialization, atomic
persistence, project membership, canonical ASS resolution, accepted lifecycle
authority, pinning, and downstream exporter integration.
"""

from __future__ import annotations

import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from services.ass import (
    OrderedASSIntegrityError,
    OrderedASSNotFoundError,
    OrderedASSStore,
    build_ordered_ass,
)
from services.scene_body import SceneBody
from services.scene_draft import (
    LIFECYCLE_ACCEPTED,
    AcceptanceLink,
    SceneDraftStore,
    SceneVersionNotFoundError,
    accept_draft,
)
from services.workspace_project import (
    ACCEPTED_BATCH_SCHEMA_VERSION,
    CHARACTER,
    LOCATION,
    MEDIA_ASSET,
    SCENE,
    AcceptedBatchNotFoundError,
    AcceptedBatchResolutionError,
    AcceptedBatchValidationError,
    AcceptedOrderedASSBatch,
    AcceptedOrderedASSRef,
    ProjectEntityRef,
    ProjectManifest,
    load_accepted_batch,
    parse_accepted_batch,
    resolve_accepted_ordered_ass_batch,
    save_accepted_batch,
    serialize_accepted_batch,
    validate_accepted_batch,
)
from tests.scene_draft.conftest import make_body

SCENE_ID_A = "SC_900"
SCENE_ID_B = "SC_901"
PROJECT_ID = "demo_project"
MANIFEST_SCHEMA = "vne_workspace_project_manifest/0.1"


def _ref(scene_id=SCENE_ID_A, version=1, ass_id="ass_sc900_1", ass_content_hash=None):
    return AcceptedOrderedASSRef(
        scene_id=scene_id,
        version=version,
        ass_id=ass_id,
        ass_content_hash=ass_content_hash if ass_content_hash is not None else "0" * 64,
    )


def _batch(project_id=PROJECT_ID, refs=None):
    return AcceptedOrderedASSBatch(
        schema_version=ACCEPTED_BATCH_SCHEMA_VERSION,
        project_id=project_id,
        scene_refs=tuple(refs) if refs is not None else (_ref(),),
    )


def _manifest(project_id=PROJECT_ID, entities=None):
    return ProjectManifest(
        schema_version=MANIFEST_SCHEMA,
        project_id=project_id,
        entities=tuple(entities) if entities is not None else (
            ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_A, source_ref="scenes/SC_900.json"),
        ),
    )


def _raw_batch(**overrides):
    base = {
        "schema_version": ACCEPTED_BATCH_SCHEMA_VERSION,
        "project_id": PROJECT_ID,
        "scene_refs": [
            {"scene_id": SCENE_ID_A, "version": 1, "ass_id": "ass_a", "ass_content_hash": "0" * 64}
        ],
    }
    base.update(overrides)
    return base


def _raw_text(d):
    return json.dumps(d).encode("utf-8")


@pytest.fixture
def ass_store(tmp_path: Path) -> OrderedASSStore:
    return OrderedASSStore(tmp_path / "canonical_ass")


@pytest.fixture
def scene_store(tmp_path: Path) -> SceneDraftStore:
    return SceneDraftStore(tmp_path / "scene_draft")


def _accept_v1(scene_store, ass_store, scene_id=SCENE_ID_A, ass_id="ass_sc900_1"):
    """Create and accept version 1 of a scene; returns (SceneVersion, OrderedASS)."""
    scene_store.create_initial_draft(scene_id, make_body(scene_id=scene_id))
    updated, ass = accept_draft(
        scene_store, scene_id, 1,
        ass_store=ass_store, ass_id=ass_id, source_ref=f"scenes/{scene_id}.json",
    )
    return updated, ass


def _ref_for(ass):
    return _ref(scene_id=ass.scene_id, version=ass.version, ass_id=ass.ass_id, ass_content_hash=ass.content_hash)


def _resolve(batch, project_manifest, ass_store, scene_store):
    return resolve_accepted_ordered_ass_batch(
        batch, project_manifest=project_manifest, ass_store=ass_store, scene_draft_store=scene_store,
    )


# ---------------------------------------------------------------------------
# Model / serialization
# ---------------------------------------------------------------------------


def test_valid_references_only_batch():
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A), _ref(scene_id=SCENE_ID_B, ass_id="ass_b")))
    assert batch.schema_version == ACCEPTED_BATCH_SCHEMA_VERSION
    assert batch.project_id == PROJECT_ID
    assert [r.scene_id for r in batch.scene_refs] == [SCENE_ID_A, SCENE_ID_B]


def test_batch_is_frozen():
    batch = _batch()
    with pytest.raises(FrozenInstanceError):
        batch.project_id = "other"


def test_ref_is_frozen():
    ref = _ref()
    with pytest.raises(FrozenInstanceError):
        ref.scene_id = "other"


def test_scene_refs_tuple_is_immutable():
    batch = _batch()
    with pytest.raises(AttributeError):
        batch.scene_refs.append(_ref())


def test_strict_round_trip():
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A), _ref(scene_id=SCENE_ID_B, ass_id="ass_b")))
    parsed = parse_accepted_batch(serialize_accepted_batch(batch))
    assert parsed == batch
    assert parsed.to_dict() == batch.to_dict()


def test_deterministic_serialization():
    batch = _batch()
    assert serialize_accepted_batch(batch) == serialize_accepted_batch(batch)


def test_serialization_preserves_utf8():
    ref = AcceptedOrderedASSRef(scene_id="сцена_900", version=1, ass_id="ass_a", ass_content_hash="0" * 64)
    batch = _batch(refs=(ref,))
    data = serialize_accepted_batch(batch)
    assert isinstance(data, bytes)
    assert "сцена_900" in data.decode("utf-8")


def test_serialization_is_lf_only():
    data = serialize_accepted_batch(_batch())
    assert b"\r\n" not in data
    assert b"\r" not in data
    assert b"\n" in data


def test_serialization_has_exactly_one_final_newline():
    data = serialize_accepted_batch(_batch())
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n")


def test_refs_serialized_ascending_despite_shuffled_input():
    r_b = _ref(scene_id=SCENE_ID_B, ass_id="ass_b")
    r_a = _ref(scene_id=SCENE_ID_A, ass_id="ass_a")
    batch = _batch(refs=(r_b, r_a))
    assert [r["scene_id"] for r in batch.to_dict()["scene_refs"]] == [SCENE_ID_A, SCENE_ID_B]
    assert [r.scene_id for r in batch.scene_refs] == [SCENE_ID_A, SCENE_ID_B]


def test_wrong_schema_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        parse_accepted_batch(_raw_text(_raw_batch(schema_version="wrong/0.0")))


def test_unknown_top_level_field_rejected():
    d = _raw_batch()
    d["batch_id"] = "xyz"
    with pytest.raises(AcceptedBatchValidationError):
        parse_accepted_batch(_raw_text(d))


def test_unknown_ref_field_rejected():
    d = _raw_batch()
    d["scene_refs"][0]["source_ref"] = "x.json"
    with pytest.raises(AcceptedBatchValidationError):
        parse_accepted_batch(_raw_text(d))


def test_ordered_ass_body_field_in_ref_rejected():
    for field in ("ordered_flow", "location_id", "participants", "content_rating"):
        d = _raw_batch()
        d["scene_refs"][0][field] = []
        with pytest.raises(AcceptedBatchValidationError):
            parse_accepted_batch(_raw_text(d))


def test_empty_batch_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _batch(refs=())


def test_duplicate_scene_id_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _batch(refs=(_ref(scene_id=SCENE_ID_A, ass_id="a"), _ref(scene_id=SCENE_ID_A, ass_id="b")))


def test_duplicate_ass_id_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _batch(refs=(_ref(scene_id=SCENE_ID_A, ass_id="same"), _ref(scene_id=SCENE_ID_B, ass_id="same")))


def test_version_zero_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(version=0)


def test_bool_version_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(version=True)


def test_bool_version_rejected_via_parse():
    d = _raw_batch()
    d["scene_refs"][0]["version"] = True
    with pytest.raises(AcceptedBatchValidationError):
        parse_accepted_batch(_raw_text(d))


def test_malformed_hash_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(ass_content_hash="not-hex")


def test_uppercase_hash_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(ass_content_hash="A" * 64)


def test_empty_scene_id_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(scene_id="")


def test_empty_ass_id_rejected():
    with pytest.raises(AcceptedBatchValidationError):
        _ref(ass_id="")


@pytest.mark.parametrize("pid", ["", "UPPER", "a", "1abc", "has-dash"])
def test_malformed_project_id_rejected(pid):
    with pytest.raises(AcceptedBatchValidationError):
        _batch(project_id=pid)


def test_source_ref_absent_from_schema():
    data = serialize_accepted_batch(_batch()).decode("utf-8")
    assert "source_ref" not in data


def test_artifact_sha256_absent_from_schema():
    data = serialize_accepted_batch(_batch()).decode("utf-8")
    assert "artifact_sha256" not in data


def test_batch_id_absent_from_schema():
    data = serialize_accepted_batch(_batch()).decode("utf-8")
    assert "batch_id" not in data


def test_artifact_sha256_ref_field_rejected():
    d = _raw_batch()
    d["scene_refs"][0]["artifact_sha256"] = "0" * 64
    with pytest.raises(AcceptedBatchValidationError):
        parse_accepted_batch(_raw_text(d))


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_load_exact_batch(tmp_path):
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A), _ref(scene_id=SCENE_ID_B, ass_id="ass_b")))
    path = tmp_path / "production.batch.json"
    save_accepted_batch(path, batch)
    assert path.is_file()
    loaded = load_accepted_batch(path)
    assert loaded.to_dict() == batch.to_dict()


def test_deterministic_persisted_bytes(tmp_path):
    batch = _batch()
    path = tmp_path / "production.batch.json"
    save_accepted_batch(path, batch)
    assert path.read_bytes() == serialize_accepted_batch(batch)


def test_explicit_caller_path_only(tmp_path):
    # There is no canonical default: load requires an explicit path and fails
    # closed when it does not exist.
    with pytest.raises(AcceptedBatchNotFoundError):
        load_accepted_batch(tmp_path / "missing.batch.json")


def test_atomic_replacement(tmp_path):
    path = tmp_path / "production.batch.json"
    save_accepted_batch(path, _batch(refs=(_ref(scene_id=SCENE_ID_A),)))
    replacement = _batch(refs=(_ref(scene_id=SCENE_ID_B, ass_id="ass_b"),))
    save_accepted_batch(path, replacement)
    assert load_accepted_batch(path).to_dict() == replacement.to_dict()
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".workspace_project_batch_")]
    assert leftovers == []


def test_temp_write_failure_preserves_previous_batch(tmp_path, monkeypatch):
    path = tmp_path / "production.batch.json"
    save_accepted_batch(path, _batch())
    original = path.read_bytes()

    def failing_fdopen(fd, mode="r", *args, **kwargs):
        os.close(fd)
        raise OSError("simulated write failure")

    monkeypatch.setattr("services.workspace_project.accepted_batch.os.fdopen", failing_fdopen)

    with pytest.raises(OSError):
        save_accepted_batch(path, _batch(refs=(_ref(scene_id=SCENE_ID_B, ass_id="ass_b"),)))

    assert path.read_bytes() == original
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".workspace_project_batch_")]
    assert leftovers == []


def test_replace_failure_preserves_previous_batch(tmp_path, monkeypatch):
    path = tmp_path / "production.batch.json"
    save_accepted_batch(path, _batch())
    original = path.read_bytes()

    def failing_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("services.workspace_project.accepted_batch.os.replace", failing_replace)

    with pytest.raises(OSError):
        save_accepted_batch(path, _batch(refs=(_ref(scene_id=SCENE_ID_B, ass_id="ass_b"),)))

    assert path.read_bytes() == original
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".workspace_project_batch_")]
    assert leftovers == []


def test_malformed_existing_target_replaced(tmp_path):
    path = tmp_path / "production.batch.json"
    path.write_text("{ not json", encoding="utf-8")
    batch = _batch()
    save_accepted_batch(path, batch)
    assert load_accepted_batch(path).to_dict() == batch.to_dict()


def test_validate_accepts_valid_rejects_malformed(tmp_path):
    valid = tmp_path / "valid.batch.json"
    save_accepted_batch(valid, _batch())
    assert validate_accepted_batch(valid) == []

    malformed = tmp_path / "malformed.batch.json"
    malformed.write_text("{ not json", encoding="utf-8")
    assert validate_accepted_batch(malformed) != []


def test_validate_reports_missing_file(tmp_path):
    assert validate_accepted_batch(tmp_path / "missing.batch.json") == ["batch does not exist"]


# ---------------------------------------------------------------------------
# Project membership
# ---------------------------------------------------------------------------


def test_exact_project_id_match_resolves(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    result = _resolve(batch, _manifest(), ass_store, scene_store)
    assert [a.ass_id for a in result] == [ass.ass_id]


def test_mismatched_project_id_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(project_id="other_project", refs=(_ref_for(ass),))
    with pytest.raises(AcceptedBatchResolutionError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_scene_present_as_scene_member_accepted(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest(entities=(
        ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_A, source_ref="scenes/SC_900.json"),
    ))
    assert len(_resolve(batch, manifest, ass_store, scene_store)) == 1


def test_scene_absent_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest(entities=())  # no SCENE members
    with pytest.raises(AcceptedBatchResolutionError):
        _resolve(batch, manifest, ass_store, scene_store)


@pytest.mark.parametrize("kind", [CHARACTER, LOCATION, MEDIA_ASSET])
def test_same_stable_id_only_other_kind_rejected(ass_store, scene_store, kind):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest(entities=(ProjectEntityRef(entity_kind=kind, stable_id=SCENE_ID_A),))
    with pytest.raises(AcceptedBatchResolutionError):
        _resolve(batch, manifest, ass_store, scene_store)


def test_manifest_source_ref_not_used_as_canonical_ass_path(ass_store, scene_store):
    # A SCENE member whose source_ref points nowhere still resolves, because
    # canonical ASS location is derived only from (scene_id, version).
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest(entities=(
        ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_A, source_ref="bogus/nowhere.json"),
    ))
    result = _resolve(batch, manifest, ass_store, scene_store)
    assert [a.ass_id for a in result] == [ass.ass_id]


def test_canonical_ass_exists_but_scene_absent_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest(entities=(
        ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_B, source_ref="scenes/SC_901.json"),
    ))
    with pytest.raises(AcceptedBatchResolutionError):
        _resolve(batch, manifest, ass_store, scene_store)


# ---------------------------------------------------------------------------
# Canonical ASS resolution
# ---------------------------------------------------------------------------


def test_exact_pins_resolve(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    result = _resolve(batch, _manifest(), ass_store, scene_store)
    assert [a.scene_id for a in result] == [SCENE_ID_A]
    assert [a.version for a in result] == [1]


def test_missing_version_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A, version=2, ass_id=ass.ass_id, ass_content_hash=ass.content_hash),))
    with pytest.raises(OrderedASSNotFoundError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_wrong_ass_id_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A, version=1, ass_id="wrong", ass_content_hash=ass.content_hash),))
    with pytest.raises(OrderedASSIntegrityError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_wrong_ass_content_hash_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref(scene_id=SCENE_ID_A, version=1, ass_id=ass.ass_id, ass_content_hash="f" * 64),))
    with pytest.raises(OrderedASSIntegrityError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_corrupted_canonical_ass_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    path = ass_store.path_for(scene_id=ass.scene_id, version=ass.version)
    path.write_bytes(b"corrupted bytes")
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(OrderedASSIntegrityError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_non_canonical_stored_bytes_rejected(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    path = ass_store.path_for(scene_id=ass.scene_id, version=ass.version)
    # Valid JSON envelope but non-canonical formatting (no indent / extra space).
    path.write_bytes(json.dumps(ass.to_dict()).encode("utf-8"))
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(OrderedASSIntegrityError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_symlink_rejected_where_platform_permits(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    path = ass_store.path_for(scene_id=ass.scene_id, version=ass.version)
    path.unlink()
    try:
        os.symlink(path.parent / "somewhere_else.json", path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not permitted on this platform")
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(OrderedASSIntegrityError):
        _resolve(batch, _manifest(), ass_store, scene_store)


# ---------------------------------------------------------------------------
# Accepted lifecycle authority
# ---------------------------------------------------------------------------


def test_accepted_with_matching_link_resolves(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    result = _resolve(batch, _manifest(), ass_store, scene_store)
    assert [a.ass_id for a in result] == [ass.ass_id]


def test_orphan_ass_with_draft_scene_version_rejected(ass_store, scene_store):
    scene_store.create_initial_draft(SCENE_ID_A, make_body(scene_id=SCENE_ID_A))
    body = SceneBody.from_dict(make_body(scene_id=SCENE_ID_A))
    orphan = build_ordered_ass(body, ass_id="ass_orphan", version=1,
                               source_ref="scenes/SC_900.json", source_hash="0" * 64)
    ass_store.save(orphan)
    batch = _batch(refs=(_ref_for(orphan),))
    with pytest.raises(AcceptedBatchResolutionError, match="not ACCEPTED"):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_missing_scene_version_rejected(ass_store, scene_store):
    body = SceneBody.from_dict(make_body(scene_id=SCENE_ID_A))
    orphan = build_ordered_ass(body, ass_id="ass_orphan", version=1,
                               source_ref="scenes/SC_900.json", source_hash="0" * 64)
    ass_store.save(orphan)
    batch = _batch(refs=(_ref_for(orphan),))
    with pytest.raises(SceneVersionNotFoundError):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_missing_acceptance_link_rejected(ass_store, scene_store, monkeypatch):
    _, ass = _accept_v1(scene_store, ass_store)

    class _FakeVersion:
        lifecycle = LIFECYCLE_ACCEPTED
        acceptance = None

    monkeypatch.setattr(scene_store, "read_version", lambda scene_id, version: _FakeVersion())
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(AcceptedBatchResolutionError, match="no AcceptanceLink"):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_acceptance_link_ass_id_mismatch_rejected(ass_store, scene_store, monkeypatch):
    _, ass = _accept_v1(scene_store, ass_store)

    class _FakeVersion:
        lifecycle = LIFECYCLE_ACCEPTED
        acceptance = AcceptanceLink(ass_id="wrong_ass", ass_content_hash=ass.content_hash)

    monkeypatch.setattr(scene_store, "read_version", lambda scene_id, version: _FakeVersion())
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(AcceptedBatchResolutionError, match="ass_id"):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_acceptance_link_hash_mismatch_rejected(ass_store, scene_store, monkeypatch):
    _, ass = _accept_v1(scene_store, ass_store)

    class _FakeVersion:
        lifecycle = LIFECYCLE_ACCEPTED
        acceptance = AcceptanceLink(ass_id=ass.ass_id, ass_content_hash="f" * 64)

    monkeypatch.setattr(scene_store, "read_version", lambda scene_id, version: _FakeVersion())
    batch = _batch(refs=(_ref_for(ass),))
    with pytest.raises(AcceptedBatchResolutionError, match="content hash"):
        _resolve(batch, _manifest(), ass_store, scene_store)


def test_loaded_ass_ref_link_triple_agrees(ass_store, scene_store):
    updated, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    result = _resolve(batch, _manifest(), ass_store, scene_store)
    loaded = result[0]
    assert updated.acceptance.ass_id == _ref_for(ass).ass_id == loaded.ass_id
    assert updated.acceptance.ass_content_hash == _ref_for(ass).ass_content_hash == loaded.content_hash


# ---------------------------------------------------------------------------
# Pinning
# ---------------------------------------------------------------------------


def test_pinning_v1_remains_after_v2_accept(ass_store, scene_store):
    _, v1 = _accept_v1(scene_store, ass_store, ass_id="ass_sc900_v1")
    batch = _batch(refs=(_ref_for(v1),))
    manifest = _manifest()

    first = _resolve(batch, manifest, ass_store, scene_store)
    assert [a.version for a in first] == [1]

    v2_draft = scene_store.fork_draft_from_version(SCENE_ID_A, 1)
    _, v2 = accept_draft(scene_store, SCENE_ID_A, v2_draft.version,
                          ass_store=ass_store, ass_id="ass_sc900_v2",
                          source_ref="scenes/SC_900.json")

    # Same batch (unchanged) still resolves the pinned v1.
    second = _resolve(batch, manifest, ass_store, scene_store)
    assert [a.version for a in second] == [1]
    assert [a.ass_id for a in second] == [v1.ass_id]

    # Explicitly constructing a new batch pinning v2 selects v2.
    batch_v2 = _batch(refs=(_ref_for(v2),))
    third = _resolve(batch_v2, manifest, ass_store, scene_store)
    assert [a.version for a in third] == [v2.version]
    assert [a.ass_id for a in third] == [v2.ass_id]


# ---------------------------------------------------------------------------
# Downstream exporter integration
# ---------------------------------------------------------------------------


def test_resolve_then_export_matches_hand_built_sorted(ass_store, scene_store, monkeypatch):
    from services.production_media_asset_binding import ResolvedAsset
    from tools.vne_to_renpy import build_ordered_project_candidate

    def fake_resolve(asset_ids, *, registry_path, repo_root):
        return {
            aid: ResolvedAsset(
                asset_id=aid,
                relative_path=f"novel/game/images/story/{aid}.png",
                renpy_image_name=aid,
            )
            for aid in asset_ids
        }

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake_resolve,
    )

    _, a_901 = _accept_v1(scene_store, ass_store, scene_id=SCENE_ID_B, ass_id="ass_sc901")
    _, a_900 = _accept_v1(scene_store, ass_store, scene_id=SCENE_ID_A, ass_id="ass_sc900")

    batch = _batch(refs=(_ref_for(a_901), _ref_for(a_900)))
    manifest = _manifest(entities=(
        ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_B, source_ref="scenes/SC_901.json"),
        ProjectEntityRef(entity_kind=SCENE, stable_id=SCENE_ID_A, source_ref="scenes/SC_900.json"),
    ))

    resolved = _resolve(batch, manifest, ass_store, scene_store)
    assert isinstance(resolved, tuple)
    assert [a.scene_id for a in resolved] == [SCENE_ID_A, SCENE_ID_B]  # ascending

    hand = tuple(sorted((a_900, a_901), key=lambda a: a.scene_id))

    kwargs = dict(reading_mode="classic_vn", character_symbols={"KIRA": "kira"},
                  registry_path=Path("dummy.json"), repo_root=Path("dummy_repo"))
    c_resolved = build_ordered_project_candidate(resolved, **kwargs)
    c_hand = build_ordered_project_candidate(hand, **kwargs)

    assert c_resolved.source == c_hand.source
    assert c_resolved.source_sha256 == c_hand.source_sha256
    assert c_resolved.scene_ids == c_hand.scene_ids == (SCENE_ID_A, SCENE_ID_B)


# ---------------------------------------------------------------------------
# No mutation during resolution
# ---------------------------------------------------------------------------


def test_resolution_is_read_only(ass_store, scene_store):
    _, ass = _accept_v1(scene_store, ass_store)
    batch = _batch(refs=(_ref_for(ass),))
    manifest = _manifest()

    ass_path = ass_store.path_for(scene_id=ass.scene_id, version=ass.version)
    sv_path = scene_store._version_path(ass.scene_id, ass.version)
    pointer_path = scene_store._pointer_path(ass.scene_id)
    ass_before = ass_path.read_bytes()
    sv_before = sv_path.read_bytes()
    pointer_before = pointer_path.read_bytes()

    result = _resolve(batch, manifest, ass_store, scene_store)
    assert len(result) == 1

    assert ass_path.read_bytes() == ass_before
    assert sv_path.read_bytes() == sv_before
    assert pointer_path.read_bytes() == pointer_before
