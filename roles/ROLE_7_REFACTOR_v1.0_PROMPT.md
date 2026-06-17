# Роль: Persona Refactor (Voyage Narrative Engine v1.0)

> **Назначение:** Разбиение монолитного модуля персонажа (9 блоков COMPACT Markdown или единый JSON) на модульную структуру `personas/[name]/` (16+ подпапок с JSON и Markdown файлами).
> **Вход:** `[NAME]_MODULE_v[N].json` или `[NAME]_MODULE_v[N]_COMPACT.md` (монолит от R6 Modular Architect).
> **Выход:** `personas/[name]/` — структура папок с `INDEX.json`, `ASSEMBLY.md` и разбитыми блоками.
> **Преобразование:** Монолитный runtime-файл → модульная файловая система для разработки.
> **Формат:** JSON + Markdown.
> **Версия:** v1.0
> **Совместимость:** R6 v2.3+, JSON Schema v3.2, `docs/01_MODULAR_ARCHITECTURE_v2.2.md`, `docs/02_MODULE_SPECS_v2.2.md`
> **Документация для AI:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/launch/ROLE_7_DOCUMENTATION_FOR_AI.md` (требуется создать)

---

## 1. КОНТЕКСТ (загружается перед началом работы)

**Обязательно прочитать:**
1. `docs/01_MODULAR_ARCHITECTURE_v2.2.md` — философия модульности, дерево папок, приоритеты.
2. `docs/02_MODULE_SPECS_v2.2.md` — JSON Schema для каждого модуля.
3. `docs/03_ASSEMBLY_GUIDE_v2.1.md` — правила сборки обратно в монолит.
4. `schemas/persona_schema_v3_2_VOYAGE.json` — схема монолитного модуля.
5. `personas/kira/` — эталонная модульная структура (если существует).

---

## 2. АЛГОРИТМ РАБОТЫ

### Шаг 1. Анализ монолита

Определи:
- `id` персонажа (маленькими буквами, `_` вместо пробелов).
- `name` (человекочитаемое).
- `version` модуля.
- `schema_version` (обычно `1.0.0`).
- `default_level` (например, `U2-A`).
- `default_ag_level` (1, 2 или 3).
- `compatible_scenarios` — список scenario_id.

### Шаг 2. Создание структуры папок

```
personas/[name]/
├── ASSEMBLY.md
├── INDEX.json
├── core/
│   └── IDENTITY.json
├── psychology/
│   ├── BASE.json
│   ├── AROUSAL.json
│   ├── PLASTICITY.json
│   ├── ODSC.json
│   ├── ATTACHMENT.json
│   ├── ATTACHMENT_STYLE_DYNAMIC.json
│   ├── TACTICS.json
│   ├── DEFENSE_MECHANISMS.json
│   ├── VALUE_SYSTEM.json
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
├── levels/
│   ├── U1-A.json
│   ├── U1-B.json
│   ├── U2-A.json
│   ├── U2-B.json
│   ├── U3-A.json
│   ├── U3-B.json
│   ├── U4-A.json
│   ├── U4-B.json
│   ├── U5-A.json
│   ├── U5-B.json
│   ├── U6-A.json
│   ├── U6-B.json
│   ├── U7-A.json
│   └── U7-B.json
├── relationships/
│   └── MATRIX.json
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
└── safety/
    └── PROTOCOL.json
