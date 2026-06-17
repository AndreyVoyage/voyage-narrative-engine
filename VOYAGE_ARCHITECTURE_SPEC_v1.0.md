# VOYAGE ARCHITECTURE SPECIFICATION v1.0.0

> **Единая архитектурная спецификация Voyage Narrative Engine (VNE).**
> Создана на основе актуальных документов репозитория. `SPEC_PART_1_2.md` и `SPEC_PART_3.md` отсутствуют — документ собран из существующих источников. Ствол 4 (Narrative Pipeline) заполнен. `PRELOAD_VNE_v3.2.1.md` по-прежнему отмечен `[NEEDS_DATA]`.

---

## Содержание

1. [Ствол 1: System Tree](#1-ствол-1-system-tree)
2. [Ствол 2: Persona Pipeline](#2-ствол-2-persona-pipeline)
3. [Ствол 3: Scenario Pipeline](#3-ствол-3-scenario-pipeline)
4. [Ствол 4: Narrative Pipeline](#4-ствол-4-narrative-pipeline)
5. [Глоссарий](#5-глоссарий)
6. [Decision Log](#6-decision-log)
7. [Статусы компонентов](#7-статусы-компонентов)
8. [Известные конфликты](#8-известные-конфликты)

---

## 1. СТВОЛ 1: SYSTEM TREE

### 1.1. Назначение

Voyage Narrative Engine — спецификационный репозиторий для создания психологически достоверных персонажей и интерактивных романтических/эротических сценариев, управляемых внешним LLM. Репозиторий не содержит исполняемого runtime; runtime — это LLM-чат, в который загружаются собранный монофайл персонажа + сценарий + state.

### 1.2. Тип репозитория

- **Спецификационный**: основные артефакты — Markdown-документы, JSON-схемы, промпты ролей.
- **Модульный**: персонажи разрабатываются в `personas/[name]/`, но для runtime собираются в монолитный JSON или COMPACT Markdown.
- **Двухсистемный**: сейчас одновременно существуют монолитные JSON-модули (`personas/*.json`) и модульная директория (`personas/kira/`).

### 1.3. Роли в системе

| Роль | Игрок | Описание |
|------|-------|----------|
| **Разработчик (человек)** | Создаёт персонажа, отвечает на вопросы ролей, принимает решения. | |
| **R1–R8 (LLM-роли)** | Специализированные промпты в `roles/`. | Собирают, анализируют, валидируют персонажа. |
| **State Manager** | `session_finalize.py` / `roles/ROLE_STATE_MANAGER_v1.0_PROMPT.md`. | Обновляет state после сессии. |
| **Narrative Editor** | `roles/ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md`. | Преобразует ФМДР в литературный рассказ. |
| **Visual Extractor / Physiognomist** | `roles/ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md`, `roles/ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md`. | Генерируют визуальные промпты. |
| **LLM Runtime** | Kimi / DeepSeek / Claude / ChatGPT / локальные модели. | Ведёт сценарий по загруженному промпту. |
| **Пользователь** | Играет от первого лица, даёт команды (`У3-А`, `АД КН`, `СТОП`). | |

### 1.4. Data Flow

```
Разработчик
    │
    ▼
┌─────────────────┐
│ R1 Interviewer  │ → PORTRAIT_[NAME]_v1.4.md
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R2 Psychologist │ → PSYCHOLOGY_[NAME]_v1.4.md (VSCNO, АД, internal_state)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R3 Sexologist   │ → SEXOLOGY_[NAME]_v1.md (TEC, shadow desires)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R4 Linguist     │ → LINGUISTICS_[NAME]_v1.4.md (речь по 14 уровням)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R5 Physiognomist│ → PHYSIOGNOMY_[NAME]_v1.md (anatomic_anchor, visuals)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R6 Architect    │ → [NAME]_MODULE_v2.3_COMPACT.md (9 блоков)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R7 Refactor     │ → personas/[name]/ (модульная JSON-структура)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R8 Auditor      │ → AUDIT_REPORT_[NAME].md (валидация)
└─────────────────┘
         │
         ▼
   Runtime: монофайл + PRELOAD + state → LLM-чат
         │
         ▼
   session_finalize.py → stories / visuals / state_update / memory_update
```

### 1.5. Инфраструктура

| Директория | Назначение | Ключевые файлы |
|------------|------------|----------------|
| `core/` | Baseline-таблицы, канонические значения | `VSCNO_BASELINE_TABLE.md`, `AD_AVAILABILITY_MATRIX.md`, `INTERNAL_STATE_BASELINE.md`, `MEMORY_BASELINE_TABLE.md` |
| `docs/` | Архитектура, спецификации, гайды | `01_MODULAR_ARCHITECTURE_v2.2.md`, `02_MODULE_SPECS_v2.2.md`, `03_ASSEMBLY_GUIDE_v2.1.md`, `VOYAGE_MASTER_DOCUMENT_v3.md` |
| `personas/` | Модули персонажей | `*.json` (runtime), `kira/` (модульная разработка) |
| `roles/` | Промпты LLM-ролей | `ROLE_1`…`ROLE_6` (готовы), `ROLE_7` (спецификация создана), `ROLE_8` (спецификация создана) |
| `scenarios/` | Сценарии runtime | `SCENARIO_*.json`, `SCENARIO_LIBRARY.json`, `SCENARIO_MATRIX.json` |
| `state/` | Стартовые state-шаблоны | `STATE_TEMPLATE_v2.json`, `WORKING.json` и др. |
| `sessions/` | Артефакты сессий | `raw/`, `state/`, `memory/`, `stories/`, `visuals/` |
| `schemas/` | JSON Schema | `persona_schema_v3_2_VOYAGE.json` |
| `knowledge/` | Cross-persona правила, TEC, схемы | `rules/CROSS_PERSONA_RULES.md`, `tec/TEC_DICTIONARY.md` |
| `governance/` | Safety, autonomy governor | `AUTONOMY_GOVERNOR*.md` |

### 1.6. Технический долг

| Долг | Описание | Статус |
|------|----------|--------|
| `tools/assemble.sh` | Ссылается на `core/VOYAGE_NARRATIVE_CORE.md`, `personas/KIRA_MODULE.json` — файлы перемещены/переименованы. | 🔴 Сломан |
| `build_prompt_v3.sh` | Ссылается на `personas/KIRA_MODULE_v12.json`, `personas/SERGEY_MODULE_v3.json` — не существуют. | 🔴 Сломан |
| `README.md` | Содержит устаревшие имена файлов (`KIRA_MODULE_v14.json`, `user_default.json`). | 🟡 Устарел |
| `personas/kira/` | Модульная структура не подключена к автоматической сборке runtime-промпта. | 🟡 В разработке |
| `ROLE_7` / `ROLE_8` | Спецификации созданы, требуют тестирования. | 🟡 В разработке |
| `PRELOAD_VNE_v3.2.1.md` | Отсутствует в корне. | 🟡 [NEEDS_DATA] |
| `SPEC_PART_1_2.md` / `SPEC_PART_3.md` | Исходные спецификации не найдены. | 🔴 Отсутствуют |

---

## 2. СТВОЛ 2: PERSONA PIPELINE

### 2.1. Общая схема

Каскадный pipeline создания персонажа: R1 собирает данные → R2–R5 анализируют параллельные аспекты → R6 собирает монолит → R7 разбивает на модули → R8 валидирует.

### 2.2. R1: Persona Interviewer v1.4

**Назначение:** Принимает свободное описание персонажа от разработчика, расширяет художественно, задаёт уточняющие вопросы. Только сбор данных, без психологического анализа.

**Вход:** Свободное текстовое описание + режим работы (A/B/C), возможен фото-референс.

**Выход:** `PORTRAIT_[NAME]_v1.4.md` — литературный портрет + сырые ответы + TEC-гипотезы (pending).

**Преобразование:** Неформальное описание → структурированный портрет.

**Формат:** Markdown.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_1_PERSONA_INTERVIEWER_v1.4_PROMPT.md`

**Статус:** ✅

### 2.3. R2: Persona Psychologist v1.4

**Назначение:** Аналитик базовой психологии. Строит психологический профиль, VSCNO, Internal State, АД-карту, memory baseline и safety-импликации.

**Вход:** `PORTRAIT_[NAME]_v1.4.md` + ответы разработчика + `STATE_TEMPLATE_v2.json` (опционально).

**Выход:** `PSYCHOLOGY_[NAME]_v1.4.md` — психологический профиль + baseline + адаптации + Confidence Matrix + CONFLICTS.

**Преобразование:** Портрет → психологические метрики и baseline.

**Формат:** Markdown + встроенные JSON-блоки.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_2_PERSONA_PSYCHOLOGIST_v1.4_PROMPT.md`

**Статус:** ✅

### 2.4. R3: Persona Sexologist v2.3

**Назначение:** Анализирует сексуальную психологию на основе данных R1–R2. Строит TEC-спецификацию (8/8), эротические сценарии, Shadow Desires, Aftercare-need.

**Вход:** `PORTRAIT_[NAME]_v1.4.md` + `PSYCHOLOGY_[NAME]_v1.4.md` + `TEC_DICTIONARY.md` + `CROSS_PERSONA_RULES.md`.

**Выход:** `SEXOLOGY_[NAME]_v1.md` + TEC-спецификация (8 JSON-структур) + рекомендации по VSCNO.

**Преобразование:** Психологический профиль → сексуальный профиль и TEC-механики.

**Формат:** Markdown + JSON.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_3_PERSONA_SEXOLOGIST_v2.3_PROMPT.md`

**Статус:** ✅

### 2.5. R4: Persona Linguist v1.3

**Назначение:** Строит речевой профиль: лексика, темп, интонация, манера речи по всем 14 подуровням (У1-А…У7-Б).

**Вход:** `PORTRAIT_[NAME]_v1.4.md` + `PSYCHOLOGY_[NAME]_v1.4.md` + `SEXOLOGY_[NAME]_v1.4.md` + `VOYAGE_NARRATIVE_CORE_v2.md`.

**Выход:** `LINGUISTICS_[NAME]_v1.4.md` — Speech Profile Matrix + примеры диалогов (ФМДР) + код-переключение.

**Преобразование:** Психология → речевая система.

**Формат:** Markdown.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_4_PERSONA_LINGUIST_v1.3_PROMPT.md`

**Статус:** ✅

### 2.6. R5: Persona Physiognomist v1.3

**Назначение:** Визуализатор. Строит Anatomic Anchor, Dynamic Visuals по 14 уровням, Lighting Map, Prompt Base + Variations, Anti-prompts, Generation History.

**Вход:** `PORTRAIT_[NAME]_v1.4.md` + `PSYCHOLOGY_[NAME]_v1.4.md` + `SEXOLOGY_[NAME]_v1.md` + `LINGUISTICS_[NAME]_v1.md` + `QWEN_ADAPTER_v2.md`.

**Выход:** `PHYSIOGNOMY_[NAME]_v1.md` — визуальный профиль + Anatomic Anchor JSON + Prompt Base + Lighting Map.

**Преобразование:** Психология/сексология/лингвистика → визуальные метрики.

**Формат:** Markdown + JSON.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_5_PERSONA_PHYSIOGNOMIST_v1.3_PROMPT.md`

**Статус:** ✅

### 2.7. R6: Modular Architect v2.3

**Назначение:** Синтезирует данные R1–R5 в единый токен-оптимизированный Markdown-файл персонажа по схеме 9 блоков (Pre-loaded Blocks).

**Вход:** PORTRAIT + PSYCHOLOGY + SEXOLOGY + LINGUISTICS + PHYSIOGNOMY + CORE-контекст.

**Выход:** `[NAME]_MODULE_v2.3_COMPACT.md` — COMPACT Markdown (~1500–2500 строк), оптимизированный для мобильного LLM.

**Преобразование:** Разрозненные аналитические файлы → единый runtime-монофайл.

**Формат:** COMPACT Markdown.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_6_MODULAR_ARCHITECT_v2.3.md`

**Статус:** ✅

### 2.8. R7: Refactor v1.0

**Назначение:** Разбиение монолитного модуля (9 блоков COMPACT) на модульную структуру `personas/[name]/` (16+ подпапок).

**Вход:** `[NAME]_MODULE_v[N].json` или `[NAME]_MODULE_v[N]_COMPACT.md` (монолит от R6).

**Выход:** `personas/[name]/` — структура папок с `INDEX.json`, `ASSEMBLY.md` и разбитыми блоками.

**Преобразование:** Монолит → модульная файловая система.

**Формат:** JSON + Markdown.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_7_REFACTOR_v1.0_PROMPT.md`

**Статус:** ⏳ (файл отсутствует, требуется создать)

### 2.9. R8: Auditor v1.0

**Назначение:** Проверка консистентности после миграции монолит → модули. Валидация против JSON Schema.

**Вход:** `personas/[name]/` (модульная структура) + `schemas/persona_schema_v3_2_VOYAGE.json` + оригинальный монолит.

**Выход:** `AUDIT_REPORT_[NAME].md` — VSCNO суммы (10), AD-консистентность, TEC-валидация, cross-persona sync, safety-протоколы.

**Преобразование:** Модульная структура → отчёт о валидации.

**Формат:** Markdown.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_8_AUDITOR_v1.0_PROMPT.md`

**Статус:** ⏳ (файл отсутствует, требуется создать)

---

## 3. СТВОЛ 3: SCENARIO PIPELINE

### 3.1. Назначение

Сценарий задаёт контекст runtime-сессии: локацию, фазы, триггеры, персонажей, recommended_ag_level и character_overrides. Сценарий — временный оверрайд над модулем персонажа.

### 3.2. Источники сценариев

| Источник | Назначение | Пример |
|----------|------------|--------|
| `scenarios/SCENARIO_LIBRARY.json` | Реестр сценариев с метаданными | `SC_003` «Тихий охотник в пустом зале» |
| `scenarios/SCENARIO_MATRIX.json` | Генеративная матрица параметров | location × time × archetype |
| `scenarios/SCENARIO_*.json` | Конкретные runtime-сценарии | `SCENARIO_SAUNA_QUARTET.json` |
| `scenarios/acts/` | Полные narrative act scripts | `ACT_2_BAR.md` |

### 3.3. Структура runtime-сценария

```json
{
  "scenario_id": "sauna_quartet",
  "recommended_ag_level": 2,
  "location": "sauna",
  "characters": ["kira", "sergey", "maksim", "marina"],
  "phases": {
    "P1_ENTRANCE": { "ag_level": 1 },
    "P2_STEAM": { "ag_level": 2 },
    "P5_CLIMAX": { "ag_level": 3 }
  },
  "character_overrides": {
    "kira": {
      "levels/U3-A.json": {
        "speech_profile.catchphrases": ["Ещё один? Я не выдержу..."]
      }
    }
  }
}
```

### 3.4. AD-матрица в сценарии

Каждая фаза сценария может активировать разрешённые для текущего уровня Алгоритмы Действий (АД). См. `core/AD_AVAILABILITY_MATRIX.md`.

| Подуровень | Доступные АД | Запрещённые АД |
|------------|-------------|----------------|
| У1-А | ПД, ПУ | ФС, ЛС, ПР |
| У2-Б | КН, ФС, ЛС | ПР, СЛ |
| У3-А | ПУ, ПД, СП | ПР, ФС |
| У3-Б | КН, ФС, ЛС, ПР | ПУ, ПД |
| У4-А | ФС, ЛС, ПР, СЛ | ПУ, ПД |
| У7-А | СЛ, ПР, ФС (нежный) | ПУ, ПД, ВС |

### 3.5. Триггеры и переходы уровней

- `state_triggers` в `levels/U*.json` определяют условия изменения `internal_state` и `vscno`.
- При одновременном срабатывании нескольких триггеров на одно поле применяется изменение с максимальным абсолютным значением.
- Переход между уровнями (У1-А → У7-Б) фиксируется `session_finalize.py` и записывается в `memory/HISTORY.json`.

### 3.6. State Manager

**Назначение:** Поддержание runtime-состояния между сессиями.

**Вход:** Сырой лог сессии (`sessions/raw/*.log`) + текущий `state/STATE.json` + persona-модуль.

**Выход:** `sessions/state/STATE_UPDATE_*.json` + обновлённые persona-модули + `memory/HISTORY.json` + `memory/FLAGS.json`.

**Преобразование:** Лог ФМДР → обновлённые метрики, флаги, история.

**Формат:** JSON.

**RAW-ссылка:** `https://raw.githubusercontent.com/AndreyVoyage/voyage-narrative-engine/main/roles/ROLE_STATE_MANAGER_v1.0_PROMPT.md`

**Статус:** ✅

### 3.7. Runtime-файл

Финальный файл, загружаемый в LLM-чат:

1. `PRELOAD_VNE_v3.2.1.md` — системный контекст (отсутствует в репозитории, `[NEEDS_DATA]`).
2. Собранный монофайл персонажа (JSON или COMPACT Markdown).
3. Сценарий (`scenarios/SCENARIO_*.json` или `.md`).
4. State (`state/STATE_TEMPLATE_v2.json` или `sessions/state/STATE_UPDATE_*.json`).

---

## 4. СТВОЛ 4: NARRATIVE PIPELINE

> **Статус:** ✅ Заполнен на основе встроенных данных (`PROMPT_E5_E6_VSCODE.md`).

### 4.1. Формат ФМДР (Мысли / Действия / Речь)

**Канонический формат:**
```
**Мысль:** [1-2 предложения, короткие, только для связи с психологией R2]
**Действие:** [физика, микроэкспрессии, осанка, движение, дыхание — визуально наблюдаемое]
**Речь:** «[текст на русском, в кавычках-ёлочках]»
```

**Критические правила:**
- Мысли — не психологический анализ (R2 = длинные мысли, R4 = короткие 1-2 предложения).
- Действия — нет внутренних состояний ("он нервничал" → "пальцы сжались, дыхание сбилось").
- Речь — в кавычках-ёлочках «» (Qwen/Llama держат формат лучше).
- На пике (У5-А) мысль = 1 слово или отсутствует (сознание перегружено).

**Few-shot примеры (Андрей Старший):**

**У2-А (бар, ревность):**
> **Мысль:** Они не знают, что я вижу.  
> **Действие:** Сидит за столом, глаза на девушках, но незаметно. Поправляет рукава. Улыбка — защитная.  
> **Речь:** «Ну что, ребята, всё нормально. Посмотрим, куда вечер заведёт. А ты смелая? Не переживай, я рядом.»

**У4-А (перелом, страсть):**
> **Мысль:** Они обе здесь. Я между ними. И я не контролирую.  
> **Действие:** Руки тянутся к обеим, но неуверенно. Впервые — без плана. Дыхание ускоряется.  
> **Речь:** «[нет слов, только дыхание, шёпот] Вы... вы обе... я... не могу... это не я... это...»

**У5-А (пик, без слов):**
> **Мысль:** Мы.  
> **Действие:** Прижимается к обеим. Дыхание прерывистое. Впервые без слов — только дыхание, стоны.  
> **Речь:** «[дыхание, шёпот, стоны] Вы... вы... я... не могу... это...»

**У7-А (aftercare, кухня):**
> **Мысль:** Боюсь расстроить Киру. Боюсь, что Марина — лишняя. Нет. Я — нужен.  
> **Действие:** Встаёт тихо, идёт на кухню. Готовит яичницу. Мясо с салатом. Для всех.  
> **Речь:** «[на кухне, тихо] Всё нормально. Я рядом. Яичница, мясо с салатом. Для всех.»

**Структура ФМДР по подуровням:**

| У | Мысль | Действие | Речь |
|---|-------|----------|------|
| У1-А | 1 предл., наблюдение | Минимальное, защитное позирование | Минимальная / молчание |
| У1-Б | 1-2 предл., проверка | Микро-движения, улыбка | Вопросы-проверки, флирт |
| У2-А | 1-2 предл., анализ | Средние, скрытое наблюдение | Философия + забота |
| У2-Б | 1-2 предл., игра | Средние, касание | Игровые вопросы, двойные смыслы |
| У3-А | 2-3 предл., ревность/тревога | Средние, скрытое возбуждение | Напряжённая, скрытая |
| У3-Б | Может отсутствовать (диссоциация) | Замирание, отвод взгляда | Философский щит, отстранение |
| У4-А | 2 предл., потеря контроля | Активные, неуверенные | Рваная, неполная, шёпот |
| У4-Б | 2 предл., забота + тревога | Осторожные, касания | Нежная, осторожная |
| У5-А | 1 слово / отсутствует | Максимальные, страсть | Дыхание, стоны, шёпот |
| У5-Б | 2-3 предл., фантазия | Минимальные, лежит, думает | Мечтательная, мягкая |
| У6-А | 2-3 предл., пустота/тревога | Минимальные, лежит | Тихая, задумчивая, философская |
| У6-Б | 2 предл., ожидание | Минимальные, слушает | Тревожная, с паузами |
| У7-А | 2-3 предл., забота | Средние, готовка, действия | Тихая, утилитарная, присутствие |
| У7-Б | 3-4 предл., открытость | Средние, близость, оставаться | Честная, впервые без фасада |

### 4.2. Якорная система (Character Anchor + Visual Signature)

**Два уровня:**

| Уровень | Название | Что это | Формат |
|---------|----------|---------|--------|
| **L1** | **Character Anchor** (Anatomic Anchor) | ДНК лица и тела. Неизменные черты. | JSON (10+ параметров) |
| **L2** | **Visual Signature** | Компактная строка для промптов. | String (100-200 слов) |

**Character Anchor JSON (обязательные блоки):** `face_shape`, `forehead`, `chin`, `overall`, `eyes` (color, shape, gaze, signature, pupil_dynamics), `nose` (shape, signature, dynamics), `lips` (shape, signature, resting, dynamics, speech), `skin` (tone, texture, dynamics, age_marks, sweat), `hair` (color, style, texture, facial_hair), `body` (height, weight, type, build, posture), `signature_items`.

**Пример Visual Signature (Андрей):**
```
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense evenly trimmed hair, 
bright blue almond wide-set eyes with warm observant gaze, strong square jaw with visible 
muscle definition, medium-high broad cheekbones, gentle closed-mouth smile left corner 
slightly higher, medium-full soft lips, fair warm skin with slight weathered texture, 
thick neck powerful chest broad shoulders, clean-shaven, expensive watch
```

**Dynamic Visuals (14 подуровней × 7 параметров):** `clothing`, `posture`, `micro_expression`, `lighting`, `blush` [0-4], `sweat` [0-4], `pupils` (текстовое описание).

**Примеры:**

| Подуровень | clothing | posture | micro_expression | lighting | blush | sweat | pupils |
|------------|----------|---------|------------------|----------|-------|-------|--------|
| У2-А | blue_shirt_jeans_watch | sits_adjusts_sleeves_nervous | observant_hidden_jealousy_eyelids_raised | spotlight_dark | 0 | 0 | normal_scanning |
| У4-А | shirt_on_shoulders_torse | bewildered_hands_reach_uncertainly | breakthrough_eyes_wide_mix_fear_passion | dramatic_side_Rembrandt | 3 | 1 | dilated_stunned |

### 4.3. Stop-Frame Engineer (SFE)

**Stop-Frame** = "замороженный кадр" для генерации изображения. Частота: каждые 3-5 ходов или на триггерные моменты.

**Структура (4 блока):**

| Блок | Что содержит | Откуда | Формат |
|------|-------------|--------|--------|
| **ANCHOR** | Visual Signature + текущая одежда | visual_signature_string + dynamic_visuals.clothing | String |
| **SCENE** | Осанка + микроэкспрессия + освещение | dynamic_visuals.posture + micro_expression + lighting | String |
| **BACKGROUND** | Локация + атмосфера + время | scenario.location + atmosphere | String |
| **TECHNICAL** | Числовые параметры + стиль + ракурс | blush + sweat + pupils + CFG/Steps | String + JSON |

**Пример (Андрей, У2-А, бар):**
```markdown
## STOP-FRAME: ANDREY_U2A_BAR
**Turn:** 3 | **Trigger:** gaze_3sec_kira

### ANCHOR
handsome athletic man 38yo... (Visual Signature) + blue shirt unbuttoned at collar, jeans, watch visible

### SCENE
sits at bar table, left hand adjusts sleeve nervously, eyes fixed on Kira, observant hidden jealousy, warm spotlight from above, dark corners

### BACKGROUND
upscale bar, evening, warm amber lighting, blurred crowd, wooden surfaces, glass reflections, soft bokeh

### TECHNICAL
blush: 0, sweat: 0, pupils: normal_scanning, CFG: 7, Steps: 30, Sampler: DPM++ 2M Karras, Style: photorealistic, RAW photo, 35mm, Angle: medium shot, eye level, Negative: cartoon, anime, 3d render, painting, ugly, deformed hands
```

### 4.4. Компрессия и память в runtime

**Проблема:** 200K токенов Kimi. Полный модуль = ~5000 токенов. Модуль + PRELOAD + история = переполнение.

**Решение: 3 слоя динамического контекста:**

```
[СЛОЙ 1: BASE] — неизменный, ~500 токенов
├── PRELOAD_BASE.md (системные команды, safety, формат ФМДР)

[СЛОЙ 2: STATE] — меняется при смене U-X, ~300-500 токенов
├── Текущий подуровень (U-X): VSCNO + AD + Internal State + Speech Profile
├── Соседний подуровень (U-X±1): только триггеры перехода

[СЛОЙ 3: LIVE] — меняется каждый ход, ~500-1000 токенов
├── Активные emotional anchors (count > 0)
├── Текущие relationships (trust/attraction)
├── История: последние 3-5 ходов (raw) или summary (если >5)

ИТОГО: ~1600 токенов. Запас: ~400 под ответ LLM.
```

**Механизм `/checkpoint`:**
- Каждые 5-10 ходов или при переходе локации/U-X.
- Сжимает историю в summary (2-3 предложения).
- Обновляет emotional anchors: `count +1` за упоминание, кратно 5 → `intensity +1`.
- Обновляет relationships и флаги memory.
- Вставляет summary в PRELOAD (заменяет старую историю).

**Механизм `/finalize`:**
- Сжимает всю сессию в handoff-документ.
- Обновляет модуль персонажа (memory, relationships, emotional anchors).
- Создаёт `SCENARIO_ARCHIVE.json`.

### 4.5. Пользовательские команды

| Команда | Действие |
|---------|----------|
| `У3-А`, `У4-Б` | Принудительно установить уровень персонажа |
| `ТГ1`, `ТГ2`, `ТГ3` | Переключить Три Грани (sterva / devotion / passion) |
| `АД КН`, `АД ПР` | Активировать Алгоритм Действий |
| `СТОП`, `ХВАТИТ`, `КРАСНАЯ КАРТОЧКА` | Экстренная деэскалация до U7 / остановка |
| `/checkpoint` | Сохранить текущее состояние и сжать историю |
| `/finalize` | Завершить сессию и запустить финализацию |

---

## 5. ГЛОССАРИЙ

| Термин | Описание |
|--------|----------|
| **VSCNO** | Четыре оси состояния: ВЛ (Веселье), СТ (Сосредоточенность), НЖ (Негатив), ОГ (Общность). Сумма = 10, каждая ось ∈ [0, 4]. |
| **АД** | Алгоритм Действий. Коды: ФС, ЛС, СП, СЛ, КН, ПД, ДР, ПУ, ПР, ВС. |
| **ФМДР** | Формат Мысли-Действия-Речь: `(Мысли: …) → *Действия: …* → «Речь: …»`. |
| **TEC** | Техника Эротической Коммуникации. 8 механик (`TEC_001`–`TEC_008`), описанных в `knowledge/tec/TEC_DICTIONARY.md`. |
| **9 блоков** | Структура COMPACT-монофайла от R6: Б0 Identity, Б1 Levels, Б2 Psychology, Б3 Sexology, Б4 Visual, Б5 Dynamics, Б6 Memory, Б7 Relationships, Б8 Environment. |
| **6 компрессоров** | Методы сжатия данных в COMPACT: `_linear_table`, `_base_delta`, `_glossary`, `_trigger_map`, `_voice_sample`, `_visual_tag`. |
| **anatomic_anchor** | Непизменные визуальные признаки лица/тела для консистентной генерации изображений. |
| **ag_level** | Глубина сборки персонажа: 1 базовая, 2 продвинутая, 3 полная. |
| **У1-А … У7-Б** | 14 эмоциональных подуровней Киры. У1 = защита, У4 = принятие, У7 = интеграция. |
| **ТГ1–ТГ3** | Три Грани Киры: стерва / преданность / страсть. |
| **Stop-Frame** | Визуальный кадр из сценария: ANCHOR + SCENE + BACKGROUND + TECHNICAL. |
| **Character Anchor** | ДНК лица и тела персонажа. Неизменные черты в JSON (L1 якорной системы). |
| **Visual Signature** | Компактная строка 100–200 слов для промптов генерации изображений (L2 якорной системы). |
| **Dynamic Visuals** | 14 подуровней × 7 параметров (clothing, posture, micro_expression, lighting, blush, sweat, pupils). |
| **`/checkpoint`** | Runtime-команда для сжатия истории и обновления emotional anchors. |
| **`/finalize`** | Runtime-команда для завершения сессии и создания handoff-документа. |
| **IFS** | Internal Family Systems — модель частей личности (manager / exile / firefighter / self). |

---

## 6. DECISION LOG

| Дата | Решение | Обоснование | Статус |
|------|---------|-------------|--------|
| 2026-06-08 | Модульная архитектура персонажей | Снижение перегрузки контекста LLM, изоляция изменений | ✅ Принято |
| 2026-06-08 | Две параллельные системы (монолит + модули) | Монолиты нужны для runtime, модули — для разработки | 🟡 Переходный период |
| 2026-06-08 | VSCNO шкала [0, 4] | Баланс точности и простоты для LLM | ✅ Канон |
| 2026-06-08 | 14 подуровней (У1-А…У7-Б) | Достаточная гранулярность для психологических переходов | ✅ Канон |
| 2026-06-08 | ag_level ∈ {1, 2, 3} | Контроль глубины контекста по типу сцены | ✅ Канон |
| 2026-06-08 | `session_finalize.py` — stdlib only | Простота деплоя в Termux / без пакетного менеджера | ✅ Канон |
| 2026-06-17 | Создание `VOYAGE_ARCHITECTURE_SPEC_v1.0.md` | `SPEC_PART_1_2.md` и `SPEC_PART_3.md` отсутствуют | ✅ Выполнено |
| 2026-06-17 | Дополнение Ствола 4 (Narrative Pipeline) | Получены данные ФМДР, якорной системы, Stop-Frame, runtime-компрессии | ✅ Выполнено |

---

## 7. СТАТУСЫ КОМПОНЕНТОВ

| Компонент | Статус | Файл | Примечание |
|-----------|--------|------|------------|
| System Tree | ✅ | `VOYAGE_ARCHITECTURE_SPEC_v1.0.md` | Собран из `docs/` и `core/` |
| Persona Pipeline R1–R6 | ✅ | `roles/ROLE_1*` … `ROLE_6*` | Готовы к использованию |
| Persona Pipeline R7 | ⏳ | `roles/ROLE_7_REFACTOR_v1.0_PROMPT.md` | Спецификация создана, требует тестирования |
| Persona Pipeline R8 | ⏳ | `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md` | Спецификация создана, требует тестирования |
| Scenario Pipeline | ✅ | `scenarios/SCENARIO_LIBRARY.json` + `SCENARIO_*.json` | Активные сценарии есть |
| State Manager | ✅ | `roles/ROLE_STATE_MANAGER_v1.0_PROMPT.md` + `session_finalize.py` | Работает |
| Narrative Pipeline | ✅ | `VOYAGE_ARCHITECTURE_SPEC_v1.0.md` | Ствол 4 заполнен |
| PRELOAD VNE v3.2.1 | 🔍 | `PRELOAD_VNE_v3.2.1.md` | `[NEEDS_DATA]` |
| VSCNO Baseline | ✅ | `core/VSCNO_BASELINE_TABLE.md` | Канон [0, 4] |
| AD Availability Matrix | ✅ | `core/AD_AVAILABILITY_MATRIX.md` | Канон |
| Internal State Baseline | ✅ | `core/INTERNAL_STATE_BASELINE.md` | Канон |
| Memory Baseline Table | ✅ | `core/MEMORY_BASELINE_TABLE.md` | Канон |
| Build Scripts | 🔴 | `tools/assemble.sh`, `build_prompt_v3.sh` | Сломаны, ссылки устарели |
| README.md | 🟡 | `README.md` | Дисклеймер добавлен, контент устарел |

---

## 8. ИЗВЕСТНЫЕ КОНФЛИКТЫ

| Конфликт | Место | Описание | Рекомендация |
|----------|-------|----------|--------------|
| `C1` | `README.md` vs `AGENTS.md` | README ссылается на `KIRA_MODULE_v14.json`, `user_default.json`, `VOYAGE_NARRATIVE_CORE_v2.md` — файлы отсутствуют или переименованы. | Не использовать README как источник архитектуры; приоритет `AGENTS.md`. |
| `C2` | `roles/ROLE_3*`, `ROLE_4*`, `ROLE_5*` | Промпты ссылаются на `VOYAGE_NARRATIVE_CORE_v2.md` и `QWEN_ADAPTER_v2.md`, которых нет в корне / по указанным путям. | `[NEEDS_DATA]` — либо восстановить файлы, либо обновить ссылки. |
| `C3` | `VSCNO` | В `state/STATE_TEMPLATE_v2.json` и модулях используется шкала [0, 4], но в некоторых legacy-файлах может встречаться [0, 10]. | При миграции приводить к [0, 4]. |
| `C4` | Роли R3/R4/R5 | Указаны входные версии Р1–Р5, которые не соответствуют актуальным (например, Р3 v2.2 vs v2.3, Р4 v1.2 vs v1.3). | Привести ссылки в промптах к актуальным версиям. |
| `C5` | Build scripts | `tools/assemble.sh` и `build_prompt_v3.sh` ссылаются на несуществующие пути. | Починить или пометить как legacy. |

---

*Спецификация создана: 2026-06-17.*
*Версия: 1.0.0.*
*Основа: `docs/01_MODULAR_ARCHITECTURE_v2.2.md`, `02_MODULE_SPECS_v2.2.md`, `03_ASSEMBLY_GUIDE_v2.1.md`, `10_STATE_SPECIFICATION.md`, `11_MEMORY_SPECS.md`, `core/*`, `roles/ROLE_1*`–`ROLE_6*`.*
