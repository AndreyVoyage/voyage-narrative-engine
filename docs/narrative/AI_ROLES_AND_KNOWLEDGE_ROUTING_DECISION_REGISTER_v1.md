# AI ROLES & KNOWLEDGE ROUTING — DECISION REGISTER (v1)

> **Статус:** PROPOSED / DRAFT — **IMPLEMENTATION NOT AUTHORIZED.**
> Этот документ содержит **Persona Context Routing Decisions** (D-RKR-16…D-RKR-35)
> как расширение к `AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md` (D-RKR-1…D-RKR-15).
> Вместе они образуют полный D-RKR registry: role routing (§1–§7 концепта) + persona
> context routing (этот документ).
>
> **Дата:** 2026-08-03
> **Опора:** `NARRATIVE_DECISIONS_v1.md`, `AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md`,
> `N7_CANONICAL_STATUS_CLOSEOUT_v1.md`, audit report `PERSONA_CONTEXT_ROUTING_READONLY_AUDIT_2026-08-03`.
> **Audit evidence:** LOCAL_EXTERNAL_EVIDENCE — `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\PERSONA_CONTEXT_ROUTING_READONLY_AUDIT_2026-08-03.{md,json}`
> **Audit HEAD:** `afa64d3af14ad78366dc34cad68af3fb91f2423c` (origin/main)
> **Audit verdict:** PREPARE_MINIMAL_ROUTER_DECISION_REGISTER
> **Audit classification:** LEVEL_ONLY
>
> **Инвариант:** код не авторизован ни одним решением; все решения — `OWNER_DECISION_REQUIRED` с `owner_choice = UNSET`.
> **Нумерация:** продолжает D-RKR-1…D-RKR-15 из концепта; Persona Context Routing = D-RKR-16…D-RKR-35.

---

## OWNER REVIEW SUMMARY

| Decision | Owner choice required | Recommended option | Blocking |
|---|:---:|---|:---:|
| D-RKR-16 — ROUTER-01 Responsibility Boundary | YES | C — separate stateless router over Gateway | **YES** |
| D-RKR-17 — ROUTER-02 Input Contract | YES | 11-field contract (§3) | **YES** |
| D-RKR-18 — ROUTER-03 Scene Type Taxonomy | YES | 6 closed enum types (§4) | NO |
| D-RKR-19 — ROUTER-04 Classification Authority | YES | D — explicit + deterministic fallback, no LLM | **YES** |
| D-RKR-20 — ROUTER-05 Module Policy Format | YES | B — versioned JSON policy file | **YES** |
| D-RKR-21 — ROUTER-06 Required/Optional/Forbidden | YES | fail-closed; denylist overrides REQUIRED (§7) | **YES** |
| D-RKR-22 — ROUTER-07 Partner and Relationship Routing | YES | single partner_id; unknown partner → fail-closed (§8) | NO |
| D-RKR-23 — ROUTER-08 Level Routing | YES | Level=None guard preserved; after-peak transition module (§9) | NO |
| D-RKR-24 — ROUTER-09 Intimacy Module Access | YES | sexology/physiology/sexual_scripts + consent/safety for U4+ intimacy (§10) | NO |
| D-RKR-25 — ROUTER-10 Conflict Module Access | YES | psychology/defense/attachment/boundaries/conflict (§11) | NO |
| D-RKR-26 — ROUTER-11 Context Budget | YES | char+tokens; REQUIRED never truncated; hard cap with manifest error (§12) | **YES** |
| D-RKR-27 — ROUTER-12 Ordering and Deduplication | YES | stable 9-phase order; dedup by module_id (§13) | NO |
| D-RKR-28 — ROUTER-13 Context Manifest | YES | 15-field manifest per routing decision (§14) | **YES** |
| D-RKR-29 — ROUTER-14 Failure Policy | YES | fail-closed for all 10 conditions; no full-persona fallback (§15) | **YES** |
| D-RKR-30 — ROUTER-15 Test and Acceptance Gates | YES | 10 minimum probes; deterministic replay; no LLM in tests (§16) | NO |
| D-RKR-31 — ROUTER-16 Code Location | YES | C — services/persona_context_routing/ (§17) | **YES** |
| D-RKR-32 — ROUTER-17 PAC Integration Boundary | YES | PacRequest fields; old projection kept until parity (§18) | NO |
| D-RKR-33 — ROUTER-18 Aside Boundary | YES | same router; task_type=aside; reads memory via Aside not alone (§19) | NO |
| D-RKR-34 — ROUTER-19 Security and Privacy | YES | registry-only IDs; no arbitrary paths; redaction; no secrets in manifest (§20) | NO |
| D-RKR-35 — ROUTER-20 Authorization Gate | YES | ALL blocking decisions must be OWNER_RATIFIED before Slice 1 (§21) | **YES** |

**Блокирующих решений:** 10 из 20 (см. колонку Blocking = YES).

---

## 1. PURPOSE AND SCOPE

Этот Decision Register определяет минимальный, проверяемый и объяснимый Persona
Context Router — stateless детерминированный механизм над существующим read-only
Persona Gateway (N7 P1).

**Цель router:**

```
Scene/Task Request
  → deterministic classification inputs
  → module-selection policy
  → Persona Gateway reads (read-only)
  → context budget/order
  → context manifest
  → PAC/provider payload
```

**Этот register НЕ проектирует:**
- multi-agent orchestration целиком
- Character Evolution Sandbox
- fine-tuning / embeddings / vector database
- LLM-based router
- autonomous agents
- новый Persona Gateway или persona schema
- Ren'Py runtime routing
- каноническую запись в personas

**Relation to D-RKR-1…D-RKR-15:**

