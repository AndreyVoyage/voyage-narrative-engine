# PLAYER EXPERIENCE SPEC — Voyage Narrative Engine (VNE)

> **Назначение.** Контракт UX-режимов: что именно видит игрок/разработчик и в каких режимах.
> Опирается на: `SCENARIO_SCHEMA_V2_SPEC.md` (что хранится) и `STORY_RUNTIME_CONTRACT.md` (как исполняется).
> Решения — `NARRATIVE_DECISIONS_v1.md`; слои — `NARRATIVE_ARCHITECTURE.md`.
>
> **Статус:** ЧЕРНОВИК v1 (контракт UX)
> **Дата:** 2026-06-30
> **Narrative baseline:** `5571bd2505715b8f19b092ad1762b8d32449c360`

---

## 1. Назначение документа

Этот документ описывает **что видит пользователь**, а не как это реализовано и не в каком порядке делается (это roadmap, N0F).

Контракт UX строится **только** на полях V2-схемы: `thought_visibility`, `pov`, `speech`, `action`, `thought`, `narration`, `emotion`, `option_text`. Никакого «показа из хаотичного текста» — режимы возможны именно потому, что каналы разделены на уровне beat.

---

## 2. Роли пользователя

| Роль | Что видит / может |
|---|---|
| **Player** | Обычный игрок: сцены, выборы, разрешённые мысли/POV согласно режиму. Технических деталей не видит. |
| **Director** | Пользователь/автор: обсуждает сцену с LLM, просит варианты реплик/мыслей/действий, делает стоп-кадры. Результат сохраняется как сцена (через нормализацию в V2). |
| **Developer** | Видит `beat_id`, `flags`, `branches`, current branch, editable-поля; может редактировать **только текстовые поля** beat'а (§10). |
| **Reviewer** | Человек, который утверждает изменения до commit (git-гейт). UX-роль: видит diff source→preview, PASS/FAIL валидаторов. |

Роли — это уровни доступа к одному источнику, а не разные продукты.

---

## 3. Режимы чтения

| Режим | Что показывается |
|---|---|
| **Classic VN** | `narration` + `dialogue` (`speech`) + `action`. Мысли скрыты. |
| **Psychological** | Classic + `thought` с `thought_visibility ∈ {revealed, always}` для POV-персонажа. |
| **Mind-reading** | Psychological + `thought` с `thought_visibility = hidden` (в т.ч. нескольких персонажей). |
| **Director** | Поверх любого режима: возможность обсуждать/генерировать варианты сцены (§9). |
| **Dev** | Поверх любого режима: technical IDs, beat structure, flags, current branch, editable fields (§10). |

Все режимы читают **один и тот же источник** — отличается только фильтр отображения (см. `STORY_RUNTIME_CONTRACT.md` §3).

---

## 4. Thought visibility rules

| `thought_visibility` | Classic VN | Psychological | Mind-reading | Director / Dev |
|---|---|---|---|---|
| `hidden` | скрыто | скрыто | показано | показано |
| `revealed` | скрыто | показано (для POV) | показано | показано |
| `always` | показано | показано | показано | показано |

Правила:
- Видимость определяется **полем источника + текущим режимом**, не переписыванием текста.
- В Dev/Director скрытые мысли видны всегда (рабочий доступ).
- `revealed` ориентирован на POV-персонажа сцены (§5).

---

## 5. POV rules

- У сцены есть `pov_default`; beat может переопределить через beat-level `pov` (POV-switch).
- В Psychological-режиме «revealed-мысли» показываются для **текущего POV-персонажа**.
- POV-переключение внутри сцены допустимо и поддерживается схемой; UX должен ясно обозначать смену POV (визуально/подписью).
- Player может иметь `preferred_pov` в настройках (§7) — влияет на подачу, но не меняет источник.

---

## 6. Choice display / choice density

- Игроку показывается `option_text` каждой доступной ветки (не внутренний `action`/`beats`).
- Недоступные ветки (если у ветки есть условие) — скрыты или заблокированы согласно runtime (§5 контракта).
- **Choice density** — насколько часто появляются выборы — это ощущение от структуры сцен, не отдельное поле. Управляется на авторинге; в настройках игрока (§7) может быть предпочтение `choice_density`, влияющее на подачу (напр. группировка/темп), но **не** на наличие канонических ветвлений.
- После выбора UX может показывать последствия (изменения флагов/отношений) — опционально, по настройке.

---

## 7. Player settings

Настройки живут в `player_state.settings` (см. контракт §6). Ориентировочный профиль:

```json
"settings": {
  "reading_mode": "classic_vn | psychological | mind_reading",
  "preferred_pov": "kira",
  "thought_visibility_pref": "respect_scene | prefer_more | prefer_less",
  "drama_intensity": "low | medium | high",
  "choice_density": "low | medium | high",
  "content_boundaries": ["..."],
  "romance_focus": "low | medium | high",
  "psychological_detail_level": "low | medium | high",
  "director_enabled": false,
  "dev_enabled": false
}
```

