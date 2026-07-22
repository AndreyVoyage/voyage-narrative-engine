# 00 — DOCUMENT INDEX — Voyage Narrative Engine (VNE)

> **Назначение.** Карта всех канонических документов проекта: где что лежит, статус, зачем.
> Начинать чтение отсюда. Пути даны относительно корня репозитория.
>
> **Обновлено:** 2026-07-22
> **Правило:** при добавлении/устаревании документа — обновить этот индекс.

Легенда статусов: **ACTIVE** (действующий) · **CANONICAL** (источник правды) ·
**SUPERSEDED** (заменён, читать как историю) · **CLOSED** (трек завершён) ·
**FUTURE** (будущий/кандидат, не авторизован).

---

## 1. Точки входа / ориентация

| Документ | Статус | Зачем |
|---|---|---|
| [`AGENTS.md`](../../AGENTS.md) | CANONICAL | Корневой источник правды для агентов: правила, ссылки на канон. Читать первым. |
| [`README.md`](../../README.md) | ACTIVE | Обзор репозитория. |
| [`STATUS.md`](../../STATUS.md) | ACTIVE | Текущий статус проекта. |
| [`PROJECT_ANALYSIS_v1.0.md`](../../PROJECT_ANALYSIS_v1.0.md) | ACTIVE | Аналитический разбор проекта. |
| **этот файл** `docs/narrative/00_DOCUMENT_INDEX.md` | ACTIVE | Карта документов. |

---

## 2. Решения и архитектура (нарратив)

| Документ | Статус | Зачем |
|---|---|---|
| [`NARRATIVE_DECISIONS_v1.md`](NARRATIVE_DECISIONS_v1.md) | CANONICAL (v1.1) | Продуктовые/архитектурные решения. Приоритет над остальными при конфликте. |
| [`NARRATIVE_ARCHITECTURE.md`](NARRATIVE_ARCHITECTURE.md) | ACTIVE | Слои системы. |
| [`NARRATIVE_ROADMAP.md`](NARRATIVE_ROADMAP.md) | ACTIVE | Текущий статус треков (N7 §10, N8 и т.д.). |
| [`NARRATIVE_FUTURE_TRACKS_v1.md`](NARRATIVE_FUTURE_TRACKS_v1.md) | ACTIVE | Будущие треки (Aside, Voice, Story Setup, …). |
| [`NARRATIVE_HANDOFF_KIMI_WORK.md`](NARRATIVE_HANDOFF_KIMI_WORK.md) | ACTIVE | Правила делегирования исполнителю + строгий промпт-шаблон + audit-checklist. |

---

## 3. Спецификации и контракты сцены/рантайма

| Документ | Статус | Зачем |
|---|---|---|
| [`SCENARIO_SCHEMA_V2_SPEC.md`](SCENARIO_SCHEMA_V2_SPEC.md) | CANONICAL | Схема V2: *что хранится* в сцене (beats, speaker/speech/action/thought, choices, flags). |
| [`STORY_RUNTIME_CONTRACT.md`](STORY_RUNTIME_CONTRACT.md) | CANONICAL | *Как исполняется* сцена (beats, flags, branches, player_state, hot-reload). |
| [`PLAYER_EXPERIENCE_SPEC.md`](PLAYER_EXPERIENCE_SPEC.md) | ACTIVE | *Как отображается* игроку (режимы чтения, thought visibility). |
| [`N5F_HYBRID_JSON_PATH_DECISION.md`](N5F_HYBRID_JSON_PATH_DECISION.md) | ACTIVE | Решение: JSON → generate-ahead `.rpy` (гибридный путь). |
| [`N5G_LIVE_DEV_JSON_CONTRACT.md`](N5G_LIVE_DEV_JSON_CONTRACT.md) | ACTIVE | Контракт будущего live/dev JSON-рантайма (dev-only). |
| [`N1C-RN-WORKFLOW-INTEGRATION-PLAN.md`](N1C-RN-WORKFLOW-INTEGRATION-PLAN.md) | ACTIVE | Интеграция rn-workflow. |

---

## 4. Треки N-серии (фичи)

