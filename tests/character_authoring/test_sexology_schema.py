"""OD-LAB-PRODUCT-SEXOLOGY-01 / -DESCRIPTION-01 authoring schema tests.

These cover the additive Character Authoring semantic extensions without
relying on the VCP distribution. Sexology is OPTIONAL and descriptions are
optional identity fields; historical revisions that omit them must still load
and re-verify their snapshot hash.
"""

from __future__ import annotations

import pytest

from services.character_authoring import (
    CharacterAuthoringStore,
    CharacterAuthoringValidationError,
    CharacterSemantic,
)

SEXOLOGY_KEYS = (
    "intimacy_attitudes",
    "preferences",
    "emotional_dynamics",
    "communication",
    "vulnerabilities",
    "intimacy_boundaries",
)


def base_semantic(**overrides) -> dict:
    semantic = {
        "identity": {"display_name": "Áster"},
        "biography": "A biography.",
        "psychology": {
            "personality": ["curious"],
            "behavioral_traits": ["observant"],
            "emotional_tendencies": ["reflective"],
            "goals_motivations": ["understand"],
        },
        "speech": {"speech_style": "measured", "register": None},
        "character_relations": {
            "relational_tendencies": ["builds trust"],
            "attachment_traits": ["values consistency"],
        },
        "appearance": {"descriptors": ["dark hair"]},
        "boundaries": {"principles": ["respects refusal"]},
        "visual_identity": {},
    }
    semantic.update(overrides)
    return semantic


def sexology(**overrides) -> dict:
    value = {key: [] for key in SEXOLOGY_KEYS}
    value.update(overrides)
    return value


def ready_store(tmp_path) -> CharacterAuthoringStore:
    store = CharacterAuthoringStore(tmp_path / "store")
    store.create_character("atlas")
    store.create_version("atlas", "draft-v1", version_label="First draft")
    return store


def test_old_revision_without_new_fields_loads_and_verifies(tmp_path):
    store = ready_store(tmp_path)
    record = store.persist_revision("atlas", "draft-v1", "r1", base_semantic())

    loaded = store.load_revision("atlas", "draft-v1", "r1")
    assert loaded.snapshot_hash == record.snapshot_hash
    semantic = loaded.semantic.to_dict()
    assert "sexology" not in semantic
    assert "short_description" not in semantic["identity"]
    assert "detailed_description" not in semantic["identity"]


def test_descriptions_round_trip(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision(
        "atlas",
        "draft-v1",
        "r1",
        base_semantic(
            identity={
                "display_name": "Atlas",
                "short_description": "A quiet observer.",
                "detailed_description": "A long and detailed description.",
            }
        ),
    )
    identity = store.load_revision("atlas", "draft-v1", "r1").semantic.to_dict()[
        "identity"
    ]
    assert identity["short_description"] == "A quiet observer."
    assert identity["detailed_description"] == "A long and detailed description."


def test_sexology_six_field_object_round_trips(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision(
        "atlas",
        "draft-v1",
        "r1",
        base_semantic(
            sexology=sexology(intimacy_attitudes=["tender"], preferences=["slow"])
        ),
    )
    loaded = store.load_revision("atlas", "draft-v1", "r1").semantic.to_dict()[
        "sexology"
    ]
    assert set(loaded) == set(SEXOLOGY_KEYS)
    assert loaded["intimacy_attitudes"] == ["tender"]
    assert loaded["preferences"] == ["slow"]


def test_sexology_is_optional(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision("atlas", "draft-v1", "r1", base_semantic())
    # No sexology key is a valid, loadable shape.
    assert "sexology" not in store.load_revision("atlas", "draft-v1", "r1").semantic.to_dict()


def test_empty_sexology_lists_are_valid(tmp_path):
    store = ready_store(tmp_path)
    store.persist_revision(
        "atlas", "draft-v1", "r1", base_semantic(sexology=sexology())
    )
    loaded = store.load_revision("atlas", "draft-v1", "r1").semantic.to_dict()["sexology"]
    assert set(loaded) == set(SEXOLOGY_KEYS)
    assert all(value == [] for value in loaded.values())


def test_malformed_sexology_missing_key_fails():
    with pytest.raises(CharacterAuthoringValidationError):
        CharacterSemantic.from_dict(
            base_semantic(sexology={"preferences": [], "emotional_dynamics": [],
                                    "communication": [], "vulnerabilities": [],
                                    "intimacy_boundaries": []})
        )


def test_malformed_sexology_extra_key_fails():
    bad = sexology()
    bad["runtime_arousal"] = ["high"]
    with pytest.raises(CharacterAuthoringValidationError):
        CharacterSemantic.from_dict(base_semantic(sexology=bad))


def test_sexology_non_list_value_fails():
    with pytest.raises(CharacterAuthoringValidationError):
        CharacterSemantic.from_dict(
            base_semantic(sexology=sexology(preferences="not-a-list"))
        )


def test_sexology_non_string_item_fails():
    with pytest.raises(CharacterAuthoringValidationError):
        CharacterSemantic.from_dict(
            base_semantic(sexology=sexology(preferences=[1, 2, 3]))
        )


def test_non_string_description_fails():
    with pytest.raises(CharacterAuthoringValidationError):
        CharacterSemantic.from_dict(
            base_semantic(identity={"display_name": "Atlas", "short_description": 5})
        )
