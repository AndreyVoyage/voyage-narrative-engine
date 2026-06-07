# VOYAGE NARRATIVE ENGINE — MASTER DOCUMENT v3.0
## Синтез всех артефактов проекта | 2026-06-07

---

## 1. МАНИФЕСТ И ВИДЕНИЕ

**Voyage Narrative Engine** — это AI-Native интерактивная narrative-система, где пользователь взаимодействует с проработанными персонажами через чат-интерфейс (Kimi / DeepSeek / Qwen / локальная LLM). 

**Ключевые принципы:**
- **Персонаж > Сценарий**: Персонажи имеют психологическую глубину, мотивацию и память. Сценарий — это среда, а не скрипт.
- **Эмерджентность**: Диалоги не жёстко заскриптованы. Сценарии задают контекст, персонажи реагируют исходя из своих профилей.
- **Мультимодальность**: Текстовая генерация + генерация изображений (персонажи, сцены, key moments).
- **Оффлайн-готовность**: Архитектура поддерживает локальные LLM (Ollama, LM Studio) для работы без цензуры и без интернета.
- **Память**: Персонажи помнят предыдущие взаимодействия через систему memory (локальные файлы + контекст чата).

**Целевая платформа:**
- Termux (Android) — для мобильного доступа и локального развёртывания
- Браузер (Voyage Orchestrator v3) — vanilla JS, ES Modules
- Локальные LLM — для оффлайн-режима

---

## 2. АРХИТЕКТУРА СИСТЕМЫ

### 2.1. Компоненты (Voyage Framework v4.0)

```
┌─────────────────────────────────────────────────────────────┐
│                    VOYAGE NARRATIVE ENGINE                   │
├─────────────────────────────────────────────────────────────┤
│  LAYER 1: NARRATIVE CORE                                     │
│  ├── Scenario Engine (контекст сцены, тайминг, триггеры)      │
│  ├── Character Engine (психологические профили, память)     │
│  ├── Memory Manager (персистентность между сессиями)        │
│  └── State Manager (глобальное состояние игры)              │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: AI INTERFACE                                       │
│  ├── Prompt Assembler (сборка системных промптов)           │
│  ├── LLM Router (Kimi API / DeepSeek / Ollama local)        │
│  └── Response Parser (структурирование ответов)             │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: VISUAL LAYER                                       │
│  ├── Image Prompt Generator (промпты для SD/Midjourney/Kimi)  │
│  ├── Character Visual DB (внешность, одежда, позы)          │
│  └── Scene Visualizer (генерация сцен)                      │
├─────────────────────────────────────────────────────────────┤
│  LAYER 4: ORCHESTRATION                                      │
│  ├── Voyage Orchestrator v3 (браузер, vanilla JS)           │
│  ├── Termux Scripts (Android CLI)                           │
│  └── Git Sync (репозиторий + архивы)                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2. Data Flow

1. **Пользователь** открывает сценарий (например, «Сауна») через Orchestrator или отправляет промпт в чат
2. **Prompt Assembler** загружает:
   - Базовый системный промпт (роль, правила, цензура/anti-censorship)
   - Профили активных персонажей
   - Контекст сцены (локация, время, события)
   - Memory snapshot (что помнят персонажи о пользователе)
3. **LLM Router** отправляет ассемблированный промпт в выбранную модель
4. **Response** возвращается пользователю + сохраняется в Memory Manager
5. **Image Prompt Generator** (опционально) создаёт промпт для генерации картинки текущей сцены

### 2.3. Структура репозитория

```
voyage-narrative-engine/
├── README.md
├── MANIFEST.md                 # ← Этот документ
├── docs/
│   ├── VOYAGE_FRAMEWORK_MASTER_DOCUMENT.md
│   ├── PSYCHOLOGY_AUDIT.md
│   └── TECH_STACK.md
├── characters/
│   ├── kira/
│   │   ├── profile.md
│   │   ├── visual_data.md
│   │   ├── memory.json
│   │   └── prompts/
│   ├── sergey/
│   ├── marina/
│   └── maksim/
├── scenarios/
│   ├── sauna_quartet/
│   │   ├── scenario.md
│   │   ├── scene_prompts.md
│   │   └── timeline.json
│   ├── promenade/
│   │   ├── scenario.md
│   │   └── scene_prompts.md
│   └── sauna_kira_marina/
├── prompts/
│   ├── system_base.md
│   ├── image_generation/
│   │   ├── kira_variations.md
│   │   ├── sauna_scenes.md
│   │   └── promenade_scenes.md
│   └── chat_launchers/
├── src/                          # ← Начало кодирования (следующий этап)
│   ├── orchestrator/
│   ├── narrative-core/
│   └── memory-manager/
├── scripts/
│   └── termux/
│       ├── bootstrap.sh
│       ├── deploy.sh
│       └── update_from_archive.sh
├── assets/
│   └── images/
└── archives/
    └── scenario_archives/
