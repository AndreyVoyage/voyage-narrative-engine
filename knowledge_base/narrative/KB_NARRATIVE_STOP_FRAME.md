# KB_NARRATIVE_STOP_FRAME.md
# Knowledge Base: Stop-Frame Engineer (SFE)
# Назначение: генерация промптов для изображений (Stable Diffusion, Midjourney, DALL-E) из персонажа + сценария
# Источники: ANDREY_SENIOR_MODULE_v1.json (dynamic_visuals + visual_data), EGOR_MODULE_v1.json (dynamic_visuals + visual_data)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. ЧТО ТАКОЕ STOP-FRAME

**Stop-Frame** — это "замороженный кадр" из narrative. Описывает визуальное состояние персонажа в конкретный момент (Turn N) для генерации изображения.

**Не путать с:**
- **Character Anchor** = постоянные черты (ДНК лица).
- **Dynamic Visuals** = таблица 14×7 (все состояния).
- **Stop-Frame** = один конкретный кадр: Anchor + текущий U-X + локация.

**Частота:** каждые N ходов (N не формализовано, обычно 3-5 ходов или на триггерные моменты).

---

## 2. СТРУКТУРА STOP-FRAME (4 блока)

| Блок | Что содержит | Откуда берётся | Формат |
|------|-------------|----------------|--------|
| **ANCHOR** | Visual Signature + текущая одежда | `visual_data.visual_signature_string` + `dynamic_visuals.clothing` (текущий U-X) | String (1 строка) |
| **SCENE** | Осанка + микроэкспрессия + освещение | `dynamic_visuals.posture` + `micro_expression` + `lighting` (текущий U-X) | String (1 строка) |
| **BACKGROUND** | Локация + атмосфера + время суток | `scenarios/[scenario].location` + `atmosphere` | String (1 строка) |
| **TECHNICAL** | Числовые параметры + стиль + ракурс | `dynamic_visuals.blush` + `sweat` + `pupils` + CFG/Steps | String + JSON |

---

## 3. БЛОК 1: ANCHOR

### Формирование
```
ANCHOR = Visual_Signature + " + " + current_clothing
```

**Пример Андрей (У2-А, бар):**
```
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense evenly trimmed hair, 
bright blue almond wide-set eyes with warm observant gaze, strong square jaw with visible 
muscle definition, medium-high broad cheekbones, gentle closed-mouth smile left corner 
slightly higher, medium-full soft lips, fair warm skin with slight weathered texture, 
thick neck powerful chest broad shoulders, clean-shaven, expensive watch, 
+ blue shirt, jeans, watch visible
```

**Пример Андрей (У4-А, треугольник):**
```
... (та же Visual Signature) + 
shirt on shoulders, torse exposed, sweat on forehead
```

**Правила:**
- Visual Signature — неизменна (копируется из модуля).
- Clothing — меняется по U-X (из Dynamic Visuals).
- Signature items (часы) — всегда присутствуют, если visible.

---

## 4. БЛОК 2: SCENE

### Формирование
```
SCENE = posture + ", " + micro_expression + ", " + lighting
```

**Пример Андрей (У2-А, бар):**
```
sits at table, adjusts sleeves nervously, observant hidden jealousy, eyelids raised, 
spotlight from above, dark corners, warm amber ambiance
```

**Пример Андрей (У4-А, пик):**
```
bewildered, hands reach uncertainly toward both, breakthrough expression, eyes wide mix 
of fear and passion, dramatic side Rembrandt lighting, high contrast
```

**Пример Егор (У3-Б, агрессия):**
```
aggressive, nose forward, fists clenched, snarling anger, teeth visible, eyelids wide, 
contrasty dark lighting, sweat on temple, muscles tense
```

**Правила:**
- Posture — физическое положение тела.
- Micro_expression — лицо (глаза, рот, брови). Не эмоции, а мышцы.
- Lighting — из Dynamic Visuals, но можно усилить локацией.

---

## 5. БЛОК 3: BACKGROUND

### Формирование
```
BACKGROUND = location_name + ", " + atmosphere + ", " + time_of_day + ", " + temperature/mood
```

