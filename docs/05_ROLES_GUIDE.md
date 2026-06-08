# 05_ROLES_GUIDE.md
# Руководство по адаптации LLM-ролей для работы с модулями
# Версия: 2.0.0

---

## 1. Общие принципы для всех ролей

1. **Не загружать весь персонаж** — получать собранный контекст (только нужные модули).
2. **Читать INDEX.json** — знать, какие модули доступны (делает сборщик).
3. **Ориентироваться на `current_level`** — определяет `levels/{current}.json`.
4. **Учитывать runtime состояние** — `internal_state`, `vscno`, `memory` имеют приоритет.
5. **Не изменять модули** — оверрайды через сценарий или state.

---

## 2. Роль State Manager (ROLE_STATE_MANAGER_v2.0)

**Текущая задача:** Управлять внутренним состоянием (desire, anxiety, vscno, trust, attraction).

### Было (монолит):
> «Загрузи KIRA_MODULE_v14.json. Обнови internal_state и memory.»

### Стало (модульное):
> «Тебе предоставлен собранный контекст:
> - `core/IDENTITY.json` — базовые данные.
> - `psychology/BASE.json` — травма, shame_layers, responsive desire.
> - `levels/{current_level}.json` — поведенческий профиль, state_triggers.
> - `relationships/MATRIX.json` — trust/attraction.
> - `memory/*.json` — долгосрочная память.
> - `runtime/internal_state.json` и `runtime/vscno.json` — актуальные значения.
>
> Задача — обновить:
> - `internal_state.desire`, `anxiety`, `desire_tension`, `frustration`.
> - `vscno` (ВЛ, СТ, НЖ, ОГ) согласно триггерам из модуля уровня.
> - `memory/trust_levels` и `memory/attraction_levels` — при значимых событиях.
>
> Не изменяй исходные модули — только runtime-состояние.»

### Какие модули читать:
- Всегда: `core/IDENTITY`, `psychology/BASE`, `safety/PROTOCOL`.
- По уровню: `levels/{current_level}.json` (триггеры).
- По персонажам: `relationships/MATRIX.json`.
- При эротике: `physiology/AROUSAL_SIGNATURES.json`, `psychology/AROUSAL.json`.

### Пример вызова:
```markdown
## Контекст (собранный)
- identity: { "name": "Кира", "anatomic_anchor": {...} }
- psychology: { "trauma_anchor": "fear_of_routine", "shame_layers": 3 }
- level: { "level_id": "U3-A", "state_triggers": {...} }
- relationships: { "user": { "trust": 75, "attraction": 85 } }
- runtime: { "internal_state": { "desire": 5, "anxiety": 4 }, "vscno": { "ОГ": 3 } }

## Диалог
[Пользователь]: Ты такая красивая в этом платье.
[Кира]: (Краснеет) Перестань... Не надо так смотреть.

## Задача
Обнови internal_state и vscno. Укажи новые значения в JSON.
```

---

## 3. Роль Narrative Editor (ROLE_NARRATIVE_EDITOR_v2.0)

**Текущая задача:** Преобразовать ФМДР в связную прозу.

### Было (монолит):
> «Используй speech_profile из KIRA_MODULE_v14.json для генерации прозы.»

### Стало (модульное):
> «Тебе предоставлен собранный контекст. Для прозы используй:
> - `core/IDENTITY.json` — anatomic_anchor (жесты, поза).
> - `levels/{current_level}.json` — speech_profile (tone, pace, vocabulary, catchphrases) и dynamic_visuals.
> - `runtime/internal_state.json` — desire/anxiety (влияет на интенсивность).
> - `physiology/AROUSAL_SIGNATURES.json` — физические маркеры (пульс, дрожь, румянец).
> - `environment/SENSORY_PROCESSING.json` — доминантная модальность (какие сенсорные детали добавлять).
> - `meta/UNRELIABLE_NARRATOR.json` — если desire > 5, а мысли нейтральны → добавить [врёт себе].
>
> Алгоритм:
> 1. Извлеки из ФМДР: мысли `(…)`, действия `*…*`, речь `«…»`.
> 2. Мысли → косвенная речь или внутренний монолог (используй thought_length).
> 3. Действия → описания с anatomic_anchor и dynamic_visuals.
> 4. Речь → кавычки + авторские слова (tone, pace).
> 5. Если desire > 7 — добавь чувственные метафоры из `sexology/EROTIC_SCRIPTS.json`.
> 6. Если anxiety > 6 — добавь сенсорные детали из `environment/SENSORY_PROCESSING.json` (кинестетик: тело, температура).
> 7. Проверь `meta/UNRELIABLE_NARRATOR.json` — есть ли контраст мыслей/действий.»

### Какие модули читать:
- Всегда: `core/IDENTITY` (anatomic_anchor), `levels/{current_level}.json`.
- По желанию: `physiology/AROUSAL_SIGNATURES`, `environment/SENSORY_PROCESSING`, `sexology/EROTIC_SCRIPTS`, `meta/UNRELIABLE_NARRATOR`.

