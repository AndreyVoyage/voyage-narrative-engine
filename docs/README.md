# 📦 VOYAGE NARRATIVE ENGINE v1.0

## Архитектура

```
voyage-narrative/
├── core/
│   └── VOYAGE_NARRATIVE_CORE.md      # ⚙️ Ядро системы (мнемоники, механики, протоколы)
├── personas/
│   ├── KIRA_MODULE.json              # 🧝‍♀️ Кира v11 (7 уровней, переменные)
│   └── SERGEY_MODULE.json            # 🏋️ Сергей v2 (харизматичный хищник)
├── state/
│   └── STATE_TEMPLATE.json           # 📊 Шаблон состояния сессии
├── scenarios/
│   └── SCENARIO_MATRIX.json          # 🎲 Генеративная сетка (10×10×10)
├── memory/
│   └── MEMORY_PROTOCOL.md            # 🧠 Память, суммаризация, символизация
├── visual/
│   └── QWEN_ADAPTER.md               # 🎨 Автоматический визуальный мост
├── governance/
│   └── AUTONOMY_GOVERNOR.md          # ⚖️ Autonomy Governor (AG 0-4)
├── living_world/
│   └── LIVING_WORLD.md               # 🌍 Proactive mode, NPC-to-NPC
└── legacy/
    ├── Промпт_Кира_v11_Семь_Врат.md  # 📜 Полный текстовый промпт Киры
    ├── Промпт_Сергей_v2_Улыбающийся_Хищник.md
    ├── Qwen_Prompt_Kira_Luxury_Dress.md
    └── Qwen_Prompt_Sergey_Open_Shirt.md
```

## Быстрый старт

1. **Ядро:** Прочитать `VOYAGE_NARRATIVE_CORE.md` — это мозг системы.
2. **Персонажи:** Отредактировать `KIRA_MODULE.json` и `SERGEY_MODULE.json` под свои нужды.
3. **Состояние:** Скопировать `STATE_TEMPLATE.json` в `STATE.json` и начать сессию.
4. **Сценарий:** Выбрать или сгенерировать сценарий из `SCENARIO_MATRIX.json`.
5. **Сборка:** Собрать PROMPT.txt = CORE + PERSONAS + STATE + SCENARIO.
6. **Запуск:** Отправить PROMPT.txt в нейросеть.

## Ключевые инновации

- **7 уровней накала** (У1-У7) с фазовыми переходами
- **Мнемоническая система** для сокращения токенов (К, Я, У, ТГ, ФМДР, АД, АС, П, В, Г)
- **JSON-модули** персонажей с переменными (возраст, волосы, уровень — всё меняется)
- **Генеративная сетка** сценариев (процедурная генерация из 10 параметров)
- **Память** (Event Log + State + Summary + Symbol-коды)
- **Autonomy Governor** (4 уровня автономии + Safety Check для У6)
- **Живой мир** (proactive events, NPC-to-NPC)
- **Автоматический Qwen-промпт** в конце каждой сцены

## Сокращение токенов

- Старая система: ~15 000 токенов на старт
- Новая система: ~3000 токенов (CORE 2000 + PERSONA 500 + STATE 300 + SCENARIO 200)
- Экономия: **80%**

## Версионирование

- Ядро: semver (v1.0.0)
- Персонажи: semver (Kira@11.0.0, Sergey@2.0.0)
- State: timestamp + session_id

---

> **Создано:** 2026-06-06
> **Автор:** Voyage Framework Team
> **Лицензия:** MIT (для личного использования)
