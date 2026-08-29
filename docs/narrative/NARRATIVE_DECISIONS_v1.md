# NARRATIVE DECISIONS v1 — Voyage Narrative Engine (VNE)

> **Назначение.** Канонический документ продуктовых и архитектурных решений по Narrative-части VNE.
> Это «source of truth» для решений, а не для механик. Если другой документ противоречит этому файлу
> по вопросу из списка ниже — приоритет у этого файла. Решения меняются только через новую версию
> (`v2`, …) с указанием причины.
>
> **Статус:** ЗАФИКСИРОВАНО (v1.1)
> **Дата:** 2026-07-08
> **Narrative baseline на момент фиксации:** `5571bd2505715b8f19b092ad1762b8d32449c360`
> **Область:** Narrative / продукт / story runtime. НЕ касается Voyage Framework automation (отдельный трек).

---

## Как пользоваться этим документом

- Каждое решение имеет: **Decision** (что решили), **Rationale** (почему), **Implications** (что из этого следует), **Status**.
- Если вопрос возникает повторно — он уже закрыт здесь. Не пересматриваем без новой версии документа.
- Отложенные решения помечены `DEFERRED` с указанием, в какой фазе к ним вернёмся.

---

## 1. Product identity — что мы строим

**Decision.** Продукт = **два независимых трека с общим лором, с явной дверью конвергенции на N6**:

1. **α — RenPy Visual Novel** — игрок запускает игру, проходит сцены, делает выборы, видит персонажей, диалоги, визуал и последствия. Это рабочий игровой runtime MVP.
2. **β — LLM Persona Pipeline** — глубокие психологические персонажи, сценарии, роли R1–R8, модульная архитектура. Используется для LLM-чата (Kimi/DeepSeek/local) и как **источник правды** для психологии персонажей.

**Конвергенция (N6+): Character Aside** — персистентный LLM-чат с персонажем внутри RenPy. Персонаж помнит канон до текущего момента и прошлые aside-сессии, но не модифицирует основную игру. Локальный LLM API предпочтителен для взрослого контента.

**Rationale.** Оба трека уже фактически присутствуют в repo (scripted RenPy + persona/LLM-система). Это не «или-или», и не «одно — legacy для другого». Оба — полноценные продукты. Конвергенция через Character Aside сохраняет чистоту каждого трека и добавляет флагманскую фичу без слияния runtime.

**Implications.**
- Это **не** только классическая VN и **не** только чат с персонажами.
- LLM-чат (β) — **активный трек**, не legacy и не demo. Он развивает психологию персонажей, которая потом используется в Character Aside.
- **Character Aside** — единственная точка конвергенции α и β на N6. До N6 треки раздельны.
- Будущая цель: диалоги с персонажами через нейросеть **внутри** RenPy (Aside).

**Status:** ЗАФИКСИРОВАНО (v1.1, 2026-07-08).

---

## 2. Source of truth — источник правды

**Decision.** Два источника правды, разделённых по домену:

- **Сцены (scenario): JSON-first.** `SCENARIO_*.json` — единственный источник правды о сцене (метаданные, диалоги, действия, мысли, choices, flags, эффекты, safety).
- **Персонажи (persona): Модульные файлы-first.** `personas/<name>/` — источник правды для психологии, речи, инициативы, динамики персонажа. Монофайл (`*_MODULE_v*.json`) = **build artifact**, собирается из модульных файлов.

**Rationale.** Ранее источника правды было два для сцен: JSON описывает сцену, а playable-сцена руками пишется в `script.rpy`. Для персон: модульные файлы + монофайл — не synced. Разделение доменов устраняет дублирование: JSON для сцен, модули для персон.

**Implications.**
- RenPy в будущем **генерируется из JSON** или читает подготовленную из JSON структуру.
- Ручной `script.rpy` — **временный** playable-прототип переходного периода.
- LLM-чат сам по себе источником правды не является (генерирует, но сохраняет в JSON/модули).
- **Монофайл** (`OLGA_MODULE_v3.json`) — собирается из `personas/olga/` при сборке, не редактируется напрямую.
- **Переходная (гибридная) схема разрешена явно:**
  - `SC_003–SC_018` — остаются playable в ручном RenPy (не переписываем без отдельного RN-задания).
  - `SC_019–SC_027` — остаются source-only JSON.
  - Все новые архитектурные решения проектируются вокруг JSON-first (сцены) и module-first (персоны).

