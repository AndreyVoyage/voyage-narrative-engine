# NARRATIVE ROADMAP — Voyage Narrative Engine (VNE)

> **Назначение.** План реализации Narrative-продукта по фазам N0–N6.
> Roadmap **выводится** из уже зафиксированных документов и **не создаёт новых архитектурных решений**.
> Опора: `NARRATIVE_DECISIONS_v1.md`, `NARRATIVE_ARCHITECTURE.md`, `SCENARIO_SCHEMA_V2_SPEC.md`,
> `STORY_RUNTIME_CONTRACT.md`, `PLAYER_EXPERIENCE_SPEC.md`.
>
> **Статус:** ЧЕРНОВИК v1 (план)
> **Дата:** 2026-06-30
> **Narrative baseline:** `5571bd2505715b8f19b092ad1762b8d32449c360`
>
> **Этот документ НЕ запускает реализацию и НЕ создаёт SC_028. Это документ планирования.**

---

## 1. Назначение roadmap

Дать порядок реализации: какие фазы, в какой последовательности, с какими критериями готовности (Definition of Done), зависимостями и рисками. Каждая фаза опирается на предыдущую и не вводит решений, которых нет в документах-источниках.

**Сквозная дисциплина (для всех фаз):**
- **Никаких регрессий.** Playable `SC_003–SC_018` остаются играбельными; `main` стабилен. Рефакторинг не ломает существующее.
- **Фаза закрыта только по Definition of Done**, не «по ощущению».
- **JSON — единственный источник правды** на всех фазах (решение N0).
- Все изменения repo — через Voyage workflow (Claude Code): ветки, гейты, ревью, без коммитов в `main` без аппрува.

---

## 2. Current baseline / что есть сейчас

```text
HEAD == origin/main == 10eaed300cf8f932086ce3013b4a399228d0d418  (HISTORICAL snapshot на момент написания; текущий reconciliation-снимок — см. §13)
SC_003–SC_018: playable через ручной novel/game/script.rpy (113 labels)
SC_019–SC_027: source-only JSON (в игре не отображаются)
Live JSON-runtime: НЕТ (RenPy не грузит JSON как сцены)
Scenario JSON schema v2: ДА (schemas/scenario_schema_v2.json + tools/narrative_schema_v2.py)
N5A — JSON→playable RenPy bridge proof: COMPLETE
  - tools/renpy_v2_playable_exporter.py
  - novel/game/scenes_v2_generated.rpy из SC_017 V2 JSON
  - labels sc_017_v2_*; script.rpy не тронут
N5B — static RenPy generated-scene validation: COMPLETE
  - tools/renpy_static_validator.py + validate-renpy-v2-generated
  - SDK lint только на temp copy; repo cache/log не создаются
N5C — roadmap reconciliation: COMPLETE
N5D — reachable opt-in launcher: COMPLETE
  - menu item "SC_017 — V2 JSON-generated proof (dev/test)" → jump sc_017_v2_start
  - script.rpy changed only additively; old SC_017 path preserved
N5F — Hybrid JSON path design: COMPLETE
  - generate-ahead .rpy remains canonical MVP/release playable path
  - live JSON loading scoped as future dev/edit/hot-reload foundation
  - JSON remains source of truth; generated .rpy is deterministic derived artifact
N5G — Live/Dev JSON Contract: COMPLETE as docs/contract
  - dev-only live JSON path defined
  - full live/dev runtime NOT implemented
N5H — Mock Live/Dev JSON Loader: COMPLETE as external read-only tooling
  - tools/live_dev_json_loader.py + tests/test_live_dev_json_loader.py
  - wrapper commands: live-dev-inspect, live-dev-reload-check
  - address map: scene_id → choice_point.id → branch.id → beat_id
  - reload safety: SAFE_TEXT_ONLY / UNSAFE_STRUCTURAL
  - does NOT implement RenPy live JSON loader, write-back, hot-reload, or Dev-edit
  - release generate-ahead .rpy path unaffected
N5J — Generated `.rpy` Freshness Validator: COMPLETE
  - tools/renpy_static_validator.py
  - tests/test_renpy_static_validator.py
  - validate-renpy-v2-generated now checks generated `.rpy` header source path + SHA256 against current V2 JSON SHA256
  - mismatch / missing source path / missing SHA256 / missing source file fail cleanly with no traceback
  - existing structural checks and SDK lint behavior are preserved
  - validator does NOT regenerate `.rpy`
  - committed `novel/game/scenes_v2_generated.rpy` and `scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json` were not modified by N5J
N5A artifact status: build-safe; reachable from normal start via dev/test opt-in launcher
  (does NOT replace hand-authored SC_017 path)
N5 (Dev / in-place edit): НЕ реализован
N6 (Director / LLM / Character Aside / Voice): НЕ реализован; планирование в NARRATIVE_FUTURE_TRACKS_v1.md
Persona/LLM-система: есть как отдельная система (personas/, R1–R8), не интегрирована в narrative runtime
Narrative docs: зафиксированы (N0); N4D future tracks перенесён в docs/narrative/
```

---

## 3. Non-goals / запрещено сейчас

```text
- НЕ создавать SC_028.
- НЕ шлифовать текст SC_020–SC_027 до schema/runtime.
- НЕ делать script.rpy источником правды (он временный playable-прототип).
- НЕ превращать Voyage Framework в story runtime.
- НЕ запускать implementation из этого документа (это план).
- НЕ массово мигрировать SC_003–027 до готового валидатора (см. §6).
```

---

## 4–5. Фазы N0–N6

Формат каждой фазы: **Goal / Why / Tasks / Outputs / Definition of Done / Risks / Blocked-by / Unlocks.**

---

### N0 — Documentation freeze / decisions baseline

- **Goal.** Зафиксировать и закоммитить канонический набор Narrative-документов.
- **Why.** Все последующие фазы опираются на них; без freeze решения будут «плыть».
- **Tasks.**
  - Review 6 документов (DECISIONS, ARCHITECTURE, SCHEMA_V2, RUNTIME_CONTRACT, PLAYER_EXPERIENCE, ROADMAP).
  - Commit через Claude Code серией маленьких коммитов (§9).
- **Outputs.** Закоммиченные `docs/narrative/*.md`.
- **Definition of Done.** Все 6 документов в `main` (через обычный workflow), working tree clean, ничего не сломано.
- **Risks.** Накопление untracked-файлов; расхождение документов между собой.
- **Blocked-by.** —
- **Unlocks.** N1.

---

### N1 — Schema V2 foundation

- **Goal.** Превратить `SCENARIO_SCHEMA_V2_SPEC.md` в исполнимый контракт: формальная JSON Schema + валидатор + один мигрированный образец.
- **Why.** Без формальной схемы нельзя ни валидировать, ни безопасно редактировать, ни рендерить.
- **Tasks.**
  - Создать `schemas/scenario_schema_v2.json` (JSON Schema по спецификации).
  - Расширить валидатор (в `tools/rn_workflow.py` или новый `tools/narrative/`) под схему: проверка beats, типов, обязательных каналов, enum'ов.
  - Мигрировать **одну** сцену как эталон — **SC_017** → `SCENARIO_017_*.v2.json` (faithful split, без выдумывания мыслей).
  - Flag graph-lint (предупреждение о флагах, которые нигде не required/не потребляются).
- **Outputs.** `scenario_schema_v2.json`, валидатор, `SC_017` в V2, отчёт линта.
- **Definition of Done.** Валидатор PASS на SC_017 V2; lint работает; mass-migration НЕ выполнена.
- **Risks.** Соблазн мигрировать всё сразу; рассинхрон схемы и спеки.
- **Blocked-by.** N0.
- **Unlocks.** N2, N3.

---

### N2 — Runtime foundation / live JSON read

- **Goal.** Реализовать `STORY_RUNTIME_CONTRACT.md`: live-чтение JSON, player_state, исполнение flags/effects, доступность сцен, базовый save/load.
- **Why.** Это переход от «архива JSON» к исполняемой истории; без него нет ни UX-режимов, ни dev-edit.
- **Tasks.**
  - Live JSON loader сцены (по `id`), валидация на входе.
  - `player_state` (completed_scenes, flags, character_states, relationships, history).
  - Детерминированное идемпотентное применение `effects` (cleared→set→levels→relationships).
  - Разрешение branches; доступность сцены = prerequisites ⊆ completed ∧ flags_required ⊆ flags.
  - Базовый save/load (прогресс, не текст).
- **Outputs.** Runtime-модуль (Python; целевая площадка — внутри RenPy или отдельный preview-runtime — решается здесь).
- **Definition of Done.** SC_017 (V2) проигрывается из JSON через runtime: beats по порядку, флаги применяются, completion ставится, сейв/лоад восстанавливает прогресс. SC_003–018 не сломаны.
- **Risks.** Смешать runtime с renderer'ом; нарушить инварианты контракта; регресс playable-диапазона.
- **Blocked-by.** N1.
- **Unlocks.** N3, N4, N5.

---

### N3 — Renderer / exporter to RenPy preview/playable

