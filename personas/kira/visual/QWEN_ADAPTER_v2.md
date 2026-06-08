# QWEN ADAPTER v2.0 — Lighting Map, Anatomic Anchors, Visual Prompts

> **Версия:** 2.0.0  
> **Совместимость:** persona_schema_v3.2, visual_data.anatomic_anchor, VOYAGE_NARRATIVE_CORE_v2.0  
> **Назначение:** Генерация консистентных визуальных промптов для Qwen Studio / Stable Diffusion / Midjourney

---

## 1. Архитектура промпта (формула)

Промпт собирается по строгой формуле:

```
[ANATOMIC_ANCHOR.visual_signature] + [SCENE_DESCRIPTION] + [LIGHTING] + [MOOD] + [CAMERA] + [STYLE] + [NEGATIVE]
```

**Правила сборки:**
1. `visual_signature` всегда идёт первым — это фиксирует лицо и телосложение.
2. `SCENE_DESCRIPTION` — из `visual_data.prompt_variations` или `dynamic_visuals` текущего подуровня.
3. `LIGHTING` — из Lighting Map по текущему подуровню.
4. `MOOD` — из `speech_profile` текущего подуровня (tone + action_detail).
5. `CAMERA` — из Camera Map по подуровню.
6. `STYLE` — `visual_data.style` + `cfg` + `steps`.
7. `NEGATIVE` — из Negative Prompts Map по фазе подуровня + `visual_data.anti_prompts`.

---

## 2. Lighting Map по подуровням (Кира, Марина)

| Подуровень | Lighting | Color palette | Shot | Mood | Camera |
|------------|----------|---------------|------|------|--------|
| U1-A | Soft diffused | Pastel, warm peach | Medium | Innocent, shy | Eye-level, slight low angle |
| U1-Б | Golden hour | Warm amber, shallow DOF | Close-up | First blush | Slight high angle |
| U2-A | Soft natural | Warm amber | Medium close-up | Self-discovery | Eye-level |
| U2-Б | Dramatic side | Cool shadows + warm highlights | Medium | Unconscious provocation | Slight low angle, side |
| U3-A | Cold overhead | Blue, isolation | Wide | Conflict, rain | High angle, distant |
| U3-Б | Soft diffused | Warm water, steam | Intimate close-up | Tears, vulnerability | Close-up, eye-level |
| U4-A | Chaotic mix | Warm/cold, grainy | Extreme close-up | Breakdown, raw | Handheld, shaky |
| U4-Б | Dramatic Rembrandt | Warm skin, cold bg | Medium | Determination, ritual | Low angle, stable |
| U5-A | Neon | Saturated, red accents | Medium | Bitch-mask | Dutch angle |
| U5-Б | Dramatic Rembrandt | Red + steel + skin | Close-up | True bitch, predator | Eye-level, piercing |
| U6-A | Neon, dramatic | Shadows, close-up | Close-up | Sweat, power | Low angle, upward |
| U6-Б | Chaotic, grainy | Extreme close-up | Extreme close-up | Tears + sweat, raw | Handheld, intimate |
| U7-A | Soft morning | Cream, warm lamp | Close-up | Repentance, nostalgic | High angle, protective |
| U7-Б | Balanced warm | Two-shot, holding hands | Two-shot | Unity, integration | Eye-level, balanced |

---

## 3. Lighting Map (Сергей, Максим)

| Уровень | Lighting | Color palette | Shot | Mood |
|---------|----------|---------------|------|------|
| S1 / M1 | Cool neutral | Grey, blue undertones | Medium | Observer, calm | Eye-level |
| S2 / M2 | Warm spot | Amber, shallow DOF | Medium close-up | Initiation, warmth | Slight low angle |
| S3 / M3 | Warm indoor | Soft yellow, wood | Medium | Ally, comfort | Eye-level |
| S4 | Dramatic shadow | Deep shadows, cold bg | Medium | Competitor, tension | Low angle |
| S5 | Cold blue | Steel, isolation | Wide | Withdrawal, distance | High angle, distant |
| S6 | Flat fluorescent | Harsh white, no shadows | Close-up | Mask failure, awkward | Eye-level |
| S7 | Cold blue | Monochrome, night | Wide | Guardian restored, closed | High angle, back turned |
| M4 | Soft golden | Warm lamp, intimate | Close-up | Gentle initiator | Eye-level, soft |
| M5 | Candle warm | Firelight, orange | Two-shot | Devoted companion | Close-up, warm |

---

## 4. Negative Prompts Map по фазам

| Фаза подуровней | Дополнительные anti-prompts | Почему |
|----------------|----------------------------|--------|
| U1-A – U2-A | `ugly, deformed, blurry, bad anatomy, extra limbs, text, watermark, anime, cartoon` | Базовый набор |
| U2-Б – U4-A | + `smiling, happy, cheerful, soft lighting, innocent gaze` | На этих уровнях персонаж НЕ счастлив — конфликт, стыд, срыв |
| U4-Б – U5-Б | + `weak, submissive, crying, vulnerable, soft lighting, gentle` | Своеволие и стерва — сила, не слабость |
| U6-A – U6-Б | + `calm, peaceful, gentle, soft, innocent, romantic` | Доминирование и перегрузка — агрессия, не романтика |
| U7-A – U7-Б | + `aggressive, dominant, angry, cold, intense, neon` | Раскаяние и интеграция — мягкость, не агрессия |

