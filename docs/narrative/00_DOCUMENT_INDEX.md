# 00 — DOCUMENT INDEX — Voyage Narrative Engine (VNE)

> **Назначение.** Карта всех канонических документов проекта: где что лежит, статус, зачем.
> Начинать чтение отсюда. Пути даны относительно корня репозитория.
>
> **Обновлено:** 2026-08-16 (добавлены CRP vNext ratification + decision register + MVP spec/contracts)
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
| [`SCENARIO_SCHEMA_V2_SPEC.md`](SCENARIO_SCHEMA_V2_SPEC.md) | HISTORICAL / FOUNDATIONAL (source schema) | Схема V2: *что хранится* в сцене (beats, speaker/speech/action/thought, choices, flags). Source/authoring-схема; accepted-scene контракт — ASS/OrderedASS (см. §7b). |
| [`STORY_RUNTIME_CONTRACT.md`](STORY_RUNTIME_CONTRACT.md) | HISTORICAL / PARTIAL (live-JSON direction) | *Как исполняется* сцена (beats, flags, branches, player_state, hot-reload). Live-JSON runtime не реализован; release-путь — deterministic generate-ahead + OrderedASS exporter (см. §7b). |
| [`PLAYER_EXPERIENCE_SPEC.md`](PLAYER_EXPERIENCE_SPEC.md) | ACTIVE | *Как отображается* игроку (режимы чтения, thought visibility). |
| [`N5F_HYBRID_JSON_PATH_DECISION.md`](N5F_HYBRID_JSON_PATH_DECISION.md) | ACTIVE | Решение: JSON → generate-ahead `.rpy` (гибридный путь). |
| [`N5G_LIVE_DEV_JSON_CONTRACT.md`](N5G_LIVE_DEV_JSON_CONTRACT.md) | ACTIVE | Контракт будущего live/dev JSON-рантайма (dev-only). |
| [`N1C-RN-WORKFLOW-INTEGRATION-PLAN.md`](N1C-RN-WORKFLOW-INTEGRATION-PLAN.md) | ACTIVE | Интеграция rn-workflow. |

---

## 4. Треки N-серии (фичи)

