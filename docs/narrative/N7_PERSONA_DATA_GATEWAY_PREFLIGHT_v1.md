> **SUPERSEDED.** Настоящий preflight-документ выполнил свою верификационную роль.
> N7 P1 (P1a-S1 + P1b Option A + Nika correction) завершён и закрыт.
> Актуальный канонический статус N7 зафиксирован в документе закрытия:
> `docs/narrative/N7_CANONICAL_STATUS_CLOSEOUT_v1.md` от 2026-07-20.
> Весь контент ниже сохранён без изменений как историческая запись preflight-анализа.

# N7 — PERSONA DATA GATEWAY — ARCHITECTURE PREFLIGHT (P0)

> **MODE: READ-ONLY / DOCUMENTATION ONLY.** Этот документ ничего не реализует и не меняет код.
> Он фиксирует контракт, threat model, иерархию источников, allowlist инструментов, provenance,
> карту переиспользования и роль разработки — до написания единой строки сервиса.
>
> **Назначение.** Следующий трек после N6 (Character Aside): вынести доступ к персонажам в единую
> безопасную domain-службу — **Persona Data Gateway**, — у которой **MCP это только один из адаптеров**.
> Строим не «персонажа внутри MCP», а чистое доменное ядро с несколькими интерфейсами над ним.
>
> **Статус:** P0 CLOSEOUT DRAFT — OWNER DECISIONS RECORDED.
> IMPLEMENTATION NOT AUTHORIZED.
> **Дата:** 2026-07-16 (correction v2)
> **Опора:** `NARRATIVE_DECISIONS_v1.md` §1–§2, `N6_CHARACTER_ASIDE_CONTRACT.md`, `NARRATIVE_HANDOFF_KIMI_WORK.md`.
> **Границы:** Narrative / persona-домен. НЕ Voyage Framework automation (отдельный трек).
>
> **N6 Character Aside** был интегрирован в origin/main:
> `afa7a13cec300b1c5917acf52c4d5300f8724d21`
>
> N6 commits:
> - `8ca63fb` fix(llm): support configurable provider timeouts
> - `695c840` fix(renpy): finalize thread-safe character aside
> - `afa7a13` docs(renpy): document character aside engineering
>
> **N6 INTEGRATION GATE: CLOSED.**

---

## 0. Главный тезис и что уже есть

**Тезис.** Gateway — **фасад над уже проверенной N6-архитектурой** (интегрирована в origin/main), а не
стройка с нуля. Почти все кирпичи существуют и проверены; задача P1 — обернуть их чистым доменным API с
provenance и security, а не переписать.

**Инвентарь (проверено в репо, 2026-07-16):**

| Уже существует | Роль в Gateway |
|---|---|
| `personas/<id>/` (модульные source-файлы) + `personas/<id>/INDEX.json` (manifest с картой `modules`) | Canon Read Plane: persona-модули + **готовый allowlist** |
| `scripts/python/build_prompt_modular.py` | сборка персоны из модулей (переиспользовать, не дублировать) |
| `tools/aside_memory_store.py` (изолированная персистентная память, time-travel guard, append-only sessions) | **Runtime Memory Plane** — уже реализован |
| `tools/aside_context_builder.py` (past-only контекст) | сборка контекста turn'а |
| `tools/llm_provider.py` (mock/local/cloud) | provider-абстракция (вне Gateway, потребитель) |
| `tools/aside_runtime.py` | оркестратор Aside (текущий потребитель) |
| `core/AD_AVAILABILITY_MATRIX.md` | источник AD-политики — см. §6 (owner decision: markdown → generated JSON) |
| `state/STATE_TEMPLATE_v2.json` | **шаблон** state (не живой канон — см. §3) |

**Чего НЕ существует** (в предложении фигурировало как готовое — это отдельные подсистемы, НЕ MVP):
`EventEngine` / `append_event`, LangGraph checkpoints, ChromaDB / embeddings, PolicyEnforcer framework,
`services/` директория, роль `vne_persona_gateway_dev`. Всё это — будущее или намеренно отложенное (§8).