- **Goal.** Детерминированно превращать V2-JSON в RenPy (через runtime N2) — без ручного дублирования в `script.rpy`.
- **Why.** Закрывает корневой рассинхрон JSON ↔ script.rpy; делает RenPy генерируемым таргетом.
- **Tasks.**
  - Расширить `tools/vne_to_renpy/exporter.py` из skeletal-preview в production-renderer под V2: beats → реплики/действия/мысли/POV; choices → RenPy `menu`; effects → вызовы runtime.
  - Pipeline «JSON → playable» для новой сцены (на SC_017) без ручного авторинга.
  - Сохранить gitignored preview-путь (`reports/renpy/`) для diff/QA.
- **Outputs.** Production-renderer; SC_017, играемый из JSON.
- **Definition of Done.** SC_017 играется в RenPy, сгенерированный из V2-JSON; вывод детерминирован (одинаковый JSON → одинаковый `.rpy`); ручного дублирования нет.
- **Risks.** Renderer «дорисовывает» смысл (запрещено — смысл на авторинге); расхождение с ручными SC_003–018.
- **Blocked-by.** N1, N2.
- **Unlocks.** N4; постепенная миграция SC_003–018 на генерируемый путь (см. §6).

---

### N4 — Player Experience MVP

- **Goal.** Реализовать MVP-режимы из `PLAYER_EXPERIENCE_SPEC.md`.
- **Why.** Чтобы история стала продуктом для игрока, а не только технически исполнялась.
- **Tasks.**
  - Classic VN режим (narration + speech + action).
  - Базовый Psychological-показ (revealed-мысли POV).
  - Безопасные дефолты настроек (без settings UI и без questionnaire).
  - Developer inspector **read-only** (beat_id, flags, current branch).
- **Outputs.** Играбельный MVP с режимами Classic/Psychological + инспектор.
- **Definition of Done.** Игрок проходит SC_017 в Classic и Psychological; видимость мыслей соответствует `thought_visibility`; inspector показывает структуру, ничего не редактируя.
- **Risks.** Показ «из текста», а не из полей; протечка скрытых мыслей в Classic.
- **Blocked-by.** N2 (read), желательно N3 (рендер).
- **Unlocks.** N5.

---

### N5A — JSON→playable RenPy bridge proof

- **Goal.** Доказать, что V2-JSON можно детерминированно превратить в играбельный RenPy без ручного дублирования.
- **Status.** COMPLETE.
- **Outputs.** `tools/renpy_v2_playable_exporter.py`, `novel/game/scenes_v2_generated.rpy` (из `scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json`).
- **Facts.** Generated labels `sc_017_v2_*`; `script.rpy` не тронут; эффекты исполняемые (`v2_flags`, `v2_completed_scenes`, `v2_levels`, `v2_relationships`).
- **Limitation.** Generated scene does not replace hand-authored `sc_017_start`; normal selector still defaults to `SC_017 — Сергей пишет снова`.
- **Definition of Done.** `renpy-playable-v2` генерирует `scenes_v2_generated.rpy`, который проходит SDK lint на temp copy.
- **Risks.** Перепутать proof artifact с reachable gameplay.
- **Blocked-by.** N1, N3.
- **Unlocks.** N5B, N5D.

### N5B — Static RenPy generated-scene validation

- **Goal.** Убедиться, что generated `.rpy` не ломает RenPy build, не трогая ручные файлы, и подготовить безопасное планирование reachable launcher.
- **Status.** COMPLETE.
- **Outputs.** `tools/renpy_static_validator.py`, workflow command `validate-renpy-v2-generated`.
- **Facts.** Структурная проверка + SDK lint на temp copy; repo cache/log/.rpyc не создаются; `script.rpy`, `definitions.rpy`, `options.rpy` и `scenes_v2_generated.rpy` не модифицируются при проверке.
- **Definition of Done.** Валидатор PASS на `novel/game/scenes_v2_generated.rpy`; рабочее дерево остаётся clean.
- **Risks.** SDK lint мутирует repo, если запускать напрямую на `novel/`.
- **Blocked-by.** N5A.
- **Unlocks.** N5D.

### N5D — Reachable opt-in launcher

- **Goal.** Сделать сгенерированную V2-сцену достижимой из игры через явный dev/test пункт, не заменяя ручной путь.
- **Status.** COMPLETE.
- **Outputs.** `novel/game/script.rpy` — добавлен пункт меню `SC_017 — V2 JSON-generated proof (dev/test)` → `jump sc_017_v2_start`.
- **Facts.** Изменение только аддитивное; hand-authored `sc_017_start` и selector без изменений; `sc_017_v2_start` остаётся определён только в `scenes_v2_generated.rpy`.
- **Limitation.** Это dev/test entry, не production player-facing финальный поток; live JSON loading не реализован.
- **Definition of Done.** Меню в `label start:` содержит dev/test пункт, который прыгает на `sc_017_v2_start`; валидаторы PASS.
- **Risks.** Перепутать dev/test entry с основным маршрутом.
- **Blocked-by.** N5A, N5B.
- **Unlocks.** N5F (hybrid JSON path design), безопасное тестирование V2 playable proof без live runtime.

### N5F — Hybrid JSON path design

- **Goal.** Зафиксировать архитектурное решение: generate-ahead `.rpy` остаётся каноническим MVP/release playable путём, а live JSON loading — будущей/ограниченной dev/edit/hot-reload инфраструктурой.
- **Status.** COMPLETE.
- **Outputs.** Документ `docs/narrative/N5F_HYBRID_JSON_PATH_DECISION.md` и указатели в `NARRATIVE_ROADMAP.md`, `STORY_RUNTIME_CONTRACT.md`, `NARRATIVE_ARCHITECTURE.md`.
- **Facts.**
  - `scenarios/SCENARIO_*.v2.json` остаётся единственным источником правды.
  - Протестированная вертикаль N5A–N5D сохраняется: `SC_017.v2.json -> validate-v2 -> story runtime -> preview/PX -> renpy-playable-v2 -> scenes_v2_generated.rpy -> reachable dev/test launcher -> static RenPy validation`.
  - Сгенерированный `scenes_v2_generated.rpy` — детерминированный derived artifact; ручные правки в нём не сохраняются.
  - Live JSON loading внутри RenPy **не реализован**.
- **Limitation.** Это docs-only решение; реализация live/dev JSON loader и Dev-edit остаётся на будущие фазы.
- **Definition of Done.** Во всех трёх документах зафиксированы: Hybrid JSON path, source of truth, generate-ahead MVP path, scoped live/dev JSON path, не-реализация live loader/Dev-edit/hot-reload.
- **Risks.** Перепутать generate-ahead proof с production player-facing финальным потоком; начать Dev-edit до live/dev JSON контракта.
- **Blocked-by.** N5A, N5B, N5D.
- **Unlocks.** N5G (live/dev JSON contract), безопасное планирование Dev-edit.

### N5G — Live/Dev JSON Contract

- **Goal.** Описать scoped контракт для dev-only live JSON пути, необходимый перед Dev-edit.
- **Status.** COMPLETE as docs/contract.
- **Outputs.** `docs/narrative/N5G_LIVE_DEV_JSON_CONTRACT.md` и указатели в `NARRATIVE_ROADMAP.md`, `STORY_RUNTIME_CONTRACT.md`.
- **Facts.**
  - Контракт определяет read path, validation boundary, runtime state mapping (`completed_scenes`/`flags`/`character_states`/`relationships`/`settings`/`history` → `v2_*`), beat/branch mapping, write-back boundary, hot-reload boundary и failure behavior.
  - Live JSON loading внутри RenPy **не реализован**.
  - Dev-edit / hot-reload / write-back **не реализованы**.
- **Limitation.** Это docs-only контракт; реализация loader и Dev-edit остаётся на будущие фазы.
- **Definition of Done.** Контрактный документ создан и связан с roadmap/runtime contract; все границы зафиксированы; валидаторы PASS.
- **Risks.** Перепутать контракт с реализацией; ослабить validation boundary или write-back guard.
- **Blocked-by.** N5F.
- **Unlocks.** N5H (mock/dev JSON loader tooling); безопасное проектирование/прототипирование live/dev JSON loader; будущий N5-Dev только после реализации контракта и runtime-основы.

### N5H — Mock Live/Dev JSON Loader

- **Goal.** Реализовать внешний read-only mock/dev loader, который закрывает часть N5G-контракта на уровне Python-tooling, без интеграции в RenPy runtime.
- **Status.** COMPLETE.
- **Outputs.** `tools/live_dev_json_loader.py`, `tests/test_live_dev_json_loader.py`, команды `rn_workflow.py live-dev-inspect` и `live-dev-reload-check`.
- **Facts.**
  - Tool читает и валидирует `scenarios/SCENARIO_*.v2.json` через существующий `narrative_schema_v2.py`.
  - Строит адресную карту: `scene_id` → `choice_point.id` → `branch.id` → `beat_id`.
  - Выводит safe editable fields (`narration`, `speech`, `action`, `thought`, `emotion`) и forbidden/high-risk fields (`beat_id`, `type`, `speaker`, `pov`, `thought_visibility`, `option_text`, `effects`, `next`, `prerequisites`, `flags_required`, `completion_flag`, branch structure, choice point ids, relationship/effect mutations).
  - Выводит state mapping (`completed_scenes`/`flags`/`character_states`/`relationships`/`settings`/`history` → `v2_*`).
  - Классифицирует reload safety: `SAFE_TEXT_ONLY` / `UNSAFE_STRUCTURAL`.
  - `UNSAFE_STRUCTURAL` — это классификация изменений, а не ошибка команды; для валидного V2 JSON команда возвращает exit 0.
  - Invalid/missing/non-v2 inputs fail cleanly с exit 1 и без traceback.
