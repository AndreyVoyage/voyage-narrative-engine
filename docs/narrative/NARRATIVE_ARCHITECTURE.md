# NARRATIVE ARCHITECTURE — Voyage Narrative Engine (VNE)

> **Назначение.** Описание слоёв Narrative-продукта и границ между ними. Это карта того, *как устроен продукт*,
> на которую затем опираются спецификация схемы, runtime-контракт, player-experience и roadmap.
> **Решения**, на которых стоит эта архитектура, зафиксированы в `NARRATIVE_DECISIONS_v1.md` (приоритетный документ).
>
> **Статус:** ЧЕРНОВИК v1 (структурный каркас)
> **Дата:** 2026-06-30
> **Narrative baseline:** `5571bd2505715b8f19b092ad1762b8d32449c360`
> **Базовое решение (N0):** JSON-first — `SCENARIO_*.json` источник правды; RenPy — primary MVP runtime, но не source of truth.

---

## 0. Обзор: слои и поток данных

Продукт = **гибрид**: играбельный RenPy-слой + будущий LLM director/character-слой, связанные общим источником правды (JSON).

**Слои (сверху вниз — от источника к игроку):**

1. **JSON Source Model** — единственный источник правды о сцене.
2. **Story Runtime Contract** — как сцена/choices/flags/state/branches исполняются.
3. **Renderer / Exporter Layer** — как JSON превращается в RenPy/preview.
4. **RenPy Playable Runtime** — primary MVP runtime, где живёт игра.
5. **LLM Director / Character Layer** — будущий режиссёрский и персонажный режим.
6. **Validation / Authoring Layer** — безопасное редактирование без поломки branches/flags.
7. **Player Experience Layer** — что видит игрок: режимы чтения/мыслей/POV.
8. **Framework Boundary** — Voyage Framework контролирует workflow/guardrails, но не является story runtime.

**Целевой поток данных (JSON-first):**

```text
                         ┌─────────────────────────────┐
   (6) Validation /      │   (1) JSON SOURCE MODEL      │
   Authoring  ◀────────▶ │   scenarios/SCENARIO_*.json │ ◀── (5) LLM Director
   schema lint, flag      │   = единственный source of  │     генерит → сохраняет
   graph, safe edit       │       truth о сцене          │     в JSON по схеме
                         └──────────────┬──────────────┘
                                        │ читается контрактом
                         ┌──────────────▼──────────────┐
                         │  (2) STORY RUNTIME CONTRACT │
                         │  flags/state/branches/save  │
                         └──────────────┬──────────────┘
                                        │ материализуется
                         ┌──────────────▼──────────────┐
                         │  (3) RENDERER / EXPORTER     │
                         │  JSON → RenPy / preview      │
                         └──────────────┬──────────────┘
                                        │ запускает
                         ┌──────────────▼──────────────┐
                         │  (4) RENPY PLAYABLE RUNTIME  │ ──▶ (7) Player Experience
                         │  novel/game/*.rpy            │     режимы чтения/POV/мысли
                         └─────────────────────────────┘

   (8) Framework Boundary: оборачивает весь dev-процесс (workflow/guardrails/audit),
       но НЕ входит в runtime-поток выше.
```

**Текущий поток данных (фактический, переходный):**

```text
SCENARIO_*.json (SC_019–027)  ──X──▶  RenPy (не подключены, source-only)
SCENARIO_*.json (SC_003–018)  ──ручной перенос──▶  novel/game/script.rpy (playable)
exporter.py                    ──▶  reports/renpy/*.rpy (skeletal preview, gitignored)
```

Главный технический факт сегодня: **live RenPy не грузит JSON как игровые сцены.** Играбельно только то, что вручную перенесено в `script.rpy`. Архитектура ниже описывает, как закрыть этот разрыв.

---

## 1. JSON Source Model — источник правды

**Ответственность.** Хранить полное, структурированное описание сцены: метаданные, упорядоченные beats (speech/action/thought), POV, choices, branches, flags/effects, safety/content-метаданные, visual-хуки.

**Owns.** `scenarios/SCENARIO_*.json` и модульные папки (`sauna_extended`, `sportcomplex_triad`, `promenade`), `SCENARIO_LIBRARY.json`, `SCENARIO_MATRIX.json`.

**Inputs.** Авторская работа человека; сохранённый результат LLM director-сессии (§5).
**Outputs.** Канонический JSON, который читают слои 2–6.

**Boundaries.** Это **единственный** source of truth. Ни RenPy, ни LLM-чат не являются источником правды, пока результат не сохранён сюда по схеме.

**Current state.** Лёгкая монолитная модель: метаданные + один `choice_points` + branches с прозой в `action`/`kira_reaction`/`yakov_reaction`/`sergey_reaction`. Мысль/действие/речь **слиты**. Нет JSON-схемы (в `schemas/` только persona-схема).