---

## 1. Архитектура (domain core + адаптеры)

```text
                     VNE persona data
                            │
                            ▼
              PERSONA DATA GATEWAY DOMAIN CORE
              единое чистое domain-ядро (Python)
              (не LLM provider, не MCP server по определению)
                            │
       ┌────────────────────┼─────────────────────┐
       │                    │                     │
 Ren'Py Adapter        MCP Adapter          HTTP Adapter
 in-process/local      Cline/VS Code         remote/mobile
 (Aside исп. это)      (authoring)           (позже, P5)
       │                    │                     │
       └────────────────────┼─────────────────────┘
                            │
            ┌───────────────┴────────────────┐
            │                                │
     CANON READ PLANE                RUNTIME MEMORY PLANE
     только чтение                  контролируемая запись
     personas/ core/ schemas/       aside_memory / sessions
     AD matrix / level JSON         event journal (append-only)
     (static source files)          (proposals → approval, §7)
```

MCP и HTTP — **адаптеры** над одним и тем же доменным ядром. Persona Data Gateway сам по себе не является
MCP-сервером и не является LLM-провайдером.

**Три правила разделения, которые нельзя нарушать:**

1. **Domain-ядро не знает про транспорт.** MCP/HTTP/Ren'Py — тонкие адаптеры; вся логика, allowlist,
   provenance и валидация живут в ядре. Один и тот же вызов даёт один результат через любой адаптер.
2. **Ren'Py НЕ ходит через MCP.** Игра вызывает то же domain-API **in-process** (как сейчас Aside).
   JSON-RPC между `aside.rpy` и той же машиной = лишняя задержка, точки отказа и сложность упаковки.
   MCP предназначен для **внешнего** LLM-клиента (Cline/VS Code), не для игрового рантайма.
3. **Два плана, две политики записи:** Canon Read Plane — строго read-only; Runtime Memory Plane —
   контролируемая запись только через proposals (§7). Модель никогда не пишет канон напрямую.

---

## 1A. LLM PROVIDER INDEPENDENCE

Persona Data Gateway является **model-independent** и может использоваться с локальными или облачными
LLM-провайдерами. Поддерживаемые концептуальные примеры:

- локальный Ollama;
- DeepSeek через его online API;
- другой совместимый облачный провайдер;
- внешний LLM-хост, такой как Cline.

Изменение LLM-провайдера **не должно требовать** переписывания persona-манифестов, history-поиска,
AD-политики, provenance или path-security логики.

**Явное разделение:**

| Компонент | Назначение |
|-----------|------------|
| **LLM provider** | генерирует model responses |
| **Persona Data Gateway** | возвращает validated и allowlisted persona data |
| **Adapter** | подключает конкретный клиент или runtime к Gateway |

---

## 1B. REN'PY + LOCAL OR CLOUD LLM

Предполагаемый flow Ren'Py:

```
Ren'Py
 → in-process Persona Data Gateway
 → detached and bounded context
 → llm_provider
 → local Ollama OR cloud API such as DeepSeek
 → response returned to Ren'Py MainThread callback
```

**Ключевые уточнения:**

- Ren'Py **не требует** MCP;
- использование облачного LLM **не требует** HTTP Gateway adapter;
- существующий слой `llm_provider` владеет коммуникацией с model API;
- Persona Gateway **не должен хранить или передавать** DeepSeek API key;
- provider credentials остаются в provider/runtime-конфигурации;
- данный документ **не авторизует** изменения в Aside или llm_provider.

---

## 1C. MCP ADAPTER — AUTHORING AND EXTERNAL LLM HOSTS

Предполагаемый flow:

```
User
 → Cline или другой MCP-совместимый хост
 → online или local LLM
 → модель запрашивает tool call
 → хост вызывает локальный MCP adapter
 → MCP adapter вызывает Persona Data Gateway
 → validated tool result возвращается хосту
 → хост отправляет tool result обратно LLM
 → LLM генерирует финальный ответ
```

