# 03_ASSEMBLY_GUIDE.md
# Руководство по сборке персонажа из модулей
# Версия: 2.1.0 (исправлено по аудиту ANA v1.0)
# Дата: 2026-06-08

---

## Исправления по аудиту (v2.0 → v2.1)

| Проблема аудита | Исправление |
|-----------------|-------------|
| ag_level не описан (откуда брать, значения по умолчанию) | ✅ Добавлен раздел «Определение ag_level» |
| Нет явного указания, что ag_level влияет на набор модулей | ✅ Добавлена таблица ag_level в шаг 6 |

---

## 1. Алгоритм сборки (пошагово)

### Шаг 1. Загрузить INDEX.json
Определить корневую папку персонажа (например, `personas/kira/`). Прочитать `INDEX.json`:
- Список модулей с версиями.
- `required: true` — обязательные.
- `compatible_scenarios` — проверка совместимости.

### Шаг 2. Определить контекст сборки
Из `state/STATE.json` (или параметров вызова):
- `current_level` — эмоциональный уровень ("U3-A").
- `active_scenario` — идентификатор сценария ("sauna_quartet").
- `other_characters` — другие персонажи в сцене.
- `scene_type` — тип сцены (романтическая, эротическая, бытовая, конфликтная).
- `ag_level` — глубина сборки (1=базовая, 2=+психология/физиология, 3=+сексология). **См. раздел 7.**

### Шаг 3. Базовый набор (всегда)
- `core/IDENTITY.json`
- `psychology/BASE.json`
- `safety/PROTOCOL.json`

### Шаг 4. Уровень
- `levels/{current_level}.json`
- Если отсутствует — использовать `default_level` из INDEX.json.

### Шаг 5. Отношения
- Если `other_characters` не пуст → `relationships/MATRIX.json`.

### Шаг 6. Дополнительные модули по контексту и ag_level

| Условие | ag_level | Добавляемые модули |
|---------|----------|-------------------|
| Базовая сцена | 1 | Только базовый набор + уровень + отношения |
| Романтика/флирт | 2 | + `physiology/AROUSAL_SIGNATURES`, `psychology/AROUSAL`, `psychology/IFS`, `meta/ATTRIBUTION_BIAS`, `environment/SENSORY_PROCESSING` |
| Конфликт | 2 | + `psychology/DEFENSE_MECHANISMS`, `dynamics/RIVALRY_TRIANGLE` |
| Эротика | 3 | + `sexology/RESPONSE_CYCLE`, `sexology/EROTIC_SCRIPTS`, `sexology/DYSPHORIA`, `meta/UNRELIABLE_NARRATOR`, `physiology/EROGENOUS_MAP` |
| Травма (U5+, triggers) | 3 | + `trauma_ptsd/THREE_LEVELS`, `psychology/COGNITIVE_DISTORTIONS` |
| Визуализация | любой | + `visual/PROMPT_BASE`, `visual/LIGHTING_MAP` |
| Сенсорика | 2+ | + `environment/SENSORY_PROCESSING`, `environment/SPATIAL_BEHAVIOR` |
| Эволюционная мотивация | 2+ | + `evolution/AROUSAL_AS_MOTIVATION` |
| Привязанность | 2+ | + `attachment/BEHAVIORAL_SYSTEMS` |

### Шаг 7. Оверрайды сценария
Если `scenarios/{scenario}.json` содержит `character_overrides` — наложить временно.

### Шаг 8. Runtime состояние
Значения из `state/STATE.json` (`internal_state`, `vscno`, `memory_*`) имеют наивысший приоритет.

### Шаг 9. Результирующий JSON
Склеить все объекты. При конфликте — правила приоритетов (раздел 3).

---

## 2. Чтение INDEX.json

```json
{
  "id": "kira",
  "version": "2.1.0",
  "modules": {
    "core/IDENTITY.json": { "version": "1.0.0", "required": true },
    "psychology/BASE.json": { "version": "1.2.0", "required": true },
    "psychology/AROUSAL.json": { "version": "1.0.0", "required": false },
    "levels/U1-A.json": { "version": "1.0.0" },
    "levels/U7-B.json": { "version": "1.0.0" },
    "relationships/MATRIX.json": { "version": "1.1.0" },
    "visual/PROMPT_BASE.json": { "version": "1.0.0" },
    "safety/PROTOCOL.json": { "version": "1.0.0", "required": true }
  },
  "default_level": "U2-A",
  "compatible_scenarios": ["sauna_quartet", "promenade", "cafe_date"]
}
```

