# KB_NARRATIVE_ANCHOR_SYSTEM.md
# Knowledge Base: Якорная система (Character Anchor + Visual Signature)
# Источник: ANDREY_SENIOR_MODULE_v1.json (visual_data), EGOR_MODULE_v1.json (visual_data)
# Назначение: консистентная визуальная идентичность персонажа в runtime и для генерации изображений
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. ДВА УРОВНЯ ЯКОРЯ

| Уровень | Название | Что это | Для чего | Формат |
|---------|----------|---------|----------|--------|
| **L1** | **Character Anchor** (Anatomic Anchor) | ДНК лица и тела. Неизменные черты. | Консистентность между сценами, сессиями, моделями генерации. | JSON (10+ параметров) |
| **L2** | **Visual Signature** | Компактная строка для промптов. | Быстрая вставка в текстовые промпты (SD, Midjourney, DALL-E). | String (1 строка, 100-200 слов) |

**Правило:** L1 → L2. Character Anchor (JSON) — источник истины. Visual Signature — производная от L1, обновляется только при изменении L1.

---

## 2. CHARACTER ANCHOR (L1) — структура JSON

**Источник:** `ANDREY_SENIOR_MODULE_v1.json` → `visual_data.anatomic_anchor`
**Источник:** `EGOR_MODULE_v1.json` → `visual_data.anatomic_anchor`

### 2.1 Обязательные блоки (10 параметров)

```json
{
  "anatomic_anchor": {
    "face_shape": "[форма + характер]",
    "forehead": "[ширина + линии]",
    "chin": "[форма + сила]",
    "overall": "[общее впечатление]",
    "eyes": {
      "color": "[цвет]",
      "shape": "[форма]",
      "gaze": "[характер взгляда]",
      "signature": "[уникальная черта]",
      "pupil_dynamics": "[U1-U2:normal, U3A:slightly_dilated, U4:dilated, U5A:max_dilated]"
    },
    "nose": {
      "shape": "[форма]",
      "signature": "[уникальная черта]",
      "dynamics": "[реакция на стресс/возбуждение]"
    },
    "lips": {
      "shape": "[форма]",
      "signature": "[уникальная черта]",
      "dynamics": "[реакция на стресс/возбуждение]",
      "resting": "[покой]",
      "speech": "[как влияет на речь]"
    },
    "skin": {
      "tone": "[тон]",
      "texture": "[текстура]",
      "dynamics": "[румянец/пот по подуровням]",
      "age_marks": "[возрастные признаки]",
      "sweat": "[U1-U3:minimal, U4-U5:light, U6:none]"
    },
    "hair": {
      "color": "[цвет]",
      "style": "[стрижка]",
      "texture": "[текстура]",
      "facial_hair": "[борода/щетина]"
    },
    "body": {
      "height": "[рост]",
      "weight": "[вес]",
      "type": "[тип]",
      "build": "[телосложение]",
      "posture": "[осанка]"
    },
    "signature_items": ["[уникальные предметы/привычки]"]
  }
}
```

### 2.2 Пример: Андрей Старший (из модуля)

```json
{
  "face_shape": "oval_strong_jaw_square_slightly_visible_muscles",
  "forehead": "broad_slight_lines",
  "chin": "strong_rounded_subtle_cleft",
  "overall": "warm_protector_approachable_strength",
  "eyes": {
    "color": "bright_blue",
    "shape": "almond_wide_set",
    "gaze": "observant_warm_scanning",
    "signature": "medium_lid_slight_hood",
    "pupil_dynamics": "U1-U2:normal_warm, U3A:slightly_dilated, U3B:constricted_distant, U4:dilated, U5A:max_dilated, U5B:soft_focus, U6A:half-closed, U7:normal_soft"
  },
  "nose": {
    "shape": "straight_strong_bridge_slightly_broad",
    "signature": "rounded_tip_downturned_smiling",
    "dynamics": "medium_symmetrical_flare_stress"
  },
  "lips": {
    "shape": "medium-full_symmetrical_soft",
    "signature": "medium-wide_warm_smile_reaches_eyes",
    "resting": "gentle_closed-mouth_left_higher",
    "dynamics": "tightens_U3B_flattens_U3A",
    "speech": "measured_warm_philosophical"
  },
  "skin": {
    "tone": "fair_warm_undertone",
    "texture": "smooth_slightly_weathered",
    "dynamics": "healthy_flush_U3A_U4B",
    "age_marks": "faint_crow's_feet_38yo",
    "sweat": "U1-U3:minimal, U4-U5:light_forehead, U6A:none"
  },
  "hair": {
    "color": "light_ash_blond",
    "style": "short_dense_evenly_trimmed",
    "texture": "thick_straight_slightly_coarse",
    "facial_hair": "none_or_2day_stubble"
  },
  "body": {
    "height": 180,
    "weight": 85,
    "type": "athletic_mesomorph",
    "build": "broad_shoulders_powerful_chest_thick_neck",
    "posture": "upright_relaxed_open_shoulders_slight_forward_lean"
  },
  "signature_items": [
    "expensive_watch",
    "adjusts_sleeves_U3B",
    "opens_palms_U1B",
    "crosses_arms_U2A"
  ]
}
```

