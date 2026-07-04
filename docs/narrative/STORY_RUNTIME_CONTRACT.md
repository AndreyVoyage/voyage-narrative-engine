# STORY RUNTIME CONTRACT — Voyage Narrative Engine (VNE)

> **Назначение.** Контракт исполнения сцен: *как* данные из `SCENARIO_SCHEMA_V2` реально играются.
> Схема (`SCENARIO_SCHEMA_V2_SPEC.md`) сказала **что хранится** — этот документ говорит **как это исполняется**.
> Решения — `NARRATIVE_DECISIONS_v1.md`; слои — `NARRATIVE_ARCHITECTURE.md`.
>
> **Статус:** ЧЕРНОВИК v1 (контракт поведения)
> **Дата:** 2026-06-30
> **Narrative baseline:** `5571bd2505715b8f19b092ad1762b8d32449c360`
> **Базовое решение (N0):** JSON-first. Runtime-контракт **не зависит от RenPy** — RenPy его исполняет, не определяет.

---

## 0. Границы документа

- Описывает **поведение** runtime: чтение JSON, исполнение beats, применение flags, разрешение branches, player_state, save/load, выбор следующей сцены, hot-reload, dev write-back.
- НЕ описывает форму данных (это `SCENARIO_SCHEMA_V2_SPEC.md`) и НЕ описывает отображение (это `PLAYER_EXPERIENCE_SPEC.md`).
- Контракт един для всех renderer'ов (RenPy сейчас; preview/браузер позже). Renderer — исполнитель, контракт — закон.

---

## 1. Источник и загрузка (live JSON read)

**Правило.** Runtime читает сцену из `SCENARIO_*.json` (источник правды). Никакого параллельного «второго источника».

| Аспект | Контракт |
|---|---|
| Что грузится | Канонический V2-JSON сцены по `id`. |
| Когда | При входе в сцену; при hot-reload (§9) — повторно. |
| Валидация на входе | Сцена обязана пройти schema-validation до исполнения; невалидная сцена → не запускается, ошибка в dev-режиме. |
| Кеш | Допустим, но инвалидируется при write-back (§9). |

**Текущее состояние (факт).** Live JSON-чтения нет: SC_003–018 захардкожены в `script.rpy`, SC_019–027 не подключены. Этот контракт описывает целевое поведение; переход — в roadmap.

### 1.1. Hybrid JSON path (N5F decision)

Принят **гибридный путь** JSON → runtime:

1. **Generate-ahead `.rpy` (MVP/release playable path).**
   - `tools/renpy_v2_playable_exporter.py` превращает V2-JSON в статический `novel/game/scenes_v2_generated.rpy`.
   - Этот артефакт — **производный** (derived), не источник правды.
   - Он детерминирован, проходит static RenPy validation (`validate-renpy-v2-generated`) и достижим через dev/test launcher (N5D).
   - Ручные правки в сгенерированном `.rpy` не сохраняются при регенерации.

2. **Live/dev JSON runtime (future foundation).**
   - Будущий RenPy/Python loader читает V2-JSON напрямую во время игры.
   - Нужен для Dev-edit, hot-reload и pause/resume по `beat_id`.
   - **Не реализован** на момент N5F; требует отдельного scoped контракта до начала Dev-edit.

3. **Source of truth invariant.**
   - В обоих путях источником правды остаётся `scenarios/SCENARIO_*.v2.json`.
   - Runtime-контракт един для generate-ahead и live-пути; RenPy его исполняет, но не определяет.

**Минимальный scoped live/dev JSON контракт** (должен быть спроектирован перед N5-Dev):
- **Read path:** откуда loader берёт JSON.
- **Validation boundary:** когда и как проходит schema validation.
- **State model:** как `player_state` Python runtime отображается на RenPy state.
- **beat_id mapping:** как beat адресуется для UI и resume.
- **Write-back boundary:** какие поля можно редактировать (только текстовые: `speech`/`action`/`thought`/`narration`/`emotion`).
- **Hot-reload boundary:** что перезагружается без рестарта и как восстанавливается позиция.
- **Source/generated separation:** JSON — источник, `.rpy` — производный артефакт.
- **Failure behavior:** невалидный JSON не должен ломать release-путь generate-ahead.

### 1.2. Live/Dev JSON Contract (N5G)

Контракт для будущего dev-only live JSON runtime зафиксирован в `docs/narrative/N5G_LIVE_DEV_JSON_CONTRACT.md`.

Runtime-контракт различает четыре слоя:

1. **Python tooling runtime** (`tools/story_runtime_v2.py`) — offline/runtime preview, state-after, availability checks.
2. **Generated RenPy artifact runtime** (`novel/game/scenes_v2_generated.rpy`) — текущий MVP/release playable путь.
3. **External mock/dev loader tooling** (`tools/live_dev_json_loader.py`, N5H) — read-only dev-only инструмент: inspection, address map, state mapping summary, reload-safety classification. Не является runtime внутри RenPy, не пишет в JSON, не делает hot-reload.
4. **Future live/dev JSON runtime** — RenPy/Python loader, который читает JSON напрямую во время игры; должен следовать N5G.

Текущий RenPy release path **не читает JSON в runtime**. N5H добавляет внешнее read-only tooling, но не заменяет generate-ahead `.rpy` и не реализует live JSON runtime. Будущий live/dev путь остаётся dev-only и не заменяет generate-ahead `.rpy` до отдельного решения.

---

## 2. Исполнение beats

Beats (`entry_beats`, затем `branches[].beats`) исполняются **по порядку**.

| `type` | Поведение runtime |
|---|---|
| `narration` | Показать `narration` от рассказчика. |
| `dialogue` | Показать `speech` от `speaker`. |
| `action` | Показать/проиграть `action` (физическое действие `speaker`). |
| `thought` | Обработать по `thought_visibility` (§3) + текущему режиму чтения (см. `PLAYER_EXPERIENCE_SPEC.md`). |

Правила:
- Beat с нарушенным контрактом полей (нет обязательного канала для своего `type`) → ошибка валидации (§1), не исполняется.
- `pov` beat'а наследуется от `pov_default`, если не задан (§5 схемы).
- Порядок строгий: runtime не переставляет beats.

---

## 3. Видимость мыслей (исполнение thought_visibility)

| `thought_visibility` | Runtime-поведение |
|---|---|
| `hidden` | Мысль загружена и хранится в состоянии, но **не выводится** в обычных режимах. Доступна Mind-reading / Director / Dev. |
| `revealed` | Выводится в psychological-режиме для POV-персонажа. |
| `always` | Выводится во всех режимах. |

> Контракт гарантирует: скрытая мысль **существует в runtime**, но решение «показать/нет» делегируется слою отображения. Один источник — разные фильтры.

---

## 4. Применение flags / effects

При выборе ветки runtime применяет `branch.effects` (§9 схемы).

**Порядок применения (детерминированный):**
1. `flags_cleared` — снять перечисленные флаги.
2. `flags_set` — поставить перечисленные флаги.
3. `level_changes` — обновить состояние персонажей (`character_id → new_state`).
4. `relationship_changes` — обновить отношения.

**Правила:**
- **Идемпотентность.** Повторное применение того же `effects` не меняет результат (set уже стоящего флага — no-op). Нужно для безопасного hot-reload и replay.
- **Конфликт `set` vs `cleared`.** Если флаг и в `flags_cleared`, и в `flags_set` — приоритет у `flags_set` (порядок шагов 1→2 это гарантирует).
- **Неизвестные флаги.** Допустимы (флаги — открытое множество строк), но валидатор-линт (§6 архитектуры) предупреждает о флагах, которые нигде не `required`/не потребляются.
- **Флаги — единственный механизм межсценовой памяти** (плюс player_state, §6).

---

## 5. Разрешение branches

| Аспект | Контракт |
|---|---|
| Выбор игрока | Игрок выбирает `branch` по `option_text`; проигрываются `branch.beats`, применяется `branch.effects`. |
| Несколько choice_points | Исполняются по порядку; состояние накапливается. |
| Доступность ветки | По умолчанию все ветки доступны. Если у ветки есть условие (опц. поле-расширение) — runtime скрывает/блокирует недоступные. |
| Merge после ветки | Ветки **не** обязаны сходиться внутри сцены; расхождение фиксируется флагами (§4) и влияет на доступность следующих сцен (§7). Явный merge — через `next` (§8 схемы). |

> Continuity между сценами держится на флагах + prerequisites (§7), а не на жёстком графе переходов внутри сцены.

---

## 6. player_state — состояние игрока

Единый объект состояния прохождения, живёт между сценами.

```json
"player_state": {
  "completed_scenes": ["sc_016_complete", "sc_017_complete"],
  "flags": ["transparency_strengthened", "choice_still_open"],
  "character_states": { "kira": "U5-выбор", "sergey": "S5-встреча" },
  "relationships": { "kira_yakov": "+transparency" },
  "settings": { "...": "см. PLAYER_EXPERIENCE_SPEC.md" },
  "history": [ { "scene": "SC_017", "branch": "1A" } ]
}
```

| Поле | Контракт |
|---|---|
| `completed_scenes` | Множество completion-флагов завершённых сцен. |
| `flags` | Текущее множество активных флагов (после применения §4). |
| `character_states` | Актуальные состояния персонажей. |
| `relationships` | Актуальные отношения. |
| `settings` | Пользовательские настройки/режимы (источник — player experience). |
| `history` | Лог выбранных веток (для replay/аналитики/отмены). |

---