| Документ | Статус | Зачем |
|---|---|---|
| [`N6_CHARACTER_ASIDE_CONTRACT.md`](N6_CHARACTER_ASIDE_CONTRACT.md) | CLOSED (в main `afa7a13`) | Character Aside: приватный LLM-чат с персонажем, изолированная память, канон read-only. |
| [`N6B_ASIDE_V2_PARALLEL_MEMORY_PREFLIGHT_v1.md`](N6B_ASIDE_V2_PARALLEL_MEMORY_PREFLIGHT_v1.md) | PREFLIGHT / SLICE 1 ИНТЕГРИРОВАН / SLICE 2 PREFLIGHT ЗАВЕРШЁН | Aside v2: параллельная память, отдельные отношения с игроком, эмоц. инерция, rollback spoiler-guard, роль-модель C. Реестр D-ASD-01…20 + D-ASD-G — все OWNER_DECIDED. Slice 1 (Memory Identity & Safety Foundation) интегрирован в `origin/main`, tests 33/33 + 246/246 PASS. Slice 2 / Stage 3 SQLite+FTS5: read-only preflight завершён (2026-08-01), два owner decisions ратифицированы (2026-08-02): D-ASD-S2-MIGRATION и D-ASD-S2-DB-SCOPE (OWNER_RATIFIED). Bounded implementation scope ещё НЕ авторизован. Runtime branch `9b00ede` и future stages (Slice 3–7) исключены. |
| [`N7_PERSONA_DATA_GATEWAY_PREFLIGHT_v1.md`](N7_PERSONA_DATA_GATEWAY_PREFLIGHT_v1.md) | SUPERSEDED | Preflight-архитектура Gateway (историческая запись). |
| [`N7_CANONICAL_STATUS_CLOSEOUT_v1.md`](N7_CANONICAL_STATUS_CLOSEOUT_v1.md) | CANONICAL / CLOSED | Актуальный статус N7 Persona Data Gateway (P1a/P1b/Nika, 138 тестов). |
| [`C4_U_RUNTIME_CANONICAL_STATUS_CLOSEOUT_v1.md`](C4_U_RUNTIME_CANONICAL_STATUS_CLOSEOUT_v1.md) | CANONICAL / CLOSED | Канонический closeout C4-U-RUNTIME core Ren'Py runtime visual proof: core visual contract закрыт (PASS); harness clean-completion и V0 forensic долг — открыты, неблокирующие. |
| [`N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md`](N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md) | ACTIVE (v0) | PAC: нейросеть-соавтор для сценариев + накопление датасета (feeds N8). |
| [`PAC_TRAINING_DATASET_SCHEMA_v1.md`](PAC_TRAINING_DATASET_SCHEMA_v1.md) | CANONICAL (v1) | PAC: формальная схема `pac-training-example-v1` для training_dataset.jsonl. D-N9-4. |
| [`CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md`](CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md) | PROPOSED (v1) | Character Evolution Sandbox: неканоническая ветвящаяся среда для экспериментов с эволюцией персонажа. |
| [`PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md`](PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md) | ACTIVE (v1) | Регистр решений: D-N9 (5 ратифицировано) + D-ASD-S2 (2 ратифицировано) + D-CES (10 pending) + DEFERRED/BLOCKED/SUPERSEDED. |
| [`PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md`](PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md) | ACTIVE (v1) | Карта параллельной разработки треков A–G, зависимости, forbidden coupling. |
| [`PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md`](PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md) | ACTIVE (v1) | Сохранение идей, обоснований и заменённых подходов (K-001–K-017 + S-001–S-008). |
| [`NARRATIVE_AUTONOMOUS_ENSEMBLE_CONCEPT_v1.md`](NARRATIVE_AUTONOMOUS_ENSEMBLE_CONCEPT_v1.md) | FUTURE (концепт) | Автономный ансамбль: персонажи действуют/общаются сами, автор наблюдает. Non-canon by default. |
| [`AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md`](AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md) | PROPOSED (v1) | Role Registry, Role Evolution, per-role Knowledge Profile, будущий Knowledge Router и context assembly. Read-side = Gateway; builders = reusable primitives. Один consolidated preflight. Impl NOT AUTHORIZED (D-RKR-1–D-RKR-15 pending). |
| [`CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md`](CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md) | **OWNER-RATIFIED DIRECTION** (2026-08-16, updated same day) | CRP vNext ("Character Reconstruction Pipeline", formal name for what was informally called "Variant C"): ratifies CRP-OD-1…14 (owner shorthand OD-1…10, D-CRP-11…14) — vNext direction, R4/R5/R7 authority, MVP role subset, revision budget, Kira benchmark split, confidence policy, R3 gate, contradiction priority, Role Registry mechanics, PAC/Sandbox access policy, legacy KB policy. Successor direction to legacy R1–R8 (`roles/`), which remains reference-only. **IMPLEMENTATION NOT AUTHORIZED.** |
| [`CRP_VNEXT_DECISION_REGISTER_v1.md`](CRP_VNEXT_DECISION_REGISTER_v1.md) | **ACTIVE DECISION REGISTER** (2026-08-16, updated same day) | Companion register: full CRP-OD-1…14 entries, complete §37 (18/18) and D-RKR (15/15) historical mapping, claim-taxonomy reconciliation (source_type + confidence axes; no pre-existing detailed taxonomy found to reconcile against — see §D), owner-gap countdown (**0 open**, was 4), implementation-parameter and source-cleanup backlogs. |
| [`CRP_MVP_SPEC_v1.md`](CRP_MVP_SPEC_v1.md) | **OWNER_RATIFIED_SPECIFICATION** (accepted 2026-08-16, owner gap count **0**) | First implementable CRP vNext MVP specification, accepted by the owner in full following an independent zero-gap review: roles R1+R2+R4+R6+R8 active (R3/R5 excluded, R7 as deterministic function), execution DAG, 3-execution revision-loop semantics (initial + 2 corrections), registry/knowledge-routing/PAC-Sandbox specification, Kira benchmark design (not executed), full mapping of all 20 decision-register implementation parameters and 4 source-cleanup items, MVP acceptance criteria. Builds on `CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md` without reopening any CRP-OD. **IMPLEMENTATION_NOT_AUTHORIZED** — ratification of the spec is a separate act from authorizing implementation. |
| [`CRP_MVP_CONTRACTS_v1.md`](CRP_MVP_CONTRACTS_v1.md) | **OWNER_RATIFIED_SPECIFICATION_CONTRACTS** (accepted 2026-08-16) | Companion contracts document: conceptual schemas for SourceEvidence, RoleClaim, ContradictionRecord, RoleTask, RoleResult, RoleRegistryEntry, KnowledgeProfile, CandidateCharacterPackage, ReconstructionAudit, BehavioralValidationRequest/Result — fields, invariants, producer/consumer, forbidden behavior, versioning, per contract. **IMPLEMENTATION_NOT_AUTHORIZED.** |
| [`CRP_MAINLINE_CONSOLIDATION_V1.md`](CRP_MAINLINE_CONSOLIDATION_V1.md) | **IMPLEMENTATION EVIDENCE RECORD** (2026-09-21) | Records that a real, tested CRP vNext implementation (`services/crp_authoring/`) was built and exercised on `feature/crp-mvp-v1` and descendants despite the specs above being marked IMPLEMENTATION_NOT_AUTHORIZED, including a real live-provider KIRA run (RUN_015), R8 PASS, and HUMAN_APPROVED acceptance (`accepted/kira/`). Documents the consolidated port onto `feature/character-lab-crp-integration-v1` (from `origin/main`), the added R3 relevance boundary, the Lab-independent application adapter, and the still-unreconciled `CRP_VNEXT_DECISION_REGISTER_v1.md` divergence. The ported `accepted/kira/*` is a regression/reference fixture only — **not** a Character Canon promotion. |

