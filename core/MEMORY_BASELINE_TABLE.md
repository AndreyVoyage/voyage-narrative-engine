# MEMORY BASELINE TABLE (CORE)
# Voyage Narrative Engine — Стандартные Memory-значения по стилям привязанности
# Версия: v1.0
# Правило: Роли используют этот файл, не создают свои версии. Адаптируют с маркировкой [ADAPTED].

---

## 1. Описание memory-структуры

| Поле | Тип | Диапазон | Описание |
|------|-----|----------|----------|
| **trust_levels** | Объект | [0, 100] | Уровень доверия к каждому персонажу |
| **attraction_levels** | Объект | [0, 100] | Уровень влечения к каждому персонажу |
| **emotional_anchors** | Массив | — | Триггеры → эмоции, привязанные к травмам/ресурсам |
| **flags** | Объект | boolean | Психологические маркеры (стиль привязанности, искажения, травмы) |
| **history** | Массив | — | События сессий (заполняется динамически) |

---

## 2. Начальные trust_levels по стилю привязанности

| Стиль | trust.user | trust.sergey | trust.marina | trust.maksim | trust.kira | trust.olga | trust.self |
|-------|------------|--------------|--------------|--------------|------------|------------|------------|
| **Avoidant** | 30-40 | 20-30 | 20-30 | 25-35 | 15-25 | 20-30 | 40-50 |
| **Anxious** | 50-60 | 40-50 | 40-50 | 45-55 | 35-45 | 40-50 | 30-40 |
| **Secure** | 60-70 | 50-60 | 50-60 | 55-65 | 45-55 | 50-60 | 50-60 |
| **Disorganized** | 40-50 | 30-40 | 30-40 | 35-45 | 25-35 | 30-40 | 35-45 |

**Правило:** trust.user всегда ≥ trust.others (пользователь — приоритет).
**Правило:** trust.self — доверие к себе, важно для автономии.

---

## 3. Начальные attraction_levels по стилю привязанности

| Стиль | attraction.user | attraction.sergey | attraction.marina | attraction.maksim | attraction.kira | attraction.olga |
|-------|-----------------|-------------------|-------------------|-------------------|-----------------|-----------------|
| **Avoidant** | 40-50 | 30-40 | 30-40 | 35-45 | 25-35 | 30-40 |
| **Anxious** | 60-70 | 50-60 | 50-60 | 55-65 | 45-55 | 50-60 |
| **Secure** | 50-60 | 40-50 | 40-50 | 45-55 | 35-45 | 40-50 |
| **Disorganized** | 50-70 (колеблется) | 40-60 | 40-60 | 45-65 | 35-55 | 40-60 |

**Правило:** attraction.user всегда ≥ attraction.others (пользователь — приоритет).
**Правило:** Disorganized — колебания ±10, не стабильно.

---

## 4. Emotional anchors (шаблоны)

### 4.1 Типы anchors

| Тип | Описание | Пример | Когда активируется |
|-----|----------|--------|-------------------|
| **Травматический** | Триггер → негативная эмоция | «Запах духов бывшего» → грусть | Встреча с триггером |
| **Ресурсный** | Триггер → позитивная эмоция | «Морской бриз» → спокойствие | Нужда в восстановлении |
| **Сценарный** | Ситуация → комплекс эмоций | «Сауна» → возбуждение + стыд | Конкретная локация |
| **Персональный** | Персонаж → специфическая эмоция | «Кира смотрит» → ревность | Взаимодействие |

### 4.2 Шаблон emotional anchor

```json
{
  "id": "anchor_[name]",
  "type": "traumatic|resource|scenario|personal",
  "trigger": "[что активирует]",
  "emotion": "[основная эмоция]",
  "intensity": [0-10],
  "sublevel": "[У?-?]",
  "source": "[травма/ресурс/сценарий/персонаж из портрета]",
  "first_encounter": "[когда впервые встретился]",
  "current_status": "active|resolved|suppressed"
}
```

---

## 5. Flags (психологические маркеры)

### 5.1 Стандартные flags

| Flag | Значение по умолчанию | Когда true | Психологическое основание |
|------|----------------------|------------|-------------------------|
| `attachment_style_avoidant` | false | Стиль = avoidant | Bowlby |
| `attachment_style_anxious` | false | Стиль = anxious | Bowlby |
| `attachment_style_disorganized` | false | Стиль = disorganized | Main |
| `attachment_style_secure` | false | Стиль = secure | Bowlby |
| `cognitive_distortion_catastrophizing` | false | Есть катастрофизация | Beck |
| `cognitive_distortion_mind_reading` | false | Есть чтение мыслей | Beck |
| `cognitive_distortion_personalization` | false | Есть персонализация | Beck |
| `cognitive_distortion_dichotomous` | false | Есть дихотомия | Beck |
| `cognitive_distortion_emotional_reasoning` | false | Есть эмоц. обоснование | Beck |
| `cognitive_distortion_mental_filter` | false | Есть ментальный фильтр | Beck |
| `cognitive_distortion_should_statements` | false | Есть долженствование | Ellis |
| `trauma_trigger_[name]` | false | Есть травматический триггер | van der Kolk |
| `resilience_resource_[name]` | false | Есть ресурс | Masten |
| `regression_prone` | false | Есть точки регрессии | — |
| `aftercare_high_need` | false | Aftercare-need > 7 | — |
| `shadow_integrated` | false | Тень интегрирована (У4-Б+) | Jung |

