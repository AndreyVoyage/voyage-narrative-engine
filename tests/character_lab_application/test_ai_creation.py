"""Facade AI-first creation: persistence, lifecycle, error mapping (offline)."""

from __future__ import annotations

import pytest

from services.character_draft import CharacterDraftError, scripted_provider
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationError,
    CharacterLabApplicationService,
)
from tests.character_draft._helpers import analysis_json, draft_json


@pytest.fixture
def service(tmp_path):
    return CharacterLabApplicationService(
        CharacterLabApplicationConfig(
            character_authoring_root=tmp_path / "authoring"
        )
    )


def test_create_flow_persists_draft_and_reloads(service):
    provider = scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()])
    analysis = service.start_ai_creation(
        display_name="Катя",
        description="shy",
        provider=provider,
        character_id_factory=lambda: "char_fixed0000000000000000000000000000000",
    )
    assert analysis.readiness.value == "READY_FOR_DRAFT"

    result = service.build_ai_draft(force=True)
    assert result.lifecycle_state == "DRAFT"
    assert result.character_id == "char_fixed0000000000000000000000000000000"

    loaded = service.load_revision_semantic(
        result.character_id, result.version_id, result.revision_id
    )
    assert loaded.lifecycle_state == "DRAFT"
    assert loaded.semantic["identity"]["display_name"] == "Катя"
    assert loaded.semantic["biography"] == "A shy young woman."
    assert loaded.semantic["psychology"]["personality"] == ["shy"]


def test_provider_error_maps_to_draft_ai_error(service):
    def failing(messages, system):
        raise CharacterDraftError(
            "API key is not configured. Set DEEPSEEK_API_KEY and retry."
        )

    with pytest.raises(CharacterLabApplicationError) as caught:
        service.start_ai_creation(
            display_name="Катя", description="shy", provider=failing
        )
    assert caught.value.code == "DRAFT_AI_ERROR"
    assert "DEEPSEEK_API_KEY" in caught.value.message


def test_continue_without_start_raises(service):
    with pytest.raises(CharacterLabApplicationError) as caught:
        service.continue_ai_creation(answer_text="x")
    assert caught.value.code == "DRAFT_AI_ERROR"


def test_ai_creation_never_approves_or_publishes(service):
    provider = scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()])
    service.start_ai_creation(display_name="Катя", description="shy", provider=provider)
    result = service.build_ai_draft(force=True)
    assert result.lifecycle_state == "DRAFT"
    pointer = service.read_version_lifecycle(result.character_id, result.version_id)
    assert pointer.lifecycle_state == "DRAFT"


def test_identical_input_creates_two_distinct_characters(service):
    provider_a = scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()])
    service.start_ai_creation(
        display_name="Катя",
        description="shy",
        provider=provider_a,
        character_id_factory=lambda: "char_aaaa0000000000000000000000000000000",
    )
    first = service.build_ai_draft(force=True)

    provider_b = scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), draft_json()])
    service.start_ai_creation(
        display_name="Катя",
        description="shy",
        provider=provider_b,
        character_id_factory=lambda: "char_bbbb0000000000000000000000000000000",
    )
    second = service.build_ai_draft(force=True)

    assert first.character_id != second.character_id
    # Both coexist; the second did not overwrite or reuse the first.
    first_loaded = service.load_revision_semantic(
        first.character_id, first.version_id, first.revision_id
    )
    second_loaded = service.load_revision_semantic(
        second.character_id, second.version_id, second.revision_id
    )
    assert first_loaded.semantic["biography"] == "A shy young woman."
    assert second_loaded.semantic["biography"] == "A shy young woman."


def test_malformed_draft_creates_no_character(service):
    provider = scripted_provider([analysis_json(readiness="READY_FOR_DRAFT"), "not json"])
    service.start_ai_creation(display_name="Катя", description="shy", provider=provider)
    with pytest.raises(CharacterLabApplicationError):
        service.build_ai_draft(force=True)
    assert len(service.list_authoring_characters()) == 0


def test_provider_failure_creates_no_character(service):
    def failing(messages, system):
        raise CharacterDraftError("provider error")

    with pytest.raises(CharacterLabApplicationError):
        service.start_ai_creation(display_name="Катя", description="shy", provider=failing)
    assert len(service.list_authoring_characters()) == 0
