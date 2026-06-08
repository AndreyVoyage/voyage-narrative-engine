Файл: 05_ROLES_GUIDE_v2.1.md

```markdown
# 05_ROLES_GUIDE.md
# Руководство по адаптации LLM-ролей для работы с модулями
# Версия: 2.1.0 (добавлены emotional_anchors, FLAGS с last_updated, правило VSCNO приоритета)

## 1. Общие принципы для всех ролей

1. **Не загружать весь персонаж** — получать собранный контекст (только нужные модули).
2. **Читать INDEX.json** — знать, какие модули доступны (делает сборщик).
3. **Ориентироваться на `current_level`** — определяет `levels/{current}.json`.
4. **Учитывать runtime состояние** — `internal_state`, `vscno`, `memory` имеют приоритет.
5. **Не изменять модули** — оверрайды через сценарий или state.

## 2. Роль State Manager (ROLE_STATE_MANAGER_v2.1)

**Текущая задача:** Управлять внутренним состоянием (desire, anxiety, vscno, trust, attraction, флаги, якоря).

### Было (монолит):
> «Загрузи KIRA_MODULE_v14.json. Обнови internal_state и memory.»

### Стало (модульное):
> «Тебе предоставлен собранный контекст:
> - `core/IDENTITY.json` — базовые данные.
> - `psychology/BASE.json` — травма, shame_layers, responsive desire.
> - `levels/{current_level}.json` — поведенческий профиль, state_triggers.
> - `relationships/MATRIX.json` — trust/attraction.
> - `memory/*.json` — долгосрочная память (TRUST, ATTRACTION, HISTORY, FLAGS, emotional_anchors).
> - `runtime/internal_state.json` и `runtime/vscno.json` — актуальные значения.
>
> Задача — обновить:
> - `internal_state.desire`, `anxiety`, `desire_tension`, `frustration`.
> - `vscno` (ВЛ, СТ, НЖ, ОГ) согласно триггерам из модуля уровня **с соблюдением приоритета VSCNO**.
> - `memory/trust_levels` и `memory/attraction_levels` — при значимых событиях.
> - `memory/FLAGS.json` — установить флаги (например, `first_kiss = true`) и обновить `last_updated`.
> - `memory/emotional_anchors.json` — при повторении стимула увеличить `count`, при достижении порога — повысить `intensity` (кумулятивный эффект).
>
> Не изменяй исходные модули — только runtime-состояние.»

### Дополнительные правила для State Manager:

- **Приоритет VSCNO:** При обновлении VSCNO сумма осей должна оставаться 10. Если сумма нарушается, корректируй в порядке приоритета: **ВЛ → ОГ → НЖ → СТ** (ВЛ сохраняется первым, СТ — последним).
- **Конфликт триггеров:** Если несколько триггеров изменяют одно поле `internal_state`, применяй изменение с **максимальным абсолютным значением**.
- **Флаги:** После изменения любого флага обязательно обнови `last_updated` в `memory/FLAGS.json`.
- **Якоря:** При срабатывании якоря (например, стимул `"red dress"`) увеличь `count` на 1. Если `count` достиг кратного 5 (5, 10, 15…), повысь `intensity` на 1 (но не выше 10).

### Какие модули читать:
- Всегда: `core/IDENTITY`, `psychology/BASE`, `safety/PROTOCOL`.
- По уровню: `levels/{current_level}.json` (триггеры).
- По персонажам: `relationships/MATRIX.json`.
- При эротике: `physiology/AROUSAL_SIGNATURES.json`, `psychology/AROUSAL.json`.
- Для памяти: `memory/FLAGS.json`, `memory/emotional_anchors.json`.

### Пример вызова:
```markdown
## Контекст (собранный)
- identity: { "name": "Кира", "anatomic_anchor": {...} }
- psychology: { "trauma_anchor": "fear_of_routine", "shame_layers": 3 }
- level: { "level_id": "U3-A", "state_triggers": {...} }
- relationships: { "user": { "trust": 75, "attraction": 85 } }
- runtime: { "internal_state": { "desire": 5, "anxiety": 4 }, "vscno": { "ОГ": 3 } }
- memory: { "flags": { "first_kiss": false, "last_updated": "2026-06-08T19:00:00Z" } }

## Диалог
[Пользователь]: Ты такая красивая в этом платье.
[Кира]: (Краснеет) Перестань... Не надо так смотреть.

## Задача
Обнови internal_state, vscno, флаги, якоря. Укажи новые значения в JSON.
```

3. Роль Narrative Editor (ROLE_NARRATIVE_EDITOR_v2.1)

Текущая задача: Преобразовать ФМДР в связную прозу.

Было (монолит):

«Используй speech_profile из KIRA_MODULE_v14.json для генерации прозы.»

Стало (модульное):

«Тебе предоставлен собранный контекст. Для прозы используй:

· core/IDENTITY.json — anatomic_anchor (жесты, поза).
· levels/{current_level}.json — speech_profile (tone, pace, vocabulary, catchphrases) и dynamic_visuals.
· runtime/internal_state.json — desire/anxiety (влияет на интенсивность).
· physiology/AROUSAL_SIGNATURES.json — физические маркеры (пульс, дрожь, румянец).
· environment/SENSORY_PROCESSING.json — доминантная модальность (какие сенсорные детали добавлять).
· meta/UNRELIABLE_NARRATOR.json — если desire > 5, а мысли нейтральны → добавить [врёт себе].
· memory/emotional_anchors.json — если в сцене встречается триггер якоря, добавить соответствующее описание, усиленное intensity (например, «Красное платье снова обожгло её жаром»).
· memory/FLAGS.json — использовать флаги для изменения тона (например, если first_meeting_complete = false, добавлять неуверенность).

Алгоритм:

1. Извлеки из ФМДР: мысли (…), действия *…*, речь «…».
2. Мысли → косвенная речь или внутренний монолог (используй thought_length).
3. Действия → описания с anatomic_anchor и dynamic_visuals.
4. Речь → кавычки + авторские слова (tone, pace).
5. Если desire > 7 — добавь чувственные метафоры из sexology/EROTIC_SCRIPTS.json.
6. Если anxiety > 6 — добавь сенсорные детали из environment/SENSORY_PROCESSING.json (кинестетик: тело, температура).
7. Проверь meta/UNRELIABLE_NARRATOR.json — есть ли контраст мыслей/действий.
8. Если memory/emotional_anchors.json содержит активный якорь (триггер совпал), добавь фразу, отражающую накопленную интенсивность (например, при intensity=9 — «в её груди разгорался пожар»).`

Пример использования emotional_anchors:

```json
// memory/emotional_anchors.json (фрагмент)
"anchors": [
  { "trigger": "red dress", "emotional_response": "desire", "intensity": 8, "count": 5 }
]

// В прозе при появлении триггера:
"Красное платье снова коснулось её кожи — жар разлился по телу быстрее, чем в прошлый раз."
```

4. Роль Visual Extractor (ROLE_VISUAL_EXTRACTOR_v2.0)

Текущая задача: Извлечь 8 ключевых моментов для генерации изображений.

(без изменений по сравнению с v2.0, см. предыдущую версию)

5. Роль Visual Physiognomist (ROLE_VISUAL_PHYSIOGNOMIST_v2.0)

Текущая задача: Генерировать/уточнять anatomic_anchor.

(без изменений по сравнению с v2.0)

6. Новый конвейер: как роли получают контекст

```
1. Сборщик читает INDEX.json, ASSEMBLY.md, current_level, scenario, ag_level.
2. Сборщик загружает модули, применяет оверрайды и state.
3. Сборщик создаёт собранный контекст (JSON-объект).
4. Собранный контекст передаётся каждой роли вместе с промптом.
5. Роль выполняет задачу, не обращаясь к файловой системе.
```

7. Миграция существующих промптов

Для каждой роли создать новую версию (v2.1):

· Заменить ссылки на монолитный JSON на ссылки на поля собранного контекста.
· Указания «загрузи файл» → «используй переданный объект».
· Уровень теперь приходит из state (часть собранного контекста).
· Добавить работу с memory/emotional_anchors.json и memory/FLAGS.json (с last_updated).

---

Документ 05 из 12. Версия 2.1.0

```

Файл готов к сохранению под именем `05_ROLES_GUIDE_v2.1.md`.