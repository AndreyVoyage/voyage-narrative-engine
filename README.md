> **⚠️ Для AI-агентов и разработчиков:** Перед началом работы прочитай `AGENTS.md` —
> он содержит актуальную архитектуру и правила. Этот README может быть устаревшим.

# Voyage Narrative Engine v2.2

> AI-Native интерактивная narrative-система с психологически достоверными персонажами.
> Подуровневая математика, TEC-механики, визуальная консистентность и автоматическая финализация сессий.

---

## Быстрый старт (TL;DR)

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git
cd voyage-narrative-engine

# 2. Установите Python (Termux / Linux / macOS)
python3 --version  # должно быть 3.7+

# 3. Запустите сессию в LLM (Kimi / DeepSeek / Claude)
#    Загрузите personas/KIRA_MODULE_v14.json + scenarios/SCENARIO_SAUNA_QUARTET.json
#    Ведите диалог, сохраните лог.

# 4. Финализируйте сессию одной командой
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet

# 5. Проверьте результаты
ls sessions/stories/      # литературный рассказ
ls sessions/visuals/      # промпты для картинок
ls sessions/state/        # обновлённые метрики
```

---

## Что это

**Voyage Narrative Engine** — это не просто набор промптов. Это **операционная система для интерактивных narrative-игр**:

- **Персонажи** с психологической глубиной (травмы, конфликты, 14 подуровней поведения)
- **Память** между сессиями (trust, attraction, история событий)
- **Механика** «body knows first» (Chivers), «responsive desire» (Basson), «erotic plasticity» (Baumeister)
- **Формат ФМДР** — структурированный вывод: (Мысли) → *Действия* → «Речь»
- **Визуальная консистентность** — anatomic_anchor гарантирует одно и то же лицо на всех картинках
- **Автоматизация** — `session_finalize.py` превращает сырой лог в 4 артефакта за 1 команду

---

## Структура репозитория

```
voyage-narrative-engine/
├── README.md                           # ← этот файл
├── session_finalize.py                 # ← ГЛАВНЫЙ СКРИПТ (финализация сессии)
├── personas/                           # Модули персонажей (JSON)
│   ├── KIRA_MODULE_v14.json           # Кира (ex-sprinter, steel butterfly, shy_to_bitch)
│   ├── SERGEY_MODULE_v4.json          # Сергей (catalyst, avoidant, guardian)
│   ├── MARINA_MODULE_v2.json          # Марина (shy_to_bloom, observer)
│   ├── ANDREY_JUNIOR_MODULE_v2.1.json    # Андрей (shy_explosive_youth) v2.1.0
│   ├── ANDREY_SENIOR_MODULE_v1.1.json    # Андрей (protector_playful_switch) v1.1.0
│   ├── OLGA_MODULE_v2.json    # Ольга v2.0.0
│   ├── KIRA_MODULE_v15.json    # Кира v15.0.0
│   ├── EGOR_MODULE_v1.json    # Егор v1.0.0
│   ├── user_default.json    # Я v1.0.0
│   ├── sergey_v3.json    # Сергей v3.0.0
│   ├── sergey_v2.json    # Сергей v2.0.0
│   ├── MAKSIM_001.json    # Максим (loyal_clumsy_giant) v1.0.0
│   ├── MARINA_001.json    # Марина (sunshine_pixie) v1.1.0
│   ├── kira_v12.json    # Кира v12.0.0
│   ├── kira_v11.json    # Кира v11.0.0
│   ├── FEMALE_USER_001.json    # Девушка v1.0.0
│   └── MAKSIM_MODULE_v2.json          # Максим (secure, bridge)
├── scenarios/                          # Сценарии (JSON)
│   ├── SCENARIO_SAUNA_QUARTET.json    # Сауна вчетвером (5 фаз)
│   └── SCENARIO_SHY_BLOOM.json        # Знакомство со скромной девушкой
├── state/                              # Текущее состояние сессии
│   └── STATE_TEMPLATE_v2.json       # Шаблон с vscno, levels, flags
├── knowledge_base/                      # Knowledge Base для всех ролей (R1–R6 + Narrative)
│   ├── R1/                               # Portrait Writer (портрет, identity, safety)
│   ├── R2/                               # Psychologist (ВСЦНО, АД, аудит, компрессия)
│   ├── R3/                               # Sexologist (TEC, сексуальные сценарии)
│   ├── R4/                               # Speech Specialist (ФМДР, речь)
│   ├── R5/                               # Physiognomist (визуал, anchor, dynamic visuals)
│   ├── R6/                               # Modular Assembly Architect (модуль, отношения)
│   └── narrative/                        # Narrative (ФМДР примеры, anchor system, stop frame)
├── roles/                              # Промпты для LLM-ролей (опционально)
│   ├── ROLE_STATE_MANAGER_v1.0_PROMPT.md
│   ├── ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md
│   ├── ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md
│   └── ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md
├── sessions/                           # Артефакты сессий (создаются автоматически)
│   ├── raw/           # Сырые логи (вы кладёте сюда)
│   ├── state/         # Обновления STATE (авто)
│   ├── memory/        # Обновления memory модулей (авто)
│   ├── stories/       # Литературные рассказы (авто)
│   └── visuals/       # Промпты для картинок (авто)
├── scripts/
│   ├── termux/        # Скрипты для Android/Termux
│   └── python/        # Python-утилиты
│       ├── refactor_universal.py         # Универсальный R7 Refactor (любой JSON → модули)
│       ├── runtime_loader.py               # Runtime Loader v2.2 (модульная загрузка)
│       ├── audit_andrey_senior_r8.py      # R8 Auditor для andrey_senior
│       └── check_consistency.py           # Проверка консистентности лиц (заглушка)
├── schemas/
│   └── persona_schema_v3_2_VOYAGE.json # JSON Schema для валидации модулей
├── docs/
│   ├── VOYAGE_NARRATIVE_CORE_v2.md    # Ядро системы (мнемоники, ФМДР, АД)
│   ├── ANALYSIS_WORKFLOW_v1.0.md      # Анализ workflow
│   ├── SESSION_FINALIZATION_WORKFLOW_v1.1.md # Подробная инструкция по финализации
│   └── RUNNING_IN_TERMUX.md           # Как запускать в Termux
└── assets/
    └── images/                         # Сгенерированные картинки
        └── character_sessions/
            ├── kira/
            ├── sergey/
            ├── marina/
            └── maksim/
