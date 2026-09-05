#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance compiler tests -- DRAFT -> ACCEPTED via the existing ASS importer."""

from __future__ import annotations

import copy

import pytest

from services.ass import ASS
from services.scene_draft import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    AcceptanceError,
    AcceptedVersionImmutableError,
    AlreadyAcceptedError,
    SceneVersionNotFoundError,
    accept_draft,
)

ASS_ID = "ass_sc900_1"
LOCATION_ID = "test"
SOURCE_REF = "scenarios/SCENARIO_900.v2.json"


def _accept(store, scene_id, version=1, **kwargs):
    return accept_draft(
        store,
        scene_id,
        version,
        ass_id=kwargs.get("ass_id", ASS_ID),
        location_id=kwargs.get("location_id", LOCATION_ID),
        source_ref=kwargs.get("source_ref", SOURCE_REF),
    )


def test_accept_draft_returns_accepted_and_ass(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, scene_id)
    assert updated.lifecycle == LIFECYCLE_ACCEPTED
    assert updated.acceptance is not None
    assert isinstance(ass, ASS)


def test_ass_generated_via_existing_import_scene(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _updated, ass = _accept(store, scene_id)
    assert ass.schema_version == "ass/0.1"
    assert len(ass.content_hash) == 64


def test_scene_version_scene_id_equals_ass_scene_id(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, scene_id)
    assert updated.scene_id == ass.scene_id == "SC_900"


def test_scene_version_version_equals_ass_version(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, scene_id)
    assert updated.version == ass.version == 1


def test_acceptance_link_matches_ass(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    updated, ass = _accept(store, scene_id)
    assert updated.acceptance.ass_id == ass.ass_id
    assert updated.acceptance.ass_content_hash == ass.content_hash


def test_authored_content_hash_unchanged_by_acceptance(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    before = store.read_version(scene_id, 1).content_hash
    updated, _ass = _accept(store, scene_id)
    assert updated.content_hash == before


def test_second_acceptance_fails_closed(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    with pytest.raises(AlreadyAcceptedError):
        _accept(store, scene_id)


def test_accepted_version_cannot_save_draft(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    with pytest.raises(AcceptedVersionImmutableError):
        store.save_draft(scene_id, 1, copy.deepcopy(valid_body))


def test_fork_after_acceptance_creates_next_draft(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    v2 = store.fork_draft_from_version(scene_id, 1)
    assert v2.version == 2
    assert v2.lifecycle == LIFECYCLE_DRAFT


def test_acceptance_does_not_alter_pointer(store, valid_body, scene_id):
    store.create_initial_draft(scene_id, valid_body)
    _accept(store, scene_id)
    assert store._read_pointer(scene_id) == 1


def test_accept_missing_version_fails(store, scene_id):
    with pytest.raises(SceneVersionNotFoundError):
        _accept(store, scene_id)


def test_accept_ass_mismatch_fails_closed(store, valid_body, scene_id, monkeypatch):
    store.create_initial_draft(scene_id, valid_body)

    import services.scene_draft.compiler as compiler_mod

    class FakeAss:
        scene_id = "SC_999"
        version = 1
        ass_id = "ass_x"
        content_hash = "a" * 64

    monkeypatch.setattr(compiler_mod, "import_scene", lambda *a, **k: FakeAss())
    with pytest.raises(AcceptanceError):
        _accept(store, scene_id)
