"""Application-service round-trip for the expanded editor fields.

Proves the thin facade preserves short_description / detailed_description /
sexology through create -> load_revision_semantic, and that the approval
lifecycle is unchanged when sexology is present.
"""

from __future__ import annotations

import pytest

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)

SEXOLOGY_KEYS = (
    "intimacy_attitudes",
    "preferences",
    "emotional_dynamics",
    "communication",
    "vulnerabilities",
    "intimacy_boundaries",
)


def semantic() -> dict:
    return {
        "identity": {
            "display_name": "Аня",
            "short_description": "Коротко",
            "detailed_description": "Подробно",
        },
        "biography": "Биография",
        "psychology": {
            "personality": ["тёплая"],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "", "register": None},
        "character_relations": {"relational_tendencies": [], "attachment_traits": []},
        "appearance": {"descriptors": []},
        "boundaries": {"principles": []},
        "sexology": {
            "intimacy_attitudes": ["нежная"],
            "preferences": ["медленно"],
            "emotional_dynamics": ["доверие"],
            "communication": ["словами"],
            "vulnerabilities": ["страх отвержения"],
            "intimacy_boundaries": ["без принуждения"],
        },
        "visual_identity": {},
    }


@pytest.fixture
def service(tmp_path) -> CharacterLabApplicationService:
    config = CharacterLabApplicationConfig(
        character_canon_root=None,
        character_authoring_root=tmp_path / "authoring",
        character_release_store_root=tmp_path / "releases",
    )
    return CharacterLabApplicationService(config)


def test_draft_save_reload_preserves_all_new_fields(service):
    result = service.create_character(
        character_id="anya",
        version_id="v1",
        revision_id="r1",
        version_label="Draft",
        semantic=semantic(),
    )
    assert result.character_id == "anya"

    loaded = service.load_revision_semantic("anya", "v1", "r1")
    assert loaded.semantic["identity"]["short_description"] == "Коротко"
    assert loaded.semantic["identity"]["detailed_description"] == "Подробно"
    assert set(loaded.semantic["sexology"]) == set(SEXOLOGY_KEYS)
    assert loaded.semantic["sexology"]["intimacy_attitudes"] == ["нежная"]
    assert loaded.semantic["sexology"]["intimacy_boundaries"] == ["без принуждения"]


def test_approval_lifecycle_unchanged_with_sexology(service):
    result = service.create_character(
        character_id="anya",
        version_id="v1",
        revision_id="r1",
        version_label="Draft",
        semantic=semantic(),
    )
    submitted = service.submit_for_approval(
        character_id="anya",
        version_id="v1",
        revision_id="r1",
        snapshot_hash=result.snapshot_hash,
    )
    assert submitted.lifecycle_state == "PENDING_APPROVAL"

    approved = service.approve_as_canon(
        character_id="anya",
        version_id="v1",
        revision_id="r1",
        snapshot_hash=result.snapshot_hash,
        decided_by="owner",
    )
    assert approved.lifecycle_state == "APPROVED_AS_CANON"