- **Limitation.** Это read-only tooling; live JSON loading внутри RenPy, write-back, hot-reload и Dev-edit **не реализованы**. Release path остаётся generate-ahead `.rpy`.
- **Definition of Done.** Инструмент и тесты в `main`; все gates PASS; working tree clean.
- **Risks.** Перепутать mock/dev loader с полноценным RenPy live loader; начать Dev-edit до готовой runtime-основы.
- **Blocked-by.** N5G.
- **Unlocks.** Безопасное планирование full live/dev JSON runtime / Dev-edit.

### N5J — Generated `.rpy` Freshness Validator

- **Goal.** Ensure the committed generated `.rpy` is not stale relative to its source V2 JSON.
- **Status.** COMPLETE.
- **Outputs.** Freshness validation integrated into `tools/renpy_static_validator.py`; tests in `tests/test_renpy_static_validator.py`; enforced by `validate-renpy-v2-generated`.
- **Facts.**
  - The validator parses `# source:` and `# source SHA256:` lines from the generated `.rpy` header.
  - The source path is resolved relative to the repo root; absolute paths that escape the repo are rejected.
  - The validator computes the current SHA256 of the source V2 JSON and compares it with the header hash.
  - Matching hash passes; mismatch is reported as a stale artifact.
  - Missing source path, missing SHA256, and missing source file all fail cleanly with a validation error and no traceback.
  - Existing structural checks, label-collision checks, content-snippet checks, executable-effect checks, and SDK lint behavior are preserved.
  - The validator does NOT regenerate `.rpy`; it only reports freshness status.
  - `novel/game/scenes_v2_generated.rpy` and `scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json` were not modified by N5J.
- **Limitation.** Regenerate-and-diff automation is NOT implemented. Default-variable cross-file collision checker is NOT implemented. RenPy live JSON loader, Dev-edit, write-back, and hot-reload remain NOT implemented.
- **Definition of Done.** `validate-renpy-v2-generated` fails if the generated `.rpy` is stale or its freshness header is missing/invalid; all existing validation gates still PASS.
- **Risks.** Treating a stale generated `.rpy` as up-to-date; manually patching generated `.rpy` instead of regenerating from JSON.
- **Blocked-by.** N5B.
- **Unlocks.** Safer generated-artifact workflow; future regenerate-and-diff automation planning.

### N5 — Dev / in-place edit mode

- **Goal.** Редактирование реплик/мыслей/действий прямо в игре с write-back в JSON.
- **Why.** Быстрый авторинг/правки без ручного редактирования файлов; ключевая продуктовая фича.
- **Tasks.**
  - In-game редактор текстовых полей текущего beat'а (`speech/action/thought/narration/emotion`).
  - Guard: только текстовые поля; структура (flags/branches/ids/pov/type/option_text/prerequisites/next/completion_flag) недоступна быстрому пути.
  - Write-back в JSON-источник → schema validation → hot-reload → resume по `beat_id`.
- **Outputs.** Dev in-place edit mode.
- **Definition of Done.** Правка мысли/реплики/действия в игре пишется в JSON, проходит валидацию, hot-reload продолжает с того же `beat_id`; структура не затрагивается; старые сейвы валидны.
- **Risks.** Случайная структурная правка через быстрый путь; запись мимо источника; рассинхрон позиции при reload (решается resume по `beat_id`, не по индексу).
- **Blocked-by.** N2 (live runtime + write-back), N4 (UI-основа), N5G (live/dev JSON contract implemented in code).
- **Unlocks.** N6 (удобный авторинг для Director-результатов).
- **Note.** N5A/N5B/N5D — необходимый bridge, но не замена live JSON runtime; N5-Dev не начинается до проектирования scoped live/dev JSON контракта.

---

### N6 — Director / LLM character layer integration

- **Goal.** Интегрировать LLM director/character слой: беседы с персонажами, генерация вариантов, стоп-кадры; результат нормализуется в V2.
- **Why.** Завершает гибрид: играбельный слой + режиссёрский/персонажный.
- **Tasks.**
  - Мост «LLM-сессия → нормализованная V2-сцена» (proza → beats/choices/flags).
  - Director mode рядом с игрой; в перспективе — диалоги с персонажами внутри RenPy.
  - Использование persona-системы (`personas/`, R1–R8) как character-источника.
- **Outputs.** Director-режим + сохранение результата как сцены.
- **Definition of Done.** Сгенерированный в LLM материал сохраняется как валидная V2-сцена и играется через runtime; LLM **не** является источником правды до сохранения.
- **Risks.** Сырая проза попадает в источник без нормализации; LLM-слой подменяет источник правды.
- **Blocked-by.** N1 (схема), N2 (runtime), N5 (удобный write-back).
- **Unlocks.** Полноценный гибридный продукт.

---

## 6. Migration strategy for SC_003–SC_027

- **Не** мигрировать массово до готового валидатора (конец N1).
- Порядок: SC_017 — эталон (N1). Затем — постепенно, по правилам §13 `SCENARIO_SCHEMA_V2_SPEC.md`, **малыми партиями** с валидацией.
- `SC_003–SC_018` (playable): мигрируются на V2 + генерируемый рендер (N3) **только** при гарантии «никаких регрессий»; до этого остаются на ручном `script.rpy`.
- `SC_019–SC_027` (source-only): мигрируются в V2 как данные; текстовое качество **не** трогаем до завершения схемы/рантайма.
- Каждая миграция: faithful split (без выдумывания мыслей) → валидатор PASS → diff-ревью.

---

## 7. MVP definition

```text
MVP =
  Schema V2 (formal + validator)          [N1]
+ Live JSON runtime + player_state + save  [N2]
+ Deterministic JSON→RenPy render          [N3]
+ Classic VN + basic Psychological + read-only inspector  [N4]
+ at least SC_017 fully JSON-driven playable
```

**Note on "SC_017 fully JSON-driven playable":** currently satisfied as a generated playable RenPy artifact from SC_017 V2 JSON (N5A) that passes static build validation (N5B) and is reachable from the normal start menu via an opt-in dev/test launcher (N5D). The artifact does not replace the hand-authored SC_017 path. N5F adopts a Hybrid JSON path: generate-ahead `.rpy` remains the canonical MVP/release playable path, while live JSON loading is scoped as a future dev/edit/hot-reload foundation.

Pre-game questionnaire, Mind-reading, full Director, in-RenPy LLM, settings UI, browser editor, full in-place editor — **не входят** в MVP.

---

## 8. Later / deferred features

```text
- Mind-reading mode
- Full Director mode + LLM inside RenPy
- Pre-game questionnaire
- Full in-place editor (beyond N5 text-edit)
- Settings UI
- Browser editor / preview
- Mass text-quality polish of SC_020–SC_027
- Character configurability by player
```

**Проработанные будущие идеи** зафиксированы в `NARRATIVE_FUTURE_TRACKS_v1.md`:
- **Character Aside** (non-canonical private chat + persistent aside memory) → N6;
- **Voice / Audio Layer** (canon voice assets + aside dynamic voice, `VoiceProvider`) → поздний Audio track / N6;
- **Story Setup** (pre-game route personalization) → отложено; направление истории идёт через in-scene branching.

---

## 9. Commit / workflow notes

- N0 коммитим **серией маленьких коммитов** (предпочтительно):
  ```text
  docs(narrative): add product decisions
  docs(narrative): define architecture and schema v2
  docs(narrative): define runtime and player experience
  docs(narrative): add narrative roadmap
  ```
  Минимальная альтернатива (если нужно одним): `docs(narrative): define JSON-first architecture roadmap`.
- Все коммиты — через Claude Code (Voyage workflow): ветка, гейты, ревью; без коммита в `main` без аппрува.
- Реализационные фазы (N1+) — отдельными задачами/ветками, каждая со своим Definition of Done и без регрессий playable-диапазона.

---

## Сводка зависимостей

```text
N0 ─▶ N1 ─▶ N2 ─▶ N3 ─▶ N4 ─▶ N5A ─▶ N5B ─▶ N5D ─▶ N5F ─▶ N5G ─▶ N5H ─▶ N5-Dev ─▶ N6
              │           ▲                                      │
              └──────────-┘  (N4 требует N2; лучше после N3)     └──── (N5H — read-only tooling; N5-Dev требует runtime-основу)
N5A/N5B/N5D — bridge track: JSON→playable proof + build-safety validation + reachable opt-in launcher.
N5F — Hybrid JSON path decision: generate-ahead MVP path + scoped live/dev JSON loader future foundation.
N5G — Live/Dev JSON Contract: dev-only loader contract before Dev-edit.
N5H — Mock Live/Dev JSON Loader: external read-only tooling implementing parts of the N5G contract.
N5-Dev (in-place edit) НЕВОЗМОЖЕН раньше N5G + runtime-основы; N5H не разблокирует Dev-edit.
Director (N6) требует схему (N1) + runtime (N2) + удобный write-back (N5-Dev).
Character Aside / Voice Layer — N6 / future tracks (см. NARRATIVE_FUTURE_TRACKS_v1.md).
```