## 7. Завершение сцены и выбор следующей

**Scene complete.** Сцена завершена, когда отыграны все beats выбранной ветки и достигнут `next.on_complete`. Тогда:
1. ставится `next.completion_flag` (напр. `sc_017_complete`) → в `completed_scenes` и `flags`;
2. фиксируется запись в `history`.

**Выбор следующей сцены.**
- Если `next.next_scene` задан явно → перейти к нему.
- Иначе runtime выбирает сцену-кандидата, у которой **выполнены `prerequisites` и `flags_required`** относительно текущего `player_state`.
- Если кандидатов несколько/ноль → решение делегируется (меню выбора / конец доступного контента). Политику уточняет roadmap.

**Контракт доступности:** сцена доступна ⇔ все её `prerequisites` ∈ `completed_scenes` И все `flags_required` ∈ `player_state.flags`.

---

## 8. Save / Load

| Аспект | Контракт |
|---|---|
| Что сохраняется | Весь `player_state` (§6) + позиция (scene id + beat index). |
| Формат | Сериализуемый JSON (совместим с RenPy save, если runtime в RenPy). |
| Load | Восстановить `player_state` и позицию; ресинхронизировать сцену из JSON-источника (а не из снапшота текста — текст всегда из актуального источника). |
| Совместимость | При изменении источника после сейва: структура (флаги/ветки) должна совпадать; текст берётся свежий. Несовпадение структуры → предупреждение/миграция сейва. |

> Принцип: **сейв хранит прогресс, не текст.** Текст всегда из источника — поэтому правки текста (§9) не ломают старые сейвы.

---

## 9. Hot-reload и Dev write-back (основа in-place edit mode)

Это контракт под «зайти в игру и править на месте» (требование из архитектуры §7).

**Hot-reload.**
- Runtime может перечитать сцену из JSON без перезапуска игры.
- После reload: `player_state` сохраняется; текущая сцена пересобирается из свежего JSON; позиция восстанавливается по `beat_id` (не по индексу — чтобы не съезжать при правках).

**Dev write-back.**
1. Dev-режим редактирует **только текстовые поля** текущего beat'а: `speech` / `action` / `thought` / `narration` (+ `emotion`).
2. Запись идёт **в JSON-источник** (§1), не в экран.
3. Перед записью — guard: изменены только текстовые поля; `beat_id`, `type`, `speaker`, `pov`, `thought_visibility`, `option_text`, `effects`, `next` **не** затронуты. Если затронуты — запись блокируется (это структурная правка, требует полноценной валидации §6 архитектуры).
4. После записи — schema-validation → hot-reload → продолжение с того же `beat_id`.

**Контракт безопасности dev-правок:** правка текста никогда не меняет флаги/ветки/состояние. Поэтому она не ломает continuity и не инвалидирует сейвы (§8).

**Текущее состояние (факт).** Ни live-reload JSON внутри RenPy, ни write-back, ни полноценный Dev-edit пока нет (SC_003–018 — статичный `.rpy`). N5H добавляет внешний read-only mock/dev loader (`tools/live_dev_json_loader.py`), который строит address map и классифицирует reload safety, но не перезагружает сцену и не пишет в JSON. Фича полноценного in-place edit реализуема как надстройка после live JSON-runtime. N5F фиксирует Hybrid JSON path: generate-ahead `.rpy` остаётся MVP/release путём, live JSON runtime — будущей dev/edit основой.

---

## 10. Что обязан гарантировать runtime (сводка инвариантов)

```text
1. Единственный источник — JSON. Никакого второго источника правды.
2. Beats исполняются строго по порядку; нарушенный beat не исполняется.
3. effects применяются детерминированно и идемпотентно (cleared → set → levels → relationships).
4. Скрытая мысль существует в состоянии, но показ решает слой отображения.
5. Доступность сцены = prerequisites ⊆ completed_scenes И flags_required ⊆ flags.
6. Сейв хранит прогресс, не текст; текст всегда из актуального источника.
7. Dev write-back пишет только текстовые поля и только в источник, затем hot-reload.
8. Любая правка структуры (флаги/ветки/pov/type) проходит полную валидацию, не быстрый dev-путь.
```

---

## Открытые вопросы для следующих документов / реализации

- Точная политика выбора следующей сцены при множестве кандидатов → roadmap/реализация.
- Формат опционального условия доступности ветки (если вводим) → расширение схемы.
- Реализация live JSON-loader в RenPy (Python внутри RenPy) vs внешний preview-runtime → roadmap (фаза runtime).
- Миграция старых сейвов при изменении структуры сцены → реализация save-системы.

> Коммит — через стандартный Narrative workflow (Claude Code), отдельным небольшим commit.
> Следующий документ: `PLAYER_EXPERIENCE_SPEC.md` (режимы чтения, POV, Director/Dev mode, settings).