**Status:** ЗАФИКСИРОВАНО (v1.1, 2026-07-08).

---

## 3. Runtime target и платформа

**Decision.** Первичный MVP runtime — **RenPy desktop**. LLM-чат остаётся в продуктовой концепции как будущий слой. Браузер — позже как editor/preview, не MVP. Termux/Android — старый dev-инструмент, не целевая платформа.

**Rationale.** RenPy уже запускается и уже содержит playable-сцены (`SC_003–SC_018`, 113 labels, RenPy SDK 8.5.3 локально).

**Implications.**
- RenPy = **первый renderer/target и playable runtime**, но **не единственный источник правды** (см. §2).
- LLM-чат в будущем: диалоги с персонажами, режиссёрский режим, генерация вариантов сцены, тестирование персонажей, настройка сюжета, стоп-кадры визуала, подготовка материала → сохранение как сцена.
- Браузерный runtime: возможен позже как web-editor / preview / панель настройки / authoring UI. `DEFERRED`.

**Status:** ЗАФИКСИРОВАНО (RenPy MVP); браузер — `DEFERRED`.

---

## 4. LLM role — роль нейросети

**Decision.** LLM — **инструмент генерации и живого диалога**, а также будущий director/character-слой. LLM **не заменяет** структурную схему и runtime-гарантии.

**Rationale & корректная формулировка (важно).**
Для генерации и живого диалога LLM может гибко понимать контекст, мысли персонажей, тон и ограничения, и имеет собственные фильтры. **Но для продукта этого недостаточно.** Схема нужна не для того, чтобы «объяснять нейросети», а чтобы:
сохранить сцену; редактировать её без поломки; отобразить в RenPy; включать/выключать мысли; переключать POV; проверять branches и flags; сохранять состояние игрока; строить preview; переносить сцену между LLM-чатом и playable runtime.

Иначе мы снова упрёмся в проблему: LLM сгенерировала красивый текст, но игра не знает, где речь, где мысль, где действие, какой choice, какой flag и что показывать игроку.

**Implications.**
- Фильтры LLM помогают в генерации, но **не являются** runtime-гарантией сохранения/воспроизведения/проверки.
- Любой результат LLM-сессии становится частью продукта только после сохранения в JSON по схеме (§5).

**Status:** ЗАФИКСИРОВАНО.

---

## 5. Scenario schema direction — направление схемы сцены

**Decision.** Нужна **минимальная структурная модель сцены** (`SCENARIO_SCHEMA_V2`). Главный дефект текущей модели: мысль, действие и речь смешаны в строках (`action`, `kira_reaction`, `yakov_reaction`, `sergey_reaction`).

**Целевая минимальная модель** (детали — в отдельном `SCENARIO_SCHEMA_V2_SPEC.md`):
- `ordered beats` — упорядоченные единицы сцены;
- `speaker` — кто говорит/действует;
- `speech` — реплика;
- `action` — действие (отдельно от речи);
- `thought` / `inner_monologue` — мысль;
- `pov` — чья точка зрения;
- `thought_visibility` — `hidden | revealed | always`;
- `choice` / `branch` — выборы и ветки;
- `flags` / `effects` — что ветка ставит/меняет;
- `safety` / `content metadata` — рейтинг, заметки, ограничения.

**Rationale.** Без разделения thought/action/speech невозможны режимы чтения, POV, безопасное редактирование и корректный рендер в RenPy.

**Implications.**
- Схему **не** делаем переусложнённой сразу — начинаем с минимально достаточной.
- Существующий `tools/vne_to_renpy/exporter.py` (JSON → skeletal `.rpy`) — зерно будущего preview-адаптера, переиспользуем.
- Персонажи: ориентир — реестр/конфиг (в exporter уже есть `DISPLAY_NAMES`), а не хардкод имён в полях. Детализация — в схеме/контракте. `DEFERRED` до schema spec.

**Status:** НАПРАВЛЕНИЕ ЗАФИКСИРОВАНО; точные поля/enum'ы — в `SCENARIO_SCHEMA_V2_SPEC.md`.

---

## 6. Player settings direction — персонализация и режимы

