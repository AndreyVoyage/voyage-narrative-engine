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
HEAD == origin/main == 5571bd2505715b8f19b092ad1762b8d32449c360
SC_003–SC_018: playable через ручной novel/game/script.rpy (113 labels)
SC_019–SC_027: source-only JSON (в игре не отображаются)
Live JSON-runtime: НЕТ (RenPy не грузит JSON как сцены)
Scenario JSON schema: НЕТ (в schemas/ только persona-схема)
Exporter: tools/vne_to_renpy/exporter.py — skeletal preview → reports/renpy/ (gitignored)
Validation: tools/rn_workflow.py, tools/vne_adapter.py — частично
Flags: декларативные, не исполняются
Persona/LLM-система: есть как отдельная система (personas/, R1–R8)
Narrative docs: 5 документов созданы, ждут commit (N0)
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
- **Blocked-by.** N2 (live runtime + write-back), N4 (UI-основа).
- **Unlocks.** N6 (удобный авторинг для Director-результатов).

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
N0 ─▶ N1 ─▶ N2 ─▶ N3 ─▶ N4 ─▶ N5 ─▶ N6
              │           ▲
              └──────────-┘  (N4 требует N2; лучше после N3)
Dev edit (N5) НЕВОЗМОЖЕН раньше live JSON-runtime (N2).
Director (N6) требует схему (N1) + runtime (N2) + удобный write-back (N5).
```

> Коммит этого документа — через стандартный Narrative workflow (Claude Code).
> Это завершает набор N0-документов: DECISIONS, ARCHITECTURE, SCHEMA_V2, RUNTIME_CONTRACT, PLAYER_EXPERIENCE, ROADMAP.
