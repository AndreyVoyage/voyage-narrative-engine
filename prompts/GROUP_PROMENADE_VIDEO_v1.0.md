# ВИДЕО-ПРОМПТ: Андрей, Кира, Марина — набережная, 5 секунд

> **Для:** Runway Gen-3, Kling AI, Pika Labs, Luma Dream Machine, Sora, Stable Video Diffusion  
> **Длительность:** 5 секунд (~125 frames @ 25fps)  
> **Ракурс:** Фронтальный, лёгкий поворот влево, slow tracking shot  
> **Стиль:** Cinematic, photorealistic, slow motion feel, graceful movement

---

## СТРАТЕГИЯ ГЕНЕРАЦИИ

Для видео с тремя персонажами рекомендуется **двухэтапный подход**:

1. **Сначала** сгенерировать статичное reference-изображение через DALL-E 3 / Midjourney по промпту `GROUP_PROMENADE_v1.0.md`.
2. **Затем** использовать это изображение как `first frame` / `image prompt` в видео-модели + motion prompt из этого файла.

Это даст максимальную консистентность лиц, пропорций и одежды.

---

## ОПИСАНИЕ ДВИЖЕНИЯ (MOTION PROMPT)

### Главное движение сцены

Slow graceful forward walking along waterfront promenade at golden hour. Three people holding hands walking gently toward camera in slight slow motion. Subtle cinematic camera tracking — very slow push-in combined with micro-drift to the left. Gentle breeze moving hair and dress fabric. Water ripples shimmering with sunset reflections in background. Distant city lights begin to twinkle. Bokeh background softly breathing. Romantic peaceful atmosphere.

---

## ПОКАДРОВОЕ РАСПРЕДЕЛЕНИЕ ДВИЖЕНИЯ (5 секунд)

### 0.0–1.0 сек (Frame 0–25): Вхождение в движение

- **Camera:** Static wide establishing shot, very subtle forward drift beginning.
- **Андрей:** Takes first slow step forward, weight shifts from back foot to front. Head remains steady, looking forward. Arms relaxed, hands gently holding women's hands. Shoulders sway naturally with step.
- **Кира:** Steps in sync, right hand swaying slightly in Andrey's grip. Head already turned toward camera with playful smile. Dark blonde hair begins to move with evening breeze — first strands lift.
- **Марина:** Steps in sync, left hand in Andrey's hand. Head tilted up toward him, eyes following his face. Light brown hair flows gently over shoulder. White dress fabric begins to catch wind.
- **Окружение:** First water ripples visible. Background lights steady. Golden light constant.

### 1.0–2.5 сек (Frame 25–62): Основное движение

- **Camera:** Slowest tracking push-in — camera moves forward slightly slower than subjects, creating subtle parallax. Micro-drift 2 degrees left.
- **Андрей:** Continuous slow walking, weight shifting rhythmically. Blue shirt sleeves rolled up showing forearms moving naturally. Muscular shoulders roll with gait. Light stubble catches golden light as head turns microscopically. Expression remains warm confident, eyes focused forward.
- **Кира:** Walking with confident hip sway, playful smile widening slightly. Dark blonde waves shoulder-length flowing with breeze — hair moves independently, strands crossing face momentarily. Red dress fabric ripples and flows with wind, hem lifting slightly. Eyes sparkle, head tilted, looking directly at viewer with mischief.
- **Марина:** Walking gracefully, delicate frame swaying gently. White dress flowing elegantly, fabric billowing softly around legs. Light brown hair waves moving with breeze and motion. Looking up at Andrey with adoring gaze — eyes follow his face as he walks. Smile softens, genuine warmth. Leans slightly into his arm.
- **Окружение:** Water reflections shimmer and animate continuously. Background bokeh lights show subtle flicker as evening transitions. Sunset light shifts microscopically warmer.

### 2.5–4.0 сек (Frame 62–100): Пик движения

- **Camera:** Same slow tracking, maintaining perfect framing. Slight depth-of-field breathing — background bokeh pulses subtly.
- **Андрей:** Walking rhythm steady. Muscular neck and shoulders clearly visible with each step. One hand gently squeezes Kira's hand, other hand holding Marina's — grip visible but gentle. Shirt fabric moves with body, collar shifts slightly. Breath subtle — chest rises and falls naturally.
- **Кира:** Hair in full motion — strands flowing freely, some tucking behind ear naturally. Red dress at peak movement — fabric wraps around legs then releases with breeze. Smile becomes more expressive, eyes narrowing playfully. Free hand (left) swings naturally with walk. Shoulder dips slightly with step.
- **Марина:** White dress at fullest flow — fabric billowing behind, creating elegant silhouette. Hair flowing backward with forward motion and breeze combined. Eyes remain locked on Andrey, following his face with devotion. Smile glows with happiness. One hand holds Andrey, other hand (right) swings gently at side.
- **Окружение:** Water ripples most visible. A bird or distant boat may pass in background (optional, subtle). Breeze visible through moving tree branches or flags if present.

### 4.0–5.0 сек (Frame 100–125): Выход / завершение

