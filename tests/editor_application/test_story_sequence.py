#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Editor Application Service v1 -- Story Sequence facade tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from services.editor_application import (
    INVALID_INPUT,
    NOT_FOUND,
    OK,
    VALIDATION_FAILED,
    EditorApplicationError,
    EditorApplicationService,
)
from services.story_sequence import StorySequence

from .conftest import build_config, make_body

SCENE_ID = "sc_test_001"
SS_FILENAME = "STORY_SEQUENCE.json"


def _config_with_story_sequence(tmp_path):
    config = build_config(tmp_path)
    return replace(config, story_sequence_path=config.manifest_path.parent / SS_FILENAME)


def _accept(service) -> None:
    result = service.create_scene(SCENE_ID, make_body())
    assert result.ok, result
    result = service.accept_scene(SCENE_ID, 1)
    assert result.ok, result


def test_get_story_sequence_not_configured(service):
    with pytest.raises(EditorApplicationError) as exc_info:
        service.get_story_sequence()
    assert exc_info.value.code == NOT_FOUND


def test_save_and_get_story_sequence(tmp_path):
    service = EditorApplicationService(_config_with_story_sequence(tmp_path))
    result = service.save_story_sequence(("sc_a", "sc_b"), "sc_a")
    assert result.ok is True
    assert result.code == OK
    ss = service.get_story_sequence()
    assert isinstance(ss, StorySequence)
    assert ss.ordered_scene_ids == ("sc_a", "sc_b")
    assert ss.start_scene_id == "sc_a"


def test_save_invalid_story_sequence_fails(tmp_path):
    service = EditorApplicationService(_config_with_story_sequence(tmp_path))
    result = service.save_story_sequence(("sc_a", "sc_b"), "sc_z")
    assert result.ok is False
    assert result.code == INVALID_INPUT


def test_publication_readiness_missing_story_sequence(tmp_path):
    service = EditorApplicationService(_config_with_story_sequence(tmp_path))
    _accept(service)
    result = service.get_publication_readiness()
    assert result.ok is False
    assert result.code == NOT_FOUND


def test_publication_readiness_invalid_story_sequence(tmp_path):
    service = EditorApplicationService(_config_with_story_sequence(tmp_path))
    _accept(service)
    saved = service.save_story_sequence(("sc_wrong_001",), "sc_wrong_001")
    assert saved.ok is True
    result = service.get_publication_readiness()
    assert result.ok is False
    assert result.code == VALIDATION_FAILED


def test_publication_readiness_valid_story_sequence(tmp_path):
    service = EditorApplicationService(_config_with_story_sequence(tmp_path))
    _accept(service)
    saved = service.save_story_sequence((SCENE_ID,), SCENE_ID)
    assert saved.ok is True
    result = service.get_publication_readiness()
    assert result.ok is True
    assert result.code == OK
