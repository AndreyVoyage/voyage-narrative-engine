# SCENARIO SCHEMA V2 — SPEC — Voyage Narrative Engine (VNE)

> **Назначение.** Контракт структуры сцены `SCENARIO_SCHEMA_V2`: что хранится в `SCENARIO_*.json` как источник правды.
> Этот документ описывает **что хранится**; *как это исполняется* — в `STORY_RUNTIME_CONTRACT.md` (следующий документ).
> Решения — в `NARRATIVE_DECISIONS_v1.md`, слои — в `NARRATIVE_ARCHITECTURE.md`.
>
> **Статус:** ЧЕРНОВИК v1 спецификации (контракт полей)
> **Дата:** 2026-06-30
> **Narrative baseline:** `5571bd2505715b8f19b092ad1762b8d32449c360`
> **Главный пример:** SC_017 (`SCENARIO_017_SERGEY_WRITES_AGAIN.json`). Вторичный sanity-пример: SC_013 (Appendix).

---

## 0. Границы документа (читать первым)

**V2 — это product/runtime schema, НЕ формат промпта для LLM.**

```text
V2 schema is a product/runtime schema, not an LLM prompt format.
LLM may generate freely, but saved scene data must be normalized into V2
before it becomes source of truth.
```

Следствия:
- LLM (§5 архитектуры) генерирует свободно — прозой, диалогом, как угодно.
- Но **сохранённая сцена** обязана быть нормализована в V2: разделена на beats, с явными speaker/pov/flags, прежде чем стать источником правды.
- Главный дефект V1, который V2 устраняет: речь, действие и мысль **слиты** в строках (`action`, `kira_reaction`, `yakov_reaction`, `sergey_reaction`).

**Чего этот документ НЕ делает:**
- НЕ мигрирует все `SC_003–SC_027` (миграция — отдельная задача; правила — §13).
- НЕ улучшает текстовое качество `SC_020–SC_027`.
- НЕ создаёт `SC_028`.
- НЕ определяет runtime-поведение (это `STORY_RUNTIME_CONTRACT.md`) — здесь только **форма** runtime-хуков.

---

## 1. Top-level metadata

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `schema_version` | string | да | Версия схемы, напр. `"2.0"`. |
| `id` | string | да | ID сцены, напр. `"SC_017"`. |
| `name` | string | да | Человекочитаемое имя. |
| `version` | string | да | Semver контента сцены. |
| `location` | string | да | Ключ локации (см. локали в exporter, напр. `home`). |
| `time` | string | да | Ключ времени (`day`, `morning`, `night`…). |
| `archetype` | string | нет | Архетип сцены или `"none"`. |
| `intensity` | int 0–10 | да | Накал. |
| `risk` | int 0–10 | да | Риск. |
| `duration_minutes` | int | нет | Ожидаемая длительность. |
| `prerequisites` | string[] | да | ID завершённых сцен/условий, напр. `["sc_016_complete"]`. |
| `flags_required` | string[] | да | Флаги, нужные для входа. |
| `emotional_anchors` | string[] | нет | Смысловые якоря (для авторинга/QA). |
| `symbols` | string[] | нет | Символ-коды (мнемоника состояния). |

> `kira_level_start/end`, `sergey_level_start/end` из V1 **переезжают** в `characters[]` (§2), а не остаются на top-level.

---

## 2. Characters registry / references

Сцена ссылается на персонажей по `id` (реестр имён уже частично есть в `tools/vne_to_renpy/exporter.py` → `DISPLAY_NAMES`: kira, sergey, yakov, marina, andrey, olga, egor, maksim). Полная модель персонажа — отдельно (persona-слой §5); здесь — участники сцены и их состояние.

```json
"characters": [
  { "id": "kira",   "display_name": "Кира",   "role": "protagonist", "present": true,  "state_start": "U5-выбор",  "state_end": "U5-выбор" },
  { "id": "yakov",  "display_name": "Яков",    "role": "partner",     "present": true,  "state_start": null,         "state_end": null },
  { "id": "sergey", "display_name": "Сергей",  "role": "third",       "present": false, "state_start": "S5-встреча", "state_end": "S5-встреча" }
]
```

| Поле | Тип | Описание |
|---|---|---|
| `id` | string | Ключ персонажа (соответствует реестру). |
| `display_name` | string | Имя для отображения. |
| `role` | string | Роль в сцене (`protagonist`/`partner`/`third`/…). |
| `present` | bool | Физически присутствует в сцене. (SC_017: Сергей `false`.) |
| `state_start` / `state_end` | string\|null | Уровень/состояние на входе/выходе (заменяет `*_level_start/end`). |

