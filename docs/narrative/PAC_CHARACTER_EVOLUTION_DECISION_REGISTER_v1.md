# PAC & Character Evolution — Decision Register v1

> **Дата:** 2026-07-22
> **Статус:** ACTIVE — регистр пополняется по мере появления решений.
> **Назначение:** Централизованный регистр всех решений по PAC (N9) и Character Evolution Sandbox. Каждое решение имеет уникальный ID, статус, владельца и связи с документами.

---

## 1. Статусная модель решений

| Статус | Описание |
|--------|----------|
| `OWNER_RATIFIED` | Решение ратифицировано владельцем. |
| `OWNER_DECISION_PENDING` | Требуется решение владельца. |
| `PROPOSED` | Предложено, не рассмотрено владельцем. |
| `DEFERRED` | Отложено до указанной фазы/условия. |
| `BLOCKED` | Заблокировано зависимостью. |
| `SUPERSEDED` | Заменено более новым решением. |
| `REJECTED` | Отклонено владельцем. |
| `OPEN_RESEARCH_QUESTION` | Открытый исследовательский вопрос. |

---

## 2. Ратифицированные решения N9 (PAC)

### D-N9-1 — PAC POSITIONING

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_RATIFIED |
| **Дата** | 2026-07-22 |
| **Документ** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §7 |
| **Решение** | PAC — активный β-трек (authoring). PAC — developer authoring companion; upstream от N8; не player-facing; не game runtime; не Voyage Framework automation. |
| **Implications** | PAC не пересекается с α-треком (Ren'Py VN) на уровне runtime; использует Gateway для read-side. |

### D-N9-2 — V0 FIRST

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_RATIFIED |
| **Дата** | 2026-07-22 |
| **Документ** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §6–§7 |
| **Решение** | PAC стартует с v0: без MCP-сервера, без базы данных, без Web UI, без автономной записи в канон. |
| **Implications** | v0 — валидация петли «соавторства»; критерии успеха измеримы (≥20–30 turns, ≥10 APPROVE_DATASET, FMDR ≥90%). |

### D-N9-3 — PROVIDER POLICY

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_RATIFIED |
| **Дата** | 2026-07-22 |
| **Документ** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §7 |
| **Решение** | Local-first; optional cloud comparison осознанно, per-run; автоматический fallback local→cloud ЗАПРЕЩЁН; провайдер выбирается человеком перед запуском; provider и model записываются в каждый approved-пример. |
| **Implications** | Для adult/чувствительного контента default = local. |

### D-N9-4 — DATASET CONTRACT

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_RATIFIED |
| **Дата** | 2026-07-22 |
| **Документ** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §9, `PAC_TRAINING_DATASET_SCHEMA_v1.md` |
| **Решение** | Схема датасета: `pac-training-example-v1`. Правила одобрения, provenance, canon snapshot — задокументированы до начала накопления данных. |
| **Implications** | Все примеры без APPROVE_DATASET не попадают в main-датасет. |

### D-N9-5 — FUTURE CODE LAYOUT

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_RATIFIED |
| **Дата** | 2026-07-22 |
| **Документ** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §11 |
| **Решение** | `services/persona_authoring/` — domain/application logic; `tools/pac_cli.py` — thin CLI adapter; `local_runs/pac/` — non-canon runtime output. |
| **Implications** | Заменяет раннюю прикидку `tools/pac/`; домен отделён от интерфейса. |

---

## 3. Открытые решения — Character Evolution Sandbox (D-CES)

### D-CES-1 — GRANULARITY OF EVOLUTION

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Ограничиваются ли эволюционные изменения памятями/транзиентным состоянием, или Sandbox также может предлагать дельты личности (personality deltas)? |
| **Риски** | Personality deltas без ограничений быстро делают персонажа неузнаваемым. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3. |

### D-CES-2 — ATOMIC VERSIONED UNIT

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Что является атомарной версионируемой единицей: снапшот, сессия, событие, сцена или ветка? |
| **Риски** | Без ясной единицы версионирования fork/reset/diff становятся неопределёнными. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3. |

### D-CES-3 — REPRESENTATION OF FORK / RESET / ARCHIVE

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Как представляются fork, reset и archive в модели данных? Какие поля обязательны, какие метаданные сохраняются? |
| **Риски** | Неправильная модель хранения приведёт к потере истории или невозможности сравнения веток. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3. |

### D-CES-4 — PAC CONSUMPTION OF SANDBOX STATE

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Может ли PAC потреблять состояние Sandbox для генерации, или PAC обязан использовать только канон (canon-only)? |
| **Риски** | Если PAC видит неканоническое состояние, грань между экспериментом и каноном размывается. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §2, `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md`. |

### D-CES-5 — MULTI-CHARACTER BRANCHES

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Может ли одна ветка Sandbox эволюционировать нескольких персонажей одновременно? |
| **Риски** | Мульти-персонажные ветки усложняют fork/compare/reset и увеличивают стоимость. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §4 (отличие от Autonomous Ensemble). |

### D-CES-6 — RECOGNIZABILITY METRICS

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Какие метрики определяют, остаётся ли персонаж «узнаваемым» после эволюции? |
| **Риски** | Без метрик невозможно автоматически предупредить о «размывании» персонажа. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §5. |

### D-CES-7 — EVIDENCE FOR CANON CHANGE

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Какие доказательства (evidence) требуются перед тем, как предложить изменение канона на основе Sandbox-эксперимента? |
| **Риски** | Слишком низкий порог — канон деградирует; слишком высокий — Sandbox бесполезен. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3, §5. |

### D-CES-8 — CODE LOCATION

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Где будет размещаться код Sandbox? Возможная локация: `services/character_evolution/`. |
| **Связанные документы** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §11 (аналогия с `services/persona_authoring/`). |

### D-CES-9 — MEMORY INFRASTRUCTURE

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Использует ли Sandbox инфраструктуру памяти сессии PAC (общий store) или отдельное хранилище? |
| **Риски** | Общий store между PAC и Sandbox может привести к утечке неканонических данных. |
| **Связанные документы** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §2.Б. |

### D-CES-10 — RETENTION / DELETION RULES

| Поле | Значение |
|------|----------|
| **Статус** | OWNER_DECISION_PENDING |
| **Вопрос** | Какие правила хранения и удаления применяются к неудачным или чувствительным экспериментам? |
| **Риски** | Неограниченное хранение чувствительных Sandbox-экспериментов — риск приватности. |
| **Связанные документы** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §5. |

---

## 4. Отложенные решения (DEFERRED)

### D-DEF-1 — MCP ADAPTER (N7 P2)

| Поле | Значение |
|------|----------|
| **Статус** | DEFERRED |
| **Описание** | Read-only MCP transport adapter для Cline/VS Code authoring. |
| **Требуется** | Отдельная авторизация владельца. |
| **Связанные документы** | `N7_CANONICAL_STATUS_CLOSEOUT_v1.md` §3. |

### D-DEF-2 — WEB UI

| Поле | Значение |
|------|----------|
| **Статус** | DEFERRED |
| **Описание** | Web-интерфейс для PAC с кнопками generate/approve/reject. |
| **Требуется** | После v0 и подтверждения полезности. |

### D-DEF-3 — DATABASE SCALE

| Поле | Значение |
|------|----------|
| **Статус** | DEFERRED |
| **Описание** | Переход от JSONL/JSON к SQLite/PostgreSQL. |
| **Требуется** | После v0, при масштабировании. |

---

## 5. Заблокированные решения (BLOCKED)

### D-BLK-1 — N8 PERSONA VOICE MODEL

| Поле | Значение |
|------|----------|
| **Статус** | BLOCKED |
| **Блокировка** | Недостаточно кураторских примеров (PAC v0 производит корпус). |
| **Описание** | Fine-tune голоса персонажа (LoRA). |
| **Связанные документы** | `NARRATIVE_ROADMAP.md` §10, `N7_CANONICAL_STATUS_CLOSEOUT_v1.md` §3. |

### D-BLK-2 — SANDBOX IMPLEMENTATION

| Поле | Значение |
|------|----------|
| **Статус** | BLOCKED |
| **Блокировка** | Не разрешены D-CES-1 – D-CES-10; не утверждена модель данных. |
| **Описание** | Реализация Character Evolution Sandbox. |

---

## 6. Заменённые/отклонённые решения (SUPERSEDED / REJECTED)

### D-SUP-1 — OLD PAC V0 LOCATION

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | D-N9-5 |
| **Описание** | Ранняя прикидка размещения кода в `tools/pac/`. Заменена на `services/persona_authoring/` + `tools/pac_cli.py` + `local_runs/pac/`. |

### D-SUP-2 — UNSAFE read_persona_module(path)

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | Существующий N7 Persona Gateway |
| **Описание** | Прямое чтение файла по пути (path traversal risk). Заменено на Gateway `read_module(id, module_id)`. |

### D-SUP-3 — START WITH MCP SERVER

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | D-N9-2 (v0 first) |
| **Описание** | Идея начинать PAC с реализации MCP-сервера. v0 не требует MCP. |

### D-SUP-4 — START WITH DATABASE

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | D-N9-2 (v0 first) |
| **Описание** | Идея начинать с SQLite/PostgreSQL. v0 использует файлы (JSONL). |

### D-SUP-5 — START WITH WEB UI

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | D-N9-2 (v0 first) |
| **Описание** | Идея начинать с Web UI. v0 использует CLI. |

### D-SUP-6 — MEMORY AS TRAINING

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | Явное разделение «память ≠ обучение» |
| **Описание** | Смешение оперативной памяти сессии с обучающей выборкой. Память не обучает модель. |

### D-SUP-7 — APPROVE_SCENE → DATASET

| Поле | Значение |
|------|----------|
| **Статус** | SUPERSEDED |
| **Заменено** | Трёхуровневое одобрение (ACCEPT_DRAFT / APPROVE_SCENE / APPROVE_DATASET) |
| **Описание** | Идея, что одобрение сцены автоматически вводит её в датасет. Разделены намеренно. |

### D-SUP-8 — SANDBOX AUTO-PROMOTION

| Поле | Значение |
|------|----------|
| **Статус** | REJECTED |
| **Описание** | Автоматическое превращение состояния Sandbox в канон. Отклонено: любое изменение канона — explicit, human-reviewed. |

---

## 7. Сводка

| Группа | Всего | OWNER_RATIFIED | OWNER_DECISION_PENDING | DEFERRED | BLOCKED | SUPERSEDED | REJECTED |
|--------|-------|----------------|------------------------|----------|---------|------------|----------|
| D-N9 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| D-CES | 10 | 0 | 10 | 0 | 0 | 0 | 0 |
| D-DEF | 3 | 0 | 0 | 3 | 0 | 0 | 0 |
| D-BLK | 2 | 0 | 0 | 0 | 2 | 0 | 0 |
| D-SUP | 8 | 0 | 0 | 0 | 0 | 7 | 1 |

---

*Конец PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md*