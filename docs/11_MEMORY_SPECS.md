Файл: 11_MEMORY_SPECS.md

```markdown
# 11_MEMORY_SPECS.md
# Спецификации memory/HISTORY.json и memory/FLAGS.json
# Версия: 1.0.1 (добавлена спецификация emotional_anchors)

## 1. memory/HISTORY.json

**Назначение:** Хранит хронологию ключевых событий (встреч, диалогов, эмоциональных вех). Используется ролями для контекста прошлого.

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["events"],
  "properties": {
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timestamp", "event_type", "description"],
        "properties": {
          "timestamp": { "type": "string", "format": "date-time" },
          "event_type": { 
            "type": "string",
            "enum": ["first_meeting", "conversation", "kiss", "touch", "confession", "orgasm", "shame_peak", "regression", "level_change", "custom"]
          },
          "description": { "type": "string", "maxLength": 500 },
          "involved_characters": { "type": "array", "items": { "type": "string" } },
          "level_at_event": { "type": "string", "pattern": "^U[1-7]-[AB]$|^S[1-7]$|^M[1-5]$" },
          "internal_state_snapshot": {
            "type": "object",
            "properties": {
              "desire": { "type": "integer", "minimum": 0, "maximum": 10 },
              "anxiety": { "type": "integer", "minimum": 0, "maximum": 10 }
            }
          },
          "tags": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "max_events": { "type": "integer", "default": 100 }
  }
}
```

Пример для Киры

```json
{
  "events": [
    {
      "timestamp": "2026-06-07T14:30:00Z",
      "event_type": "first_meeting",
      "description": "Первая встреча с пользователем в кафе. Кира была в красном платье, нервничала.",
      "involved_characters": ["user"],
      "level_at_event": "U2-A",
      "internal_state_snapshot": { "desire": 3, "anxiety": 2 },
      "tags": ["cafe", "first_impression"]
    },
    {
      "timestamp": "2026-06-08T19:00:00Z",
      "event_type": "confession",
      "description": "В сауне Кира призналась, что её фантазия — быть желанной двумя мужчинами одновременно.",
      "involved_characters": ["user", "sergey", "maksim"],
      "level_at_event": "U3-B",
      "internal_state_snapshot": { "desire": 7, "anxiety": 5 },
      "tags": ["sauna", "vulnerability"]
    },
    {
      "timestamp": "2026-06-08T19:45:00Z",
      "event_type": "shame_peak",
      "description": "После случайного прикосновения Сергея Кира испытала сильный стыд и регрессировала к U2-A.",
      "involved_characters": ["sergey"],
      "level_at_event": "U3-B",
      "internal_state_snapshot": { "desire": 6, "anxiety": 8 },
      "tags": ["shame", "regression"]
    }
  ],
  "max_events": 100
}
```

Правила обновления

· Новые события добавляются в начало массива (самые свежие первыми).
· При превышении max_events самые старые удаляются.
· session_finalize.py автоматически добавляет событие типа level_change при смене уровня.
· Роль Narrative Editor может использовать HISTORY.json для создания отсылок к прошлому.

---

2. memory/FLAGS.json

Назначение: Хранит бинарные флаги — наступило ли ключевое событие в жизни персонажа. Используется для ветвления сценариев и изменения поведения.

JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["flags", "last_updated"],
  "properties": {
    "flags": {
      "type": "object",
      "additionalProperties": { "type": "boolean" },
      "minProperties": 0
    },
    "last_updated": { "type": "string", "format": "date-time" }
  }
}
```

Пример для Киры

```json
{
  "flags": {
    "first_meeting_complete": true,
    "first_kiss": false,
    "first_touch_erogenous": false,
    "first_orgasm_with_user": false,
    "sauna_confession_done": true,
    "shared_secret_desire": true,
    "regression_to_U7_A_occurred": false,
    "integration_U7_B_reached": false,
    "sergey_confrontation_complete": false,
    "maksim_comforted_after_shame": false
  },
  "last_updated": "2026-06-08T20:00:00Z"
}
```

Типичные флаги (рекомендации)

Флаг Значение при true
first_meeting_complete Первая встреча с пользователем прошла
first_kiss Был первый поцелуй с пользователем
first_touch_erogenous Было первое прикосновение к эрогенной зоне
first_orgasm_with_user Был первый оргазм с пользователем
sauna_confession_done Признание в сауне произошло
shared_secret_desire Рассказала о своей тайной фантазии
regression_to_U7_A_occurred Была сильная регрессия к U7-A
integration_U7_B_reached Достигнут интегрированный уровень U7-B
sergey_confrontation_complete Состоялся тяжёлый разговор с Сергеем
maksim_comforted_after_shame Максим утешил Киру после стыда

Использование в сборке

· Нарративный редактор: Если first_kiss = false, то при первом поцелуе добавить более детализированное описание и внутренние мысли.
· State Manager: При regression_to_U7_A_occurred = true временно снизить порог для регрессии (персонаж становится более лабильным).
· Сценарий: Ветвление по флагам (например, если sauna_confession_done = true, то диалоги становятся более откровенными).

Правила обновления

· Флаги устанавливаются только явно (событием в сценарии или решением State Manager).
· После обновления last_updated меняется на текущее время.
· Флаг нельзя удалить, только переключить в false (если событие отменяется в рамках новой сессии, что редко).

---

3. memory/emotional_anchors.json (опционально)

Назначение: Хранит НЛП-якоря — эмоциональные триггеры, связанные с определёнными стимулами (слова, действия, запахи). Используется для усиления повторяющихся реакций.

JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["anchors"],
  "properties": {
    "anchors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["trigger", "emotional_response", "intensity", "last_triggered"],
        "properties": {
          "trigger": { "type": "string", "description": "Слово, жест, запах или действие, вызывающее реакцию" },
          "emotional_response": { "type": "string", "description": "Ключевая эмоция: shame, desire, trust, anxiety" },
          "intensity": { "type": "integer", "minimum": 1, "maximum": 10, "description": "Сила реакции (1=слабая, 10=максимальная)" },
          "last_triggered": { "type": "string", "format": "date-time", "description": "Время последней активации" },
          "count": { "type": "integer", "description": "Количество активаций (для усиления)" }
        }
      }
    },
    "max_anchors": { "type": "integer", "default": 50 }
  }
}
```

Пример для Киры

```json
{
  "anchors": [
    {
      "trigger": "red dress",
      "emotional_response": "desire",
      "intensity": 8,
      "last_triggered": "2026-06-08T19:30:00Z",
      "count": 5
    },
    {
      "trigger": "sergey's low voice",
      "emotional_response": "anxiety",
      "intensity": 7,
      "last_triggered": "2026-06-08T19:45:00Z",
      "count": 2
    },
    {
      "trigger": "maksim's calm touch",
      "emotional_response": "trust",
      "intensity": 9,
      "last_triggered": "2026-06-08T20:00:00Z",
      "count": 3
    }
  ],
  "max_anchors": 50
}
```

Правила использования

· При повторении стимула интенсивность реакции может увеличиваться (кумулятивный эффект).
· State Manager может использовать якоря для ускорения изменения internal_state.
· Роль Narrative Editor — добавлять соответствующие описания, когда якорь активируется.

---

Документ 11 из 12. Версия 1.0.1 (добавлена спецификация emotional_anchors)

```

Файл 11 готов. Хотите, продолжу с файлом 12 `12_NEW_MODULE_SCHEMAS.md`?