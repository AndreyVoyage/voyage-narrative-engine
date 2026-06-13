# 🗂️ QUICK REFERENCE CARD: Voyage Narrative Engine v2.1.0
## Одностраничная шпаргалка для разработчиков и пользователей
### Diátaxis: Reference | Compatible: VNE v2.1.0+ | 2026-06-10

---

## 🚀 БЫСТРЫЙ СТАРТ (3 шага)

```bash
# 1. Клонируй
$ git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
$ cd voyage-narrative-engine

# 2. Играй (загрузи в LLM: Kimi/DeepSeek/Claude)
#    personas/KIRA_MODULE_v14.json + scenarios/SCENARIO_SAUNA_QUARTET.json

# 3. Финализируй
$ python3 session_finalize.py --log sessions/raw/session_YYYYMMDD.log --scenario sauna_quartet
```

---

## 🎭 РОЛИ VNE — ЧТО КОГДА ИСПОЛЬЗОВАТЬ

| Задача | Роль | Файл | Команда/Действие |
|--------|------|------|-----------------|
| Создать персонажа | **Prompt Architect** | `ROLE_PROMPT_ARCHITECT_v1.0.md` | `Создай персонажа: [описание]` |
| Изменить модуль | **Prompt Architect** | `ROLE_PROMPT_ARCHITECT_v1.0.md` | `Измени [файл]: [инструкции]` |
| Аудит модуля | **Prompt Architect** | `ROLE_PROMPT_ARCHITECT_v1.0.md` | `Аудит [файл]` |
| Собрать игровой промпт | **Prompt Architect** | `ROLE_PROMPT_ARCHITECT_v1.0.md` | `Собери Unified Prompt из [файлы]` |
| Создать гайд/документацию | **Documentation Architect** | `ROLE_DOCUMENTATION_ARCHITECT_v1.0.md` | `Создай гайд: [описание]` |
| Аудит документации | **Documentation Architect** | `ROLE_DOCUMENTATION_ARCHITECT_v1.0.md` | `Аудит [файл]` |
| Играть сценарий | **Unified Prompt Assembly** | `UNIFIED_PROMPT_ASSEMBLY_v3.0.md` | Загрузить в LLM |
| Финализировать сессию | **Session Finalizer** | `session_finalize.py` | `python3 session_finalize.py --log ...` |
| Проверить изображение | **Visual Physiognomist** | `ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md` | Загрузить фото + модуль |
| Исправить STATE | **State Manager** | `ROLE_STATE_MANAGER_v1.0_PROMPT.md` | Загрузить лог + STATE |
| Литературная обработка | **Narrative Editor** | `ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md` | Загрузить лог |
| Извлечь визуальные моменты | **Visual Extractor** | `ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md` | Загрузить лог |

---

## 📝 КОМАНДЫ PROMPT ARCHITECT

### CREATE
```
Создай персонажа: [описание]
Создай сценарий: [описание]
Создай STATE для сценария [ID] с персонажами [список]
```

### EDIT
```
Измени [файл]: [инструкции]
```

### AUDIT
```
Аудит [файл]
```

### MIGRATE
```
Мигрируй [файл] с [vX] на [vY]
```

### ASSEMBLE
```
Собери Unified Prompt из [модули] + [сценарий] + [STATE]
```

### LAZY LOAD
```
[LOAD:template_persona]     [LOAD:example_olga]
[LOAD:template_scenario]    [LOAD:example_andrey]
[LOAD:template_state]       [LOAD:schema_v3_2]
[LOAD:tec_basson]           [LOAD:tec_birnbaum]
[LOAD:rules_fmdr]           [LOAD:rules_vscno]
```

### ЧЕКПОИНТ
```
Чекпоинт          → Сохранить прогресс
Продолжи          → Возобновить после чекпоинта
```

---

## 📝 КОМАНДЫ DOCUMENTATION ARCHITECT

```
Создай гайд: [описание]
Создай роль: [описание]
Создай README: [описание]
Измени [файл]: [инструкции]
Аудит [файл]
Мигрируй [файл] с [формат] на [формат]
Собери документацию из [файлы]
Чекпоинт
Продолжи
```

