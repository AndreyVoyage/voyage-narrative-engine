# 04_MIGRATION_GUIDE.md
# Руководство по миграции монолита на модульную структуру
# Версия: 2.0.0

---

## 1. Подготовка

- Создать структуру папок для персонажа (см. `01_MODULAR_ARCHITECTURE.md`).
- Подготовить шаблоны модулей (см. `02_MODULE_SPECS.md`).
- Сделать резервную копию исходного монолитного файла.

**Исходный файл:** `personas/KIRA_MODULE_v14.json`

---

## 2. Карта соответствия полей

| Поле в монолите | Целевой модуль | Примечание |
|----------------|----------------|------------|
| `id`, `name`, `version` | `INDEX.json` (метаданные) | Не в IDENTITY, а в манифест |
| `variables` (age, height, hair_color...) | `core/IDENTITY.json` → `variables` | |
| `anatomic_anchor` | `core/IDENTITY.json` → `anatomic_anchor` | Был в `visual_data`, теперь в core |
| `psychology` (trauma, core_conflict, secret_desire, shame_layers) | `psychology/BASE.json` | |
| `psychology` (responsive_desire, Basson) | `psychology/BASE.json` → `desire_model` | |
| `psychology` (response_to_male_tactics, attachment_response) | `psychology/BASE.json` → `response_to_tactics` | |
| `arousal_specificity` (Chivers) | `psychology/AROUSAL.json` | НОВЫЙ файл |
| `erotic_plasticity` (Baumeister) | `psychology/PLASTICITY.json` | НОВЫЙ файл |
| `object_of_desire` (Bogaert) | `psychology/ODSC.json` | НОВЫЙ файл |
| `attachment_sexuality` (Birnbaum) | `psychology/ATTACHMENT.json` | НОВЫЙ файл |
| `modes` (shy_to_bitch, emotional_level_map) | `levels/` (14 файлов) | Каждый подуровень — отдельный файл |
| `speech_profile` (по подуровням) | `levels/U*.json` → `speech_profile` | 14 файлов |
| `dynamic_visuals` (по подуровням) | `levels/U*.json` → `dynamic_visuals` | |
| `state_triggers` (общие и по уровням) | `levels/U*.json` → `state_triggers` | |
| `relationships` (user, sergey, maksim, marina) | `relationships/MATRIX.json` | |
| `visual_data.prompt_base`, `variations`, `anti_prompts`, `seed` | `visual/PROMPT_BASE.json` | |
| `visual_data.anatomic_anchor` | `core/IDENTITY.json` → `anatomic_anchor` | (если не дублируется) |
| `visual_data.generation_history` | `visual/GENERATION_HISTORY.json` | Отдельный файл |
| `memory.trust_levels` | `memory/TRUST.json` | |
| `memory.attraction_levels` | `memory/ATTRACTION.json` | |
| `memory.history` | `memory/HISTORY.json` | |
| `memory.flags` | `memory/FLAGS.json` | |
| `autonomous.activities` | `autonomous/ACTIVITIES.json` | |
| `autonomous.message_templates` | `autonomous/TEMPLATES.json` | |
| `regression_triggers` | `safety/PROTOCOL.json` → `regression_triggers` | |
| `internal_state` (desire, anxiety...) | **НЕ в модулях!** → `state/STATE.json` | Runtime |
| `vscno` (4 оси) | **НЕ в модулях!** → `state/STATE.json` | Runtime |
| `algorithms`, `safety`, `format`, `volume` | `safety/PROTOCOL.json` + `INDEX.json` | |

---

## 3. Новые модули (не из монолита, создаются на основе психологии)

