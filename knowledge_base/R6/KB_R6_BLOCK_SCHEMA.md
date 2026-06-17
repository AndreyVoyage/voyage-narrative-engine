# KB_R6_BLOCK_SCHEMA.md
# Knowledge Base: Роль 6 — Block Schema & Module Assembly
# Назначение: Техническая спецификация структуры Persona Module
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. БЛОК-СХЕМА МОДУЛЯ

```
Persona Module (root)
├── INDEX.json           # Корневой индекс
├── ASSEMBLY.md          # Карта сборки
├── HANDOFF_R6.md        # Финальная компрессия
├── HUMAN/
│   ├── core/
│   │   ├── PORTRAIT.md        # R1: портрет
│   │   ├── VSCNO.md           # R2: ВСЦНО (14 строк)
│   │   ├── IDENTITY.json      # R1: identity (12 полей)
│   │   └── COMPACT.md         # R2: компрессия ВСЦНО
│   ├── levels/
│   │   ├── U1-A/
│   │   │   ├── PREVIOUS.md    # ФМДР + визуал (предыдущий)
│   │   │   ├── CURRENT.md     # 2×ФМДР + визуал (текущий)
│   │   │   └── FUTURE.md      # 3×ФМДР + визуал (будущий)
│   │   ├── U1-B/
│   │   │   ├── PREVIOUS.md
│   │   │   ├── CURRENT.md
│   │   │   └── FUTURE.md
│   │   ├── U2-A/ … U7-B/      # 14 папок всего
│   ├── psychology/
│   │   ├── TRAUMA.md          # R2: травма, защиты, триггеры
│   │   ├── SPEECH_PATTERNS.md # R2: речевые паттерны
│   │   └── COMPACT.md         # R2: компрессия
│   ├── sexology/
│   │   ├── TEC.md             # R3: TEC матрица (10×6)
│   │   ├── SCENARIOS.md       # R3: сексуальные сценарии
│   │   └── COMPACT.md         # R3: компрессия
│   ├── visual/
│   │   ├── ANCHOR.json        # R5: Anatomic Anchor (10 блоков)
│   │   ├── SIGNATURE.md       # R5: Visual Signature (строка)
│   │   ├── DYNAMIC.md         # R5: Dynamic Visuals (14×7)
│   │   └── COMPACT.md         # R5: компрессия
│   ├── dynamics/
│   │   ├── MOVEMENT.md        # R5: типы движения (5 типов)
│   │   ├── AGGRESSION.md      # R5: агрессия/нежность (7 градаций)
│   │   └── COMPACT.md         # R5: компрессия
│   ├── memory/
│   │   ├── ANCHORS.md         # R1+R2: якоря (запах, звук, тактиль)
│   │   ├── TRIGGERS.md        # R2: триггеры (3 категории)
│   │   └── ASSOCIATIONS.md    # R1: ассоциативные сети
│   ├── relationships/
│   │   ├── INDEX.json         # R6: список отношений
│   │   ├── [Name].json        # R6: JSON для каждого отношения
│   │   └── COMPACT.md         # R6: компрессия
│   ├── environment/
│   │   ├── LOCATIONS.md       # R1: локации (бар, квартира, работа)
│   │   ├── FLORA_FAUNA.md     # R1: флора/фауна (кот, растения)
│   │   └── COMPACT.md         # R1: компрессия
│   └── safety/
│       ├── VRI_MONITOR.md     # R2+R3: мониторинг ВРИ (7 показателей)
│       ├── SAFE_CODES.md      # R2: сейф-коды (3 уровня)
│       └── ESCALATION.md      # R2+R3: экскалация (3 уровня)
├── AUTONOMOUS/
│   └── (empty)              # Зарезервировано для v2.0
└── META/
    ├── INDEX.json             # R6: метаданные модуля
    ├── CHANGELOG.md           # R6: история изменений
    └── TEST_CASES.md          # R6: тест-кейсы для аудита
```

---

## 2. ФОРМАТ INDEX.json (корневой)

```json
{
  "module_name": "andrey_senior",
  "version": "1.2",
  "created": "2026-06-16",
  "roles": {
    "R1": {"version": "1.1", "file": "HUMAN/core/PORTRAIT.md"},
    "R2": {"version": "1.1", "file": "HUMAN/core/VSCNO.md"},
    "R3": {"version": "1.0", "file": "HUMAN/sexology/TEC.md"},
    "R4": {"version": "1.0", "file": "HUMAN/levels/U1-A/CURRENT.md"},
    "R5": {"version": "1.0", "file": "HUMAN/visual/ANCHOR.json"},
    "R6": {"version": "1.0", "file": "INDEX.json"}
  },
  "sublevels": ["U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A", "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B"],
  "compression": {
    "method": "_linear_table + _base_delta + _glossary",
    "target_size": "40-50% of full"
  }
}
```

