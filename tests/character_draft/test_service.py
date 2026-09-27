"""Interview flow + draft builder + deterministic ID policy (offline)."""

from __future__ import annotations

import json

import pytest

from services.character_authoring import CharacterSemantic, validate_identifier
from services.character_draft import (
    CharacterDraftError,
    CharacterDraftService,
    Readiness,
    scripted_provider,
)
from services.character_draft.service import new_character_id
from tests.character_draft._helpers import analysis_json, draft_json


def test_new_character_id_matches_identifier_grammar():
    character_id = new_character_id()
    assert character_id.startswith("char_")
    assert validate_identifier(character_id, field="character_id") == character_id


def test_identical_input_can_yield_distinct_default_ids():
    assert new_character_id() != new_character_id()


def test_injected_character_id_factory_is_used():
    service = CharacterDraftService(
        scripted_provider([analysis_json()]),
        character_id_factory=lambda: "char_injected00000000000000000000000000",
    )
    assert service.create_character_id() == "char_injected00000000000000000000000000"


def test_analyze_returns_questions():
    service = CharacterDraftService(scripted_provider([analysis_json()]))
    result = service.analyze("Катя", "shy young woman")
    assert result.readiness is Readiness.NEEDS_INPUT
    assert len(result.questions) == 1


def test_answer_updates_analysis_adaptively():
    service = CharacterDraftService(
        scripted_provider(
            [analysis_json(), analysis_json(readiness="READY_FOR_DRAFT")]
        )
    )
    service.analyze("Катя", "shy")
    result = service.answer("she wants to be seen")
    assert result.readiness is Readiness.READY_FOR_DRAFT


def test_ready_state_terminates_interview():
    service = CharacterDraftService(
        scripted_provider([analysis_json(readiness="READY_FOR_DRAFT")])
    )
    result = service.analyze("Катя", "rich description")
    assert result.readiness is Readiness.READY_FOR_DRAFT
    assert service.answer("anything") is result  # no-op when already ready


def test_build_draft_requires_readiness_unless_forced():
    service = CharacterDraftService(scripted_provider([analysis_json()]))
    service.analyze("Катя", "shy")
    with pytest.raises(CharacterDraftError):
        service.build_draft(force=False)


def test_force_build_draft_preserves_known_and_unknown():
    service = CharacterDraftService(
        scripted_provider([analysis_json(), draft_json()])
    )
    service.analyze("Катя", "shy")
    semantic = service.build_draft(force=True)
    assert isinstance(semantic, CharacterSemantic)
    data = semantic.to_dict()
    assert data["identity"]["display_name"] == "Катя"  # user's explicit name wins
    assert data["identity"]["short_description"] == "Shy"
    assert data["identity"]["detailed_description"] == "A shy character"
    assert data["biography"] == "A shy young woman."
    assert data["psychology"]["personality"] == ["shy"]
    assert data["visual_identity"] == {}


def test_loop_fail_safe_prevents_endless_interview():
    service = CharacterDraftService(
        scripted_provider([analysis_json()] * 20), max_rounds=3
    )
    service.analyze("Катя", "shy")  # round 1
    service.answer("a")  # round 2
    service.answer("b")  # round 3
    with pytest.raises(CharacterDraftError):
        service.answer("c")  # exceeds max rounds


def test_sexology_preserved_when_present():
    service = CharacterDraftService(
        scripted_provider(
            [
                analysis_json(),
                draft_json(
                    sexology={
                        "intimacy_attitudes": ["tender"],
                        "preferences": [],
                        "emotional_dynamics": [],
                        "communication": [],
                        "vulnerabilities": [],
                        "intimacy_boundaries": [],
                    }
                ),
            ]
        )
    )
    service.analyze("Катя", "shy")
    semantic = service.build_draft(force=True)
    assert semantic.to_dict()["sexology"]["intimacy_attitudes"] == ["tender"]


def test_malformed_sexology_fails_closed():
    service = CharacterDraftService(
        scripted_provider(
            [analysis_json(), draft_json(sexology={"intimacy_attitudes": ["x"]})]
        )
    )
    service.analyze("Катя", "shy")
    with pytest.raises(CharacterDraftError):
        service.build_draft(force=True)


def test_malformed_draft_response_fails_closed():
    service = CharacterDraftService(
        scripted_provider([analysis_json(), "this is not JSON"])
    )
    service.analyze("Катя", "shy")
    with pytest.raises(CharacterDraftError):
        service.build_draft(force=True)


def test_missing_semantic_object_fails_closed():
    service = CharacterDraftService(
        scripted_provider([analysis_json(), json.dumps({"no_semantic": True})])
    )
    service.analyze("Катя", "shy")
    with pytest.raises(CharacterDraftError):
        service.build_draft(force=True)


def test_unsupported_domain_is_not_persisted():
    # A top-level domain outside the Character Authoring schema must fail closed.
    service = CharacterDraftService(
        scripted_provider(
            [analysis_json(), draft_json(unknown_domain={"x": 1})]
        )
    )
    service.analyze("Катя", "shy")
    with pytest.raises(CharacterDraftError):
        service.build_draft(force=True)