---

## 📊 У-УРОВНИ (14 подуровней)

| Уровень | Название | Речь | Визуал | Safety |
|---------|----------|------|--------|--------|
| **У1-А** | Маска | Формальная, дистанцированная | Сдержанная поза, нейтральное лицо | — |
| **У1-Б** | Тревога | Короткие фразы, паузы | Микродвижения, напряжение | — |
| **У2-А** | Игла | Ирония, провокация | Активная поза, вызов | — |
| **У2-Б** | Рана | Защитная, отстранённая | Сжатие, закрытость | — |
| **У3-А** | Танец | Игривая, флиртующая | Расслабленность, улыбка | — |
| **У3-Б** | Порог | Двусмысленная, осторожная | Колебание, приближение | ✅ Checkpoint |
| **У4-А** | Зеркало | Тихая, глубокая | Мягкий взгляд, открытость | — |
| **У4-Б** | Тишина | Минимум слов, жесты | Покой, ожидание | — |
| **У5-А** | Ритуал | Паттерны, церемониальная | Ритуальные движения | ✅ Checkpoint |
| **У5-Б** | Разрыв | Конфликтная, эмоциональная | Резкие движения, дистанция | ✅ Checkpoint |
| **У6-А** | Пламя | Страстная, импульсивная | Потеря контроля, близость | ✅ Checkpoint |
| **У6-Б** | Пепел | Уставшая, рефлексивная | Расслабленность, отстранение | — |
| **У7-А** | Корень | Спокойная, уверенная | Стабильная поза, контакт | — |
| **У7-Б** | Целостность | Гармоничная, интегрированная | Естественность, баланс | ✅ Checkpoint |

---

## ⚖️ VSCNO (сумма = 10)

| Компонента | Диапазон | Что означает | Высокое значение |
|------------|----------|--------------|------------------|
| **ВЛ** (Воля) | 0–4 | Самоконтроль, дисциплина | Держит дистанцию, сопротивляется |
| **СТ** (Страсть) | 0–4 | Желание, импульсивность | Действует спонтанно, химия |
| **НЖ** (Нежность) | 0–4 | Эмоциональная близость | Открывается, забота, уязвимость |
| **ОГ** (Ощущение Границ) | 0–4 | Безопасность, комфорт | Чувствует себя в безопасности |

**Примеры:**
- `ВЛ4 СТ2 НЖ2 ОГ2` = Контроль, сдержанность
- `ВЛ1 СТ4 НЖ3 ОГ2` = Импульс, страсть, близость
- `ВЛ2 СТ2 НЖ3 ОГ3` = Баланс, комфорт, нежность

---

## 🛡️ SAFETY ПРОТОКОЛЫ

### Stop-слова (обязательны)
```json
["СТОП", "ХВАТИТ", "НЕТ"]
```

### Hard Limits (примеры)
```json
["насилие", "принуждение", "публичное унижение", "несогласованная запись"]
```

### Soft Limits (примеры)
```json
["публичные места", "грубая лексика", "физическая боль"]
```

### Safety Checkpoints
```
У3-Б → У5-А → У5-Б → У6-А → У7-Б
```

---

## 📁 NAMING CONVENTIONS

| Тип файла | Формат | Пример |
|-----------|--------|--------|
| Модуль персонажа | `[NAME]_MODULE_v[N].json` | `OLGA_MODULE_v2.json` |
| Сценарий | `SC_[NAME]_v[N].json` | `SC_SPORTCOMPLEX_TRIAD_v2.json` |
| STATE | `STATE_[SCENARIO]_v[N].json` | `STATE_TEMPLATE_SC_SPORTCOMPLEX_TRIAD_v2.json` |
| Роль | `ROLE_[NAME]_v[N].md` | `ROLE_PROMPT_ARCHITECT_v1.0.md` |
| Гайд | `USER_GUIDE_[NAME].md` | `USER_GUIDE_PROMPT_ARCHITECT.md` |
| Глоссарий | `GLOSSARY_VNE_v[N].md` | `GLOSSARY_VNE_v1.0.md` |
| Сессия | `session_YYYYMMDD_NNN.log` | `session_2026-06-10_001.log` |
| Story | `STORY_[SCENARIO]_YYYYMMDD.md` | `STORY_SAUNA_QUARTET_2026-06-10.md` |
| Visuals | `VISUAL_PROMPTS_[SCENARIO]_YYYYMMDD.md` | `VISUAL_PROMPTS_SAUNA_QUARTET_2026-06-10.md` |