D-RKR-1…D-RKR-15 (в `AI_ROLES_AND_KNOWLEDGE_ROUTING_CONCEPT_v1.md`) отвечают за
routing знаний **per-role** (психолог vs. лингвист vs. аудитор). D-RKR-16…D-RKR-35
(this register) отвечают за routing **per-scene/task для одного персонажа** (PAC, Aside).

Это разные слои routing:
- **Role-level routing** = какие knowledge sources нужны конкретной роли (D-RKR-1…15)
- **Persona-context routing** = какие persona modules нужны для конкретной сцены/задачи (D-RKR-16…35)

Оба слоя — над Gateway; Gateway остаётся read-only и не знает ни о ролях, ни о сценах.

---

## 2. CURRENT STATE (IMPLEMENTED vs PROVEN LIMITATIONS vs NOT AUTHORIZED)

### 2.1 IMPLEMENTED

- Modular personas with INDEX/registry allowlist
- Read-only Persona Gateway (N7 P1a+P1b, 138 tests)
- PAC Gateway adapter (`services/persona_authoring/gateway_adapter.py`)
- Level-aware static projection (character_id + level → modules)
- PAC provider pipeline
- FMDR validation

### 2.2 PROVEN LIMITATIONS (из audit)

- **LEVEL_ONLY classification:** routing использует только `character_id` + `level`
- **Scene-awareness absent (GAP-01):** situation, scene type, themes не влияют на выбор модулей
- **Intimacy categories blocked at all levels (GAP-02, CRITICAL):** 5 prefix категорий
  (`visual/`, `physiology/`, `sexology/`, `sexual_scripts/`, `memory/`) исключаются
  статическими константами независимо от сцены
- **Partner routing absent (GAP-03):** partner_id не участвует в module selection
- **Context budget absent (GAP-04):** нет механизма контроля размера контекста
- **No complete runtime context manifest:** манифест есть только для full-persona
  тестовой сборки, не для каждого routing-решения
- **Probe A и Probe B при одинаковом level получили идентичные module sets** —
  доказывает отсутствие scene-awareness
- **U5-A не получает sexology, physiology или sexual scripts** — критический
  дефект для интимных сцен

### 2.3 NOT AUTHORIZED

- Persona Context Router implementation
- RKR code
- LLM classifier
- Vector retrieval / embeddings / fine-tuning
- U5/U6 dataset production
- Automatic canon mutation

---

## 3. D-RKR-16 — ROUTER-01: RESPONSIBILITY BOUNDARY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-16 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Где находится selection policy — какие persona modules включать для данной сцены/задачи? |
| **Audit evidence** | Current routing lives inside `gateway_adapter.py` in PAC trial worktree; hard-coded `character_id` + `level` with static exclusion list. No separation between Gateway reads and policy decisions. |
| **Варианты** | A. Внутри Persona Gateway (Gateway знает о сценах) |
|  | B. Внутри PAC gateway adapter (PAC владеет routing) |
|  | C. Отдельный stateless service над Gateway (router — тонкий слой, Gateway — чистый read-only библиотекарь) |
| **Рекомендация** | **C — отдельный тонкий stateless router над существующим read-only Gateway.** |
| **Trade-offs** | A нарушает принцип Gateway как безопасного библиотекаря (Gateway получает знание о сценах / интимности). B завязывает routing на одного consumer (PAC) и усложняет переиспользование для Aside. C добавляет один новый домен, но сохраняет чистоту Gateway и позволяет PAC + Aside быть независимыми consumers одного router. |
| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 4. D-RKR-17 — ROUTER-02: INPUT CONTRACT

| Поле | Значение |
|---|---|
| **ID** | D-RKR-17 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие поля обязательны/optional/enum для минимального router input? |
| **Audit evidence** | Current input: `character_id` + `level`. `situation_text` передаётся как prompt text, но не влияет на routing. Ни partner, ни scene_type не учитываются. |
| **Варианты** | Определены ниже как рекомендуемый контракт |
| **Рекомендация** | Минимальный контракт из 11 полей (6 обязательных, 5 optional): |

| # | Поле | Обязательное | Тип | Поведение при отсутствии |
|---|---|---|---|---|
| 1 | `character_id` | **Yes** | string (registry key) | Error: unknown character |
| 2 | `task_type` | **Yes** | enum: `pac_authoring`, `aside_chat`, `scene_preview` | Error: unknown task_type |
| 3 | `level` | **Yes** (для pac_authoring) | string или null | null → явная ошибка для pac_authoring; optional для aside_chat |
| 4 | `scene_type` | No (default: `ordinary`) | closed enum (§5) | Default = `ordinary` |
| 5 | `partner_id` | No | string или null | null → relationship modules не включаются |
| 6 | `relationship_id` | No | string или null | null → общий relationship matrix |
| 7 | `themes` | No | list of enum strings | [] → no theme-specific modules |
| 8 | `pov` | No | string или null | null → no POV-specific module routing |
| 9 | `context_budget` | No | object `{max_chars, max_tokens}` | default 80K chars / 20K tokens |
| 10 | `content_mode` | No | enum: `safe`, `standard`, `explicit` | default = `standard` |
| 11 | `situation` | No | string или null | null → no situation-aware module boost |

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 5. D-RKR-18 — ROUTER-03: SCENE TYPE TAXONOMY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-18 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие минимальные типы сцен v0? Закрытый enum или расширяемые tags? |
| **Audit evidence** | Scene type отсутствует в routing вообще. Все probe-запросы дали одинаковые module sets при одинаковом level. |
| **Варианты** | A. 6 закрытых enum значений (рекомендация) |
|  | B. Расширяемые free-form tags |
|  | C. Смешанная: enum base + optional tags |
| **Рекомендация** | **A — закрытый enum из 6 типов для v0:** |

