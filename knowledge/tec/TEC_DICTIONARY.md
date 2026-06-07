# TEC Dictionary — Voyage Narrative Engine v1.0

> **Назначение:** Единый справочник техник (TEC — Theoretical & Empirical Constructs), на который ссылаются роли Persona Analyst, TEC Validator, Scenario Writer и State Manager.
> **Контекст:** Voyage Narrative Engine v2.0+ (CORE + подуровни A/Б + режимы default/shy_to_bitch/shy_to_bloom)
> **Формат:** Для каждого TEC-кода указаны обязательные JSON-пути, типы данных, диапазоны и правила валидации.

---

## Метаданные справочника

| Поле | Значение |
|------|----------|
| `tec_version` | 1.0.0 |
| `core_compatibility` | VOYAGE_NARRATIVE_CORE_v2.0 |
| `schema_compatibility` | persona_schema_v3.2 |
| `last_updated` | 2026-06-07 |

---

## TEC_003: Responsive Desire (Basson Model)

> **Описание:** Модель отзывчивого желания (Rosemary Basson). Желание возникает не спонтанно, а в ответ на стимул. Критично для режима `shy_to_bitch` (уровни У1-А — У3-Б).

### Обязательные поля

```json
{
  "psychology": {
    "responsive_desire": {
      "active_mode": "string (enum: shy_to_bitch | default)",
      "applicable_levels": ["array of strings (U1-A..U7-Б)"],
      "baseline_state": "string (e.g. spontaneous_denial)",
      "trigger_condition": "string (описание стимула)",
      "response_state": "string (состояние после срабатывания)",
      "shame_peak": "integer (0-10)",
      "desire_peak": "integer (0-10)",
      "source": "string (Basson_R_2001)",
      "validation_required": "boolean"
    }
  }
}
```

### Валидация
- `shame_peak` должен быть ≥ `desire_peak` на уровнях У1-А — У3-А (стыд доминирует).
- `desire_peak` должен превышать `shame_peak` на У3-Б и выше (желание пробивается).
- `applicable_levels` должны пересекаться с `modes.shy_to_bitch.emotional_level_map`.

---

## TEC_005: Attachment × Sexual Desire (Birnbaum et al.)

> **Описание:** Связь стиля привязанности с сексуальным желанием. Определяет, как персонаж реагирует на близость/отстранение партнёра.

### Обязательные поля

```json
{
  "psychology": {
    "attachment_sexuality": {
      "style": "string (enum: anxious_preoccupied | avoidant_dismissive | secure | fearful_avoidant)",
      "manifestation": {
        "reassurance_seeking": "boolean",
        "desire_pattern": "string",
        "anxiety_triggers": ["array of strings"],
        "desire_peak_after_stimulus": "string"
      },
      "compatibility": {"type": "object"},
      "user_compatibility": {"type": "object"}
    }
  }
}
```

### Валидация
- Для `shy_to_bitch` рекомендуется `anxious_preoccupied` или `fearful_avoidant`.
- `reassurance_seeking` должен быть `true` для `anxious_preoccupied`.
- `desire_pattern` для anxious: `increases_with_partner_withdrawal` (токсичное притяжение).

---

## TEC_006: Arousal Specificity (Chivers et al.)

> **Описание:** Рассогласование физиологической и психологической готовности. Критично для подуровней У4-А (срыв) и У4-Б (своеволие).

### Обязательные поля

```json
{
  "psychology": {
    "arousal_specificity": {
      "physiological_readiness": {
        "description": "string",
        "manifestation_levels": {"type": "object"}
      },
      "subjective_desire": {
        "description": "string",
        "requires": ["array of strings"],
        "accelerated_by": "string",
        "decelerated_by": "string"
      },
      "body_mind_lag": {
        "description": "string",
        "levels_affected": ["array of strings"],
        "narrative_device": "string"
      }
    }
  }
}
```

### Валидация
- На У4-А: `physiological_readiness` > `subjective_desire` (тело опережает разум).
- На У4-Б: `subjective_desire` догоняет или превышает физиологическую.
- `body_mind_lag.levels_affected` должен включать У1-А — У2-А (ранние уровни).

---

## TEC_007: Erotic Plasticity (Baumeister)

> **Описание:** Способность к эротической пластичности — насколько легко персонаж меняет сценарий/границы под влиянием контекста.

### Обязательные поля

```json
{
  "psychology": {
    "erotic_plasticity": {
      "level": "integer (0-10)",
      "can_rewrite_script": "boolean",
      "identity_shift_speed": "string (enum: slow | medium | fast | very_fast | none)",
      "scripts": {"type": "object"},
      "script_conflict": {"type": "object"},
      "masks": {"type": "object"},
      "core_identity": "string",
      "core_stability": "string",
      "stable_script": "string",
      "plasticity_speed": "string",
      "script_awareness": "string",
      "rapid_transitions": "boolean"
    }
  }
}
```