> **N8 — Persona Voice Model:** FUTURE, NOT AUTHORIZED. Заблокирован данными; см. `NARRATIVE_ROADMAP.md` и N9 (PAC производит корпус).
> **Character Evolution Sandbox:** PROPOSED. Документация и модель состояния — разрешены. Имплементация — BLOCKED (D-CES-1 – D-CES-10 pending).

---

## 4b. Внешние исследовательские источники (research-вход, не канон)

| Документ | Статус | Зачем |
|---|---|---|
| [`docs/research/README.md`](../research/README.md) | REFERENCE | Указатель research-источников + карта «раздел отчёта → трек». |
| [`docs/research/VNE_TECH_SURVEY_2026-07`](../research/VNE_TECH_SURVEY_2026-07.docx) | REFERENCE | Обзор индустрии AI-персонажей 2025–2026. Валидирует архитектуру VNE; питает решения PAC/D-CES/D-RKR/N8. НЕ канон, цифры не принимать на веру. |

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

## 7b. Implemented Scenario architecture (accepted-scene / ASS) — код-области

> **IMPLEMENTED CODE AREA** (не CANONICAL DOCUMENT). Формальных Markdown-спек для ASS/OrderedASS
> пока нет — источник правды по этим механизмам находится в коде и тестах. Не путать с
> CANONICAL DOCUMENT (Markdown-спеки) и HISTORICAL / LEGACY CONTRACT (`SCENARIO_SCHEMA_V2_SPEC`,
> `STORY_RUNTIME_CONTRACT` — §3).

### 7b.1 Accepted-scene authority (ASS / OrderedASS)