| Enum value | Описание | Пример |
|---|---|---|
| `ordinary` | Обычная беседа, повседневность | U2-A café glances |
| `conflict` | Конфликт, напряжение, спор | U4-A hidden problem |
| `intimacy` | Близость, интимная сцена | U5-A+ intimate scene |
| `recovery` | Восстановление после пика/конфликта | U5-B after-peak |
| `visual_description` | Описание внешности/окружения | Visual prompt generation |
| `authoring_audit` | Аудит/проверка канона | Role-based audit |

**Правила:**
- Комбинация типов через `themes` field, не через множественный scene_type
- `scene_type` = primary classification (ровно одно значение)
- Extending enum → versioned policy upgrade

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 6. D-RKR-19 — ROUTER-04: CLASSIFICATION AUTHORITY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-19 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Как определяется scene_type для routing? |
| **Audit evidence** | Classification отсутствует полностью; routing не использует scene_type. |
| **Варианты** | A. Только явно задаётся вызывающей стороной |
|  | B. Детерминированные правила по structured fields |
|  | C. LLM classifier |
|  | D. Комбинация: explicit field → deterministic fallback |
| **Рекомендация** | **D — explicit scene_type имеет приоритет; fallback — ограниченные детерминированные правила; неопределённость → fail-closed или ordinary-safe mode. LLM classifier НЕ авторизован.** |

**Deterministic fallback rules (примеры, для owner review):**
- `level ∈ {U5-A, U5-B, U6-A, U6-B}` ∧ no explicit type → `intimacy` (только если content_mode = standard/explicit)
- `level ∈ {U4-A, U4-B}` ∧ no explicit type → `conflict`
- `themes` содержит `"конфликт"` → `conflict`
- `themes` содержит `"близость"` → `intimacy`
- иначе → `ordinary`

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 7. D-RKR-20 — ROUTER-05: MODULE POLICY FORMAT

| Поле | Значение |
|---|---|
| **ID** | D-RKR-20 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Где хранится mapping: scene_type / task_type / level / relationship → required / optional / forbidden module categories? |
| **Audit evidence** | Текущий mapping — hard-coded Python constants в `gateway_adapter.py`: static `EXCLUDED_PREFIXES` + `_build_module_list()` с `character_id` + `level`. |
| **Варианты** | A. Hard-coded Python (текущее состояние) |
|  | B. Versioned YAML/JSON policy file (рекомендация) |
|  | C. Persona-specific files (per-character INDEX расширение) |
|  | D. Гибрид: policy file + persona overrides |
| **Рекомендация** | **B — versioned JSON policy file.** |

**Сравнение:**

| Критерий | A (hard-coded) | B (JSON policy) | C (per-persona) | D (hybrid) |
|---|---|---|---|---|
| Auditability | Низкая | Высокая | Средняя | Средняя |
| Versioning | Git-only | Schema + version field | Per-persona | Complex |
| Testability | Требует импорта кода | Pure data-driven | Per-persona tests | Mixed |
| Risk of drift | Высокий | Низкий | Per-persona drift | Medium |
| Owner editability | Код | JSON (проще) | JSON per persona | Mixed |

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 8. D-RKR-21 — ROUTER-06: REQUIRED / OPTIONAL / FORBIDDEN

| Поле | Значение |
|---|---|
| **ID** | D-RKR-21 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Поведение при REQUIRED отсутствует, OPTIONAL отсутствует, FORBIDDEN запрошен; может ли static denylist переопределять REQUIRED? |
| **Audit evidence** | Текущее поведение: 5 префиксов (`visual/`, `physiology/`, `sexology/`, `sexual_scripts/`, `memory/`) статически исключаются всегда — даже для U5-A где они необходимы. Это и есть главный дефект GAP-02. |
| **Варианты** | Определены ниже как правила |
| **Рекомендация** | **Три статуса модулей с чёткими правилами:** |

### REQUIRED
- **При отсутствии:** fail-closed → routing error с указанием missing module_id
- **Нельзя** обрезать при budget overflow (см. D-RKR-26)
- **Примеры:** `core/IDENTITY`, `safety/PROTOCOL`, `levels/<level>.json`, `meta/COHERENCE_VETO`

### OPTIONAL
- **При отсутствии:** skip gracefully, логгировать в manifest
- Может быть обрезано при budget overflow по ordering priority
- **Примеры:** `autonomous/ACTIVITIES`, `environment/SENSORY_PROCESSING`

### FORBIDDEN
- Static denylist **НЕ переопределяет REQUIRED** — policy должна быть согласована
- Если module в FORBIDDEN списке policy, он исключается даже если категория implied by scene_type
- FORBIDDEN ≠ «не нужен сейчас» — это жёсткий запрет для данного task_type/content_mode
- **Примеры:** `visual/` modules FORBIDDEN для `pac_authoring` text-only задач;
  `sexology/` может быть FORBIDDEN для `content_mode=safe`

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 9. D-RKR-22 — ROUTER-07: PARTNER AND RELATIONSHIP ROUTING

| Поле | Значение |
|---|---|
| **ID** | D-RKR-22 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Как выбираются relationship modules при наличии partner_id? Что при неизвестном партнёре? |
| **Audit evidence** | GAP-03 — partner routing полностью отсутствует. `relationships/MATRIX.json` всегда включается, но partner-specific данные не резолвятся. |
| **Варианты** | A. Только общий `relationships/MATRIX.json` (без partner-specific) — текущее состояние |
|  | B. `partner_id` → partner-specific relationship module + общий MATRIX |
|  | C. Multi-partner (сложнее, для будущих версий) |
| **Рекомендация** | **B для v0. Один partner_id; неизвестный partner → fail-closed (routing error).** |