> Детальная модель (`current_state`, `relationship_state`, `visible_traits`, `hidden_traits`) — `DEFERRED` в persona/runtime-документы. Здесь хватает ссылки + состояния в сцене.

---

## 3. Ordered beats — базовая единица сцены

**Beat** — атомарная единица. Смешанные строки V1 **разбиваются** на несколько beats. Beats упорядочены и исполняются по порядку.

Beats живут в двух местах:
- `entry_beats` — то, что проигрывается **до** точки выбора (setup/нарратив).
- `branches[].beats` — то, что проигрывается **внутри** выбранной ветки.

```json
{
  "beat_id": "b1",
  "type": "action",
  "speaker": "kira",
  "pov": "kira",
  "action": "Показывает сообщение Якову сразу — прозрачность прежде реакции.",
  "speech": null,
  "thought": null,
  "thought_visibility": null,
  "narration": null,
  "emotion": "U5-выбор",
  "visual_cue": null
}
```

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `beat_id` | string | да | Уникален в пределах сцены. |
| `type` | enum | да | `dialogue` \| `action` \| `thought` \| `narration`. |
| `speaker` | string\|null | усл. | Персонаж-источник; `null` для `narration`. |
| `pov` | string\|null | да | Чья точка зрения (см. §5). |
| `speech` | string\|null | усл. | Реплика — для `type=dialogue`. |
| `action` | string\|null | усл. | Физическое действие — для `type=action`. |
| `thought` | string\|null | усл. | Внутренний монолог — для `type=thought`. |
| `thought_visibility` | enum\|null | усл. | `hidden` \| `revealed` \| `always` — только для `thought` (см. §6). |
| `narration` | string\|null | усл. | Текст рассказчика — для `type=narration`. |
| `emotion` | string\|null | нет | Эмоц./уровневая метка beat'а. |
| `visual_cue` | string\|null | нет | Хук визуала на уровне beat (§11). |

**Правило заполнения по type:** ровно одно из `speech`/`action`/`thought`/`narration` непусто и соответствует `type`. Остальные `null`.

---

## 4. Speech / action / thought / narration — разделение

Это сердце V2. Один V1-абзац → несколько типизированных beats:

| V1 (слито) | V2 (раздельно) |
|---|---|
| `action: "Показывает… 'Он написал.'"` | `action`-beat + отдельный `dialogue`-beat(ы) |
| `kira_reaction: "'Он написал.' 'Я показываю…'"` | два `dialogue`-beat'а (kira) |
| `yakov_reaction: "'Ты показываешь…' '…'"` | `dialogue`-beat'ы (yakov) |
| (мысли не было) | опциональный `thought`-beat — **новый канал V2** |

Принцип: **никогда не смешивать каналы в одной строке.** Если в V1 действие и реплика были в одной строке — на миграции они разделяются (§13).

---

## 5. POV

| Поле | Значение |
|---|---|
| `pov` (scene default) | POV-владелец по умолчанию для сцены. Для SC_017 — `kira`. |
| `pov` (beat-level) | Может переопределять scene default внутри сцены (POV-switch). |

Правила:
- Каждая сцена имеет `pov_default` (top-level или в choice_point).
- Beat без явного `pov` наследует `pov_default`.
- POV-переключение внутри сцены допускается через beat-level `pov` (включает соответствующие режимы в §7 player experience).
- `thought`-beat виден игроку в зависимости от POV + `thought_visibility` (§6) — детали отображения в `PLAYER_EXPERIENCE_SPEC.md`.

---

## 6. thought_visibility

Применяется только к `type=thought`:

| Значение | Смысл |
|---|---|
| `hidden` | Мысль хранится в источнике, но по умолчанию **не показывается** игроку (доступна mind-reading / director режимам). |
| `revealed` | Показывается в psychological-режиме для POV-персонажа. |
| `always` | Показывается всегда, во всех режимах. |

Это поле — то, что делает возможными режимы чтения (§7 архитектуры) **без переписывания текста**: один и тот же источник, разные фильтры отображения.

---

## 7. Choices

```json
"choice_points": [
  {
    "id": "CP_1",
    "timing": "new_message_arrives",
    "pov_default": "kira",
    "prompt": "Телефон загорается новым сообщением от Сергея… Что делает Кира?",
    "branches": [ /* §8 */ ]
  }
]
```