---

## 3. ФОРМАТ RELATIONSHIP JSON

```json
{
  "with": "Elena",
  "scene": "corporate_office",
  "tone": "formal_hidden_tension",
  "history": "2 years colleagues, one night drunk",
  "current_status": "U3-B",
  "power_dynamic": "equal_formal",
  "triggers": ["she_looks_at_phone", "he_adjusts_watch"],
  "vscno_influence": {"ВЛ": -1, "СТ": +2, "НЖ": -1, "ОГ": 0},
  "tec_codes": ["СЛ", "КН"]
}
```

**Поля:**
- `with`: имя персонажа.
- `scene`: локация, snake_case.
- `tone`: тон, 2–3 токена, snake_case.
- `history`: 1–2 предложения.
- `current_status`: текущий подуровень (U3-B).
- `power_dynamic`: отношения власти (equal_formal, dominant_submissive, etc.).
- `triggers`: массив строк, snake_case.
- `vscno_influence`: влияние на ВСЦНО (Δ относительно baseline).
- `tec_codes`: активные ТЭК-коды в этом отношении.

---

## 4. ФОРМАТ PREVIOUS/CURRENT/FUTURE

### PREVIOUS.md
```markdown
# U3-A — PREVIOUS (U2-A)

## ФМДР (пример из U2-A)
**Мысль:** Они не знают, что я вижу.
**Действие:** [sits, adjusts sleeves, observant hidden jealousy]
**Речь:** «Ну что, ребята, всё нормально.»

## Визуал (U2-A)
- clothing: blue_shirt_jeans_watch
- posture: sits_adjusts_sleeves_nervous
- micro_expression: observant_hidden_jealousy
- lighting: spotlight_dark
- blush: 0, sweat: 0, pupils: normal
```

### CURRENT.md
```markdown
# U3-A — CURRENT

## ФМДР (2 примера)
**Пример 1:**
**Мысль:** Она близко. Слишком близко.
**Действие:** [leans, tension visible, intense focus]
**Речь:** «Ты… ты уверена?»

**Пример 2:**
**Мысль:** Не могу отвести глаз.
**Действие:** [reaches, hand trembles, stops himself]
**Речь:** (молчит, только дыхание)

## Визуал (U3-A)
- clothing: unbuttoned_shirt_torse
- posture: leaning_tension_visible
- micro_expression: intense_focus_lips_tight
- lighting: dramatic_side
- blush: 2, sweat: 1, pupils: slightly_dilated
```

### FUTURE.md
```markdown
# U3-A — FUTURE (U4-A)

## ФМДР (3 примера — куда идёт)
**Пример 1:**
**Мысль:** Всё. Я сдался.
**Действие:** [shirt on shoulders, hands reach uncertainly, eyes wide]
**Речь:** «Я… я не могу больше притворяться.»

**Пример 2:**
**Мысль:** Страх. И… свобода?
**Действие:** [breakthrough, mix of fear and passion, dilated pupils]
**Речь:** «Прости. Прости, что я такой.»

**Пример 3:**
**Мысль:** Она видит. Видит меня.
**Действие:** [bewildered, hands uncertain, breakthrough eyes]
**Речь:** (молчит, только слёзы)

## Визуал (U4-A)
- clothing: shirt_on_shoulders_torse
- posture: bewildered_hands_reach_uncertainly
- micro_expression: breakthrough_eyes_wide_mix_fear_passion
- lighting: dramatic_side_Rembrandt
- blush: 3, sweat: 1, pupils: dilated
```

---

## 5. ПРАВИЛА СБОРКИ

1. **Не изменять данные:** R6 только копирует и агрегирует. Если данные R1–R5 неверны — фиксить в исходной роли, не здесь.
2. **Консистентность путей:** Все пути в INDEX.json должны существовать физически.
3. **Версионирование:** Каждая роль указывает свою версию. Если R2 обновляется — меняется только VSCNO.md, не весь модуль.
4. **Компрессия:** R6 создаёт COMPACT.md в каждой папке, но не сжимает сам — это задача R7 (Refactor).
5. **Тест-кейсы:** META/TEST_CASES.md содержит минимум 3 теста на консистентность (cross-role, cross-level, cross-persona).

---

*KB_R6_BLOCK_SCHEMA.md | Voyage Narrative Engine | 2026-06-16*