```

---

## Knowledge Base (R1–R6 + Narrative)

Каждая роль имеет **собственный Knowledge Base** — источник истины для генерации, аудита и компрессии.

| Роль | Назначение | Файлов | Ключевые документы |
|------|-----------|--------|-------------------|
| **R1** Portrait Writer | Портрет, identity, soft skills, narrative techniques | 4 | `KB_R1_CORE.md`, `KB_R1_TRAUMA_INFORMED.md` |
| **R2** Psychologist | ВСЦНО (14 подуровней), АД (10 кодов), защиты, аудит | 5 | `KB_R2_VSCNO_RULES.md`, `KB_R2_AD_RULES.md`, `KB_R2_AUDIT_CHECKLIST.md` |
| **R3** Sexologist | TEC (6 уровней), сексуальные сценарии, словарь | 3 | `KB_R3_TEC_DICTIONARY.md` |
| **R4** Speech Specialist | ФМДР формат, речевые паттерны, матрица речи | 3 | `KB_R4_SPEECH_MATRIX.md` |
| **R5** Physiognomist | Anatomic Anchor, Visual Signature, Dynamic Visuals (14×7) | 3 | `KB_R5_DYNAMIC_VISUALS.md` |
| **R6** Assembly Architect | Persona Module, HUMAN/AUTONOMOUS/META, отношения | 3 | `KB_R6_BLOCK_SCHEMA.md` |
| **Narrative** | ФМДР примеры, Anchor System, Stop Frame, Runtime Compression | 4 | `KB_NARRATIVE_FMDR_EXAMPLES.md` |

**Всего: 25 KB-файлов (~200 KB).** Каждый файл содержит:
- **Core** — теория и правила
- **Audit** — чек-лист валидации (5 секций)
- **Compression** — правила сжатия (3 метода)

### Pipeline: KB → Generation → Audit → Compression → Next Role

1. **Загрузка KB** — загрузить `KB_R*_CORE.md` + `KB_R*_AUDIT.md` + `KB_R*_COMPRESSION.md`
2. **Генерация** — создать артефакт (портрет, психология, речь, визуал)
3. **Аудит** — проверить по `KB_R*_AUDIT.md` (PASS / FAIL / WARNING)
4. **Компрессия** — сжать по `KB_R*_COMPRESSION.md` (40–50% размера)
5. **Передача** — передать в следующую роль

---

## Runtime (модульная загрузка)

Система поддерживает **модульную структуру** персонажей: `personas/[id]/` вместо монолитных `*.json`.

### Runtime Loader
```bash
python scripts/python/runtime_loader.py andrey_senior
```

Загружает:
- `personas/[id]/INDEX.json` — манифест модуля
- Все 12 подпапок: core, levels, psychology, sexology, visual, dynamics, memory, relationships, environment, safety, autonomous, meta
- Возвращает объединённый словарь (как старый монолит)

### Валидация
```bash
python scripts/python/runtime_loader.py andrey_senior
# Output: [PASS] basic_fields, levels, vscno, safety, core
```

### Статус миграции

| Персонаж | Метод | Статус |
|----------|-------|--------|
| andrey_senior | Python скрипт | ✅ Модульная + Runtime PASS |
| kira | Ручная | ✅ Модульная |
| user | Kimi Code | ✅ Модульная |
| female_user | Kimi Code | ✅ Модульная |
| egor | Python скрипт | ✅ Модульная |
| andrey_junior | Python скрипт | ✅ Модульная |
| maksim | Python скрипт | ✅ Модульная |
| marina | Python скрипт | ✅ Модульная |
| olga | Python скрипт | ✅ Модульная |
| sergey | Python скрипт | ✅ Модульная |

**Всего: 10 персонажей мигрированы.** Монолитные JSON-файлы оставлены для обратной совместимости.

---

## Как играть (сессия)

### 1. Подготовка

Откройте чат с LLM (Kimi, DeepSeek, Claude, GPT-4). Загрузите:
1. `personas/KIRA_MODULE_v14.json` — модуль персонажа (или несколько)
2. `scenarios/SCENARIO_SAUNA_QUARTET.json` — сценарий (опционально)
3. `state/STATE_TEMPLATE_v2.json` — текущее состояние (опционально, для продолжения)

### 2. Игровой процесс

- Пишите от первого лица (`Я подхожу к Кире`)
- Или команды (`ВЛ2 СТ3`, `АД КН`, `У3-Б`)
- Или в режиме режиссёра (`Пусть Кира улыбнётся`)
- LLM генерирует ответ в формате ФМДР

### 3. Финализация (после сессии)

```bash
# Сохраните лог в файл
mkdir -p sessions/raw
nano sessions/raw/session_2026-06-08.log
# (вставьте весь текст из чата, Ctrl+O, Enter, Ctrl+X)

