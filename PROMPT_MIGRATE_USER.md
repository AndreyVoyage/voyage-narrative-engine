# MIGRATE: USER_MODULE.json → personas/user/ (R7 → R8)
# Voyage Narrative Engine | Single Persona Migration Prompt
# Скопируй в Kimi Code Chat (VS Code) и нажми Enter

---

## ЗАДАЧА

Мигрировать `personas/USER_MODULE.json` в модульную структуру `personas/user/` через роли R7 (Refactor) и R8 (Auditor).

## КОНТЕКСТ (загрузить перед началом)

1. `roles/ROLE_7_REFACTOR_v1.0_PROMPT.md` — правила разбиения монолита на модули
2. `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md` — правила аудита после миграции
3. `knowledge_base/R6/KB_R6_CORE.md` — структура Persona Module
4. `knowledge_base/R6/KB_R6_BLOCK_SCHEMA.md` — полная блок-схема модулей
5. `schemas/persona_schema_v3_2_VOYAGE.json` — JSON Schema для валидации

## ВХОД

Файл: `personas/USER_MODULE.json`

## ВЫХОД

Структура: `personas/user/` с 12 подпапками:
- core/
- levels/ (U1-A … U7-B)
- psychology/
- sexology/
- visual/
- dynamics/
- memory/
- relationships/
- environment/
- safety/
- autonomous/
- meta/

Файлы в корне папки:
- INDEX.json — манифест модуля
- ASSEMBLY.md — инструкция сборки
- HANDOFF_R7.md — отчёт о миграции
- AUDIT_REPORT_user.md — отчёт R8 аудита

## АЛГОРИТМ

### Шаг 1. Прочитать USER_MODULE.json

Определить:
- `id` → "user" (маленькими буквами)
- `name` → имя персонажа
- `version` → "2.0.0" (major bump после R7)
- `schema_version` → "1.0.0"
- `default_level` → U1-A
- `default_ag_level` → 1
- `compatible_scenarios` → из поля scenarios или meta

### Шаг 2. Создать папки

```bash
mkdir -p personas/user/{core,levels,psychology,sexology,visual,dynamics,memory,relationships,environment,safety,autonomous,meta}
```

### Шаг 3. Разбить JSON на модули (R7 Refactor)

#### core/IDENTITY.json
- Извлечь: id, name, version, age, archetype, persona_type, anatomic_anchor, visual_signature
- Пример: `{"id": "user", "name": "Я", "version": "1.0.0", ...}`

#### levels/U1-A.json … levels/U7-B.json (14 файлов)
- Извлечь для каждого подуровня: speech_profile, dynamic_visuals, vscno, internal_state, ad_availability
- Если в JSON нет dynamic_visuals — оставить пустую строку `""`
- Если нет ad_availability — использовать baseline из `KB_R2_AD_RULES.md`

#### psychology/BASE.json
- core_conflict, secret_desire, shame_layers, sensory_register, trauma_anchor

#### psychology/ATTACHMENT.json
- attachment_sexuality (если есть)

#### psychology/AROUSAL.json
- responsive_desire, arousal_specificity (если есть)

#### psychology/PLASTICITY.json
- erotic_plasticity (если есть)

#### psychology/TEC.json
- tec_mechanics (если есть)

#### sexology/RESPONSE_CYCLE.json
- pacing, responsive_desire (если есть)

#### sexology/EROTIC_SCRIPTS.json
- archetypes, switch_context, bdsm_interest (если есть)

#### sexology/DYSPHORIA_AND_SHAME.json
- shame_layers, receiving_preferences (если есть)

#### sexology/FANTASY_VS_REALITY.json
- secret_desire, ideal_ending (если есть)

#### visual/PROMPT_BASE.json
- prompt_base, signature_features, anti_prompts, visual_signature, anatomic_anchor_last_verified, reference_image

#### visual/GENERATION_HISTORY.json
- generation_history (пустой массив, если нет)