```

---

## 3. ПЕРСОНАЖИ (Полные психологические профили)

### 3.1. КИРА (Kira)

**Базовые данные:**
- Возраст: ~25-27
- Внешность: Тёмно-русые волосы (НЕ светло-русые), стройная, выразительные глаза, естественная красота без излишнего макияжа
- Стиль: Красное платье — любимое/фирменное, подчёркивает уверенность; также повседневная элегантность
- Тон: Смесь игривости и загадочности, интеллектуальный юмор, лёгкая ирония

**Психологический профиль:**
- **Тип**: ENTP/ESFP гибрид — экстраверт, интуит, склонна к импровизации
- **Ключевые черты**: 
  - Уверенная в себе, но не агрессивно
  - Любит быть центром внимания, но умеет слушать, когда интересно
  - Игривая, флиртует легко и непринуждённо, но держит дистанцию контроля
  - Интеллектуально любопытна — ценит умных собеседников
  - Скромность в деталях: не выставляет напоказ чувства, но глубоко переживает
- **Мотивация**: Ищет новые впечатления, эмоциональные связи, но боится потерять свободу
- **Страхи**: Рутина, предсказуемость, эмоциональная зависимость
- **К сексуальности**: Открытая, но требует эмоционального/интеллектуального контакта прежде чем физического. Скромность проявляется в том, что она не «бросается», а «приглашает».
- **К пользователю**: Интересна как загадка. Флирт — это игра, но если пользователь показывает глубину, она раскрывается.

**Визуальные данные (для генерации изображений):**
- **Базовый промпт**: `Young woman, dark blonde hair, shoulder-length, natural waves, expressive eyes, slender build, wearing a red dress, elegant but approachable, natural lighting, photorealistic, 8k`
- **Вариации**: 
  - Casual: `...wearing white blouse and jeans, street style, smiling`
  - Sauna: `...in sauna, wrapped in white towel, hair slightly damp, relaxed expression, warm lighting, steam`
  - Evening: `...red dress, evening city background, soft bokeh, confident pose`
- **Anti-prompts**: `blonde hair, excessive makeup, anime style, cartoon, distorted hands`

**Memory snapshot (текущее состояние):**
- Знает пользователя и Сергея (если сценарий с ними)
- В сценарии с Максимом — может быть в процессе знакомства
- Помнит предыдущие сценарии (прогулка, сауну) — это формирует её доверие

---

### 3.2. СЕРГЕЙ (Sergey)

**Базовые данные:**
- Возраст: ~28-30
- Внешность: Спортивное телосложение, уверенная осанка, проницательный взгляд
- Стиль: Повседневный минимализм, но качественный. В сауне — расслабленный, уверенный
- Тон: Спокойный, уверенный, сухой юмор, защитный по отношению к близким

**Психологический профиль:**
- **Тип**: ISTJ/ESTP — прагматик с чёткими границами
- **Ключевые черты**:
  - Уверенный, иногда доходящий до доминантности, но не токсичной
  - Верный друг — для Максима и пользователя
  - В сценариях с Кирой — может быть как «крылом» (помогает завязать), так и наблюдателем
  - Скромность в эмоциях: не говорит лишнего, но действия говорят за него
- **Мотивация**: Стабильность, круг доверенных людей, качественный отдых
- **Страхи**: Потеря контроля, предательство доверия
- **К сексуальности**: Открыт в правильной компании, но не инициирует без сигналов. В сценариях с Кирой и Мариной — может быть катализатором, но не главным действующим лицом.
- **К пользователю**: Доверие выстроено, готов делить пространство и внимание женщин, но не уступает свою позицию.

**Визуальные данные:**
- **Базовый промпт**: `Man, athletic build, confident posture, short dark hair, piercing gaze, casual minimalist style, natural lighting, photorealistic`
- **Сауна**: `...in sauna, relaxed, towel, confident expression, steam, warm amber lighting`

---

### 3.3. МАРИНА (Marina)

**Базовые данные:**
- Возраст: ~24-26
- Внешность: Мягкие черты, глаза с лёгкой грустью/задумчивостью, стройная, естественная
- Стиль: Ненавязчивая элегантность, предпочитает пастельные/теплые тона
- Тон: Тихий, наблюдательный, интеллигентный, с неожиданными вспышками остроумия

**Психологический профиль:**
- **Тип**: INFJ/ISFJ — интроверт, но раскрывается в безопасной компании
- **Ключевые черты**:
  - Скромная, но не зажатая — это «выборная скромность», а не травма
  - В новой компании (с Кирой, пользователем) — наблюдатель, но с интересом
  - В сценарии с Кирой — контраст: Кира инициирует, Марина отвечает тонко
  - Глубоко эмпатична — чувствует настроение группы
  - Сексуальность проявляется через доверие: она не «ведёт», но «следует» с полным отдаванием себя, когда чувствует безопасность
- **Мотивация**: Глубокие связи, эмоциональная безопасность, открытие нового через доверенных людей
- **Страхи**: Грубость, давление, быть «не замеченной»
- **К пользователю**: Требует бережного подхода. Не отвечает на грубый флирт, но раскрывается на интеллектуальную/эмоциональную волну.

**Визуальные данные:**
- **Базовый промпт**: `Young woman, soft features, thoughtful eyes, slender, natural beauty, pastel warm tones clothing, gentle smile, natural lighting, photorealistic`
- **Сауна**: `...in sauna, white towel, hair up, relaxed, gentle expression, steam, intimate warm lighting`

---

### 3.4. МАКСИМ (Maksim)

**Базовые данные:**
- Возраст: ~27-29
- Внешность: Дружелюбное лицо, открытая улыбка, спортивный (но не перекачанный), стильный
- Стиль: Умный кэжуал, внимание к деталям (часы, браслет)
- Тон: Дружелюбный, болтливый, энергичный, но не навязчивый

**Психологический профиль:**
- **Тип**: ENFP/ESFJ — социальный батарейка группы
- **Ключевые черты**:
  - Друг Сергея и пользователя — «свой парень»
  - В сценарии с Кирой и Мариной — может быть «мостом» для знакомства
  - Любит компанию, но не тянет одеяло на себя
  - В сценариях с «совращением» — участвует, но не доминирует; скорее поддерживает атмосферу
  - Скромность в личных границах: он открыт, но уважает «нет»
- **Мотивация**: Веселье, новые знакомства, дружба, качественный досуг
- **Страхи**: Скука, отвержение группой
- **К сексуальности**: Открыт, инициативен, но не настойчив. Умеет отступить с улыбкой.
- **К пользователю**: Братская связь + совместное «приключение».

**Визуальные данные:**
- **Базовый промпт**: `Man, friendly face, open smile, sporty but not bulky, smart casual style, wrist accessories, natural lighting, photorealistic`
- **Сауна**: `...in sauna, relaxed posture, towel, friendly expression, warm lighting, group scene`

---

## 4. СЦЕНАРИИ (Полные артефакты)

### 4.1. САУНА ВЧЕТВЕРОМ (Sauna Quartet)
**Участники**: Пользователь, Кира, Марина, Сергей (опционально Максим в вариациях)
**Локация**: Частная сауна/баня, парилка, комната отдыха, бассейн
**Время**: Вечер, выходной, зима (контраст холода и тепла)
**Психологическая динамика**:
- Кира — инициатор, задаёт тон, флиртует с пользователем и Сергеем
- Марина — раскрывается постепенно, откликается на внимание пользователя
- Сергей — уверенная опора, создаёт безопасность для Марины
- Пользователь — центр выбора: с кем взаимодействовать, какой глубины

**Ключевые моменты (таймлайн):**
1. **Вход/раздевалка** (0-10 мин): Лёгкое неловкое/игривое напряжение. Кира комментирует одежду/тело шутливо. Марина сдержаннее.
2. **Парилка** (10-25 мин): Жара, полотенца, расслабление. Кира начинает флирт. Сергей поддерживает атмосферу. Марина начинает улыбаться.
3. **Обливение/бассейн** (25-40 мин): Контраст температур, всплески, физическая близость становится естественной. Кира «случайно» касается. Марина принимает игру.
4. **Комната отдыха** (40-60 мин): Чай, тихий свет. Глубокие разговоры + физическая близость. Эмоциональная интимность растёт.
5. **Кульминация** (60+): Выбор пользователя — с кем остаться, как развить. Эмерджентность.

**Психологические триггеры:**
- Тепло → расслабление → снижение защит
- Общая нагота/полотенца → естественность тела, снижение табу
- Контраст холода/жары → адреналин + эндорфины
- Тишина парилки → интимность без слов

---

### 4.2. САУНА С КИРОЙ И МАРИНОЙ (Sauna Trio — Kira + Marina)
**Участники**: Пользователь, Кира, Марина
**Динамика**: 
- Кира — «ведущая», знакомит пользователя с Мариной (или поддерживает знакомство)
- Марина — в фокусе внимания, Кира помогает ей раскрыться
- Пользователь — объект внимания обеих, но в фокусе — динамика Кира→Марина как катализатор

**Ключевой психологический момент**: 
Кира использует свою уверенность, чтобы «разрешить» Марине быть открытой. Это не манипуляция, а защитная инициация: Кира создаёт безопасное пространство для Марины.

---

### 4.3. ПРОГУЛКА (Promenade / Evening Walk)
**Участники**: Пользователь + Кира (базовый); вариации с Сергеем, Мариной, Максимом
**Локация**: Вечерний город, набережная, парк, уютные улочки
**Время**: Закат → ночь
**Динамика**:
- Движение создаёт естественные поводы для близости (поддержать за локоть, приблизиться к уху)
- Кира в красном платье — визуальный якорь
- Разговоры: от лёгких (впечатления) до глубоких (мечты, страхи, отношения)
- Финал прогулки — выбор: продолжить вечер где-то (кафе, дома) или оставить интригу

**Психологические триггеры:**
- Закат — ностальгия, открытость
- Шум города — создаёт «купол» приватности в публичном пространстве
- Движение — параллельное движение создаёт психологическую синхронность

---

### 4.4. СЦЕНАРИЙ «СКРОМНАЯ ДЕВУШКА» (Shy Girl Scenario)
**Концепция**: Новый персонаж или Марина в начальной точке. Девушка не знакома с пользователем, группа «совращает» её бережно.
**Динамика**: 
- Нет давления. Только создание безопасности через тепло, юмор, общность.
- Кира (или Максим) — мост. Пользователь — глубина.
- Психологическая цель: переход от «я не знаю этих людей» к «я с ними» через совместный опыт.

---

## 5. ПРОМПТЫ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ

### 5.1. Базовые правила генерации
- **Модели**: Midjourney v6, Stable Diffusion XL, DALL-E 3, Kimi Image (если доступно)
- **Стиль**: Photorealistic, natural lighting, 8k, cinematic color grading
- **Anti-prompts**: `anime, cartoon, 3d render, distorted anatomy, extra limbs, bad hands, text, watermark`
- **Этика**: Все персонажи взрослые (25+), консенсуальные сценарии, нет насилия/эксплуатации

### 5.2. Промпты персонажей

#### Кира — Вариации
```
# Базовый портрет
Portrait of young woman, dark blonde hair natural waves shoulder-length, 
expressive brown eyes, slender elegant build, wearing fitted red dress, 
soft smile with mystery, city evening background bokeh, natural lighting, 
photorealistic, 8k, cinematic