| Поле | Тип | Описание |
|---|---|---|
| `id` | string | ID точки выбора. |
| `timing` | string | Когда срабатывает (триггер-ключ). |
| `pov_default` | string | POV по умолчанию для веток. |
| `prompt` | string | Вопрос/постановка выбора (то, что в V1 было `question`). |
| `branches` | array | Варианты (§8). |

---

## 8. Branches

В V1 `branch.action` служил **и** описанием выбора, **и** первым действием. В V2 это разделено: `option_text` (что выбирает игрок) отдельно от `beats` (что происходит).

```json
{
  "id": "1A",
  "option_text": "Показать сообщение Якову сразу",
  "beats": [ /* §3 ordered beats */ ],
  "effects": { /* §9 */ },
  "next": { /* §10 */ }
}
```

| Поле | Тип | Описание |
|---|---|---|
| `id` | string | ID ветки (`1A`/`1B`/`1C`). |
| `option_text` | string | Текст выбора для игрока (player-facing). |
| `beats` | beat[] | Что проигрывается при выборе. |
| `effects` | object | Изменения состояния (§9). |
| `next` | object | Runtime-хук перехода (§10). |

---

## 9. Flags / effects

`effects` нормализует то, что в V1 было `branch.flags` + `next_level`:

```json
"effects": {
  "flags_set":     ["kira_shows_message_immediately", "transparency_strengthened", "sc_017_1a"],
  "flags_cleared": [],
  "level_changes": { "kira": "U5-выбор" },
  "relationship_changes": { "kira_yakov": "+transparency" }
}
```

| Поле | Тип | Описание |
|---|---|---|
| `flags_set` | string[] | Флаги, которые ветка ставит. |
| `flags_cleared` | string[] | Флаги, которые ветка снимает. |
| `level_changes` | obj | `character_id → new_state` (заменяет `next_level`). |
| `relationship_changes` | obj | Изменения отношений (опц.). |

> Семантика применения (когда/как исполняется, конфликты, идемпотентность) — в `STORY_RUNTIME_CONTRACT.md`. Здесь только форма.

---

## 10. Runtime hooks (форма, не поведение)

```json
"next": {
  "on_complete": "scene_end",
  "next_scene": null,
  "completion_flag": "sc_017_complete"
}
```

| Поле | Описание |
|---|---|
| `on_complete` | Что считается завершением ветки/сцены (`scene_end` / `goto` / …). |
| `next_scene` | Явный следующий сцен-ID или `null` (выбор делает runtime по prerequisites). |
| `completion_flag` | Флаг завершения сцены (в V1 жил в `flags_set` как `sc_XXX_complete`). |

> **Поведение** этих хуков определяет `STORY_RUNTIME_CONTRACT.md`. Схема лишь декларирует поля.

---

## 11. Visual hooks

```json
"visual": {
  "scene_id": "VS_017",
  "stills": []
}
```

- `visual.scene_id` — заменяет V1 `visual_scene_id`.
- `visual.stills` — стоп-кадры (в т.ч. сгенерированные в LLM director-режиме §5).
- Beat-level `visual_cue` (§3) — хук визуала к конкретному моменту.

---

## 12. Safety / content metadata

```json
"safety": {
  "content_rating": "PG-13",
  "stop_words_enabled": true,
  "present_constraints": "Сергей физически отсутствует и без реплик.",
  "notes": "Сцена проверяет правило прозрачности после SC_016… Нет физической эскалации, принуждения, угроз или игнорирования стоп-слов. Выбор не разрешается."
}
```

- Объединяет V1 `content_rating` + `safety_notes`.
- `stop_words_enabled` — стоп-слова активны (governance-слой).
- Согласуется с `RN-SAFETY-STYLE-1`: safety-метаданные — для проверки/гейтинга и предупреждений, не как переписывание контента.

---

## 13. Migration rules (V1 → V2)

Детерминированные правила. Миграция — **отдельная задача**, не этот документ.

| V1 | V2 |
|---|---|
| `location`, `time`, `archetype`, `intensity`, `risk`, `duration_minutes`, `prerequisites`, `flags_required`, `emotional_anchors`, `symbols` | 1:1 в top-level (§1). |
| `kira_level_start/end`, `sergey_level_start/end` | `characters[].state_start/end` (§2). |
| `visual_scene_id` | `visual.scene_id` (§11). |
| `content_rating` + `safety_notes` | `safety.*` (§12). |
| `choice_points[].question` | `choice_points[].prompt` (§7). |
| `branch.action` | разбить: `option_text` (выбор) + `action`-beat(ы) (§3/§8). |
| `branch.kira_reaction` / `yakov_reaction` / `sergey_reaction` | разбить на `dialogue`-beats по `speaker`, по репликам в кавычках (§4). |
| `branch.next_level` | `effects.level_changes` (§9). |
| `branch.flags` | `effects.flags_set` (§9). |
| `flags_set` (top-level, напр. `sc_XXX_complete`) | `next.completion_flag` + ветка `effects.flags_set`. |