**Decision.** Персонализация и режимы чтения **настраиваются пользователем**. В MVP их реализовывать не обязательно, но **схему проектируем так, чтобы это стало возможным**.

**Персонализация = настройки истории/режима** (перед стартом или во время игры):
частота показа мыслей; драматичность тона; плотность выборов; предпочтительный POV; допустимые/нежелательные темы; режим «режиссёр»; включён ли LLM-чат; степень вмешательства игрока в сюжет.

**Режимы чтения (целевые):**
- **Classic VN** — речь + действия;
- **Psychological** — речь + действия + внутренний монолог POV-персонажа;
- **Mind-reading** — видны скрытые мысли нескольких персонажей;
- **Director** — пользователь обсуждает сцену с персонажами/нейросетью;
- **Hidden** — часть мыслей хранится, но не показывается игроку.

**Возможная модель `player_profile` (ориентир, не финал):**
`preferred_pov`, `thought_visibility`, `drama_intensity`, `choice_density`, `content_boundaries`, `romance_focus`, `psychological_detail_level`.

**Status:** НАПРАВЛЕНИЕ ЗАФИКСИРОВАНО; реализация — `DEFERRED` (не первая фаза). Схема обязана это поддерживать на уровне дизайна.

---

## 7. Documentation structure — структура документации

**Decision.** Выводы закрепляем **набором канонических Narrative-документов** в `docs/narrative/`, а не одним файлом.

| Документ | Назначение |
|---|---|
| `NARRATIVE_DECISIONS_v1.md` (этот файл) | Зафиксированные продуктовые/архитектурные решения |
| `NARRATIVE_ARCHITECTURE.md` | Слои продукта: source model → runtime → renderer → RenPy → validation → authoring |
| `SCENARIO_SCHEMA_V2_SPEC.md` | Новая модель сцены: beats, speech, action, thought, pov, choices, flags |
| `STORY_RUNTIME_CONTRACT.md` | Как исполняются scenes/branches/flags/state, save/load, доступность следующей сцены |
| `PLAYER_EXPERIENCE_SPEC.md` | Что видит игрок: мысли, POV, choice density, tone, settings |
| `NARRATIVE_ROADMAP.md` | Фазы N0–N6 с задачами, критериями готовности и порядком |

**Status:** ЗАФИКСИРОВАНО. Прочие документы из таблицы создаются в следующих шагах.

---

## 8. Framework / Narrative boundary — граница ответственности

**Decision.** Чёткое разделение ролей:

- **Voyage Framework** управляет **процессом разработки**: guardrails, validation, workflow, handoff, source-only loops, audit, automation, CLI (`voyage` / `vne_adapter.py`).
- **Narrative project** содержит **продукт**: сценарии, персонажей, RenPy, story runtime, player experience.

**Правила:**
- Framework **не** становится игровым runtime.
- Narrative **не** изобретает свою workflow-automation, если это задача Framework.
- Формула: **Voyage контролирует разработку Narrative, но не заменяет Narrative runtime.**

**Rationale.** Ранее Framework и Narrative смешивались. Граница уже частично описана в `FRAMEWORK_VNE_INTEGRATION.md` (voyage CLI снаружи, VNE остаётся спецификацией, `tools/vne_adapter.py` — обёртка). Здесь это закреплено как решение.

**Status:** ЗАФИКСИРОВАНО.

---

## 9. Out of scope now — что сейчас НЕ делаем

- Создание `SC_028` и продолжение source-only pipeline — **ЗАПРЕЩЕНО** до решений по schema/runtime.
- Текстовое «улучшение качества» `SC_020–SC_027` — **не делаем** до `SCENARIO_SCHEMA_V2` (иначе перепишем при миграции).
- RenPy-патчи сверх существующего playable-диапазона `SC_003–SC_018` — отдельная фаза, не сейчас.
- Реализация player settings / pre-game questionnaire — `DEFERRED` (не первая фаза).
- Браузерный runtime, авто-launch, bridge-execution, изменения Framework core — вне Narrative-трека.
- Массовая миграция старых сцен на schema v2 — отдельная задача после утверждения спецификации.
- **Массовый экспорт персон из `personas/<name>/` в RenPy-формат** — `DEFERRED` до N6 / Character Aside. До N6 персонажи в RenPy — hardcoded или ручной перенос.
- Текстовое «улучшение качества» `SC_020–SC_027` — **не делаем** до `SCENARIO_SCHEMA_V2` (иначе перепишем при миграции).
- RenPy-патчи сверх существующего playable-диапазона `SC_003–SC_018` — отдельная фаза, не сейчас.
- Реализация player settings / pre-game questionnaire — `DEFERRED` (не первая фаза).
- Браузерный runtime, авто-launch, bridge-execution, изменения Framework core — вне Narrative-трека.
- Массовая миграция старых сцен на schema v2 — отдельная задача после утверждения спецификации.