**Правила:**
- `required: true` — обязательны. Если отсутствуют → ошибка.
- Без `required` — загружаются по контексту.
- Версии должны соответствовать INDEX.json. Несовпадение → предупреждение.

---

## 3. Приоритеты при конфликтах полей

| Приоритет | Источник | Примечание |
|-----------|----------|------------|
| 1 | **Runtime состояние** (`state/STATE.json`) | Всегда побеждает |
| 2 | **Оверрайды сценария** | Временно, для одной сессии |
| 3 | **Модуль уровня** (`levels/{current}.json`) | Перезаписывает базовые |
| 4 | **Специализированные модули** | Влияют на отдельные поля |
| 5 | **Базовый модуль** (`psychology/BASE.json`) | Самый общий уровень |
| 6 | **Модуль идентичности** (`core/IDENTITY.json`) | Только неизменяемые данные |

**Если конфликт не разрешается автоматически** → сборщик выдаёт ошибку и останавливается.

---

## 4. Пример сборки: Кира, U3-A, sauna_quartet, ag_level=2

**Исходные данные:**
- `current_level` = "U3-A"
- `active_scenario` = "sauna_quartet"
- `other_characters` = ["sergey", "maksim", "marina"]
- `scene_type` = "erotic/romantic"
- `ag_level` = 2 (из сценария: P2_STEAM требует ag_level=2)

**Шаги:**

1. **Обязательные:**
   - `core/IDENTITY.json`
   - `psychology/BASE.json`
   - `safety/PROTOCOL.json`

2. **Уровень:**
   - `levels/U3-A.json`

3. **Отношения:**
   - `relationships/MATRIX.json`

4. **Глубинная психология (ag_level >= 2):**
   - `psychology/AROUSAL.json`
   - `psychology/PLASTICITY.json`
   - `psychology/ODSC.json`
   - `psychology/ATTACHMENT.json`
   - `psychology/DEFENSE_MECHANISMS.json` (U3-A = neurotic level)
   - `psychology/IFS_PARTS.json` (U3-A = exile_butterfly)
   - `psychology/COGNITIVE_DISTORTIONS.json` (U3-A = emotional_reasoning + should_statements)

5. **Физиология (ag_level >= 2, эротическая сцена):**
   - `physiology/AROUSAL_SIGNATURES.json`
   - `physiology/MICROEXPRESSIONS.json`

6. **Сексология (ag_level >= 3? Нет, ag_level=2, значит НЕ загружаем RESPONSE_CYCLE и EROTIC_SCRIPTS полностью, только если сценарий явно требует)**
   - **Важно:** ag_level=2 НЕ включает sexology/RESPONSE_CYCLE и sexology/EROTIC_SCRIPTS по умолчанию. Эти модули загружаются только при ag_level=3 ИЛИ если сценарий явно помечен как эротический с `scene_type: "erotic"`.
   - В данном случае `scene_type` = "erotic/romantic", поэтому загружаем:
     - `sexology/RESPONSE_CYCLE.json` (фаза receptivity)
     - `sexology/EROTIC_SCRIPTS.json` ("Соревнование двух мужчин")

7. **Сценарийная:**
   - `dynamics/RIVALRY_TRIANGLE.json` (Sergey vs Maksim)
   - `environment/SENSORY_PROCESSING.json` (сауна: пар, влажность, тепло)
   - `environment/SPATIAL_BEHAVIOR.json` (проксемика в парилке)

8. **Мета:**
   - `meta/UNRELIABLE_NARRATOR.json` (desire=5, мысли нейтральны → 80% лжи)
   - `meta/ATTRIBUTION_BIAS.json`

9. **Визуал:**
   - `visual/PROMPT_BASE.json`
   - `visual/LIGHTING_MAP.json` (dramatic Rembrandt для U3-A)

10. **Оверрайды сценария (если есть):**
    ```json
    "character_overrides": {
      "kira": {
        "levels/U3-A.json": {
          "speech_profile.catchphrases": ["Ещё один? Я не выдержу..."]
        }
      }
    }
    ```

11. **Runtime состояние:**
    ```json
    {
      "internal_state": { "desire": 5, "anxiety": 4 },
      "vscno": { "ВЛ": 2, "СТ": 3, "НЖ": 3, "ОГ": 2 },
      "memory": { "trust_levels": {...}, "attraction_levels": {...} }
    }
    ```

