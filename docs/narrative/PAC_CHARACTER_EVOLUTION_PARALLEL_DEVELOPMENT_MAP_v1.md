# PAC & Character Evolution — Parallel Development Map v1

> **Дата:** 2026-07-22
> **Статус:** ACTIVE — обновляется при изменении зависимостей.
> **Назначение:** Документировать треки параллельной разработки PAC, Character Evolution Sandbox и смежных систем — зависимости, запрещённые соединения (forbidden coupling), интеграционные гейты и границы владения.

---

## 1. Обзор треков

```
TRACK A  PAC v0 Authoring Loop            [ACTIVE — документация готова, имплементация отдельно]
TRACK B  Character Evolution Specification [ACTIVE — только документация и модель]
TRACK C  Corpus & Quality Pipeline         [ACTIVE — схема + правила]
TRACK D  N7 P2 MCP Adapter                 [DEFERRED]
TRACK E  PAC Interface (CLI)               [DEFERRED до имплементации v0]
TRACK F  N8 Persona Voice Model            [BLOCKED — недостаточно кураторских примеров]
TRACK G  Sandbox Implementation             [BLOCKED — D-CES решения не разрешены]
```

---

## 2. TRACK A — PAC v0 Authoring Loop

**Статус:** Документация готова. Имплементация требует отдельной авторизации.

**Зависит от:**
- ✅ N7 Persona Gateway (read-side) — CLOSED.
- ✅ Provider layer (N6 `tools/llm_provider.py`) — CLOSED AND INTEGRATED.
- ✅ Dataset schema (`pac-training-example-v1`) — RATIFIED (D-N9-4).

**НЕ зависит от:**
- ❌ MCP сервера.
- ❌ Базы данных (SQLite/PostgreSQL).
- ❌ Web UI.
- ❌ N8 Persona Voice Model.
- ❌ Реализованного Sandbox.

**Гейт интеграции:**
- v0 acceptance criteria выполнены (≥20 turns, ≥10 APPROVE_DATASET, FMDR ≥90%).
- `training_dataset.jsonl` валидируется построчно.
- 0 записей в канонические директории.
- PAC v0 не пишет в канон.

**Владелец:** Narrative authoring track (β).

---

## 3. TRACK B — Character Evolution Specification

**Статус:** PROPOSED. Документация и проектирование модели состояния — разрешены. Имплементация — BLOCKED.

**Зависит от:**
- ✅ N7 Persona Gateway.
- ✅ N6 memory pattern (`aside_memory_store`).
- ❌ D-CES-1 – D-CES-10 решений (OWNER_DECISION_PENDING).

**НЕ зависит от:**
- ❌ PAC v0 (спецификация Sandbox может разрабатываться параллельно).
- ❌ N8.
- ❌ Ren'Py runtime.

**Гейт интеграции:**
- D-CES решения разрешены владельцем.
- Модель данных утверждена.
- Отдельная авторизация на имплементацию.

**Владелец:** Narrative / character track (отдельно от PAC).

---

## 4. TRACK C — Corpus & Quality Pipeline

**Статус:** ACTIVE (схема ratificирована).

**Зависит от:**
- ✅ Dataset schema (`pac-training-example-v1`).
- ✅ Provenance rules.
- ✅ FMDR validation rules.
- ✅ Speech uniqueness rules (R8 auditor pattern).

**Компоненты:**
- Provenance tracking (`human-written` / `human-edited` / `model-raw-approved`).
- Canon snapshot (`source_commit` + `content_hash` per module, from Gateway provenance).
- FMDR validation gate.
- Speech uniqueness gate.
- Edit metrics (`was_edited` в v0; расширенные метрики DEFERRED).
- Dataset inspection (проверка JSONL на валидность).

**НЕ зависит от:**
- ❌ PAC v0 имплементации.
- ❌ N8.

**Гейт интеграции:**
- `PAC_TRAINING_DATASET_SCHEMA_v1.md` — RATIFIED.
- Правила валидации задокументированы.

**Владелец:** Narrative / data quality (разделяется с PAC).

---

## 5. TRACK D — N7 P2 MCP Adapter

**Статус:** DEFERRED до отдельной авторизации.

**Зависит от:**
- ✅ N7 P1 Persona Gateway (CLOSED).
- ❌ Отдельная авторизация владельца.

**Описание:** Read-only MCP transport adapter для Cline/VS Code authoring. Не содержит persona business logic.

**НЕ зависит от:**
- ❌ PAC v0.
- ❌ Sandbox.

**Гейт интеграции:**
- Авторизация владельца.
- Transport-only, read-only.

**Владелец:** N7 (расширение Persona Gateway).

---

## 6. TRACK E — PAC Interface (CLI)

**Статус:** DEFERRED до имплементации PAC v0.

**Зависит от:**
- ❌ PAC v0 domain logic (`services/persona_authoring/`).
- ✅ D-N9-5 (code layout).

**Описание:** `tools/pac_cli.py` — тонкая CLI-оболочка над domain-ядром. Web UI — отдельное решение, DEFERRED.

**Гейт интеграции:**
- PAC v0 domain logic реализовано.

**Владелец:** Narrative / PAC.

