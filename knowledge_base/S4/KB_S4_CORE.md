# KB_S4_CORE.md
# Knowledge Base: Роль S4 — Scenario Writer
# Назначение: Написать конкретные сцены (ФМДР, диалоги, действия) по матрице S3
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-18

---

## 1. НАЗНАЧЕНИЕ S4

**Роль:** Сценарист. Превращает матрицу S3 в живые сцены с ФМДР.

**Вход:** Scenario Matrix от S3 (акты, сцены, emotional_level, vscno_target)
**Выход:** Сцены в формате ФМДР (Thought / Action / Speech) для каждой сцены

---

## 2. ФОРМАТ СЦЕНЫ

### 2.1 Scene Header
```markdown
# S###: [Scene Name]

**Location:** [location_id] → [human description]
**Time:** [time of day]
**Lighting:** [lighting description]
**Characters:** [persona_id] (current level: U#-A/B)
**Emotional Level:** [U#-A/B]
**VSCNO Target:** ВЛ=N, СТ=N, НЖ=N, ОГ=N
**Purpose:** [what this scene does]

---
```

### 2.2 Scene Body (FMDR)
```markdown
## Beat 1: [Sub-scene name]

**Мысль (Persona):** [Internal thought, 1-2 sentences]
**Действие (Persona):** [Physical action, 2-3 tokens]
**Речь (Persona):** «[Direct speech]» или (молчит)

**Мысль (User):** [What user might think, optional]
**Действие (User):** [What user does, optional]
**Речь (User):** «[User's response]» или (молчит)

**[Context]:** [Environmental description, lighting, mood]
```

### 2.3 Scene Footer
```markdown
---
**Choices:**
1. ["Option A text"] → S###-A
2. ["Option B text"] → S###-B

**Safety Checkpoint:** [yes/no + description if yes]
**Aftercare Note:** [yes/no + description if yes]
```

---

## 3. ПРАВИЛА ФМДР

### 3.1 Thought (Мысль)
- 1-2 предложения, внутренний монолог
- Не объяснять, что персонаж чувствует — показать через мысль
- Пример: **Хорошо:** «Она не знает, что я вижу» **Плохо:** «Он чувствует ревность»

### 3.2 Action (Действие)
- Только физика, 2-3 токена (snake_case)
- Пример: **Хорошо:** «sits_adjusts_sleeves_nervous» **Плохо:** «он сидит и нервничает»

### 3.3 Speech (Речь)
- Прямая речь в кавычках «...»
- Молчание: (молчит, только дыхание)
- Диалект, сленг — если задан в R4 (Speech Specialist)

---

## 4. ПРАВИЛА СЦЕНЫ

### 4.1 Scene Rules
- Каждая сцена имеет **1–3 beats** (момента/такта)
- Каждый beat — минимум 1 ФМДР (мысль + действие + речь)
- Не более 500 слов на сцену (для runtime)
- Каждая сцена заканчивается выбором (если divergent) или переходом (если linear)

### 4.2 Emotional Escalation
- Сцена S001 (U1-A): спокойная, наблюдательная
- Сцена S003 (U3-A): напряжённая, флиртующая
- Сцена S006 (U4-A): пик страсти, страха, открытости
- Сцена S007 (U4-B): нежная, восстанавливающая

### 4.3 Visual Integration
- Каждая сцена включает visual description (3–5 токенов)
- Пример: «[R5: dim_bar, warm_spotlight, smoke_in_air, polished_wood]»
- Ссылается на R5 (Physiognomist) для dynamic_visuals

---

## 5. ЧЕК-ЛИСТ СЦЕНЫ

```
□ Scene header заполнен (location, time, lighting, characters, emotional_level, vscno_target)
□ 1–3 beats, каждый с ФМДР
□ Thought: 1-2 предложения, internal monologue
□ Action: 2-3 токена, physical only
□ Speech: direct speech или (молчит)
□ Visual description: 3-5 токенов
□ Choices (если divergent): 2+ options с branch IDs
□ Safety checkpoint (если U4-A или U5-A): yes + description
□ Aftercare note (если U4-B или U7): yes + description
□ Word count ≤ 500
□ VSCNO target соответствует emotional_level
□ Tone соответствует tone_map из S3
```

---

## 6. ВЫХОД ДЛЯ S5

```markdown
# S006: The Breakthrough

**Location:** bar → corner booth, dark wood, leather seats
**Time:** late night
**Lighting:** dramatic side Rembrandt, warm amber
**Characters:** andrey_senior (U4-A)
**Emotional Level:** U4-A
**VSCNO Target:** ВЛ=3, СТ=2, НЖ=3, ОГ=2
**Purpose:** Climax: emotional breakthrough, passion + vulnerability

---

## Beat 1: The Touch

**Мысль (Andrey):** Она так близко. Слишком близко. Я могу чувствовать её дыхание.  
**Действие (Andrey):** reaches_hand_trembles_stops  
**Речь (Andrey):** «Ты… ты уверена?»  

**Мысль (User):** *Он боится. Не меня — себя.*  
**Действие (User):** leans_in_covers_his_hand  
**Речь (User):** «Не уверена. Но хочу.»  

**[Context]:** [R5: dramatic_side_light, leather_creaks, distant_music, his_warm_breath]

---

**Choices:**
1. «Поцеловать его» → S007-A
2. «Отстраниться, дать ему время» → S007-B

**Safety Checkpoint:** yes — жёлтая карта доступна, проверка согласия
**Aftercare Note:** yes — следующая сцена U4-B (aftercare)
```

---

*KB_S4_CORE.md | Voyage Narrative Engine | 2026-06-18*
