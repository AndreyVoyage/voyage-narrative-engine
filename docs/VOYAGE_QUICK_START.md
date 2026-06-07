# VOYAGE QUICK START — Быстрый старт v1.0

> **Для кого:** Пользователи, которые успешно прошли тест и готовы к регулярным сессиям.
> **Время:** 5 минут на подготовку, 30-120 минут на сессию.
> **Платформа:** Kimi (рекомендуется), DeepSeek, Ollama (local).

---

## 🚀 Быстрый старт (3 шага)

### Шаг 1: Сборка PROMPT.txt (1 минута)

```bash
# В Termux или терминале
cd ~/voyage-narrative-engine
./build_prompt.sh sauna_quartet kira sergey marina

# Результат: PROMPT.txt (~2300 токенов)
```

**Или вручную:**
```bash
cat core/VOYAGE_NARRATIVE_CORE_v2.md     personas/KIRA_MODULE_v14.json     personas/SERGEY_MODULE_v4.json     personas/MARINA_MODULE_v2.json     scenarios/SCENARIO_SAUNA_QUARTET.json     state/STATE_TEMPLATE_v2.json     > PROMPT.txt
```

### Шаг 2: Запуск сессии (1 минута)

1. **Откройте новый чат** в Kimi (https://kimi.moonshot.cn).
2. **Вставьте весь PROMPT.txt** в первое сообщение.
3. **Отправьте.** LLM сгенерирует первый ход (вход в сауну).
4. **Играйте.** Вводите действия, реплики, команды.

### Шаг 3: Сохранение прогресса (3 минуты)

После сессии:
```bash
# 1. Скопируйте ключевые события из чата в файл
nano session_notes.txt

# 2. Обновите STATE
./update_state.sh session_notes.txt

# 3. Закоммитьте в git
git add state/ session_notes.txt
git commit -m "session: sauna with kira/sergey/marina, kira reached U3-A"
git push origin main
```

---

## 🎮 Команды во время сессии

| Команда | Когда использовать | Эффект |
|---------|-------------------|--------|
| `@статус` | Хотите проверить состояние | Показывает уровни, ВСНО, флаги |
| `@визуал` | Хотите картинку | Генерирует промпт для Qwen/SD |
| `СТОП` / `ХВАТИТ` | Что-то пошло не так | Emergency exit, все на безопасные уровни |
| `У3-Б` | Хотите ускорить дугу Киры | Переключает Киру на У3-Б (признание) |
| `ТГ3` | Хотите уязвимость | Переключает грань на 3 (открытость) |
| `@сброс` | После теста или ошибки | Возвращает персонажей к начальным уровням |

---

## 📁 Структура репозитория (минимальная)

```
voyage-narrative-engine/
├── build_prompt.sh          # Сборка PROMPT.txt
├── update_state.sh          # Обновление STATE после сессии
├── PROMPT.txt               # Текущий промпт (генерируется)
├── core/
│   └── VOYAGE_NARRATIVE_CORE_v2.md
├── personas/
│   ├── KIRA_MODULE_v14.json
│   ├── SERGEY_MODULE_v4.json
│   ├── MAKSIM_MODULE_v2.json
│   └── MARINA_MODULE_v2.json
├── scenarios/
│   └── SCENARIO_SAUNA_QUARTET.json
├── state/
│   └── STATE_TEMPLATE_v2.json
└── knowledge/
    ├── schemas/persona_schema_v3.2.json
    ├── tec/TEC_DICTIONARY.md
    └── rules/CROSS_PERSONA_RULES.md
```

---

## 🔄 Рабочий цикл (Workflow)

```
[Сессия N] → [Сохранить notes] → [Обновить STATE] → [Git commit]
     ↑                                              ↓
     └──────────── [Собрать PROMPT.txt] ←───────────┘
```

**Каждая сессия:**
1. Собираете PROMPT.txt (с актуальным STATE).
2. Загружаете в Kimi.
3. Играете.
4. Сохраняете notes.
5. Обновляете STATE.
6. Git commit.

---

## 🆘 Troubleshooting

| Проблема | Решение |
|----------|---------|
| **LLM "забыл" формат** | Напишите: «Вернися к ФМДР. Мысли в скобках, действия в звёздочках, речь в кавычках» |
| **Кира "скачет" по уровням** | Напишите: «Кира, оставайся на У2-А. Не меняй уровень без моей команды» |
| **Марина слишком смелая** | Напишите: «Марина, ты на У1-Б. Ты скромная. Вернися к себе» |
| **Сергей не avoidant** | Напишите: «Сергей, ты avoidant. Отстранись. Минимум слов» |
| **Сессия слишком длинная** | Скажите «СТОП», затем начните новый чат с обновлённым STATE |
| **PROMPT.txt не влезает** | Уберите MARINA_MODULE (играйте только с Кирой и Сергеем) |

---

## 🎯 Следующие шаги (опционально)

| Шаг | Что | Сложность |
|-----|-----|-----------|
| **Добавить Максима** | Включить MAKSIM_MODULE в сцену | Легко — добавьте в build_prompt.sh |
| **Новый сценарий** | Создать SCENARIO_PROMENADE.json | Средне — скопируйте sauna, измените локацию |
| **Локальная LLM** | Ollama + llama3:70b | Средне — требует 32GB RAM |
| **Оптимизация** | Сократить PROMPT до 1500 токенов | Средне — уберите speech_profile, оставьте только current level |
| **Android/Termux** | Играть на телефоне | Легко — Termux + git + nano |
| **Визуал** | Генерация картинок через Qwen Studio | Легко — используйте @визуал |

---

## 📞 Поддержка

- **Репозиторий:** https://github.com/AndreyVoyage/voyage-narrative-engine
- **Документация:** `docs/VOYAGE_FRAMEWORK_MASTER_DOCUMENT_v3.md`
- **Тесты:** `TEST_PROMPT.md` (для проверки корректности)

---

*Voyage Narrative Engine v2.0 | Quick Start v1.0 | 2026-06-07*
