# PAC & Character Evolution — Knowledge Capture v1

> **Дата:** 2026-07-22
> **Статус:** ACTIVE — пополняется по мере появления новых идей, возражений и отменённых подходов.
> **Назначение:** Сохранить идеи и обоснования (rationale) без автоматической ратификации всего содержимого. Каждая запись классифицирована по статусу, источнику и связанным решениям.

---

## 1. Формат записи

| Поле | Описание |
|------|----------|
| **Topic** | Краткая тема. |
| **Statement** | Утверждение. |
| **Rationale** | Почему это важно / почему так, а не иначе. |
| **Source category** | `OWNER_RATIFIED` / `EXISTING_REPOSITORY_FACT` / `PROPOSED` / `INFERRED` / `SUPERSEDED`. |
| **Status** | Статус утверждения. |
| **Related decision** | ID решения из Decision Register (если есть). |
| **Related document** | Документ-источник. |
| **Risks** | Риски, если игнорировать. |
| **Next verification** | Когда перепроверить. |

---

## 2. Канонические факты (OWNER_RATIFIED / EXISTING_REPOSITORY_FACT)

### K-001 — Memory is not training

| Поле | Значение |
|------|----------|
| **Topic** | Разделение памяти и обучения. |
| **Statement** | Оперативная память сессии ≠ пакетное дообучение модели. Разговор с персонажем не переобучает модель. |
| **Rationale** | Два процесса с разной стоимостью и частотой: память — каждый turn (~0 стоимости), обучение — пакетно, отдельный этап N8. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-SUP-6 (SUPERSEDED: memory as training) |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §1 |
| **Risks** | Смешение приведёт к деградации модели (обучение на каждом turn) или к потере контекста. |
| **Next verification** | При имплементации PAC v0 memory layer. |

### K-002 — PAC creates corpus while assisting scene writing

| Поле | Значение |
|------|----------|
| **Topic** | Двойное назначение PAC. |
| **Statement** | PAC одновременно помогает писать сцены и накапливает кураторский датасет для N8. |
| **Rationale** | Автор пишет игру, а система незаметно копит примеры — машина производства корпуса, которого сейчас нет. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-1 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §3 |
| **Risks** | Если датасет не curated, N8 обучится на некачественных примерах. |
| **Next verification** | При первых 10 APPROVE_DATASET примерах. |

### K-003 — Local-first provider policy

| Поле | Значение |
|------|----------|
| **Topic** | Порядок выбора провайдера. |
| **Statement** | Local-first; optional cloud comparison — осознанно, per-run; автоматический fallback local→cloud ЗАПРЕЩЁН. |
| **Rationale** | Adult/чувствительный контент не должен утекать в облако без явного решения; дистилляция чужого стиля нежелательна. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-3 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §7 |
| **Risks** | Автоматический fallback — утечка чувствительного контента; неконтролируемая дистилляция. |
| **Next verification** | При имплементации provider layer. |

### K-004 — Raw output retained but not automatically trained on

| Поле | Значение |
|------|----------|
| **Topic** | Хранение сырого вывода модели. |
| **Statement** | `model_output_raw` сохраняется для аудита, сравнения и измерения правок; никогда автоматически не становится обучающей целью. |
| **Rationale** | Сырой вывод нужен, чтобы измерять объём правок и выявлять систематические дефекты модели. Но обучать на сыром выводе — значит впечатывать дефекты базовой модели. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-4 |
| **Related document** | `PAC_TRAINING_DATASET_SCHEMA_v1.md` §6 |
| **Risks** | Если `model_output_raw` попадёт в обучение, N8 унаследует слабый русский, уклонения и ошибки формата. |
| **Next verification** | При первых approved-примерах. |

### K-005 — Scene approval differs from dataset approval

| Поле | Значение |
|------|----------|
| **Topic** | Трёхуровневое одобрение. |
| **Statement** | APPROVE_SCENE ≠ APPROVE_DATASET. Сцена может быть хороша сюжетно, но не годиться как training target, и наоборот. |
| **Rationale** | Разные критерии качества: сцена — драматургия; датасет — стиль, уникальность речи, соответствие формату. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-SUP-7 (SUPERSEDED: APPROVE_SCENE → dataset) |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §8 |
| **Risks** | Смешение приведёт к зашумлению датасета стилистически неподходящими примерами. |
| **Next verification** | При первых 10 APPROVE_DATASET. |

