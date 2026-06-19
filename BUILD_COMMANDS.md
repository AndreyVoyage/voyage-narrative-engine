# Voyage Narrative Engine — Команды сборки и запуска

## Быстрый старт (2 режима сборки)

### Режим 1: ОТДЕЛЬНЫЕ ФАЙЛЫ (рекомендуется для игры в чате)

Каждый персонаж — отдельный файл. Сценарий — отдельный файл. Триггерный гайд — отдельный файл.

```bash
bash build_prompt_modular.sh sauna_extended standard AG3 --separate
```

**Результат — 7 файлов:**

| Файл | Размер | Назначение |
|------|--------|------------|
| `PROMPT_SCENARIO.txt` | ~41 KB | **Сценарий** — загружать ПЕРВЫМ. Содержит таймлайн, фазы, триггеры, ветки, динамику, триггер-карту |
| `PROMPT_KIRA.txt` | ~39 KB | **Кира** — полная речевая матрица, инициативы, VSCNO, психология |
| `PROMPT_MARINA.txt` | ~27 KB | **Марина** — полная речевая матрица, инициативы, VSCNO |
| `PROMPT_SERGEY.txt` | ~25 KB | **Сергей** — полная речевая матрица, инициативы, VSCNO |
| `PROMPT_MAKSIM.txt` | ~27 KB | **Максим** — полная речевая матрица, инициативы, VSCNO |
| `PROMPT_ANDREY_SENIOR.txt` | ~37 KB | **Андрей Старший** — полная речевая матрица, инициативы, VSCNO |
| `TRIGGER_GUIDE.txt` | ~10 KB | **Гайд для LLM** — когда и как подгружать персонажей по триггерам |

### Режим 2: ОДИН ФАЙЛ (для тестов или коротких сессий)

```bash
bash build_prompt_modular.sh sauna_extended standard AG3
```

**Результат:** `PROMPT_MODULAR.txt` (~104 KB) — всё в одном файле.

---

## Как правильно написать запрос (чтобы ничего не пропало)

❌ **Неправильно:**
> Собери промпт для игры в сауне.

⚠️ Риск: я соберу один файл, возможно сокращённый.

✅ **Правильно — отдельные файлы:**
> Собери `sauna_extended` в режиме **--separate** (отдельные файлы). Каждый персонаж — в свой файл. Сценарий — отдельно. Включи **ВСЕ модули**: timeline, phases (с triggers и character_states), locations (с sensory anchors), branches (с FMDR), dynamics, markdown-сцены (P1b, P2b, P3b). Не сокращай.

✅ **Правильно — один файл:**
> Собери **ПОЛНЫЙ** `PROMPT_MODULAR.txt` для `sauna_extended`. Включи **ВСЕ модули** сценария и **ВСЕХ** персонажей с полными speech matrix, initiatives, activities. Не сокращай.

---

## Триггерная подгрузка (как экономить контекст)

### Проблема
5 персонажей × ~30 KB = 150 KB. Сценарий = 40 KB. Итого ~190 KB — слишком много для одного сообщения.

### Решение
1. **Загружаем сценарий** (`PROMPT_SCENARIO.txt`) — 41 KB. Внутри есть **Trigger Map**.
2. **LLM ведёт игру** с минимальным контекстом (сценарий + текущие персонажи).
3. **Когда срабатывает триггер** — LLM получает команду загрузить конкретного персонажа.

### Пример триггерной подгрузки

**Шаг 1:** Загружаем сценарий:
> [Вставляем PROMPT_SCENARIO.txt]
> Начни игру. Я — пользователь. Фаза P1_entrance.

**Шаг 2:** Сценарий говорит: "В фазе P1 присутствуют Кира, Марина, Сергей, Максим. Андрей входит позже."

**Шаг 3:** Когда срабатывает триггер `andrey_entrance` (фаза P1b), пользователь или LLM загружает:
> [ЗАГРУЗИ ANDREY_SENIOR] или вставляем `PROMPT_ANDREY_SENIOR.txt`

**Шаг 4:** Теперь в контексте: сценарий + Кира + Марина + Сергей + Максим + Андрей. Но Андрей загружен только когда нужен.

### Ручные команды загрузки (для пользователя)

- **ЗАГРУЗИ КИРА** → LLM загружает `PROMPT_KIRA.txt`
- **ЗАГРУЗИ МАРИНА** → LLM загружает `PROMPT_MARINA.txt`
- **ЗАГРУЗИ ВСЕХ** → LLM загружает все 5 персонажей
- **ВЫГРУЗИ [ID]** → Убрать персонажа из контекста

### Автоматическая выгрузка

Персонаж автоматически выгружается если:
- Пользователь покидает локацию, где персонаж отсутствует
- Прошло более 30 минут без упоминания (AG≥3)
- Команда ВЫГРУЗИ [ID]

---

## Сборка через PythonRun (если bash недоступен)

```python
import sys
from pathlib import Path
repo = Path("C:/DEV/Narrative/voyage-narrative-engine")
sys.path.insert(0, str(repo / "scripts" / "python"))
from build_prompt_modular import build_separate

# Собрать отдельные файлы
built = build_separate("sauna_extended", "standard", "AG3")
for fname, size in built:
    print(f"{fname}: {size} bytes")
```

---

## Варианты режимов (Mode)

