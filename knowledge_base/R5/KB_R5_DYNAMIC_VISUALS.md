# KB_R5_DYNAMIC_VISUALS.md
# Knowledge Base: Роль 5 — Dynamic Visuals Specification
# Назначение: 14×7 параметров для каждого подуровня (U1-A … U7-B)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. ФОРМАТ ДАННЫХ

Для каждого из 14 подуровней создаётся JSON-объект с 7 параметрами:

```json
{
  "sublevel": "U2-A",
  "clothing": "string",
  "posture": "string",
  "micro_expression": "string",
  "lighting": "string",
  "blush": 0,
  "sweat": 0,
  "pupils": "string"
}
```

---

## 2. ПАРАМЕТРЫ (7 штук)

### 2.1 clothing (одежда)
**Формат:** snake_case строка, 3–5 токенов.

**Примеры:**
- `blue_shirt_jeans_watch` — У2-А (бар, адаптивный)
- `shirt_on_shoulders_torse` — У4-А (пик страсти)
- `black_turtleneck_coat` — У1-А (барьерный)
- `loose_sweatpants_barefoot` — У7-Б (aftercare)

**Правила:**
- Без цветовых прилагательных, если цвет не ключевой (не «красная рубашка»).
- Указывать signature items (часы, кольцо, шрам).
- У4-А и выше: может быть частично раздетым (не нагота — это сценарий, а не персонаж).

### 2.2 posture (осанка)
**Формат:** snake_case, 2–4 токена.

**Примеры:**
- `sits_adjusts_sleeves_nervous` — У2-А
- `bewildered_hands_reach_uncertainly` — У4-А
- `aggressive_forward_hands_on_table` — У5-А
- `curled_fetal_protecting_chest` — У6-Б
- `relaxed_leaning_head_tilted` — У7-Б

**Правила:**
- Описывать позу, не действие (не «подходит к двери», а «стоит, плечи напряжены»).
- Руки — важны: open_palms, clenched_fists, touching_face, crossed_arms.

### 2.3 micro_expression (микроэкспрессия)
**Формат:** snake_case, 3–5 токена.

**Примеры:**
- `observant_hidden_jealousy_eyelids_raised` — У2-А
- `breakthrough_eyes_wide_mix_fear_passion` — У4-А
- `distant_gaze_avoidant` — У3-Б
- `soft_eyes_half_closed_relax` — У7-Б

**Правила:**
- Не указывать эмоцию напрямую — только физические признаки (eyes_wide, jaw_clenched, lip_bitten).
- Скрытые эмоции через контраст: «warm smile, cold eyes».

### 2.4 lighting (освещение)
**Формат:** строка из Lighting Map (KB_R5_CORE.md §5).

**Примеры:**
- `spotlight_dark` — У2-А (фокус на персонаже)
- `dramatic_side_Rembrandt` — У4-А (контраст, страсть)
- `soft_diffused` — У7-Б (aftercare)
- `clinical_white` — У1-А (диссоциация)

### 2.5 blush (румянец)
**Формат:** integer ∈ [0, 4].

| Значение | Описание | Когда |
|----------|----------|-------|
| 0 | Нет | Барьерные, нейтральные |
| 1 | Лёгкий | Стыд, лёгкое волнение |
| 2 | Умеренный | Волнение, страсть |
| 3 | Сильный | Пик возбуждения, стыд |
| 4 | Максимальный | Пик страсти, регрессия |

### 2.6 sweat (пот)
**Формат:** integer ∈ [0, 4].

| Значение | Описание | Когда |
|----------|----------|-------|
| 0 | Нет | Барьерные, холодные |
| 1 | Лёгкий | Нервозность, физическая нагрузка |
| 2 | Умеренный | Тревога, страсть |
| 3 | Сильный | Пик, страх, регрессия |
| 4 | Максимальный | Паника, агония, тяжёлая физическая нагрузка |

### 2.7 pupils (зрачки)
**Формат:** строка, динамическая шкала.

| Состояние | Описание | Когда |
|-----------|----------|-------|
| `normal` | Норма | У1-А, У2-А, У7-Б |
| `slightly_dilated` | Лёгкое расширение | У2-А (возбуждение), У3-А |
| `dilated` | Расширены | У4-А (страсть), У5-А (ярость) |
| `max_dilated` | Максимально | У6-А (паника), У4-А (пик) |
| `constricted` | Сужены | У1-А (яркий свет), У6-Б (опиоиды, диссоциация) |
| `pinpoint` | Точка | У6-Б (передоз, тяжёлая диссоциация) |