**Ключевые уточнения:**

- online-модель DeepSeek **может использовать** локально хранимые VNE-данные через Cline;
- Cline является **медиатором** между DeepSeek API и локальным MCP-процессом;
- online-модель **не открывает напрямую** файлы репозитория;
- MCP adapter **не нуждается** в DeepSeek API key;
- MCP adapter — **transport-only** и не содержит persona business logic;
- MCP tool results, отправленные online-провайдеру, становятся частью запроса к этому провайдеру
  и поэтому **требуют data minimization** (см. §1D).

**Future P2 read-only MCP tools:**

```
list_characters
get_character_manifest
read_module
get_state_snapshot
search_history
check_ad
```

Эти инструменты **не реализуются** в данной задаче (P0).

---

## 1D. CLOUD LLM DATA MINIMIZATION

Всё, что возвращается tool'ом и отправляется DeepSeek или другому облачному провайдеру, может покинуть
локальную машину. Поэтому каждый ответ, предназначенный для online LLM, должен применять:

- **character allowlist** — только разрешённые персонажи;
- **module allowlist** — только модули из манифеста;
- **field minimization** — минимально необходимые поля;
- **response size cap** — ограничение размера ответа;
- **secret redaction** — удаление секретов;
- **past-only filtering** — только прошлые данные;
- **session isolation** — изоляция между сессиями;
- **schema validation** — валидация по схеме;
- **provenance** — отслеживание источника;
- **no arbitrary filesystem paths** — запрет произвольных путей;
- **no repository-wide dumps** — запрет дампов всего репозитория;
- **no API keys** — запрет ключей API;
- **no unrelated character data** — только данные запрошенного персонажа.

Gateway должен возвращать **только минимум данных**, необходимый для текущего turn'а.

---

## 1E. HTTP ADAPTER — REMOTE GATEWAY ACCESS

Два отдельных HTTP-соединения могут существовать параллельно:

1. application/backend → DeepSeek API;
2. application/backend → Persona Data Gateway HTTP API.

Это **не один и тот же сервис**.

| Сервис | Назначение |
|--------|------------|
| **DeepSeek API** | предоставляет model inference |
| **Persona Gateway HTTP adapter** | предоставляет authenticated remote access к persona data |

**Future flow (P5):**

```
web/mobile client
 → backend orchestrator
 → DeepSeek API
 → tool request
 → Persona Gateway HTTPS adapter
 → validated tool result
 → DeepSeek API
 → final response
```

**Почему HTTP остаётся на P5:**

- authentication;
- authorization;
- TLS;
- rate limiting;
- concurrency;
- API versioning;
- audit logging;
- session isolation;
- backup and migration policy;
- response caps;
- remote threat model.

**Важно:** локальный MCP stdio **не должен** просто выставляться в интернет через tunnel.
HTTP adapter — отдельная реализация с полным набором security-слоёв.

HTTP endpoints **не создаются** в данной задаче (P0).

---

## 2. Два разных «канона» — критическая граница

Это ключевое уточнение к исходной диаграмме. Существуют **два независимых источника канона**, и Gateway
работает только с одним из них:

**(A) Static source canon — файлы на диске.** `personas/`, `core/`, `schemas/`, level JSON, AD matrix.
Неизменны во время игры. **Gateway Canon Read Plane читает именно это.**

**(B) Live runtime canon — только в памяти процесса Ren'Py.** `v2_flags`, `v2_completed_scenes`,
`v2_levels`, `v2_relationships`, `progress_index`. Существует лишь во время партии; на диске в общем виде
его нет (есть только сейв конкретного слота). **Gateway НЕ читает и НЕ должен читать это с диска.**

**Следствия:**

