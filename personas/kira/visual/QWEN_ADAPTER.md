# 🎨 QWEN ADAPTER — Автоматический визуальный мост

> **Назначение:** Конвертация текстовой сцены в Qwen Studio prompt за 1 шаг.
> **Принцип:** Нейросеть анализирует сцену и генерирует [AUTO_VISUAL] блок в конце каждого ответа.

---

## 🔧 АЛГОРИТМ РАБОТЫ

### Шаг 1: Извлечение визуальных элементов из текста

Нейросеть сканирует сгенерированный ответ и извлекает:

| Элемент | Откуда брать | Пример |
|---------|-------------|--------|
| **Персонажи** | Кто действует | Kira, Sergey, User |
| **Локация** | Где | gym, bar, hotel room |
| **Время** | Когда | night, morning, evening |
| **Одежда** | Что надето | red dress, open shirt, sportswear |
| **Поза/Действие** | Что делают | lying on mat, standing close, sitting on bar |
| **Освещение** | Какой свет | cold fluorescent, warm neon, golden hour |
| **Настроение** | Атмосфера | tension, aftercare, seduction, dominance |

### Шаг 2: Сопоставление с переменными модуля

Из KIRA_MODULE.json и SERGEY_MODULE.json берутся:
- hair_color, hair_length, hair_texture
- eye_color
- body_type
- clothing (текущее из STATE.json)
- signature_features

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
Params: --ar [ratio] --cfg [4.5-5.5] --steps 50
```

---

## 🎯 ПРИМЕРЫ

### Пример 1: Кира в баре (У5)

**Текстовая сцена:**
> Кира стоит у барной стойки в красном платье без белья. Сергей сидит рядом, рубашка нараспашку. Тёплый неон. Она смотрит на него через плечо.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: bar, night, Kira+Sergey, flirting at counter, red evening gown no underwear + open linen shirt, warm neon and amber light, seductive tension
Qwen: Athletic 24yo light blonde curly woman in tight red evening gown no underwear, sitting at bar counter, 27yo athletic man in open linen shirt leaning close, warm neon lighting, cinematic medium shot, shallow depth of field, photorealistic, 8K, film grain
Negative: blurry, plastic skin, doll-like, deformed hands, extra fingers, oversaturated, watermark
Params: --ar 16:9 --cfg 4.5 --steps 50
```

### Пример 2: Кира в зале (У4-пик)

**Текстовая сцена:**
> Кира лежит на красном мате. Сергей на коленях между её ног. Его руки под её топом. Она плачет и смеётся одновременно.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: gym, night, Kira+Sergey, intimate on red mat, crop top pushed up + grey tank top, cold overhead + warm skin contrast, dramatic tension peak
Qwen: Athletic 24yo light blonde curly woman in black crop top pushed up lying on red leather gym mat, 27yo athletic man kneeling between her legs hands under top, dramatic Rembrandt lighting, cold and warm contrast, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain
Negative: blurry, deformed hands, extra fingers, plastic skin, doll-like, watermark, bad anatomy
Params: --ar 4:3 --cfg 5.5 --steps 50
```

### Пример 3: Aftercare дома (У7)

**Текстовая сцена:**
> Кира лежит на груди Я в серой рубашке. Волосы мокрые. Она плачет тихо. Тёплая лампа на тумбочке.

**[AUTO_VISUAL]:**
```
[AUTO_VISUAL]
Scene: bedroom, night, Kira+User, lying on chest embracing, oversized grey shirt, warm amber lamp light, intimate tender aftercare
Qwen: Athletic 24yo light blonde curly woman in oversized grey shirt lying on man's chest in bed, wet hair, tears on cheeks, warm amber lamp light on nightstand, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain, warm color palette
Negative: blurry, plastic skin, doll-like, deformed hands, extra fingers, watermark, cold lighting
Params: --ar 4:3 --cfg 4.0 --steps 50
```

---

## 🎨 ТАБЛИЦА СООТВЕТСТВИЯ УРОВНЕЙ И СТИЛЯ

| Уровень К | Стиль освещения | Цветовая палитра | Камера | Риск деформации |
|-----------|----------------|------------------|--------|-----------------|
| У1-У2 | Soft natural, golden hour | Warm, peach, amber | Medium close-up, shallow DOF | Low |
| У3-У4 | Dramatic side, strong shadows | Cool shadows + warm highlights | High contrast, film noir | Medium |
| У4-пик | Chaotic mix warm/cold | Grainy, desaturated except skin | Extreme close-up, raw | High |
| У5-У6 | Neon, bar/club lights | Saturated, red accents | Medium shot, motion blur | Medium |
| У6-пик | Dramatic Rembrandt | Red + steel + skin | Close-up, intense | High |
| У7 | Soft diffused morning | Cream, beige, soft pink | Close-up, nostalgic | Low |

---

## 📋 ЧЕК-ЛИСТ ГЕНЕРАЦИИ

- [ ] Персонажи соответствуют модулям (волосы, глаза, тело)
- [ ] Одежда соответствует STATE.json (underwear: true/false)
- [ ] Уровень К определяет стиль освещения
- [ ] 30-60 слов, 1-3 предложения
- [ ] Subject в начале
- [ ] Style + Lighting + Camera + Quality в конце
- [ ] Negative prompt заполнен
- [ ] CFG соответствует уровню (4.0-5.5)
- [ ] Aspect ratio подобран под сцену
- [ ] Seed зафиксирован для серии

---

## 🔗 ИНТЕГРАЦИЯ С CORE

В CORE.md добавляется правило:
```
[В] Визуал: В конце каждого ответа — [AUTO_VISUAL] блок с Qwen-промптом.
```

Нейросеть обучена на примерах из этого файла и генерирует [AUTO_VISUAL] автоматически.

---

> **Принцип:** Каждая сцена — это кадр. Каждый кадр — это Qwen-промпт. Текст и визуал идут рука об руку.
