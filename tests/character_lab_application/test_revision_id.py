"""Sequential revision-id allocation (Character Lab usability slice, offline)."""

from __future__ import annotations

from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
    next_sequential_revision_id,
)


def _semantic(name: str) -> dict:
    return {
        "identity": {"display_name": name},
        "biography": f"Биография {name}.",
        "psychology": {
            "personality": ["curious"],
            "behavioral_traits": ["observant"],
            "emotional_tendencies": ["calm"],
            "goals_motivations": ["understand"],
        },
        "speech": {"speech_style": "plain", "register": None},
        "character_relations": {
            "relational_tendencies": ["cooperative"],
            "attachment_traits": ["secure"],
        },
        "appearance": {"descriptors": ["dark hair"]},
        "boundaries": {"principles": ["respects refusal"]},
        "visual_identity": {},
    }


def test_empty_yields_r1():
    assert next_sequential_revision_id([]) == "r1"


def test_single_r1_yields_r2():
    assert next_sequential_revision_id(["r1"]) == "r2"


def test_r1_r2_r3_yields_r4():
    assert next_sequential_revision_id(["r1", "r2", "r3"]) == "r4"


def test_custom_ids_do_not_shift_sequential():
    assert next_sequential_revision_id(["r1", "custom-rev", "r3"]) == "r4"


def test_leading_zero_is_treated_as_custom():
    assert next_sequential_revision_id(["r1", "r04"]) == "r2"


def test_uses_max_numeric_suffix():
    assert next_sequential_revision_id(["r2", "r10", "r3"]) == "r11"


def test_custom_only_yields_r1():
    assert next_sequential_revision_id(["custom-a", "custom-b"]) == "r1"


def test_service_next_available_revision_id(tmp_path):
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=tmp_path / "authoring")
    )
    service.create_character(
        character_id="char_a",
        version_id="v1",
        revision_id="r1",
        version_label="v1",
        semantic=_semantic("A"),
    )
    assert service.next_available_revision_id("char_a", "v1") == "r2"

    service.save_character(
        character_id="char_a",
        version_id="v1",
        revision_id="r2",
        semantic=_semantic("A"),
    )
    assert service.next_available_revision_id("char_a", "v1") == "r3"