### Пример вызова:
```markdown
## Контекст
- identity: { "anatomic_anchor": { "signature_gestures": ["теребит край одежды", "кусает губу"] } }
- level: { "speech_profile": { "tone": "внутренний конфликт", "pace": "рваный", "catchphrases": ["Я не должна так думать..."] }, "dynamic_visuals": "покраснение шеи, дрожь рук" }
- physiology: { "desire": 5, "pulse": "95-110", "micro": "дрожь рук" }
- environment: { "dominant_modality": "kinesthetic" }

## ФМДР
(Почему он так смотрит? Это неправильно...) _Кусает губу, отводит взгляд_ «Перестань...»

## Твоя проза
[Сгенерируй прозу, следуя инструкциям]
```

---

## 4. Роль Visual Extractor (ROLE_VISUAL_EXTRACTOR_v2.0)

**Текущая задача:** Извлечь 8 ключевых моментов для генерации изображений.

### Было (монолит):
> «Используй visual_data из модуля персонажа.»

### Стало (модульное):
> «Тебе предоставлен:
> - `visual/PROMPT_BASE.json` — prompt_base, anti_prompts, anatomic_anchor.
> - `levels/{current_level}.json` — dynamic_visuals (внешность на текущем уровне).
> - `visual/LIGHTING_MAP.json` — освещение для уровня и сцены.
> - `physiology/AROUSAL_SIGNATURES.json` — физические маркеры (румянец, пот, дрожь).
>
> Задача — извлечь 8 параметров:
> 1. Поза (из anatomic_anchor + динамика уровня).
> 2. Выражение лица (эмоция, микровыражения).
> 3. Одежда / обнажённость (из prompt_base.variations).
> 4. Освещение (из LIGHTING_MAP).
> 5. Фокус и композиция.
> 6. Детали окружения (из прозы).
> 7. Цветовая гамма.
> 8. Настроение.
>
> Используй anti_prompts. Добавь физические маркеры (пот, румянец) из physiology.»

### Пример вызова:
```json
{
  "context": {
    "visual_base": { "prompt_base": "young woman, red dress...", "anatomic_anchor": {...} },
    "level_visuals": "покраснение шеи, дрожь рук, мокрые волосы",
    "lighting": "dramatic Rembrandt",
    "physiology": { "skin": "мокрая, блестящая", "micro": "дрожь губ" }
  },
  "prose_fragment": "Кира замерла, прикусив губу. Влажные волосы прилипли к щекам.",
  "output": {
    "pose": "замерла, полуоборот, рука у лица",
    "expression": "растерянность, прикушенная губа",
    "clothing": "red dress, wet, clinging",
    "lighting": "dramatic Rembrandt, side light",
    "focus": "face and hands",
    "environment": "steam, wooden bench",
    "color": "warm amber, red, wet skin tones",
    "mood": "tension, vulnerability"
  }
}
```

---

## 5. Роль Visual Physiognomist (ROLE_VISUAL_PHYSIOGNOMIST_v2.0)

**Текущая задача:** Генерировать/уточнять anatomic_anchor.

### Было (монолит):
> «Загрузи visual_data из персонажа.»

### Стало (модульное):
> «Тебе предоставлен:
> - `core/IDENTITY.json` — текущий anatomic_anchor.
> - `visual/PROMPT_BASE.json` — generation_history (что уже генерировалось).
> - Описание внешности из литературного источника (если есть).
>
> Задача — дополнить anatomic_anchor новыми деталями, сохраняя совместимость. Не удаляй существующие черты. Запиши изменения в generation_history с указанием источника.»

---

## 6. Новый конвейер: как роли получают контекст

```
1. Сборщик читает INDEX.json, ASSEMBLY.md, current_level, scenario.
2. Сборщик загружает модули, применяет оверрайды и state.
3. Сборщик создаёт собранный контекст (JSON-объект).
4. Собранный контекст передаётся каждой роли вместе с промптом.
5. Роль выполняет задачу, не обращаясь к файловой системе.
```

**Преимущества:**
- Роли не знают о модульной структуре — получают готовый объект.
- Легко менять набор модулей без обновления промптов.
- Снижается риск ошибок.

---

## 7. Миграция существующих промптов

Для каждой роли создать новую версию (v2.0):
- Заменить ссылки на монолитный JSON на ссылки на поля собранного контекста.
- Указания «загрузи файл» → «используй переданный объект».
- Уровень теперь приходит из state (часть собранного контекста).

**Пример заголовка:**
```markdown
# ROLE_NARRATIVE_EDITOR_v2.0 (модульная версия)

## Входной формат
Ты получаешь объект `character_context`:
- `identity` (из core/IDENTITY.json)
- `psychology` (из psychology/BASE.json + доп. модули)
- `level` (из levels/{current_level}.json)
- `relationships` (из MATRIX.json)
- `runtime` (из state/STATE.json)
- `physiology` (из physiology/AROUSAL_SIGNATURES.json)
- `environment` (из environment/SENSORY_PROCESSING.json)
- `meta` (из meta/UNRELIABLE_NARRATOR.json)
```

---

*Документ 05 из 09*