**Правила v0:**
- `partner_id = null` → только общий `relationships/MATRIX.json`
- `partner_id = "sergey"` → `relationships/MATRIX.json` + `relationships/partner_sergey.json` (если существует)
- Неизвестный `partner_id` (нет в registry) → routing error: `UNKNOWN_PARTNER`
- Никакой silent fallback на общий MATRIX без partner-specific
- Multi-partner сцены: v0 ограничивается одним partner_id; multiple participants → будущая версия

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 10. D-RKR-23 — ROUTER-08: LEVEL ROUTING

| Поле | Значение |
|---|---|
| **ID** | D-RKR-23 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Как выбираются level-specific модули? Что с соседними уровнями и after-peak transition? |
| **Audit evidence** | Текущее поведение: ровно один level module включается (`levels/<level>.json`). Соседние уровни и transition не роутятся. Level=None guard реализован и работает. |
| **Варианты** | A. Только текущий level (статус-кво) |
|  | B. Текущий level + transition module для after-peak (рекомендация) |
|  | C. Текущий + соседние уровни (U4-A → также U3-B, U4-B) |
| **Рекомендация** | **B — текущий level + transition/after-peak module.** |

**Правила:**
- `level = None` ∧ `task_type = pac_authoring` → явная ошибка (существующий guard сохраняется)
- `level = None` ∧ `task_type = aside_chat` → допустимо; level module не включается
- Всегда включается `levels/<level>.json`
- Для after-peak сцен (`scene_type = recovery`): включается `levels/<level>.json` + `levels/transition_after_peak.json` (если существует)
- Соседние уровни не включаются (v0 минимален)
- `level` вне enum → routing error: `UNKNOWN_LEVEL`

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 11. D-RKR-24 — ROUTER-09: INTIMACY MODULE ACCESS

| Поле | Значение |
|---|---|
| **ID** | D-RKR-24 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие категории обязательны/опциональны для интимных сцен? Как разрешить sexology/physiology без утечки в ordinary сцены? |
| **Audit evidence** | GAP-02 CRITICAL. 5 префиксов исключаются статически: `visual/`, `physiology/`, `sexology/`, `sexual_scripts/`, `memory/`. U5-A Probe D получил те же 30 модулей что U2-A Probe A. Интимные сцены не имеют доступа к sexology, physiology, sexual scripts, memory. |
| **Варианты** | Рекомендация ниже — на основе реальных зарегистрированных категорий Kira |
| **Рекомендация** | **Условное включение intimacy-specific категорий только при `scene_type=intimacy` или `scene_type=recovery` И `level ≥ U4-A` И `content_mode ∈ {standard, explicit}`.** |

**Intimacy-specific категории (реальные зарегистрированные в Kira INDEX):**

| Категория | Статус для intimacy | Модули |
|---|---|---|
| `sexology/` | **REQUIRED** (U4-A+) | `DYSPHORIA_AND_SHAME.json`, `EROTIC_SCRIPTS.json`, `FANTASY_VS_REALITY.json`, `RESPONSE_CYCLE.json` |
| `physiology/` | **REQUIRED** (U4-A+) | `AROUSAL_SIGNATURES.json`, `CORTICAL_ACTIVATION.json`, `EROGENOUS_MAP.json`, `MICROEXPRESSIONS.json` |
| `sexual_scripts/` | **OPTIONAL** (U5-A+) | `EROTIC_SCRIPTS.json` |
| `memory/` | **REQUIRED** (U4-A+) | `ATTRACTION.json`, `TRUST.json`, `emotional_anchors.json` |
| `safety/PROTOCOL.json` | **REQUIRED** (всегда) | Контент для безопасности и согласия |
| `psychology/AROUSAL.json` | **REQUIRED** (U4-A+) | Уже включается в базовый набор |
| `evolution/AROUSAL_AS_MOTIVATION.json` | **REQUIRED** (U4-A+) | Уже включается в базовый набор |

**Guard:**
- `scene_type=ordinary` → intimacy категории **FORBIDDEN** (не протекают)
- `scene_type=intimacy` ∧ `level < U4-A` → routing error: `LEVEL_TOO_LOW_FOR_INTIMACY`
- `content_mode=safe` → intimacy категории **FORBIDDEN** независимо от scene_type

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 12. D-RKR-25 — ROUTER-10: CONFLICT MODULE ACCESS

| Поле | Значение |
|---|---|
| **ID** | D-RKR-25 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие категории обязательны для conflict scenes? |
| **Audit evidence** | Probe C (U4-A conflict) получил идентичный набор модулей с Probe A (U2-A ordinary). Conflict-specific категории не выделяются. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Дополнительные REQUIRED категории для `scene_type=conflict`:** |

| Категория | Статус для conflict | Обоснование |
|---|---|---|
| `psychology/DEFENSE_MECHANISMS.json` | **REQUIRED** (уже в базе) | Защитные механизмы критичны для конфликта |
| `psychology/COGNITIVE_DISTORTIONS.json` | **REQUIRED** (уже в базе) | Когнитивные искажения в конфликте |
| `psychology/TACTICS.json` | **REQUIRED** (уже в базе) | Манипулятивные тактики |
| `attachment/BEHAVIORAL_SYSTEMS.json` | **REQUIRED** (уже в базе) | Поведение привязанности в стрессе |
| `trauma_ptsd/THREE_LEVELS.json` | **OPTIONAL** → **REQUIRED** | Травма-триггеры при конфликте |
| `relationships/MATRIX.json` | **REQUIRED** (уже в базе) | Динамика отношений в конфликте |