**Target.** `SCENARIO_SCHEMA_V2`: ordered beats c полями `speaker / speech / action / thought / inner_monologue / pov / thought_visibility / emotion`, нормализованные choices/branches, `flags`/`effects`, `safety`. Детали — в `SCENARIO_SCHEMA_V2_SPEC.md`.

---

## 2. Story Runtime Contract — контракт исполнения

**Ответственность.** Определить, как сцена реально «играется»: что значит scene complete, какие flags требуются/ставятся, что происходит после branch, как выбирается следующая сцена, как сохраняется состояние игрока.

**Owns.** Контракт (документ + в будущем реализация): flag engine, branch resolver, continuity-граф, player_state, save/load.

**Inputs.** JSON Source Model (§1) + player_state.
**Outputs.** Разрешённый порядок сцен, актуальное состояние флагов/персонажей, точки сохранения.

**Boundaries.** Контракт **не зависит от RenPy**: один и тот же контракт обслуживает и RenPy-рендер, и preview, и (в будущем) другой renderer. RenPy его *исполняет*, но не *определяет*.

**Current state.** Фактически отсутствует. Флаги **декларативны** (`flags_required`/`flags_set` записаны, но не исполняются). Нет state-машины, continuity-графа, save/load для JSON-сцен. `runtime_loader.py` грузит **персонажей**, не сценарии.

**Target.** `STORY_RUNTIME_CONTRACT.md`: executable flags, prerequisites, branch outcomes, scene completion, player_state, доступность следующей сцены.

---

## 3. Renderer / Exporter Layer — JSON → playable/preview

**Ответственность.** Превращать канонический JSON (через контракт §2) в исполняемое представление: RenPy-сцены и/или text/HTML preview — **без ручного авторинга каждой сцены**.

**Owns.** `tools/vne_to_renpy/exporter.py` (JSON → skeletal `.rpy` → `reports/renpy/`, gitignored, не трогает `novel/game/`), будущий полноценный generator/adapter.

**Inputs.** JSON Source Model + runtime-контракт.
**Outputs.** `.rpy`-сцены (для §4) и/или preview-артефакты (для ревью/QA).

**Boundaries.** Renderer **детерминирован**: одна и та же JSON-сцена → один и тот же вывод. Не добавляет смысла, которого нет в источнике (никакой «дорисовки» сюжета — это задача LLM-слоя §5 на этапе авторинга, не рендера).

**Current state.** Exporter существует и работает на skeletal-уровне (`SC_003–013` preview, smoke-check `check_renpy_exporter.py` 11/11 PASS). Это **зерно** будущего пути «JSON → playable». Он эмитит narrator-превью, не production-сцены.

### 3.1 Hybrid JSON path (N5F decision)

Принят гибридный путь от JSON к RenPy:

1. **Generate-ahead `.rpy` — канонический MVP/release playable путь.**
   - `tools/renpy_v2_playable_exporter.py` генерирует `novel/game/scenes_v2_generated.rpy` из V2-JSON.
   - Генерация детерминирована; артефакт проходит static RenPy validation.
   - Сгенерированный `.rpy` — **derived artifact**, не источник правды; ручные правки в нём теряются при регенерации.
   - N5A–N5D доказали вертикальный срез для SC_017; этот путь сохраняется.

2. **Live/dev JSON loader — отложенная dev/edit инфраструктура.**
   - Будущий RenPy/Python loader будет читать JSON прямо в runtime для Dev-edit, hot-reload и pause/resume.
   - **Не реализован** на момент N5F; требуется scoped контракт до начала Dev-edit (см. `STORY_RUNTIME_CONTRACT.md` §1.1).
   - Не заменяет generate-ahead путь в релизе до готовности.

3. **Инвариант source of truth.**
   - В обоих путях канонический источник — `scenarios/SCENARIO_*.v2.json`.
   - Renderer детерминирован и не добавляет смысла, которого нет в источнике.

**Target.** Расширить exporter из skeletal-preview в production-generator под `SCENARIO_SCHEMA_V2`: beats → реплики/действия/мысли/POV, choices → RenPy `menu`, flags → вызовы runtime-контракта.

---

## 4. RenPy Playable Runtime — игра

**Ответственность.** Запускать игру для игрока: сцены, выборы, персонажи, визуал, последствия. Primary MVP runtime.

**Owns.** `novel/game/{script,screens,definitions,options}.rpy`, `novel/README.md` (Runbook), RenPy SDK 8.5.3 (локально у разработчика).

**Inputs.** Сгенерированные/подготовленные `.rpy` из §3 (целевое) ИЛИ ручной `script.rpy` (переходное).
**Outputs.** Играбельный опыт; player-choices и сохранения (которые должны питать §2).