---

## 5. CFG & Steps

| Диапазон подуровней | CFG | Steps | Aspect Ratio |
|---------------------|-----|-------|--------------|
| U1-A – U2-A | 4.5 | 50 | 4:3 |
| U2-Б – U4-A | 5.0 | 50 | 4:3 |
| U4-Б – U5-Б | 5.5 | 50 | 16:9 |
| U6-A – U6-Б | 6.0 | 60 | 16:9 |
| U7-A – U7-Б | 4.5 | 50 | 4:3 или 2:3 |

---

## 6. Групповые сцены (2+ персонажа)

### Композиция
- **Центральный персонаж** — на переднем плане, в фокусе.
- **Остальные** — в боке, отражении (зеркала/вода), или размытые (DOF).
- **Правило третей** — центральный персонаж на пересечении линий.

### Освещение
- **Парная (сауна):** тёплый туман с холодными тенями, steam diffusion.
- **Комната отдыха:** мягкие лампы + свечи, warm amber.
- **Улица:** закатный боке, контровой свет.

### Negative prompt для групп
```
distorted hands, overlapping limbs, merged bodies, extra limbs, 
conjoined faces, anatomically incorrect, bad proportions, 
cloned faces, identical expressions
```

---

## 7. Пример сборки промпта (Кира, U2-Б, сауна)

### Исходные данные из модуля
- `anatomic_anchor.visual_signature`: `oval face, almond brown eyes with amber, straight nose, full lower lip, defined jaw, dark blonde waves, athletic slender build, red dress signature`
- `prompt_variations.sauna`: `Young woman in sauna, hair slightly damp messy natural, wrapped in white towel, flushed cheeks from heat, relaxed confident expression, steam, warm amber lighting, wooden interior, photorealistic, intimate atmosphere`
- `lighting_map_ref`: `U2-Б:dramatic_side`
- `anti_prompts`: `["anime", "cartoon", ...]` + фазовые дополнения

### Собранный промпт
```
Oval face with almond brown eyes with amber undertones, straight nose, full lower lip, defined jaw, dark blonde natural waves, athletic slender build. Young woman in sauna, hair slightly damp messy natural, wrapped in white towel, flushed cheeks from heat, relaxed confident expression, steam, warm amber lighting with cool shadows on one side, wooden interior, dramatic side lighting, medium shot, photorealistic, 8k, intimate atmosphere. --ar 4:3 --cfg 5.0 --steps 50

Negative: anime, cartoon, 3d render, distorted anatomy, extra limbs, bad hands, text, watermark, smiling, happy, cheerful, soft lighting, innocent gaze
```

---

## 8. Интеграция с модулями

| Поле модуля | Назначение | Где используется |
|-------------|-----------|------------------|
| `visual_data.anatomic_anchor.visual_signature` | Начало промпта | QWEN_ADAPTER — фиксация лица |
| `visual_data.prompt_base` | Базовый промпт | QWEN_ADAPTER — если нет вариации |
| `visual_data.prompt_variations.[scene]` | Сценарная вариация | QWEN_ADAPTER — замена prompt_base |
| `visual_data.lighting_map_ref` | Ссылка на Lighting Map | QWEN_ADAPTER — освещение |
| `visual_data.anti_prompts` | Базовые negative | QWEN_ADAPTER + фазовые дополнения |
| `visual_data.aspect_ratio` | Пропорции | QWEN_ADAPTER — `--ar` |
| `visual_data.cfg` / `steps` | Технические | QWEN_ADAPTER — `--cfg` / `--steps` |
| `dynamic_visuals.[level]` | Описание внешности | QWEN_ADAPTER — детали одежды/позы |

---

## 9. Консистентность между сессиями

**Проблема:** AI-генераторы (Qwen, SD) не запоминают лица между сессиями.

**Решения:**
1. **Фиксированный seed** — `visual_data.seed` (42 для Киры, 43 для Сергея, 44 для Максима, 45 для Марины).
2. **Anatomic anchor** — детальное описание лица в начале каждого промпта.
3. **Visual signature** — компактная строка, которая НЕ меняется между сессиями.
4. **Style lock** — `photorealistic`, `8k`, `cinematic` — одинаковые стилистические токены.
5. **Для Midjourney:** `--cref [URL]` (Character Reference) + `--cw 0` (только лицо).
6. **Для SD:** IP-Adapter + ControlNet с фиксированным reference image.
7. **Для Qwen:** Seed + идентичный prompt_base + signature_features.

---

## 10. Версионирование

- `QWEN_ADAPTER_v2.md` — версионируется по semver.
- `v2.0.0` — добавлен `anatomic_anchor` и `visual_signature`.
- Изменения Lighting Map или Negative Prompts требуют обновления всех модулей.