**Status:** ЗАФИКСИРОВАНО.

---

## 10. Manual Scene Reference Input (SVA-MR1) — OD-SVA-MR-01

> **Трек:** SVA — Scenario Visual Authoring (scene image authoring).
> **Milestone:** SVA-MR1 — `MANUAL_SCENE_REFERENCE_INPUT_V0`.
> **Owner decision:** `OD-SVA-MR-01 = A` — Manual Scene Reference Input is a **required** authoring capability.
> **Дата записи (addendum к v1.1):** 2026-08-28.

**Decision.** During scene image authoring, the application must let a user manually attach visual
references to a specific character and/or to the scene (current authoring item), alongside the
automatically derived Character Canon references. Manual reference upload is a planned, ratified product
capability — not an optional prototype.

**Rationale.** Scene image authoring needs author-controllable visual input (per-character and
scene-level) that does **not** require mutating Character Canon. Manual references are an additional
*input* to reference selection / `ReferenceBundle` construction — not a second provider pipeline.

**Status:** `PLANNED / RATIFIED_REQUIREMENT`. The requirement is ratified by the owner; implementation
is **NOT** authorized in this task and must occur **after** the generic multi-character reference
conditioning foundation is proven.

### Required semantics (OD-SVA-MR-01 = A)

1. The application derives visible character sections from the scene's `characters_in_frame`.
2. A user may manually attach a reference to a specific character.
3. Every character-specific manual reference must have explicit `character_id`, `role`, and `scope`.
4. Manual references may also be scene-level (no character ownership), for example: interaction/pose
   composition, camera/composition, location/environment.
5. Default `scope` = `THIS_SCENE_ONLY` / current authoring item.
6. Manual upload MUST NOT automatically mutate Character Canon.
7. Required conceptual modes:
   - **A. `ADD_TO_CURRENT_GENERATION`** — add a manual ref alongside Canon refs for the current
     scene/media item.
   - **B. `OVERRIDE_FOR_CURRENT_GENERATION`** — replace/disable a selected automatic ref only for the
     current generation/media item.
   - **C. `PROPOSE_FOR_CANON`** — a separate explicit workflow; a manual ref may be proposed to
     Character Canon but requires the normal review/approval process before becoming canonical.
8. The authoring UI should preview the references that will actually be sent before generation.
9. The user should be able to enable/disable individual refs before generation, subject to fail-closed
   minimum identity/reference requirements defined by the implementation contract.
10. Manual references must integrate with the same generic `ReferenceBundle` architecture.
11. No character-specific code.
12. Future correctly registered characters must automatically receive the same manual-reference UI and
    pipeline behavior.

### Architectural position (conceptual flow)

```text
Scene / MediaItem
+
Character Canon automatic refs
+
Manual scene references
        ↓
reference selection / ownership
        ↓
generic ReferenceBundle
        ↓
conditioned provider attachment
        ↓
image provider
```

Manual refs are an **input** to bundle construction/selection. They are **NOT** a second independent
provider pipeline.

### Ownership model (planning level)

- **Character-specific reference:** `character_id` = explicit owner; `role` = explicit; `scope` =
  scene/media-local by default.
- **Scene-level reference:** no false character ownership; `role` = interaction / composition /
  location / equivalent supported role; `scope` = scene/media-local.

A low-level storage schema is **not** finalized here — that belongs to the later SVA-MR1 contract
implementation.

### Planned authoring UX (semantics only)

Before image generation, the UI should expose, per visible character (e.g. KIRA, SERGEY): automatic
Canon refs, manual refs, and enable/disable controls; plus a SCENE section for
interaction/composition/location refs. The actual UI framework/layout is **not** decided in this task.

### Non-goals (SVA-MR1 v0 does NOT mean)