- Живой снимок канона (past-only) **инжектится Ren'Py-адаптером** в вызов Gateway; time-travel guard и
  past-only проверяются против переданного `progress_index`, как в N6. Gateway его не выдумывает.
- Инструмент `get_state_snapshot` в MCP/authoring-контексте относится к **aside/authoring runtime memory
  или сохранённой сессии**, а не к живому игровому канону. У внешнего LLM-клиента живой игры нет —
  значит state либо передан явно, либо взят из сохранённой сессии, но **никогда не фабрикуется сервером**.
- Монолиты `personas/*_MODULE_*.json` — **build artifacts** (`NARRATIVE_DECISIONS §2`), НЕ канон. Gateway
  читает модульные source-файлы + `INDEX.json`, а не монофайл.

---

## 3. Canon Read Plane — инструменты (read-only)

Доменное API (транспорт-независимое). MVP — только чтение:

```text
list_characters()                       → id + имя из REGISTRY.json (allowlisted)
get_character_manifest(character)        → INDEX.json: modules map, versions, default_level
read_module(character, module_id)        → один модуль по стабильному ID (см. §5 allowlist)
get_state_snapshot(character, session)   → снимок из сохранённой сессии/aside-памяти (НЕ живой канон, §2)
search_history(character, query, limit)  → поиск по aside/session истории (literal/token, §8)
check_ad(character, level, ad_code)      → доступность AD-кода на уровне (из сгенерированного JSON, §6)
```

`get_loaded_sources` **исключён** из required P1 core API. Tracking загруженных источников принадлежит
более позднему orchestration/session-слою. Каждый индивидуальный read-ответ уже включает provenance.

**Все канонические источники строго read-only.** Gateway не имеет write-доступа к `personas/`, `core/`,
`schemas/`, `scenarios/`, `v2_*`.

---

## 4. Runtime Memory Plane — изменяемое состояние (изолированно)

Опирается на существующий `tools/aside_memory_store.py` (уже: изоляция per save_slot+character,
персистентность, time-travel guard, append-only sessions).

```text
LOCAL_STORAGE/
  sessions/           # append-only журнал turn'ов
  aside_memory/       # суммаризованная память персонажа (не канон)
  runtime_state/      # изменяемое рабочее состояние (не канон)
  event_journal/      # append-only аудит
```

Модель может **читать** это свободно. Прямой произвольной записи в MVP нет — только proposals (§7).

---

## 5. Allowlist и защита от path traversal

**Не принимать сырой `module_path`.** В исходном примере сервер брал `module_path="levels/U3-A.json"` —
это открывает path traversal (`../../secret`). Вместо этого:

- Инструмент принимает **стабильный ID**: `module_id="level.U3-A"` / `"core.IDENTITY"`.
- Сервер разрешает ID → путь через **allowlist из `INDEX.json`** (он уже есть и содержит карту `modules`).
  Всё, чего нет в манифесте, — отвергается. Никакой конкатенации путей из пользовательского ввода.

```json
// resolver, производный от personas/<id>/INDEX.json
{ "core.IDENTITY": "personas/kira/core/IDENTITY.json",
  "level.U3-A":    "personas/kira/levels/U3-A.json" }
```

**Каждый ответ несёт provenance:**

```json
{
  "data": { },
  "source": "personas/kira/levels/U3-A.json",
  "schema": "persona-level-v3",
  "content_hash": "sha256:…",
  "version": "1.0.0",
  "read_only": true
}
```

### 5A. PATH-SECURITY CONTRACT (mandatory layers)

Каждый read-запрос обязан пройти все слои:

1. **character ID** существует в `personas/REGISTRY.json`;
2. **module ID** существует в character `INDEX.json`;
3. **resolved path** остаётся под `personas/<character>/` после `resolve()`;
4. **extension** — в allowlist;
5. **file size** — capped;
6. **parsed data** проходит schema validation;
7. **response** включает provenance;
8. **no raw caller-controlled filesystem path** принимается.

---

## 6. AD-политика: markdown → generated JSON (owner decision)