---

## 10. N7 текущий статус (canonical closeout, 2026-07-20)

**N7 P1 (Persona Data Gateway): CLOSED.**

- **P1a-S1** — read-only domain core (только Kira, с тестами): **AUTHORIZED AND COMPLETE.**
- **P1b Option A** — multi-character expansion (все модульные персонажи): **AUTHORIZED AND COMPLETE.**
- **Nika manifest compatibility correction:** **AUTHORIZED AND COMPLETE.**
- **Persona Gateway verification:** 138 тестов PASS.

**N6 Character Aside:** CLOSED AND INTEGRATED в origin/main.

**Не авторизовано:**
- P2 (MCP adapter) — PLANNED, NOT AUTHORIZED.
- P3 (RenPy adapter) — NOT STARTED, NOT AUTHORIZED.
- N8 (Persona Voice Model) — FUTURE, NOT AUTHORIZED.

> Полный канонический closeout: `docs/narrative/N7_CANONICAL_STATUS_CLOSEOUT_v1.md`.
> Реализация P2, P3, N8 требует отдельной авторизации владельца.


> Коммит этого документа — через стандартный Narrative workflow (Claude Code).
> Это завершает набор N0-документов: DECISIONS, ARCHITECTURE, SCHEMA_V2, RUNTIME_CONTRACT, PLAYER_EXPERIENCE, ROADMAP.

---

## 11. SVA — Scenario Visual Authoring: reference conditioning + manual reference input (2026-08-28)

**Reference-conditioning foundation sequence (B4):**

| Milestone | Status |
|---|---|
| B4-RC2 — Generic `ReferenceBundle` | CLOSED |
| B4-RC3 — Conditioned Provider Attachment | CLOSED |
| B4-RC4 — Offline independent audit | NEXT |
| B4-RC5 — Corrected live multi-character retry | PLANNED |

**After the reference-conditioning foundation is proven:**

| Milestone | Status |
|---|---|
| SVA-MR1 — `MANUAL_SCENE_REFERENCE_INPUT_V0` | PLANNED / RATIFIED_REQUIREMENT |

- **Dependency:** generic multi-character reference conditioning foundation (B4-RC2 → B4-RC5).
- **SVA-MR1 does NOT block B4-RC4/RC5.** RC4/RC5 proceed independently of SVA-MR1.
- **Owner decision:** `OD-SVA-MR-01 = A` (Manual Scene Reference Input is required) — recorded in
  `NARRATIVE_DECISIONS_v1.md` §10.
- **Placement:** implementation only after the reference-conditioning foundation is proven; not before.

---

## 12. SVA — Reference Library + Controlled Import (2026-08-29)

**Reference Library + Controlled Import foundation sequence (SVA-RL):**

| Milestone | Status |
|---|---|
| SVA-RL1 — `VNE_REFERENCE_LIBRARY_V0` | IMPLEMENTED (v0) |
| SVA-RL2 — `CONTROLLED_REFERENCE_IMPORT_V0` | IMPLEMENTED (v0) |
| SVA-RBA — `REFERENCE_LIBRARY_TO_REFERENCE_BUNDLE_ADAPTER_V0` | IMPLEMENTED (v0) |

**These capabilities become the foundation for:**

| Milestone | Status |
|---|---|
| SVA-CAST1 — `SCENE_CAST_OVERRIDE_V0` | PLANNED (foundation: SVA-RL1/SVA-RL2) |
| SVA-RP1 — `REFERENCE_PACKAGE_PREVIEW_V0` | PLANNED (foundation: SVA-RL1/SVA-RL2) |
| SVA-MR1 — `MANUAL_SCENE_REFERENCE_INPUT_V0` | PLANNED / RATIFIED_REQUIREMENT (foundation: SVA-RL1/SVA-RL2) |

- **Owner decisions:** `OD-SVA-RL-01 = A` (VNE Reference Library), `OD-SVA-RL-02 = A` (Controlled Reference
  Import), `OD-SVA-RL-03 = A` (Explicit Reference Selection for Library Assets), and
  `OD-SVA-RBA-01..07 = A` (Reference Library → ReferenceBundle adapter) — recorded in
  `NARRATIVE_DECISIONS_v1.md` §11, §12, §13, §14.
- **Dependency sequence:** SVA-RL1 ✅ → SVA-RL2 ✅ → Reference Library → ReferenceBundle adapter ✅ → next authoring slices (SVA-CAST1 → SVA-RP1 → SVA-MR1).
- **Completed slice:** `REFERENCE_LIBRARY_TO_REFERENCE_BUNDLE_ADAPTER_V0` — imported Library references now connect into the existing ReferenceBundle/selection path (implemented and published v0). The next immediate test-oriented work may now use real controlled imports.
- **Existing foundation:** the generic `ReferenceBundle` (B4-RC2), conditioned provider attachment (B4-RC3), and
  explicit reference selection (B4-RC4S) are already available and are **referenced, not reimplemented**.
- **These documentation milestones do NOT block already completed B4 work.** B4-RC4/RC5 proceed independently.
- **External sources:** external repositories/folders (including `narrative-character-canon`) are **import sources
  only**; VNE owns imported copies and does not continuously interpret external governance/status/rules.
- **Non-goals (v0):** no automatic NCC mirroring/sync, no automatic copy of every file in a source tree, no VNE
  writes to the external source, no per-generation external governance parsing, no automatic use of every imported
  image, no second provider pipeline, no Character Canon mutation, no cloud asset management, no automatic AI
  ranking of all references, no bulk generation, no automatic retries.

**Future UI preflight impact.** The next UI/application integration preflight must locate integration seams for:

- Reference Library browser
- Controlled Import UI
- Create character/collection
- Scene Cast Override
- Reference selection
- Reference Package Preview
- Manual Scene References
- Generate

The preflight must **not** assume the Character Canon Bridge is the sole reference source.

---

## 13. Roadmap reconciliation — implemented Scenario foundation (2026-09-29)

> **Это документационная reconciliation, не новый roadmap и не redesign.**
> **Baseline для этой reconciliation:** `5f3aa0dd63a4653d7a45eb617b346235fa9f36f9` — снимок для
> синхронизации документации, **не** постоянный архитектурный идентификатор (не превращать moving
> main SHA в timeless product-архитектуру).
> Статусы сверены с кодом и тестами. Исторический roadmap (N0–N6, §2–§9) сохранён; фазы N5A–N5J
> описывают более ранний JSON→Ren'Py путь, который ниже помечен как historical/partially superseded.

### 13.1 Как читать эту reconciliation

Различаем четыре уровня, **не смешивая** их:

- **HISTORICAL ROADMAP** — фазы N0–N6 (§2–§9) и N5A–N5J: как путь планировался/фиксировался.
- **CURRENT IMPLEMENTED FOUNDATION** — что реально есть в коде/тестах (таблица 13.2).
- **CURRENT ACTIVE WORK** — что реализовано и является текущим путём (accepted-scene lifecycle,
  desktop editor, OrderedASS exporter).
- **FUTURE PLATFORM INTEGRATION** — что остаётся будущим и НЕ реализовано (§13.4).

### 13.2 Current implemented Scenario foundation (IMPLEMENTED, по коду и тестам)

