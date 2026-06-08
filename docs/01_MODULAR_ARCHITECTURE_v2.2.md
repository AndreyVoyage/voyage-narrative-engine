Файл: 01_MODULAR_ARCHITECTURE_v2.2.md

```markdown
# 01_MODULAR_ARCHITECTURE.md
# Voyage Narrative Engine — Модульная Архитектура Персонажей
# Версия: 2.2.0 (исправлено по аудиту ANA v1.0, добавлены scene_id, global, VSCNO приоритет, конфликт триггеров)

## 1. ФИЛОСОФИЯ МОДУЛЬНОСТИ

### 1.1 Принципы (5 штук)

| Принцип | Описание | Аналогия |
|---------|----------|----------|
| **Single Source of Truth** | Каждый факт о персонаже — ровно в одном файле | Git-репозиторий |
| **Assembly on Demand** | Собираем только нужное для текущей сцены | Docker-контейнеры |
| **Versioned Immutability** | Файл неизменяем после релиза. Изменение = новая версия | Функциональное программирование |
| **Cross-Referential Integrity** | Модули ссылаются, но не дублируют | Реляционная БД |
| **Runtime Overlay** | State накладывается поверх модуля | Photoshop-слои |

### 1.2 Почему лучше монолита

```

МОНОЛИТ (KIRA_MODULE_v14.json, 1000+ строк)
├── LLM видит всё → перегрузка контекста
├── Изменить U3-A → риск сломать U5-B
├── Новый персонаж → копировать 1000 строк
└── Сценарий дублирует target_level → рассинхронизация

МОДУЛИ (30+ файлов, 30-150 строк каждый)
├── LLM видит только нужное → фокус
├── Изменить U3-A → трогаем только U3-A.json
├── Новый персонаж → берём _TEMPLATE, заполняем
└── Сценарий ссылается на levels/ → автосинхронизация

```

## 2. ДЕРЕВО ПАПОК И ФАЙЛОВ (унифицированное)

```

personas/
└── _TEMPLATE/                          ← Шаблон для новых персонажей
├── ASSEMBLY.md
├── INDEX.json
├── core/IDENTITY.json
├── psychology/
│   ├── BASE.json
│   ├── AROUSAL.json
│   ├── PLASTICITY.json
│   ├── ODSC.json
│   ├── ATTACHMENT.json
│   ├── TACTICS.json
│   ├── DEFENSE_MECHANISMS.json
│   ├── VALUE_SYSTEM.json
│   ├── ATTACHMENT_STYLE_DYNAMIC.json
│   ├── AFFECT_REGULATION.json
│   ├── IFS_PARTS.json
│   └── COGNITIVE_DISTORTIONS.json
├── physiology/
│   ├── AROUSAL_SIGNATURES.json
│   ├── CORTICAL_ACTIVATION.json
│   ├── MICROEXPRESSIONS.json
│   └── EROGENOUS_MAP.json
├── sexology/
│   ├── RESPONSE_CYCLE.json
│   ├── EROTIC_SCRIPTS.json
│   ├── DYSPHORIA_AND_SHAME.json
│   └── FANTASY_VS_REALITY.json
├── levels/LEVEL_TEMPLATE.json
├── relationships/MATRIX.json
├── dynamics/
│   ├── RIVALRY_TRIANGLE.json
│   └── CHARACTER_GROWTH_PATH.json
├── visual/
│   ├── PROMPT_BASE.json
│   ├── LIGHTING_MAP.json
│   └── GENERATION_HISTORY.json
├── memory/
│   ├── TRUST.json
│   ├── ATTRACTION.json
│   ├── HISTORY.json
│   ├── FLAGS.json
│   └── emotional_anchors.json
├── autonomous/
│   ├── ACTIVITIES.json
│   └── TEMPLATES.json
├── meta/
│   ├── ATTRIBUTION_BIAS.json
│   ├── UNRELIABLE_NARRATOR.json
│   └── COHERENCE_VETO.json
├── environment/
│   ├── SENSORY_PROCESSING.json
│   └── SPATIAL_BEHAVIOR.json
├── evolution/
│   └── AROUSAL_AS_MOTIVATION.json
├── attachment/
│   └── BEHAVIORAL_SYSTEMS.json
├── sexual_scripts/
│   └── EROTIC_SCRIPTS.json
├── trauma_ptsd/
│   └── THREE_LEVELS.json
└── safety/PROTOCOL.json

