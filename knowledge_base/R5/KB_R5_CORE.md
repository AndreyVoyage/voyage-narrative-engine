# KB_R5_CORE.md
# Knowledge Base: Роль 5 — Persona Physiognomist v1.3
# Назначение: Anatomic Anchor, Dynamic Visuals, Lighting Map, Visual Signature
# Источники: SPEC_PART_1_2, ANDREY_SENIOR_MODULE_v1.json (visual_data), EGOR_MODULE_v1.json (visual_data)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. НАЗНАЧЕНИЕ R5

**Роль:** Визуальный архитектор. Создаёт статичный портрет (Anatomic Anchor) и динамическую таблицу (14×7 параметров) для каждого подуровня.

**Критично:** Не создавать речь (это R4). Не психологизировать (это R2). Не сексологизировать (это R3). Не агрегировать (это R6).

---

## 2. ANATOMIC ANCHOR (L1) — ДНК лица

**Формат:** JSON (10 параметров). Неизменный. Источник истины для Visual Signature.

### Обязательные блоки

| Блок | Что описывает | Пример (Андрей) | Пример (Егор) |
|------|--------------|-----------------|---------------|
| **face_shape** | Форма лица + характер | oval, strong jaw, square | oval, angular, sharp jaw |
| **forehead** | Лоб + линии | broad, slight lines | broad, smooth |
| **chin** | Подбородок | strong, rounded, subtle cleft | sharp, defined, masculine |
| **overall** | Общее впечатление | warm protector, approachable | predatory elegance, wolf-like |
| **eyes** | Глаза (color, shape, gaze, signature, pupil_dynamics) | bright blue, almond, warm, medium lid, pupils dilate on stress | gray, almond, intense, left squint when lying, pupils constrict on anger |
| **nose** | Нос (shape, signature, dynamics) | straight, strong bridge, rounded tip | straight, sharp, medium symmetrical flare |
| **lips** | Губы (shape, signature, resting, dynamics, speech) | medium-full, soft, gentle closed-mouth, tightens on stress | medium cupid bow, thin, asymmetrical smirk, flattens when angry |
| **skin** | Кожа (tone, texture, dynamics, age_marks, sweat) | fair warm, smooth weathered, blush on stress, 38yo crow's feet | light olive, smooth, no marks, sweat on temple |
| **hair** | Волосы (color, style, texture, facial_hair) | light ash-blond, short dense, straight, clean-shaven | dark ash-blond, military cut, textured, no facial hair |
| **body** | Тело (height, weight, type, build, posture) | 180/85, athletic mesomorph, broad shoulders, upright relaxed | 180/83, athletic, narrow waist, aggressive forward |
| **signature_items** | Уникальные предметы/привычки | expensive watch, adjusts sleeves, opens palms | expensive watch, fingers tap, clench when regressing |

---

## 3. VISUAL SIGNATURE (L2) — строка для промптов

**Формат:** Одна строка, 100–200 слов.

**Структура:** возраст + пол + телосложение → волосы → глаза → лицо → кожа → особенности → одежда → впечатление.

**Пример (Андрей):**
```
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense evenly trimmed hair, 
bright blue almond wide-set eyes with warm observant gaze, strong square jaw with visible 
muscle definition, medium-high broad cheekbones, gentle closed-mouth smile left corner 
slightly higher, medium-full soft lips, fair warm skin with slight weathered texture, 
thick neck powerful chest broad shoulders, clean-shaven, blue casual elegant shirt with 
rolled-up sleeves, expensive watch
```

**Правила:**
- Без эмоциональных оценок (не «красивый», а «handsome»).
- Без контекста (не «в баре»).
- Без динамики (не «улыбается»).
- Порядок строгий: волосы → глаза → лицо → кожа → тело → особенности → одежда.

---

## 4. DYNAMIC VISUALS (14×7 таблица)

| Параметр | Описание | Диапазон |
|----------|----------|----------|
| **clothing** | Одежда | текстовое описание |
| **posture** | Осанка | текстовое описание |
| **micro_expression** | Микроэкспрессия | текстовое описание |
| **lighting** | Освещение | текстовое описание |
| **blush** | Румянец | 0–4 (integer) |
| **sweat** | Пот | 0–4 (integer) |
| **pupils** | Зрачки | текстовое описание |

**Пример (Андрей У2-А):**
```json
{
  "clothing": "blue_shirt_jeans_watch",
  "posture": "sits_adjusts_sleeves_nervous",
  "micro_expression": "observant_hidden_jealousy_eyelids_raised",
  "lighting": "spotlight_dark",
  "blush": 0,
  "sweat": 0,
  "pupils": "normal_scanning"
}
```

**Пример (Андрей У4-А):**
```json
{
  "clothing": "shirt_on_shoulders_torse",
  "posture": "bewildered_hands_reach_uncertainly",
  "micro_expression": "breakthrough_eyes_wide_mix_fear_passion",
  "lighting": "dramatic_side_Rembrandt",
  "blush": 3,
  "sweat": 1,
  "pupils": "dilated_stunned"
}
```

---

## 5. LIGHTING MAP (7 диапазонов)

| Диапазон | Описание | Когда используется | Пример |
|----------|----------|-------------------|--------|
| **1** | Клинический белый | Нейтральный, отстранённый | У1-А, У3-Б (диссоциация) |
| **2** | Тусклый, размытый | Усталость, пустота | У6-А, У6-Б |
| **3** | Тёплый, янтарный | Интимный, безопасный | У2-А, У7-А |
| **4** | Контрастный, драматический | Перелом, страсть | У3-А, У4-А |
| **5** | Мягкий, диффузный | Нежность, aftercare | У4-Б, У7-Б |
| **6** | Холодный, синий | Одиночество, тревога | У1-А (ночь), У6-Б |
| **7** | Тёмный, Rembrandt | Пик, mystery | У4-А, У5-А |

---

## 6. СВЯЗЬ С R4 (ФМДР)

R5 добавляет визуальные данные к ФМДР-примерам R4:

```
**Мысль:** Они не знают, что я вижу.
**Действие:** [R5: sits at table, adjusts sleeves, observant hidden jealousy, warm spotlight]
**Речь:** «Ну что, ребята, всё нормально.»
```

---

## 7. ЧЕК-ЛИСТ САМОПРОВЕРКИ (R5)

```
□ Anatomic Anchor содержит 10+ блоков.
□ Visual Signature — одна строка, 100–200 слов, без эмоций.
□ Dynamic Visuals — 14 строк, каждая с 7 параметрами.
□ Blush/sweat ∈ [0,4].
□ Pupil_dynamics логичны: норма → dilated → max_dilated → constricted.
□ Signature items уникальны (не дублируют других персонажей).
□ Lighting Map соответствует подуровню.
```

---

*KB_R5_CORE.md | Voyage Narrative Engine | 2026-06-16*