---

## 🛠️ ИНСТРУМЕНТЫ АУДИТА (CLI)

```bash
# 1. Markdown структура
$ markdownlint docs/*.md roles/*.md

# 2. Стиль и читаемость
$ vale docs/*.md
$ write-good docs/*.md

# 3. Метрики Flesch-Kincaid
$ python -m textstat docs/*.md

# 4. JSON валидация модулей
$ python3 -c "import json; json.load(open('personas/OLGA_MODULE_v2.json'))"

# 5. VSCNO проверка (сумма = 10)
#    Ручная проверка через jq или Python

# 6. Консистентность лиц (ручная)
$ python3 scripts/python/check_consistency.py KIRA_MODULE_v14 new.png ref.png
```

---

## 📱 TERMUX (Android)

```bash
# Установка (один раз)
$ pkg update && pkg install python3 git -y

# Клонирование
$ git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
$ cd ~/voyage-narrative-engine

# Финализация
$ python3 session_finalize.py --log sessions/raw/session_2026-06-10.log --scenario sauna_quartet

# Результаты
$ ls sessions/stories/      # рассказ
$ ls sessions/visuals/      # промпты
$ ls sessions/state/        # метрики
```

---

## 🎮 ФМДР-ФОРМАТ (игровая сессия)

```
(Мысли)      → внутренний монолог, курсив
_Действия_   → физические действия, подчёркивание
«Речь»       → диалог, кавычки-ёлочки
```

**Пример:**
```
(Она думает, что он слишком самоуверен, но это заводит)
_Кира откидывает волосы назад, слегка наклоняется_
«Ты уверен, что справишься? Я не из лёгких»
```

---

## 📦 СТРУКТУРА РЕПОЗИТОРИЯ

```
voyage-narrative-engine/
├── personas/          ← Модули персонажей (JSON)
├── scenarios/         ← Сценарии (JSON)
├── states/            ← STATE-шаблоны (JSON)
├── roles/             ← Роли для LLM (MD)
├── docs/              ← Гайды и документация (MD)
├── sessions/          ← Артефакты сессий
│   ├── raw/           ← Сырые логи
│   ├── state/         ← Обновления STATE
│   ├── memory/        ← Обновления memory
│   ├── stories/       ← Литературные рассказы
│   └── visuals/       ← Промпты для картинок
├── scripts/           ← Python + Termux скрипты
├── schemas/           ← JSON Schema для валидации
└── assets/            ← Сгенерированные изображения
```

---

## ⚡ ЧИСТЫЙ СПИСОК КОМАНД (копировать)

```
Создай персонажа:
Создай сценарий:
Создай STATE для сценария
Создай гайд:
Создай роль:
Измени [файл]:
Аудит [файл]
Мигрируй [файл] с [vX] на [vY]
Собери Unified Prompt из
Собери документацию из
[LOAD:template_persona]
[LOAD:example_olga]
[LOAD:schema_v3_2]
[LOAD:tec_basson]
[LOAD:rules_vscno]
Чекпоинт
Продолжи
```

---

## 📊 META

| Параметр | Значение |
|----------|----------|
| **Версия** | v1.0 |
| **Совместимость** | VNE v2.1.0+ |
| **Diátaxis** | Reference |
| **Терминов** | 79 (в Glossary) |
| **Ролей** | 7 |
| **У-уровней** | 14 |
| **Компонент VSCNO** | 4 |
| **Дата** | 2026-06-10 |

---

*Quick Reference Card — всё под рукой, ничего лишнего.*
