#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Editor Application Service v1 tests -- discovery, lifecycle, acceptance,
idempotency, immutability, structured validation, and storage-hiding."""

from __future__ import annotations

import pytest

from services.ass import OrderedASSStore
from services.editor_application import (
    ACCEPTED_IMMUTABLE,
    ALREADY_EXISTS,
    INVALID_INPUT,
    NOT_FOUND,
    OK,
    VALIDATION_FAILED,
    EditorApplicationError,
    EditorApplicationService,
)

from .conftest import PROJECT_ID, build_config, make_body

SCENE_ID = "sc_test_001"


def _config_without_characters(config):
    from dataclasses import replace

    return replace(config, character_canon_root=None)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_list_characters(service):
    characters = service.list_characters()
    ids = [c.character_id for c in characters]
    assert ids == ["KIRA", "SERGEY"]
    assert all(c.label == c.character_id for c in characters)
    assert all(c.status == "APPROVED_AS_CANON" for c in characters)


def test_list_characters_without_canon_root(tmp_path):
    config = build_config(tmp_path, with_characters=False)
    service = EditorApplicationService(_config_without_characters(config))
    assert service.list_characters() == ()


def test_list_locations(service):
    locations = service.list_locations()
    ids = [loc.location_id for loc in locations]
    assert ids == ["gym", "yoga_hall"]
    assert all(loc.label == loc.location_id for loc in locations)


def test_list_scenes_empty_then_populated(service):
    assert service.list_scenes() == ()
    result = service.create_scene(SCENE_ID, make_body())
    assert result.ok
    scenes = service.list_scenes()
    assert [s.scene_id for s in scenes] == [SCENE_ID]


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


def test_get_scene_workspace_after_create(service):
    service.create_scene(SCENE_ID, make_body())
    workspace = service.get_scene_workspace(SCENE_ID)
    assert workspace.scene_id == SCENE_ID
    assert workspace.latest_version == 1
    assert workspace.lifecycle == "DRAFT"
    assert workspace.body["scene_id"] == SCENE_ID
    assert workspace.acceptance is None
    assert workspace.manifest_included is True


def test_get_scene_workspace_not_found(service):
    with pytest.raises(EditorApplicationError) as exc_info:
        service.get_scene_workspace("sc_missing_001")
    assert exc_info.value.code == NOT_FOUND


# ---------------------------------------------------------------------------
# Create / save
# ---------------------------------------------------------------------------


def test_create_scene(service):
    result = service.create_scene(SCENE_ID, make_body())
    assert result.ok is True
    assert result.code == OK
    assert result.scene_id == SCENE_ID
    assert result.version == 1
    assert result.lifecycle == "DRAFT"


def test_create_scene_duplicate(service):
    service.create_scene(SCENE_ID, make_body())
    result = service.create_scene(SCENE_ID, make_body())
    assert result.ok is False
    assert result.code == ALREADY_EXISTS


def test_create_scene_invalid_body(service):
    result = service.create_scene(SCENE_ID, {"scene_id": SCENE_ID})
    assert result.ok is False
    assert result.code == INVALID_INPUT


def test_save_draft(service):
    service.create_scene(SCENE_ID, make_body())
    edited = make_body(scene_title="Edited title")
    result = service.save_draft(SCENE_ID, 1, edited)
    assert result.ok is True
    assert result.code == OK
    workspace = service.get_scene_workspace(SCENE_ID)
    assert workspace.body["scene_title"] == "Edited title"


def test_save_draft_not_found(service):
    result = service.save_draft(SCENE_ID, 1, make_body())
    assert result.ok is False
    assert result.code == NOT_FOUND


# ---------------------------------------------------------------------------
# Acceptance / immutability
# ---------------------------------------------------------------------------


def _accept(service):
    service.create_scene(SCENE_ID, make_body())
    return service.accept_scene(SCENE_ID, 1)


def test_accept_scene_coordinates_manifest_and_batch(service):
    result = _accept(service)
    assert result.ok is True
    assert result.code == OK
    assert result.lifecycle == "ACCEPTED"

    state = service.get_acceptance_state(SCENE_ID, 1)
    assert state.accepted is True
    assert state.ass_id == f"ass_{SCENE_ID}_v1"
    assert state.manifest_included is True
    assert state.batch_included is True
    assert state.batch_resolvable is True

    scenes = service.list_scenes()
    assert scenes[0].accepted_version == 1
    assert scenes[0].ass_id == f"ass_{SCENE_ID}_v1"


def test_save_accepted_is_immutable(service):
    _accept(service)
    result = service.save_draft(SCENE_ID, 1, make_body(scene_title="changed"))
    assert result.ok is False
    assert result.code == ACCEPTED_IMMUTABLE


def test_fork_accepted_creates_new_draft(service):
    _accept(service)
    result = service.fork_scene_version(SCENE_ID, 1)
    assert result.ok is True
    assert result.version == 2
    assert result.lifecycle == "DRAFT"

    state_v1 = service.get_acceptance_state(SCENE_ID, 1)
    assert state_v1.accepted is True

    state_v2 = service.get_acceptance_state(SCENE_ID, 2)
    assert state_v2.accepted is False
    assert state_v2.lifecycle == "DRAFT"


def test_accepted_v1_unchanged_after_fork_and_edit_v2(service):
    _accept(service)
    v1_before = service.get_acceptance_state(SCENE_ID, 1)
    assert v1_before.accepted is True

    service.fork_scene_version(SCENE_ID, 1)
    service.save_draft(SCENE_ID, 2, make_body(scene_title="v2 changed"))

    v1_after = service.get_acceptance_state(SCENE_ID, 1)
    assert v1_after.accepted is True
    assert v1_after.ass_id == f"ass_{SCENE_ID}_v1"
    assert v1_after.ass_content_hash == v1_before.ass_content_hash

    v2_after = service.get_acceptance_state(SCENE_ID, 2)
    assert v2_after.accepted is False


def test_accept_idempotent_after_partial_state(service):
    """Repeated accept after a prior accept completes missing inclusion without
    rewriting accepted authority."""
    _accept(service)
    v1_hash_before = service.get_acceptance_state(SCENE_ID, 1).ass_content_hash

    # Second accept is idempotent: already ACCEPTED, inclusion already complete.
    result = service.accept_scene(SCENE_ID, 1)
    assert result.ok is True
    assert result.code == OK

    v1_hash_after = service.get_acceptance_state(SCENE_ID, 1).ass_content_hash
    assert v1_hash_after == v1_hash_before


# ---------------------------------------------------------------------------
# Validation (structured diagnostics)
# ---------------------------------------------------------------------------


def test_validate_acceptance_complete(service):
    service.create_scene(SCENE_ID, make_body())
    result = service.validate_scene(SCENE_ID, 1)
    assert result.ok is True
    assert result.code == OK
    assert result.diagnostics == ()


def test_validate_invalid_branch_returns_structured_diagnostic(service):
    # A CHOICE whose ENTRY target does not resolve inside the SceneBody.
    body = make_body(
        entries=[
            {
                "entry_id": "c1",
                "kind": "CHOICE",
                "prompt": "broken",
                "options": [
                    {
                        "option_id": "o1",
                        "display_text": "Go",
                        "target": {"target_kind": "ENTRY", "target_id": "missing_target"},
                    }
                ],
            },
            {
                "entry_id": "e1",
                "kind": "TEXT",
                "presentation": "NARRATIVE",
                "text": "Some text.",
                "character_id": None,
                "thought_visibility": None,
            },
        ]
    )
    service.create_scene(SCENE_ID, body)
    result = service.validate_scene(SCENE_ID, 1)
    assert result.ok is False
    assert result.code == VALIDATION_FAILED
    assert len(result.diagnostics) >= 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == VALIDATION_FAILED
    assert diagnostic.severity == "error"
    assert "missing_target" in diagnostic.message


def test_diagnostic_entry_id_extraction(service):
    # A blank text entry yields an entry-localized validator message.
    body = make_body(
        entries=[
            {
                "entry_id": "e1",
                "kind": "TEXT",
                "presentation": "NARRATIVE",
                "text": "   ",
                "character_id": None,
                "thought_visibility": None,
            }
        ]
    )
    service.create_scene(SCENE_ID, body)
    result = service.validate_scene(SCENE_ID, 1)
    assert result.ok is False
    entry_diags = [d for d in result.diagnostics if d.entry_id == "e1"]
    assert entry_diags, result.diagnostics
    assert entry_diags[0].entry_id == "e1"


def test_validate_missing_version(service):
    result = service.validate_scene(SCENE_ID, 1)
    assert result.ok is False
    assert result.code == NOT_FOUND


def test_accept_invalid_returns_validation_failed(service):
    body = make_body(entries=[])
    service.create_scene(SCENE_ID, body)
    result = service.accept_scene(SCENE_ID, 1)
    assert result.ok is False
    assert result.code == VALIDATION_FAILED
    assert len(result.diagnostics) >= 1


# ---------------------------------------------------------------------------
# Storage hiding / no base32 leak
# ---------------------------------------------------------------------------


def test_public_dtos_expose_no_storage_paths(service):
    import base64

    _accept(service)

    summary = service.list_scenes()[0]
    workspace = service.get_scene_workspace(SCENE_ID)
    state = service.get_acceptance_state(SCENE_ID, 1)

    # The base32 token the domain uses internally for canonical ASS storage.
    token = base64.b32encode(SCENE_ID.encode("utf-8")).decode("ascii").lower().rstrip("=")

    string_values = [
        summary.scene_id,
        summary.ass_id,
        state.ass_id,
        state.ass_content_hash,
        state.lifecycle,
    ]
    for value in string_values:
        if value is not None:
            assert "/" not in value and "\\" not in value
            assert token not in value

    _assert_no_paths_recursive(workspace.body)
    _assert_no_paths_recursive(workspace.acceptance)


def test_base32_storage_is_internal_only(tmp_path):
    import base64

    config = build_config(tmp_path)
    service = EditorApplicationService(config)
    _accept(service)

    token = base64.b32encode(SCENE_ID.encode("utf-8")).decode("ascii").lower().rstrip("=")

    # The canonical ASS on disk IS stored under a base32-encoded directory ...
    ass_store = OrderedASSStore(config.accepted_ass_root)
    path = ass_store.path_for(scene_id=SCENE_ID, version=1)
    assert token in str(path)

    # ... but the facade never exposes that encoded directory in its results.
    scenes = service.list_scenes()
    assert all(token not in str(s.scene_id) for s in scenes)
    assert all(token not in (s.ass_id or "") for s in scenes)


def _assert_no_paths_recursive(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert "/" not in key and "\\" not in key
            _assert_no_paths_recursive(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_paths_recursive(item)


# ---------------------------------------------------------------------------
# Publication readiness (read-only)
# ---------------------------------------------------------------------------


def test_publication_readiness_before_accept(service):
    result = service.get_publication_readiness()
    assert result.ok is False
    assert result.code == NOT_FOUND  # no batch yet


def test_publication_readiness_after_accept(service):
    _accept(service)
    result = service.get_publication_readiness()
    assert result.ok is True
    assert result.code == OK


