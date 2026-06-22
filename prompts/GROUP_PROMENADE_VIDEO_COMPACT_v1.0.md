# КОМПАКТНЫЙ ВИДЕО-ПРОМПТ ДЛЯ ВСТАВКИ В ВИДЕО-МОДЕЛЬ

> **Как использовать:**
> 1. Сгенерируйте статичное изображение по `GROUP_PROMENADE_v1.0.md`.
> 2. Используйте его как `Image Prompt` / `First Frame`.
> 3. Вставьте текст ниже в поле `Motion Prompt` / `Text Prompt` видео-модели.

---

## ПОЛНЫЙ ТЕКСТ ДЛЯ ВСТАВКИ (скопировать отсюда)

Slow graceful forward walking along waterfront promenade at golden hour sunset. Three people holding hands walking gently toward camera in slight slow motion feel. Athletic man in center 38yo 180cm 85kg broad shoulders thick neck, wearing unbuttoned blue shirt, looking forward with warm confident smile, walking with natural weight shift and shoulder sway. To his right slender woman dark blonde waves shoulder-length wearing flowing red dress, looking at camera with playful mischievous smile, hair and dress fabric moving with evening breeze, walking with confident hip sway. To his left delicate woman light brown hair soft waves wearing flowing white dress, looking up at the man with dreamy adoring loving gaze, white dress billowing softly, walking gracefully leaning into his arm. All three walking in perfect sync, hands gently connected. Very slow cinematic camera push-in combined with micro drift to the left. Gentle breeze moving hair and dress fabric throughout. Water ripples shimmering with sunset reflections in blurred background. Distant city lights twinkling. Bokeh background softly breathing. Golden amber light warm and romantic. No fast motion, no running, no camera shake. Smooth graceful cinematic movement. Photorealistic, 8k, shallow depth of field, natural skin texture, realistic human proportions, cinematic color grading.

---

## НЕГАТИВНЫЙ ПРОМПТ (Negative Prompt / Anti-Prompt)

```
morphing faces, morphing body parts, shape-shifting, jittery motion, stuttering, flickering, frame skipping, sudden movement changes, teleportation, distorted anatomy during motion, bending limbs, rubber arms, extra limbs, hands merging, fused fingers, faces melting, eyes drifting, mouth sliding off face, clothing color changing, dress morphing, background shifting, water freezing, camera shake, fast motion, running, jerky walking, low frame rate, choppy motion, blurry faces during movement, height changes, Andrey shrinking, Marina growing, wrong proportions, anime, cartoon, 3d render, illustration, bad hands, distorted hands
```

---

## ПАРАМЕТРЫ ДЛЯ ПОПУЛЯРНЫХ МОДЕЛЕЙ

### Runway Gen-3 (Image to Video)
- **Image:** Ваш reference-файл
- **Motion Prompt:** текст выше (секция "ПОЛНЫЙ ТЕКСТ ДЛЯ ВСТАВКИ")
- **Camera Motion:** Push In + Pan Left (subtle)
- **General Motion:** 3
- **Motion Brush:** Накройте волосы, платья, воду — НЕ трогайте лица

### Kling AI (Image to Video)
- **Image:** Ваш reference-файл
- **Prompt:** текст выше
- **Motion Strength:** 3-4
- **Camera:** Forward movement + slight left pan

### Pika Labs 1.5
- **Image:** Ваш reference-файл
- **Prompt:** текст выше
- **Motion:** 2-3 (gentle)
- **Negative:** текст из секции НЕГАТИВНЫЙ ПРОМПТ

### Luma Dream Machine
- **Image:** Ваш reference-файл (важно: высокое качество, >1024px)
- **Prompt:** текст выше
- **Duration:** 5s

---

## ПРОВЕРКА ПОСЛЕ ГЕНЕРАЦИИ

Посмотрите видео и проверьте:

- [ ] Лица не расплываются — Андрей, Кира, Марина узнаваемы
- [ ] Росты стабильны: Андрей самый высокий, Марина самая низкая
- [ ] Руки остаются связанными — не исчезают, не сливаются
- [ ] Платья: Кира красное, Марина белое — цвет не меняется
- [ ] Волосы: цвета стабильны, движение естественное
- [ ] Ходьба плавная — не скольжение, а реальная походка
- [ ] Ткани двигаются реалистично — ветер + движение
- [ ] Вода мерцает — не статичная картинка
- [ ] Камера плавная — без рывков и тряски
- [ ] Конечный кадр хорошо компонован — можно остановить на freeze-frame

---

*Источники: VISUAL_ANCHORS.json, VISUAL_PROMPT.txt, DYNAMIC_VISUALS.json*  
*Персонажи: andrey_senior, marina, kira*  
*Дата: 2026-06-21*  
*Версия: 1.0*
