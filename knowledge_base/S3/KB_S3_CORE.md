# KB_S3_CORE.md
# Knowledge Base: Роль S3 — Scenario Architect
# Назначение: Создать матрицу сценария (3 акта, сцены, ветвления) на основе анализа S2
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S3

**Роль:** Архитектор. Создаёт каркас сценария: акты, сцены, ветвления, эмоциональные дуги.

**Вход:** Анализ от S2 (Scenario DNA, Conflict Map, Agency Map)
**Выход:** Scenario Matrix (JSON) для S4 (Scenario Writer)

---

## 2. СТРУКТУРА МАТРИЦЫ

### 2.1 Three-Act Matrix
```json
{
  "act_1": {
    "percentage": 25,
    "purpose": "Setup, Hook, Inciting Incident",
    "scenes": [
      {
        "id": "S001",
        "name": "Prologue",
        "location": "bar",
        "time": "evening",
        "characters": ["andrey_senior"],
        "emotional_level": "U1-A",
        "vscno_target": {"ВЛ": 3, "СТ": 3, "НЖ": 1, "ОГ": 3},
        "purpose": "Hook: introduce tension",
        "choices": [{"text": "Подойти к бару", "branch": "S002-A"}, {"text": "Осмотреться", "branch": "S002-B"}]
      }
    ]
  },
  "act_2": {
    "percentage": 50,
    "purpose": "Confrontation, Rising Action, Midpoint",
    "scenes": [...]
  },
  "act_3": {
    "percentage": 25,
    "purpose": "Resolution, Climax, Aftercare",
    "scenes": [...]
  }
}
```

### 2.2 Scene Template
```json
{
  "id": "S###",
  "name": "Human-readable name",
  "location": "ref to environment/LOCATIONS.json",
  "time": "morning/afternoon/evening/night",
  "lighting": "ref to environment/LIGHTING.json",
  "characters": ["persona_id"],
  "emotional_level": "U#-A/B",
  "vscno_target": {"ВЛ": N, "СТ": N, "НЖ": N, "ОГ": N},
  "purpose": "What this scene does for the story",
  "fmdr_focus": "thought/action/speech/mix",
  "choices": [
    {
      "text": "What user sees",
      "type": "dialogue/tactical/emotional",
      "impact": "emotional/pacing/plot",
      "branch": "S###-A",
      "vscno_shift": {"ВЛ": +1, "СТ": -1}
    }
  ],
  "merge_point": "S### (if branches converge)",
  "aftercare_required": true/false
}
```

---

## 3. ПРАВИЛА СЦЕН

### 3.1 Scene Rules
- Каждая сцена имеет **emotional_level** (U1-A … U7-B)
- Сцены внутри акта идут по уровням: U1 → U2 → U3 → U4
- Нельзя пропускать уровни (нельзя U1 → U4 без U2, U3)
- Aftercare-сцены (U4-B, U7-A, U7-B) всегда после climax
- Safety checkpoint перед U4-A и U5-A

### 3.2 Branching Rules
- **Linear:** 1 вход → 1 выход ( exposition, transition)
- **Divergent:** 1 вход → 2+ выхода (выбор пользователя)
- **Convergent:** 2+ входа → 1 выход (выборы сходятся)
- **Diamond:** 1 → 2 → 1 (выбор влияет на эмоцию, не путь)
- **Threaded:** 1 → 2 → 2+ (выбор влияет на память/отношения)

### 3.3 Agency Rules
- Low agency: наблюдатель (персонажи действуют сами)
- Medium agency: диалоговые выборы, тактика
- High agency: стратегия, темп, глубина
- Agency level не может превышать capability персонажа

---

## 4. ЭМОЦИОНАЛЬНАЯ КАРТА

### 4.1 Emotional Arc by Scene
```
S001: Curiosity (0.3) → U1-A
S002: Interest (0.4) → U2-A
S003: Attraction (0.5) → U2-A
S004: Tension (0.6) → U3-A
S005: Desire (0.7) → U3-A
S006: Peak (0.9) → U4-A
S007: Aftercare (0.8) → U4-B
S008: Reflection (0.6) → U7-A
```

### 4.2 Contrast Principle
- После высокой интенсивности → низкая (U4-A → U4-B)
- После стресса → нежность (U6-A → U7-A)
- Контраст усиливает эмоцию

---

## 5. ВАЛИДАЦИЯ

### 5.1 Structural Checks
```
□ 3 акта, сумма = 100% (25+50+25)
□ Акт 1 заканчивается Plot Point 1
□ Акт 2 имеет Midpoint
□ Акт 3 имеет Climax + Denouement
□ Каждая сцена имеет emotional_level
□ Уровни идут последовательно (U1 → U2 → U3 → U4)
□ Нет orphan branches (все ветки сходятся или ведут к climax)
□ После U4-A есть aftercare (U4-B или U7)
```

### 5.2 Consistency Checks
```
□ Персонажи в сценах существуют в personas/
□ Локации описаны в environment/
□ VSCNO target сумма = 10 для каждой сцены
□ VSCNO target соответствует emotional_level
□ Safety checkpoints перед U4-A и U5-A
```

---

## 6. ВЫХОД ДЛЯ S4

```json
{
  "scenario_matrix": {
    "id": "SC-001",
    "name": "Bar Encounter with Andrey",
    "acts": [...],
    "total_scenes": 12,
    "branches": 4,
    "emotional_arc": [...],
    "recommended_vscno_progression": [
      {"scene": "S001", "vscno": {"ВЛ": 3, "СТ": 3, "НЖ": 1, "ОГ": 3}},
      {"scene": "S006", "vscno": {"ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2}}
    ]
  }
}
```

---

*KB_S3_CORE.md | Voyage Narrative Engine | 2026-06-18*
