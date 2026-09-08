#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic, character-agnostic random-scenario foundation for Companion.

No LLM, no provider, no network. A small generic pool of Russian scene
fragments; :func:`random_scenario` composes one editable ``{place, time,
situation, mood}`` suggestion, :func:`random_field` re-rolls a single field.
Nothing here is part of any Character Package -- these are generic UI
suggestions the user edits before starting a chat.
"""

from __future__ import annotations

import random
from typing import Dict, Optional

SCENE_FIELDS = ("place", "time", "situation", "mood")

_POOLS: Dict[str, tuple] = {
    "place": (
        "Небольшая кухня в квартире",
        "Столик у окна в кафе",
        "Городской парк, скамейка у пруда",
        "Крыша дома вечером",
        "Книжный магазин, отдел поэзии",
        "Набережная реки",
        "Уютная гостиная с торшером",
        "Тихий двор старого дома",
        "Вагон ночного поезда",
        "Терраса летнего кафе",
    ),
    "time": (
        "Раннее утро",
        "Позднее утро буднего дня",
        "Полдень",
        "Ранний вечер",
        "Поздний вечер",
        "Глубокая ночь",
        "Пасмурный день",
        "Первый тёплый день весны",
    ),
    "situation": (
        "Случайная встреча после долгого перерыва",
        "Разговор за чашкой чая без особого повода",
        "Ждут общего знакомого, который опаздывает",
        "Пережидают дождь под навесом",
        "Обсуждают только что просмотренный фильм",
        "Делают перерыв в работе над общим проектом",
        "Знакомятся впервые через общих друзей",
        "Возвращаются домой после долгой прогулки",
    ),
    "mood": (
        "Спокойное, чуть уставшее",
        "Лёгкое и непринуждённое",
        "Задумчивое",
        "Тёплое, доверительное",
        "Слегка напряжённое, осторожное",
        "Приподнятое, с ноткой волнения",
        "Меланхоличное",
        "Игривое",
    ),
}


def _rng(seed: Optional[int]) -> random.Random:
    return random.Random(seed)


def random_field(field: str, *, seed: Optional[int] = None) -> str:
    if field not in _POOLS:
        raise ValueError(f"unknown scenario field {field!r}; expected one of {SCENE_FIELDS}")
    return _rng(seed).choice(_POOLS[field])


def random_scenario(*, seed: Optional[int] = None) -> Dict[str, str]:
    """A full editable suggestion. Deterministic for a given ``seed``."""
    rng = _rng(seed)
    return {field: rng.choice(_POOLS[field]) for field in SCENE_FIELDS}