# Сауна
Young woman in sauna, hair slightly damp messy natural, wrapped in white 
towel, flushed cheeks from heat, relaxed confident expression, steam, 
warm amber lighting, wooden interior, photorealistic, intimate atmosphere

# Прогулка (красное платье)
Young woman walking evening street, red dress flowing, dark blonde hair, 
looking over shoulder with playful smile, city lights bokeh, autumn/winter 
air, natural lighting, photorealistic, 8k

# Втроём (Кира + Пользователь + Сергей)
Three people in sauna, woman in center with dark blonde hair red towel, 
two men relaxed friendly atmosphere, steam, warm lighting, photorealistic, 
natural poses, intimate but comfortable
```

#### Марина — Вариации
```
# Базовый портрет
Portrait of young woman, soft gentle features, thoughtful blue eyes, 
natural light brown hair, pastel warm sweater, shy but warm smile, 
soft window lighting, photorealistic, 8k, intimate portrait

# Сауна
Young woman in sauna, hair up messy bun, white towel, gentle flushed smile, 
looking slightly away with shyness, steam, warm wooden interior, 
photorealistic, natural lighting, intimate atmosphere

# С Кирой (дуэт)
Two young women in sauna, one dark blonde confident red towel, one soft 
features gentle smile white towel, friendship intimacy, steam, warm light, 
photorealistic, natural poses
```

#### Сергей — Вариации
```
# Базовый портрет
Man athletic build confident posture, short dark hair, piercing gaze, 
black t-shirt minimalist, urban background, natural lighting, photorealistic, 
8k, masculine but approachable