**Решение владельца:** `core/AD_AVAILABILITY_MATRIX.md` → deterministic generator →
`generated/policies/AD_AVAILABILITY.json`.

- Markdown остаётся **source of truth**;
- сгенерированный JSON — **reproducible derived artifact**;
- Gateway читает сгенерированный JSON;
- generator и reader требуют **golden tests**;
- provenance включает **оба хеша**: source Markdown hash + generated artifact hash;
- `generated/policies/` — новая утверждённая конвенция для derived policy;
- **ни один generated file не создаётся в P0**.

В обоих случаях `check_ad` возвращает `{level, ad, available, reason, source, content_hash}`.

---

## 7. Модель записи: только proposals, не автономная запись

Жёстко: **LLM канон не пишет** (`N6 §6`). Даже для non-canon памяти — не даём модели `update_memory` /
`set_flag` / `update_state`. Вместо этого один безопасный write-tool:

```text
propose_memory_update(target, operation, payload, reason) → proposal (requires_approval)
```

```json
{ "proposal_id": "mem-2026-0017", "target": "aside_memory/kira",
  "operation": "append", "reason": "Игрок сообщил предпочтение", "requires_approval": true }
```

Подтверждает предложение **не модель**, а один из: игровой код · детерминированный policy-слой · человек ·
отдельный session finalizer. Компаньоны (P4): `list_memory_proposals`, `approve_memory_proposal`,
`reject_memory_proposal`. Canon-планы остаются read-only всегда.

### 7A. PHYSICALLY READ-ONLY P1

P1 **не содержит**:

- file writes;
- write-capable handles;
- canonical mutation;
- runtime-memory mutation;
- proposal writes;
- session finalizer;
- event append API;
- MCP adapter;
- HTTP adapter;
- background daemon;
- remote listener.

P1-тесты должны доказывать, что read operations **не модифицируют**:

- source canon;
- runtime-memory files;
- repository state.

Все proposal-инструменты остаются в P4:

```
propose_memory_update
list_memory_proposals
approve_memory_proposal
reject_memory_proposal
```

---

## 8. Non-goals MVP (намеренно НЕ делаем сейчас)

```text
ChromaDB / semantic embeddings   — только после измерения качества простого поиска
LangGraph                        — не нужен доменному ядру
EventEngine / append_event       — отдельная подсистема, не существует, не для MVP
PolicyEnforcer framework         — Voyage-территория, не тянуть в narrative
автономные state transitions     — запрещены (детерминизм)
canonical write-tools            — запрещены инвариантом
remote/cloud deployment          — только после локального MVP (P5)
```

Для небольшого корпуса персонажа на старте достаточно: manifest lookup · JSON field filtering · tag search ·
простой полнотекстовый поиск · append-only session journal. Вектора — позже и по измерению, не по вере.

### 8A. P1 search_history — ограничения

P1 `search_history` должен использовать **только**:

- literal or normalized-token matching;
- deterministic ordering;
- explicit result limit;
- progress/date filtering;
- past-only enforcement.

**Никаких semantic embeddings в P1.**

---

## 9. Threat model (сервер не доверяет модели)

Каждый tool обязан обеспечивать:

```text
allowlist персонажей (REGISTRY)          size-cap ответа
allowlist модулей (INDEX, стабильный ID)  timeout
schema-валидация выдачи                   rate limits (remote)
запрет сырых путей / traversal            provenance (source+schema+hash+read_only)
audit log (event_journal, append-only)     session_id в каждом вызове
authentication (только remote-адаптер)     запрет секретов в ответах
```

**Транспортные оговорки:** локальный MCP stdio **не выставлять в интернет** через tunnel напрямую; для
remote — отдельный authenticated HTTPS/WebSocket адаптер (P5) с auth + rate limit + timeout.

---

## 10. Экономика (корректно)