| Режим | Описание | AG |
|-------|----------|-----|
| **standard** | Стандартный — сценарий + персонажи + инструкции | AG3 |
| **compact** | Минимальный контекст, экономия токенов | AG1 |
| **extended** | Максимальный контекст + автономия | AG4 |

---

## Уровни AG (Autonomy Governance)

| AG | Что NPC могут делать |
|----|----------------------|
| **AG0** | Только реагируют на пользователя. Не инициируют. |
| **AG1** | Продолжают текущую сцену. Мягкие переходы. |
| **AG2** | Переключение POV между персонажами. |
| **AG3** | NPC-to-NPC разрешён. Кира может подойти к Андрею. Марина может уйти к Максиму. |
| **AG4** | Полная автономия. Персонажи могут уходить, приходить, разговаривать друг с другом. |

---

## Структура репозитория (что важно знать)

```
voyage-narrative-engine/
├── PROMPT_SCENARIO.txt            # Сценарий — загружать ПЕРВЫМ (~41 KB)
├── PROMPT_KIRA.txt                # Кира — отдельный файл (~39 KB)
├── PROMPT_MARINA.txt              # Марина — отдельный файл (~27 KB)
├── PROMPT_SERGEY.txt              # Сергей — отдельный файл (~25 KB)
├── PROMPT_MAKSIM.txt              # Максим — отдельный файл (~27 KB)
├── PROMPT_ANDREY_SENIOR.txt       # Андрей Старший — отдельный файл (~37 KB)
├── TRIGGER_GUIDE.txt              # Триггерная подгрузка (~10 KB)
├── PROMPT_MODULAR.txt             # Всё в одном (~104 KB) — альтернатива
│
├── personas/                      # Персонажи (модульные)
│   ├── kira/                      # Кира — speech/, autonomous/INITIATIVE.json
│   ├── marina/                    # Марина — speech/, autonomous/INITIATIVE.json
│   ├── sergey/                    # Сергей — speech/, autonomous/INITIATIVE.json
│   ├── maksim/                    # Максим — speech/, autonomous/INITIATIVE.json
│   ├── andrey_senior/             # Андрей Старший — speech/, autonomous/INITIATIVE.json
│   ├── andrey_junior/             # Speech ✅, Initiatives ❌
│   ├── olga/                      # ❌ — нужен апдейт
│   └── egor/                      # ❌ — нужен апдейт
│
├── scenarios/                     # Сценарии (модульные)
│   └── sauna_extended/            # Сауна v3.0 — 8 фаз, 4 ветки, 7 динамик
│       ├── core/INDEX.json
│       ├── scenes/                # JSON + Markdown сцены
│       ├── structure/             # phases.json, timeline.json, locations.json
│       ├── branches/BRANCHES.json
│       ├── dynamics/CROSS_CHARACTER.json
│       ├── characters/ROLES.json
│       └── environment/ATMOSPHERE.json
│
├── scripts/python/
│   ├── build_prompt_modular.py    # Сборщик (single + separate режимы)
│   ├── runtime_loader.py          # Загрузчик модульных персонажей
│   └── test_runtime_all.py
│
├── build_prompt_modular.sh        # Shell-скрипт (single + --separate)
├── build_prompt_v3.sh             # Legacy скрипт (старые монолитные)
├── BUILD_COMMANDS.md              # Этот файл
├── README_MODULAR.md              # Документация для разработчика
└── Voyage_Sauna_Game_v3.zip       # Архив для скачивания
```

---

## Команды для разработчика

### Проверить, что все персонажи загружаются
```bash
# Через PythonRun (python нет в PATH)
```

### Собрать архив для игры
Архив `Voyage_Sauna_Game_v3.zip` собирается автоматически через PythonRun. Содержит:
- 7 готовых промпт-файлов (scenario + 5 personas + trigger guide)
- Альтернативу: PROMPT_MODULAR.txt (всё в одном)
- Все исходные JSON-модули (personas + scenarios)
- Скрипты сборки
- Документацию

---

## Как работает сборка (сейчас)

1. **Сценарий** (`sauna_extended`) содержит 8 фаз + 3 markdown-сцены + timeline + branches + dynamics
2. **Builder** (`build_prompt_modular.py`) поддерживает два режима:
   - **default** — один файл `PROMPT_MODULAR.txt`
   - **--separate** — 7 файлов (scenario + 5 personas + trigger guide)
3. **Персонажи** загружаются с `speech/SPEECH_MATRIX.json` + `autonomous/INITIATIVE.json`
4. **Триггерная подгрузка** позволяет не перегружать контекст сразу всеми 5 персонажами

---

## Состояние обновления персонажей

| Персонаж | Speech Matrix | Initiatives | Activities | Status |
|----------|--------------|-------------|------------|--------|
| Kira | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Marina | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Sergey | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Maksim | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Andrey Senior | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Andrey Junior | ✅ v2.0 | ❌ | ❌ | Speech готов, нужны Initiatives |
| Olga | ❌ | ❌ | ❌ | Не в сценарии sauna_extended |
| Egor | ❌ | ❌ | ❌ | Не в сценарии sauna_extended |

---

## СТОП-слово и безопасность

- **СТОП** — мгновенный сброс всех персонажей на безопасные уровни
- **Г0** — NPC только реагируют
- **СТОП-слово** работает на любом уровне AG

---

*Последнее обновление: 2026-06-19*
*Версия системы: v3.1.0 (separate mode + trigger loading)*
*Сценарий: sauna_extended (полная сборка)*
