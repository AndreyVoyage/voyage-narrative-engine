#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance compiler tests -- DRAFT -> ACCEPTED via build_ordered_ass."""

from __future__ import annotations

import copy

import pytest

from services.ass import (
    OrderedASS, OrderedASSStoreError, OrderedASSIntegrityError,
    OrderedASSNotFoundError, build_ordered_ass, serialize_ordered_ass,
)
from services.scene_draft import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    AcceptanceError,
    AcceptanceIncompleteError,
    AcceptedVersionImmutableError,
    AlreadyAcceptedError,
    AcceptanceLink,
    SceneVersionNotFoundError,
    accept_draft,
)
from tests.scene_draft.conftest import make_body

ASS_ID = "ass_sc900_1"
SOURCE_REF = "scenes/SC_900.json"


def _accept(store, ass_store, scene_id, version=1, **kwargs):
    return accept_draft(
        store,
        scene_id,
        version,
        ass_store=ass_store,
        ass_id=kwargs.get("ass_id", ASS_ID),
        source_ref=kwargs.get("source_ref", SOURCE_REF),
    )


def test_accept_draft_returns_accepted_and_ordered_ass(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, ass_store, scene_id)
    assert updated.lifecycle == LIFECYCLE_ACCEPTED
    assert updated.acceptance is not None
    assert isinstance(ass, OrderedASS)