Исходная фраза «tool results не считаются input tokens» — **неверна**: результаты tool-call попадают в
контекст последующих turn'ов и стоят токенов. Реальная экономия в другом: вместо постоянной передачи
~2000 токенов монолита сервер возвращает **150–400 релевантных токенов** по требованию. Плюс — латентность
сетевых вызовов реальна, поэтому Ren'Py остаётся in-process (§1, правило 2).

---

## 11. Карта переиспользования (P1 = фасад, не переписывание)

```text
PersonaRepository      ← persona module readers + INDEX.json manifest (+ build_prompt_modular для сборки)
StateSnapshotService   ← сохранённые сессии / aside_memory_store (НЕ живой v2_*; §2)
HistoryQueryService    ← aside_memory_store (append-only sessions, поиск)
ADPolicyReader         ← generated/policies/AD_AVAILABILITY.json (§6) + golden tests
ProvenanceService      ← новый тонкий слой: source + schema + content_hash + read_only
```

Провайдер (`llm_provider.py`) и оркестрация Aside (`aside_runtime.py`) — **потребители** Gateway, не его часть.

### 11A. PACKAGE ROOT

Утверждённый P1 package root:

```
services/persona_gateway/
```

Слово `services` означает **application/domain service package**, а не network server или daemon.

Планируемая будущая структура:

```
services/persona_gateway/
  __init__.py
  errors.py
  models.py
  persona_repository.py
  state_snapshot_service.py
  history_query_service.py
  ad_policy_reader.py
  provenance.py

tests/persona_gateway/
```

**Не создавать** эти пути в данной задаче (P0).

### 11B. PERSONA REGISTRY

Будущий explicit allowlist registry:

```
personas/REGISTRY.json
```

Registry сопоставляет утверждённые character ID с их `INDEX.json`-манифестами.

**Слепое сканирование** каждой поддиректории `personas/` запрещено.

Конкретный пример: `personas/visual_prompts/` — не является персонажем и демонстрирует, почему итерация
по директориям небезопасна.

**Не создавать** `REGISTRY.json` сейчас.

---

## 12. Роль разработки (предложение; .voyage/roles.yaml НЕ трогаем в P0)

`.voyage/roles.yaml` **не модифицируется** в ходе P0.

Future task: **D-N7-002 — Gateway development and QA roles.**

Future роли должны трактовать:

- `personas/`
- `core/`
- `schemas/`

как **read-only inputs**.

Предлагаемая структура ролей (реальная правка roles.yaml — отдельной delegated-задачей, не в этом preflight):

```yaml
vne_persona_gateway_dev:
  purpose: "Develops read-only Persona Data Gateway and external adapters."
  allowed_paths: [ services/persona_gateway/, tests/persona_gateway/, docs/persona_gateway/ ]
  approval_required_paths: [ personas/, core/, schemas/ ]
  forbidden_paths: [ scenarios/, novel/, voyage_framework/ ]
# + vne_persona_gateway_qa — read-only security/canon аудит
```

---

## 13. Инварианты (незыблемо)

```text
personas/   READ ONLY        session memory   CONTROLLED WRITE (proposals)
core/       READ ONLY        aside memory     CONTROLLED WRITE (proposals)
schemas/    READ ONLY        event journal    APPEND ONLY
scenarios/  READ ONLY
v2_*        READ ONLY (и не читается с диска Gateway'ем — инжектится Ren'Py, §2)
```

VNE остаётся narrative content core; Voyage Framework не превращается в runtime; автоматическая
перезапись persona без review запрещена.

---

## 14. Фазовый план (owner decisions)