### 2.3 Пример: Егор (контраст для проверки уникальности)

```json
{
  "face_shape": "oval_angular_jaw_sharp_defined_masculine",
  "overall": "predatory_elegance_wolf-like",
  "eyes": {
    "color": "gray",
    "gaze": "intense_calculating_predatory",
    "signature": "left_squint_when_lying",
    "pupil_dynamics": "U1-U3:normal_cold, U4-U5:dilated, U3A-U5B:constricted, U4B-U5A:max_dilated"
  },
  "lips": {
    "signature": "asymmetrical_smirk_left_higher",
    "dynamics": "tightens_anger_flattens_lying"
  },
  "signature_items": [
    "expensive_watch",
    "fingers_tap_anxious_clench_regressing"
  ]
}
```

**Контраст (проверка уникальности):**
| Черта | Андрей | Егор |
|-------|--------|------|
| Взгляд | warm, observant, scanning | intense, calculating, predatory |
| Улыбка | gentle, reaches eyes, left higher | asymmetrical smirk, left higher |
| Основа | warm protector | predatory elegance |
| Signature items | adjusts sleeves, opens palms | fingers tap, clench when regressing |

---

## 3. VISUAL SIGNATURE (L2) — структура строки

**Источник:** `ANDREY_SENIOR_MODULE_v1.json` → `visual_data.visual_signature_string`
**Источник:** `EGOR_MODULE_v1.json` → `visual_data.visual_signature_string`

### 3.1 Формат

Одна строка, 100-200 слов, содержит:
1. **Возраст + пол + телосложение**
2. **Рост/вес** (если релевантно)
3. **Волосы** (цвет, стиль, текстура)
4. **Глаза** (цвет, форма, взгляд)
5. **Лицо** (форма, челюсть, скулы, нос, губы)
6. **Кожа** (тон, текстура)
7. **Особенности** (борода, шрамы, предметы)
8. **Одежда** (базовая, если персонаж одет)
9. **Впечатление** (эмоциональное качество: warm, predatory, shy, etc.)

### 3.2 Пример: Андрей Старший

```
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense evenly trimmed hair, 
bright blue almond wide-set eyes with warm observant gaze, strong square jaw with visible 
muscle definition, medium-high broad cheekbones, gentle closed-mouth smile left corner 
slightly higher, medium-full soft lips, fair warm skin with slight weathered texture, 
thick neck powerful chest broad shoulders, clean-shaven, blue casual elegant shirt with 
rolled-up sleeves, expensive watch
```

### 3.3 Пример: Егор

```
handsome athletic man 35yo, 180cm/83kg, dark ash-blond short military cut textured top, 
intense gray almond eyes with predatory calculating gaze and slight left eye squint, 
sharp angular jaw with visible clench muscles, high prominent cheekbones, slight 
asymmetrical smirk, medium cupid bow thin lips, light olive smooth skin, no facial hair, 
broad shoulders narrow waist, visible muscle definition, expensive watch
```

### 3.4 Правила Visual Signature

- **Без эмоциональных оценок** (не "красивый", а "handsome" — нейтральное описание).
- **Без контекста** (не "в баре", "в сауне" — это Dynamic Visuals, не Signature).
- **Без динамики** (не "улыбается", "напрягается" — это микроэкспрессии, не Anchor).
- **Порядок строгий**: волосы → глаза → лицо → кожа → тело → особенности → одежда.
- **Повторяемость**: одна и та же строка вставляется в каждый промпт для генерации.

---

## 4. ЯКОРНАЯ СИСТЕМА В RUNTIME

### 4.1 Первое упоминание в тексте (narrative)