### K-006 — Canon is read-only

| Поле | Значение |
|------|----------|
| **Topic** | Защита канона. |
| **Statement** | `personas/`, `scenarios/`, `knowledge_base/`, `v2_*` — read-only для PAC и Sandbox. Запись — только человеком вручную. |
| **Rationale** | Канон — source of truth. Автоматическая запись разрушает доверие к состоянию персонажей. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-1, D-N9-2, D-SUP-8 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §2.А, §4 |
| **Risks** | Автоматическая мутация канона — необратимая деградация персонажей. |
| **Next verification** | При имплементации PAC v0: подтвердить 0 записей в канон. |

### K-007 — Persona Gateway is reused

| Поле | Значение |
|------|----------|
| **Topic** | Read-side для PAC. |
| **Statement** | PAC читает persona/canon-факты только через существующий N7 Persona Gateway read-side. |
| **Rationale** | Gateway уже построен, проверен (138 тестов), предоставляет provenance и защиту от traversal. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-SUP-2 (SUPERSEDED: read_persona_module(path)) |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §5.1 |
| **Risks** | Дублирование read-side — path traversal риск; расхождение с Gateway. |
| **Next verification** | При имплементации PAC: проверить, что read_persona_module(path) не используется. |

### K-008 — MCP deferred for v0

| Поле | Значение |
|------|----------|
| **Topic** | MCP-адаптер не нужен для v0. |
| **Statement** | PAC v0 не требует MCP-сервера. N7 P2 (MCP adapter) — DEFERRED. |
| **Rationale** | v0 валидирует петлю соавторства; MCP — транспортный слой, не добавляет ценности на этапе валидации. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-2, D-SUP-3 (SUPERSEDED: start with MCP server) |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §6 |
| **Risks** | Преждевременная инфраструктура отвлекает от валидации петли. |
| **Next verification** | После v0 acceptance criteria. |

### K-009 — Files sufficient for v0

| Поле | Значение |
|------|----------|
| **Topic** | Хранение в v0. |
| **Statement** | Для v0 достаточно файлов (JSONL/JSON). SQLite/PostgreSQL — апгрейд после v0, если понадобится масштаб. |
| **Rationale** | v0 — валидация петли на 20–30 примеров. Файлы проще, прозрачнее, не требуют схемы БД. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-2, D-SUP-4 (SUPERSEDED: start with database) |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §6 |
| **Risks** | Масштабирование на тысячи примеров в JSONL может стать неудобным — но это проблема post-v0. |
| **Next verification** | При ≥100 approved-примерах. |

### K-010 — N8 is data-blocked

| Поле | Значение |
|------|----------|
| **Topic** | Блокировка N8. |
| **Statement** | N8 Persona Voice Model заблокирован отсутствием кураторского корпуса. PAC производит этот корпус. |
| **Rationale** | Реальных реплик Киры ~50–110 — недостаточно для fine-tune. Нужны тысячи выверенных примеров. |
| **Source category** | EXISTING_REPOSITORY_FACT |
| **Status** | BLOCKED |
| **Related decision** | D-BLK-1 |
| **Related document** | `N7_CANONICAL_STATUS_CLOSEOUT_v1.md` §3, `NARRATIVE_ROADMAP.md` §10 |
| **Risks** | Попытка обучить на недостаточных данных — переобучение, потеря разнообразия. |
| **Next verification** | При ≥1000 approved-примеров. |

### K-011 — Sandbox is branchable/resettable

| Поле | Значение |
|------|----------|
| **Topic** | Модель песочницы. |
| **Statement** | Character Evolution Sandbox — ветвящаяся, сбрасываемая, неканоническая среда. |
| **Rationale** | Эксперименты с эволюцией персонажа должны быть обратимы и изолированы от канона. |
| **Source category** | PROPOSED |
| **Status** | AWAITING D-CES DECISIONS |
| **Related decision** | D-CES-1 – D-CES-10 |
| **Related document** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §1, §3 |
| **Risks** | Без сбрасываемости эксперименты загрязняют канон. |
| **Next verification** | При разрешении D-CES. |

### K-012 — Experimental evolution is not canon evolution