**Результат:**
```json
{
  "identity": { "name": "Кира", "age": 26, ... },
  "psychology": { "base": {...}, "arousal": {...}, "ifs_parts": {...}, ... },
  "level": { "level_id": "U3-A", "speech_profile": {...}, "ifs_part": "exile_butterfly" },
  "relationships": { "user": { "trust": 75, "attraction": 85 }, ... },
  "physiology": { "desire": 5, "pulse": "95-110", "micro": "дрожь рук" },
  "sexology": { "phase": "receptivity", "script": "Соревнование двух мужчин" },
  "dynamics": { "rivalry": "Sergey vs Maksim", "threshold": 10 },
  "environment": { "dominant_modality": "kinesthetic", "triggers": ["пар", "влажность"] },
  "meta": { "unreliable_narrator": true, "lie_type": "rationalization" },
  "safety": { "hard_limits": [...], "regression_triggers": [...] },
  "runtime": { "internal_state": {...}, "vscno": {...}, "memory": {...} }
}
```

---

## 5. Использование ASSEMBLY.md

`ASSEMBLY.md` — человеко- и LLM-читаемый файл с правилами сборки, специфичными для персонажа.

**Пример (Кира):**
```markdown
# ASSEMBLY: Кира

## Всегда загружать
- core/IDENTITY.json
- psychology/BASE.json
- safety/PROTOCOL.json

## По current_level
- levels/{current_level}.json
- visual/LIGHTING_MAP.json#/level_{current_level}

## Если другие персонажи в сцене
- relationships/MATRIX.json

## Если сценарий эротический/романтический
- physiology/AROUSAL_SIGNATURES.json
- sexology/RESPONSE_CYCLE.json
- sexology/EROTIC_SCRIPTS.json

## Если обнаружены триггеры травмы
- trauma_ptsd/THREE_LEVELS.json
- psychology/DEFENSE_MECHANISMS.json

## Приоритеты
- Состояние > Сценарий > Уровень > Специализированные > Базовые > Идентичность
```

---

## 6. Валидация после сборки

- [ ] Все обязательные поля присутствуют.
- [ ] Типы данных совпадают.
- [ ] Значения в диапазонах (desire 0-10, trust 0-100).
- [ ] VSCNO сумма = 10.
- [ ] `level_id` совпадает с `current_level`.
- [ ] `ifs_part` из `levels/{current}.json` существует в `psychology/IFS_PARTS.json`.
- [ ] `ag_level` в собранном контексте соответствует заявленному.

Если валидация не пройдена — сборка неудачна, сессия не начинается.

---

## 7. Определение ag_level (НОВОЕ)

| ag_level | Значение | Какие модули добавляются | Когда использовать |
|----------|----------|-------------------------|-------------------|
| 1 | Базовая | core + psychology/BASE + safety + levels + relationships | Бытовая сцена, первое знакомство, нет физической близости |
| 2 | Продвинутая | + physiology + psychology/AROUSAL + psychology/IFS + meta/ATTRIBUTION + environment/SENSORY | Романтическая сцена, флирт, лёгкое прикосновение, конфликт |
| 3 | Полная | + sexology + meta/UNRELIABLE_NARRATOR + dynamics/RIVALRY + trauma/THREE_LEVELS | Эротическая сцена, глубокий конфликт, тревожный триггер |

**Источник ag_level:**
1. Из `scenarios/{scenario}.json` → поле `recommended_ag_level` или `phases/{phase}.ag_level`.
2. Из `state/STATE.json` → поле `ag_level` (может быть переопределено сценарием).
3. По умолчанию: `ag_level = 1`.

**Пример в сценарии:**
```json
{
  "scenario_id": "sauna_quartet",
  "recommended_ag_level": 2,
  "phases": {
    "P1_ENTRANCE": { "ag_level": 1 },
    "P2_STEAM": { "ag_level": 2 },
    "P5_CLIMAX": { "ag_level": 3 }
  }
}
```

**Правило:** Если `scene_type` = "erotic" и `ag_level` < 2 — повысить до 2 (минимум для физиологии). Если `scene_type` = "erotic" и есть явные эротические действия — повысить до 3.

---

## 8. Советы для LLM (если сборку делает LLM)

- Не загружайте весь персонаж целиком — перегрузит контекст.
- Используйте INDEX.json как карту.
- Всегда начинайте с обязательных модулей.
- Для определения уровня обращайтесь к state/STATE.json.
- ag_level определяет, какие модули включены — проверяйте его перед сборкой.
- Если модуль отсутствует, но не required — пропустите.
- Не изменяйте исходные модули; оверрайды храните отдельно.

---

*Документ 03 из 09. Версия 2.1.0 (исправлена по аудиту ANA v1.0)*