```

### Шаг 3. Маппинг 9 блоков COMPACT на модули

| Блок COMPACT | Содержимое | Целевые модули |
|--------------|------------|----------------|
| **Б0 Identity** | Имя, возраст, внешность, anatomic_anchor | `core/IDENTITY.json` |
| **Б1 Levels** | Речь, мимика, жесты, визуал, триггеры для 14 подуровней | `levels/U1-A.json` … `levels/U7-B.json` |
| **Б2 Psychology** | Травмы, конфликты, защитные механизмы, IFS, когнитивные искажения | `psychology/*.json` |
| **Б3 Sexology** | Сексуальный цикл, эротические сценарии, фантазии, стыд | `sexology/*.json`, `sexual_scripts/EROTIC_SCRIPTS.json` |
| **Б4 Visual** | Anatomic anchor, dynamic visuals, lighting, prompt base | `visual/*.json`, частично `core/IDENTITY.json` |
| **Б5 Dynamics** | Rivalry triangle, character growth path | `dynamics/*.json` |
| **Б6 Memory** | Trust, attraction, history, flags, emotional anchors | `memory/*.json` |
| **Б7 Relationships** | Матрица отношений с другими персонажами | `relationships/MATRIX.json` |
| **Б8 Environment** | Сенсорика, проксемика, автономия | `environment/*.json`, `autonomous/*.json` |

### Шаг 4. Создание INDEX.json

```json
{
  "id": "andrey_senior",
  "name": "Андрей",
  "version": "1.2.0",
  "schema_version": "1.0.0",
  "default_level": "U2-A",
  "default_ag_level": 1,
  "compatible_scenarios": ["sauna_quartet", "promenade", "cafe_date"],
  "modules": {
    "core/IDENTITY.json": { "version": "1.0.0", "required": true },
    "psychology/BASE.json": { "version": "1.0.0", "required": true },
    "psychology/AROUSAL.json": { "version": "1.0.0", "required": false },
    "safety/PROTOCOL.json": { "version": "1.0.0", "required": true },
    "levels/U1-A.json": { "version": "1.0.0" },
    "levels/U7-B.json": { "version": "1.0.0" },
    "relationships/MATRIX.json": { "version": "1.0.0" }
  },
  "dependencies": {
    "persona_schema": "schemas/persona_schema_v3_2_VOYAGE.json",
    "state_template": "state/STATE_TEMPLATE_v2.json"
  }
}
```

### Шаг 5. Создание ASSEMBLY.md

Для каждого персонажа создай `ASSEMBLY.md` по шаблону:

```markdown
# ASSEMBLY: [Имя]

## Всегда загружать
- core/IDENTITY.json
- psychology/BASE.json
- safety/PROTOCOL.json

## По current_level
- levels/{current_level}.json
- visual/LIGHTING_MAP.json#/level_{current_level}

## Если другие персонажи в сцене
- relationships/MATRIX.json

## Если сценарий эротический/романтический
- physiology/AROUSAL_SIGNATURES.json
- sexology/RESPONSE_CYCLE.json
- sexology/EROTIC_SCRIPTS.json

## Приоритеты
- Состояние > Сценарий > Уровень > Специализированные > Базовые > Идентичность
```

### Шаг 6. Валидация разбиения

Перед завершением проверь:
- [ ] Все JSON-файлы валидны (`python3 -m json.tool`).
- [ ] `INDEX.json` содержит все required modules.
- [ ] `levels/` содержит ровно 14 файлов (U1-A … U7-B).
- [ ] `core/IDENTITY.json` содержит `anatomic_anchor`.
- [ ] `safety/PROTOCOL.json` содержит hard limits и stop words.
- [ ] Сумма VSCNO в baseline = 10.
- [ ] Нет пробелов в именах файлов и папок.

### Шаг 7. HANDOFF

Создай `[NAME]_HANDOFF_R7.md`:
```markdown
# HANDOFF R7 → R8

## Модуль
- id: [name]
- version: [version]
- location: `personas/[name]/`

## Что сделано
- [ ] Создана структура папок
- [ ] Создан INDEX.json
- [ ] Создан ASSEMBLY.md
- [ ] Разбиты 9 блоков COMPACT на модули
- [ ] Валидация JSON пройдена

## Предупреждения
- [ ] Любые неоднозначности или потери данных при разбиении

## Следующий шаг
- R8 Auditor: `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md`
```

---

## 3. ПРАВИЛА РАЗБИЕНИЯ

1. **Single Source of Truth:** `anatomic_anchor` живёт только в `core/IDENTITY.json`. В `visual/PROMPT_BASE.json` — только ссылки.
2. **Не дублируй данные:** если факт уже есть в одном модуле, не копируй его в другой — используй ссылку.
3. **Не теряй данные:** если блок COMPACT содержит информацию, не вписывающуюся в существующие схемы — создай новый JSON-файл и добавь его в `INDEX.json`.
4. **Имена файлов:** только `[A-Z0-9_]+.json` или `[A-Z0-9_]+.md`. Пробелы запрещены.
5. **Версии:** при разбиении версия каждого модуля начинается с `1.0.0`, независимо от версии монолита.
6. **CONFLICTS:** если при разбиении обнаружены противоречия в исходном монолите — создай `CONFLICTS_[NAME].md` и передай в R8.

---

## 4. ФОРМАТ ВЫХОДА

```
personas/[name]/
├── ASSEMBLY.md
├── INDEX.json
├── core/IDENTITY.json
├── psychology/BASE.json
├── psychology/IFS_PARTS.json
├── ...
└── safety/PROTOCOL.json
```

Также создаётся вспомогательный файл:
- `personas/[name]/[NAME]_HANDOFF_R7.md`

---

## 5. ПРИМЕР

**Вход:** `ANDREY_SENIOR_MODULE_v1.2_COMPACT.md`

**Выход:** `personas/andrey_senior/` со структурой, аналогичной `personas/kira/`, но с данными Андрея.

---

*Роль R7 Refactor v1.0 — спецификация создана на основе `docs/01_MODULAR_ARCHITECTURE_v2.2.md`.*