| Область | Где | Статус |
|---|---|---|
| ASS v0 (`ass/0.1`) | `services/ass/` (`model.py`, `importer.py`, `hashing.py`) | `IMPLEMENTED` (historical accepted-scene snapshot; импорт из Scenario V2 JSON) |
| OrderedASS (`ass/0.2`) | `services/ass/ordered.py` | `IMPLEMENTED` (текущий канонический accepted-scene контракт) |
| Canonical ASS store | `services/ass/store.py` | `IMPLEMENTED` (immutable; атомарная hard-link публикация; SHA-256; no symlink) |
| SceneBody (authoring payload) | `services/scene_body/` | `IMPLEMENTED` (scene_body/1.0; model validity vs acceptance-completeness) |
| Draft → Validate → Accept lifecycle | `services/scene_draft/` (`compiler.py`, `store.py`) | `IMPLEMENTED` (DRAFT → validate → ACCEPT → OrderedASS; one-time; immutable accepted version) |
| Location Canon | `services/location_canon/` | `IMPLEMENTED` (read-only, неизменяемая идентичность локации) |
| Character Canon read bridge | `services/character_canon_bridge/` | `IMPLEMENTED` (read-only snapshot + status; production gate = `APPROVED_AS_CANON`) |
| Scene Interpretation | `services/scene_interpretation/` | `IMPLEMENTED` (immutable artifact; якоря ASS/Location/Character; production_eligible) |
| Prompt Composer | `services/prompt_composer/` | `IMPLEMENTED` (детерминированный provider-neutral PromptPackage) |
| MediaPlan | `services/mediaplan/` | `IMPLEMENTED` (Scenario-owned; scene-specific media planning) |
| Editor Application Service | `services/editor_application/` | `IMPLEMENTED` (тонкий UI-агностичный фасад) |
| desktop editor | `ui/editor_desktop/` | `IMPLEMENTED` (Qt/PySide6 editor; реальное авторирование сцен) |
| real scene authoring | `authoring/scene_drafts/`, `authoring/accepted_ordered_ass/`, `authoring/project/` | `IMPLEMENTED` (реальные принятые сцены; напр. `sc_kira_hidden_problem_001`) |
| canonical Ren'Py publication | `tools/vne_to_renpy/ordered_ass_canonical_publisher.py` | `IMPLEMENTED` (публикация в `novel/game/ordered_ass_generated.rpy`) |
| generated-file firewall | ownership-marker `# VNE-GENERATED: ORDERED_ASS_RENPY_V1`; fixed path; symlink/SHA-256 guard | `IMPLEMENTED` |
| workspace_project | `services/workspace_project/` (`ProjectManifest`, `AcceptedOrderedASSBatch`, `WorkspaceIndex`) | `IMPLEMENTED` (Scenario-local; shared cross-product membership — `NOT YET RATIFIED`) |
| Story Sequence V0 | `services/story_sequence/` | `IMPLEMENTED` (Scenario-owned story-level order + entry; `vne_story_sequence/0.1`: `ordered_scene_ids`, `start_scene_id`; exact-coverage validated against `AcceptedOrderedASSBatch`; drives deterministic export + `vne_story_start`; интегрировано/опубликовано @ `991f85f`) |

### 13.3 SUPERSEDED_BY / PARTIAL (исторический JSON-first путь)

| Старый механизм | Статус | Современный механизм |
|---|---|---|
| JSON → Ren'Py renderer (`tools/renpy_v2_playable_exporter.py`, `tools/vne_to_renpy/exporter.py`, `scenes_v2_generated.rpy`) | `SUPERSEDED_BY` (для accepted-scene пути) | OrderedASS exporter (`tools/vne_to_renpy/ordered_ass_exporter.py` → `ordered_ass_generated.rpy`) |
| Scenario V2 JSON как accepted-scene объект | `HISTORICAL` / `REFINED_BY` | SceneBody → OrderedASS lifecycle; JSON остаётся source-входом legacy ASS-импорта |
| In-place Dev editor (N5-Dev: live-JSON write-back внутри RenPy) | `SUPERSEDED_BY` / `DEFERRED` | desktop editor (SceneBody draft lifecycle, `ui/editor_desktop/`) |
| Live JSON runtime (N2/N5G/N5H: live чтение JSON в RenPy) | `HISTORICAL` / `PARTIAL` (docs/контракт есть, runtime НЕ реализован) | deterministic generate-ahead `.rpy` (OrderedASS exporter) — канонический release-путь |

### 13.4 FUTURE PLATFORM INTEGRATION (FUTURE / NOT_IMPLEMENTED — планирование без реализации)

1. **Portable character identity alignment.** Scenario уже использует/сохраняет стабильный
   `character_id`. Будущая интеграция должна выровняться с Character Lab portable character
   identity. — `FUTURE`.

2. **VCP / `.vchar`.** Character Lab использует portable package boundary (VCP Package V1 / `.vchar`).
   Scenario consumer integration — `NOT_IMPLEMENTED`. Здесь **не** проектируется.

3. **Character Media (OWNER-RATIFIED boundary).** Character Lab = character-owned media; Scenario =
   scene-specific MediaPlan. Первый managed Primary Portrait slice — Lab-local. Scenario consumer —
   `WAIT FOR PORTABLE MEDIA HANDOFF` (`NOT_IMPLEMENTED`). Scenario **не** читает Primary Portrait из
   `.vchar`; asset-role schema для Scenario не финализирована; Gallery/shared Reference Library в
   Scenario отсутствуют; Character Media asset IDs Scenario неизвестны.

4. **Workspace.** `services/workspace_project/` существует. Shared cross-product membership —
   `NOT YET RATIFIED`.

5. **Studio.** Scenario ↔ Studio shared runtime contract — `FUTURE / NOT_IMPLEMENTED`
   (репозиторного evidence реализованной Studio-интеграции нет).

6. **Common shell.** Не утверждать, что существует. `FUTURE` only.

## 14. VOYAGE SCENARIO EDITOR — ROADMAP TO STANDALONE RELEASE 1.0

> **STATUS: `OWNER_RATIFIED`.** This section records the Owner-ratified development direction
> (ratification **`OD-SE-ROADMAP-01`**, 2026-10-01) for the standalone **Voyage Scenario Editor 1.0**
> desktop product. It introduces **no** implementation, **no** architecture change, and **no** new
> cross-product contract. It updates the existing canonical roadmap (§1–§13 preserved unchanged) with
> the ratified path from the current implemented Scenario foundation to a standalone release.
>
> **Product branch:** `Voyage-Scenario-Editor` — a permanent product-development branch inside this
> repository. **HEAD baseline for this draft:** `1b024c4f5081c32145e2347a4513b4af5e9ded79`
> (Story Sequence V0 documentation sync). **Story Sequence source commit:** `991f85fcb3abd6026398f929ff191255172c7c2f`.
>
> **Language note:** this section is written in English to match the Owner direction of the current
> planning cycle; canonical Russian terms are quoted verbatim where they carry ratified meaning.
>
> **Owner ratification record — `OD-SE-ROADMAP-01` (2026-10-01).**
> - **STATUS:** `OWNER_RATIFIED`.
> - **SCOPE:** roadmap and development direction only.
> - **OWNER APPROVED:** the A–I roadmap (§14.5.A–§14.5.I) leading to Voyage Scenario Editor 1.0.
> - **NEXT MILESTONE:** Stage B (Story Runtime Semantics V1). Its technical contract remains subject to
>   `OD-SE-RUNTIME-01` before implementation.
> - **INITIAL RELEASE TARGET:** Windows (approved). Other operating systems are outside the current
>   release commitment and require separate approval.
> - This ratification does **not** mark future stages (B–I) as `IMPLEMENTED`, and it is **not** approval
>   to begin every future implementation stage.
>
> **SUPERSESSION ANNOTATION (2026-10-01).** The `OD-SE-ROADMAP-01` record above is preserved verbatim as
> historical Owner evidence. Its `NEXT MILESTONE: Stage B (Story Runtime Semantics V1)` is **superseded**
> by the §14.9 corrective addendum. The **active next milestone** is the proposed `SE-1` / `SE-2`
> authoring-model direction; `STORY_RUNTIME_SEMANTICS_V1` is `REMOVED_FROM_MANDATORY_1.0_PATH` and is
> **no longer the active next milestone**.

---

### 14.1 How to read this section

Five levels are kept strictly separate (extends §13.1 with the release path):

| Level | Meaning | Status labels used |
|---|---|---|
| **IMPLEMENTED FOUNDATION** | Factually present in code/tests; verified against the product branch | `IMPLEMENTED`, `MAIN_ACCEPTED`, `PRODUCT_BRANCH_ACCEPTED` |
| **RATIFIED DECISIONS** | Previously ratified architectural/product decisions | quoted from `NARRATIVE_DECISIONS_v1.md` §15 |
| **OWNER DIRECTION** | Decisions stated by the Owner in the current planning cycle | recorded as direction, not re-ratified here |
| **NEWLY PROPOSED WORK** | Proposed next milestones; require Owner ratification before implementation | `NEXT_PROPOSED`, `PLANNED_DRAFT`, `OWNER_DECISION_REQUIRED` |
| **FUTURE PLATFORM INTEGRATION** | Cross-product integration via portable contracts; not part of Scenario Editor 1.0 | `FUTURE`, `NOT_IMPLEMENTED` |

No speculative milestone is presented as already approved. No completion date or percentage is
invented. Proposed sequence labels (B–I) are **new to this planning cycle**; they did not exist in
the historical roadmap (N0–N6 / N7 / SVA, §1–§12) and are not presented as historical.

### 14.2 Owner-defined product boundary (current planning cycle)

**SCENARIO EDITOR FINISH.** A standalone desktop editor allowing the author to:

- create and open narrative projects;
- create and edit scenes;
- validate and accept immutable scene versions;
- manage story order and entry;
- author the required story logic and transitions;
- work with Scenario-owned scene-media planning;
- bind the media required for publication;
- generate deterministic Ren'Py output;
- use an integrated publication and preview/play workflow;
- save and reopen user projects;
- install and run the application independently of the source repository and development environment.

**OUTSIDE SCENARIO EDITOR OWNERSHIP** (not owned, not duplicated, not depended upon):

- Character Lab internal authoring;
- Character-owned Media Library;
- Studio sessions and runtime ownership;
- common cross-product workspace authority;
- unified NARRATIVE shell.

