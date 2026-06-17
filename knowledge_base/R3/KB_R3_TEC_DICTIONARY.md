# KB_R3_TEC_DICTIONARY.md
# Knowledge Base: TEC (Technical Erotic Components) Dictionary v2.3
# Источник: SPEC_PART_1_2 (раздел 2.3), ANDREY_SENIOR_MODULE_v1.json (tec_data)
# Назначение: канонические JSON-схемы для 8 TEC + 3 TEC_M
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. СТРУКТУРА TEC JSON

```json
{
  "tec_id": "TEC_001",
  "name": "Desire Style Profile",
  "category": "psychological",
  "validation_required": true,
  "data": {
    "primary": "SPON|RESP|MIX",
    "triggers": ["trigger_1", "trigger_2"],
    "contexts": ["context_1", "context_2"],
    "notes": "string"
  }
}
```

---

## 2. 8 TEC + 3 TEC_M

### TEC_001: Desire Style Profile (Профиль стиля желания)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | SPON / RESP / MIX | RESP | SPON |
| **triggers** | array | Что вызывает желание | ["proximity", "trust", "familiarity"] | ["novelty", "challenge", "visual"] |
| **contexts** | array | Где работает | ["intimate", "private", "evening"] | ["any", "public", "travel"] |
| **notes** | string | Комментарий | «Требуется контекст для возбуждения» | «Спонтанный в большинстве ситуаций» |

### TEC_002: Responsive Context Map (Карта responsive-контекстов)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | RESP / SPON / MIX | RESP | MIX |
| **triggers** | array | Контексты, которые работают | ["sauna", "evening", "warm_lighting"] | ["bar", "new_city", "competition"] |
| **contexts** | array | Где НЕ работает | ["public", "daytime", "stress"] | ["routine", "domestic", "commitment"] |
| **notes** | string | Комментарий | «Вечер + тепло + знакомое = responsive» | «Новое + вызов = responsive» |

### TEC_003: Mixed Mode Trigger Matrix (Матрица mixed-режимов)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | MIX | MIX | MIX |
| **triggers** | array | Ситуации для SPON | ["travel", "anonymity", "risk"] | ["morning", "home", "familiar"] |
| **contexts** | array | Ситуации для RESP | ["home", "intimate", "evening"] | ["travel", "bar", "new"] |
| **notes** | string | Комментарий | «Дома = RESP, в путешествии = SPON» | «Дома = SPON, в баре = RESP» |

### TEC_004: Erotic Trigger Inventory (Инвентарь эротических триггеров)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | RESP / SPON / MIX | RESP | SPON |
| **triggers** | array | Конкретные триггеры | ["gaze_3sec", "smile", "proximity_30cm"] | ["eye_contact", "competition", "surrender"] |
| **contexts** | array | Контекст триггера | ["intimate", "trust"] | ["power", "novelty"] |
| **notes** | string | Комментарий | «Взгляд 3 сек = проверка» | «Взгляд = начало охоты» |

### TEC_005: Attachment × Sexuality Integration (Интеграция привязанности и сексуальности)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | anxious / avoidant / secure | anxious | avoidant |
| **triggers** | array | Как привязанность влияет на секс | ["needs_closeness", "fear_of_loss", "aftercare_important"] | ["needs_distance", "fear_of_intimacy", "aftercare_minimal"] |
| **contexts** | array | Сексуальный стиль | ["responsive", "caring", "verbal"] | ["spontaneous", "dominant", "physical"] |
| **notes** | string | Комментарий | «Боится расстроить партнёра» | «Отталкивает после близости» |

**Критично:** TEC_005.style = стиль привязанности из R2 (Bowlby/Ainsworth). Если R2 сказал anxious — TEC_005.primary = anxious. Если R2 сказал avoidant — TEC_005.primary = avoidant. Не противоречить.

