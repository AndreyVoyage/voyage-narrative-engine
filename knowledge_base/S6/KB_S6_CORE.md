# KB_S6_CORE.md
# Knowledge Base: Роль S6 — Scenario Assembly Architect
# Назначение: Собрать сценарий из модулей (S3–S5) в единый Scenario Module
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S6

**Роль:** Сборщик. Агрегирует матрицу (S3), сцены (S4), визуал (S5) в единый Scenario Module.

**Аналогия:** Как R6 для персонажей — сборка модульной структуры.

---

## 2. СТРУКТУРА SCENARIO MODULE

```
scenarios/[scenario_id]/
├── INDEX.json
├── ASSEMBLY.md
├── core/
│   ├── CONCEPT.md
│   └── GENRE.json
├── structure/
│   ├── THREE_ACT.json
│   └── HERO_JOURNEY.json
├── scenes/
│   ├── S001.md
│   ├── S002.md
│   └── ...
├── branches/
│   └── BRANCH_MAP.json
├── characters/
│   ├── ROLES.json
│   └── ARCS.json
├── dynamics/
│   ├── PACING.json
│   └── TONE_MAP.json
├── environment/
│   ├── LOCATIONS.json
│   ├── LIGHTING.json
│   └── PROPS.json
├── safety/
│   ├── PROTOCOL.json
│   └── AFTERCARE.md
└── meta/
    └── CHANGELOG.md
```

---

## 3. ФОРМАТ INDEX.json

```json
{
  "id": "bar_encounter_andrey",
  "name": "Bar Encounter with Andrey",
  "version": "1.0.0",
  "schema_version": "1.0.0",
  "duration": "single_session",
  "total_scenes": 8,
  "total_branches": 4,
  "personas": ["andrey_senior"],
  "locations": ["bar"],
  "modules": {
    "core/CONCEPT.md": {"version": "1.0.0", "required": true},
    "structure/THREE_ACT.json": {"version": "1.0.0", "required": true},
    "scenes/S001.md": {"version": "1.0.0", "required": true},
    "safety/PROTOCOL.json": {"version": "1.0.0", "required": true}
  }
}
```

---

## 4. ПРАВИЛА СБОРКИ

### 4.1 Assembly Rules
1. Не менять данные S3–S5 — только агрегировать
2. Каждая сцена имеет ссылку на emotional_level и vscno_target
3. Каждая сцена имеет safety checkpoint (если U4-A или U5-A)
4. Каждая сцена имеет aftercare note (если U4-B или U7)
5. Все branches converging к climax или aftercare

### 4.2 ASSEMBLY.md Template
```markdown
# ASSEMBLY: [Scenario Name]

## Всегда загружать
- core/CONCEPT.md
- structure/THREE_ACT.json
- safety/PROTOCOL.json

## По акту
- Act 1: scenes/S001.md → scenes/S003.md
- Act 2: scenes/S004.md → scenes/S006.md
- Act 3: scenes/S007.md → scenes/S008.md

## По emotional_level
- U1-A: scenes/S001.md
- U2-A: scenes/S002.md
- U3-A: scenes/S004.md
- U4-A: scenes/S006.md
- U4-B: scenes/S007.md
- U7-A: scenes/S008.md

## Приоритеты
- Сцена > Визуал > Безопасность > Мета
```

---

## 5. ЧЕК-ЛИСТ СБОРКИ

```
□ INDEX.json содержит все модули
□ ASSEMBLY.md описывает порядок загрузки
□ Все сцены из S3 присутствуют в scenes/
□ Все visual из S5 присутствуют в scenes/ (теги [R5: ...])
□ Safety/PROTOCOL.json содержит hard limits из интервью
□ Aftercare описан для U4-B и U7 сцен
□ Branches converging или имеют endpoint
□ Нет orphan сцен (все сцены связаны)
□ Эмоциональная дуга непрерывна (U1 → U2 → U3 → U4 → U7)
```

---

## 6. ВЫХОД ДЛЯ S7

```json
{
  "scenario_module": {
    "id": "bar_encounter_andrey",
    "status": "assembled",
    "modules": 12,
    "scenes": 8,
    "branches": 4,
    "next_step": "S7 Refactor (compression)"
  }
}
```

---

*KB_S6_CORE.md | Voyage Narrative Engine | 2026-06-18*