- arbitrary automatic Canon mutation
- implicit identity reassignment
- hidden mixing of all uploaded files
- unordered anonymous reference pool
- character-ID hardcodes
- bypassing approval/status gates
- bypassing `ReferenceBundle`
- using local path text instead of real image attachment

---

## 11. VNE Reference Library (SVA-RL1) — OD-SVA-RL-01

> **Трек:** SVA — Scenario Visual Authoring (scene image authoring).
> **Milestone:** SVA-RL1 — `VNE_REFERENCE_LIBRARY_V0`.
> **Owner decision:** `OD-SVA-RL-01 = A` — VNE must own a dedicated working Reference Library for visual authoring assets.
> **Дата записи (addendum к v1.1):** 2026-08-29.

**Decision.** VNE authoring has its own working visual reference library. External repositories and arbitrary
local folders — including `narrative-character-canon` — are **import sources only**, not runtime or authoring
dependencies that VNE must continuously interpret. After a successful controlled import, VNE works from its own
copied assets.

**Rationale.** VNE must not depend on the availability, governance, status, or rules of an external repository to
select ordinary authoring references. Copying into a VNE-owned library decouples authoring from the source's
lifecycle.

**Status:** `PLANNED / RATIFIED_REQUIREMENT`. The requirement is ratified by the owner; implementation is **NOT**
authorized in this task.

### Required semantics (OD-SVA-RL-01 = A)

1. VNE owns a dedicated working Reference Library for visual authoring assets.
2. External repositories and arbitrary local folders are **IMPORT SOURCES only**.
3. `narrative-character-canon` is one possible import source — not a runtime or authoring dependency that VNE
   must continuously interpret.
4. After a successful import:
   - VNE works from its own copy;
   - the source repository may move/change without invalidating the imported VNE copy;
   - VNE does **not** automatically reread external governance/status/rules;
   - VNE does **not** modify the source asset or source repository.
5. This does **not** mean every file from every external folder is automatically approved or automatically
   imported. Import remains an explicit user-controlled action.

### Library organization (planning level only)

The application must support:

- character-owned reference collections;
- creation of new character folders/collections;
- adding newly approved/generated visual files;
- browsing imported references per character;
- optional organization such as identity/body/outfit/scene/custom collections.

Those folder names are **not** mandatory schema in this task; the implementation may choose a more flexible
collection model.

### Technical manifest (planning level only)

The library requires a small technical manifest/index. Minimum conceptual metadata:

- `asset_id`
- `character_id`
- `relative_path`
- `filename`
- `sha256`
- `file_type`

Optional planning-level metadata: `role`, `collection`, `source_filename`, `source_type`.

Rules:

- stable `asset_id` belongs to the VNE Reference Library;
- `relative_path` is VNE-library-relative;
- imported asset identity must not depend solely on the original absolute source path;
- the source absolute machine path is not required as canonical identity;
- the manifest is technical authoring metadata, **NOT** Character Canon governance.

The JSON/schema version is **not** finalized in this task.

### Relation to the existing Character Canon Bridge

The existing Character Canon Bridge is **NOT** deleted. Existing strict Canon-based workflows may continue using
it. However, ordinary Scene Authoring Reference Library selection must not require VNE to understand the external
`narrative-character-canon` repository's complete governance/status workflow. The new Reference Library is an
additional controlled authoring source feeding the **same** downstream `ReferenceBundle` architecture. Existing
bridge code is **not** marked deprecated here.

### Non-goals (SVA-RL v0 does NOT require)

- automatic mirroring/synchronization with NCC
- automatic copying of every file found in a source tree
- VNE modifying the external source repository
- external governance parsing for every generation
- automatic use of every imported image
- a new provider pipeline
- Character Canon mutation
- cloud asset management
- automatic AI ranking of all references
- bulk generation
- automatic retries

### Implementation decisions (OD-SVA-RL-IMPL-01..04 = A)

The SVA-RL1 implementation slice (`VNE_REFERENCE_LIBRARY_V0`) finalizes the
previously "planning level only" points as follows:

| Decision | Value |
|---|---|
| OD-SVA-RL-IMPL-01 = A | `REFERENCE_LIBRARY_ROOT = authoring/reference_library/`; manifest `authoring/reference_library/REFERENCE_LIBRARY_MANIFEST.json`; future asset root `authoring/reference_library/assets/`; future character convention `authoring/reference_library/assets/characters/<character_id>/...` |
| OD-SVA-RL-IMPL-02 = A | Manifest, code, and tests are Git-tracked; reference image bytes under `authoring/reference_library/assets/**` are Git-ignored in v0; no Git LFS in v0 |
| OD-SVA-RL-IMPL-03 = A | Reference metadata uses a required opaque `character_id` plus an optional free-string `collection`; no collection enum; no filesystem-slug requirement for `collection`; no explicit character-registration operation in RL1 |
| OD-SVA-RL-IMPL-04 = A | SVA-RL1 is additive and isolated; no refactor of `tools/visual_asset_registry.py`; shared-helper extraction is deferred to SVA-RL2 only if justified |

SVA-RL1 is implemented and published (see `NARRATIVE_ROADMAP.md` §12).
Controlled import (copy-in, add/update/remove, and external-source
magic-byte validation) belongs to SVA-RL2 and is **NOT** implemented in
SVA-RL1.

---

## 12. Controlled Reference Import (SVA-RL2) — OD-SVA-RL-02

> **Трек:** SVA — Scenario Visual Authoring (scene image authoring).
> **Milestone:** SVA-RL2 — `CONTROLLED_REFERENCE_IMPORT_V0`.
> **Owner decision:** `OD-SVA-RL-02 = A` — Controlled Reference Import is required.
> **Дата записи (addendum к v1.1):** 2026-08-29.

**Decision.** Bringing an external or local source image into the VNE Reference Library is a controlled import
action, not an automatic sync. The imported copy is registered in the technical manifest and becomes available to
scene authoring.

**Rationale.** A controlled copy preserves VNE ownership of authoring assets while keeping the external source
read-only and non-authoritative for the imported copy.

**Status:** `PLANNED / RATIFIED_REQUIREMENT`. Implementation is **NOT** authorized in this task.

### Conceptual pipeline (OD-SVA-RL-02 = A)

```text
external/local source image
        ↓
user selects import
        ↓
format/path validation
        ↓
copy into VNE Reference Library
        ↓
SHA-256
        ↓
technical manifest registration
        ↓
available to scene authoring
```

### Import rules

- no automatic source synchronization is required;
- no automatic overwrite of an imported asset from its original source;
- importing a newer source file is a separate controlled action;
- duplicate detection may use SHA-256;
- the source repository remains read-only.

### Supported image formats

Align with the existing VNE visual asset policy where practical:

- PNG
- WEBP
- JPEG/JPG

The implementation schema and exact filesystem root are **not** finalized in this task.

### Implementation decisions (OD-SVA-RL2-IMPL-01..03 = A)

The SVA-RL2 implementation slice (`CONTROLLED_REFERENCE_IMPORT_V0`) finalizes the
previously "not finalized" points as follows:

| Decision | Value |
|---|---|
| OD-SVA-RL2-IMPL-01 = A | Physical imported asset convention: `authoring/reference_library/assets/characters/<character_id>/<asset_id>.<ext>` (canonical `.png` / `.jpg` / `.webp`). `collection` remains metadata only and never affects the physical path. |
| OD-SVA-RL2-IMPL-02 = A | Duplicate SHA ownership policy: same SHA + same `character_id` → deterministic no-op (no duplicate binary or record); same SHA + different `character_id` → fail closed (no cross-character binary sharing). |
| OD-SVA-RL2-IMPL-03 = A | `asset_id` collision policy: same `asset_id` + same SHA + same ownership → deterministic no-op allowed; same `asset_id` + different bytes / conflicting ownership → reject. No update/replace/remove/overwrite in v0. |

SVA-RL2 v0 is explicit controlled single-file COPY import only: no directory
scanning, no automatic sync, no source mutation, no update, and no remove.
`role`/`source_type` manifest fields remain deferred (the RL1 manifest contract
is not extended in this slice).

SVA-RL2 is implemented and published (see `NARRATIVE_ROADMAP.md` §12).

---

## 13. Explicit Reference Selection for Library Assets — OD-SVA-RL-03

> **Трек:** SVA — Scenario Visual Authoring (scene image authoring).
> **Owner decision:** `OD-SVA-RL-03 = A` — Explicit reference selection for library assets is required.
> **Дата записи (addendum к v1.1):** 2026-08-29.