### Валидация
- Для `shy_to_bitch` рекомендуется `level` ≥ 6 (высокая пластичность — невинность легко переписывается).
- `can_rewrite_script` должно быть `true` для У5+ (стерва переписывает сценарий).
- `identity_shift_speed` должен быть `fast` или `very_fast` для Киры.
- `scripts` должен содержать `good_girl`, `bitch_in_control`, `integrated_self`.

---

## TEC_008: Object of Desire Self‑Consciousness (Bogaert & Brotto)

> **Описание:** Самосознание как объекта желания. Критично для подуровней У2-Б (первая провокация) — У5-Б (стерва-натура).

### Обязательные поля

```json
{
  "psychology": {
    "object_of_desire": {
      "public_odsc": {"type": "object"},
      "private_odsc": {"type": "object"},
      "unconscious_tests": {"type": "object"},
      "odsc_ownership": {"type": "object"},
      "odsc_as_command": {"type": "object"},
      "odsc_loss_fear": {"type": "object"},
      "odsc_integrated": {"type": "object"},
      "odsc_roles": {"type": "object"}
    }
  }
}
```

### Валидация
- `public_odsc.active` должен быть `false` на У1-А — У2-А (не осознаёт себя объектом).
- `private_odsc.active` должен резко расти на У2-Б — У3-Б (осознание в одиночестве).
- `odsc_integrated` должно достигаться только на У7-Б.
- `odsc_roles` должен содержать ссылки на `user`, `sergey`, `maksim`.

---

## TEC_M_001: Male Attraction Tactics (Brown et al.)

> **Описание:** Тактики мужского привлечения. Для мужских персонажей — собственные тактики; для женских — реакция на них.

### Для женских персонажей (Кира, Марина)

```json
{
  "psychology": {
    "response_to_male_tactics": {
      "good_genes": {
        "active_levels": ["array of strings"],
        "typical_male": "string",
        "effect": "string",
        "description": "string"
      },
      "good_partner": {
        "active_levels": ["array of strings"],
        "typical_male": "string",
        "effect": "string",
        "description": "string"
      }
    }
  }
}
```

### Для мужских персонажей (Сергей, Максим)

```json
{
  "male_specific": {
    "attraction_tactics": {
      "source": "string",
      "primary": "string (enum: short_term | long_term)",
      "signals": ["array of strings"],
      "contexts": ["array of strings"],
      "mask_adaptation_levels": ["array of strings"],
      "mask_fail_probability": "number (0-1)",
      "consistency": "string"
    }
  }
}
```

### Валидация
- `sergey.primary` должен быть `short_term` (доминирование, юмор, отличительность).
- `maksim.primary` должен быть `long_term` (ресурсы, благожелательность, моногамия).
- `mask_fail_probability` у Сергея должен быть ≥ 0.3 (низкая пластичность Baumeister).
- `mask_fail_probability` у Максима должен быть ≤ 0.2 (высокая согласованность).

---

## TEC_M_002: Male Attachment Desire (Mizrahi et al.)

> **Описание:** Как мужское желание зависит от стиля привязанности и отзывчивости партнёрши.

### Для мужских персонажей

```json
{
  "male_specific": {
    "attachment_desire": {
      "source": "string",
      "style": "string (enum: avoidant_dismissive | secure | anxious_preoccupied)",
      "responsiveness_effect": "string (enum: desire_suppression | desire_increase)",
      "withdrawal_effect": "string (enum: desire_increase_paradoxical | anxiety_increase_desire_decrease)",
      "typical_phrases": ["array of strings"],
      "proactive_withdrawal": "boolean",
      "anxious_care": "boolean"
    }
  }
}
```

### Для женских персонажей (реакция на мужское отстранение)

```json
{
  "psychology": {
    "attachment_response": {
      "to_sergey_withdrawal": {
        "effect": "string",
        "description": "string",
        "mechanism": "string"
      },
      "to_maksim_responsiveness": {
        "effect": "string",
        "description": "string",
        "mechanism": "string"
      }
    }
  }
}
```

### Валидация
- `sergey.responsiveness_effect` должен быть `desire_suppression` (avoidant: близость гасит желание).
- `sergey.withdrawal_effect` должен быть `desire_increase_paradoxical` (отстранение = вызов).
- `maksim.responsiveness_effect` должен быть `desire_increase` (secure: близость усиливает желание).
- `to_sergey_withdrawal.effect` у Киры должен включать `desire_tension +1` (токсичное притяжение).

---

## TEC_M_003: Mate Retention (Nascimento et al.)

> **Описание:** Тактики удержания партнёрши. Применимо к мужским персонажам в роли ally/rival/catalyst.

### Для мужских персонажей

```json
{
  "male_specific": {
    "mate_retention": {
      "source": "string",
      "style": "string (enum: benefit_provisioning | cost_inflicting | mixed)",
      "tactics": ["array of strings"],
      "under_threat": "string",
      "proactive_care": "boolean",
      "proactive_withdrawal": "boolean"
    }
  }
}
```