**Дефолты новых полей при миграции:**
- `pov` → scene `pov_default` (для существующих сцен — POV-персонаж, обычно `kira`).
- `type` → выводится: реплики в кавычках → `dialogue`; описательная проза → `action`; рассказчик → `narration`.
- `thought` / `thought_visibility` → **не выдумывать**. Мысли в V1 не было → `thought`-beats не создаются автоматически; добавляются автором/LLM позже (новый канал). Если создаются — дефолт `thought_visibility: "hidden"`.
- `present` → выводится из `safety_notes`/контекста (SC_017: Сергей `present:false`).

**Правило целостности при миграции:** разбиение на beats не меняет смысл — только разделяет каналы. Тон, флаги, ветки, agency сохраняются (проверяется validation-слоем §6 архитектуры).

---

## 14. Worked example — SC_017 «было → стало»

### 14.1 БЫЛО (V1, фрагмент ветки 1A)

```json
{
  "id": "1A",
  "action": "Показывает сообщение Якову сразу. Прозрачность прежде реакции.",
  "kira_reaction": "'Он написал.' 'Я показываю тебе это до ответа. Не потому что прошу разрешения. Потому что не хочу тайны.'",
  "yakov_reaction": "'Ты показываешь мне это до ответа?' 'Тогда я рядом. Но отвечать будешь ты. Я не буду читать за тебя и не буду решать вместо тебя.'",
  "next_level": "U5-выбор",
  "flags": ["kira_shows_message_immediately","yakov_stays_beside_not_over","transparency_strengthened","sc_017_1a"]
}
```

### 14.2 СТАЛО (V2 — полная сцена, faithful split)

```json
{
  "schema_version": "2.0",
  "id": "SC_017",
  "name": "Сергей пишет снова",
  "version": "2.0",
  "location": "home",
  "time": "day",
  "archetype": "none",
  "intensity": 6,
  "risk": 3,
  "duration_minutes": 25,
  "prerequisites": ["sc_016_complete"],
  "flags_required": ["next_step_agreed", "morning_after_cafe"],
  "emotional_anchors": ["новое сообщение от Сергея","тест прозрачности","граница честности под давлением","агентность Киры","выбор остаётся открытым"],
  "symbols": ["S017:U5-выбор→U5-выбор:K+Я:home:day:sergey_writes_again"],
  "characters": [
    { "id": "kira",   "display_name": "Кира",   "role": "protagonist", "present": true,  "state_start": "U5-выбор",  "state_end": "U5-выбор" },
    { "id": "yakov",  "display_name": "Яков",    "role": "partner",     "present": true,  "state_start": null,        "state_end": null },
    { "id": "sergey", "display_name": "Сергей",  "role": "third",       "present": false, "state_start": "S5-встреча","state_end": "S5-встреча" }
  ],
  "pov_default": "kira",
  "entry_beats": [
    { "beat_id": "e1", "type": "narration", "speaker": null, "pov": "kira",
      "narration": "Дом. День. Утренний разговор с Яковом ещё не успел стать привычкой.",
      "speech": null, "action": null, "thought": null, "thought_visibility": null, "emotion": "U5-выбор", "visual_cue": "VS_017" }
  ],
  "choice_points": [
    {
      "id": "CP_1",
      "timing": "new_message_arrives",
      "pov_default": "kira",
      "prompt": "Телефон загорается новым сообщением от Сергея. Что делает Кира?",
      "branches": [
        {
          "id": "1A",
          "option_text": "Показать сообщение Якову сразу",
          "beats": [
            { "beat_id": "1A-b1", "type": "action",   "speaker": "kira",  "pov": "kira", "action": "Показывает сообщение Якову сразу — прозрачность прежде реакции.", "speech": null, "thought": null, "thought_visibility": null, "narration": null, "emotion": "U5-выбор", "visual_cue": null },
            { "beat_id": "1A-b2", "type": "dialogue", "speaker": "kira",  "pov": "kira", "speech": "Он написал.", "action": null, "thought": null, "thought_visibility": null, "narration": null, "emotion": null, "visual_cue": null },
            { "beat_id": "1A-b3", "type": "dialogue", "speaker": "kira",  "pov": "kira", "speech": "Я показываю тебе это до ответа. Не потому что прошу разрешения. Потому что не хочу тайны.", "action": null, "thought": null, "thought_visibility": null, "narration": null, "emotion": null, "visual_cue": null },
            { "beat_id": "1A-b4", "type": "dialogue", "speaker": "yakov", "pov": "kira", "speech": "Ты показываешь мне это до ответа?", "action": null, "thought": null, "thought_visibility": null, "narration": null, "emotion": null, "visual_cue": null },
            { "beat_id": "1A-b5", "type": "dialogue", "speaker": "yakov", "pov": "kira", "speech": "Тогда я рядом. Но отвечать будешь ты. Я не буду читать за тебя и не буду решать вместо тебя.", "action": null, "thought": null, "thought_visibility": null, "narration": null, "emotion": null, "visual_cue": null }
          ],
          "effects": {
            "flags_set": ["kira_shows_message_immediately","yakov_stays_beside_not_over","transparency_strengthened","sc_017_1a"],
            "flags_cleared": [],
            "level_changes": { "kira": "U5-выбор" },
            "relationship_changes": { "kira_yakov": "+transparency" }
          },
          "next": { "on_complete": "scene_end", "next_scene": null, "completion_flag": "sc_017_complete" }
        }
        /* ветки 1B, 1C мигрируются по тем же правилам §13 */
      ]
    }
  ],
  "visual": { "scene_id": "VS_017", "stills": [] },
  "safety": {
    "content_rating": "PG-13",
    "stop_words_enabled": true,
    "present_constraints": "Сергей физически отсутствует и не имеет реплик.",
    "notes": "Сцена проверяет правило прозрачности после SC_016: Кира решает, как обращаться с новым сообщением. Яков остаётся рядом, но не контролирует ответ. Нет физической эскалации, принуждения, угроз или игнорирования стоп-слов. Выбор не разрешается."
  }
}
```