| Область | Путь | Что делает |
|---|---|---|
| ASS v0 (`ass/0.1`) | `services/ass/` (`model.py`, `importer.py`, `hashing.py`) | Неизменяемый accepted-scene snapshot; импорт из Scenario V2 JSON. |
| OrderedASS (`ass/0.2`) | `services/ass/ordered.py` | Текущий канонический accepted-scene контракт; проекция из `SceneBody`. |
| Canonical store | `services/ass/store.py` | Immutable-файлы канонических OrderedASS; атомарная hard-link публикация; SHA-256. |

### 7b.2 Authoring / draft lifecycle

| Область | Путь | Что делает |
|---|---|---|
| SceneBody | `services/scene_body/` | Единый редактируемый authoring-пейлоад (`scene_body/1.0`). |
| Scene Draft lifecycle | `services/scene_draft/` | DRAFT → validate → ACCEPT; `AcceptanceLink`; immutable accepted version. |
| Editor Application Service | `services/editor_application/` | Тонкий UI-агностичный фасад над domain-сервисами. |
| Desktop editor | `ui/editor_desktop/` | Qt (PySide6) editor поверх фасада; реальное авторирование сцен. |

### 7b.3 Canon / interpretation / media / prompt

| Область | Путь | Что делает |
|---|---|---|
| Location Canon | `services/location_canon/` | Неизменяемая каноническая идентичность локации (read-only). |
| Character Canon bridge | `services/character_canon_bridge/` | Read-only мост к Character Canon; snapshot + статус (production gate `APPROVED_AS_CANON`). |
| Scene Interpretation | `services/scene_interpretation/` | Immutable interpretation artifact; якоря ASS/Location/Character. |
| MediaPlan | `services/mediaplan/` | Immutable упорядоченный медиа-план сцены (Scenario-owned). |
| Prompt Composer | `services/prompt_composer/` | Детерминированный provider-neutral `PromptPackage`. |

### 7b.4 Workspace / publication

| Область | Путь | Что делает |
|---|---|---|
| workspace_project | `services/workspace_project/` | `ProjectManifest`, `AcceptedOrderedASSBatch`, `WorkspaceIndex` (membership boundary). |
| Story Sequence V0 | `services/story_sequence/` | Scenario-owned story-level scene order + entry (`vne_story_sequence/0.1`: `ordered_scene_ids`, `start_scene_id`); exact-coverage validated against `AcceptedOrderedASSBatch`; drives deterministic export order + `vne_story_start` entry label. |
| OrderedASS → Ren'Py | `tools/vne_to_renpy/ordered_ass_exporter.py`, `ordered_ass_project_exporter.py`, `ordered_asset_resolver.py` | Детерминированный экспорт OrderedASS → `.rpy`. |
| Canonical publisher | `tools/vne_to_renpy/ordered_ass_canonical_publisher.py` | Публикация в `novel/game/ordered_ass_generated.rpy` + generated-file firewall. |

> **FUTURE CONTRACT (не реализовано):** Character Media portable consumption (`WAITING_FOR_PORTABLE_MEDIA_HANDOFF`),
> VCP/`.vchar` Scenario consumer, shared Character Lab/Scenario workspace membership, Studio-интеграция,
> общий NARRATIVE shell. См. `NARRATIVE_DECISIONS_v1.md` §15 и `NARRATIVE_ROADMAP.md` §13.

---

## 8. Порядок чтения для нового участника

1. `AGENTS.md` → 2. этот индекс → 3. `NARRATIVE_DECISIONS_v1.md` (вкл. §15 accepted-scene authority) →
4. `NARRATIVE_ROADMAP.md` (вкл. §13 reconciliation) →
5. §7b этого индекса (реализованные accepted-scene код-области) →
6. нужный контракт (`SCENARIO_SCHEMA_V2_SPEC` / `STORY_RUNTIME_CONTRACT` — historical source/live-JSON) →
7. нужный трек (`N6…` / `N7_CANONICAL_STATUS_CLOSEOUT` / `N9…`) →
8. `NARRATIVE_HANDOFF_KIMI_WORK.md` перед делегированием.