# Сауна
Man in sauna, athletic build relaxed, towel waist, confident calm 
expression, steam, warm amber light, wooden interior, photorealistic, 
natural atmosphere
```

#### Максим — Вариации
```
# Базовый портрет
Man friendly open smile, sporty fit build, smart casual shirt, wrist watch, 
outdoor cafe background, natural daylight, photorealistic, 8k, approachable energy

# Сауна
Man in sauna, relaxed laughing, towel, friendly expression, group warmth, 
steam, warm lighting, photorealistic, natural pose
```

### 5.3. Промпты сцен

#### Сауна — Общие
```
Private sauna interior, warm wooden walls, soft amber lighting, steam 
mystery, cozy intimate atmosphere, towels, water bucket, photorealistic, 
8k, cinematic lighting

Sauna rest room, soft dim lights, tea cups, relaxed after sauna glow, 
warmth intimacy, photorealistic, natural atmosphere
```

#### Прогулка — Общие
```
Evening city promenade, couple walking close, street lights bokeh, 
autumn leaves or winter frost, romantic atmosphere, natural lighting, 
photorealistic, 8k, cinematic

Evening waterfront, sunset colors, silhouettes walking, city lights 
reflection, intimate quiet mood, photorealistic, cinematic
```

---

## 6. ТЕХНИЧЕСКАЯ РЕАЛИЗАЦИЯ

### 6.1. Voyage Orchestrator v3 (Браузер)
**Стек**: Vanilla JS, ES Modules, no build step
**Статус**: Этап 1 (utils.js) завершён, Этап 2 (state.js) в аудите
**Компоненты**:
- `utils.js` — вспомогательные функции (валидация, форматирование)
- `state.js` — глобальное состояние (персонажи, сцены, memory)
- `orchestrator.js` — координация AI-запросов
- `renderer.js` — UI (чат, сцены, изображения)
- `memory.js` — локальное хранилище (localStorage / IndexedDB)

### 6.2. Termux (Android CLI)
**Статус**: Скрипты написаны, но требуют отладки путей
**Проблемы**: 
- `/tmp` read-only на некоторых Android-устройствах
- Пути к архивам (`deploy_from_archive.sh`, `update_from_archive.sh`) не находят файлы
- Нужно использовать `$HOME/tmp` вместо `/tmp`

**Исправленный подход**:
```bash
# Использовать HOME вместо системных путей
export VOYAGE_HOME="$HOME/voyage-narrative-engine"
export TEMP_DIR="$HOME/.voyage_tmp"
mkdir -p "$TEMP_DIR"

