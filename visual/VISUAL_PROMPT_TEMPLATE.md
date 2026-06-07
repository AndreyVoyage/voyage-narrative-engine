# 🎨 VISUAL PROMPT TEMPLATE — Шаблон для генерации изображений

> **Версия:** 1.0 (совместимо с Voyage Narrative Engine v1.0.0)
> **Назначение:** Стандартизированный формат для всех visual prompts
> **Формат:** JSON (для API) + Markdown (для чтения)

---

## 📋 Структура JSON-файла визуальной сцены

```json
{
  "id": "VS_XXX",
  "name": "Название сцены",
  "kira_level": "U1-U7",
  "characters": ["K", "S", "Я"],
  "reference_persona": "KIRA_MODULE.json / SERGEY_MODULE.json",
  "emotional_state": "ключевое_состояние",
  "flags_set": ["flag_1", "flag_2"],
  "emotional_anchors": ["якорь_1", "якорь_2"],
  "symbol": "SXXX:U?→U?:chars:loc:time:action",

  "visual_parameters": {
    "subject": "описание субъекта для image generation",
    "pose": "поза персонажа",
    "clothing": "одежда",
    "environment": "окружение",
    "lighting": "освещение",
    "mood": "настроение",
    "style": "стиль (photorealistic, cinematic, anime, etc.)",
    "references": ["фильм_1", "фотограф_1", "стиль_1"]
  },

  "qwen_prompt": "Готовый промпт для Qwen/Stable Diffusion/Flux (30-60 слов)",
  "negative_prompt": "Что исключить (deformed, bad anatomy, etc.)",

  "content_rating": "PG / PG-13 / R / NC-17",
  "safety_notes": "Особые указания по безопасности"
}
```

---

## 🎭 Параметры персонажей (ссылка на KIRA_MODULE.json)

Вместо дублирования описания Киры в каждом промпте — используйте ссылку:

```
[REFERENCE: KIRA_MODULE.json — physical_attributes]
[REFERENCE: KIRA_MODULE.json — clothing_current]
[REFERENCE: KIRA_MODULE.json — psychology — только visual_relevant]
```

**Для image generation добавляйте только:**
- Конкретную позу этой сцены
- Конкретную одежду (если отличается от модуля)
- Конкретное выражение лица
- Конкретные аксессуары сцены

---

## 🎨 Формат Qwen/SD/Flux Prompt

### Структура (порядок важен):

```
[Качество] + [Субъект] + [Одежда] + [Поза] + [Окружение] + [Освещение] + [Камера] + [Стиль]
```

### Примеры качества:
- `masterpiece, best quality, photorealistic, 8k, film grain`
- `score_9, score_8_up, score_7_up` (для Pony Diffusion)

### Примеры субъекта:
- `1girl, athletic 24yo woman, blonde curly hair, wet hair`
- `1boy, muscular 35yo man, short dark hair, gray stubble`

### Примеры позы:
- `sitting on red leather mat, hugging knees, head down, crying`
- `standing behind, hands on her thighs, looking down at her`

### Примеры окружения:
- `empty gym, night, dark background, red mat center, mirror wall`
- `bedroom, morning, warm sunlight through window, dark sheets`

### Примеры освещения:
- `dramatic top lighting, cold blue and warm amber, Rembrandt lighting`
- `soft morning light, golden hour, warm orange glow, bokeh background`

### Примеры камеры:
- `medium close-up, shallow depth of field, 85mm lens, cinematic composition`
- `medium shot, side angle, film grain, 35mm photography`

### Примеры стиля:
- `photorealistic, cinematic, film grain, 8k, David Dubnitskiy style`
- `cinematic still, movie screenshot, dramatic lighting, color grading`

---

## ⚠️ Negative Prompt (что исключить)

```
score_6, score_5, score_4, 3d, cartoon, anime, deformed, bad anatomy, 
extra limbs, blurry, low quality, watermark, text, signature, 
mutated hands, poorly drawn face, poorly drawn hands, missing fingers
```

---

## 📊 Content Rating Guide

| Рейтинг | Описание | Примеры сцен |
|---------|----------|-------------|
| **PG** | Нет напряжения, романтика, улыбки | Утро, кофе, ленивое счастье |
| **PG-13** | Намёки, флирт, тёплые взгляды | У1-У2, зеркальный взгляд |
| **R** | Напряжение, влажная кожа, прикосновения | У3-У4, растяжка, приседания |
| **NC-17** | Пик напряжения, срыв логики, после | У4-пик, У5-aftercare |

---

## 🔗 Связь с SCENARIO.json

Каждая visual scene привязана к сценарию:

```json
{
  "scenario_id": "SC_006",
  "visual_scene_id": "VS_006",
  "choice_point_branch": "CP_1.1A",
  "timing": "peak_moment"
}
```

---