**Пример (бар, вечер):**
```
bar counter, evening, warm amber lighting, intimate crowd blurred in background, 
wooden surfaces, glass reflections, soft bokeh
```

**Пример (сауна, парилка):**
```
private sauna, steam room, 90°C heat, warm wood panels, steam diffusion, 
dim amber lighting, intimate atmosphere, contrasting temperatures
```

**Пример (кухня, утро):**
```
kitchen, morning after, soft golden light through curtains, cooking sounds, 
warm domestic atmosphere, eggs and meat on counter, steam rising
```

**Правила:**
- BACKGROUND из сценария (`SCENARIO_SAUNA_QUARTET.json` → `location`).
- Не перегружать деталями — фон должен быть размытым (bokeh).
- Цветовая гамма должна гармонировать с lighting из SCENE.

---

## 6. БЛОК 4: TECHNICAL

### 6.1 Числовые параметры (из Dynamic Visuals)

```json
{
  "blush": 0,
  "sweat": 0,
  "pupils": "normal_scanning",
  "eye_dilation": "normal",
  "muscle_tension": "low"
}
```

**Перевод в текст промпта:**
```
blush: none, sweat: none, pupils normal, relaxed muscles
```

**Пример пик (У4-А):**
```json
{
  "blush": 3,
  "sweat": 1,
  "pupils": "dilated_stunned",
  "eye_dilation": "dilated",
  "muscle_tension": "high"
}
```

**Перевод:**
```
visible blush on cheekbones, light sweat on forehead, dilated pupils stunned expression, 
tense muscles, veins visible on neck
```

### 6.2 CFG / Steps (для Stable Diffusion)

| Параметр | Базовое | Пик (У4-У5) | Тревога (У3) | Утро (У6-У7) |
|----------|---------|-------------|--------------|--------------|
| **CFG** | 7 | 5-6 (мягче, меньше артефактов) | 8-9 (жёстче, детали) | 7-8 |
| **Steps** | 30 | 40 (детальнее кожа) | 25 (быстрее, raw) | 35 |
| **Sampler** | DPM++ 2M Karras | Euler a (мягкость) | DPM++ 2M (чёткость) | DPM++ 2M Karras |

**Пример TECHNICAL блока (SD):**
```
CFG: 7, Steps: 30, Sampler: DPM++ 2M Karras, 
Style: photorealistic, RAW photo, 
Angle: medium shot, eye level, 
Focus: face + upper body, 
Bokeh: background blurred f/1.8, 
Negative: cartoon, anime, 3d render, painting, ugly, deformed hands
```

### 6.3 Размер / Разрешение

- **Портрет:** 512×768 (вертикальный) — лицо + плечи.
- **Средний план:** 768×512 (горизонтальный) — тело + локация.
- **Деталь лица:** 512×512 + hires.fix (для глаз/зрачков).

---

## 7. ИТОГОВЫЙ ПРОМПТ (SFE-OUTPUT)

### Пример: Андрей, У2-А, бар

```markdown
## STOP-FRAME: ANDREY_U2A_BAR
**Turn:** 3
**Trigger:** gaze_3sec_kira

### ANCHOR
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense evenly trimmed hair, 
bright blue almond wide-set eyes with warm observant gaze, strong square jaw with visible 
muscle definition, medium-high broad cheekbones, gentle closed-mouth smile left corner 
slightly higher, medium-full soft lips, fair warm skin with slight weathered texture, 
thick neck powerful chest broad shoulders, clean-shaven, expensive watch, 
blue shirt unbuttoned at collar, jeans, watch visible

### SCENE
sits at bar table, left hand adjusts sleeve nervously, right hand on glass, 
eyes fixed on Kira but seemingly casual, observant hidden jealousy, eyelids slightly raised, 
warm spotlight from above, dark corners around

### BACKGROUND
 upscale bar, evening, warm amber lighting, blurred crowd, wooden surfaces, 
glass reflections, intimate atmosphere, soft bokeh

### TECHNICAL
blush: 0, sweat: 0, pupils: normal_scanning, relaxed posture, 
CFG: 7, Steps: 30, Sampler: DPM++ 2M Karras, 
Style: photorealistic, RAW photo, 35mm, 
Angle: medium shot, eye level, 
Focus: face and upper body, 
Negative: cartoon, anime, 3d render, painting, ugly, deformed hands, extra fingers
```