```text
P0  Architecture preflight        ← ЭТОТ ДОКУМЕНТ (docs only, no code).
                                   Owner decisions recorded. Implementation NOT authorized.

P1a Kira-only read-only vertical slice
                                   PersonaRepository / StateSnapshotService / HistoryQueryService /
                                   ADPolicyReader / ProvenanceService — чистый Python, unit+golden tests.
                                   Только Kira. Без MCP. Без HTTP. Без write.
                                   Физически read-only — не модифицирует source canon, runtime-memory,
                                   repository state.

P1b Multi-character manifest inventory and compatibility
                                   Инспектировать все 11 persona INDEX.json-манифестов;
                                   сравнить schemas и versions;
                                   проверить required modules;
                                   обнаружить broken manifest paths;
                                   определить multi-character compatibility.
                                   (Не утверждать, что multi-character compatibility уже доказана.)

P2  MCP adapter (authoring)       Cline → MCP stdio → Gateway; только read-only tools, без write.
                                   Может использоваться с local Ollama или online моделью (DeepSeek API).
                                   MCP adapter — transport-only, не содержит persona business logic.

P3  Ren'Py adapter                Aside использует то же domain-API in-process (НЕ MCP).
                                   LLM provider может оставаться локальным или облачным.

P4  Non-canonical memory proposals propose_/list_/approve_/reject_memory_*.
                                   Только proposals; модель канон не пишет.

P5  Remote API                    HTTPS + auth + per-session authz + concurrency + backups + versioning.
                                   Отдельный HTTP adapter над тем же domain-ядром.
                                   НЕ просто tunnel поверх MCP stdio.
```

---

## 15. Precondition до P1

**N6 INTEGRATION GATE: CLOSED**

Evidence:
- origin/main = `afa7a13cec300b1c5917acf52c4d5300f8724d21`
- N6 commits интегрированы (3 шт.)
- visible diagnostic UI: **NONE** (file-only observability, ACCEPTABLE)
- independent QA: **PASS WITH NONBLOCKING NOTES**

**Оставшиеся gates перед P1:**

1. corrected P0 document reviewed by owner;
2. corrected P0 document selectively committed and pushed through a
   separately authorized task;
3. role/governance task D-N7-002 completed **or** a task-scoped role exception
   explicitly approved;
4. dedicated owner prompt authorizes P1a implementation.

> **P1 IMPLEMENTATION IS NOT AUTHORIZED BY THIS DOCUMENT.**

---

## 16. Credential boundaries

| Компонент | Владеет облачными credentials? |
|-----------|-------------------------------|
| Persona Data Gateway | **НЕТ** — не должен знать cloud LLM credentials |
| MCP adapter | **НЕТ** — не должен получать DeepSeek API key |
| Ren'Py llm_provider | **ДА** — владеет provider credentials |
| Cline или backend orchestrator | **ДА** — владеет cloud provider credentials |
| HTTP adapter | **НЕТ** — использует собственные auth credentials, не LLM provider keys |

Credentials **не должны появляться** в:

- Gateway tool results;
- provenance;
- logs;
- reports;
- persona memory;
- repository files.

---

## 17. Итоговый вердикт preflight

Модернизация через сервер — **нужна и перспективна**, но правильная формулировка:
**создать Persona Data Gateway как единую безопасную domain-службу**; MCP использовать как **read-only
adapter** для Cline/внешних LLM; Ren'Py подключать к той же службе **напрямую, без MCP**; канон оставить
read-only; изменяемую память изолировать и вводить только через proposals + approval. Это **не переписывание
Character Aside**, а следующий слой над уже интегрированной N6-архитектурой.

Gateway является **provider-independent**: поддерживает локальные и облачные LLM (Ollama, DeepSeek API
и другие) без изменения доменной логики. MCP adapter обслуживает authoring-сценарии; Ren'Py adapter
обслуживает runtime. Оба используют одно доменное ядро. HTTP adapter — отдельная future-задача (P5)
с полным security-стеком.

**Следующая задача — НЕ `vne_mcp_server.py` на 300 строк.** Следующая задача — ревью этого
скорректированного preflight владельцем и решение по gates (§15), затем P1a (read-only domain-ядро,
только Kira, с тестами) отдельным delegated-промптом.

**P1 IMPLEMENTATION IS NOT AUTHORIZED BY THIS DOCUMENT.**