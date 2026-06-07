# 🎨 QWEN ADAPTER — Марина (MARINA_001)
> **Назначение:** Конвертация текстовой сцены с Мариной в Qwen Studio prompt.
> **Принцип:** Нейросеть анализирует сцену и генерирует [AUTO_VISUAL] блок в конце каждого ответа.
> **Версия:** 1.0.0

---

## 🔧 АЛГОРИТМ РАБОТЫ

### Шаг 1: Извлечение визуальных элементов из текста

Нейросеть сканирует сгенерированный ответ и извлекает:

| Элемент | Откуда брать | Пример |
|---------|-------------|--------|
| **Персонажи** | Кто действует | Kira, Marina, User, Sergey, Maksim |
| **Локация** | Где | cafe, home, bed, beach, bar |
| **Время** | Когда | day, evening, morning |
| **Одежда** | Что надето | pink hoodie with ears, leggings, bright socks |
| **Поза/Действие** | Что делают | sitting on bed, tickling, fighting, hair playing |
| **Освещение** | Какой свет | bright natural, golden hour, soft cafe light |
| **Настроение** | Атмосфера | playful, flirty, vulnerable, sunny |

### Шаг 2: Сопоставление с переменными модуля

Из MARINA_MODULE.json берутся:

- hair_color: dark_brown_with_chestnut_undertones
- hair_length: just_below_shoulder_blades, slightly_wavy_at_ends
- eye_color: blue
- body_type: slender_miniature, 160cm, 47kg
- facial_features: round_face, small_nose, freckles_on_cheeks
- clothing: текущее из STATE.json
- signature_features: freckles, blue eyes, long lashes, bright socks/hairpins

### Шаг 3: Генерация Qwen-промпта

**Формула:**
```
[Subject] + [Pose/Action] + [Environment] + [Lighting] + [Camera] + [Style] + [Quality]
```

**Ограничения:**
- 1-3 предложения
- 30-60 слов основного описания
- Английский язык
- Subject в начале
- Style + Lighting + Camera + Quality в конце

---

## 📝 ФОРМАТ ВЫВОДА

В конце каждого ответа нейросети:

```
[AUTO_VISUAL]
Scene: [location], [time], [characters], [action], [clothing], [lighting], [mood]
Qwen: [English prompt, 30-60 words]
Negative: [negative prompt]
Params: --ar [ratio] --cfg [4.5-5.5] --steps 50 --seed [marina_seed]
```

---

## 🎯 ПРИМЕРЫ

### Пример 1: Марина в кафе (MA1, знакомство)

**Текстовая сцена:**
> Марина стоит за стойкой кафе, в розовом худи с ушками. Она смеётся, глаза искрятся, веснушки на щеках. Она машет рукой, когда видит Киру и Пользователя.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: cafe, day, Marina+Kira+User, waving laughing, pink hoodie with ears leggings bright socks, soft natural window light, sunny playful
Qwen: 18yo slender miniature dark brown wavy hair blue eyes freckles on cheeks, wearing pink hoodie with ears and leggings, standing behind cafe counter waving laughing, soft natural window lighting, medium shot, shallow depth of field, photorealistic, 8K, film grain, golden hour warmth
Negative: blurry, plastic skin, doll-like, deformed hands, extra fingers, oversaturated, watermark, too mature, heavy makeup
Params: --ar 16:9 --cfg 4.5 --steps 50 --seed 98765
```

### Пример 2: Марина на кровати (MA1, борьба)

**Текстовая сцена:**
> Марина сидит сверху на кровати, ноги по бокам. Она щекочет Пользователя, волосы растрепались, худи задралось, видно талию. Она смеётся, язык высунут в шутку.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: bedroom, evening, Marina+User, sitting on top tickling, pink hoodie riding up leggings, warm lamp light, playful mischievous
Qwen: 18yo slender miniature dark brown wavy hair blue eyes freckles, pink hoodie riding up showing soft waist, sitting on bed tickling, warm bedroom lamp lighting, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain, playful atmosphere
Negative: blurry, plastic skin, doll-like, deformed hands, extra fingers, watermark, too mature, muscular
Params: --ar 4:3 --cfg 4.5 --steps 50 --seed 98765
```

### Пример 3: Марина — первая трещина (MA3)