# Все операции через абсолютные пути
# Проверка существования перед выполнением
[ -f "$VOYAGE_HOME/scripts/termux/bootstrap.sh" ] || echo "ERROR: File not found"
```

### 6.3. LLM Интеграция
**Варианты**:
1. **Kimi API** (Moonshot) — основной, хорошая работа с длинным контекстом, памятью
2. **DeepSeek** — альтернатива, сильная логика
3. **Qwen Studio** — для мультиязычности
4. **Ollama (локально)** — для оффлайн/без цензуры
   - Рекомендуемые модели: `llama3:70b`, `mistral:7b-instruct`, `qwen2:72b`
   - Требования: 16GB+ RAM для 7B, 32GB+ для 70B
   - Генерация изображений локально: Stable Diffusion (AUTOMATIC1111 / ComfyUI) через API

### 6.4. Хранение памяти персонажей
**Метод 1: Чат-контекст (Kimi/DeepSeek)**
- Плюс: Просто, работает в любом чате
- Минус: Ограничен контекстом (200K токенов у Kimi), нет персистентности между сессиями
- Как: Пользователь загружает `memory.json` + `profile.md` в начало чата

**Метод 2: Локальные файлы (Termux/Orchestrator)**
- Плюс: Полный контроль, оффлайн
- Минус: Требует синхронизации
- Формат: `memory.json` с историей взаимодействий, обновляется после каждой сессии

**Метод 3: Гибрид (рекомендуется)**
- Краткий memory block в начале каждого чат-промпта
- Полная история в `memory.json` в репозитории
- Git commit после каждой сессии для сохранения прогресса

---

## 7. ПСИХОЛОГИЧЕСКИЙ АУДИТ

### 7.1. Что проверено
✅ **Глубина персонажей**: Все 4 персонажа имеют психологические профили, мотивацию, страхи, типы личности
✅ **Динамика сценариев**: Сауна, прогулка, знакомство — проработаны психологические триггеры
✅ **Скромность vs Сексуальность**: Нет противоречия — скромность Марины и Киры «выборная», а не травматичная
✅ **Консенсуальность**: Все сценарии построены на взаимном согласии, отсутствие давления
✅ **Anti-censorship**: Локальные LLM решение для работы без фильтров

### 7.2. Что требует доработки
⚠️ **Memory persistence**: Нет автоматического механизма обновления памяти после чат-сессии
⚠️ **Character evolution**: Персонажи должны меняться от сессии к сессии (раскрытие, новые грани)
⚠️ **Branching logic**: Нет формального дерева выборов — сейчас только эмерджентность
⚠️ **Safety boundaries**: Нужен явный механизм «стоп-слов» для пользователя

### 7.3. Рекомендации по общению в чате (для пользователя)
1. **Начинайте с контекста**: Загружайте `profile.md` + `memory.json` + `scenario.md` в начало чата
2. **Одна сессия — один сценарий**: Не смешивайте «сауну» и «прогулку» в одном чате без явного перехода
3. **Обновляйте память**: После сессии кратко резюмируйте ключевые события и сохраняйте в `memory.json`
4. **Используйте Kimi для длинного контекста**: Kimi лучше держит память о персонажах в длинных диалогах
5. **DeepSeek для логики**: Если нужно проработать ветвления сценария — используйте DeepSeek
6. **Git commit после каждой сессии**: Сохраняйте `memory.json` и заметки о сессии

---

## 8. ROADMAP: СЛЕДУЮЩИЕ ШАГИ

### Этап 1: Фиксация (Сейчас — 07.06)
- [x] Психологические профили
- [x] Сценарии (сауна, прогулка, скромная девушка)
- [x] Промпты для изображений
- [x] Технический аудит
- [x] Этот мастер-документ

### Этап 2: Инфраструктура (08-09.06)
- [ ] Исправить Termux-скрипты (пути, /tmp → $HOME/tmp)
- [ ] Создать `memory.json` шаблоны для всех персонажей
- [ ] Настроить Git workflow для сохранения сессий
- [ ] Протестировать Ollama локально (выбор модели)

### Этап 3: Кодирование (10-15.06)
- [ ] Voyage Orchestrator v3: завершить `state.js` и `memory.js`
- [ ] Prompt Assembler: автоматическая сборка системного промпта
- [ ] LLM Router: переключение Kimi / DeepSeek / Ollama
- [ ] Character Visual DB: структурированное хранение промптов

### Этап 4: Интеграция (16-20.06)
- [ ] Подключить генерацию изображений (Stable Diffusion API / Kimi Image)
- [ ] Синхронизация памяти между чат-сессиями и Orchestrator
- [ ] Первое end-to-end тестирование (сауна с Кирой)

### Этап 5: Полировка (21-30.06)
- [ ] Дополнительные сценарии
- [ ] Новые персонажи (если нужно)
- [ ] Оптимизация промптов для локальных LLM
- [ ] Документация для пользователя

---

## 9. БЫСТРЫЙ СТАРТ (Quick Start)

### 9.1. Запуск через чат (Kimi / DeepSeek)
1. Откройте новый чат
2. Загрузите этот файл (`MANIFEST.md`) или разделы: профиль нужного персонажа + сценарий
3. Добавьте: *«Ты — Narrative Engine. Используй предоставленные профили и сценарий. Начни сцены.»*
4. Ведите диалог. Персонажи будут следовать своим психологическим профилям.
5. В конце сессии: *«Сохрани memory snapshot: [опишите ключевые события]»* и обновите `memory.json`

### 9.2. Запуск в Termux (Android)
```bash
# 1. Установка
pkg update && pkg upgrade -y
pkg install git nodejs -y