- **Camera:** Movement slows to nearly imperceptible drift. Final frame holds composition stable for loop potential.
- **Андрей:** Steps slowing to near-stop, weight settling. Final pose: walking but almost pausing, as if noticing something beautiful ahead. Warm smile remains.
- **Кира:** Hair settling into final flowing position. Red dress fabric falling back into elegant drape. Playful expression holds — eyes still at camera. Hand still in Andrey's.
- **Марина:** White dress settling, hair flowing to rest. Loving gaze still on Andrey. Final gentle squeeze of his hand visible.
- **Окружение:** Water calms slightly. Golden light holds. Final frame is perfect still-like composition with subtle residual motion — ideal for seamless loop or freeze-frame.

---

## ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ ВИДЕО

### Runway Gen-3 Alpha
```
Mode: Image to Video (recommended)
Duration: 5 seconds / 10 seconds (if available)
Camera Motion: Push In + Micro Pan Left
Motion Brush: Use on hair, dress fabric, water reflections
General Motion: 3-4 (moderate, not too fast)
```

### Kling AI (快手可灵)
```
Mode: Image to Video / Text to Video
Duration: 5s
Motion Strength: 3-5 (medium)
Camera: Forward movement + slight left pan
CFG: 0.5-0.7
```

### Pika Labs 1.5
```
Mode: Image prompt + text motion prompt
Duration: 5s
Motion: 2-3 (gentle)
Camera: Zoom in slow + pan left subtle
Negative: morphing, jittery, distorted faces, extra limbs
```

### Luma Dream Machine
```
Mode: Image to Video (strongly recommended)
Duration: 5s
Motion: Walking forward, gentle breeze, camera push-in
Key: Use high-quality reference image
```

### Sora (OpenAI, если доступен)
```
Style: photorealistic cinematic footage, 24fps, shallow depth of field
Duration: 5 seconds
Camera: Slow tracking shot forward with slight left drift
```

---

## ANTI-PROMPTS ДЛЯ ВИДЕО (КРИТИЧНО)

Video-specific negative prompts:

- morphing faces, morphing body parts, shape-shifting
- jittery motion, stuttering, flickering, frame skipping
- sudden movement changes, teleportation, jump cuts
- distorted anatomy during motion, bending limbs, rubber arms
- extra limbs appearing during walk, hands merging, fused fingers
- faces melting, eyes drifting, mouth sliding off face
- clothing color changing mid-video, dress becoming different color
- background shifting unrealistically, buildings morphing
- water freezing suddenly, reflections breaking logic
- camera shake, unstable footage, handheld look (unless specified)
- fast motion, running, sudden stops, jerky walking
- loop artifacts, seamless loop fail (if looping intended)
- low frame rate, choppy motion, blurry faces during movement
- wrong person heights changing mid-video, Andrey shrinking, Marina growing

---

## ПРОВЕРКА КОНСИСТЕНТНОСТИ ВИДЕО (ЧЕКЛИСТ)

- [ ] Faces remain consistent throughout 5 seconds — no morphing
- [ ] Heights and proportions stable — Andrey stays tallest, Marina shortest
- [ ] Hands stay connected logically — no hand teleportation or merging
- [ ] Dress colors stable — Kira RED, Marina WHITE, no color drift
- [ ] Hair color consistent — Andrey light blonde, Kira dark blonde, Marina light brown
- [ ] Walking motion natural — weight shift, shoulder sway, not sliding
- [ ] Fabric movement realistic — wind + forward motion, not chaotic
- [ ] Water reflections animate naturally — shimmer, not static or broken
- [ ] Camera movement smooth — no jumps, no shakes, cinematic drift
- [ ] No extra limbs, bent anatomy, or distorted proportions at any frame
- [ ] Expressions hold — Andrey forward/confident, Kira playful at camera, Marina loving at Andrey
- [ ] Final frame matches reference image composition for freeze-frame potential

---

## СОВЕТЫ ПО ГЕНЕРАЦИИ

### Если лицо искажается при движении
1. Используйте `image-to-video` вместо `text-to-video` с reference-фото.
2. В Runway: примените `Motion Brush` только на тело/фон, минимально на лицо.
3. В Kling: понизьте `Motion Strength` до 2-3.

### Если руки «расплываются»
1. Добавьте в negative prompt: `bad hands, fused fingers, merging hands, extra fingers, distorted hands`.
2. Убедитесь, что reference image показывает руки чётко.

### Если платья меняют цвет или форму
1. Усильте negative: `color changing, dress morphing, clothing shifting`.
2. Используйте image-to-video с чётким reference.

### Если нужно бесшовное зацикливание (loop)
- Попросите модель: `seamless loop, ending frame matches beginning frame`.
- Или сгенерируйте 5 сек, затем в видеоредакторе сделайте crossfade 0.5 сек между концом и началом.

---

## СВЯЗЬ СО СТАТИЧНЫМ ПРОМПТОМ

Этот видео-промпт является **motion layer** над статичным промптом:
- Статичный: `prompts/GROUP_PROMENADE_v1.0.md` — описывает КТО и КАК ВЫГЛЯДИТ.
- Видео: `prompts/GROUP_PROMENADE_VIDEO_v1.0.md` — описывает КАК ДВИГАЕТСЯ.

Для идеального результата:
1. Сгенерируйте reference image по статичному промпту.
2. Пропустите через `mia_validator.py` или ручную проверку на пропорции.
3. Используйте это изображение как `first frame` в видео-модель + motion prompt из этого файла.

---

*Источники: VISUAL_ANCHORS.json, VISUAL_PROMPT.txt, DYNAMIC_VISUALS.json*  
*Персонажи: andrey_senior, marina, kira*  
*Дата: 2026-06-21*
