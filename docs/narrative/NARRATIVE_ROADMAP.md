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
HEAD == origin/main == 603816e40dad99da0f9a982d2212035a360f22aa
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
- **Unlocks.** безопасное тестирование V2 playable proof без live runtime.

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
- **Blocked-by.** N2 (live runtime + write-back), N4 (UI-основа), reachable/live JSON path.
- **Unlocks.** N6 (удобный авторинг для Director-результатов).
- **Note.** N5A/N5B — необходимый bridge, но не замена reachable/live JSON runtime.

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

**Note on "SC_017 fully JSON-driven playable":** currently satisfied as a generated playable RenPy artifact from SC_017 V2 JSON (N5A) that passes static build validation (N5B) and is reachable from the normal start menu via an opt-in dev/test launcher (N5D). The artifact does not replace the hand-authored SC_017 path; live JSON loading and production player-facing reachability remain separate future steps.

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
N0 ─▶ N1 ─▶ N2 ─▶ N3 ─▶ N4 ─▶ N5A ─▶ N5B ─▶ N5D ─▶ N5-Dev ─▶ N6
              │           ▲
              └──────────-┘  (N4 требует N2; лучше после N3)
N5A/N5B/N5D — bridge track: JSON→playable proof + build-safety validation + reachable opt-in launcher.
N5-Dev (in-place edit) НЕВОЗМОЖЕН раньше reachable/live JSON path.
Director (N6) требует схему (N1) + runtime (N2) + удобный write-back (N5-Dev).
Character Aside / Voice Layer — N6 / future tracks (см. NARRATIVE_FUTURE_TRACKS_v1.md).
```

> Коммит этого документа — через стандартный Narrative workflow (Claude Code).
> Это завершает набор N0-документов: DECISIONS, ARCHITECTURE, SCHEMA_V2, RUNTIME_CONTRACT, PLAYER_EXPERIENCE, ROADMAP.