### TEC_006: Physiological Arousal Markers (Физиологические маркеры возбуждения)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | RESP / SPON / MIX | RESP | SPON |
| **triggers** | array | Тело: что меняется | ["breathing_accelerates", "blush", "eye_contact"] | ["muscle_tension", "pupil_dilation", "jaw_clench"] |
| **contexts** | array | Сенсорные маркеры | ["warmth", "touch", "scent"] | ["visual", "sound", "competition"] |
| **notes** | string | Комментарий | «Тело отвечает медленно, но надёжно» | «Тело отвечает быстро, агрессивно» |

### TEC_007: Linguistic Erotic Markers (Речевые эротические маркеры)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | RESP / SPON / MIX | RESP | SPON |
| **triggers** | array | Слова, фразы | ["привет", "всё нормально", "я рядом"] | ["ты смелая", "я вижу через тебя", "я победил»] |
| **contexts** | array | Тон, стиль | ["quiet", "philosophical", "caring"] | ["provocative", "challenging", "dominant"] |
| **notes** | string | Комментарий | «Философия = защитная маска» | «Провокация = охота» |

### TEC_008: Contextual Preference Matrix (Матрица контекстных предпочтений)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | RESP / SPON / MIX | RESP | MIX |
| **triggers** | array | Места, обстановки | ["home", "sauna", "kitchen", "evening"] | ["bar", "hotel", "travel", "morning"] |
| **contexts** | array | Атмосфера | ["warm", "intimate", "safe", "domestic"] | ["anonymity", "novelty", "risk", "public"] |
| **notes** | string | Комментарий | «Кухня = aftercare, сауна = страсть» | «Бар = охота, отель = победа» |

### TEC_M_001: Male Sexual Socialization (Мужская сексуальная социализация)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | gender_role | traditional / modern / conflicted | conflicted | traditional |
| **triggers** | array | Ожидания от мужчины | ["provider", "protector", "family_man"] | ["winner", "hunter", "alpha"] |
| **contexts** | array | Конфликт ролей | ["family vs desire", "stability vs passion"] | ["power vs emptiness", "win vs connection"] |
| **notes** | string | Комментарий | «Стабильность семейного человека vs скрытые желания» | «Победитель vs пустота после» |

### TEC_M_002: Male Arousal Pattern (Мужской паттерн возбуждения)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | visual / tactile / emotional / mixed | emotional / tactile | visual / tactile |
| **triggers** | array | Что возбуждает | ["emotional_closeness", "trust", "care"] | ["visual_stimulus", "competition", "novelty"] |
| **contexts** | array | Порядок возбуждения | ["emotion → body → desire»] | [«visual → body → desire»] |
| **notes** | string | Комментарий | «Нужно эмоциональное разрешение» | «Нужно визуальное подтверждение» |

### TEC_M_003: Male Orgasm & Resolution (Мужская оргастическая фаза)

| Поле | Тип | Описание | Пример (Андрей) | Пример (Егор) |
|------|-----|----------|-----------------|---------------|
| **primary** | string | integrated / disconnected / conflicted | conflicted | disconnected |
| **triggers** | array | Что после | ["guilt", "tenderness", "aftercare"] | ["emptiness", "next_target", "distance"] |
| **contexts** | array | Пиковая фаза | [«emotional_peak», «physical_release», «tenderness»] | [«physical_peak», «power_peak», «separation»] |
| **notes** | string | Комментарий | «После — нужна близость, но стыд» | «После — пустота, нужен новый охот» |

---

## 3. ВАЛИДАЦИЯ TEC

```
□ Все 8 TEC JSON имеют: tec_id, name, category, validation_required, data.
□ data содержит: primary, triggers[], contexts[], notes.
□ primary ∈ {SPON, RESP, MIX} для TEC_001–008.
□ TEC_005.primary = стиль привязанности из R2 (anxious/avoidant/secure).
□ TEC_M_001–003 используются только если gender=male (или по запросу).
□ validation_required = true для всех (R8 проверит).
□ Нет противоречий между TEC (например, TEC_001=SPON, но TEC_002=RESP с теми же triggers).
```

---

*KB_R3_TEC_DICTIONARY.md | Voyage Narrative Engine | 2026-06-16*
*Канон: 8 TEC + 3 TEC_M из SPEC_PART_1_2 и модулей персонажей*