Правила:
- Настройки меняют **подачу**, не источник правды.
- Безопасные дефолты: `classic_vn`, director/dev выключены.
- `content_boundaries` согласуются с safety-слоем (§12 схемы) и `RN-SAFETY-STYLE-1`.

---

## 8. Pre-game questionnaire

Опрос перед стартом, который заполняет начальные `settings` (§7).

- Назначение: задать тон/режим/границы до начала истории.
- Примеры вопросов: предпочтительный режим чтения, POV, уровень драматичности, плотность выборов, границы контента, включать ли Director.
- Результат → `player_state.settings`. Может переопределяться во время игры.
- **Статус: DEFERRED** (не MVP). В MVP — разумные дефолты без опроса.

---

## 9. Director Mode

- Пользователь обсуждает сцену с LLM/персонажами: просит варианты реплик, мыслей, действий, альтернативные ветки, стоп-кадры для визуала.
- Director **не является источником правды**: сгенерированное становится частью игры только после **нормализации в V2** и сохранения в JSON (решение `NARRATIVE_DECISIONS_v1.md` §4).
- Director может работать рядом с игрой (authoring) и, в будущем, внутри RenPy (диалоги с персонажами в игре).
- **Статус: target** (полный Director — Later). Базовое обсуждение/генерация рядом с игрой возможны раньше.

---

## 10. Dev / in-place edit mode

**Чётко и жёстко:**

```text
Dev mode НЕ редактирует script.rpy.
Dev mode НЕ меняет flags / branches / ids / pov / type / thought_visibility /
            option_text / prerequisites / next / completion_flag.
Dev mode редактирует ТОЛЬКО текстовые поля beat'а:
  speech
  action
  thought
  narration
  emotion
```

**Workflow (совпадает с `STORY_RUNTIME_CONTRACT.md` §9):**

```text
1. edit current beat (только текстовые поля)
2. guard: изменены только текстовые поля; структура не затронута
3. write back to JSON (источник правды), НЕ в экран
4. schema validation
5. hot-reload
6. continue from same beat_id
```

Правила:
- Любая **структурная** правка (флаги/ветки/ids/pov/type/…) идёт **не** через быстрый dev-путь, а через полную валидацию + Reviewer-гейт.
- Dev-правка текста не ломает continuity и не инвалидирует сейвы (сейв хранит прогресс, не текст).
- **Статус: target feature после live JSON-runtime** — без него правке «некуда писать» (архитектура §7).

---

## 11. What is MVP / what is deferred

**MVP:**
- Classic VN режим.
- Базовый Psychological-показ (revealed-мысли POV).
- Базовое JSON-driven отображение сцены (live чтение источника).
- Developer inspector (просмотр `beat_id`/flags/branch; без полноценного редактора).

**Later (deferred):**
- Mind-reading mode.
- Полный Director mode.
- LLM-диалоги внутри RenPy.
- Pre-game questionnaire.
- Полный in-place editor (write-back).
- Settings UI.
- Браузерный editor/preview.

---

## 12. Current state vs target

| Возможность | Сейчас (факт) | Target |
|---|---|---|
| JSON-driven сцена | нет (SC_003–018 ручной `.rpy`) | live чтение JSON |
| Режимы чтения | нет (захардкожено в `.rpy`) | Classic / Psychological / Mind-reading |
| Видимость мыслей | нет канала мыслей | через `thought_visibility` |
| POV | нет | `pov_default` + beat-level switch |
| Player settings | нет | `player_state.settings` |
| Pre-game questionnaire | нет | deferred |
| Director mode | persona/LLM как отд. система | интегрированный target |
| Dev inspector | частично (rn_workflow audit вне игры) | в игре |
| Dev in-place edit | нет | после live JSON-runtime |

---

## 13. UX invariants

```text
1. Один источник — JSON. Все режимы читают его, отличается только фильтр показа.
2. Режимы не переписывают текст; видимость мыслей = поле источника + режим.
3. Игроку показывается option_text, а не внутренние beats/flags.
4. Настройки меняют подачу, не источник правды.
5. Director/Dev-результат входит в игру только после нормализации в V2 и сохранения в JSON.
6. Dev in-place edit правит только текстовые поля и только в источник; структура — через полную валидацию.
7. Безопасные дефолты: Classic VN, director/dev выключены, границы контента уважаются.
8. Смена POV всегда явно обозначена игроку.
```

---

## Открытые вопросы для реализации / roadmap

- Конкретный UI инспектора и редактора (внутри RenPy vs браузер) → roadmap.
- Как именно `choice_density`/`drama_intensity` влияют на подачу без изменения канона → дизайн позже.
- Объём pre-game questionnaire для первой версии → при разморозке фичи.

> Коммит — через стандартный Narrative workflow (Claude Code), отдельным небольшим commit.
> Следующий документ: `NARRATIVE_ROADMAP.md` (N0F) — фазы N0–N6, выводятся из архитектуры + контракта + этого UX-контракта.
