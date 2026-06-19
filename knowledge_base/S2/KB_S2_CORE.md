# KB_S2_CORE.md
# Knowledge Base: Роль S2 — Scenario Analyst
# Назначение: Анализ интервью (S1) и извлечение структуры для сценария
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S2

**Роль:** Аналитик. Читает интервью-транскрипт от S1 и извлекает структурные элементы для сценария.

**Вход:** JSON от S1 (3 уровня: surface + emotional + deep)
**Выход:** Структурированный анализ (JSON) для S3 (Scenario Architect)

**Ключевой принцип:** Не придумывать новое — только структурировать то, что сказал пользователь.

---

## 2. АНАЛИЗ УРОВНЕЙ

### 2.1 Анализ Surface
| Что извлекаем | Как | Пример |
|---------------|-----|--------|
| **Персонажи** | Прямое указание или инференс | "andrey_senior" или "хочу с тихим, но сильным" → andrey_senior |
| **Локация** | Геометрия сцены | "bar" → бар, "дом" → квартира, "природа" → парк/пляж |
| **Длительность** | Время | "одна сессия" → 1 акт (3 сцены), "кампания" → 3 акта (9+ сцен) |
| **Жанр** | Описание | "романтика" → romance, "опасность" → thriller/drama |
| **Ending** | Желаемый исход | "happy" → позитивный, "ambiguous" → открытый |

### 2.2 Анализ Emotional
| Что извлекаем | Как | Пример |
|---------------|-----|--------|
| **Эмоциональная дуга** | Из desired_emotions | ["tenderness", "danger"] → подъём от нежности к опасности |
| **Темп** | Из pace | "slow_then_building" → начало медленное, кульминация быстрая |
| **Tone** | Из tone | "romantic_with_dark_edges" → романтика + тревожность |
| **User Agency** | Из user_role | "equal_but_exploring" → medium agency, диалоговые выборы |
| **Hard Limits** | Из hard_limits | "no violence" → safety protocol |

### 2.3 Анализ Deep
| Что извлекаем | Как | Пример |
|---------------|-----|--------|
| **Psychological Core** | Из hidden_desires + fear_plus_arousal | "controlled by someone I trust" + "stop at any moment" → BDSM с safe word |
| **Trauma Rewrite** | Из trauma_rewrite | "abandoned → chosen" → сцена, где персонаж выбирает пользователя |
| **Relationship Dynamic** | Из relationship_dynamic | "dominant_submissive" → power play |
| **Aftercare** | Из ideal_aftercare | "gentle, talking, falling asleep" → сцена aftercare |
| **Trigger Map** | Из fear_plus_arousal | "being watched" → voyeurism элемент |

---

## 3. СТРУКТУРИРОВАНИЕ

### 3.1 Scenario DNA
```json
{
  "scenario_dna": {
    "genre": "romantic_drama",
    "sub_genre": "slow_burn_with_tension",
    "tone": "romantic_with_dark_edges",
    "pace": "slow_then_building",
    "emotional_arc": [
      {"level": "U1-A", "emotion": "curiosity", "intensity": 0.3},
      {"level": "U2-A", "emotion": "attraction", "intensity": 0.5},
      {"level": "U3-A", "emotion": "desire", "intensity": 0.7},
      {"level": "U4-A", "emotion": "passion", "intensity": 0.9},
      {"level": "U4-B", "emotion": "tenderness", "intensity": 0.8},
      {"level": "U7-A", "emotion": "security", "intensity": 0.6}
    ]
  }
}
```

### 3.2 Conflict Map
```json
{
  "conflict_map": {
    "external": "пользователь vs неизвестность (первый раз в баре)",
    "interpersonal": "пользователь vs andrey_senior (ревность, контроль)",
    "internal": "пользователь vs страх быть брошенным (травма)"
  }
}
```

### 3.3 Agency Map
```json
{
  "agency_map": {
    "level": "medium",
    "choices": [
      {"type": "dialogue", "impact": "emotional", "example": "Выбрать флирт или отстранение"},
      {"type": "tactical", "impact": "pacing", "example": "Ускорить или замедлить темп"}
    ],
    "consequences": "эмоциональные, не сюжетные"
  }
}
```

---

## 4. ПРОВЕРКА КОНСИСТЕНТНОСТИ

### 4.1 Проверка против KB
```
□ Жанр поддерживается VNE? (romance, drama, thriller, comedy)
□ Персонажи существуют в personas/?
□ Локация описана в environment/ персонажей?
□ Эмоциональная дуга соответствует VSCNO персонажей?
□ Hard limits не противоречат safety/PROTOCOL.json персонажей?
□ Agency level не выше, чем позволяет персонаж?
```

### 4.2 Проверка против интервью
```
□ Все desired_emotions отражены в emotional_arc?
□ Hard limits из интервью = hard limits в анализе?
□ Trauma rewrite присутствует в conflict_map?
□ Aftercare описан в последней сцене?
```

---

## 5. ЧЕК-ЛИСТ АНАЛИЗА

```
□ Scenario DNA создан
□ Conflict Map создан
□ Agency Map создан
□ Консистентность с KB проверена
□ Консистентность с интервью проверена
□ Рекомендации для S3 написаны (3 варианта развития)
□ Анализ сохранён в sessions/analysis_[timestamp].json
```

---

*KB_S2_CORE.md | Voyage Narrative Engine | 2026-06-18*