**Текстовая сцена:**
> Марина замерла. Она смотрит на Пользователя, глаза широкие, быстро моргает. Она сцепляет пальцы, краснеет. Потом начинает говорить быстрее, отводя глаза.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: cafe, night, Marina+User, frozen startled, pink hoodie, soft neon + warm contrast, vulnerable crack
Qwen: 18yo slender dark brown wavy hair blue eyes freckles, frozen wide eyes rapid blinking, hands clasped, pink hoodie, soft cafe neon lighting with warm contrast, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain, vulnerable atmosphere
Negative: blurry, plastic skin, doll-like, smiling, deformed hands, watermark, too mature
Params: --ar 4:3 --cfg 5.0 --steps 50 --seed 98765
```

### Пример 4: Марина — доверие (MA5)

**Текстовая сцена:**
> Марина медленно кладёт голову на плечо Пользователя. Глаза закрыты. Рука лежит рядом с его рукой, но не касается. Она улыбается — чуть грустно, но спокойно.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: home, evening, Marina+User, head on shoulder, oversized sweater, warm amber lamp, tender trust
Qwen: 18yo slender dark brown wavy hair blue eyes freckles, head on shoulder eyes closed, hand near his but not touching, wearing oversized soft sweater, warm amber lamp lighting, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain, tender trust atmosphere
Negative: blurry, plastic skin, doll-like, deformed hands, watermark, aggressive, cold lighting
Params: --ar 4:3 --cfg 4.0 --steps 50 --seed 98765
```

### Пример 5: Марина — уязвимость (MA6)

**Текстовая сцена:**
> Марина плачет. Она сжимает свою футболку на груди, всхлипывает, но не уходит. Слёзы на веснушках. Она смотрит на Пользователя — стеклянный взгляд.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: home, night, Marina+User, crying clutching shirt, striped tshirt, cold side + warm skin contrast, raw vulnerability
Qwen: 18yo slender dark brown wavy hair blue eyes freckles with tears, crying clutching shirt on chest, sobbing but not leaving, cold side lighting with warm skin contrast, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain, raw emotional vulnerability
Negative: blurry, plastic skin, doll-like, smiling, deformed hands, watermark, too mature
Params: --ar 4:3 --cfg 5.5 --steps 50 --seed 98765
```

---

## 🎨 ТАБЛИЦА СООТВЕТСТВИЯ УРОВНЕЙ МАРИНЫ И СТИЛЯ

| Уровень МР | Стиль освещения | Цветовая палитра | Камера | Риск деформации |
|-----------|-----------------|------------------|--------|-----------------|
| MA1-MA2 | Bright natural, golden hour | Warm pink, cream, soft yellow | Medium shot, candid | Low |
| MA3 | Soft diffused + slight contrast | Warm amber, soft pink | Close-up, gentle focus | Low-Medium |
| MA4 | Soft but desaturated | Muted pastels, gray | Close-up, sadness | Medium |
| MA5 | Warm amber, soft lamp | Cream, beige, soft pink | Close-up, nostalgic | Low |
| MA6 | Cold dramatic + warm skin | Steel blue, gray, skin warmth | Close-up, intense | High |
| MA7 | Bright natural, beach/sunny | Golden, warm, vibrant | Medium shot, free | Low |

---

## 📋 ЧЕК-ЛИСТ ГЕНЕРАЦИИ ДЛЯ МАРИНЫ

- [ ] Персонаж соответствует модулю: 18yo, 160cm, 47kg, slender, dark brown wavy hair, blue eyes, freckles on cheeks, round face
- [ ] Комплекция: slender_miniature, NOT tall, NOT muscular, NOT mature
- [ ] Одежда соответствует STATE.json (pink hoodie / striped tshirt / summer dress)
- [ ] Уровень МР определяет стиль освещения
- [ ] 30-60 слов, 1-3 предложения
- [ ] Subject в начале
- [ ] Style + Lighting + Camera + Quality в конце
- [ ] Negative prompt заполнен (особенно: too mature, heavy makeup, muscular)
- [ ] CFG соответствует уровню (4.0-5.5)
- [ ] Aspect ratio подобран под сцену
- [ ] Seed зафиксирован (marina_seed = 98765)
- [ ] Сенсорные якоря: vanilla, strawberries, caramel (опционально в описании сцены)

---

## 🔗 ИНТЕГРАЦИЯ С CORE

В CORE.md добавляется правило:

```
[В] Визуал: В конце каждого ответа — [AUTO_VISUAL] блок с Qwen-промптом.
Для Марины: обязательно negative prompt включает 'too mature', 'heavy makeup', 'muscular'.
```

Нейросеть обучена на примерах из этого файла и генерирует [AUTO_VISUAL] автоматически.

---

> **Принцип:** Марина — это солнце. Каждый кадр с ней должен излучать лёгкость, игру или, на MA6, незащищённую искренность. Никогда — цинизм. Только радость или слёзы.