| Модуль | Источник | Зачем нужен |
|--------|----------|-------------|
| `psychology/DEFENSE_MECHANISMS.json` | Анализ поведения Киры | Защиты по уровням тревоги |
| `psychology/VALUE_SYSTEM.json` | Конфликты autonomy vs belonging | Ценности и их столкновения |
| `psychology/IFS_PARTS.json` | IFS (Schwartz) | 5 частей личности |
| `psychology/COGNITIVE_DISTORTIONS.json` | Beck CBT | Как Кира искажает реальность |
| `psychology/AFFECT_REGULATION.json` | Стратегии регуляции аффекта | Как справляется с эмоциями |
| `psychology/ATTACHMENT_STYLE_DYNAMIC.json` | Bowlby + Birnbaum | Как стиль привязанности меняется |
| `physiology/AROUSAL_SIGNATURES.json` | Физиология возбуждения | Тело по шкале desire 0-10 |
| `physiology/CORTICAL_ACTIVATION.json` | ЦНС пороги | Замедленные/порывистые движения |
| `physiology/MICROEXPRESSIONS.json` | Ekman | Мимика по уровням |
| `physiology/EROGENOUS_MAP.json` | Карта эрогенных зон | 5 зон с чувствительностью |
| `sexology/RESPONSE_CYCLE.json` | Basson + Masters-Johnson | 6 фаз цикла |
| `sexology/EROTIC_SCRIPTS.json` | Gagnon & Simon | Типичные сценарии |
| `sexology/DYSPHORIA_AND_SHAME.json` | Посткоитальный стыд | Стыд и его проявления |
| `sexology/FANTASY_VS_REALITY.json` | Фантазии vs поведение | Контраст мыслей и действий |
| `dynamics/RIVALRY_TRIANGLE.json` | Конкуренция в сцене | Sergey vs Maksim за Киру |
| `dynamics/CHARACTER_GROWTH_PATH.json` | Арки развития | U1→U7, интеграция травмы |
| `meta/ATTRIBUTION_BIAS.json` | Интерпретация действий | Враждебность vs благосклонность |
| `meta/UNRELIABLE_NARRATOR.json` | Когда Кира врёт себе | 4 типа лжи |
| `meta/COHERENCE_VETO.json` | Форс-мажор | Паническая атака, опьянение |
| `environment/SENSORY_PROCESSING.json` | НЛП | Репрезентативные системы |
| `environment/SPATIAL_BEHAVIOR.json` | Проксемика | Зоны личного пространства |
| `evolution/AROUSAL_AS_MOTIVATION.json` | Crosby & Buss 2021 | Возбуждение смещает мотивацию |
| `attachment/BEHAVIORAL_SYSTEMS.json` | Shaver, Hazan, Bradshaw | Три системы: привязанность, забота, секс |
| `sexual_scripts/EROTIC_SCRIPTS.json` | Gagnon & Simon 1973 | Кто, с кем, что, где, когда |
| `trauma_ptsd/THREE_LEVELS.json` | Almas & Benestad 2017 | Когнитивный, эмоциональный, телесный |

---

## 4. Пошаговая инструкция миграции

### Шаг 1. Создать папку
```bash
mkdir -p personas/kira/{core,psychology,levels,relationships,visual,memory,autonomous,safety,dynamics,meta,environment,physiology,sexology,evolution,attachment,sexual_scripts,trauma_ptsd}
```

### Шаг 2. Создать INDEX.json
Извлечь `id`, `name`, `version` из монолита. Указать список модулей.

### Шаг 3. Разобрать core/IDENTITY.json
- `variables` (age, height, hair_color, eye_color, clothing_signature).
- `anatomic_anchor` (из `visual_data` или отдельно).

### Шаг 4. Разобрать psychology/BASE.json
- `trauma_anchor`, `core_conflict`, `secret_desire`, `shame_layers`.
- `desire_model` (type: responsive, source: Basson).
- `response_to_tactics`.

### Шаг 5. Создать уровни (levels/U1-A.json … U7-B.json)
- Для каждого подуровня из `speech_profile` и `dynamic_visuals`:
  - `level_id`, `speech_profile`, `dynamic_visuals`.
  - `state_triggers` (если есть для уровня).
  - `lighting` (можно вынести в LIGHTING_MAP).
  - **НОВОЕ:** `active_defenses`, `cognitive_distortions`, `ifs_part` (из анализа).

### Шаг 6. Создать relationships/MATRIX.json
- Перенести `relationships` объект.

### Шаг 7. Создать visual/PROMPT_BASE.json
- `prompt_base`, `variations`, `anti_prompts`, `seed`.
- `anatomic_anchor` уже в IDENTITY.
- `generation_history` → `visual/GENERATION_HISTORY.json` (пустой массив).

### Шаг 8. Создать memory/*.json
- `TRUST.json`, `ATTRACTION.json`, `HISTORY.json`, `FLAGS.json`.

### Шаг 9. Создать autonomous/*.json
- `ACTIVITIES.json`, `TEMPLATES.json`.

### Шаг 10. Создать safety/PROTOCOL.json
- `hard_limits`, `soft_limits`, `stop_words`.
- `regression_triggers`.

