# Voyage Narrative Engine — Команды сборки и запуска

## Быстрый старт

### Собрать промпт для игры в сауне (6 персонажей)

```bash
cd C:/DEV/Narrative/voyage-narrative-engine

# Способ 1: Через новый modular builder (рекомендуется)
bash build_prompt_modular.sh sauna_extended standard AG3

# Способ 2: Через Python напрямую
python scripts/python/build_prompt_modular.py sauna_extended standard AG3
```

Результат: файл `PROMPT_MODULAR.txt` в корне репозитория.

---

## Варианты режимов (Mode)

| Режим | Описание | Команда |
|-------|----------|---------|
| **sauna_extended** | Сауна с Андреем Старшим, 6 персонажей | `build_prompt_modular.sh sauna_extended standard AG3` |
| **sauna_extended compact** | Минимальный контекст, экономия токенов | `build_prompt_modular.sh sauna_extended compact AG1` |
| **sauna_extended extended** | Максимальный контекст + автономия | `build_prompt_modular.sh sauna_extended extended AG4` |

---

## Варианты сборки (Variant)

| Variant | Что включает | Когда использовать |
|---------|-------------|-------------------|
| **compact** | Только ядро + персонажи + текущий state | Экономия токенов |
| **standard** | Ядро + персонажи + state + governance + сценарий | **По умолчанию** |
| **extended** | Всё + память + визуал + proactive mode | Максимальная автономия NPC |

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
├── personas/                    # Персонажи (модульные)
│   ├── kira/                    # Кира — speech/, autonomous/INITIATIVE.json
│   ├── marina/                  # Марина — speech/, autonomous/INITIATIVE.json
│   ├── sergey/                  # Сергей — speech/, autonomous/INITIATIVE.json
│   ├── maksim/                  # Максим — speech/, autonomous/INITIATIVE.json
│   ├── andrey_senior/           # Андрей Старший — speech/, autonomous/INITIATIVE.json
│   ├── andrey_junior/           # Андрей Младший — пока без speech/initiative
│   ├── olga/                    # Ольга — пока без speech/initiative
│   └── egor/                    # Егор — пока без speech/initiative
│
├── scenarios/                   # Сценарии (модульные)
│   └── sauna_extended/          # Сауна v3.0 — фазы, роли, атмосфера
│       ├── core/INDEX.json          # Мета-информация
│       ├── scenes/P1_entrance.json  # Фаза 1: вход
│       ├── scenes/P2_steam.json     # Фаза 2: парная
│       ├── scenes/P3_pool.json      # Фаза 3: бассейн
│       ├── scenes/P4_rest.json      # Фаза 4: комната отдыха
│       ├── scenes/P5_climax.json    # Фаза 5: кульминация
│       ├── characters/ROLES.json    # Роли персонажей
│       └── environment/ATMOSPHERE.json
│
├── scripts/python/
│   ├── build_prompt_modular.py    # Python-сборщик промпта
│   ├── runtime_loader.py          # Загрузчик модульных персонажей
│   └── test_runtime_all.py        # Тесты
│
├── build_prompt_modular.sh        # Shell-скрипт для modular сборки
├── build_prompt_v3.sh             # Legacy скрипт (только старые монолитные)
└── PROMPT_MODULAR.txt             # Результат сборки (создаётся автоматически)
```

---

## Команды для разработчика

### Проверить, что все персонажи загружаются
```bash
python scripts/python/runtime_loader.py marina
python scripts/python/runtime_loader.py sergey
python scripts/python/runtime_loader.py kira
python scripts/python/runtime_loader.py maksim
python scripts/python/runtime_loader.py andrey_senior
```

### Проверить валидность JSON всех сценариев
```bash
python -c "import json, glob; [json.load(open(f)) for f in glob.glob('scenarios/**/*.json', recursive=True)]; print('All JSON valid')"
```

### Собрать архив для игры
```bash
# Скрипт автоматически создаст архив в рабочей директории
# См. README_MODULAR.md для инструкций
```

---

## Как работает сборка

1. **Сценарий** (`sauna_extended`) описывает: фазы, кто участвует, какие триггеры, безопасность
2. **Персонажи** (`personas/[id]/`) содержат: речь, инициативы, психологию, отношения
3. **Builder** (`build_prompt_modular.py`) загружает всё и собирает один `PROMPT_MODULAR.txt`
4. **LLM** читает промпт и генерирует речь в стиле Speech Matrix каждого персонажа

---

## Состояние обновления персонажей

| Персонаж | Speech Matrix | Initiatives | Activities | Status |
|----------|--------------|-------------|------------|--------|
| Kira | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Marina | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Sergey | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Maksim | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Andrey Senior | ✅ v2.0 | ✅ v2.0 | ✅ v2.0 | **Готов** |
| Andrey Junior | ❌ | ❌ | ❌ | **Нужен апдейт** |
| Olga | ❌ | ❌ | ❌ | **Нужен апдейт** |
| Egor | ❌ | ❌ | ❌ | **Нужен апдейт** |
| Female User | ❌ | ❌ | ❌ | Не требуется |
| User | ❌ | ❌ | ❌ | Не требуется |

---

## СТОП-слово и безопасность

- **СТОП** — мгновенный сброс всех персонажей на безопасные уровни
- **Г0** — NPC только реагируют
- **СТОП-слово** работает на любом уровне AG

---

*Последнее обновление: 2025-06-19*
*Версия системы: v3.0.0*
*Сценарий: sauna_extended*
