"""Shared offline helpers for Test Dialogue tests."""

from __future__ import annotations

from services.character_authoring import compute_snapshot_hash
from services.character_dialogue import TestDialoguePin


def make_semantic(**overrides) -> dict:
    """A valid authored semantic with all eight required domains."""

    data = {
        "identity": {
            "display_name": "Марина",
            "short_description": "Сдержанная и наблюдательная.",
            "detailed_description": "Врач тридцати лет из приморского города.",
        },
        "biography": "Выросла у моря, давно работает врачом.",
        "psychology": {
            "personality": ["сдержанная", "наблюдательная"],
            "behavioral_traits": ["методичная"],
            "emotional_tendencies": ["спокойная"],
            "goals_motivations": ["помогать людям"],
        },
        "speech": {"speech_style": "кратко и по делу", "register": "нейтральный"},
        "character_relations": {
            "relational_tendencies": ["кооперативная"],
            "attachment_traits": ["надежная"],
        },
        "appearance": {"descriptors": ["тёмные волосы", "собранная"]},
        "boundaries": {"principles": ["не любит фамильярность"]},
        "visual_identity": {},
    }
    data.update(overrides)
    return data


def make_pin(
    semantic: dict,
    *,
    character_id: str = "char_marina",
    version_id: str = "v1",
    revision_id: str = "r1",
) -> TestDialoguePin:
    return TestDialoguePin(
        character_id=character_id,
        version_id=version_id,
        revision_id=revision_id,
        snapshot_hash=compute_snapshot_hash(semantic),
    )


def capturing_provider(response: str = "Ответ персонажа."):
    """Return (provider, calls) where calls records (messages, system) per call."""

    calls: list[dict] = []

    def _call(messages, system):
        calls.append({"messages": list(messages), "system": system})
        return response

    return _call, calls