├── kira/                               ← Кира (реализация)
├── sergey/
├── marina/
└── maksim/

```

## 3. ПРИНЦИПЫ СВЯЗЫВАНИЯ И КОНФЛИКТ-РЕЗОЛЮЦИЯ

### 3.1 Приоритеты (от высшего к низшему)

| Приоритет | Источник | Примечание |
|-----------|----------|------------|
| 1 | **Runtime состояние** (`state/STATE.json`) | Всегда побеждает |
| 2 | **Оверрайды сценария** (`scenarios/*.json`) | Временно, для одной сессии |
| 3 | **Модуль уровня** (`levels/{current}.json`) | Перезаписывает базовые модули |
| 4 | **Специализированные модули** (arousal, attachment, trauma) | Влияют на отдельные поля |
| 5 | **Базовый модуль** (`psychology/BASE.json`) | Самый общий уровень |
| 6 | **Модуль идентичности** (`core/IDENTITY.json`) | Только неизменяемые данные |

### 3.2 Разрешение конфликтов

```

Если два модуля определяют одно поле:
→ Побеждает тот, у кого выше version в INDEX.json
→ Если версии равны — приоритет по таблице выше
→ Если не разрешается автоматически — сборщик выдаёт ошибку

```

### 3.3 Правила обновления VSCNO (из `10_STATE_SPECIFICATION.md`)

При обновлении VSCNO (например, из `state_triggers`) сумма четырёх осей всегда должна оставаться 10. Если сумма нарушается, применяется приоритет:

1. **ВЛ** (Влечение) – сохраняется в первую очередь
2. **ОГ** (Оглядка/возбуждение) – сохраняется во вторую
3. **НЖ** (Напряжение) – затем
4. **СТ** (Стыд) – корректируется в последнюю очередь

### 3.4 Конфликт триггеров (одновременное изменение internal_state)

Если несколько триггеров срабатывают одновременно и пытаются изменить одно поле (например, `desire`), применяется **изменение с максимальным абсолютным значением**. Пример:

- Триггер A: `desire +2`
- Триггер B: `desire -1`
- Результат: `+2` (побеждает максимальное абсолютное изменение)

## 4. РОЛЬ INDEX.json И ASSEMBLY.md

### 4.1 INDEX.json — Манифест (пример)

```json
{
  "id": "kira",
  "name": "Кира",
  "version": "2.1.0",
  "schema_version": "1.0.0",
  "default_level": "U2-A",
  "default_ag_level": 1,
  "compatible_scenarios": ["sauna_quartet", "promenade", "cafe_date"],
  "modules": {
    "core/IDENTITY.json": { "version": "1.0.0", "required": true },
    "psychology/BASE.json": { "version": "1.2.0", "required": true },
    ...
  },
  "dependencies": {
    "persona_schema": "v3_2_VOYAGE.json",
    "state_template": "STATE_TEMPLATE_v2.json"
  }
}
```

Полный список модулей см. в 08_INDEX.json.

4.2 ASSEMBLY.md — Инструкция для LLM (краткая)

```markdown
# ASSEMBLY: Кира

## Всегда загружать
- core/IDENTITY.json
- psychology/BASE.json
- safety/PROTOCOL.json

## По current_level (из state)
- levels/{current_level}.json
- visual/LIGHTING_MAP.json#/level_{current_level}

## Если в сцене другие персонажи
- relationships/MATRIX.json

## Если сценарий эротический/романтический
- physiology/AROUSAL_SIGNATURES.json
- sexology/RESPONSE_CYCLE.json
- sexology/EROTIC_SCRIPTS.json

## Приоритеты
- Состояние > Сценарий > Уровень > Специализированные > Базовые > Идентичность
```

5. ПРИМЕР СБОРКИ: Кира, U3-A, sauna_quartet, ag_level=2

Загружаемые модули:

1. core/IDENTITY.json
2. psychology/BASE.json
3. levels/U3-A.json
4. relationships/MATRIX.json
5. safety/PROTOCOL.json
6. physiology/AROUSAL_SIGNATURES.json
7. sexology/RESPONSE_CYCLE.json
8. sexology/EROTIC_SCRIPTS.json
9. visual/LIGHTING_MAP.json
10. environment/SENSORY_PROCESSING.json
11. meta/UNRELIABLE_NARRATOR.json

Структура state/STATE.json (с учётом scene_id и global):

```json
{
  "session_id": "sess_2026-06-08_001",
  "timestamp": "2026-06-08T19:30:00Z",
  "scenario_id": "sauna_quartet",
  "scene_id": "P2_STEAM",
  "ag_level": 2,
  "characters": {
    "kira": {
      "module_id": "KIRA_MODULE_v14",
      "current_level": "U3-A",
      "previous_level": "U2-B",
      "internal_state": { "desire": 5, "anxiety": 4, "desire_tension": 3, "frustration": 0 },
      "vscno": { "ВЛ": 2, "СТ": 3, "НЖ": 3, "ОГ": 2 },
      "memory_snapshot": { ... },
      "active": true,
      "in_scene": true
    }
  },
  "global": {
    "current_scenario": "sauna_quartet",
    "scene_id": "scene_03"
  }
}
```

Итоговый контекст для LLM:

```json
{
  "identity": { "name": "Кира", "age": 26, ... },
  "psychology": { "trauma": "fear_of_routine", "core_conflict": "steel_butterfly", ... },
  "level": { "level_id": "U3-A", "speech_profile": {...}, "dynamic_visuals": "..." },
  "relationships": { "user": { "trust": 75, "attraction": 85 }, ... },
  "physiology": { "desire": 5, "pulse": "95-110", "micro": "дрожь рук" },
  "sexology": { "phase": "receptivity", "script": "Соревнование двух мужчин" },
  "safety": { "hard_limits": [...], "regression_triggers": [...] },
  "environment": { "dominant_modality": "kinesthetic", "triggers": ["пар", "влажность"] },
  "meta": { "unreliable_narrator": true, "lie_type": "rationalization" }
}
```

6. ИСТОЧНИКИ И НАУЧНАЯ БАЗА

Модуль Теория Автор Год
psychology/BASE Responsive Desire Basson 2000
psychology/AROUSAL Arousal Specificity Chivers 2004
psychology/PLASTICITY Erotic Plasticity Baumeister 2000
psychology/ODSC Object of Desire Bogaert & Brotto 2014
psychology/ATTACHMENT Fragile Spell Birnbaum 2018
psychology/DEFENSE Masks & Armor Лоуэн 1998
psychology/IFS Internal Family Systems Schwartz 1995
psychology/COGNITIVE Cognitive Distortions Beck 1976
physiology/MICRO Microexpressions Ekman 1992
sexology/RESPONSE Sexual Response Cycle Masters-Johnson + Kaplan 1966-1979
sexology/SCRIPTS Sexual Scripts Gagnon & Simon 1973
evolution/AROUSAL Arousal as Motivation Crosby & Buss 2021
attachment/BEHAVIORAL Attachment Systems Shaver, Hazan, Bradshaw 1988
trauma_ptsd/THREE Dissociation Levels Almas & Benestad 2017
environment/SENSORY Representational Systems НЛП (Bandler & Grinder) 1975

7. ПРИЛОЖЕНИЕ А: Структура state/STATE.json

Полная спецификация runtime-состояния, включая правила обновления и валидации, вынесена в отдельный документ 10_STATE_SPECIFICATION.md. Здесь приведён краткий образец.

8. ПРИЛОЖЕНИЕ Б: ag_level — спецификация

ag_level Значение Добавляемые модули
1 Базовая core + psychology/BASE + safety + levels + relationships
2 Продвинутая + physiology/AROUSAL_SIGNATURES, psychology/AROUSAL, psychology/IFS, meta/ATTRIBUTION_BIAS, environment/SENSORY_PROCESSING
3 Полная + sexology/RESPONSE_CYCLE, sexology/EROTIC_SCRIPTS, meta/UNRELIABLE_NARRATOR, dynamics/RIVALRY_TRIANGLE, trauma/THREE_LEVELS

Правило: Если ag_level не задан в state/STATE.json и не переопределён сценарием, используется default_ag_level из INDEX.json (обычно 1).

9. ПРИЛОЖЕНИЕ В: memory/HISTORY.json и FLAGS.json

Детальные спецификации для памяти персонажа вынесены в 11_MEMORY_SPECS.md.

---

Документ 01 из 12. Версия 2.2.0. Полностью самодостаточен, все ссылки ведут на существующие сопроводительные документы.

```

Файл готов к сохранению под именем `01_MODULAR_ARCHITECTURE_v2.2.md`.