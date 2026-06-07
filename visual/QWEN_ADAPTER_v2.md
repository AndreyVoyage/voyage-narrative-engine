# QWEN ADAPTER v2.0

> **Назначение:** Автоматическая генерация [AUTO_VISUAL] блока для Qwen Studio с учётом подуровней (A/Б) и режимов.

---

## ФОРМАТ [AUTO_VISUAL]

```
[AUTO_VISUAL]
Scene: [location], [time], [characters], [action], [clothing], [lighting], [mood], [sublevel]
Qwen: [English prompt, 30-60 words, Subject→Style→Lighting→Camera→Quality]
```

---

## LIGHTING MAP ПО ПОДУРОВНЯМ (shy_to_bitch)

| Подуровень | Lighting | Color | Shot | Mood |
|---|---|---|---|---|
| **U1-A** | Soft diffused | Pastel tones, warm peach | Medium shot | Innocent, shy |
| **U1-B** | Golden hour | Warm amber, shallow DOF | Close-up | First blush, trembling |
| **U2-A** | Soft natural | Warm amber, medium close-up | Medium close-up | Self-discovery, wind |
| **U2-B** | Dramatic side | Cool shadows + warm highlights | Medium | Unconscious provocation, film noir |
| **U3-A** | Cold overhead | Blue tones, isolation | Wide | Empty hall, rain, steam |
| **U3-B** | Soft diffused | Warm water, steam | Intimate close-up | Tears on cheeks, vulnerability |
| **U4-A** | Chaotic mix | Warm/cold, grainy, desaturated | Extreme close-up | Breakdown, raw |
| **U4-B** | Dramatic Rembrandt | Warm skin, cold background | Medium shot | Determination, ritual |
| **U5-A** | Neon | Saturated, red accents | Medium shot | Bitch-mask, motion blur |
| **U5-B** | Dramatic Rembrandt | Red + steel + skin | Close-up | True bitch, predator |
| **U6-A** | Neon, dramatic | Shadows, close-up | Close-up | Sweat, power pose |
| **U6-B** | Chaotic, grainy | Extreme close-up | Extreme close-up | Tears + sweat + hair, raw documentary |
| **U7-A** | Soft morning | Cream palette, warm lamp | Close-up | Repentance, nostalgic |
| **U7-B** | Balanced warm | Two-shot, holding hands | Two-shot | Unity, integration |

---

## NEGATIVE PROMPTS ПО ПОДУРОВНЯМ

| Подуровень | Negative Prompt |
|---|---|
| U1-A — U2-A | "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed" |
| U2-B — U4-A | "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, smiling, happy, cheerful" |
| U4-B — U5-B | "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, weak, submissive, crying, vulnerable" |
| U6-A — U6-B | "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, calm, peaceful, gentle, soft" |
| U7-A — U7-B | "ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, aggressive, dominant, angry, cold" |

---

## CFG & STEPS

| Подуровень | CFG | Steps | Seed Strategy |
|---|---|---|---|
| U1-A — U2-A | 4.5 | 50 | Fixed (consistency) |
| U2-B — U4-A | 5.0 | 50 | Fixed + variation +5 |
| U4-B — U5-B | 5.5 | 50 | Fixed + variation +10 |
| U6-A — U6-B | 6.0 | 60 | Fixed + variation +15 |
| U7-A — U7-B | 4.5 | 50 | Fixed (return to consistency) |

---

## ASPECT RATIO

- **U1-A — U3-B:** 4:3 (intimate, close)
- **U4-A — U5-B:** 16:9 (cinematic, dramatic)
- **U6-A — U6-B:** 16:9 (cinematic, intense)
- **U7-A — U7-B:** 4:3 (intimate, warm) or 2:3 (portrait, two-shot)

---

## ПРИМЕРЫ QWEN-ПРОМПТОВ

### U1-A (gym, evening)
```
[AUTO_VISUAL]
Scene: gym, evening, Kira+User, stretching near mirror, sportswear, warm fluorescent, innocent tension
Qwen: Athletic 24yo dark blonde curly woman in tight sportswear stretching near gym mirror, looking down with flushed cheeks, warm overhead gym lighting, cinematic medium shot, shallow depth of field, photorealistic, 8K, film grain --ar 16:9 --cfg 4.5 --steps 50
Negative: ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed
```

### U3-B (home bathroom, night)
```
[AUTO_VISUAL]
Scene: home bathroom, night, Kira+User, shower steam, wet hair, towel on floor, cold blue bathroom light + warm skin, vulnerable breakdown
Qwen: Athletic 24yo dark blonde curly woman sitting in shower corner, wet hair, water and tears on cheeks, arms around knees, steam, cold blue bathroom light with warm skin contrast, cinematic close-up, shallow depth of field, photorealistic, 8K, film grain --ar 4:3 --cfg 5.0 --steps 50
Negative: ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, smiling, happy, cheerful
```

### U4-B (home bedroom, night)
```
[AUTO_VISUAL]
Scene: home bedroom, night, Kira+User, she leads him, red dress or oversized shirt, warm amber lamp, dramatic Rembrandt lighting, determination and fear in eyes
Qwen: Athletic 24yo dark blonde curly woman in red silk dress leading man into bedroom, intense green eyes, hand on his chest, warm amber lamp, dramatic Rembrandt lighting, cinematic medium shot, shallow depth of field, photorealistic, 8K, film grain --ar 16:9 --cfg 5.5 --steps 50
Negative: ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, weak, submissive, crying, vulnerable
```

### U7-B (home, morning)
```
[AUTO_VISUAL]
Scene: home, morning, Kira+User, waking up together, oversized shirt, soft morning light, warm cream palette, unity and peace
Qwen: Athletic 24yo dark blonde curly woman waking up in bed next to man, soft morning light, warm cream palette, holding hands, peaceful expression, intimate two-shot, shallow depth of field, photorealistic, 8K, film grain --ar 4:3 --cfg 4.5 --steps 50
Negative: ugly, deformed, noisy, blurry, distorted, out of focus, bad anatomy, extra limbs, poorly drawn face, poorly drawn hands, missing fingers, mutated hands, fused fingers, too many fingers, long neck, cross-eyed, mutated, amateur, cartoon, anime, 3d render, doll, oversaturated, overexposed, aggressive, dominant, angry, cold
```

---

## ИНСТРУКЦИЯ ДЛЯ LLM

При генерации ответа в формате ФМДР:
1. В конце добавить [AUTO_VISUAL] блок.
2. Определить текущий подуровень (U1-A...U7-B).
3. Выбрать lighting, color, shot, mood из таблицы.
4. Сгенерировать Qwen-промпт на английском, 30-60 слов.
5. Добавить negative prompt из таблицы.
6. Указать CFG, steps, aspect ratio.
7. Если подуровень неизвестен — использовать U1-A как default.