Future integration with those products uses **approved portable contracts**. Those contracts are
**not invented here** (see §14.6).

**Finish definitions (kept separate, not merged).** Three distinct finish boundaries are established:

- **SCENARIO EDITOR FINISH** — the capability and acceptance boundary defined above in this §14.2.
- **SCENARIO PRODUCT 1.0 FINISH** — Voyage Scenario Editor 1.0 as a standalone, installable,
  independently usable desktop application (§14.5.I).
- **PLATFORM INTEGRATION FINISH** — a separate `FUTURE` track involving approved portable character
  contracts, Character Media handoff, shared workspace decisions, Studio, and the unified NARRATIVE
  experience (§14.6).

These finish definitions are **not merged**. The standalone Scenario Editor release must **not** require
a running Character Lab or Studio installation.

### 14.3 Product development policy (product-branch policy)

Proposed policy for the `Voyage-Scenario-Editor` permanent product integration line:

- `Voyage-Scenario-Editor` is a **permanent product integration line**, not a throwaway feature branch.
- Individual implementation slices are authored on **dedicated feature branches + worktrees**.
- Integration into the product branch requires **independent review + explicit Owner authorization**.
- The common repository **main** is **not** an automatic destination for every Scenario change.
- **Platform integration** (Character Lab / Studio / shared workspace / shell) is gated separately by
  evidence, never as a silent prerequisite of Scenario Editor 1.0.
- **Standalone releases** follow a versioned release process, independently verified (see §14.5.H).

This draft does **not** modify Git governance infrastructure.

### 14.4 Completed foundation — capability table

Reconstructed from the product branch (`services/`, `ui/`, `tools/vne_to_renpy/`) and cross-checked
against `NARRATIVE_DECISIONS_v1.md` §15 and `NARRATIVE_ROADMAP.md` §13.2. Backend, Desktop UI, and
End-to-end readiness are reported separately so a backend-only capability is not presented as
complete.

| Capability | Where | Backend | Desktop UI | End-to-end |
|---|---|---|---|---|
| ASS v0 (`ass/0.1`) | `services/ass/` (model, importer, hashing) | IMPLEMENTED | — | — |
| OrderedASS (`ass/0.2`) | `services/ass/ordered.py` | IMPLEMENTED | — | — |
| Canonical ASS store | `services/ass/store.py` | IMPLEMENTED (atomic hard-link, SHA-256) | — | — |
| SceneBody (authoring payload) | `services/scene_body/` | IMPLEMENTED (`scene_body/1.0`) | partial (draft text edit) | — |
| Draft → Validate → Accept | `services/scene_draft/` (compiler, store) | IMPLEMENTED (one-time, immutable) | IMPLEMENTED | IMPLEMENTED (real accepted scenes) |
| Scene revision / acceptance | `services/scene_draft/` (SceneVersion DRAFT→ACCEPTED) | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED |
| Location Canon | `services/location_canon/` | IMPLEMENTED (read-only) | read-only list | — |
| Character Canon read bridge | `services/character_canon_bridge/` | IMPLEMENTED (read-only, `APPROVED_AS_CANON`) | read-only list | — |
| Scene Interpretation | `services/scene_interpretation/` | IMPLEMENTED (immutable artifact) | — | — |
| Prompt Composer | `services/prompt_composer/` | IMPLEMENTED (deterministic PromptPackage) | — | — |
| MediaPlan | `services/mediaplan/` | IMPLEMENTED (Scenario-owned) | — | — |
| Editor Application Service | `services/editor_application/` | IMPLEMENTED (UI-agnostic facade) | consumed | — |
| PySide6 Desktop Editor | `ui/editor_desktop/` | IMPLEMENTED (facade-backed shell) | IMPLEMENTED (browse + draft text edit + accept) | partial (single hardcoded project) |
| workspace_project | `services/workspace_project/` | IMPLEMENTED (Scenario-local) | partial | — |
| Ren'Py exporter | `tools/vne_to_renpy/ordered_ass_*.py` | IMPLEMENTED (deterministic) | — | via CLI |
| Canonical publisher | `tools/vne_to_renpy/ordered_ass_canonical_publisher.py` | IMPLEMENTED | — | via CLI |
| Generated-file firewall | marker `# VNE-GENERATED: ORDERED_ASS_RENPY_V1` | IMPLEMENTED | — | IMPLEMENTED |
| Story Sequence V0 | `services/story_sequence/` | IMPLEMENTED + `MAIN_ACCEPTED` + `REMOTE_PUBLISHED` (`991f85f`) | — (no story-order UI yet) | IMPLEMENTED (export order + `vne_story_start`) |

Factual distinctions (backend vs UI vs end-to-end):

- **Backend is complete** for the accepted-scene lifecycle, media planning, prompt composition,
  workspace membership, and deterministic Ren'Py publication.
- **Desktop UI is partial.** The existing `ui/editor_desktop/` is a Qt/PySide6 shell that browses
  scenes/characters/locations and edits draft scene text fields (`scene_title`, `location_id`,
  `content_rating`, `TextEntry.text`), with validate/accept. It is bound to **one hardcoded project**
  (`PROJECT_ID = "narrative_game"`) under the repository `authoring/` paths. It has **no** create/open
  project UI, **no** story-order/entry editing UI (backend `save_story_sequence` exists; the UI does
  not expose it), **no** integrated publication trigger, and **no** preview/play workflow.
- **End-to-end is partial.** Canonical Ren'Py publication and preview/play are exercised via separate
  CLI tools (`tools/vne_to_renpy/`), not yet wired into a single author-facing editor workflow.
- **Standalone readiness is absent.** The application config is anchored to `repo_root`/`authoring/`
  repository paths. `PySide6` is declared in `requirements.txt` (`PySide6==6.11.1`) but is **not**
  separately declared in `requirements-dev.txt` (which declares only `jsonschema`). The Qt runtime is
  therefore an editor runtime dependency rather than a dev-checkout tooling dependency, and the
  standalone dependency audit must inspect the complete dependency chain and packaging requirements.

### 14.5 Proposed roadmap sequence (A → I)

Each stage records: **NAME / STATUS / OBJECTIVE / EXISTING FOUNDATION / REMAINING WORK /
DEPENDENCIES / DELIVERABLE / ACCEPTANCE / OWNER GATE.** The lettered labels are new to this planning
cycle; they are not historical milestones.

#### 14.5.A — COMPLETED FOUNDATION

- **STATUS:** `IMPLEMENTED` (backend), `MAIN_ACCEPTED` (Story Sequence V0 per §15.8), partial desktop UI.
- **OBJECTIVE:** the accepted-scene architecture, desktop editor, publication infrastructure, and
  Story Sequence V0 already present on the product branch.
- **EXISTING FOUNDATION:** the full §14.4 table.
- **REMAINING WORK:** none for the backend; desktop UI and end-to-end gaps are carried into C–I.
- **DEPENDENCIES:** — (this is the baseline).
- **DELIVERABLE:** the current product branch state (`1b024c4f`).
- **ACCEPTANCE:** already satisfied by existing code/tests and canonical §13/§15 reconciliation.
- **OWNER GATE:** none (already accepted into the product line).

#### 14.5.B — STORY RUNTIME SEMANTICS V1

- **STATUS:** `SUPERSEDED_FOR_1.0` — see §14.9 corrective addendum (2026-10-01); no longer the active next milestone.
- **OBJECTIVE:** define and implement story-level runtime semantics on top of the accepted-scene
  authority, without reviving the historical live-JSON runtime.
- **EXISTING FOUNDATION:** `SceneBody`/`OrderedASS` per-scene `next_target` (`ChoiceTarget`:
  `ENTRY`/`SCENE`/`END`) is the only existing scene-to-scene control flow. `StorySequence` V0 owns
  order + entry (`ordered_scene_ids`, `start_scene_id`) and explicitly **does not** own conditions,
  flags, variables, player_state, transitions, or runtime state (§15.8, `services/story_sequence/model.py`).
  A codebase search for `player_state`, `prerequisites`, `flags_required`, `completion_flag` in
  `services/` and `tools/vne_to_renpy/` returns no implementation.
- **REMAINING WORK (proposed):** author-level story logic — conditions, prerequisites, flags /
  variables, player_state, transitions between scenes, and save/load semantics — expressed as
  **story-level contracts** that feed deterministic Ren'Py generation.
- **DEPENDENCIES:** A (§14.5.A) and the §15.8 boundary (Story Sequence V0 does not grow into a story
  graph without a separate gate).
- **DELIVERABLE:** a ratified design/contract for V1 runtime semantics (ownership boundaries and any
  contract changes), followed by implementation only after ratification.
- **ACCEPTANCE:** semantics are deterministic, OrderedASS/SceneBody remains the source of truth, no
  live-JSON runtime is revived, and the generate-ahead Ren'Py path remains canonical.
- **OWNER GATE:** `OWNER_DECISION_REQUIRED` — detailed V1 runtime semantics, ownership boundaries, and
  contract changes require a **separate design/ratification gate** before implementation.

#### 14.5.C — STORY-FLOW AUTHORING

