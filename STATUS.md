# STATUS.md — Voyage Narrative Engine

*Дата: 2026-06-17*

## Сводка

Все 6 этапов завершены. Репозиторий приведён к консистентному состоянию:
- Структурные проблемы исправлены (пробелы в именах файлов, устаревшие R6, AGENTS.md).
- Создана единая архитектурная спецификация с 4 полными стволами.
- Созданы спецификации R7 Refactor и R8 Auditor.
- Ствол 4 (Narrative Pipeline) дополнен данными ФМДР, якорной системы, Stop-Frame, runtime-компрессии.

---

## Компоненты

| Компонент | Статус | Файл | Примечание |
|-----------|--------|------|------------|
| `VOYAGE_ARCHITECTURE_SPEC_v1.0.md` | ✅ | корень | 4 ствола, глоссарий, Decision Log, конфликты |
| Ствол 1: System Tree | ✅ | SPEC | Репозиторий, роли, Data Flow, технический долг |
| Ствол 2: Persona Pipeline | ✅ | SPEC | R1–R6 полностью, R7–R8 специфицированы |
| Ствол 3: Scenario Pipeline | ✅ | SPEC | AD, триггеры, State Manager, runtime-файл |
| Ствол 4: Narrative Pipeline | ✅ | SPEC | ФМДР, Character Anchor, Visual Signature, Stop-Frame, `/checkpoint`, `/finalize` |
| `AGENTS.md` | ✅ | корень | AI-ориентир на русском |
| `README.md` | 🟡 | корень | Дисклеймер добавлен, основной контент устарел |
| R1 Persona Interviewer | ✅ | `roles/ROLE_1_PERSONA_INTERVIEWER_v1.4_PROMPT.md` | Готов |
| R2 Persona Psychologist | ✅ | `roles/ROLE_2_PERSONA_PSYCHOLOGIST_v1.4_PROMPT.md` | Готов |
| R3 Persona Sexologist | ✅ | `roles/ROLE_3_PERSONA_SEXOLOGIST_v2.3_PROMPT.md` | Готов |
| R4 Persona Linguist | ✅ | `roles/ROLE_4_PERSONA_LINGUIST_v1.3_PROMPT.md` | Готов |
| R5 Persona Physiognomist | ✅ | `roles/ROLE_5_PERSONA_PHYSIOGNOMIST_v1.3_PROMPT.md` | Готов |
| R6 Modular Architect | ✅ | `roles/ROLE_6_MODULAR_ARCHITECT_v2.3.md` | Готов |
| R7 Refactor | ⏳ | `roles/ROLE_7_REFACTOR_v1.0_PROMPT.md` | Спецификация создана, требует тестирования |
| R8 Auditor | ⏳ | `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md` | Спецификация создана, требует тестирования |
| State Manager | ✅ | `roles/ROLE_STATE_MANAGER_v1.0_PROMPT.md` + `session_finalize.py` | Работает |
| Narrative Editor | ✅ | `roles/ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md` | Готов |
| Visual Extractor / Physiognomist | ✅ | `roles/ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md`, `ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md` | Готовы |
| VSCNO Baseline | ✅ | `core/VSCNO_BASELINE_TABLE.md` | Канон [0, 4] |
| AD Availability Matrix | ✅ | `core/AD_AVAILABILITY_MATRIX.md` | Канон |
| Internal State Baseline | ✅ | `core/INTERNAL_STATE_BASELINE.md` | Канон |
| Memory Baseline Table | ✅ | `core/MEMORY_BASELINE_TABLE.md` | Канон |
| JSON Schema | ✅ | `schemas/persona_schema_v3_2_VOYAGE.json` | Канон |
| `personas/kira/` (модульная структура) | ✅ | `personas/kira/` | Эталонная реализация |
| Монолитные runtime-модули | ✅ | `personas/*.json` | Активно используются |
| `scenarios/SCENARIO_LIBRARY.json` | ✅ | `scenarios/SCENARIO_LIBRARY.json` | 13 сценариев + visual scenes |
| `tools/assemble.sh` | 🔴 | `tools/assemble.sh` | Сломан, ссылки устарели |
| `build_prompt_v3.sh` | 🔴 | `build_prompt_v3.sh` | Сломан, ссылки устарели |
| `PRELOAD_VNE_v3.2.1.md` | 🔍 | `PRELOAD_VNE_v3.2.1.md` | `[NEEDS_DATA]` — отсутствует |

---

## Известные проблемы

| ID | Проблема | Статус | Решение |
|----|----------|--------|---------|
| `C1` | `README.md` устарел и содержит неверные ссылки | 🟡 | Добавлен дисклеймер; полное обновление отложено |
| `C2` | Роли R3/R4/R5 ссылаются на `VOYAGE_NARRATIVE_CORE_v2.md` и `QWEN_ADAPTER_v2.md`, которых нет | 🔍 | `[NEEDS_DATA]` — восстановить файлы или обновить ссылки |
| `C3` | Шкала VSCNO [0, 10] встречается в legacy-файлах | 🟡 | При миграции приводить к канонической [0, 4] |
| `C4` | Входные версии ролей в R3/R4/R5 не соответствуют актуальным | 🟡 | Привести ссылки к актуальным версиям |
| `C5` | Build scripts ссылаются на несуществующие пути | 🔴 | Починить или пометить как legacy |

---

## Следующие шаги (для разработчика)

1. **Тестирование R7/R8:** запустить `ANDREY_SENIOR_MODULE_v1.2` → `personas/andrey_senior/` → `AUDIT_REPORT_ANDREY_SENIOR.md`.
2. **Создание PRELOAD:** написать `PRELOAD_VNE_v3.2.1.md` на основе Ствола 4 и `core/*`.
3. **Исправление build scripts:** починить `tools/assemble.sh` и `build_prompt_v3.sh` под актуальные пути.
4. **KB-файлы:** создать `knowledge_base/narrative/KB_NARRATIVE_*.md` для повторного использования.
5. **Offline runtime:** протестировать Ollama/Qwen2.5:7b с собранным монофайлом.
6. **Обновление README:** полностью переписать `README.md` после стабилизации архитектуры.

---

*STATUS.md создан автоматически по завершении Этапа 6.*