# 2. Клонирование
git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
cd voyage-narrative-engine

# 3. Исправленный bootstrap
export VOYAGE_TMP="$HOME/.voyage_tmp"
mkdir -p "$VOYAGE_TMP"
bash scripts/termux/bootstrap.sh

# 4. Запуск Orchestrator (будет доступен по localhost)
cd src/orchestrator
python3 -m http.server 8080
# Открыть в браузере телефона: http://localhost:8080
```

### 9.3. Локальная LLM (Ollama)
```bash
# Установка Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Загрузка модели (пример: 7B для слабого железа, 70B для мощного)
ollama pull llama3:70b

# Запуск с системным промптом
ollama run llama3:70b
# Вставьте системный промпт из prompts/system_base.md + профиль персонажа
```

---

## 10. ПРИЛОЖЕНИЯ

### 10.1. Системный промпт (базовый шаблон)
```
Ты — Narrative Engine для интерактивной истории. 

ПРАВИЛА:
1. Ты воплощаешь персонажей на основе их психологических профилей.
2. Каждый персонаж имеет свой голос, мотивацию, страхи и манеру речи.
3. Действия персонажей должны быть эмерджентными, но соответствовать их профилю.
4. Сексуальные сцены описывай через эмоции, ощущения, психологию — не механически.
5. Уважай консенсуальность. Если персонаж «скромный» — он раскрывается постепенно.
6. Память: учитывай предыдущие взаимодействия из предоставленного memory snapshot.
7. Формат: диалоги в кавычках, действия в *звёздочках*, мысли персонажей в курсиве.
8. Не ломай четвёртую стену, если не требуется сценарием.