| Документ | Статус | Зачем |
|---|---|---|
| [`N6_CHARACTER_ASIDE_CONTRACT.md`](N6_CHARACTER_ASIDE_CONTRACT.md) | CLOSED (в main `afa7a13`) | Character Aside: приватный LLM-чат с персонажем, изолированная память, канон read-only. |
| [`N7_PERSONA_DATA_GATEWAY_PREFLIGHT_v1.md`](N7_PERSONA_DATA_GATEWAY_PREFLIGHT_v1.md) | SUPERSEDED | Preflight-архитектура Gateway (историческая запись). |
| [`N7_CANONICAL_STATUS_CLOSEOUT_v1.md`](N7_CANONICAL_STATUS_CLOSEOUT_v1.md) | CANONICAL / CLOSED | Актуальный статус N7 Persona Data Gateway (P1a/P1b/Nika, 138 тестов). |
| [`N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md`](N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md) | ACTIVE (v0) | PAC: нейросеть-соавтор для сценариев + накопление датасета (feeds N8). |
| [`PAC_TRAINING_DATASET_SCHEMA_v1.md`](PAC_TRAINING_DATASET_SCHEMA_v1.md) | CANONICAL (v1) | PAC: формальная схема `pac-training-example-v1` для training_dataset.jsonl. D-N9-4. |
| [`CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md`](CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md) | PROPOSED (v1) | Character Evolution Sandbox: неканоническая ветвящаяся среда для экспериментов с эволюцией персонажа. |
| [`PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md`](PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md) | ACTIVE (v1) | Регистр решений: D-N9 (5 ратифицировано) + D-CES (10 pending) + DEFERRED/BLOCKED/SUPERSEDED. |
| [`PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md`](PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md) | ACTIVE (v1) | Карта параллельной разработки треков A–G, зависимости, forbidden coupling. |
| [`PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md`](PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md) | ACTIVE (v1) | Сохранение идей, обоснований и заменённых подходов (K-001–K-017 + S-001–S-008). |
| [`NARRATIVE_AUTONOMOUS_ENSEMBLE_CONCEPT_v1.md`](NARRATIVE_AUTONOMOUS_ENSEMBLE_CONCEPT_v1.md) | FUTURE (концепт) | Автономный ансамбль: персонажи действуют/общаются сами, автор наблюдает. Non-canon by default. |

> **N8 — Persona Voice Model:** FUTURE, NOT AUTHORIZED. Заблокирован данными; см. `NARRATIVE_ROADMAP.md` и N9 (PAC производит корпус).
> **Character Evolution Sandbox:** PROPOSED. Документация и модель состояния — разрешены. Имплементация — BLOCKED (D-CES-1 – D-CES-10 pending).

---

## 5. Границы с Voyage Framework (отдельный трек)

| Документ | Статус | Зачем |
|---|---|---|
| [`NARRATIVE_VOYAGE_CONTROL_INTEGRATION.md`](NARRATIVE_VOYAGE_CONTROL_INTEGRATION.md) | ACTIVE | Граница нарратива и Voyage-automation. |
| [`FRAMEWORK_VNE_INTEGRATION.md`](../../FRAMEWORK_VNE_INTEGRATION.md) | ACTIVE | Интеграция Framework ↔ VNE. |
| [`VOYAGE_ARCHITECTURE_SPEC_v1.0.md`](../../VOYAGE_ARCHITECTURE_SPEC_v1.0.md) | ACTIVE | Спека Voyage-архитектуры. |

---

## 6. Роли

| Где | Что |
|---|---|
| [`.voyage/roles.yaml`](../../.voyage/roles.yaml) | Роли **разработки** (dev): владение путями, права, включая persona-gateway роли. |
| [`docs/narrative/roles/`](roles/) | Нарративные роли-подсказки (если есть). |
| [`roles/`](../../roles/) | **R1–R8 создания персонажа** (уже существуют как промпты): `ROLE_1_PERSONA_INTERVIEWER` · `ROLE_2_PERSONA_PSYCHOLOGIST` · `ROLE_3_PERSONA_SEXOLOGIST` · `ROLE_4_PERSONA_LINGUIST` · `ROLE_5_PERSONA_PHYSIOGNOMIST` · `ROLE_6_PERSONA_ARCHITECT` · `ROLE_7_REFACTOR` · `ROLE_8_AUDITOR`. Плюс `ROLE_RENPY_ENGINE_QA`, `ROLE_NARRATIVE_EDITOR`, `ROLE_SESSION_FINALIZER`, `ROLE_STATE_MANAGER` и др. |

---

## 7. Ключевой код (для контекста, не документация)

| Путь | Что |
|---|---|
| `services/persona_gateway/` | N7: read-only доменное ядро доступа к персонажам (allowlist, provenance). CLOSED. |
| `tools/aside_*.py`, `tools/llm_provider.py` | N6: провайдер LLM, изолированная память, past-only контекст, оркестратор Aside. |
| `novel/game/aside.rpy` | Ren'Py-экран Character Aside (в main). |
| `tools/pac/` | SUPERSEDED: ветка `feature/n9-pac-v0` (ранняя прикидка). Канонический layout: `services/persona_authoring/` + `tools/pac_cli.py` + `local_runs/pac/` (D-N9-5). |
| `personas/<id>/` + `INDEX.json` | Модульная «ДНК» персонажей (источник правды; монофайл = build artifact). |
| `knowledge_base/` | Теоретический справочный корпус (для R-ролей). |
| `scenarios/` | Сценарии (v1 + V2 JSON). |

---

## 8. Порядок чтения для нового участника

1. `AGENTS.md` → 2. этот индекс → 3. `NARRATIVE_DECISIONS_v1.md` → 4. `NARRATIVE_ROADMAP.md` →
5. нужный контракт (`SCENARIO_SCHEMA_V2_SPEC` / `STORY_RUNTIME_CONTRACT`) →
6. нужный трек (`N6…` / `N7_CANONICAL_STATUS_CLOSEOUT` / `N9…`) →
7. `NARRATIVE_HANDOFF_KIMI_WORK.md` перед делегированием.