**Boundaries.** RenPy = **renderer/target и playable runtime**, но **не источник правды** (§1) и **не определяет** контракт исполнения (§2). Ручной `script.rpy` — временный прототип переходного периода.

**Current state.** `SC_003–SC_018` playable (113 labels) через **ручной** `script.rpy`. `SC_019–SC_027` не отображаются. Choices исполняемы только в hand-authored сценах. N5D добавил dev/test entry для сгенерированного SC_017 V2 (`scenes_v2_generated.rpy`); он не заменяет hand-authored SC_017. Файлы playable-диапазона не менять без отдельного RN-задания.

**Target.** RenPy перестаёт быть «ручным дублёром JSON» и становится генерируемым/подготавливаемым из источника (§3). В будущем — точка интеграции LLM-диалогов (§5) внутри игры.

---

## 5. LLM Director / Character Layer — режиссёрский и персонажный режим

**Ответственность.** Авторский/режиссёрский инструмент: беседы с персонажами, тестирование поведения, генерация вариантов сцены и диалогов, стоп-кадры для визуала, развитие сюжета. Результат **сохраняется как структурированная сцена** (§1).

**Owns.** `personas/` (модульные + монолиты), R1–R8 pipeline, `knowledge_base/`, PRELOAD/ФМДР-формат, `runtime_loader.py` (загрузка персон).

**Inputs.** Персона-модули + контекст текущей истории/сцены.
**Outputs.** Черновой материал → после сохранения по схеме становится JSON Source (§1).

**Boundaries.** LLM-слой **не является источником правды** до сохранения. Его фильтры помогают генерации, но **не заменяют** runtime-гарантии (сохранение/воспроизведение/проверку). На старте — рядом с игрой (authoring/director mode); цель — встроить диалоги с персонажами в RenPy (§4).

**Current state.** Богатая persona-система и pipeline существуют и работают как отдельная LLM-система. Не подключены к JSON-сценам как единый продукт.

**Target.** Мост «LLM-сессия → JSON-сцена по `SCENARIO_SCHEMA_V2`»: что нагенерировано в чате, нормализуется в beats/choices/flags и сохраняется в источник.

---

## 6. Validation / Authoring Layer — безопасное редактирование

**Ответственность.** Гарантировать, что сцену можно редактировать, не ломая branches/flags/continuity; проверять схему, баланс di[alogue/action/thought], tone/risk, последствия веток; строить diff source→preview.

**Owns.** `tools/rn_workflow.py` (gates / validate / audit-source), `tools/vne_adapter.py` (обёртка voyage CLI), `scripts/python/check_renpy_exporter.py`, `scenarios/sauna_extended/scenario_validator.py`, будущие линтеры.

**Inputs.** JSON Source (§1) + схема (§1 target) + контракт (§2).
**Outputs.** PASS/FAIL отчёты, предупреждения, edit-safe гарантии.

**Boundaries.** Валидаторы **советуют и проверяют**, но не переписывают контент. Safety-scan — предупреждающая система (см. `RN-SAFETY-STYLE-1`): флагует для ревью, не цензурирует и не блокирует творческое планирование автоматически.

**Current state.** Есть `audit-source`, `validate`, exporter smoke-check, гейт `renpy_exporter` в `vne_adapter gates`. Нет: scenario JSON schema validation, flag graph lint, branch continuity audit, source→preview diff как единого pipeline.

**Target.** `safe editing pipeline`: schema validation → flag graph lint → branch continuity audit → dialogue/action/thought balance → tone/risk check → render preview diff → human approval gates.

---

## 7. Player Experience Layer — что видит игрок

**Ответственность.** Определить, как история подаётся игроку: видимость мыслей, POV, плотность выборов, тон, режимы чтения, последствия выборов.

**Owns.** UX-контракт (документ) + RenPy-экраны (`screens.rpy`) как точка показа.

**Inputs.** Сцена из runtime (§2) + player settings (§ ниже).
**Outputs.** То, что реально отображается: речь/действие/мысль/выбор, в нужном режиме.

**Целевые режимы чтения** (управляются `thought_visibility` и POV из схемы):
- **Classic VN** — речь + действия;
- **Psychological** — + внутренний монолог POV-персонажа;
- **Mind-reading** — видны скрытые мысли нескольких персонажей;
- **Director** — обсуждение сцены с персонажами/нейросетью (§5);
- **Hidden** — часть мыслей хранится, но не показывается;
- **Dev / in-place edit** — разработчик заходит в игру и редактирует текущий beat (`speech`/`action`/`thought`/`narration`) прямо на месте; в этом режиме видны и скрытые мысли.