### 14.3 Что V2 ДОБАВЛЯЕТ (иллюстрация нового канала)

В источнике SC_017 мысли не было — поэтому в faithful-split её нет. Но V2 позволяет автору/LLM добавить `thought`-beat, не ломая остальное. Пример того, *куда* и *как* он встанет (иллюстративно, не канон):

```json
{ "beat_id": "1A-t1", "type": "thought", "speaker": "kira", "pov": "kira",
  "thought": "<внутренний монолог Киры>", "thought_visibility": "hidden",
  "speech": null, "action": null, "narration": null, "emotion": "U5-выбор", "visual_cue": null }
```

`thought_visibility: "hidden"` → в Classic VN не виден, в Mind-reading/Director — доступен. Так режимы чтения (§7 архитектуры) работают поверх одного источника.

---

## Appendix A — SC_013 sanity-note (вторичный пример)

SC_013 (`Сообщение от Сергея`, home/morning) короче и проще: ветка `1A` имела `action` + `kira_reaction` + `yakov_reaction` (слитые реплики/мысли в строках вида `"Я — не знаю. Я — думала…"`). Те же правила §13: `action` → `action`-beat + `option_text`; `*_reaction` → `dialogue`-beats по speaker. SC_013 полезна как исторический минимум, но для целевой архитектуры менее показательна, чем SC_017 (нет теста прозрачности, реакции Якова, отсутствующего Сергея и unresolved triangle).

---

## Сводка контракта (быстрый справочник)

```text
scene
├── metadata (§1)
├── characters[] (§2)         id, display_name, role, present, state_start/end
├── pov_default (§5)
├── entry_beats[] (§3/§4)     beat: type, speaker, pov, speech|action|thought|narration,
│                                   thought_visibility, emotion, visual_cue
├── choice_points[] (§7)
│   └── branches[] (§8)       option_text + beats[] + effects + next
│       ├── effects (§9)      flags_set/cleared, level_changes, relationship_changes
│       └── next (§10)        on_complete, next_scene, completion_flag
├── visual (§11)              scene_id, stills[]
└── safety (§12)              content_rating, stop_words_enabled, present_constraints, notes
```

> Коммит — через стандартный Narrative workflow (Claude Code), отдельным небольшим commit.
> Следующий документ: `STORY_RUNTIME_CONTRACT.md` (как это исполняется).
