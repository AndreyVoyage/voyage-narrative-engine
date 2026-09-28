"""Deterministic persona/context renderer for Test Dialogue.

Renders the authored :class:`CharacterSemantic` (as a plain mapping) into a
stable, human-readable persona block. It never serializes filesystem paths,
binary/media data, or ``visual_identity`` (which is structurally empty in V1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def persona_context(semantic: Mapping[str, Any]) -> str:
    """Return a deterministic persona text block from an authored semantic."""

    identity = _mapping(semantic.get("identity"))
    lines: list[str] = []

    display_name = str(identity.get("display_name", "")).strip()
    if display_name:
        lines.append(f"Имя: {display_name}")

    short = str(identity.get("short_description", "")).strip()
    if short:
        lines.append(f"Краткое описание: {short}")

    detailed = str(identity.get("detailed_description", "")).strip()
    if detailed:
        lines.append(f"Подробное описание: {detailed}")

    biography = str(semantic.get("biography", "")).strip()
    if biography:
        lines.append(f"Биография: {biography}")

    psychology = _mapping(semantic.get("psychology"))
    for key, label in (
        ("personality", "Личность"),
        ("behavioral_traits", "Поведение"),
        ("emotional_tendencies", "Эмоции"),
        ("goals_motivations", "Цели/мотивация"),
    ):
        values = _as_list(psychology.get(key))
        if values:
            lines.append(f"{label}: {', '.join(values)}")

    speech = _mapping(semantic.get("speech"))
    speech_style = str(speech.get("speech_style", "")).strip()
    if speech_style:
        lines.append(f"Стиль речи: {speech_style}")
    register = speech.get("register")
    if register is not None and str(register).strip():
        lines.append(f"Регистр речи: {register}")

    relations = _mapping(semantic.get("character_relations"))
    relational = _as_list(relations.get("relational_tendencies"))
    if relational:
        lines.append(f"Отношения: {', '.join(relational)}")
    attachment = _as_list(relations.get("attachment_traits"))
    if attachment:
        lines.append(f"Привязанность: {', '.join(attachment)}")

    appearance = _mapping(semantic.get("appearance"))
    descriptors = _as_list(appearance.get("descriptors"))
    if descriptors:
        lines.append(f"Внешность: {', '.join(descriptors)}")

    boundaries = _mapping(semantic.get("boundaries"))
    principles = _as_list(boundaries.get("principles"))
    if principles:
        lines.append(f"Границы: {', '.join(principles)}")

    # Sexology is OPTIONAL baseline authored information. It is framed here as
    # baseline attitudes/preferences -- explicitly NOT current desire, arousal,
    # consent or relationship state.
    sexology = semantic.get("sexology")
    if isinstance(sexology, Mapping):
        sex_lines: list[str] = []
        for key, label in (
            ("intimacy_attitudes", "Отношение к близости"),
            ("preferences", "Предпочтения"),
            ("emotional_dynamics", "Эмоциональная динамика"),
            ("communication", "Стиль коммуникации"),
            ("vulnerabilities", "Уязвимости"),
            ("intimacy_boundaries", "Границы близости"),
        ):
            values = _as_list(sexology.get(key))
            if values:
                sex_lines.append(f"{label}: {', '.join(values)}")
        if sex_lines:
            lines.append(
                "Сексология (базовые авторские установки, НЕ текущее "
                "состояние/согласие):"
            )
            lines.extend(f"  {item}" for item in sex_lines)

    return "\n".join(lines)


def display_name(semantic: Mapping[str, Any]) -> str:
    """Return the human-readable character name, with a safe fallback."""

    identity = _mapping(semantic.get("identity"))
    name = str(identity.get("display_name", "")).strip()
    return name or "Персонаж"


__all__ = ["display_name", "persona_context"]