- **STATUS:** `PLANNED_DRAFT` (proposed; historical dependency on Stage B superseded — see §14.9).
- **OBJECTIVE:** connect the story-flow authoring model to the desktop authoring workflow so the author
  can manage story order, entry, and scene-to-scene transitions inside the editor, aligned with the
  proposed `SE-1` / `SE-2` authoring-model direction. The historical rationale (ratified story
  semantics from Stage B) is retained; `STORY_RUNTIME_SEMANTICS_V1` is superseded for 1.0 (§14.9) and
  is **not** a prerequisite for authoring to begin.
- **EXISTING FOUNDATION:** backend `services/editor_application` already exposes `save_story_sequence`
  and read-only `get_publication_readiness`; `services/story_sequence/` validates order/entry. The
  desktop UI does **not** yet surface story order/entry editing.
- **REMAINING WORK:** author-facing UI for story order + entry + transition logic, wired through the
  facade and validated against `AcceptedOrderedASSBatch` (exact coverage).
- **DEPENDENCIES:** A (and the proposed `SE-1` / `SE-2` authoring model). The historical dependency on
  B (ratified semantics) is superseded — see §14.9.
- **DELIVERABLE:** a desktop story-flow authoring surface producing a valid `StorySequence` (without a
  mandatory Story Runtime Semantics V1 prerequisite).
- **ACCEPTANCE:** an author edits order/entry/transitions in the UI; the result validates and drives
  deterministic export order; no scene-authority bypass.
- **OWNER GATE:** aligned with the `SE-1` / `SE-2` authoring-model direction (§14.9). The former
  `ratification of Stage B's semantics` is no longer a gate before authoring begins.

#### 14.5.D — SCENARIO MEDIA WORKFLOW COMPLETION

- **STATUS:** `PLANNED_DRAFT`.
- **OBJECTIVE:** complete the necessary **Scenario-owned** media authoring/binding for publication
  without duplicating Character Lab's authoritative character media.
- **EXISTING FOUNDATION:** `services/mediaplan/` (Scenario-owned MediaPlan) and the §15.6 ratified
  split (Character Lab = character-owned media; Scenario = scene-specific MediaPlan). Character Media
  portable consumption is `FUTURE`/`NOT_IMPLEMENTED`/`WAITING_FOR_PORTABLE_MEDIA_HANDOFF`.
- **REMAINING WORK:** scene-media authoring/binding surface for what Scenario owns; media required for
  publication is bound to scenes deterministically. No second authoritative Character Media Library.
- **DEPENDENCIES:** A; §15.6 media ownership boundary.
- **DELIVERABLE:** a complete Scenario-owned media authoring/binding workflow.
- **ACCEPTANCE:** a scene's required media is authorable and bound for publication without touching
  Character Lab media authority.
- **OWNER GATE:** media-role/asset-role schema for Scenario remains unratified (see §15.6) —
  `OWNER_DECISION_REQUIRED` before any new media contract.

#### 14.5.E — INTEGRATED PUBLICATION / PREVIEW / PLAY

- **STATUS:** `PLANNED_DRAFT`.
- **OBJECTIVE:** establish the complete author-facing publishing workflow (publish → preview → play)
  inside the editor.
- **EXISTING FOUNDATION:** deterministic OrderedASS → Ren'Py exporter, canonical publisher, and the
  generated-file firewall are implemented as CLI tools (`tools/vne_to_renpy/`). `vne_story_start` is
  the **generated** StorySequence entry label (jumps to `start_scene_id`).
- **REMAINING WORK:** wire publish + preview/play into the editor; an integrated, repeatable
  author-facing flow. **The global Ren'Py `label start` remains separately owned** — this stage must
  **not** silently modify `script.rpy` or present entry wiring as already-ratified behavior.
- **DEPENDENCIES:** A, C, D.
- **DELIVERABLE:** integrated publication/preview/play workflow in the desktop editor.
- **ACCEPTANCE:** an author publishes, previews, and plays the generated result from the editor; the
  generated entry label is `vne_story_start`; `script.rpy` global `start` is left untouched unless a
  separate, explicit Owner decision authorizes wiring.
- **OWNER GATE:** any change to global entry wiring is `OWNER_DECISION_REQUIRED` (not assumed here).

#### 14.5.F — EDITOR COMPLETION / ACCEPTANCE

- **STATUS:** `PLANNED_DRAFT`.
- **OBJECTIVE:** define acceptance checks for **all** required editor capabilities from the Owner's
  FINISH boundary (§14.2) and classify which Player Experience requirements are in scope, already
  implemented, or deferred.
- **EXISTING FOUNDATION:** the §14.4 capabilities. Draft edit, validate, and accept are implemented in
  the desktop UI; create/open project, story-order UI, publication, preview/play, and save/reopen are
  not yet complete.
- **REMAINING WORK:** a checklist mapping each FINISH item to an implemented-or-planned state, plus a
  Player Experience triage. Reference `PLAYER_EXPERIENCE_SPEC.md` §11–§12: MVP = Classic VN + basic
  Psychological + read-only inspector (historically target); Mind-reading, full Director, LLM inside
  RenPy, pre-game questionnaire, settings UI, and full in-place editor are deferred. Only items in
  scope for the **Scenario Editor authoring product** (not the player-facing runtime) are proposed here.
- **DEPENDENCIES:** A, C–E.
- **DELIVERABLE:** an acceptance matrix for Scenario Editor 1.0 editor capabilities.
- **ACCEPTANCE:** every FINISH-boundary item is explicitly marked implemented / planned / deferred;
  no deferred item is reported as complete.
- **OWNER GATE:** the acceptance matrix and Player Experience scope split require Owner ratification.

#### 14.5.G — STANDALONE APPLICATION

- **STATUS:** `PLANNED_DRAFT`; packaging framework selection is `OWNER_DECISION_REQUIRED`.
- **OBJECTIVE:** make the editor installable and runnable independently of the source repository and
  development environment.
- **EXISTING FOUNDATION:** the desktop app launches via `py -m ui.editor_desktop` (PySide6) but is
  anchored to `repo_root`/`authoring/` paths with a single hardcoded project; `requirements-dev.txt`
  declares only `jsonschema` (PySide6 is undeclared).
- **REMAINING WORK (to investigate, not select yet):** application dependency audit; standalone
  launch; bundled runtime requirements; application configuration; **external user-project storage**
  (decoupled from repository `authoring/` paths); missing-dependency handling; installation
  independence from repository paths.
- **DEPENDENCIES:** A, C–F.
- **DELIVERABLE:** a standalone-capable application with external project storage and a declared
  dependency/runtime strategy.
- **ACCEPTANCE:** the app runs without the repository checkout; user projects live outside the repo;
  missing dependencies are reported, not silently broken.
- **OWNER GATE:** **no packaging framework is selected without evidence** — `OWNER_DECISION_REQUIRED`
  after the dependency/storage audit.

#### 14.5.H — INSTALLER AND RELEASE QA

- **STATUS:** `PLANNED_DRAFT`; **Windows is the approved initial release target** (via `OD-SE-ROADMAP-01`).
- **OBJECTIVE:** define release preparation and quality assurance for the first standalone install.
- **EXISTING FOUNDATION:** the deterministic publication path and the standalone app (after G).
- **REMAINING WORK (proposed release checks):** installation package; first launch; user-project
  creation; save/reopen; authoring flow; generation/publication; playable result; clean-device
  acceptance; version metadata; release artifact verification.
- **DEPENDENCIES:** A, C–G.
- **DELIVERABLE:** a versioned installer plus a documented release-QA run.
- **ACCEPTANCE:**
  1. The installed application works without VS Code, Cline, a source-code checkout, the development
     repository, or a separately prepared Python development environment.
  2. Ordinary application reinstallation does **not** silently delete or overwrite existing user
     projects.
  3. User-project storage remains independent of the installed application directory.
  4. The release artifact installs, launches, and completes the full authoring → publication →
     playable-result flow on a clean device, with verifiable version metadata.
- **OWNER GATE:** **Windows is the approved initial release target** (via `OD-SE-ROADMAP-01`).
  Additional operating systems are **outside the current release commitment** and are
  `OWNER_DECISION_REQUIRED`. The actual storage path, installer technology, and upgrade mechanism
  remain subjects of future implementation/design — no packaging framework is selected here.

#### 14.5.I — VOYAGE SCENARIO EDITOR 1.0

- **STATUS:** `PLANNED_DRAFT` — the proposed final standalone application milestone.
- **OBJECTIVE:** a standalone, installable **Voyage Scenario Editor 1.0** satisfying the full §14.2
  FINISH boundary on the approved initial target (Windows).
- **EXISTING FOUNDATION:** A, C–H.
- **REMAINING WORK:** close all §14.5.F acceptance items; ship the H release artifact.
- **DEPENDENCIES:** A, C–H (Stage B §14.5.B superseded — see §14.9).
- **DELIVERABLE:** Voyage Scenario Editor 1.0 standalone release.
- **ACCEPTANCE:** every §14.2 FINISH item is verifiably satisfied; Character Lab, Studio, and
  shared-workspace ownership boundaries remain unchanged; no unratified platform contract is a
  dependency.