В отличие от intimacy, conflict не требует новых excluded категорий — большинство
conflict-specific модулей уже входят в базовый набор. Основное изменение:
повышение статуса `trauma_ptsd/` с OPTIONAL до REQUIRED.

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 13. D-RKR-26 — ROUTER-11: CONTEXT BUDGET

| Поле | Значение |
|---|---|
| **ID** | D-RKR-26 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Единица бюджета, hard cap, поведение при превышении, что нельзя обрезать? |
| **Audit evidence** | GAP-04. Текущий контекст не имеет budget control — Probe B (full persona) = 68K chars. PAC-контекст собирается без ограничений. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Двойная единица (characters + tokens), hard cap, REQUIRED-модули никогда не обрезаются молча.** |

### Budget spec

| Параметр | Значение |
|---|---|
| Единица | Characters (для file size) + tokens (для LLM context window) |
| Default hard cap | 50K chars / 12K tokens per persona |
| Reserved space | 2K chars для situation/instruction/output-формата |
| Truncation strategy | Drop OPTIONAL modules by reverse priority order |
| REQUIRED modules | **Никогда не обрезаются молча** |
| Превышение hard cap после удаления всех OPTIONAL | → явный routing error: `BUDGET_OVERFLOW` |
| Manifest включает | `total_chars`, `total_tokens`, `truncated_modules[]` |

### Ordering for truncation (first to drop)
1. `autonomous/` (OPTIONAL)
2. `environment/` (OPTIONAL)
3. `dynamics/` (OPTIONAL)
4. `evolution/` (OPTIONAL)
5. `speech/` (OPTIONAL — если не REQUIRED для сцены)

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 14. D-RKR-27 — ROUTER-12: ORDERING AND DEDUPLICATION

| Поле | Значение |
|---|---|
| **ID** | D-RKR-27 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Стабильный порядок модулей, дедупликация, versioning policy? |
| **Audit evidence** | Текущий порядок не определён явно; модули собираются через `_build_module_list()` без документированного ordering contract. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Стабильный 9-phase порядок; дедупликация по module_id.** |

### Stable order (draft for owner review)

| Phase | Категории | Rationale |
|---|---|---|
| 1 | `core/` | Identity first — фундамент |
| 2 | `safety/` | Safety/boundaries до всего остального |
| 3 | `psychology/` | Психологический профиль |
| 4 | `relationships/` + `attachment/` | Контекст отношений |
| 5 | Scene-specific domain (`sexology/`, `physiology/`, `trauma_ptsd/`) | Сценарный домен |
| 6 | `levels/` | Текущий уровень + transition |
| 7 | `speech/` | Речевая матрица |
| 8 | `meta/` | Coherence/meta-rules |
| 9 | `autonomous/`, `environment/`, `dynamics/`, `evolution/`, `memory/` | Опциональный контекст |

### Deduplication
- **По `module_id`:** если один module_id появляется из двух источников — включить один раз
- **По path/hash:** не делать content-based dedup (дорого); доверять module_id
- **Стабильность:** одинаковый router input → одинаковый порядок (детерминизм)
- **Versioning:** политика версионируется вместе с policy-файлом (semver)

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 15. D-RKR-28 — ROUTER-13: CONTEXT MANIFEST

| Поле | Значение |
|---|---|
| **ID** | D-RKR-28 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Обязательные поля manifest; сохраняется ли с PAC run; доступен ли пользователю; воспроизводимость? |
| **Audit evidence** | Полноценный runtime context manifest отсутствует. Существующий manifest только для тестовой full-persona сборки. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Обязательный 15-field manifest для каждого routing-решения.** |

### Manifest fields

| # | Поле | Тип | Описание |
|---|---|---|---|
| 1 | `router_version` | string | Semver версия router + policy |
| 2 | `character_id` | string | Как в input |
| 3 | `task_type` | string | Как в input |
| 4 | `scene_type` | string | После classification |
| 5 | `partner_id` | string или null | Как в input |
| 6 | `level` | string или null | Как в input |
| 7 | `included_modules` | list of {module_id, path, hash, status} | Все включённые модули |
| 8 | `excluded_modules` | list of {module_id, reason} | Исключённые с причиной |
| 9 | `truncated_modules` | list of {module_id, reason} | Обрезанные по budget |
| 10 | `total_chars` | int | Суммарный размер в символах |
| 11 | `total_tokens` | int | Оценка токенов |
| 12 | `policy_version` | string | Версия policy-файла |
| 13 | `warnings` | list of string | Предупреждения |
| 14 | `errors` | list of string | Ошибки (если fail-closed — manifest может быть partial) |
| 15 | `run_id` | string (UUID) | Уникальный ID для воспроизводимости |

### Сохранение и воспроизводимость
- Manifest сохраняется вместе с PAC run артефактами
- Доступен пользователю как часть output
- По `run_id` можно воспроизвести сборку (детерминизм)

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 16. D-RKR-29 — ROUTER-14: FAILURE POLICY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-29 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Fail-closed поведение для 10 failure scenarios? |
| **Audit evidence** | Текущая система не имеет формального failure policy; ошибки обрабатываются Python exceptions. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Fail-closed для всех 10 условий. Автоматический fallback на полную persona запрещён.** |

### Failure table

