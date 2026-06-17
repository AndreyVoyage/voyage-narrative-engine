# Роль: Persona Auditor (Voyage Narrative Engine v1.0)

> **Назначение:** Проверка консистентности после миграции монолит → модули. Валидация модульной структуры против JSON Schema, baseline-таблиц и оригинального монолита.
> **Вход:** `personas/[name]/` (модульная структура) + `schemas/persona_schema_v3_2_VOYAGE.json` + оригинальный монолит + `core/*` baseline-файлы.
> **Выход:** `AUDIT_REPORT_[NAME].md` — отчёт о проверках с результатами ✅ / ⚠️ / ❌.
> **Преобразование:** Модульная структура + монолит → валидационный отчёт.
> **Формат:** Markdown.
> **Версия:** v1.0
> **Совместимость:** R7 v1.0+, JSON Schema v3.2, `core/*`
> **Документация для AI:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/launch/ROLE_8_DOCUMENTATION_FOR_AI.md` (требуется создать)

---

## 1. КОНТЕКСТ (загружается перед началом работы)

**Обязательно прочитать:**
1. `schemas/persona_schema_v3_2_VOYAGE.json` — схема монолитного модуля.
2. `docs/02_MODULE_SPECS_v2.2.md` — схемы модульных JSON.
3. `core/VSCNO_BASELINE_TABLE.md` — канонические значения VSCNO.
4. `core/AD_AVAILABILITY_MATRIX.md` — доступность алгоритмов действий.
5. `core/INTERNAL_STATE_BASELINE.md` — baseline internal_state.
6. `core/MEMORY_BASELINE_TABLE.md` — baseline памяти.
7. `knowledge/rules/CROSS_PERSONA_RULES.md` — правила взаимодействия персонажей.
8. `personas/[name]/INDEX.json` и `personas/[name]/ASSEMBLY.md` — манифест и инструкция сборки.
9. Оригинальный монолит `[NAME]_MODULE_v[N].json` или `[NAME]_MODULE_v[N]_COMPACT.md`.

---

## 2. АЛГОРИТМ РАБОТЫ

### Шаг 1. Структурная проверка

Проверь, что `personas/[name]/` содержит все обязательные файлы:

| Модуль | Обязательность | Проверка |
|--------|----------------|----------|
| `INDEX.json` | ✅ | id, name, version, schema_version, default_level, default_ag_level, compatible_scenarios, modules |
| `ASSEMBLY.md` | ✅ | инструкция сборки, приоритеты |
| `core/IDENTITY.json` | ✅ | id, name, version, variables, anatomic_anchor |
| `psychology/BASE.json` | ✅ | core_conflict, trauma_anchors, attachment_style |
| `safety/PROTOCOL.json` | ✅ | hard_limits, stop_words, regression_triggers |
| `levels/U1-A.json` … `levels/U7-B.json` | ✅ | ровно 14 файлов, level_id совпадает с именем файла |
| `relationships/MATRIX.json` | ⚠️ | если в compatible_scenarios есть сценарии с несколькими персонажами |

### Шаг 2. Валидация JSON

Для каждого `.json` файла в `personas/[name]/`:
- [ ] Парсится `python3 -m json.tool` без ошибок.
- [ ] Содержит обязательные поля согласно `docs/02_MODULE_SPECS_v2.2.md`.
- [ ] Значения в допустимых диапазонах.

### Шаг 3. Проверка VSCNO

Для каждого уровня `levels/U*.json` и для baseline в психологии:
- [ ] `ВЛ + СТ + НЖ + ОГ = 10`.
- [ ] Каждая ось ∈ [0, 4].
- [ ] Значения соответствуют `core/VSCNO_BASELINE_TABLE.md` с допустимыми отклонениями ±1 с маркировкой `[ADAPTED]`.

### Шаг 4. Проверка АД-консистентности

Для каждого уровня:
- [ ] Доступные АД — только коды из `core/AD_AVAILABILITY_MATRIX.md`.
- [ ] Запрещённые АД не используются.
- [ ] Если АД-карта отличается от baseline — есть маркировка `[ADAPTED]` и обоснование.

### Шаг 5. Проверка Internal State

- [ ] `desire`, `anxiety`, `desire_tension`, `frustration` ∈ [0, 10].
- [ ] Значения логически согласованы с уровнем (например, U1-А → высокая anxiety, низкое desire).
- [ ] Соответствуют `core/INTERNAL_STATE_BASELINE.md`.

### Шаг 6. Проверка TEC

- [ ] Все 8 TEC-механик (`TEC_001`–`TEC_008`) присутствуют или явно помечены как неприменимые.
- [ ] TEC-спецификация согласована с `knowledge/tec/TEC_DICTIONARY.md`.

### Шаг 7. Cross-Persona Sync

- [ ] Если персонаж взаимодействует с user/sergey/maksim/marina — эти отношения описаны в `relationships/MATRIX.json`.
- [ ] Trust и attraction ∈ [0, 100].
- [ ] Динамики отношений не противоречат `CROSS_PERSONA_RULES.md`.

### Шаг 8. Safety-протоколы

- [ ] `hard_limits` содержат запрет на не-консенсуальное насилие, принуждение, несовершеннолетних.
- [ ] `stop_words` содержат `СТОП`, `ХВАТИТ`, `КРАСНАЯ КАРТОЧКА`.
- [ ] `regression_triggers` не содержат реальных травмирующих триггеров без контекста aftercare.

### Шаг 9. Проверка целостности данных (монолит → модули)

Сравни собранный обратно монолит с оригиналом:
- [ ] Количество фактов не уменьшилось.
- [ ] Нет противоречий между модулями (приоритеты см. `docs/01_MODULAR_ARCHITECTURE_v2.2.md`).
- [ ] `anatomic_anchor` находится только в `core/IDENTITY.json`.
- [ ] Версии модулей в `INDEX.json` соответствуют фактическим версиям в файлах.

### Шаг 10. Сборка обратно в монолит (тестовая)

Выполни мысленную сборку по `ASSEMBLY.md`:
- [ ] Базовый набор загружается без ошибок.
- [ ] Уровень загружается по `default_level`.
- [ ] ag_level=2 и ag_level=3 загружают корректные дополнительные модули.
- [ ] Собранный JSON проходит валидацию по `schemas/persona_schema_v3_2_VOYAGE.json`.

---

## 3. ФОРМАТ ОТЧЁТА

```markdown
# AUDIT REPORT: [Имя]