### Валидация
- `sergey.style` должен быть `cost_inflicting` (ревность, обесценивание, эмоциональное отстранение).
- `maksim.style` должен быть `benefit_provisioning` (ресурсы, забота, время).
- `sergey.proactive_withdrawal` должен быть `true`.
- `maksim.proactive_care` должен быть `true`.

---

## Runtime-поля (не TEC, но обязательны для движка)

### internal_state

```json
{
  "internal_state": {
    "desire": "integer (0-10)",
    "anxiety": "integer (0-10)",
    "desire_tension": "integer (0-10)",
    "frustration": "integer (0-10)"
  }
}
```

**Правила:**
- У1-А: desire=0, anxiety=2-4, desire_tension=0, frustration=0
- У3-Б: desire=5-7, anxiety=7-9, desire_tension=8-10, frustration=3-5
- У5-Б: desire=8-10, anxiety=2-4, desire_tension=6-8, frustration=0-2
- У7-А: desire=3-5, anxiety=8-10, desire_tension=2-4, frustration=0
- У7-Б: desire=7-9, anxiety=2-3, desire_tension=4-6, frustration=0

### vscno (ВЛ-СТ-НЖ-ОГ)

```json
{
  "vscno": {
    "ВЛ": "integer (0-4)",
    "СТ": "integer (0-4)",
    "НЖ": "integer (0-4)",
    "ОГ": "integer (0-4)"
  }
}
```

> **Расшифровка:** ВЛ = Влюблённость, СТ = Страсть, НЖ = Нежность, ОГ = Огонь/Контраст.

**Правила:**
- Сумма ВЛ + СТ + НЖ + ОГ = 10 (всегда).
- У1-А: ВЛ=1, СТ=3, НЖ=4, ОГ=2
- У5-Б: ВЛ=4, СТ=1, НЖ=2, ОГ=3
- У7-Б: ВЛ=3, СТ=1, НЖ=4, ОГ=2

### engagement

```json
{
  "engagement": {
    "turn_count_since_stimulus": "integer (0+)",
    "stimulus_type": "string (e.g. gaze, touch, word, silence)",
    "last_user_message_timestamp": "ISO8601 или null",
    "proactive_count_since_last_session": "integer (0+)"
  }
}
```

### transition_state

```json
{
  "transition_state": {
    "required_turns": "integer (0+)",
    "current_turn": "integer (0+)",
    "target_level": "string (U1-A..U7-Б)",
    "trigger_type": "enum (auto | manual | safety_check)",
    "safety_check_pending": "boolean"
  }
}
```

### visual_data

```json
{
  "visual_data": {
    "prompt_base": "string (базовый промпт для Qwen)",
    "anti_prompts": ["array of strings"],
    "signature_features": ["array of strings (e.g. dark blonde curly hair, athletic build)"],
    "lighting_map_ref": "string (ссылка на подуровень из QWEN_ADAPTER_v2)",
    "aspect_ratio": "string (4:3 | 16:9 | 2:3)",
    "cfg": "number (4.5-6.0)",
    "steps": "integer (50-60)"
  }
}
```

### memory

```json
{
  "memory": {
    "trust_levels": {"type": "object (user, sergey, maksim, marina) каждый 0-100"},
    "attraction_levels": {"type": "object (user, sergey, maksim, marina) каждый 0-100"},
    "history": ["array of objects (event_id, timestamp, type, summary)"],
    "emotional_anchors": ["array of strings"],
    "regression_triggers": ["array of strings"],
    "flags": {"type": "object (boolean flags)"}
  }
}
```

### scenarios

```json
{
  "scenarios": ["array of strings (идентификаторы сценариев из scenarios/SCENARIO_*.json)"]
}
```

---

## Интеграция TEC с CORE v2.0

| TEC | Подуровни | Мнемоника | Алгоритм |
|-----|-----------|-----------|----------|
| TEC_003 | У1-А — У3-Б | Р, ПУ | — |
| TEC_005 | У3-А — У7-Б | ТГ2, ТГ3 | ПР, ВС |
| TEC_006 | У4-А — У4-Б | ПУ | СЛ |
| TEC_007 | У2-Б — У6-Б | Р | ПД, ДР |
| TEC_008 | У2-Б — У5-Б | ПУ | ФС, ЛС |
| TEC_M_001 | У1-А — У5-Б | К, С | — |
| TEC_M_002 | У3-А — У7-А | ТГ2, ТГ3 | ПР |
| TEC_M_003 | У4-А — У6-Б | С | КН, ПУ |

---

## Версионирование

- `TEC_DICTIONARY.md` — версионируется по semver.
- `v1.0.0` — базовый набор для v2.0+ engine.
- Добавление новых TEC требует обновления `persona_schema_v3.2` и `CROSS_PERSONA_RULES.md`.