**Decision.** `DISCOVERY != SELECTION`. The application may discover/show all imported visual references for a
character, but only an explicitly selected bounded subset is allowed to enter a specific generation request.

**Rationale.** Showing a library is not the same as sending it to a provider. Without an explicit bounded
selection, every imported image could leak into a generation request, which is prohibited.

**Status:** `PLANNED / RATIFIED_REQUIREMENT`.

### Conceptual flow (OD-SVA-RL-03 = A)

```text
Reference Library
        ↓
user/reference selection
        ↓
Reference Package Preview
        ↓
ReferenceBundle
        ↓
existing RC3 conditioned provider attachment
```

No second provider pipeline is created. The existing generic architecture remains authoritative downstream:
`explicit selection → ReferenceBundle → conditioned provider attachment`.

### Relation to SVA-MR1

The existing ratified `OD-SVA-MR-01 = A` (SVA-MR1 — `MANUAL_SCENE_REFERENCE_INPUT_V0`) is preserved. Planned UX:

Add manual reference
→ either choose an existing VNE Reference Library asset
OR
→ import a new visual into the library
OR, if later supported,
→ temporary generation-only reference

Temporary mode is **not** required in RL1/RL2 implementation. `PROPOSE_FOR_CANON` remains a separate workflow and
is not automatic.

---

## 14. Reference Library → ReferenceBundle Adapter (RBA v0) — OD-SVA-RBA

> **Трек:** SVA — Scenario Visual Authoring (scene image authoring).
> **Milestone:** SVA-RBA — `REFERENCE_LIBRARY_TO_REFERENCE_BUNDLE_ADAPTER_V0`.
> **Owner decisions:** `OD-SVA-RBA-01..07 = A`.
> **Дата записи (addendum к v1.1):** 2026-08-29.

**Decision.** Imported VNE Reference Library records flow into the existing provider-neutral `ReferenceBundle`
contract through a dedicated adapter; there is no second provider pipeline. Library-origin bundles use the
neutral transport role `reference` and carry no Character Canon metadata.

### Owner decisions (OD-SVA-RBA-01..07 = A)

| Decision | Value |
|---|---|
| OD-SVA-RBA-01 = A | Strategy B: `ReferenceCharacterGroup.status` and `.canon_content_hash` become optional; Library groups carry both `None`; Canon groups keep real Canon values. Valid pairs are both-non-empty or both-None. |
| OD-SVA-RBA-02 = A | `ReferenceCharacterGroup` field order `(character_id, references, status=None, canon_content_hash=None)`; existing constructions are keyword-based. |
| OD-SVA-RBA-03 = A | `ReferenceEntry.source_asset_id: Optional[str] = None`; Canon entries omit it; Library entries carry the real `ReferenceRecord.asset_id` in the semantic payload/hash. |
| OD-SVA-RBA-04 = A | Library selection-time roles via optional `roles_by_asset_id`; default role `"reference"` (neutral transport role, not identity / not minimum-identity evidence / not a finalized role taxonomy). |
| OD-SVA-RBA-05 = A | The adapter receives already-resolved ordered `ReferenceRecord` sequences per character; it does NOT load/search the manifest, import files, or allocate asset IDs. |
| OD-SVA-RBA-06 = A | Byte resolution is `repo_root / ReferenceRecord.relative_path`; the parameter is named `repo_root` (not `library_root`). |
| OD-SVA-RBA-07 = A | `REFERENCE_BUNDLE_SCHEMA_VERSION` remains `reference_bundle/0.1`; no schema-version bump. |

### Implementation facts (SVA-RBA v0)

- Library-origin ReferenceBundle support is implemented (`build_reference_bundle_from_library`).
- Canon-only `status`/`canon_content_hash` are optional as a paired invariant (fail closed on mixed/empty).
- Library groups carry neither Canon field; `source_asset_id` provides VNE Library traceability.
- Existing Canon semantic payload and content-hash semantics are preserved (byte-for-byte).
- `DEFAULT_LIBRARY_ROLE = "reference"`.
- The adapter takes resolved `ReferenceRecord` inputs and resolves `record.relative_path` from `repo_root`.
- ReferenceBundle schema remains `reference_bundle/0.1`; RC3 (conditioned provider attachment) is unchanged and reused.
- No second provider pipeline exists.

### Non-goals (v0)