### Шаг 11. Создать НОВЫЕ модули (на основе анализа)
- `psychology/DEFENSE_MECHANISMS.json` — из поведенческих паттернов.
- `psychology/IFS_PARTS.json` — 5 частей (Искорка, Сталь, Бабочка, Стерва, Соба).
- `psychology/COGNITIVE_DISTORTIONS.json` — 5 искажений (Beck).
- `physiology/AROUSAL_SIGNATURES.json` — шкала 0-10.
- `sexology/RESPONSE_CYCLE.json` — 6 фаз (Basson).
- `meta/UNRELIABLE_NARRATOR.json` — 4 типа лжи.
- `environment/SENSORY_PROCESSING.json` — доминантный кинестетик.
- И остальные (см. таблицу в разделе 3).

### Шаг 12. Создать ASSEMBLY.md
Написать инструкцию по сборке (см. `03_ASSEMBLY_GUIDE.md`).

### Шаг 13. Валидация
- Все обязательные поля из `INDEX.json` присутствуют.
- Ни одно поле из монолита не потеряно.
- JSON валидны.

### Шаг 14. Тестирование
- Собрать персонажа через `assemble_persona()`.
- Сравнить с оригинальным монолитом — эквивалентны.
- Тестовая сессия.

---

## 5. Пример: перенос speech_profile для U3-A

**Исходный монолит:**
```json
"speech_profile": {
  "U3-A": {
    "tone": "внутренний конфликт, голос дрожит",
    "pace": "рваный, с паузами",
    "vocabulary": "смешение спортивной решительности и женской неуверенности",
    "thought_length": "мысли длинные, полные стыда и желания",
    "action_detail": "замирание, покраснение, невольное приближение",
    "catchphrases": ["Я не должна так думать...", "Почему ты смотришь так?"]
  }
}
```

**Целевой файл levels/U3-A.json:**
```json
{
  "level_id": "U3-A",
  "speech_profile": {
    "tone": "внутренний конфликт, голос дрожит",
    "pace": "рваный, с паузами",
    "vocabulary": "смешение спортивной решительности и женской неуверенности",
    "thought_length": "мысли длинные, полные стыда и желания",
    "action_detail": "замирание, покраснение, невольное приближение",
    "catchphrases": ["Я не должна так думать...", "Почему ты смотришь так?"]
  },
  "dynamic_visuals": "покраснение шеи и декольте, дрожь рук, мокрые волосы, тяжёлое дыхание",
  "state_triggers": { "on_gaze": "SET vscno.ОГ +1" },
  "lighting": "dramatic Rembrandt, high contrast, conflict tension",
  "active_defenses": ["repression", "intellectualization"],
  "cognitive_distortions": ["emotional_reasoning", "should_statements"],
  "ifs_part": "exile_butterfly"
}
```

---

## 6. Что делать с runtime-состоянием

`internal_state` и `vscno` **не входят в модули**. Они хранятся в `state/STATE.json`.
- При миграции: скопировать текущие значения из монолита в `state/STATE.json`.
- В будущем: модули содержат только дефолтные значения.

---

## 7. Чек-лист после миграции

- [ ] Создана папка `personas/kira/`.
- [ ] Создан `INDEX.json`.
- [ ] Создан `core/IDENTITY.json`.
- [ ] Создан `psychology/BASE.json`.
- [ ] Созданы все 14 файлов уровней.
- [ ] Создан `relationships/MATRIX.json`.
- [ ] Создан `visual/PROMPT_BASE.json`.
- [ ] Созданы файлы памяти.
- [ ] Создан `safety/PROTOCOL.json`.
- [ ] Создан `autonomous/` (если есть).
- [ ] Созданы НОВЫЕ модули (DEFENSE, IFS, COGNITIVE, physiology, sexology, meta, environment, dynamics).
- [ ] Создан `ASSEMBLY.md`.
- [ ] Проведена валидация и тестовая сборка.

---

## 8. Типичные проблемы

| Проблема | Решение |
|----------|---------|
| Некоторые уровни отсутствуют в монолите | Создать на основе соседних или оставить заглушки |
| `anatomic_anchor` размазан по разным местам | Собрать в IDENTITY.json, выбирая наиболее детальное описание |
| Нет явного разделения trust/attraction | Оставить как есть, уточнить позже |
| Монолит содержит кастомные поля | Добавить в соответствующий модуль или создать новый |

---

*Документ 04 из 09*