#### dynamics/REACTION_PATTERNS.json
- reaction_patterns (если есть)

#### dynamics/LEVEL_LOCK_MATRIX.json
- level_lock_matrix (если есть)

#### dynamics/EMOTIONAL_INFLUENCE_MATRIX.json
- emotional_influence_matrix (если есть)

#### dynamics/CONFLICT_RESOLUTION_MATRIX.json
- conflict_resolution_matrix (если есть)

#### memory/TRUST.json
- trust_levels (если есть, иначе `{}`)

#### memory/ATTRACTION.json
- attraction_levels (если есть, иначе `{}`)

#### memory/FLAGS.json
- flags (если есть, иначе `{}`)

#### memory/HISTORY.json
- history (если есть, иначе `[]`)

#### memory/EMOTIONAL_ANCHORS.json
- emotional_anchors (если есть, иначе `{}`)

#### relationships/MATRIX.json
- relationships (массив отношений, иначе `[]`)

#### environment/STATE_TRIGGERS.json
- state_triggers (если есть)

#### environment/SPATIAL_BEHAVIOR.json
- Создать stub: `{"note": "[NEEDS_DATA] Проксемика не задана в оригинале", "default": "neutral"}`

#### safety/PROTOCOL.json
- stop_words, default_mode, hard_limits, soft_limits, safety_check_points, ag_max, peak_explosion_note, emergency_phrase

#### autonomous/ACTIVITIES.json
- activities (если есть, иначе `[]`)

#### autonomous/TEMPLATES.json
- message_templates_by_sublevel, message_templates (если есть)

#### meta/META.json
- meta + chat_display_name + persona_type + age_bracket + algorithms + format + volume + scenarios + engagement + transition_state

### Шаг 4. Создать INDEX.json

```json
{
  "id": "user",
  "name": "Я",
  "version": "2.0.0",
  "schema_version": "1.0.0",
  "default_level": "U1-A",
  "default_ag_level": 1,
  "compatible_scenarios": ["..."],
  "modules": {
    "core/IDENTITY.json": {"version": "1.0.0", "required": true},
    "psychology/BASE.json": {"version": "1.0.0", "required": true},
    "safety/PROTOCOL.json": {"version": "1.0.0", "required": true},
    "levels/U1-A.json": {"version": "1.0.0", "required": true}
  },
  "dependencies": {
    "persona_schema": "schemas/persona_schema_v3_2_VOYAGE.json",
    "source_monolith": "USER_MODULE.json"
  }
}
```

### Шаг 5. Создать ASSEMBLY.md

