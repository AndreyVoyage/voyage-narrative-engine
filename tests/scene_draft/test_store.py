#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SceneDraftStore lifecycle / persistence / fail-closed tests."""

from __future__ import annotations

import copy

import pytest

from services.scene_draft import (
    LIFECYCLE_DRAFT,
    AcceptedVersionImmutableError,
    PersistenceError,
    SceneHistoryExistsError,
    SceneIdMismatchError,
    SceneVersion,
    SceneVersionNotFoundError,
    accept_draft,
    serialize_version_record,
)

ASS_ID = "ass_sc900_1"
LOCATION_ID = "test"
SOURCE_REF = "scenarios/SCENARIO_900.v2.json"


def _with_name(body, name):
    b = copy.deepcopy(body)
    b["name"] = name
    return b


def _accept(store, scene_id, version=1):
    return accept_draft(
        store,
        scene_id,
        version,
        ass_id=ASS_ID,
        location_id=LOCATION_ID,
        source_ref=SOURCE_REF,
    )


def test_create_initial_draft_gives_version_1(store, valid_body, scene_id):
    v = store.create_initial_draft(scene_id, valid_body)
    assert v.version == 1
    assert v.lifecycle == LIFECYCLE_DRAFT


def test_duplicate_initial_creation_rejected(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    with pytest.raises(SceneHistoryExistsError):
        store.create_initial_draft(scene_id, valid_body)


def test_save_draft_preserves_version(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    v = store.save_draft(scene_id, 1, _with_name(valid_body, "Updated"))
    assert v.version == 1
    assert v.body["name"] == "Updated"


def test_save_draft_does_not_increment_latest(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    store.save_draft(scene_id, 1, _with_name(valid_body, "Updated"))
    v2 = store.fork_draft_from_version(scene_id, 1)
    assert v2.version == 2  # pointer stayed at 1, so fork allocates 2


def test_save_draft_scene_id_must_remain_identical(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    bad_body = copy.deepcopy(valid_body)
    bad_body["id"] = "SC_999"
    with pytest.raises(SceneIdMismatchError):
        store.save_draft(scene_id, 1, bad_body)


def test_save_accepted_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    with pytest.raises(AcceptedVersionImmutableError):
        store.save_draft(scene_id, 1, _with_name(valid_body, "MUTATED"))


def test_accepted_file_unchanged_after_rejected_save(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    path = store._version_path(scene_id, 1)
    before = path.read_bytes()
    with pytest.raises(AcceptedVersionImmutableError):
        store.save_draft(scene_id, 1, _with_name(valid_body, "MUTATED"))
    assert path.read_bytes() == before


def test_fork_accepted_creates_new_highest_draft(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    v2 = store.fork_draft_from_version(scene_id, 1)
    assert v2.version == 2
    assert v2.lifecycle == LIFECYCLE_DRAFT
    assert v2.acceptance is None


def test_fork_old_historical_version_creates_new_highest(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    store.fork_draft_from_version(scene_id, 1)  # v2
    v3 = store.fork_draft_from_version(scene_id, 1)  # restore from v1 -> v3
    assert v3.version == 3
    assert v3.lifecycle == LIFECYCLE_DRAFT
    assert v3.body_plain() == valid_body


def test_fork_does_not_modify_source(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    before = store._version_path(scene_id, 1).read_bytes()
    store.fork_draft_from_version(scene_id, 1)
    assert store._version_path(scene_id, 1).read_bytes() == before


def test_next_version_from_pointer_not_directory_scan(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    stray = store._version_path(scene_id, 99)
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("{}", encoding="utf-8")
    v2 = store.fork_draft_from_version(scene_id, 1)
    assert v2.version == 2  # from pointer (1 + 1), not from stray file 99


def test_malformed_pointer_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    store._pointer_path(scene_id).write_text("not json", encoding="utf-8")
    with pytest.raises(PersistenceError):
        store.fork_draft_from_version(scene_id, 1)


def test_malformed_version_file_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    store._version_path(scene_id, 1).write_text("not json", encoding="utf-8")
    with pytest.raises(PersistenceError):
        store.read_version(scene_id, 1)


def test_version_mismatch_persisted_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    v3 = SceneVersion(scene_id=scene_id, version=3, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    path = store._version_path(scene_id, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_version_record(v3), encoding="utf-8")
    with pytest.raises(PersistenceError):
        store.read_version(scene_id, 2)


def test_scene_id_mismatch_persisted_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    bad_body = copy.deepcopy(valid_body)
    bad_body["id"] = "SC_999"
    v2 = SceneVersion(scene_id="SC_999", version=2, lifecycle=LIFECYCLE_DRAFT, body=bad_body)
    path = store._version_path(scene_id, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_version_record(v2), encoding="utf-8")
    with pytest.raises(PersistenceError):
        store.read_version(scene_id, 2)


def test_read_missing_version_fails(store, scene_id):
    with pytest.raises(SceneVersionNotFoundError):
        store.read_version(scene_id, 1)


def test_deterministic_serialization(valid_body):
    v1 = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    v2 = SceneVersion(
        scene_id="SC_900",
        version=1,
        lifecycle=LIFECYCLE_DRAFT,
        body=copy.deepcopy(valid_body),
    )
    assert serialize_version_record(v1) == serialize_version_record(v2)


def test_atomic_write_leaves_no_temp_files(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    store.save_draft(scene_id, 1, _with_name(valid_body, "Updated"))
    store.fork_draft_from_version(scene_id, 1)
    leftovers = [
        p for p in store._scene_dir(scene_id).rglob("*.tmp") if p.name.startswith(".scene_draft_")
    ]
    assert leftovers == []
