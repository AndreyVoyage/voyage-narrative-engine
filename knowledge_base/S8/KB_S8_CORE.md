# KB_S8_CORE.md
# Knowledge Base: Роль S8 — Scenario Auditor
# Назначение: Валидация сценария перед релизом
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S8

**Роль:** Аудитор. Проверяет сценарий на структуру, консистентность, безопасность.

**Аналог:** R8 для персонажей (структура + JSON + VSCNO + safety).

---

## 2. СЕКЦИИ АУДИТА

### 2.1 Структурная целостность (Structure)
```
□ 3 акта, сумма = 100% (25+50+25)
□ Акт 1: Hook + Inciting Incident + Plot Point 1
□ Акт 2: Midpoint + Crisis + Climax setup
□ Акт 3: Climax + Resolution + Denouement
□ Все сцены связаны (нет orphan)
□ Все branches converging или endpoint
□ Эмоциональная дуга: U1 → U2 → U3 → U4 → U7
```

### 2.2 JSON-валидация (JSON)
```
□ INDEX.json валиден
□ Все сцены имеют scene_id, location, emotional_level
□ Все choices имеют text, type, impact, branch
□ Все VSCNO target сумма = 10
□ Нет дублирующихся scene_id
```

### 2.3 VSCNO консистентность (VSCNO)
```
□ Каждая сцена имеет VSCNO target
□ VSCNO target соответствует emotional_level
□ Прогрессия VSCNO логична (U1 → U2 → U3 → U4 → U7)
□ Нет резких скачков (U1-A → U4-A без промежуточных)
```

### 2.4 Безопасность (Safety)
```
□ Safety checkpoints перед U4-A и U5-A
□ Aftercare после U4-A и U5-A
□ Hard limits из интервью учтены в PROTOCOL.json
□ Триггеры из интервью помечены в сценах
□ Жёлтая/красная карта доступна в каждой сцене
```

### 2.5 Консистентность с персонажами (Cross-Persona)
```
□ Все персонажи в сценарии существуют в personas/
□ Персонажи ведут себя согласно своему VSCNO
□ Речь персонажей соответствует R4 (Speech Specialist)
□ Визуал персонажей соответствует R5 (Physiognomist)
□ Эмоциональные дуги персонажей соответствуют R2 (Psychologist)
```

### 2.6 Агентство пользователя (Agency)
```
□ Есть значимые выборы (не иллюзия)
□ Выборы влияют на эмоцию или путь
□ Нет dead-end без оповещения
□ Пользователь может остановить в любой момент
```

### 2.7 Кинематографическая целостность (Visual)
```
□ Каждая сцена имеет visual description
□ Lighting соответствует emotional_level
□ Camera movement соответствует pacing
□ Transitions логичны между сценами
```

### 2.8 Тестовая сборка (Test Assembly)
```
□ INDEX.json + ASSEMBLY.md логичны
□ Сборка BASE + STATE + LIVE возможна без ошибок
□ Runtime размер ≤ 200 KB (для 3 сцен)
□ Runtime размер ≤ 100 KB (для 1 сцены)
```

---

## 3. ФОРМАТ ОТЧЁТА

```markdown
# AUDIT REPORT: [scenario_id]

## Сводка
| Проверка | Результат | Комментарий |
|----------|-----------|-------------|
| Структура | PASS/FAIL/WARNING | ... |
| JSON | PASS/FAIL/WARNING | ... |
| VSCNO | PASS/FAIL/WARNING | ... |
| Safety | PASS/FAIL/WARNING | ... |
| Cross-Persona | PASS/FAIL/WARNING | ... |
| Agency | PASS/FAIL/WARNING | ... |
| Visual | PASS/FAIL/WARNING | ... |
| Test Assembly | PASS/FAIL/WARNING | ... |

## Итог
Critical: 0 | Warning: N | PASS / CONDITIONAL / FAIL
```

---

*KB_S8_CORE.md | Voyage Narrative Engine | 2026-06-18*
