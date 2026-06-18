# PROMPT: Миграция всех персонажей (R7 → R8) через Kimi Code
# Voyage Narrative Engine | Batch Persona Migration v1.0

---

## ЗАДАЧА

Поочерёдно мигрировать всех персонажей из `personas/*.json` в модульную структуру `personas/[name]/` через роли R7 (Refactor) и R8 (Auditor).

---

## ПОДГОТОВКА

### 1. Загрузи KB-файлы (источники истины)

```
knowledge_base/R6/KB_R6_CORE.md          — структура Persona Module
knowledge_base/R6/KB_R6_BLOCK_SCHEMA.md   — полная блок-схема
roles/ROLE_7_REFACTOR_v1.0_PROMPT.md      — R7 Refactor
roles/ROLE_8_AUDITOR_v1.0_PROMPT.md       — R8 Auditor
```

### 2. Проверь список персонажей для миграции

```bash
ls -1 personas/*.json | grep -v "andrey_senior\|kira"
```

**Ожидаемый список (10 персонажей):**
- ANDREY_JUNIOR_MODULE_v2.1.json
- EGOR_MODULE_v1.json
- FEMALE_USER_MODULE.json
- MAKSIM_MODULE_v2.json
- MARINA_MODULE_v2.json
- OLGA_MODULE_v2_FIXED.json
- SERGEY_MODULE_v4.json
- USER_MODULE.json

---

## АЛГОРИТМ (по одному персонажу за шаг)

### Шаг 1. Загрузить JSON-монолит

```json
// Прочитать personas/[NAME]_MODULE_v[N].json
// Определить: id, name, version, top-level keys
```

### Шаг 2. Применить R7 (Refactor) для JSON

**Universal JSON → Module Mapping (9 блоков):**

| Блок JSON | Целевые модули | Правило извлечения |
|-----------|----------------|-------------------|
| **Identity** (name, age, archetype, visual_data) | `core/IDENTITY.json` | anatomic_anchor → visual_data.anatomic_anchor |
| **Levels** (speech_profile, dynamic_visuals, vscno_by_sublevel, internal_state_by_sublevel, ad_by_sublevel) | `levels/U1-A.json` … `levels/U7-B.json` | По 1 файлу на подуровень, объединить все поля |
| **Psychology** (core_conflict, trauma, attachment, responsive_desire, arousal_specificity, erotic_plasticity, tec_mechanics) | `psychology/BASE.json`, `AROUSAL.json`, `PLASTICITY.json`, `TEC.json`, `ATTACHMENT.json` | Разбить по подтемам |
| **Sexology** (intimacy_preferences, pacing, archetypes, switch_context, bdsm_interest, ideal_ending) | `sexology/RESPONSE_CYCLE.json`, `EROTIC_SCRIPTS.json`, `DYSPHORIA_AND_SHAME.json`, `FANTASY_VS_REALITY.json` | Разбить по подтемам |
| **Visual** (visual_data: prompt_base, signature_features, anti_prompts, generation_history) | `visual/PROMPT_BASE.json`, `GENERATION_HISTORY.json` | Всё из visual_data |
| **Dynamics** (reaction_patterns, cross_persona_sync) | `dynamics/REACTION_PATTERNS.json`, `LEVEL_LOCK_MATRIX.json`, `EMOTIONAL_INFLUENCE_MATRIX.json`, `CONFLICT_RESOLUTION_MATRIX.json` | Разбить по типам |
| **Memory** (trust_levels, attraction_levels, flags, history, emotional_anchors) | `memory/TRUST.json`, `ATTRACTION.json`, `FLAGS.json`, `HISTORY.json`, `EMOTIONAL_ANCHORS.json` | По 1 файлу на тип памяти |
| **Relationships** (relationships) | `relationships/MATRIX.json` | Массив отношений |
| **Environment** (state_triggers) | `environment/STATE_TRIGGERS.json`, `SPATIAL_BEHAVIOR.json` | state_triggers + проксемика (stub) |
| **Safety** (safety: stop_words, hard_limits, soft_limits, etc.) | `safety/PROTOCOL.json` | Все safety-поля |
| **Autonomous** (autonomous: activities, message_templates) | `autonomous/ACTIVITIES.json`, `TEMPLATES.json` | Активности + шаблоны |
| **Meta** (meta + chat_display_name + algorithms + format + volume + scenarios + engagement) | `meta/META.json` | Метаданные + runtime-параметры |

### Шаг 3. Создать структуру папок

```bash
mkdir -p personas/[id]/
mkdir -p personas/[id]/{core,levels,psychology,sexology,visual,dynamics,memory,relationships,environment,safety,autonomous,meta}
```

### Шаг 4. Записать JSON-файлы

Для каждого модуля:
- `write_json(path, data)` — ensure_ascii=False, indent=2
- Валидировать JSON перед записью

### Шаг 5. Создать INDEX.json

```json
{
  "id": "[id]",
  "name": "[name]",
  "version": "2.0.0",
  "schema_version": "1.0.0",
  "default_level": "U1-A",
  "default_ag_level": 1,
  "compatible_scenarios": ["..."],
  "modules": {
    "core/IDENTITY.json": {"version": "1.0.0", "required": true},
    "psychology/BASE.json": {"version": "1.0.0", "required": true},
    "levels/U1-A.json": {"version": "1.0.0", "required": true},
    "...": "..."
  }
}
```

### Шаг 6. Создать ASSEMBLY.md

По шаблону из `KB_R6_BLOCK_SCHEMA.md` §4.

### Шаг 7. Создать HANDOFF_R7.md

Список что сделано, предупреждения, следующий шаг (R8).