Not implemented in this slice: scene-level references, `SceneReferenceGroup`, `prompt_alias`, minimum identity
gate, `SceneVariant`, cast override, authoring facade, and Ren'Py UI.

**Status:** `IMPLEMENTED (v0)`.

---

## Сводка решений (быстрый справочник)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Product identity | Dual-product (C): RenPy VN + LLM Persona Pipeline; конвергенция через Character Aside на N6 |
| 2 | Source of truth | Сцены: JSON-first; Персоны: модульные `personas/<name>/` = источник, монофайл = build artifact |
| 3 | Runtime target | RenPy desktop = primary MVP; браузер позже; Termux — dev-tool |
| 4 | LLM role | Генерация/диалог/director; **не** заменяет схему и runtime |
| 5 | Scenario schema | Нужна; ordered beats + speech/action/thought/pov/visibility/choice/flags/safety |
| 6 | Player settings | Настраиваются пользователем; реализация отложена; схема обязана поддерживать |
| 7 | Documentation | Набор канонических docs в `docs/narrative/` |
| 8 | Framework boundary | Framework = workflow/guardrails; Narrative = продукт/runtime |
| 9 | Out of scope | SC_028 нет; качество SC_020–027 не трогаем; миграция позже; массовый export персон в RenPy — N6+ |
| 10 | Manual Scene Reference Input (SVA-MR1) | OD-SVA-MR-01 = A: ручной scene-reference обязателен; character_id/role/scope; scene-local по умолчанию; НЕ мутирует Canon; через ReferenceBundle; UI preview + enable/disable |
| 11 | VNE Reference Library (SVA-RL1) | OD-SVA-RL-01 = A: собственная рабочая Reference Library визуальных ассетов; внешние репозитории/папки = только import-источники; VNE владеет импортированными копиями; без авто-синка с источником |
| 12 | Controlled Reference Import (SVA-RL2) | OD-SVA-RL-02 = A: контролируемый импорт (валидация формата/пути → копия → SHA-256 → манифест); PNG/WEBP/JPEG/JPG; источник read-only; дубликаты по SHA-256 |
| 13 | Explicit Reference Selection for Library Assets | OD-SVA-RL-03 = A: DISCOVERY ≠ SELECTION; только явно выбранное ограниченное подмножество идёт в generation-запрос; Reference Library → selection → Reference Package Preview → ReferenceBundle → RC3 attachment |
| 14 | Reference Library → ReferenceBundle adapter (RBA v0) | OD-SVA-RBA-01..07 = A: Strategy B (optional paired Canon metadata); `source_asset_id` traceability; neutral `reference` role; resolved-record input; `repo_root` resolution; schema stays `reference_bundle/0.1` |
|---|---|---|
| 1 | Product identity | Гибрид: RenPy VN + LLM director/character layer |
| 2 | Source of truth | **JSON-first** (переходный гибрид разрешён) |
| 3 | Runtime target | RenPy desktop = primary MVP; браузер позже; Termux — dev-tool |
| 4 | LLM role | Генерация/диалог/director; **не** заменяет схему и runtime |
| 5 | Scenario schema | Нужна; ordered beats + speech/action/thought/pov/visibility/choice/flags/safety |
| 6 | Player settings | Настраиваются пользователем; реализация отложена; схема обязана поддерживать |
| 7 | Documentation | Набор канонических docs в `docs/narrative/` |
| 8 | Framework boundary | Framework = workflow/guardrails; Narrative = продукт/runtime |
| 9 | Out of scope | SC_028 нет; качество SC_020–027 не трогаем; миграция позже |

---

## Следующие шаги (порядок)

1. `NARRATIVE_ARCHITECTURE.md` — зафиксировать слои продукта.
2. `SCENARIO_SCHEMA_V2_SPEC.md` — минимальная модель сцены + 1 пример сцены в новой схеме + правила миграции `SC_003–027`.
3. `STORY_RUNTIME_CONTRACT.md` — контракт исполнения (scene complete, flags, state, save/load, доступность следующей сцены).
4. `PLAYER_EXPERIENCE_SPEC.md` — режимы чтения, POV, choice density, settings.
5. `NARRATIVE_ROADMAP.md` — фазы N0–N6 с критериями готовности.

> Коммит этого документа выполняется через стандартный Narrative workflow (Claude Code), не напрямую.