---

## 3. СВЯЗЬ С ВСЦНО (R2)

| ВСЦНО | Влияние на visuals |
|-------|-------------------|
| ВЛ↑ | posture: более открытая, shoulders back; blush: может быть 0 (контроль) |
| СТ↑ | posture: напряжённая, jaw_clenched; sweat: 1–2; pupils: dilated |
| НЖ↑ | micro_expression: warmth, soft_eyes; blush: 2–3; lighting: warm |
| ОГ↑ | posture: отстранённая, arms_crossed; micro_expression: distant; lighting: cold |

---

## 4. ПРИМЕР ПОЛНОЙ ТАБЛИЦЫ (Андрей Старший, 14 строк)

```json
[
  {"sublevel":"U1-A","clothing":"black_turtleneck_coat","posture":"upright_bar_leaning","micro_expression":"mask_controlled_hands_in_pockets","lighting":"clinical_white","blush":0,"sweat":0,"pupils":"normal"},
  {"sublevel":"U2-A","clothing":"blue_shirt_jeans_watch","posture":"sits_adjusts_sleeves_nervous","micro_expression":"observant_hidden_jealousy_eyelids_raised","lighting":"spotlight_dark","blush":0,"sweat":0,"pupils":"normal"},
  {"sublevel":"U3-A","clothing":"unbuttoned_shirt_torse","posture":"leaning_tension_visible","micro_expression":"intense_focus_lips_tight","lighting":"dramatic_side","blush":2,"sweat":1,"pupils":"slightly_dilated"},
  {"sublevel":"U4-A","clothing":"shirt_on_shoulders_torse","posture":"bewildered_hands_reach_uncertainly","micro_expression":"breakthrough_eyes_wide_mix_fear_passion","lighting":"dramatic_side_Rembrandt","blush":3,"sweat":1,"pupils":"dilated"},
  {"sublevel":"U5-A","clothing":"disheveled_shirt_bare_torse","posture":"aggressive_forward_hands_on_table","micro_expression":"predatory_gaze_jaw_clenched","lighting":"dark_Red","blush":2,"sweat":2,"pupils":"dilated"},
  {"sublevel":"U6-A","clothing":"loose_clothes_stained","posture":"collapsed_against_wall","micro_expression":"dilated_pupils_shock","lighting":"flashing_neon","blush":4,"sweat":3,"pupils":"max_dilated"},
  {"sublevel":"U7-A","clothing":"soft_sweater","posture":"leaning_close_gentle","micro_expression":"soft_eyes_half_closed","lighting":"warm_amber","blush":2,"sweat":0,"pupils":"normal"},
  {"sublevel":"U1-B","clothing":"black_turtleneck_coat","posture":"rigid_back_turned","micro_expression":"mask_eyes_empty","lighting":"clinical_white","blush":0,"sweat":0,"pupils":"normal"},
  {"sublevel":"U2-B","clothing":"white_shirt_loose","posture":"leans_table_fingers_tap","micro_expression":"cool_gaze_calculating","lighting":"blue_cold","blush":0,"sweat":0,"pupils":"normal"},
  {"sublevel":"U3-B","clothing":"casual_jeans_shirt","posture":"slouched_hands_in_pockets","micro_expression":"distant_gaze_avoidant","lighting":"soft_diffused","blush":0,"sweat":0,"pupils":"slightly_dilated"},
  {"sublevel":"U4-B","clothing":"shirt_unbuttoned_rolled_sleeves","posture":"sits_edge_leaning_in","micro_expression":"vulnerable_eyes_pleading","lighting":"soft_golden","blush":2,"sweat":1,"pupils":"dilated"},
  {"sublevel":"U5-B","clothing":"white_shirt_stained_torn","posture":"hunched_shoulders_tense","micro_expression":"wild_eyes_gaze_darting","lighting":"dark_Red","blush":3,"sweat":2,"pupils":"dilated"},
  {"sublevel":"U6-B","clothing":"loose_sweatpants_barefoot","posture":"curled_fetal_protecting_chest","micro_expression":"vacant_eyes_tears_dried","lighting":"soft_blue","blush":0,"sweat":0,"pupils":"constricted"},
  {"sublevel":"U7-B","clothing":"loose_sweatpants_barefoot","posture":"relaxed_leaning_head_tilted","micro_expression":"soft_eyes_half_closed_relax","lighting":"soft_diffused","blush":1,"sweat":0,"pupils":"normal"}
]
```

---

*KB_R5_DYNAMIC_VISUALS.md | Voyage Narrative Engine | 2026-06-16*