def test_ass_generated_via_ordered_builder(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _updated, ass = _accept(store, ass_store, scene_id)
    assert ass.schema_version == "ass/0.2"
    assert len(ass.content_hash) == 64
    assert len(ass.ordered_flow) == 3


def test_scene_version_scene_id_equals_ass_scene_id(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, ass_store, scene_id)
    assert updated.scene_id == ass.scene_id == "SC_900"


def test_scene_version_version_equals_ass_version(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, ass_store, scene_id)
    assert updated.version == ass.version == 1


def test_acceptance_link_matches_ass(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, ass_store, scene_id)
    assert updated.acceptance.ass_id == ass.ass_id
    assert updated.acceptance.ass_content_hash == ass.content_hash


def test_authored_content_hash_unchanged_by_acceptance(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    before = store.read_version(scene_id, 1).content_hash
    updated, _ass = _accept(store, ass_store, scene_id)
    assert updated.content_hash == before


def test_location_comes_from_scene_body(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, make_body(location_id="gym_night"))
    _updated, ass = _accept(store, ass_store, scene_id)
    assert ass.location_id == "gym_night"


def test_second_acceptance_fails_closed(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, ass_store, scene_id)
    with pytest.raises(AlreadyAcceptedError):
        _accept(store, ass_store, scene_id)


def test_accepted_version_cannot_save_draft(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, ass_store, scene_id)
    with pytest.raises(AcceptedVersionImmutableError):
        store.save_draft(scene_id, 1, copy.deepcopy(valid_body))


def test_fork_after_acceptance_creates_next_draft(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, ass_store, scene_id)
    v2 = store.fork_draft_from_version(scene_id, 1)
    assert v2.version == 2
    assert v2.lifecycle == LIFECYCLE_DRAFT


def test_acceptance_does_not_alter_pointer(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, ass_store, scene_id)
    assert store._read_pointer(scene_id) == 1


def test_accept_missing_version_fails(store, ass_store, scene_id):
    with pytest.raises(SceneVersionNotFoundError):
        _accept(store, ass_store, scene_id)


def test_accept_incomplete_body_fails_before_mutation(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, make_body(location_id=None))
    with pytest.raises(AcceptanceIncompleteError):
        _accept(store, ass_store, scene_id)
    # still DRAFT on disk -- no lifecycle mutation happened
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT
    assert not ass_store.path_for(scene_id=scene_id, version=1).exists()


def test_accept_ass_mismatch_fails_closed(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)

    import services.scene_draft.compiler as compiler_mod

    class FakeAss:
        scene_id = "SC_999"
        version = 1
        ass_id = "ass_x"
        content_hash = "a" * 64

    monkeypatch.setattr(compiler_mod, "build_ordered_ass", lambda *a, **k: FakeAss())
    with pytest.raises(AcceptanceError):
        _accept(store, ass_store, scene_id)


def test_persist_reload_then_commit_order(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)
    events = []
    real_save, real_load, real_commit = ass_store.save, ass_store.load, store.commit_acceptance
    loaded = []
    def save(scene):
        events.append("save")
        assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT
        return real_save(scene)
    def load(**kwargs):
        events.append("load")
        assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT
        result = real_load(**kwargs)
        loaded.append(result)
        return result
    def commit(*args, **kwargs):
        assert events[0] == "save" and events[-1] == "load"
        assert kwargs["verified_ass"] is loaded[-1]
        events.append("commit")
        return real_commit(*args, **kwargs)
    monkeypatch.setattr(ass_store, "save", save)
    monkeypatch.setattr(ass_store, "load", load)
    monkeypatch.setattr(store, "commit_acceptance", commit)
    updated, result = _accept(store, ass_store, scene_id)
    assert updated.lifecycle == LIFECYCLE_ACCEPTED
    assert any(result is item for item in loaded)
    assert result.to_dict() == real_load(scene_id=scene_id, version=1).to_dict()
    assert updated.acceptance == AcceptanceLink(result.ass_id, result.content_hash)
    assert ass_store.path_for(scene_id=scene_id, version=1).read_bytes() == serialize_ordered_ass(result)


def test_save_failure_leaves_exact_draft(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)
    before = store._version_path(scene_id, 1).read_bytes()
    def fail(scene):
        raise OrderedASSStoreError("injected save failure")
    monkeypatch.setattr(ass_store, "save", fail)
    with pytest.raises(OrderedASSStoreError):
        _accept(store, ass_store, scene_id)
    assert store._version_path(scene_id, 1).read_bytes() == before
    assert not ass_store.path_for(scene_id=scene_id, version=1).exists()


def test_verify_failure_leaves_draft(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)
    real_save = ass_store.save
    def fail(**kwargs):
        raise OrderedASSIntegrityError("injected verification failure")
    def save(scene):
        result = real_save(scene)
        monkeypatch.setattr(ass_store, "load", fail)
        return result
    monkeypatch.setattr(ass_store, "save", save)
    with pytest.raises(OrderedASSIntegrityError):
        _accept(store, ass_store, scene_id)
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT
    assert store.read_version(scene_id, 1).acceptance is None


def test_commit_failure_orphan_retry(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)
    original = store._write_version_record
    def fail(record):
        raise OSError("injected record write failure")
    monkeypatch.setattr(store, "_write_version_record", fail)
    with pytest.raises(OSError):
        _accept(store, ass_store, scene_id)
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT
    path = ass_store.path_for(scene_id=scene_id, version=1)
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    monkeypatch.setattr(store, "_write_version_record", original)
    updated, ass = _accept(store, ass_store, scene_id)
    assert updated.lifecycle == LIFECYCLE_ACCEPTED
    assert path.read_bytes() == before == serialize_ordered_ass(ass)
    assert path.stat().st_mtime_ns == mtime


def test_changed_draft_between_save_and_commit_rejected(store, ass_store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)
    original = store.commit_acceptance
    changed = copy.deepcopy(valid_body)
    changed["scene_title"] = "Изменено до commit"
    def race(*args, **kwargs):
        store.save_draft(scene_id, 1, changed)
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "commit_acceptance", race)
    with pytest.raises(AcceptanceError, match="Draft content changed"):
        _accept(store, ass_store, scene_id)
    current = store.read_version(scene_id, 1)
    assert current.lifecycle == LIFECYCLE_DRAFT and current.acceptance is None
    assert current.body_plain() == changed
    assert ass_store.load(scene_id=scene_id, version=1).scene_title == valid_body["scene_title"]


def _commit_inputs(store, scene_id, *, body=None):
    record = store.read_version(scene_id, 1)
    ass = build_ordered_ass(
        record.body if body is None else body, ass_id=ASS_ID, version=1,
        source_ref=SOURCE_REF, source_hash=record.content_hash,
    )
    return ass, AcceptanceLink(ass.ass_id, ass.content_hash), record.content_hash


def test_public_commit_requires_backing_file(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id)
    with pytest.raises(OrderedASSNotFoundError):
        store.commit_acceptance(scene_id, 1, link, expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=ass)
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT


def test_public_commit_rejects_arbitrary_link(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id)
    ass_store.save(ass)
    with pytest.raises(AcceptanceError, match="link mismatch"):
        store.commit_acceptance(scene_id, 1, AcceptanceLink("invented", link.ass_content_hash),
                                expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=ass)
    assert store.read_version(scene_id, 1).acceptance is None


def test_public_commit_rechecks_actual_persisted_identity(store, ass_store, valid_body, scene_id):
    from dataclasses import replace
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id)
    ass_store.save(replace(ass, ass_id="different_persisted_id"))
    with pytest.raises(OrderedASSIntegrityError, match="ass_id mismatch"):
        store.commit_acceptance(scene_id, 1, link, expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=ass)
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT


def test_public_commit_rechecks_full_verified_envelope(store, ass_store, valid_body, scene_id):
    from dataclasses import replace
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id)
    ass_store.save(replace(ass, author="different"))
    with pytest.raises(AcceptanceError, match="envelope mismatch"):
        store.commit_acceptance(scene_id, 1, link, expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=ass)
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT


def test_old_unverified_commit_signature_is_not_an_accept_route(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    with pytest.raises(TypeError):
        store.commit_acceptance(scene_id, 1, AcceptanceLink("arbitrary", "0" * 64))
    assert store.read_version(scene_id, 1).acceptance is None


@pytest.mark.parametrize("field,value", [("scene_id", "SC_901"), ("version", 2)])
def test_public_commit_wrong_verified_identity(store, ass_store, valid_body, scene_id, field, value):
    from dataclasses import replace
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id)
    with pytest.raises(AcceptanceError, match="identity"):
        store.commit_acceptance(scene_id, 1, link, expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=replace(ass, **{field: value}))
    assert store.read_version(scene_id, 1).lifecycle == LIFECYCLE_DRAFT


def test_forged_source_hash_cannot_accept_different_content(store, ass_store, valid_body, scene_id):
    from services.scene_body import SceneBody
    store.create_initial_draft(scene_id, valid_body)
    ass, link, expected = _commit_inputs(store, scene_id, body=SceneBody.from_dict(make_body(scene_title="Other")))
    ass_store.save(ass)
    with pytest.raises(AcceptanceError, match="Draft projection"):
        store.commit_acceptance(scene_id, 1, link, expected_draft_content_hash=expected,
                                ass_store=ass_store, verified_ass=ass)
    assert store.read_version(scene_id, 1).acceptance is None


def test_accepted_versions_retained_and_pointer_unchanged(store, ass_store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _, a = _accept(store, ass_store, scene_id)
    old_path = ass_store.path_for(scene_id=scene_id, version=1)
    old_bytes = old_path.read_bytes()
    v2 = store.fork_draft_from_version(scene_id, 1)
    before_pointer = store._pointer_path(scene_id).read_bytes()
    _, b = _accept(store, ass_store, scene_id, v2.version)
    assert b.version == 2 and b.ass_id == a.ass_id  # Caller semantics unchanged.
    assert b.content_hash == a.content_hash
    assert old_path.read_bytes() == old_bytes
    assert ass_store.load(scene_id=scene_id, version=1).to_dict() == a.to_dict()
    assert store._pointer_path(scene_id).read_bytes() == before_pointer