| Поле | Значение |
|------|----------|
| **Topic** | Non-canon природа Sandbox. |
| **Statement** | Эволюция в Sandbox — эксперимент, не каноническое изменение. Любое изменение канона — explicit, human-reviewed. |
| **Rationale** | Канон защищён от автоматических мутаций. Песочница — лаборатория, не фабрика канона. |
| **Source category** | PROPOSED |
| **Status** | AWAITING D-CES DECISIONS |
| **Related decision** | D-SUP-8 (REJECTED: auto-promotion) |
| **Related document** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3, §5 |
| **Risks** | Автоматическое повышение — необратимая деградация персонажей. |
| **Next verification** | При имплементации Sandbox. |

### K-013 — Provenance differs from quality

| Поле | Значение |
|------|----------|
| **Topic** | Два независимых измерения. |
| **Statement** | `provenance` (кто создал) ≠ `quality_status` (пригодно ли для обучения). Эти измерения независимы. |
| **Rationale** | `human-written` может быть rejected; `model-raw-approved` может быть approved (если прошло все гейты). |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-4 |
| **Related document** | `PAC_TRAINING_DATASET_SCHEMA_v1.md` §7 |
| **Risks** | Смешение приведёт к исключению хороших модельных примеров или включению плохих human-written. |
| **Next verification** | При первых approved-примерах. |

### K-014 — content_hash comes from Gateway provenance

| Поле | Значение |
|------|----------|
| **Topic** | Источник хешей модулей. |
| **Statement** | `canon_snapshot.modules[].content_hash` берётся из `ModuleResult` provenance Gateway, не вычисляется вручную. |
| **Rationale** | Gateway уже вычисляет хеши при чтении модуля. Дублирование вычислений — риск расхождения. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-4 |
| **Related document** | `PAC_TRAINING_DATASET_SCHEMA_v1.md` §3.3 |
| **Risks** | Ручное вычисление хешей — риск несовпадения с Gateway; ненадёжная provenance. |
| **Next verification** | При имплементации PAC canon snapshot. |

### K-015 — source_commit is session-level evidence

| Поле | Значение |
|------|----------|
| **Topic** | Отличие source_commit от content_hash. |
| **Statement** | `source_commit` фиксируется один раз в начале авторской сессии (`git rev-parse HEAD`). `content_hash` — покомпонентный хеш модуля. |
| **Rationale** | `source_commit` — контекст всей сессии; `content_hash` — точный снапшот каждого потреблённого модуля. Вместе обеспечивают полную воспроизводимость. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-4 |
| **Related document** | `PAC_TRAINING_DATASET_SCHEMA_v1.md` §3.4 |
| **Risks** | Без source_commit невозможно определить, из какой версии репозитория был пример. |
| **Next verification** | При имплементации PAC authoring session. |

### K-016 — Rejected/quarantined v0 data stays outside main dataset

| Поле | Значение |
|------|----------|
| **Topic** | v0-упрощение датасета. |
| **Statement** | В v0 `training_dataset.jsonl` содержит только примеры с `APPROVE_DATASET`. Отклонённые и quarantined кандидаты не хранятся в main-файле. |
| **Rationale** | Упрощает v0; sidecar-лог для аудита — DEFERRED. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-4 |
| **Related document** | `PAC_TRAINING_DATASET_SCHEMA_v1.md` §1 |
| **Risks** | Потеря rejected-примеров для анализа — но это проблема post-v0. |
| **Next verification** | При ≥50 approved-примерах. |

### K-017 — Domain logic and CLI remain separated

| Поле | Значение |
|------|----------|
| **Topic** | Разделение логики и интерфейса. |
| **Statement** | `services/persona_authoring/` — domain/application logic; `tools/pac_cli.py` — thin CLI adapter. Домен не знает про транспорт/интерфейс. |
| **Rationale** | Тот же принцип, что в Persona Gateway: ядро тестируемо независимо от CLI/Web/MCP. |
| **Source category** | OWNER_RATIFIED |
| **Status** | ACTIVE |
| **Related decision** | D-N9-5 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §11 |
| **Risks** | Смешение домена и интерфейса затруднит тестирование и перенос на другие транспорты. |
| **Next verification** | При имплементации PAC v0. |

---

## 3. SUPERSEDED IDEAS (Заменённые идеи)

