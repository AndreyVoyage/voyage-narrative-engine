# 📖 GLOSSARY VNE v2.1.0
## Voyage Narrative Engine — Единый словарь терминов
### Diátaxis Type: Reference | Compatible: VNE v2.1.0+

---

## 📋 СОДЕРЖАНИЕ

**Быстрый поиск:** Нажмите `Ctrl+F` и введите термин.

- [A](#a)
- [B](#b)
- [C](#c)
- [D](#d)
- [E](#e)
- [F](#f)
- [G](#g)
- [H](#h)
- [I](#i)
- [K](#k)
- [L](#l)
- [M](#m)
- [N](#n)
- [O](#o)
- [P](#p)
- [R](#r)
- [S](#s)
- [T](#t)
- [U](#u)
- [V](#v)
- [W](#w)
- [Y](#y)
- [Ф](#ф)

---

## A

### **ACTIVE_STATE**
JSON-блок, который Prompt Architect выводит в каждом ответе. Содержит `project_id`, `current_task`, `progress`, `validation_status`, `warnings`, `next_phase`. Позволяет отслеживать состояние работы и возобновлять после чекпоинта.

> *См. также:* [CHECKPOINT](#checkpoint), [Prompt Architect](#prompt-architect)

### **AG (Arousal Gradient)**
Градиент возбуждения. Шкала от 1 до 5, определяющая интенсивность сценария. Используется в `safety.ag_max` для ограничения максимального уровня персонажа.

> *См. также:* [safety](#safety), [intensity](#intensity)

### **anatomic_anchor**
Визуальный якорь, гарантирующий консистентность лица персонажа при генерации изображений. Содержит `face_shape`, `eyes`, `nose`, `lips`, `jaw`, `visual_signature` (итоговая строка для промпта, ≤500 символов).

> *См. также:* [visual_data](#visual_data), [Visual Physiognomist](#visual-physiognomist)

### **attachment_sexuality**
Психологический блок модуля персонажа, основанный на теории Бирнбаума. Определяет стиль привязанности (`anxious`, `avoidant`, `disorganized`, `secure`) и его проявления в сексуальном поведении.

> *См. также:* [Birnbaum](#birnbaum), [psychology](#psychology)

### **AUDIT**
Режим работы Prompt Architect или Documentation Architect. Проверка существующего файла на соответствие стандартам: JSON Schema, VSCNO, Level Lock Matrix, Safety Protocols, читаемость.

> *См. также:* [Prompt Architect](#prompt-architect), [Documentation Architect](#documentation-architect)

---

## B

### **Basson (Responsive Desire)**
Теория Розмари Бассон. **Responsive Desire** — желание, которое возникает в ответ на стимул, а не спонтанно. В VNE используется для моделирования женских персонажей: `baseline_state` → `trigger_condition` → `active_mode`.

> *См. также:* [responsive_desire](#responsive_desire), [TEC](#tec)

### **Baumeister (Erotic Plasticity)**
Теория Роя Баумейстера. **Erotic Plasticity** — способность эротического поведения адаптироваться к социальным, культурным и психологическим факторам. В VNE: `level` (0-10), `scripts` (сценарии поведения).

> *См. также:* [erotic_plasticity](#erotic_plasticity), [TEC](#tec)

### **Birnbaum**
Теория привязанности и сексуальности (Attachment × Desire). В VNE используется в блоке `attachment_sexuality`. Ключевые концепции: `reassurance_seeking`, `emotional_closeness`, `intimacy_avoidance`.

> *См. также:* [attachment_sexuality](#attachment_sexuality), [TEC](#tec)

---

## C

### **CHECKPOINT**
Протокол сохранения прогресса при работе с большими файлами (>50KB). Содержит `completed_sections`, `pending_sections`, `partial_output`. Позволяет возобновить работу в новом чате.

> *См. также:* [ACTIVE_STATE](#active_state), [Hierarchical Memory](#hierarchical-memory)

### **Chivers (Arousal Specificity)**
Теория Мередит Чиверс. **Arousal Specificity** — разрыв между физиологической готовностью и субъективным желанием. В VNE: `physiological_readiness` vs `subjective_desire`.

> *См. также:* [arousal_specificity](#arousal_specificity), [TEC](#tec)

### **Context Folding**
Технология делегирования под-задач в Prompt Architect. Симуляция "sub-agents" (Psychologist, Physiognomist, Narrative Designer), каждый из которых видит только необходимые данные. Предотвращает перегрузку контекста.

> *См. также:* [Prompt Architect](#prompt-architect), [Hierarchical Memory](#hierarchical-memory)

### **core_conflict**
Центральный психологический конфликт персонажа. Формат: `disciplined_teacher_vs_wounded_dancer`. Определяет архетип поведения и траекторию развития через уровни.

> *См. также:* [psychology](#psychology), [trauma_anchor](#trauma_anchor)

### **Cross-Persona Consistency**
Проверка консистентности между модулями персонажей. Убеждается, что взаимодейные отношения, уровни и флаги согласованы между всеми участниками сцены.

> *См. также:* [cross_persona_sync](#cross_persona_sync), [AUDIT](#audit)

### **cross_persona_sync**
Блок модуля персонажа, содержащий `level_lock_matrix` — матрицу блокировки уровней для пар персонажей. Определяет, какие уровни доступны при взаимодействии с конкретным партнёром.

> *См. также:* [level_lock_matrix](#level_lock_matrix), [Cross-Persona Consistency](#cross-persona-consistency)

---

## D

### **desire**
Метрика внутреннего состояния персонажа. Шкала 0-10. Отражает силу сексуального/эмоционального желания. Изменяется динамически в процессе сессии.

> *См. также:* [internal_state](#internal_state), [anxiety](#anxiety)

### **desire_tension**
Метрика внутреннего состояния. Шкала 0-10. Отражает напряжение между желанием и сопротивлением (когнитивный диссонанс).

> *См. также:* [internal_state](#internal_state), [frustration](#frustration)

### **Diátaxis Framework**
Методология классификации документации на 4 типа: **Tutorial** (обучение), **How-To Guide** (задача), **Explanation** (понимание), **Reference** (справка). Documentation Architect использует для определения структуры документа.

> *См. также:* [Documentation Architect](#documentation-architect), [5Cs+U](#5csu)

### **Documentation Architect (DOC-ARCH)**
Роль для LLM, созданная для создания, аудита и оптимизации документации VNE. Использует Diátaxis, 5Cs+U, Flesch-Kincaid, Plain Language, Scannability Engineering. НЕ ведёт ролевой диалог.

> *См. также:* [Prompt Architect](#prompt-architect), [USER_GUIDE](#user_guide)

### **dynamic_visuals**
Блок модуля персонажа, описывающий внешность персонажа на каждом уровне (У1-А…У7-Б). Позволяет LLM генерировать визуальные описания, соответствующие текущему психологическому состоянию.

> *См. также:* [visual_data](#visual_data), [У-уровни](#у-уровни)

---

## E

### **erotic_plasticity**
Блок модуля персонажа, основанный на теории Баумейстера. `level` (0-10) — степень пластичности. `scripts` — сценарии поведения, которые персонаж может адаптировать.

> *См. также:* [Baumeister](#baumeister), [psychology](#psychology)

---

## F

### **Flesch-Kincaid**
Метрика читаемости текста. **Grade Level** — школьный класс, необходимый для понимания. **Reading Ease** — лёгкость чтения (0-100). Documentation Architect использует для аудита документов.

| Тип документа | Grade Level | Reading Ease |
|---------------|-------------|--------------|
| Гайд пользователя | ≤ 10 | 60–70 |
| Роль для LLM | 10–12 | 50–60 |
| README | ≤ 8 | 60–80 |
| Спецификация | 12–14 | 40–50 |

> *См. также:* [Plain Language](#plain-language), [Documentation Architect](#documentation-architect)

### **FMDR (ФМДР)**
Формат вывода LLM при игровой сессии: **(Мысли)** → _Действия_ → «Речь». Структурирует ответ, разделяя внутренний монолог, физические действия и диалог.

> *См. также:* [Unified Prompt Assembly](#unified-prompt-assembly), [scenario](#scenario)

### **frustration**
Метрика внутреннего состояния. Шкала 0-10. Отражает уровень фрустрации персонажа (например, от неудовлетворённого желания или внешнего сопротивления).

> *См. также:* [internal_state](#internal_state), [desire_tension](#desire_tension)

---

## G

### **generation_history**
Массив в блоке `visual_data`, заполняемый после каждой генерации изображения. Содержит `prompt`, `tool`, `date`, `result_quality`. Гарантирует консистентность при повторной генерации.

> *См. также:* [visual_data](#visual_data), [anatomic_anchor](#anatomic_anchor)

---

## H

### **hard_limits**
Массив в блоке `safety`. Содержит абсолютные запреты для персонажа (например, `["насилие", "принуждение", "публичное унижение"]`). LLM НЕ может нарушать hard_limits ни при каких обстоятельствах.

> *См. также:* [safety](#safety), [soft_limits](#soft_limits), [stop_words](#stop_words)

### **Hierarchical Memory**
Технология управления контекстом в Prompt Architect. 3 уровня: **Level 1** (Static Core, ~2K tokens), **Level 2** (Active Project, ~3K tokens), **Level 3** (Reference Library, lazy load, 0-15K tokens).

> *См. также:* [Prompt Architect](#prompt-architect), [Prompt Caching](#prompt-caching)

---

## I

### **intensity**
Интенсивность сценария. Шкала 1-10. Определяет темп развития событий, глубину раскрытия персонажей и психологическую нагрузку. НЕ путать с `ag_level`.

> *См. также:* [AG](#ag-arousal-gradient), [scenario](#scenario)

### **internal_state**
Блок модуля персонажа с 4 метриками: `desire`, `anxiety`, `desire_tension`, `frustration`. Каждая — шкала 0-10. Обновляется динамически в процессе сессии.

> *См. также:* [desire](#desire), [anxiety](#anxiety), [desire_tension](#desire_tension), [frustration](#frustration)

---

## K

### **Kimi**
Рекомендуемая LLM для VNE. Контекст 200K tokens. Оптимальна для загрузки больших модулей персонажей и длинных сессий. Альтернативы: DeepSeek, Claude, GPT-4o.

> *См. также:* [LLM](#llm), [context](#context)

---

## L

### **LAZY LOAD**
Механизм загрузки reference-данных по требованию. Команды формата `[LOAD:example_olga]` загружают шаблоны и примеры в Level 3 памяти Prompt Architect.

> *См. также:* [Hierarchical Memory](#hierarchical-memory), [Prompt Architect](#prompt-architect)

### **level_lock_matrix**
Матрица в `cross_persona_sync`, определяющая доступные уровни для пар персонажей. Формат: `{ "Ольга_Андрей": { "max_level": "У5-Б", "min_level": "У1-А", "blocked": ["У6-А", "У7-Б"] } }`.

> *См. также:* [cross_persona_sync](#cross_persona_sync), [У-уровни](#у-уровни)

### **level_system**
Система уровней персонажа. Для VNE v2.1.0 используется **У-система** (У1-А…У7-Б). Старые версии использовали Y-систему (устарела).

> *См. также:* [У-уровни](#у-уровни), [Y-уровни](#y-уровни)

### **LLM**
Large Language Model — большая языковая модель (Kimi, DeepSeek, Claude, GPT-4o). VNE использует LLM для игровых сессий, финализации и ролевых задач.

> *См. также:* [Kimi](#kimi), [Unified Prompt Assembly](#unified-prompt-assembly)

---

## M

### **MIGRATE**
Режим работы Prompt Architect. Перенос файла с одной версии на другую (например, с v2.0 на v2.1.0). Включает изменение `level_system`, `compatible_vne`, структуры JSON.

> *См. также:* [Prompt Architect](#prompt-architect), [compatible_vne](#compatible_vne)

### **MODULE**
JSON-файл, описывающий персонажа. Содержит: `id`, `name`, `psychology`, `speech_profile`, `visual_data`, `safety`, `vscno`, `internal_state`, `cross_persona_sync`. Название: `[NAME]_MODULE_v[N].json`.

> *См. также:* [persona](#persona), [Prompt Architect](#prompt-architect)

---

## N

### **Narrative Editor**
Роль для LLM в VNE. Превращает сырые логи сессии (ФМДР-формат) в литературный Markdown-рассказ. НЕ предназначен для создания документации.

> *См. также:* [Session Finalizer](#session-finalizer), [ФМДР](#фмдр)

---

## O

### **ОГ (Ощущение Границ)**
Компонента VSCNO. Шкала 0-4. Отражает чувство безопасности, границ, контроля над ситуацией. Высокое ОГ = персонаж чувствует себя в безопасности.

> *См. также:* [VSCNO](#vscno), [ВЛ](#вл)

---

## P

### **persona**
Персонаж VNE. Полностью описывается MODULE (JSON-файлом). Содержит психологический профиль, речевой профиль, визуальные данные, safety-протоколы.

> *См. также:* [MODULE](#module), [Prompt Architect](#prompt-architect)

### **Plain Language**
Подход к написанию документации: активный залог, простые слова, короткие предложения (≤20 слов), короткие абзацы (≤5 предложений). Documentation Architect использует для аудита.

> *См. также:* [Flesch-Kincaid](#flesch-kincaid), [Documentation Architect](#documentation-architect)

### **Prompt Architect (PROMPT-ARCH)**
Роль для LLM, созданная для создания, редактирования и аудита файлов VNE: модули персонажей, сценарии, STATE-шаблоны, документация. НЕ ведёт ролевой диалог.

> *См. также:* [Documentation Architect](#documentation-architect), [USER_GUIDE](#user_guide)

### **Prompt Caching**
Технология кэширования статических частей промпта в Prompt Architect. Экономит токены при длинных сессиях. Статические части (правила, шаблоны) не пересылаются повторно.

> *См. также:* [Hierarchical Memory](#hierarchical-memory), [Prompt Architect](#prompt-architect)

### **psychology**
Блок модуля персонажа, содержащий психологический профиль: `core_conflict`, `secret_desire`, `shame_layers`, `trauma_anchor`, `responsive_desire`, `attachment_sexuality`, `arousal_specificity`, `erotic_plasticity`.

> *См. также:* [MODULE](#module), [TEC](#tec)

---

## R

### **RAG (Retrieval-Augmented Generation)**
Технология поиска по reference в Prompt Architect. Эмулируется через keyword-matching в загруженных модулях. При создании нового персонажа ищет похожие паттерны в существующих.

> *См. также:* [Prompt Architect](#prompt-architect), [LAZY LOAD](#lazy-load)

### **responsive_desire**
Блок модуля персонажа, основанный на теории Бассон. Описывает "responsive desire" — желание, возникающее в ответ на стимул. `active_mode`, `applicable_levels`, `baseline_state`, `trigger_condition`.

> *См. also:* [Basson](#basson), [psychology](#psychology)

---

## S

### **safety**
Блок модуля персонажа, содержащий протоколы безопасности: `stop_words`, `default_mode`, `hard_limits`, `soft_limits`, `safety_check_points`, `ag_max`.

> *См. также:* [hard_limits](#hard_limits), [soft_limits](#soft_limits), [stop_words](#stop_words)

### **safety_check_points**
Массив уровней в `safety`, при достижении которых LLM должна проверить согласие и комфорт. Обычно: `["У3-Б", "У5-А", "У6-Б", "У7-Б"]`.

> *См. также:* [safety](#safety), [У-уровни](#у-уровни)

### **scenario**
Файл сценария (JSON или YAML). Содержит: `scenario_id`, `ag_level`, `intensity`, `location`, `time`, `characters`, `acts` (Prologue, Act I, Act II, Act III, Epilogue).

> *См. также:* [SCENARIO](#scenario), [Session Finalizer](#session-finalizer)

### **SCENARIO**
Сценарий VNE. Определяет локацию, время, участников, арки развития и уровни для каждого персонажа. Название: `SC_[NAME]_v[N].json`.

> *См. также:* [scenario](#scenario), [Prompt Architect](#prompt-architect)

### **Scannability Engineering**
Подход к созданию документации, ориентированный на "сканирование" текста вместо чтения. Инструменты: информативные заголовки, front-loaded paragraphs, списки, таблицы, white space, TOC.

> *См. также:* [Documentation Architect](#documentation-architect), [Plain Language](#plain-language)

### **secret_desire**
Блок в `psychology`. Содержит `surface` (видимое желание) и `shadow` (подсознательное/скрытое желание). Определяет мотивацию персонажа.

> *См. также:* [psychology](#psychology), [core_conflict](#core_conflict)

### **sensory_register**
Параметр в `psychology`. Определяет доминантный канал восприятия персонажа: `tactile` (тактильный), `visual` (визуальный), `olfactory` (обонятельный), `auditory` (слуховой).

> *См. также:* [psychology](#psychology), [state_triggers](#state_triggers)

### **session_finalize.py**
Python-скрипт для автоматической финализации сессии. Принимает `--log` и `--scenario`. Создаёт 4 артефакта: STATE, memory, story, visuals. Работает на стандартной библиотеке Python.

> *См. также:* [Session Finalizer](#session-finalizer), [Termux](#termux)

### **Session Finalizer**
Роль/скрипт для финализации игровой сессии. Включает: State Manager, Narrative Editor, Visual Extractor, Visual Physiognomist. Результат: 4 файла + обновлённые модули.

> *См. также:* [session_finalize.py](#session_finalizepy), [Narrative Editor](#narrative-editor)

### **soft_limits**
Массив в `safety`. Содержит гибкие запреты, которые персонаж может преодолеть при определённых условиях (высокий trust, explicit consent). Например: `["публичные места", "грубая лексика"]`.

> *См. также:* [safety](#safety), [hard_limits](#hard_limits)

### **speech_profile**
Блок модуля персонажа, описывающий речь на каждом уровне (У1-А…У7-Б). Каждый уровень содержит: `tone`, `pace`, `vocabulary`, `catchphrases`. Должно быть ≥ 14 подуровней.

> *См. также:* [У-уровни](#у-уровни), [MODULE](#module)

### **STATE**
JSON-файл, описывающий текущее состояние сессии. Содержит: `session_id`, `scenario_id`, `ag_level`, `intensity`, `characters` (текущие уровни, метрики, флаги), `scenario_flags`.

> *См. также:* [State Manager](#state-manager), [session_finalize.py](#session_finalizepy)

### **State Manager**
Роль для LLM в VNE. Парсит лог сессии, определяет подуровни (У1-А…У7-Б), обновляет `desire`/`anxiety`, фиксирует флаги, проверяет `vscno=10`.

> *См. также:* [STATE](#state), [Session Finalizer](#session-finalizer)

### **state_triggers**
Блок модуля персонажа, описывающий триггеры перехода между состояниями: `on_sensory_cue` (сенсорный), `on_emotional_trigger` (эмоциональный), `on_physical_contact` (физический).

> *См. также:* [internal_state](#internal_state), [sensory_register](#sensory_register)

### **stop_words**
Массив в `safety`. Слова/фразы, которые немедленно останавливают сцену. Обязательно содержит `"СТОП"`. Дополнительно: `["ХВАТИТ", "НЕТ", "СТОП"]`.

> *См. также:* [safety](#safety), [hard_limits](#hard_limits)

### **Structured Generation**
Технология генерации структурированного вывода (JSON) с валидацией. Prompt Architect выводит `ACTIVE_STATE`, `OUTPUT`, `VALIDATION` в каждом ответе.

> *См. также:* [Prompt Architect](#prompt-architect), [JSON Schema](#json-schema)

---

## T

### **TEC**
Теоретические и эмпирические концепции (Theoretical & Empirical Concepts), используемые в VNE для психологической достоверности: Basson, Birnbaum, Baumeister, Chivers.

> *См. также:* [Basson](#basson), [Birnbaum](#birnbaum), [Baumeister](#baumeister), [Chivers](#chivers)

### **Termux**
Android-терминал, рекомендуемый для запуска VNE на мобильных устройствах. Поддерживает Python 3.8+, git, nano. Инструкция: `docs/RUNNING_IN_TERMUX.md`.

> *См. также:* [session_finalize.py](#session_finalizepy), [README](#readme)

### **trauma_anchor**
Блок в `psychology`, описывающий травму персонажа: `name`, `origin`, `trigger_sensory`, `trigger_emotional`, `coping`. Определяет реакции персонажа в стрессовых ситуациях.

> *См. также:* [psychology](#psychology), [core_conflict](#core_conflict)

### **trust_level**
Метрика в `relationships`. Шкала 0-100. Отражает уровень доверия персонажа к user или другому персонажу. Обновляется между сессиями.

> *См. также:* [relationships](#relationships), [attraction_level](#attraction_level)

---

## U

### **USER_GUIDE**
Гайд пользователя для роли или компонента VNE. Должен соответствовать стандартам Documentation Architect: Diátaxis-тип, Flesch-Kincaid ≤ 10, активный залог ≥ 80%.

> *См. также:* [Documentation Architect](#documentation-architect), [Prompt Architect](#prompt-architect)

---

## V

### **Vale**
Инструмент линтинга документации. Проверяет стиль, терминологию, readability. Используется Documentation Architect при аудите. Команда: `vale doc.md`.

> *См. также:* [Documentation Architect](#documentation-architect), [markdownlint](#markdownlint)

### **visual_data**
Блок модуля персонажа, содержащий визуальную информацию: `prompt_base`, `signature_features`, `anti_prompts`, `anatomic_anchor`, `generation_history`.

> *См. также:* [anatomic_anchor](#anatomic_anchor), [Visual Physiognomist](#visual-physiognomist)

### **Visual Extractor**
Роль для LLM в VNE. Находит 8 ключевых визуальных моментов в логе сессии для генерации изображений.

> *См. также:* [Visual Physiognomist](#visual-physiognomist), [Session Finalizer](#session-finalizer)

### **Visual Physiognomist**
Роль для LLM в VNE. Генерирует промпты для генерации изображений с `anatomic_anchor` для консистентности лица. Проверяет, что лицо "не поплыло".

> *См. также:* [anatomic_anchor](#anatomic_anchor), [visual_data](#visual_data)

### **VNE (Voyage Narrative Engine)**
AI-Native интерактивная narrative-система с психологически достоверными персонажами. Подуровневая математика, TEC-механики, визуальная консистентность, автоматическая финализация сессий.

> *См. также:* [README](#readme), [Unified Prompt Assembly](#unified-prompt-assembly)

### **VSCNO**
Внутренняя система координат персонажа. 4 компоненты: **ВЛ** (Воля), **СТ** (Страсть), **НЖ** (Нежность), **ОГ** (Ощущение Границ). Сумма всегда = 10. Используется для определения текущего психологического состояния.

| Компонента | Диапазон | Значение |
|------------|----------|----------|
| **ВЛ** (Воля) | 0–4 | Контроль, дисциплина, сопротивление |
| **СТ** (Страсть) | 0–4 | Желание, импульсивность, химия |
| **НЖ** (Нежность) | 0–4 | Эмоциональная близость, забота |
| **ОГ** (Ощущение Границ) | 0–4 | Безопасность, комфорт, контроль |

> *См. также:* [ВЛ](#вл), [СТ](#ст), [НЖ](#нж), [ОГ](#ог-ощущение-границ)

---

## W

### **write-good**
CLI-инструмент для проверки простоты языка. Находит пассивный залог, сложные слова, клише. Используется Documentation Architect. Команда: `write-good doc.md`.

> *См. также:* [Documentation Architect](#documentation-architect), [Plain Language](#plain-language)

---

## Y

### **Y-уровни**
Устаревшая система уровней (v1.x). Заменена на **У-систему** (У1-А…У7-Б) в VNE v2.1.0. Использование Y-уровней в новых модулях — ошибка.

> *См. также:* [У-уровни](#у-уровни), [level_system](#level_system)

---

## Ф

### **ФМДР**
См. [FMDR](#fmdr-фмдр).

---

## У

### **У-уровни**
Система 14 подуровней поведения персонажа (У1-А…У7-Б). Каждый уровень — комбинация глубины (1-7) и модальности (А/Б). Используется в `speech_profile`, `dynamic_visuals`, `safety_check_points`.

| Уровень | Название | Описание |
|---------|----------|----------|
| У1-А | Маска | Поверхностное поведение, социальная маска |
| У1-Б | Тревога | Маска дрожит, первые трещины |
| У2-А | Игла | Провокация, тестирование границ |
| У2-Б | Рана | Травма просыпается, уязвимость |
| У3-А | Танец | Флирт, игра, повышенная химия |
| У3-Б | Порог | Решение — войти или отступить |
| У4-А | Зеркало | Глубокое узнавание, эмпатия |
| У4-Б | Тишина | Пауза, накопление, ожидание |
| У5-А | Ритуал | Паттерны, церемониальность |
| У5-Б | Разрыв | Конфликт, кризис, перелом |
| У6-А | Пламя | Пик страсти, потеря контроля |
| У6-Б | Пепел | Послепиковая усталость, рефлексия |
| У7-А | Корень | Базовая безопасность, интеграция |
| У7-Б | Целостность | Гармония всех частей |

> *См. также:* [level_system](#level_system), [speech_profile](#speech_profile)

---

## В

### **ВЛ (Воля)**
Компонента VSCNO. Шкала 0-4. Отражает силу воли, самоконтроль, способность сопротивляться импульсам. Высокая ВЛ = персонаж держит дистанцию.

> *См. также:* [VSCNO](#vscno), [СТ](#ст)

---

## С

### **СТ (Страсть)**
Компонента VSCNO. Шкала 0-4. Отражает силу сексуального/эмоционального желания, импульсивность, химическую реакцию. Высокая СТ = персонаж действует импульсивно.

> *См. также:* [VSCNO](#vscno), [ВЛ](#вл)

### **СТОП**
Обязательное stop-слово в `safety.stop_words`. Немедленно останавливает сцену при любом использовании. Дополнительные stop-слова: `["ХВАТИТ", "НЕТ"]`.

> *См. также:* [stop_words](#stop_words), [safety](#safety)

---

## Н

### **НЖ (Нежность)**
Компонента VSCNO. Шкала 0-4. Отражает эмоциональную близость, заботу, теплоту. Высокая НЖ = персонаж открывается, проявляет уязвимость.

> *См. также:* [VSCNO](#vscno), [ОГ](#ог-ощущение-границ)

---

## Дополнительные разделы

### JSON Schema
JSON-файл для валидации модулей персонажей. Путь: `schemas/persona_schema_v3_2_VOYAGE.json`. Проверяет структуру, типы данных, обязательные поля.

> *См. также:* [AUDIT](#audit), [MODULE](#module)

### markdownlint
Инструмент для проверки Markdown-форматирования. Проверяет структуру заголовков, списки, таблицы, отступы. Команда: `markdownlint doc.md`.

> *См. также:* [Documentation Architect](#documentation-architect), [Vale](#vale)

### README
Главный файл репозитория. Должен содержать: описание проекта, быстрый старт, структуру, требования, лицензию. Диátaxis-тип: Overview + Tutorial.

> *См. также:* [Documentation Architect](#documentation-architect), [Termux](#termux)

### Unified Prompt Assembly (UPA)
Игровой промпт, собранный из модулей персонажей + сценария + STATE. Загружается в LLM для игровой сессии. Файл: `UNIFIED_PROMPT_ASSEMBLY_v3.0.md`.

> *См. также:* [LLM](#llm), [scenario](#scenario)

### 5Cs+U
Шесть критериев качества документации: **Clarity** (ясность), **Conciseness** (лаконичность), **Completeness** (полнота), **Correctness** (корректность), **Consistency** (единообразие), **Usability** (удобство). Documentation Architect использует для аудита.

> *См. также:* [Documentation Architect](#documentation-architect), [Diátaxis Framework](#diátaxis-framework)

---

## 📊 META

| Параметр | Значение |
|----------|----------|
| **Версия глоссария** | v1.0 |
| **Совместимость** | VNE v2.1.0+ |
| **Diátaxis-тип** | Reference |
| **Количество терминов** | 60+ |
| **Алфавит** | A-Z, А-Я (русские термины) |
| **Cross-references** | Да |
| **Дата** | 2026-06-10 |
| **Создано через** | Documentation Architect (DOC-ARCH) v1.0 |

---

*Glossary VNE — единый источник истины для всех терминов проекта.*