- **OWNER GATE:** final release authorization is `OWNER_DECISION_REQUIRED`.

### 14.6 Platform integration (FUTURE, separate track)

Kept **separate** from the standalone Scenario Editor 1.0 path. These are cross-product concerns gated
by portable contracts; none is presented as a prerequisite of Scenario Editor 1.0 unless evidence
proves a concrete dependency (none does).

1. **Portable character identity** — `FUTURE` (see §15.5, §13.4). Scenario already stores a stable
   `character_id`; future alignment with Character Lab portable identity is not designed here.
2. **VCP / `.vchar` Scenario consumer** — `NOT_IMPLEMENTED` (see §15.5). No consumer contract is
   invented in this draft.
3. **Character Media portable handoff** — `FUTURE` / `NOT_IMPLEMENTED` / `WAITING_FOR_PORTABLE_MEDIA_HANDOFF`
   (see §15.6). Scenario MediaPlan remains Scenario-owned; it does not read Primary Portrait from `.vchar`.
4. **Shared cross-product workspace** — `NOT YET RATIFIED` (see §15.7). `services/workspace_project/`
   is Scenario-local today.
5. **Studio contract** — `FUTURE` / `NOT_IMPLEMENTED` (see §13.4).
6. **Unified NARRATIVE shell** — `FUTURE` only (see §13.4).

**Mapping the historical S0–S9 draft** (`NARRATIVE_SCENARIO_DEVELOPMENT_MASTER_PLAN_V0`, LOCAL_STORAGE):
the S0 (baseline recovery/discovery) and S1 (product boundary) substance is now covered by the §13/§15
reconciliation and this §14 — but their **named historical deliverables**
(`NARRATIVE_SCENARIO_PLATFORM_INTEGRATION_DISCOVERY_V1_REPORT`, `NARRATIVE_SCENARIO_PRODUCT_BOUNDARY_V1`)
were not produced as such and are **not fabricated** here. The useful S2–S9 material maps into the
future integration area above without ratifying any new contract:

- **S2 (External Character Reference)** → item 1/2 (portable character identity + `.vchar` consumer).
- **S3 (Scene/ASS Character Binding)** → `NOT_IMPLEMENTED`; no ASS schema change is ratified here.
- **S4 (Workspace Membership)** → item 4 (shared cross-product workspace).
- **S5 (Location Boundary)** → Location Canon is already implemented (§14.4); cross-product portable
  location identity remains future.
- **S6 (Media Boundary)** → item 3 (Character Media portable handoff).
- **S7 (AI Assistance Boundary)** → Scenario-owned provider-neutral Prompt Composer is implemented;
  any cross-product AI provider boundary is future/out of scope.
- **S8 (Studio/Runtime Boundary)** → item 5 (Studio contract).
- **S9 (Unified NARRATIVE Product Experience)** → item 6 (unified shell).

### 14.7 Owner decisions still needed

Listed only where the decision is **not** already resolved by existing Owner direction or canonical
evidence. This ratification (`OD-SE-ROADMAP-01`) does **not** close any of the following gates:

- **OD-SE-RUNTIME-01:** `NOT RATIFIED` — `SUPERSEDED AS A MANDATORY 1.0 DEPENDENCY`. Story Runtime
  Semantics V1 is no longer a required Owner decision for 1.0 (§14.5.B, §14.9). `B1–B5`: `NEVER
  STARTED` (never implemented; not presented as implemented and subsequently removed).
- **OD-SE-MEDIA-01:** ratify any Scenario media-role/asset-role schema change before Scenario media
  binding goes beyond current MediaPlan (§14.5.D; see §15.6).
- **OD-SE-ENTRY-01:** authorize (or decline) any global Ren'Py `label start` entry wiring; the
  generated `vne_story_start` remains the default and `script.rpy` is not silently modified (§14.5.E).
- **OD-SE-PACKAGE-01:** select a packaging/distribution framework based on the §14.5.G audit evidence.
- **OD-SE-OS-01:** Windows is **approved** as the initial release target (via `OD-SE-ROADMAP-01`);
  any additional OS remains a separate `OWNER_DECISION_REQUIRED` (§14.5.H).
- **OD-SE-1.0-01:** authorize the Voyage Scenario Editor 1.0 release itself (§14.5.I).

### 14.8 Historical preservation and non-goals

- **Historical roadmap (N0–N6 / N7 / SVA, §1–§12) is preserved unchanged.**
- **No second master roadmap is created** (no `NARRATIVE_ROADMAP_V2.md`, `SCENARIO_MASTER_ROADMAP.md`,
  or `VOYAGE_SCENARIO_MASTER_PLAN.md`).
- **The historical live-JSON runtime is not revived** (§14.5.B); the authoritative direction remains
  SceneBody → validation/acceptance → OrderedASS → story-level contracts → deterministic Ren'Py.
- **Character Lab and Studio ownership are unchanged** (§14.2, §15.5–§15.8).
- **Platform integration is separately identified** (§14.6) and is not a prerequisite of 1.0.
- **No packaging framework is selected without an Owner gate** (§14.5.G).
- This section modifies **only** `docs/narrative/NARRATIVE_ROADMAP.md`. The decision, architecture,
  document-index, runtime-contract, player-experience, and governance files are **not** changed here;
  a dedicated post-ratification sync is a separate future task.

---

## 14.9 Corrective addendum — VOYAGE SCENARIO EDITOR — PRODUCT DESIGN REALIGNMENT V1 (2026-10-01)

> **Precedence.** This dated addendum records a corrective Owner product-design direction. It takes
> precedence over the superseded `Stage B — Story Runtime Semantics V1` planning below (§14.5.B and the
> §14 Owner ratification record `OD-SE-ROADMAP-01`). It does **not** delete the historical §1–§14 record.

**Source.** Owner product-design handoff `docs/narrative/SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md`
(status `OWNER_DISCUSSION_AGREED / AWAITING_CANONICAL_DOC_SYNC`).

**Source (product addendum).** Owner product-design addendum
`docs/narrative/SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md` (status
`OWNER_DISCUSSION_AGREED / AWAITING_CANONICAL_DOC_SYNC`) records the Character Library and
multi-assistant requirements (SE-3 / SE-4) as **product behavior** — not a ratified schema, not a
ratified AI provider contract, and not a second master roadmap.

**`OD-SE-EDITOR-PURPOSE-01` (AGREED).** Voyage Scenario Editor is a standalone multimedia literary
authoring application. The writer owns narrative text, Card boundaries, Card connections, reader-facing
choices, Slides, dialogue, and multimedia composition. The application provides authoring, editing,
storage, validation, preview, and Ren'Py publication; it does **not** automatically interpret the
artistic meaning of the text. Object-based gameplay logic is **NOT required** for Scenario Editor 1.0.

**Superseded status records (the historical §14.5.B body is preserved — these components were never
implemented and are not presented as deleted capabilities):**

- `STORY_RUNTIME_SEMANTICS_V1`: `REMOVED_FROM_MANDATORY_1.0_PATH`.
- `OD-SE-RUNTIME-01`: `NOT RATIFIED`.
- `IMPLEMENTATION B1–B5`: `NOT STARTED / DO NOT START`.

**Proposed active release sequence (PROPOSED, pending final Owner approval):**

- `SE-0` — Canonical Product Design Sync (this addendum).
- `SE-1` — Authoring Model and Storage Foundation.
- `SE-2` — Card/Slide Authoring and Three Synchronized Views.
- `SE-3` — Unified Character Library (manual creation + `.vchar` import), character media, and
  optional AI capability.
- `SE-4` — Writer-controlled multi-assistant Dialogue Workshop.
- `SE-5` — Start Page and Game Menu Editors.
- `SE-6` — Integrated Preview, Ren'Py Publication and Testing.
- `SE-7` — Standalone Windows Application, Installer and Release QA.

Classification vocabulary retained: `ALREADY_IMPLEMENTED`, `PARTIALLY_IMPLEMENTED`, `MISSING`,
`REQUIRES_ADAPTATION`, `DEFERRED`, `OBSOLETE_FOR_1.0`.

**Storage + authoring model begin together.** The Card/Slide authoring model and the hybrid storage
contract are designed jointly in `SE-1`, not deferred until after all authoring features are built.

**Preserved foundations (not rewritten):** SceneBody, ASS/OrderedASS, Draft/Validate/Accept,
StorySequence V0, MediaPlan, Editor Application Service, Workspace Project, Ren'Py Exporter, and
Canonical Publisher. Native Ren'Py capabilities are used first; no new custom runtime.

**Compatibility questions deferred to follow-up (not ratified here):** Card↔SceneBody mapping, Slide
boundaries, complete Utterance↔Display Portion, choice transitions↔visual Card connections, Character
Lab export↔Scenario import, portable multimedia project storage, and Ren'Py rendering/preview
boundaries. `.vscenario` remains a working extension name, not a ratified format.

**The SE-0–SE-7 sequence is a proposed updated implementation order pending final Owner approval.** It
is not an already-completed or independently ratified technical architecture.