### S-001 — Old PAC v0 prompt placing implementation in tools/pac/

| Поле | Значение |
|------|----------|
| **Topic** | Старое размещение кода PAC. |
| **Statement** | Первый delegated-черновик предлагал `tools/pac/` как место для кода PAC. |
| **Status** | SUPERSEDED by D-N9-5 |
| **Why superseded** | `services/persona_authoring/` + `tools/pac_cli.py` + `local_runs/pac/` — три разделённые локации, как в Gateway. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §11 |

### S-002 — Unsafe read_persona_module(path)

| Поле | Значение |
|------|----------|
| **Topic** | Прямое чтение файла персонажа. |
| **Statement** | Ранний концепт предполагал функцию `read_persona_module(path)` для чтения модулей. |
| **Status** | SUPERSEDED by N7 Persona Gateway |
| **Why superseded** | Path traversal risk; Gateway уже предоставляет `read_module(id, module_id)` с allowlist и provenance. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §5.1 |

### S-003 — Starting with a new MCP server

| Поле | Значение |
|------|----------|
| **Topic** | MCP-сервер как первый шаг PAC. |
| **Statement** | Идея начинать PAC с реализации MCP-сервера для Cline. |
| **Status** | SUPERSEDED by D-N9-2 |
| **Why superseded** | v0 валидирует петлю без инфраструктуры; MCP — DEFERRED (N7 P2). |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §6 |

### S-004 — Starting with SQLite/PostgreSQL

| Поле | Значение |
|------|----------|
| **Topic** | База данных для v0. |
| **Statement** | Идея начинать PAC с реляционной БД. |
| **Status** | SUPERSEDED by D-N9-2 |
| **Why superseded** | Для v0 и 20–30 примеров файлы достаточны. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §2.Б, §6 |

### S-005 — Starting with Web UI

| Поле | Значение |
|------|----------|
| **Topic** | Web-интерфейс для v0. |
| **Statement** | Идея начинать PAC с Web UI. |
| **Status** | SUPERSEDED by D-N9-2 |
| **Why superseded** | v0 использует CLI; Web UI — DEFERRED. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §6 |

### S-006 — Treating memory as training

| Поле | Значение |
|------|----------|
| **Topic** | Смешение памяти и обучения. |
| **Statement** | Идея, что наполнение памяти сессии эквивалентно обучению модели. |
| **Status** | SUPERSEDED by K-001 |
| **Why superseded** | Память и обучение — разные процессы с разной стоимостью и частотой. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §1 |

### S-007 — APPROVE_SCENE automatically entering dataset

| Поле | Значение |
|------|----------|
| **Topic** | Автоматическое попадание в датасет. |
| **Statement** | Идея, что одобрение сцены автоматически добавляет её в тренировочный датасет. |
| **Status** | SUPERSEDED by трёхуровневым одобрением |
| **Why superseded** | APPROVE_SCENE и APPROVE_DATASET разделены намеренно — разные критерии качества. |
| **Date superseded** | 2026-07-22 |
| **Related document** | `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §8 |

### S-008 — Sandbox automatically promoting evolution into canon

| Поле | Значение |
|------|----------|
| **Topic** | Автоматическое повышение Sandbox → канон. |
| **Statement** | Идея, что успешный эксперимент в Sandbox автоматически становится каноном. |
| **Status** | REJECTED |
| **Why rejected** | Любое изменение канона должно быть explicit, human-reviewed. |
| **Date rejected** | 2026-07-22 |
| **Related document** | `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` §3, §5 |

---

## 4. Открытые вопросы (OPEN)

### Q-001 — Расширенные edit-метрики

| Поле | Значение |
|------|----------|
| **Topic** | Метрики редактирования beyond was_edited. |
| **Question** | Какие метрики нужны для измерения качества правок: diff ratio, edit distance, время редактирования? |
| **Status** | DEFERRED (post-v0) |

### Q-002 — Sidecar audit log

| Поле | Значение |
|------|----------|
| **Topic** | Хранение rejected/quarantined примеров. |
| **Question** | Нужен ли отдельный sidecar-лог для аудита отклонённых примеров, или достаточно того, что они не попадают в main-датасет? |
| **Status** | DEFERRED (post-v0) |

---

*Конец PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md*