---

## 7. TRACK F — N8 Persona Voice Model

**Статус:** BLOCKED.

**Зависит от:**
- ❌ Достаточное количество кураторских примеров (PAC v0 производит корпус).
- ❌ Отдельная авторизация владельца.

**Описание:** Fine-tune голоса персонажа (LoRA/GGUF) на основе approved-примеров из PAC.

**НЕ зависит от:**
- ❌ Sandbox.
- ❌ MCP adapter.

**Гейт интеграции:**
- Накоплен достаточный корпус approved-примеров.
- Отдельная авторизация.

**Владелец:** Narrative / N8 (будущий трек).

---

## 8. TRACK G — Sandbox Implementation

**Статус:** BLOCKED.

**Зависит от:**
- ❌ D-CES-1 – D-CES-10 решений (OWNER_DECISION_PENDING).
- ❌ Утверждённая модель данных.

**Описание:** Реализация Character Evolution Sandbox.

**НЕ зависит от:**
- ❌ PAC v0 имплементации (спецификация идёт параллельно).
- ❌ N8.

**Гейт интеграции:**
- D-CES решения разрешены.
- Модель данных утверждена.
- Отдельная авторизация на код.

**Владелец:** Narrative / Character Evolution (отдельный трек от PAC).

---

## 9. Граф зависимостей

```
N7 Persona Gateway (CLOSED)
├──▶ TRACK A: PAC v0 Authoring Loop [документация готова, имплементация отдельно]
│    ├──▶ TRACK C: Corpus & Quality Pipeline [схема ratificирована]
│    ├──▶ TRACK E: PAC CLI [DEFERRED]
│    └──▶ TRACK F: N8 Voice Model [BLOCKED — ждёт корпус]
│
├──▶ TRACK B: Character Evolution Spec [PROPOSED, документация разрешена]
│    └──▶ TRACK G: Sandbox Implementation [BLOCKED — ждёт D-CES]
│
└──▶ TRACK D: N7 P2 MCP Adapter [DEFERRED]

N6 aside_memory_store (CLOSED)
├──▶ TRACK A (PAC memory pattern)
└──▶ TRACK B (Sandbox memory pattern)
```

---

## 10. Что можно безопасно параллелить

| Пара треков | Статус | Условия |
|-------------|--------|---------|
| **Track A (PAC docs) ∥ Track B (Sandbox spec)** | ✅ Безопасно | Оба — documentation-only. Разные документы, разные namespace. |
| **Track C (Corpus pipeline) ∥ Track B (Sandbox spec)** | ✅ Безопасно | Независимые концепции. |
| **PAC v0 implementation ∥ Sandbox spec** | ✅ Безопасно | При условии: PAC не потребляет Sandbox состояние (D-CES-4 pending). По умолчанию canon-only. |
| **Track A ∥ Track D (MCP adapter)** | ✅ Безопасно | Независимые треки; PAC v0 не требует MCP. |
| **Track B (Sandbox spec) ∥ Track D (MCP adapter)** | ✅ Безопасно | Разные домены. |

---

## 11. Запрещённое соединение (FORBIDDEN COUPLING)

| Соединение | Причина |
|------------|---------|
| **PAC → Canon write** | PAC — read-only к канону. Запись в `personas/`, `scenarios/`, `knowledge_base/`, `v2_*` запрещена. |
| **Sandbox → Canon write** | Sandbox — non-canon. Автоматическое повышение до канона запрещено (REJECTED: D-SUP-8). |
| **PAC → N8 training автоматически** | Только APPROVE_DATASET. Сырой вывод модели не становится training target. |
| **Sandbox → N8 training автоматически** | Данные Sandbox — неканонические, не curated. Не попадают в N8. |
| **PAC ↔ Voyage Framework automation** | PAC — authoring tool, не Framework automation. |
| **PAC ↔ Ren'Py runtime state** | Разные плоскости. PAC не влияет на сейвы/прогресс игры. |
| **Sandbox ↔ Ren'Py runtime state** | Разные плоскости. Сейвы игры и Sandbox-снапшоты — разные namespace. |
| **Модель → выбор провайдера** | Провайдер выбирает человек перед запуском. Автоматический fallback запрещён (D-N9-3). |

---

## 12. Границы владения

| Трек | Владелец | Документация | Код (когда авторизован) |
|------|----------|--------------|------------------------|
| PAC v0 | Narrative / β authoring | `docs/narrative/N9_*.md`, `PAC_TRAINING_DATASET_SCHEMA_v1.md` | `services/persona_authoring/`, `tools/pac_cli.py` |
| Sandbox | Narrative / Character Evolution | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` | `services/character_evolution/` (предложено, D-CES-8 pending) |
| Corpus pipeline | Narrative / data quality | `PAC_TRAINING_DATASET_SCHEMA_v1.md` | Часть PAC domain logic |
| MCP adapter (N7 P2) | N7 Gateway | `N7_CANONICAL_STATUS_CLOSEOUT_v1.md` | Транспортный адаптер (read-only) |
| N8 Voice Model | Narrative / N8 (будущий) | Будет создан | `services/persona_voice/` (предварительно) |

---

*Конец PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md*