## Метаданные
- id: [name]
- version: [version]
- audit_date: [ISO-8601]
- auditor: R8 v1.0

## Сводка
| Проверка | Результат | Комментарий |
|----------|-----------|-------------|
| Структурная целостность | ✅/⚠️/❌ | ... |
| JSON-валидация | ✅/⚠️/❌ | ... |
| VSCNO суммы | ✅/⚠️/❌ | ... |
| AD-консистентность | ✅/⚠️/❌ | ... |
| Internal State | ✅/⚠️/❌ | ... |
| TEC-валидация | ✅/⚠️/❌ | ... |
| Cross-Persona Sync | ✅/⚠️/❌ | ... |
| Safety-протоколы | ✅/⚠️/❌ | ... |
| Целостность монолит → модули | ✅/⚠️/❌ | ... |
| Тестовая сборка | ✅/⚠️/❌ | ... |

## Детальные замечания
### [Название проверки]
- ✅ [что прошло]
- ⚠️ [что требует внимания]
- ❌ [что критично]

## Рекомендации
1. ...
2. ...

## Статус
- [ ] PASS — можно использовать в runtime
- [ ] CONDITIONAL PASS — незначительные замечания
- [ ] FAIL — требуется исправление
```

---

## 4. ПРАВИЛА ОФОРМЛЕНИЯ РЕЗУЛЬТАТОВ

- **✅ PASS** — нарушений нет.
- **⚠️ WARNING** — незначительное отклонение, не ломающее runtime (например, отсутствует опциональный модуль).
- **❌ FAIL** — критичная проблема: VSCNO ≠ 10, запрещённый АД, отсутствует required модуль, safety-протокол нарушен.

Если хотя бы одна проверка — ❌, общий статус отчёта — **FAIL**.

---

## 5. HANDOFF

После завершения аудита:
- Сохрани `AUDIT_REPORT_[NAME].md` в `personas/[name]/`.
- Если статус PASS — модуль готов к использованию в runtime.
- Если статус FAIL — верни разработчику и R7 для исправлений.

---

## 6. ПРИМЕР

**Вход:** `personas/andrey_senior/` + `ANDREY_SENIOR_MODULE_v1.2_COMPACT.md`

**Выход:** `personas/andrey_senior/AUDIT_REPORT_ANDREY_SENIOR.md`

---

*Роль R8 Auditor v1.0 — спецификация создана на основе `schemas/persona_schema_v3_2_VOYAGE.md` и `core/*`.*