### 5.2 Bit-flags (для компактности)

```json
"flags": {
  "_bits": "0b0000000000000000",
  "_map": [
    "attachment_avoidant", "attachment_anxious", "attachment_disorganized", "attachment_secure",
    "distortion_catastrophizing", "distortion_mind_reading", "distortion_personalization",
    "distortion_dichotomous", "distortion_emotional_reasoning", "distortion_mental_filter",
    "distortion_should_statements", "trauma_trigger_active", "resilience_resource_active",
    "regression_prone", "aftercare_high_need", "shadow_integrated"
  ]
}
```

---

## 6. Правила адаптации

1. **trust_levels ∈ [0, 100].** Clamp при адаптации.
2. **attraction_levels ∈ [0, 100].** Clamp при адаптации.
3. **trust.user ≥ trust.others.** Пользователь — приоритет.
4. **attraction.user ≥ attraction.others.** Пользователь — приоритет.
5. **Avoidant:** trust.user ≤ 40, attraction.user ≤ 50.
6. **Anxious:** trust.user ≥ 50, attraction.user ≥ 60.
7. **Secure:** trust.user ≥ 60, attraction.user ≥ 50.
8. **Disorganized:** trust.user колеблется 40-50, attraction.user колеблется 50-70.
9. **Emotional anchors:** Минимум 3, максимум 7. Привязать к фактам из портрета.
10. **Flags:** Только те, что подтверждены портретом. Не выдумывать.

---

## 7. Примеры адаптации

### Пример 1: Кира (Avoidant)
```
[CORE] Avoidant: trust.user=35, trust.sergey=25, trust.marina=25, trust.maksim=30, trust.kira=20, trust.olga=25
[ADAPTED] Кира: trust.user=40, trust.sergey=30, trust.marina=25, trust.maksim=35, trust.kira=20, trust.olga=25
  Основание: «доверяет только мужу» → trust.user↑ на 5, trust.maksim↑ на 5 (Максим — друг мужа)
  Проверка: все ∈ [0,100] ✅, trust.user ≥ trust.others ✅

[CORE] Avoidant: attraction.user=45, attraction.sergey=35, attraction.marina=35, attraction.maksim=40, attraction.kira=30, attraction.olga=35
[ADAPTED] Кира: attraction.user=50, attraction.sergey=30, attraction.marina=35, attraction.maksim=40, attraction.kira=30, attraction.olga=35
  Основание: «внутри пожар» → attraction.user↑ на 5, attraction.sergey↓ на 5 (избегает)
  Проверка: все ∈ [0,100] ✅, attraction.user ≥ attraction.others ✅

[ADAPTED] Emotional anchors:
  {
    "id": "anchor_sauna",
    "type": "scenario",
    "trigger": "сауна, парилка, влажность",
    "emotion": "возбуждение + стыд",
    "intensity": 8,
    "sublevel": "У2-А",
    "source": "портрет: 'в сауне раскрывается'",
    "first_encounter": "сессия 1",
    "current_status": "active"
  }
```

### Пример 2: Ольга (Disorganized)
```
[CORE] Disorganized: trust.user=45, trust.sergey=35, trust.marina=35, trust.maksim=40, trust.kira=30, trust.olga=35
[ADAPTED] Ольга: trust.user=50, trust.sergey=40, trust.marina=35, trust.maksim=40, trust.kira=35, trust.olga=30
  Основание: «ищет защиты» → trust.user↑ на 5, trust.sergey↑ на 5 (Сергей — катализатор)
  Проверка: все ∈ [0,100] ✅

[ADAPTED] Emotional anchors:
  {
    "id": "anchor_control_loss",
    "type": "traumatic",
    "trigger": "потеря контроля, неожиданность",
    "emotion": "паника + возбуждение",
    "intensity": 9,
    "sublevel": "У6-Б",
    "source": "портрет: 'не знаю что чувствую'",
    "first_encounter": "сессия 1",
    "current_status": "active"
  }
```

---

## 8. Связь с VSCNO

| VSCNO ось | Как влияет на Memory |
|-----------|---------------------|
| **ВЛ↑** | trust↑ (доверие растёт с радостью), emotional anchors (ресурсные) активны |
| **СТ↑** | trust↓ (дистанция = недоверие), flags (avoidant) активны |
| **НЖ↑** | trust↓ (тревога = недоверие), emotional anchors (травматические) активны |
| **ОГ↑** | trust↑ (общность = доверие), emotional anchors (все типы) активны |

---

## 9. Связь с Internal State

| Метрика | Как влияет на Memory |
|---------|---------------------|
| **desire↑** | attraction↑, emotional anchors (сценарные) активны |
| **anxiety↑** | trust↓, emotional anchors (травматические) активны |
| **desire_tension↑** | emotional anchors (сценарные) активны, flags (regression_prone) |
| **frustration↑** | trust↓, flags (distortion_*) активны |

---

**Используйте этот файл как baseline. Адаптируйте с маркировкой [ADAPTED].**
**Не создавайте Memory с нуля — это нарушает совместимость системы.**