# Запустите финализатор
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet

# Результаты:
# sessions/stories/STORY_...md       — литературный рассказ
# sessions/visuals/VISUAL_PROMPTS_...md — промпты для Qwen/Midjourney
# sessions/state/STATE_UPDATE_...json   — обновлённые метрики
# personas/KIRA_MODULE_v14.json       — обновлённая память (авто)
```

---

## Как запустить session_finalize.py

### Termux (Android)

```bash
# 1. Установите Python (один раз)
pkg update && pkg install python3 -y

# 2. Проверьте версию
python3 --version  # Python 3.11+ или 3.8+

# 3. Перейдите в репозиторий
cd ~/voyage-narrative-engine

# 4. Запустите
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet

# 5. Если ошибка "Module not found" — ничего ставить не нужно,
#    скрипт использует только стандартную библиотеку.
#    Если всё же нужно — проверьте путь:
ls -la session_finalize.py
```

### Linux / macOS / Windows (WSL)

```bash
cd ~/voyage-narrative-engine
python3 session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet
```

### Аргументы скрипта

| Аргумент | Описание | Пример |
|----------|----------|--------|
| `--log` | **Обязательно.** Путь к логу сессии | `sessions/raw/session_2026-06-08.log` |
| `--scenario` | ID сценария | `sauna_quartet`, `promenade`, `cafe_date` |
| `--repo` | Путь к репозиторию (если не `~/voyage-narrative-engine`) | `/path/to/repo` |
| `--no-git` | Не делать `git commit` | `--no-git` |

---

## Что делает session_finalize.py (внутри)

**Один файл — 4 роли:**

1. **State Manager** — парсит лог, определяет подуровни (У1-А…У7-Б), обновляет desire/anxiety (0-10), фиксирует флаги, проверяет vscno=10
2. **Narrative Editor** — превращает ФМДР в литературный Markdown-рассказ
3. **Visual Extractor** — находит 8 ключевых визуальных моментов
4. **Visual Physiognomist** — генерирует промпты с `anatomic_anchor` для консистентности лица

**Выход:** 4 файла + обновлённые модули персонажей + git commit.

---

## Что делать с check_consistency.py

Это **заглушка** для будущей автоматической проверки консистентности лиц.

**Сейчас (ручной режим):**
```bash
cd ~/voyage-narrative-engine
python3 scripts/python/check_consistency.py KIRA_MODULE_v14 /path/to/new_kira.png /path/to/reference_kira.png
```

Скрипт выведет список `anatomic_anchor` (форма лица, глаза, нос, родинки) и попросит сравнить визуально.

**Будущее:** Подключение CLIP/ResNet для автоматического сравнения эмбеддингов.

---

## Роли (Knowledge Base Pipeline R1–R6)

Персонаж создаётся через 6 ролей с последовательной передачей артефактов:

| Роль | Назначение | Вход | Выход | Ключевой KB |
|------|-----------|------|-------|-------------|
| **R1** Portrait Writer | Портрет, identity, soft skills | Название, возраст, базовые черты | PORTRAIT (400+ строк) | `KB_R1_CORE.md` |
| **R2** Psychologist | ВСЦНО, АД, защиты, травмы | PORTRAIT от R1 | PSYCHOLOGY (600+ строк) | `KB_R2_VSCNO_RULES.md` |
| **R3** Sexologist | TEC, сексуальные сценарии | PSYCHOLOGY от R2 | SEXOLOGY (300+ строк) | `KB_R3_TEC_DICTIONARY.md` |
| **R4** Speech Specialist | ФМДР, речь, сленг | SEXOLOGY от R3 | SPEECH (200+ строк) | `KB_R4_SPEECH_MATRIX.md` |
| **R5** Physiognomist | Визуал, anchor, dynamic visuals | SPEECH от R4 | VISUAL (300+ строк) | `KB_R5_DYNAMIC_VISUALS.md` |
| **R6** Assembly Architect | Модуль, отношения, PREVIOUS/CURRENT/FUTURE | VISUAL от R5 | PERSONA MODULE (12 папок) | `KB_R6_BLOCK_SCHEMA.md` |

**Каждая роль:** загружает KB → генерирует артефакт → аудит по KB → компрессия → передача в следующую роль.

### Legacy роли (для финализации сессий)

Если `session_finalize.py` недостаточен (редкие случаи), используйте роли по отдельности:

| Роль | Файл | Когда использовать |
|------|------|-------------------|
| **State Manager** | `roles/ROLE_STATE_MANAGER_v1.0_PROMPT.md` | Если скрипт неправильно определил уровень |
| **Narrative Editor** | `roles/ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md` | Если нужна более литературная обработка |
| **Visual Extractor** | `roles/ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md` | Если нужно больше/меньше 8 моментов |
| **Visual Physiognomist** | `roles/ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md` | Если лицо «поплыло» — усилить anatomic_anchor |

---

## Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| Python | 3.7 | 3.10+ |
| Git | 2.20+ | Любая |
| LLM для сессий | Любая (Kimi/DeepSeek/Claude) | Kimi (200K контекст) |
| LLM для ролей | Любая | Claude/GPT-4 (стилистика) |
| Генерация картинок | Qwen / Midjourney / SD | Qwen (локально) или MJ |
| ОС | Android/Termux, Linux, macOS, Windows | Любая |

---

## Версионирование

| Версия | Что нового |
|--------|-----------|
| **v2.0.0** | Базовая система: модули, сценарии, STATE, ФМДР, TEC |
| **v2.1.0** | `session_finalize.py`, 4 роли, автоматическая финализация, anatomic_anchor, generation_history |
| **v2.2.0** | **Knowledge Base pipeline** — R1–R6 KB с аудитом и компрессией, 25 KB-файлов, 12-папочная структура модуля, VS Code промпты, **Runtime Loader** для модульных персонажей |

Семантическое версионирование: `MAJOR.MINOR.PATCH`
- **MAJOR** — изменение архитектуры (новые модули несовместимы)
- **MINOR** — новые функции (совместимы)
- **PATCH** — багфиксы

---

## Лицензия и использование

- Все персонажи — вымышленные, совершеннолетние (25+)
- Сценарии построены на консенсуальности и психологической безопасности
- Hard limits: насилие, принуждение — блокируются safety-протоколом
- Для оффлайн-использования: поддерживаются локальные LLM (Ollama, LM Studio)

---

## Ссылки и помощь

- **Репозиторий:** https://github.com/AndreyVoyage/voyage-narrative-engine
- **Issues:** https://github.com/AndreyVoyage/voyage-narrative-engine/issues
- **Документация:** `docs/SESSION_FINALIZATION_WORKFLOW_v1.1.md`
- **Termux-гайд:** `docs/RUNNING_IN_TERMUX.md`

---

*Voyage Narrative Engine — где психология встречает код.*