**Dev / in-place edit mode (требование).** Разработчик может редактировать реплики/мысли/действия прямо во время игры. Ключевое правило: правка пишется **обратно в JSON-источник** (§1), а не патчит только экран; затем — быстрый чек (задеты только текстовые поля, не `flags`/`branches`/`pov`/`type`) и **hot-reload** сцены. Это требует: live-чтения JSON рантаймом (§2/§4), write-back + валидации (§6) и V2-схемы с раздельными beats (§1). Без live JSON-runtime «правка на месте» технически некуда писать → фича идёт отдельной фазой после него.

**Персонализация** (`player_profile`, настраивается пользователем): `preferred_pov`, `thought_visibility`, `drama_intensity`, `choice_density`, `content_boundaries`, `romance_focus`, `psychological_detail_level`.

**Boundaries.** Player Experience — это **режим отображения**, а не источник правды. Режимы возможны только потому, что схема (§1) разделяет thought/action/speech/pov. Реализация настроек — `DEFERRED` (не первая фаза), но схема обязана это поддерживать.

**Current state.** Отсутствует: нет player settings, pre-game questionnaire, режимов чтения/POV. RenPy показывает то, что захардкожено в сцене.

**Target.** `PLAYER_EXPERIENCE_SPEC.md`: режимы, POV-правила, choice density, settings-слой.

---

## 8. Framework Boundary — граница с Voyage Framework

**Ответственность.** Voyage Framework управляет **процессом разработки** Narrative: guardrails, validation-workflow, handoff, source-only loops, audit, automation, CLI.

**Owns.** `voyage` CLI (установлен отдельно), `.voyage/` (project.yaml, roles.yaml, task_templates), обёртка `tools/vne_adapter.py`, интеграция описана в `FRAMEWORK_VNE_INTEGRATION.md`.

**Boundaries (жёстко).**
- Framework **не** является и **не** становится story runtime (§2/§4).
- Narrative **не** изобретает собственную workflow-automation, если это задача Framework.
- Формула: **Voyage контролирует разработку Narrative, но не заменяет Narrative runtime.**

**Current state.** Граница частично описана (`FRAMEWORK_VNE_INTEGRATION.md`, `.voyage/`, `vne_adapter.py`). Закреплена решением в `NARRATIVE_DECISIONS_v1.md` §8.

---

## Матрица «кто чем владеет»

| Слой | Source of truth? | Исполняет? | Артефакты | Статус |
|---|---|---|---|---|
| 1 JSON Source | **ДА** | — | `scenarios/*.json` | есть, схема нужна |
| 2 Runtime Contract | нет | определяет правила | (док + будущая реализация) | отсутствует |
| 3 Renderer/Exporter | нет | материализует | `tools/vne_to_renpy/exporter.py` | skeletal, расширить |
| 4 RenPy Runtime | нет | играет | `novel/game/*.rpy` | playable SC_003–018 (ручной) |
| 5 LLM Director | нет (до сохранения) | генерирует | `personas/`, R1–R8 | есть как отд. система |
| 6 Validation/Authoring | нет | проверяет | `rn_workflow.py`, `vne_adapter.py` | частично |
| 7 Player Experience | нет | показывает | `screens.rpy` + UX-контракт | отсутствует |
| 8 Framework Boundary | нет | контролирует процесс | `.voyage/`, `vne_adapter.py` | описано |

---

## Открытые вопросы, вынесенные в следующие документы

- **Точные поля и enum'ы схемы**, реестр персонажей (id/display_name/state/relationship) → `SCENARIO_SCHEMA_V2_SPEC.md`.
- **Семантика исполнения**: scene complete, flag-эффекты, branch-merge, continuity, save/load → `STORY_RUNTIME_CONTRACT.md`.
- **Режимы чтения, POV-правила, settings, questionnaire** → `PLAYER_EXPERIENCE_SPEC.md`.
- **Порядок реализации (фазы N0–N6)** → `NARRATIVE_ROADMAP.md` (последним).

---

## Принципы, которые архитектура фиксирует

1. **Один источник правды** (JSON). Всё остальное — производное.
2. **Runtime-контракт отделён от renderer'а.** RenPy исполняет, не определяет.
3. **Renderer детерминирован.** Смысл добавляется на авторинге (LLM §5), не на рендере.
4. **LLM — авторский инструмент, не источник правды.** Результат живёт только после сохранения по схеме.
5. **Режимы игрока возможны только при структурном разделении** thought/action/speech/pov.
6. **Framework контролирует процесс, не игру.**
7. **Переходный гибрид допустим:** SC_003–018 playable (ручной), SC_019–027 source-only, новое — JSON-first.

> Коммит этого документа — через стандартный Narrative workflow (Claude Code), отдельным небольшим commit.