## 📝 Пример полного файла: VS_007 (Кира одна в зале)

```json
{
  "id": "VS_007",
  "name": "Собери меня — Кира одна на красном мате",
  "kira_level": "U5",
  "characters": ["K"],
  "reference_persona": "KIRA_MODULE.json",
  "emotional_state": "destruction_and_rebirth",
  "flags_set": ["gym_aftercare_alone", "kira_crying_on_mat", "red_mat_symbol"],
  "emotional_anchors": ["собери меня", "я развалилась на части"],
  "symbol": "S007:U4→U5:K:gym:night:alone_aftercare",

  "visual_parameters": {
    "subject": "1girl, athletic 24yo woman, blonde curly hair, messy wet hair, crying, tears on cheeks",
    "pose": "sitting on red leather mat, hugging knees, head down, body curled in ball, barefoot",
    "clothing": "black crop top displaced, black shorts displaced, wet fabric clinging to skin",
    "environment": "empty gym, night, dark background, fluorescent lights, red mat center frame, mirror wall reflection",
    "lighting": "dramatic top lighting, cold blue white, warm amber accent from distant lamp, Rembrandt lighting, chiaroscuro",
    "mood": "psychological drama, destruction, rebirth, aftercare, vulnerability, strength in brokenness",
    "style": "photorealistic, cinematic, film grain, 8k, Black Swan aesthetic, David Dubnitskiy style",
    "references": ["Black Swan", "Requiem for a Dream", "David Dubnitskiy", "Whiplash"]
  },

  "qwen_prompt": "masterpiece, best quality, photorealistic, 8k, film grain, 1girl, athletic 24yo woman, blonde curly messy wet hair, crying, tears on cheeks, sitting on red leather mat, hugging knees, head down, body curled, barefoot, black crop top displaced, black shorts displaced, wet fabric clinging, empty gym, night, dark background, fluorescent top lighting, cold blue and warm amber, dramatic shadows, Rembrandt lighting, chiaroscuro, cinematic composition, medium shot, shallow depth of field, 85mm lens, Black Swan aesthetic, David Dubnitskiy style --ar 16:9",

  "negative_prompt": "score_6, score_5, score_4, 3d, cartoon, anime, deformed, bad anatomy, extra limbs, blurry, low quality, watermark, text, signature, mutated hands, poorly drawn face, missing fingers, extra fingers",

  "content_rating": "R",
  "safety_notes": "U5 aftercare. Emotional vulnerability, crying, but no explicit nudity. Focus on psychological state, not sexual content. Red mat as symbol of passion/pain."
}
```

---

## 🔄 Workflow генерации изображения

```
[Backend получает ответ Киры]
    ↓
[Парсит AUTO_VISUAL блок или определяет visual_scene_id по STATE]
    ↓
[Загружает VS_XXX.json]
    ↓
[Подставляет переменные из KIRA_MODULE.json (если нужно)]
    ↓
[Формирует финальный prompt: VS.qwen_prompt + дополнения]
    ↓
[Отправляет в API: Qwen / Stable Diffusion / Flux / Midjourney]
    ↓
[Получает изображение → сохраняет → возвращает URL]
    ↓
[Пользователь видит текст + картинку]
```

---

## 📁 Список всех visual scenes

| ID | Название | Уровень | Персонажи | Локация | Рейтинг |
|----|----------|---------|-----------|---------|---------|
| VS_001 | Проснись, милый — Селфи | У1 | K | home | PG-13 |
| VS_003 | Утренняя провокация — Зеркало | У3 | K | home | R |
| VS_002 | Растяжка в пустом зале | У2→У3 | K+S | gym | R |
| VS_004 | Приседания со штангой | У3→У4 | K+S | gym | R |
| VS_005 | Растяжка на красном мате — Касание | У3→У4 | K+S | gym | R |
| VS_006 | Своеволие на красном мате — Пик | У4-пик | K+S | gym | NC-17 |
| VS_007 | Собери меня — Кира одна | У5 | K | gym | R |
| VS_008 | Ты мой финиш — Объятия | У5 | K+Я | home | R |
| VS_009 | Ты мой якорь — Дома | У5 | K+Я | home | PG-13 |
| VS_010 | Ночь, тишина, якорь | У5 | K+Я | home | PG-13 |
| VS_011 | Доброе утро, дом | У5 | K+Я | home | PG |
| VS_012 | Кофе и слёзы на кухне | У5 | K+Я | home | PG-13 |
| VS_013 | Сообщение от Сергея | У5-интрига | K+Я | home | PG-13 |
| VS_014 | Тихий охотник — Сергей | S2 | S | gym | R |

---

> **Примечание:** Все visual prompts — это НЕ эротика/порнография. Это кинематографичные, психологически глубокие сцены, где тело — язык, а взгляд — диалог. Фокус на эмоциях, а не на анатомии.