| # | Condition | Behavior |
|---|---|---|
| 1 | Unknown character (не в registry) | Routing error: `UNKNOWN_CHARACTER` |
| 2 | Unknown level (валидный character, но level не существует) | Routing error: `UNKNOWN_LEVEL` |
| 3 | Missing REQUIRED module (есть в policy, нет в filesystem/Gateway) | Routing error: `MISSING_REQUIRED_MODULE` |
| 4 | Ambiguous scene type (после fallback — неоднозначность) | Fail-closed → routing error: `AMBIGUOUS_SCENE_TYPE` |
| 5 | Unknown partner (partner_id не в registry) | Routing error: `UNKNOWN_PARTNER` |
| 6 | Budget overflow (после обрезания всех OPTIONAL всё ещё > hard cap) | Routing error: `BUDGET_OVERFLOW` |
| 7 | Registry mismatch (module_id есть в INDEX но файл отсутствует) | Routing error: `REGISTRY_MISMATCH` |
| 8 | Duplicate module ID в разных категориях | Routing warning + dedup; не ошибка |
| 9 | Unsafe category request (FORBIDDEN module для данного content_mode) | Routing error: `UNSAFE_CATEGORY_REQUEST` |
| 10 | Gateway read failure (filesystem error, permission) | Routing error: `GATEWAY_READ_FAILURE` |

**Категорически запрещено:**
- Silent fallback на полную persona (все модули)
- Silent fallback на level-only старую проекцию
- Пропуск REQUIRED модуля без ошибки

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 17. D-RKR-30 — ROUTER-15: TEST AND ACCEPTANCE GATES

| Поле | Значение |
|---|---|
| **ID** | D-RKR-30 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Минимальная батарея тестов для приёмки router implementation? |
| **Audit evidence** | Audit probes A–D покрывают ordinary / full / conflict / intimacy, но не partner routing, budget, failure, или воспроизводимость. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **10 обязательных probes для acceptance.** |

### Minimum test battery

| # | Probe | Что проверяет | Критерий |
|---|---|---|---|
| 1 | Ordinary U2-A (`scene_type=ordinary`) | Базовый routing | Module set ≠ full persona; intimacy категории исключены |
| 2 | Ordinary vs Intimacy (одинаковый level) | Scene-awareness | Разные module sets; intimacy получает sexology/physiology |
| 3 | Conflict U4-A (`scene_type=conflict`) | Conflict routing | trauma_ptsd REQUIRED |
| 4 | Intimacy U5-A (`scene_type=intimacy`) | Intimacy routing GAP-02 fix | sexology/physiology/sexual_scripts включены |
| 5 | Recovery U5-B (`scene_type=recovery`) | After-peak routing | transition module включён |
| 6 | Unknown partner | Failure policy D-RKR-29 #5 | Routing error: UNKNOWN_PARTNER |
| 7 | Missing REQUIRED module (mocked Gateway) | Failure policy D-RKR-29 #3 | Routing error: MISSING_REQUIRED_MODULE |
| 8 | Budget overflow (искусственно малый budget) | Budget handling | Routing error: BUDGET_OVERFLOW |
| 9 | Deterministic replay (одинаковый input × 2) | Determinism | Идентичные manifest-ы |
| 10 | Manifest completeness | Manifest schema | Все 15 полей присутствуют и валидны |

### Обязательные критерии для acceptance
- Ordinary и intimacy дают **разные** module sets (GAP-02 закрыт)
- U5-A intimacy получает утверждённые intimacy categories (D-RKR-24)
- Ordinary **не получает** лишние intimacy категории (no leak)
- Partner relationship выбирается корректно при указании partner_id
- Одинаковый request даёт одинаковый manifest (детерминизм)
- Gateway остаётся read-only (ни одна операция не пишет в personas/)
- Полный prompt не нужен для доказательства routing (тестируется manifest, не LLM output)
- Никакой LLM provider не вызывается в unit/integration тестах

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 18. D-RKR-31 — ROUTER-16: CODE LOCATION

| Поле | Значение |
|---|---|
| **ID** | D-RKR-31 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Где в репозитории разместить router package? |
| **Audit evidence** | Текущий PAC routing находится в `services/persona_authoring/gateway_adapter.py` (в PAC trial worktree). После merge — в `services/persona_authoring/`. |
| **Варианты** | A. `services/persona_gateway/` (внутри Gateway — не рекомендуется) |
|  | B. `services/persona_authoring/` (внутри PAC — ограничивает переиспользование) |
|  | C. `services/persona_context_routing/` (отдельный домен — рекомендуется) |
| **Рекомендация** | **C — отдельный домен `services/persona_context_routing/`.** |

**Rationale:**
- Gateway (`services/persona_gateway/`) остаётся read-only библиотекарем
- PAC (`services/persona_authoring/`) становится первым consumer router, но не владельцем routing policy
- Будущий Aside может стать отдельным consumer того же router
- Router остаётся stateless
- Implementation **НЕ авторизована** этим решением

**Proposed layout (не авторизован):**
```
services/persona_context_routing/
├── __init__.py
├── contracts.py          # PacRequest/PacContext/RoutingManifest dataclasses
├── router.py             # Stateless router: input → module list + manifest
├── policy.py             # Policy loader (JSON)
├── policy_v1.json        # Scene-type → module-category mapping
├── classifier.py         # Deterministic scene_type classifier (fallback rules)
├── manifest.py           # Manifest builder
└── errors.py             # RoutingError hierarchy
```

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 19. D-RKR-32 — ROUTER-17: PAC INTEGRATION BOUNDARY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-32 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие поля добавляются в PacRequest; кто вызывает router; backward compatibility? |
| **Audit evidence** | Текущий `PacRequest` в `services/persona_authoring/contracts.py` содержит поля для сцены и персонажа, но scene_type и partner_id не передаются в routing (только в prompt text). |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Расширить PacRequest; PAC gateway adapter вызывает router; старую static projection не удалять до parity tests.** |

### PacRequest changes (proposed, not authorized)