### Шаг 8. Запустить R8 (Auditor)

**Проверки (10 штук):**
1. Структурная целостность — все обязательные файлы есть
2. JSON-валидация — парсится без ошибок
3. VSCNO — сумма = 10, каждая ось ∈ [0,4]
4. AD-консистентность — только канонические коды
5. Internal State — desire, anxiety ∈ [0,10]
6. TEC — все 8 механик или явно помечены как неприменимые
7. Cross-Persona — trust, attraction ∈ [0,100]
8. Safety — hard_limits, stop_words, emergency_phrase
9. Целостность монолит → модули — нет потерянных данных
10. Тестовая сборка — INDEX.json + ASSEMBLY.md логичны

### Шаг 9. Сохранить AUDIT_REPORT_[ID].md

Формат:
```markdown
# AUDIT REPORT: [Name]

## Сводка
| Проверка | Результат |
|----------|-----------|
| Структура | ✅/⚠️/❌ |
| JSON | ✅/⚠️/❌ |
| VSCNO | ✅/⚠️/❌ |
| ... | ... |

## Итог: PASS / CONDITIONAL / FAIL
```

### Шаг 10. Git commit этого персонажа

```bash
git add personas/[id]/
git commit -m "persona: migrate [id] to modular structure (R7+R8)"
```

---

## ПОСЛЕДОВАТЕЛЬНОСТЬ ОБРАБОТКИ

Обработай персонажей **в этом порядке** (от простого к сложному):

1. **USER_MODULE.json** — самый простой (базовый user proxy)
2. **FEMALE_USER_MODULE.json** — базовый female proxy
3. **EGOR_MODULE_v1.json** — молодой, структура похожа на Андрея
4. **ANDREY_JUNIOR_MODULE_v2.1.json** — молодой Андрей
5. **MAKSIM_MODULE_v2.json** — простой, secure attachment
6. **MARINA_MODULE_v2.json** — shy_to_bloom
7. **OLGA_MODULE_v2_FIXED.json** — predatory_huntress
8. **SERGEY_MODULE_v4.json** — catalyst, avoidant

**Пропустить:** KIRA (уже мигрирована), ANDREY_SENIOR (уже мигрирован).

---

## ПРАВИЛА

1. **Не меняй данные** — только разбиваешь и переформатируешь
2. **Если поле не вписывается в схему** — создай новый JSON-файл и добавь в INDEX.json
3. **Если данные противоречивы** — создай `CONFLICTS_[id].md` в папке персонажа
4. **Если VSCNO сумма ≠ 10** — пометь как WARNING, не исправляй (это R2)
5. **Каждый персонаж — отдельный коммит** — чтобы можно было откатить

---

## КОМАНДА ДЛЯ ЗАПУСКА В VS CODE

### 1. Открой терминал VS Code (Ctrl+`)

### 2. Перейди в репозиторий
```bash
cd C:\DEV\Narrative\voyage-narrative-engine
```

### 3. Открой файл промпта в VS Code
```bash
code PROMPT_R7_BATCH_VSCODE.md
```

### 4. Запусти Kimi Code через VS Code Command Palette

**Способ A — Через Command Palette:**
```
Ctrl+Shift+P → "Kimi Code: Generate" → выбери PROMPT_R7_BATCH_VSCODE.md
```

**Способ B — Через Kimi Code Chat:**
```
1. Открой Kimi Code Chat (Ctrl+Shift+L или Ctrl+Shift+P → "Kimi Code: Open Chat")
2. Вставь содержимое PROMPT_R7_BATCH_VSCODE.md
3. Нажми Enter
```

**Способ C — Через inline-запрос:**
```
1. Открой любой JSON персонажа (например, personas/EGOR_MODULE_v1.json)
2. Выдели весь текст (Ctrl+A)
3. Нажми Ctrl+Shift+I (Inline Chat)
4. Вставь: "Мигрируй этого персонажа по правилам R7 из PROMPT_R7_BATCH_VSCODE.md"
5. Нажми Enter
```

### 5. Kimi Code выполнит автоматически:
- Прочитает JSON
- Создаст модульную структуру в personas/[id]/
- Создаст INDEX.json, ASSEMBLY.md, HANDOFF_R7.md
- Запустит R8 аудит (проверит VSCNO=10, JSON валидность, и т.д.)
- Создаст AUDIT_REPORT_[id].md
- Сделает git commit

### 6. Проверь результат
```bash
git log --oneline -5
ls -la personas/[id]/
cat personas/[id]/AUDIT_REPORT_[id].md
```

### 7. Переходи к следующему персонажу

Повтори шаги 4-6 для следующего персонажа из списка.

---

*PROMPT_R7_BATCH_VSCODE.md | Voyage Narrative Engine | 2026-06-17*

---

## TROUBLESHOOTING

### Проблема: Kimi Code не видит JSON-файл
**Решение:** Убедись, что файл открыт в VS Code (вкладка активна). Kimi Code работает с текущим контекстом.

### Проблема: Контекстное окно переполнено
**Решение:** JSON > 100KB может не поместиться. Используй Способ C (inline) — тогда Kimi Code видит только текущий файл, а не весь проект.

### Проблема: R8 аудит не проходит (VSCNO ≠ 10)
**Решение:** Это нормально — прометь WARNING и передай в R2 (Psychologist) для исправления. Не правь данные в R7.

### Проблема: Git commit не работает
**Решение:** Проверь `git status` вручную и сделай коммит после завершения миграции всех персонажей.

---

*PROMPT_R7_BATCH_VSCODE.md | Voyage Narrative Engine | 2026-06-17*