```
[Первое упоминание] = полное описание (Visual Signature + Dynamic Visuals текущего U-X)

Пример:
«Андрей стоял у стойки — высокий, широкоплечий, светлые волосы аккуратно подстрижены, 
голубые глаза с тёплым, но внимательным взглядом. Синяя рубашка с закатанными рукавами, 
дорогие часы на запястье. Он не смотрел на кого-то конкретно, но видел всё.»
```

### 4.2 Последующие упоминания (narrative)

```
[Последующие] = короткие якоря (2-3 черты) + текущая динамика

Пример:
«Андрей улыбнулся — тот самый, с приподнятым левым уголком.»
«Он поправил рукава часов, глаза остались на Кире.»
«Тёплый взгляд на мгновение стал холодным — потом снова щит.»
```

### 4.3 Якоря для других персонажей (cross-persona)

Каждый персонаж запоминает якоря других:
```
memory.emotional_anchors: [
  {name: "anchor_andrey_smile", source: "Левый уголок выше, защитная", intensity: 7, count: 3},
  {name: "anchor_andrey_sleeves", source: "Поправляет рукава при тревоге", intensity: 6, count: 2}
]
```

**Кумулятивность:** count кратен 5 → intensity +1 (макс. 10).

---

## 5. DYNAMIC VISUALS (изменяемые по U-X)

**Источник:** `ANDREY_SENIOR_MODULE_v1.json` → `dynamic_visuals._table`
**Источник:** `EGOR_MODULE_v1.json` → `dynamic_visuals._table`

### 5.1 Структура таблицы (14 подуровней × 7 параметров)

| Параметр | Описание | Диапазон |
|----------|----------|----------|
| **clothing** | Одежда | текстовое описание |
| **posture** | Осанка | текстовое описание |
| **micro_expression** | Микроэкспрессия | текстовое описание |
| **lighting** | Освещение | текстовое описание |
| **blush** | Румянец | 0-4 (integer) |
| **sweat** | Пот | 0-4 (integer) |
| **pupils** | Зрачки | текстовое описание |

### 5.2 Пример строки: Андрей У2-А

```json
{
  "level": "U2-A",
  "clothing": "blue_shirt_jeans_watch",
  "posture": "sits_adjusts_sleeves_nervous",
  "micro_expression": "observant_hidden_jealousy_eyelids_raised",
  "lighting": "spotlight_dark",
  "blush": 0,
  "sweat": 0,
  "pupils": "normal_scanning"
}
```

### 5.3 Пример строки: Андрей У4-А (пик)

```json
{
  "level": "U4-A",
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

## 6. АУДИТ ЯКОРНОЙ СИСТЕМЫ

```
□ Character Anchor JSON содержит все 10 обязательных блоков.
□ Visual Signature — одна строка, 100-200 слов, без эмоциональных оценок.
□ Visual Signature производна от Character Anchor (нет противоречий).
□ Dynamic Visuals — 14 строк, каждая с 7 параметрами.
□ Blush/sweat ∈ [0,4] (или [0,10] если модель поддерживает).
□ Pupil_dynamics логичны: норма → dilated → max_dilated → constricted (после).
□ Signature items уникальны (не дублируют других персонажей).
□ Cross-persona: якоря других персонажей описаны в memory.
□ Первое упоминание в тексте = полное. Последующие = 2-3 черты.
```

---

## 7. СВЯЗЬ С STOP-FRAME

Character Anchor + Visual Signature + Dynamic Visuals (текущий U-X) = **данные для Stop-Frame Engineer** (SFE).

SFE собирает:
1. **ANCHOR** = Visual Signature (L2) + текущий clothing из Dynamic Visuals.
2. **SCENE** = posture + micro_expression + lighting (из текущего U-X).
3. **BACKGROUND** = локация из сценария (bar/sauna/kitchen).
4. **TECHNICAL** = blush, sweat, pupils (числовые параметры для CFG/Steps).

Формат SFE-промпта:
```
[ANCHOR] handsome athletic man 38yo, light ash-blond hair... + blue shirt, jeans
[SCENE] sits at table, adjusts sleeves nervously, observant hidden jealousy, spotlight dark
[BACKGROUND] bar, evening, warm amber lighting
[TECHNICAL] blush:0, sweat:0, pupils:normal_scanning, style:photorealistic, angle:medium_shot
```

---

*KB_NARRATIVE_ANCHOR_SYSTEM.md | Voyage Narrative Engine | 2026-06-16*
*Источники: ANDREY_SENIOR_MODULE_v1.json, EGOR_MODULE_v1.json*
*Персонажи: Андрей Старший, Егор (контрасты для проверки уникальности)*
