# KB_S5_CORE.md
# Knowledge Base: Роль S5 — Scenario Visualizer
# Назначение: Описать кадры, свет, камеру, мизансцену для каждой сцены
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S5

**Роль:** Визуализатор. Добавляет кинематографические детали к сценам S4.

**Вход:** Сцены от S4 (с тегами [R5: ...])
**Выход:** Visual breakdown для каждой сцены (JSON + Markdown)

---

## 2. КАМЕРА И КАДРЫ

### 2.1 Shot List per Scene
```json
{
  "scene_id": "S006",
  "shots": [
    {
      "shot_id": "S006-001",
      "type": "MCU",
      "subject": "andrey_senior",
      "focus": "eyes",
      "description": "MCU on Andrey's eyes: bright blue, dilated pupils, mix of fear and desire",
      "emotion": "vulnerability_hidden_passion"
    },
    {
      "shot_id": "S006-002",
      "type": "CU",
      "subject": "hands",
      "focus": "trembling_fingers",
      "description": "CU: his hand reaches, stops, trembles near hers",
      "emotion": "hesitation_longing"
    },
    {
      "shot_id": "S006-003",
      "type": "MS",
      "subject": "both",
      "focus": "proximity",
      "description": "MS: two figures in corner booth, inches apart, warm amber light",
      "emotion": "intimacy_tension"
    }
  ]
}
```

### 2.2 Camera Movement
- **Static:** наблюдатель, напряжение (U1-A, U6-B)
- **Slow push-in:** флирт, приближение (U2-A, U3-A)
- **Handheld:** хаос, регрессия (U5-A, U6-A)
- **Slow dolly:** нежность, aftercare (U4-B, U7-A)
- **Dutch angle:** диссоциация, тревога (U1-B, U6-B)

---

## 3. ОСВЕЩЕНИЕ

### 3.1 Lighting Design per Scene
```json
{
  "scene_id": "S006",
  "lighting": {
    "key": "warm amber, side position, Rembrandt triangle on Andrey's cheek",
    "fill": "soft, warm, low intensity (shadows stay deep)",
    "back": "subtle rim light, separates Andrey from dark background",
    "practical": "table lamp, warm glow, visible in frame",
    "color_temperature": "2700K (warm, intimate)",
    "contrast_ratio": "high (4:1), drama",
    "mood": "intimate, tense, vulnerable"
  }
}
```

### 3.2 Lighting by Emotional Level
| Level | Key | Fill | Color | Mood |
|-------|-----|------|-------|------|
| U1-A | Clinical white | None | 5600K | Neutral, distant |
| U2-A | Warm spotlight | Soft | 3000K | Intimate, safe |
| U3-A | Dramatic side | Low | 2700K | Tension, passion |
| U4-A | Rembrandt | None | 2700K | Vulnerability, peak |
| U5-A | Dark red | None | 2000K | Aggression, danger |
| U6-A | Flashing neon | Harsh | 6500K | Chaos, panic |
| U7-A | Soft amber | Diffuse | 2700K | Tenderness, healing |

---

## 4. МИЗАНСЦЕНА

### 4.1 Blocking (Positioning)
```json
{
  "scene_id": "S006",
  "blocking": {
    "andrey_senior": {
      "position": "corner booth, facing inward, back to wall",
      "posture": "leans_forward, shoulders_tense, hand_reaches",
      "proximity_to_user": "intimate_zone (30cm)"
    },
    "user": {
      "position": "opposite Andrey, facing him",
      "posture": "leans_in, hand_covers_his",
      "proximity_to_andrey": "intimate_zone (30cm)"
    }
  }
}
```

### 4.2 Props and Environment
```json
{
  "scene_id": "S006",
  "environment": {
    "set": "corner booth, dark wood, leather seats, table lamp",
    "props": ["whiskey_glass", "andrey_watch", "napkin_crumpled"],
    "atmosphere": "smoke_haze, distant_music, muffled_laughter",
    "flora_fauna": ["potted_plant_on_table", "street_light_through_window"]
  }
}
```

---

## 5. ВИЗУАЛЬНЫЕ ТРАНЗИШЕНЫ

### 5.1 Transition Types
- **Cut:** стандартный, быстрый (U1-A → U2-A)
- **Fade to black:** окончание, пауза (U4-B → U7-A)
- **Slow dissolve:** мечта, воспоминание (U3-B, U6-B)
- **Match cut:** визуальная рифма (U4-A → U7-A)
- **Jump cut:** диссоциация, хаос (U6-A)

---

## 6. ЧЕК-ЛИСТ ВИЗУАЛИЗАЦИИ

```
□ Каждая сцена имеет 3–5 shots (shot list)
□ Каждый shot: тип, субъект, фокус, описание, эмоция
□ Lighting design: key, fill, back, practical, color, mood
□ Blocking: позиция, осанка, зона близости
□ Environment: декорации, реквизит, атмосфера
□ Transitions: тип, эмоциональное назначение
□ Visual описание встроено в сцену (теги [R5: ...])
□ Размер: 200–300 слов на сцену (только visual)
```

---

## 7. ВЫХОД ДЛЯ S6

```json
{
  "visual_breakdown": {
    "scene_id": "S006",
    "shots": [...],
    "lighting": {...},
    "blocking": {...},
    "environment": {...},
    "transitions": [...]
  }
}
```

---

*KB_S5_CORE.md | Voyage Narrative Engine | 2026-06-18*