### Пример: Андрей, У4-А, треугольник

```markdown
## STOP-FRAME: ANDREY_U4A_TRIANGLE
**Turn:** 12
**Trigger:** cold_splash + kira_marina_closeness

### ANCHOR
... (та же Visual Signature) + 
shirt on shoulders, torse exposed, light sweat on chest

### SCENE
bewildered, hands reach toward both women uncertainly, first time without plan, 
breath accelerated, breakthrough eyes wide mix of fear and passion, 
dramatic side Rembrandt lighting, high contrast shadows

### BACKGROUND
private sauna, shower pool area, cold water contrast, steam rising, 
90°C heat, intimate atmosphere, contrasting temperatures, wet skin

### TECHNICAL
blush: 3, sweat: 1, pupils: dilated_stunned, tense muscles, 
CFG: 5, Steps: 40, Sampler: Euler a, 
Style: photorealistic, cinematic lighting, 
Angle: medium close-up, slightly low angle, 
Focus: face and hands, 
Negative: ...
```

---

## 8. КОГДА ГЕНЕРИРОВАТЬ STOP-FRAME

| Событие | Частота | Пример |
|---------|---------|--------|
| **Триггерный момент** | Обязательно | Переход U-X, ключевой диалог, первый физический контакт |
| **Каждые N ходов** | Опционально (N=3-5) | Для визуальной консистентности сессии |
| **Checkpoint** | Опционально | Фиксация сессии — генерация "портрета текущего состояния" |
| **Finalize** | Опционально | Итоговый кадр сессии — для архива |

**Правило:** Не генерировать каждый ход. Только на **триггеры** или **раз в 3-5 ходов**.

---

## 9. АНТИ-ПРОМПТЫ (Negative Prompts)

**Базовый анти-пrompt для всех персонажей VNE:**
```
cartoon, anime, 3d render, painting, illustration, ugly, deformed, mutated, 
extra limbs, extra fingers, malformed hands, bad anatomy, bad proportions, 
blurry, out of focus, watermark, signature, text, logo, cropped, worst quality, 
low quality, normal quality, jpeg artifacts, duplicate, morbid, mutilated, 
missing arms, missing legs, extra arm, extra leg, fused fingers, too many fingers, 
long neck, cross-eyed, mutated hands, polar lowres, bad face, cloned face
```

**Персонаж-специфичный анти-prompt (Андрей):**
```
aggressive expression, angry eyes, predatory gaze, sharp teeth, violent pose, 
bearded, long hair, bald, obese, skinny, pale skin, cold eyes, gray eyes, 
left eye squint (это Егор, не Андрей), asymmetrical smirk (Егор)
```

---

## 10. АУДИТ STOP-FRAME

```
□ ANCHOR содержит Visual Signature (неизменная часть) + текущую одежду.
□ ANCHOR не содержит эмоций или контекста ("в баре", "нервный").
□ SCENE содержит posture + micro_expression + lighting.
□ SCENE не содержит одежду (это ANCHOR) или локацию (это BACKGROUND).
□ BACKGROUND содержит локацию + атмосферу + время.
□ BACKGROUND не содержит персонажа (это ANCHOR + SCENE).
□ TECHNICAL содержит числовые параметры blush/sweat/pupils.
□ TECHNICAL содержит CFG/Steps/Sampler для SD.
□ Negative prompt присутствует и не конфликтует с персонажем.
□ Размер изображения указан (512×768 / 768×512 / 512×512).
```

---

*KB_NARRATIVE_STOP_FRAME.md | Voyage Narrative Engine | 2026-06-16*
*Источники: ANDREY_SENIOR_MODULE_v1.json, EGOR_MODULE_v1.json*
*Персонажи: Андрей Старший (примеры), Егор (контраст)*