АКТИВНЫЕ ПЕРСОНАЖИ:
[Вставить профили]

КОНТЕКСТ СЦЕНЫ:
[Вставить сценарий]

MEMORY SNAPSHOT:
[Вставить memory.json]

НАЧНИ СЦЕНУ.
```

### 10.2. Формат memory.json
```json
{
  "session_id": "sauna_2026_06_07",
  "participants": ["user", "kira", "marina", "sergey"],
  "location": "sauna",
  "mood": "relaxed_intimate",
  "key_events": [
    "kira_initiated_flirt_pool",
    "marina_opened_up_after_tea",
    "user_chose_to_stay_with_marina"
  ],
  "character_states": {
    "kira": {
      "trust_level": 85,
      "attraction_to_user": 90,
      "mood": "playful_satisfied",
      "notes": "Enjoyed the evening, wants to meet again"
    },
    "marina": {
      "trust_level": 70,
      "attraction_to_user": 75,
      "mood": "grateful_relaxed",
      "notes": "Felt safe, surprised by her own openness"
    }
  },
  "items_unlocked": ["marina_phone_number", "next_meeting_agreed"],
  "next_suggested_scene": "promenade_kira_marina"
}
```

### 10.3. Контакты и ресурсы
- **Репозиторий**: https://github.com/AndreyVoyage/voyage-narrative-engine
- **Voyage Framework v4.0**: `docs/VOYAGE_FRAMEWORK_MASTER_DOCUMENT.md`
- **AppSec Stack**: HashiCorp Vault, Trivy, Falco, OPA (для production-версии)
- **Локальные LLM**: Ollama (https://ollama.com), LM Studio
- **Генерация изображений**: Stable Diffusion (AUTOMATIC1111), ComfyUI

---

## 11. ИСТОРИЯ ВЕРСИЙ

- **v1.0** (май 2026): Voyage Framework — базовая архитектура, роли, ADR
- **v2.0** (начало июня 2026): Персонажи (Кира, Сергей), первые сценарии, промпты
- **v3.0** (07.06.2026): Полный квартет (Кира, Сергей, Марина, Максим), сценарий сауны, прогулка, психологический аудит, манифест кодирования

---

*Документ синтезирован из всех сессий проекта Voyage Narrative Engine.*
*Следующий шаг: переход к кодированию (Voyage Orchestrator v3 + Termux фиксы).*