Новые поля в дополнение к существующим:
- `scene_type: Optional[SceneType]` — явное указание типа сцены
- `partner_id: Optional[str]` — ID партнёра по сцене
- `themes: Optional[List[str]]` — темы сцены
- `context_budget: Optional[ContextBudget]` — ограничения контекста (опционально)
- `content_mode: ContentMode` — safe/standard/explicit

### Integration flow (proposed)
```
PacRequest (с новыми полями)
  → PersonaContextRouter.route(request)
  → RoutingManifest
  → PersonaGateway.read_modules(manifest.included_modules)
  → Assemble context
  → LLM prompt
```

### Backward compatibility
- Старую static level-only projection (`gateway_adapter._build_module_list()`) **не удалять**
  до прохождения parity tests (D-RKR-30)
- **Не использовать** старую проекцию как silent fallback при ошибках router
- Миграция существующих тестов: добавить новые тесты с router; старые тесты
  оставить до подтверждения parity, затем удалить

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 20. D-RKR-33 — ROUTER-18: ASIDE BOUNDARY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-33 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Использует ли Aside тот же router? Как учитывается session memory? |
| **Audit evidence** | Aside (N6) в настоящее время использует `tools/aside_context_builder.py` — отдельный механизм сборки контекста, не интегрированный с PAC routing. |
| **Варианты** | A. Aside использует свой отдельный routing (статус-кво) |
|  | B. Aside использует тот же Persona Context Router (рекомендация) |
|  | C. Aside не использует router вообще (только conversation history) |
| **Рекомендация** | **B — Aside использует тот же router с `task_type=aside_chat`. Но НЕ менять Aside сейчас.** |

### Aside-specific routing rules (proposed)
- `task_type = aside_chat`
- `level` может быть null (Aside — не всегда level-structured)
- `scene_type` может быть `ordinary` по умолчанию
- Memory modules (`memory/`) включаются для Aside (в отличие от PAC где они excluded)
- Router **не читает** Aside session memory напрямую — Aside передаёт необходимые memory
  references через input contract
- Read-only граница personas сохраняется — Aside не пишет в personas/

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 21. D-RKR-34 — ROUTER-19: SECURITY AND PRIVACY

| Поле | Значение |
|---|---|
| **ID** | D-RKR-34 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Запрет arbitrary paths; secrets; интимное содержание в логах; redaction policy? |
| **Audit evidence** | N/A — security/privacy не оценивались в текущем audit. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **Registry-only module IDs; никаких arbitrary paths; никаких secrets в manifest.** |

### Security rules

| # | Rule | Enforcement |
|---|---|---|
| 1 | **Только registry module IDs** — router принимает module IDs только из INDEX/registry персонажа. Никаких произвольных файловых путей. | Allowlist в Gateway |
| 2 | **Никакие secrets в manifest** — manifest не содержит содержимого модулей, только metadata. | Schema validation |
| 3 | **Отсутствие полного интимного module content в логах** — module content не пишется в application log. Manifest (metadata-only) — допустим. | Logging policy |
| 4 | **Redaction policy** — интимный контент в error messages redacted. | Error message templates |
| 5 | **Local artifact retention** — manifest сохраняется локально в `local_runs/pac/`; не отправляется во внешние сервисы. | Storage path |
| 6 | **Provider payload logging** — полный payload (module content + situation) не пишется в логи по умолчанию; только по explicit debug flag. | Opt-in debug logging |

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | NO |

---

## 22. D-RKR-35 — ROUTER-20: AUTHORIZATION GATE

| Поле | Значение |
|---|---|
| **ID** | D-RKR-35 |
| **Статус** | OWNER_DECISION_REQUIRED |
| **Вопрос** | Какие решения должны быть ратифицированы владельцем перед implementation Slice 1? |
| **Audit evidence** | N/A — governance решение. |
| **Варианты** | Рекомендация ниже |
| **Рекомендация** | **ВСЕ BLOCKING decisions должны быть OWNER_RATIFIED перед Slice 1.** |

### Authorization sequence (proposed)

1. **Owner ratifies ALL blocking decisions (10 of 20):**
   - D-RKR-16 (Responsibility Boundary)
   - D-RKR-17 (Input Contract)
   - D-RKR-19 (Classification Authority)
   - D-RKR-20 (Policy Format)
   - D-RKR-21 (Required/Optional/Forbidden)
   - D-RKR-26 (Context Budget)
   - D-RKR-28 (Context Manifest)
   - D-RKR-29 (Failure Policy)
   - D-RKR-31 (Code Location)
   - D-RKR-35 (Authorization Gate — this decision)

2. **После ратификации всех blocking decisions:**
   - Отдельная документационная ратификация (update Status → OWNER_RATIFIED в этом register)
   - Отдельный implementation preflight
   - Отдельная owner authorization на bounded Slice 1

3. **Slice 1 scope (proposed, not authorized):**
   - `services/persona_context_routing/` package scaffold
   - `contracts.py` with dataclasses
   - `errors.py` with RoutingError hierarchy
   - `policy_v1.json` (initial policy for ordinary + intimacy)
   - `router.py` stateless implementation
   - Unit tests covering test battery (D-RKR-30)
   - PAC integration (gateway_adapter calls router)
   - **НЕ:** Aside integration, multi-partner, LLM classifier, embedding/vector, fine-tuning

| **Owner choice** | UNSET |
| **Code authorization** | NO |
| **Blocking** | YES |

---

## 23. DECISION DEPENDENCY GRAPH

