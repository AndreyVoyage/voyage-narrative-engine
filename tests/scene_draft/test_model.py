#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SceneVersion / AcceptanceLink model invariant tests."""

from __future__ import annotations

import pytest

from services.scene_draft import (
    LIFECYCLE_ACCEPTED,
    LIFECYCLE_DRAFT,
    AcceptanceLink,
    SceneIdMismatchError,
    SceneInvariantError,
    SceneValidationError,
    SceneVersion,
)


def _link(ass_id: str = "ass_sc900_1") -> AcceptanceLink:
    return AcceptanceLink(ass_id=ass_id, ass_content_hash="a" * 64)


def test_valid_draft(valid_body):
    v = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    assert v.version == 1
    assert v.lifecycle == LIFECYCLE_DRAFT
    assert v.scene_id == "SC_900"
    assert v.acceptance is None
    assert len(v.content_hash) == 64


def test_valid_accepted(valid_body):
    link = _link()
    v = SceneVersion(
        scene_id="SC_900",
        version=2,
        lifecycle=LIFECYCLE_ACCEPTED,
        body=valid_body,
        acceptance=link,
    )
    assert v.lifecycle == LIFECYCLE_ACCEPTED
    assert v.acceptance is link
    assert v.acceptance.ass_id == "ass_sc900_1"
    assert v.acceptance.ass_content_hash == "a" * 64


def test_draft_with_acceptance_rejected(valid_body):
    with pytest.raises(SceneInvariantError):
        SceneVersion(
            scene_id="SC_900",
            version=1,
            lifecycle=LIFECYCLE_DRAFT,
            body=valid_body,
            acceptance=_link(),
        )


def test_accepted_without_acceptance_rejected(valid_body):
    with pytest.raises(SceneInvariantError):
        SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_ACCEPTED, body=valid_body)


@pytest.mark.parametrize("bad_version", [0, -1, 1.5, "1", True, None])
def test_invalid_version_rejected(valid_body, bad_version):
    with pytest.raises(SceneInvariantError):
        SceneVersion(
            scene_id="SC_900",
            version=bad_version,
            lifecycle=LIFECYCLE_DRAFT,
            body=valid_body,
        )


def test_invalid_body_rejected():
    with pytest.raises(SceneValidationError):
        SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body={"id": "SC_900"})


def test_non_dict_body_rejected():
    with pytest.raises(SceneValidationError):
        SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body="not a dict")


def test_scene_id_mismatch_rejected(valid_body):
    with pytest.raises(SceneIdMismatchError):
        SceneVersion(scene_id="SC_999", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)


def test_deterministic_authored_content_hash(valid_body):
    a = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    reordered = dict(reversed(list(valid_body.items())))
    b = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=reordered)
    assert a.content_hash == b.content_hash


def test_content_hash_unchanged_by_lifecycle(valid_body):
    draft = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    accepted = SceneVersion(
        scene_id="SC_900",
        version=1,
        lifecycle=LIFECYCLE_ACCEPTED,
        body=valid_body,
        acceptance=_link(),
    )
    assert draft.content_hash == accepted.content_hash


def test_caller_mutation_cannot_affect_model(valid_body):
    v = SceneVersion(scene_id="SC_900", version=1, lifecycle=LIFECYCLE_DRAFT, body=valid_body)
    original_hash = v.content_hash
    original_name = v.body["name"]
    valid_body["name"] = "MUTATED"
    valid_body["characters"][0]["display_name"] = "MUTATED"
    valid_body["choice_points"][0]["branches"][0]["option_text"] = "MUTATED"
    assert v.body["name"] == original_name
    assert v.content_hash == original_hash
    with pytest.raises(TypeError):
        v.body["name"] = "x"


def test_acceptance_link_requires_non_empty():
    with pytest.raises(SceneValidationError):
        AcceptanceLink(ass_id="", ass_content_hash="a" * 64)
    with pytest.raises(SceneValidationError):
        AcceptanceLink(ass_id="ass_x", ass_content_hash="")