По шаблону из `KB_R6_BLOCK_SCHEMA.md` §4:
- Всегда загружать: core/IDENTITY.json, psychology/BASE.json, safety/PROTOCOL.json
- По current_level: levels/{current_level}.json
- По ag_level: ag=2 → +psychology/ATTACHMENT,AROUSAL,PLASTICITY,TEC; ag=3 → +sexology/*
- Если другие персонажи: relationships/MATRIX.json
- Runtime: memory/* + autonomous/*

### Шаг 6. Создать HANDOFF_R7.md

```markdown
# HANDOFF_R7: USER_MODULE.json → personas/user/

## Результат
- Модульная структура создана: `personas/user/` (12 подпапок, 35+ файлов)
- Версия: 2.0.0
- Источник: USER_MODULE.json

## Маппинг блоков
| Блок монолита | Модуль |
|---------------|--------|
| Identity | core/IDENTITY.json |
| Levels | levels/U1-A.json … U7-B.json |
| Psychology | psychology/BASE.json … |
| ... | ... |

## Предупреждения
- [ ] Список [NEEDS_DATA] или противоречий

## Следующий шаг
- R8 Auditor: roles/ROLE_8_AUDITOR_v1.0_PROMPT.md
```

### Шаг 7. R8 Аудит (проверки)

#### Проверка 1: Структурная целостность
- [ ] Все обязательные файлы есть (INDEX.json, ASSEMBLY.md, core/IDENTITY.json, psychology/BASE.json, safety/PROTOCOL.json, levels/U1-A…U7-B)
- [ ] Ровно 14 файлов в levels/
- [ ] Нет пробелов в именах файлов

#### Проверка 2: JSON-валидация
- [ ] Все .json файлы парсятся без ошибок
- [ ] Соответствуют `schemas/persona_schema_v3_2_VOYAGE.json`

#### Проверка 3: VSCNO
- [ ] Для каждого уровня: ВЛ + СТ + НЖ + ОГ = 10
- [ ] Каждая ось ∈ [0, 4]
- [ ] Если сумма ≠ 10 → WARNING, не FAIL

#### Проверка 4: AD-консистентность
- [ ] Только канонические коды: ФС, ЛС, СП, СЛ, КН, ПД, ДР, ПУ, ПР, ВС
- [ ] Если отклонение от baseline > 2 кодов → [ADAPTED] с обоснованием

#### Проверка 5: Internal State
- [ ] desire, anxiety ∈ [0, 10]
- [ ] Логически согласованы с уровнем

#### Проверка 6: TEC
- [ ] Если есть tec_mechanics — все 8 или явно помечены как неприменимые

#### Проверка 7: Safety
- [ ] hard_limits содержит запрет на насилие, принуждение, несовершеннолетних
- [ ] stop_words содержит "СТОП", "ХВАТИТ", "КРАСНАЯ КАРТОЧКА"
- [ ] emergency_phrase задана

#### Проверка 8: Целостность данных
- [ ] Количество фактов не уменьшилось (сравнить с оригинальным JSON)
- [ ] anatomic_anchor только в core/IDENTITY.json
- [ ] Нет противоречий между модулями

#### Проверка 9: Тестовая сборка
- [ ] INDEX.json логичен (все required modules на месте)
- [ ] ASSEMBLY.md содержит правильные приоритеты
- [ ] Сборка по умолчанию (U1-A, ag=1) возможна без ошибок

### Шаг 8. Создать AUDIT_REPORT_user.md

Формат:
```markdown
# AUDIT REPORT: user (Я)

## Метаданные
- id: user
- version: 2.0.0
- audit_date: 2026-06-17
- auditor: R8 v1.0

## Сводка
| Проверка | Результат | Комментарий |
|----------|-----------|-------------|
| Структурная целостность | ✅/⚠️/❌ | ... |
| JSON-валидация | ✅/⚠️/❌ | ... |
| VSCNO суммы | ✅/⚠️/❌ | ... |
| AD-консистентность | ✅/⚠️/❌ | ... |
| Internal State | ✅/⚠️/❌ | ... |
| TEC | ✅/⚠️/❌ | ... |
| Safety | ✅/⚠️/❌ | ... |
| Целостность данных | ✅/⚠️/❌ | ... |
| Тестовая сборка | ✅/⚠️/❌ | ... |

## Итог
- Critical: 0 | Warning: N | PASS / CONDITIONAL / FAIL
```

### Шаг 9. Git commit

```bash
git add personas/user/
git commit -m "persona: migrate user to modular structure (R7+R8)"
```

## ПРАВИЛА

1. **Не изменяй данные** — только разбиваешь и переформатируешь
2. **Если поле не вписывается в схему** — создай новый JSON и добавь в INDEX.json
3. **Если данные противоречивы** — создай `CONFLICTS_user.md` в папке
4. **Если VSCNO сумма ≠ 10** — пометь как WARNING, не исправляй (это R2)
5. **Если нет поля в JSON** — создай пустой `{}` или `[]` с комментарием

## ГОТОВО К ЗАПУСКУ

Скопируй этот файл в Kimi Code Chat (VS Code) и нажми Enter.
Kimi Code автоматически:
1. Загрузит USER_MODULE.json
2. Создаст personas/user/
3. Выполнит R8 аудит
4. Сделает git commit

---
*PROMPT_MIGRATE_USER.md | Voyage Narrative Engine | 2026-06-17*