```
D-RKR-16 (Responsibility Boundary)
  → D-RKR-17 (Input Contract)
    → D-RKR-18 (Scene Type Taxonomy)
    → D-RKR-19 (Classification Authority)
      → D-RKR-20 (Policy Format)
        → D-RKR-21 (Required/Optional/Forbidden)
          → D-RKR-22 (Partner Routing)
          → D-RKR-23 (Level Routing)
          → D-RKR-24 (Intimacy Access)
          → D-RKR-25 (Conflict Access)
            → D-RKR-26 (Context Budget)
              → D-RKR-27 (Ordering/Dedup)
                → D-RKR-28 (Context Manifest)
                  → D-RKR-29 (Failure Policy)
                    → D-RKR-30 (Test Gates)
                      → D-RKR-31 (Code Location)
                        → D-RKR-32 (PAC Integration)
                        → D-RKR-33 (Aside Boundary)
                          → D-RKR-34 (Security/Privacy)
                            → D-RKR-35 (Authorization Gate)
```

**BLOCKING decisions (implementation cannot start without these):**
D-RKR-16, D-RKR-17, D-RKR-19, D-RKR-20, D-RKR-21, D-RKR-26, D-RKR-28, D-RKR-29, D-RKR-31, D-RKR-35

---

## 24. RELATION TO EXISTING TRACKS

### Persona Gateway (N7 P1)
- Остаётся read-only библиотекарем
- Читает только разрешённые module IDs (allowlist)
- **Не** классифицирует сцены, не выбирает смысловой context, не знает о партнёрах или интимности

### PAC (N9)
- Authoring/evaluation consumer
- Первый consumer router
- **Не** владеет общей routing policy (если выбран отдельный router domain)

### Aside (N6)
- Отдельный runtime consumer
- **Не изменяется** этим Decision Register
- Интеграция с router требует отдельного решения (D-RKR-33)

### RKR (D-RKR-1…D-RKR-15)
- Общий governance-трек для knowledge routing
- Minimal Persona Context Router — bounded механизм внутри RKR, а не отдельный конкурирующий проект
- D-RKR-16…D-RKR-35 продолжают существующую нумерацию

### Character Evolution Sandbox (CES)
- **Не участвует** в Persona Context Routing
- **Не изменяется** этим Decision Register
- Sandbox memory не подключается к router

### N8 / Fine-tuning
- Остаётся BLOCKED
- Persona Context Router и approved PAC corpus должны быть готовы раньше, чем N8

---

## 25. OWNER RESPONSE TEMPLATE

```
D-RKR-16 (Responsibility Boundary): A / B / C
D-RKR-17 (Input Contract): ACCEPT / MODIFY (указать изменения)
D-RKR-18 (Scene Type Taxonomy): A / B / C
D-RKR-19 (Classification Authority): A / B / C / D
D-RKR-20 (Policy Format): A / B / C / D
D-RKR-21 (Required/Optional/Forbidden): ACCEPT / MODIFY
D-RKR-22 (Partner Routing): A / B / C
D-RKR-23 (Level Routing): A / B / C
D-RKR-24 (Intimacy Access): ACCEPT / MODIFY
D-RKR-25 (Conflict Access): ACCEPT / MODIFY
D-RKR-26 (Context Budget): ACCEPT / MODIFY
D-RKR-27 (Ordering/Dedup): ACCEPT / MODIFY
D-RKR-28 (Context Manifest): ACCEPT / MODIFY
D-RKR-29 (Failure Policy): ACCEPT / MODIFY
D-RKR-30 (Test Gates): ACCEPT / MODIFY
D-RKR-31 (Code Location): A / B / C
D-RKR-32 (PAC Integration): ACCEPT / MODIFY
D-RKR-33 (Aside Boundary): A / B / C
D-RKR-34 (Security/Privacy): ACCEPT / MODIFY
D-RKR-35 (Authorization Gate): ACCEPT / MODIFY

Clarifications:
...
```

---

## APPENDIX A: AUDIT EVIDENCE SUMMARY

| Audit item | Value | Source |
|---|---|---|
| Audit HEAD | `afa64d3af14ad78366dc34cad68af3fb91f2423c` | JSON manifest §audit_HEAD |
| Registered Kira modules | 61 | JSON manifest §module_inventory.registered_module_count |
| Physical files | 63 (61 registered + INDEX.json + levels/ALGORITHMS.json) | JSON manifest §module_inventory.physical_file_count |
| Excluded prefixes | 5 (`visual/`, `physiology/`, `sexology/`, `sexual_scripts/`, `memory/`) | JSON manifest §excluded_prefixes |
| Probe A (ordinary U2-A) | 30 modules, 12 categories | JSON manifest §probes.A |
| Probe C (conflict U4-A) | 30 modules, same categories as A | JSON manifest §probes.C |
| Probe D (intimacy U5-A) | 30 modules, same categories as A | JSON manifest §probes.D |
| GAP-01 | Scene-awareness absent | MD report §1, §6.1 |
| GAP-02 | Intimacy categories blocked at all levels (CRITICAL) | MD report §1, §6.2; probes A=C=D |
| GAP-03 | Partner routing absent | MD report §1, §6.3 |
| GAP-04 | Context budget absent | MD report §1, §6.4 |
| Verdict | PREPARE_MINIMAL_ROUTER_DECISION_REGISTER | MD report §1 |
| Classification | LEVEL_ONLY | MD report §1 |
| Source commit (PAC trial worktree) | `653f52ff1e60b2543774399ec5e73edfa17d7653` | JSON manifest §probes.B.source_commit |

**Evidence source:** LOCAL_EXTERNAL_EVIDENCE — `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\PERSONA_CONTEXT_ROUTING_READONLY_AUDIT_2026-08-03.{md,json}`

---

*Последнее обновление: 2026-08-03*
*Все решения: OWNER_DECISION_REQUIRED; implementation: NOT AUTHORIZED.*