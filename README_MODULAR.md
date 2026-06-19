# Voyage Narrative Engine — Модульная архитектура v3.0

## Обзор

Система перешла с монолитных JSON-файлов персонажей на **модульную архитектуру**:
- Персонажи разбиты на 12+ модулей (`speech/`, `autonomous/`, `psychology/`, `levels/`, ...)
- Сценарии разбиты на фазы (`scenes/P1.json`, `scenes/P2.json`, ...)
- Промпт собирается на лету через `runtime_loader.py`

---

## Архитектура: как всё связано

```
┌──────────────────────────────────────────────────────────┐
│  СЦЕНАРИЙ (scenarios/sauna_extended/)                      │
│  • Фазы (P1-P5)                                            │
│  • Роли персонажей (characters/ROLES.json)                 │
│  • Триггеры, атмосфера, безопасность                        │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  RUNTIME LOADER (scripts/python/runtime_loader.py)         │
│  • Загружает INDEX.json персонажа                          │
│  • Загружает все модули: speech, autonomous, psychology    │
│  • Собирает единый persona-объект (как старый монолит)      │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  PROMPT BUILDER (scripts/python/build_prompt_modular.py)   │
│  • Загружает сценарий + всех персонажей                    │
│  • Форматирует Speech Matrix, Initiatives, Activities      │
│  • Собирает PROMPT_MODULAR.txt                             │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  LLM (Kimi, Claude, GPT...)                                │
│  • Читает промпт как системные инструкции                 │
│  • Генерирует речь по Speech Matrix (тон, темп, словарь)  │
│  • Инициирует действия по Initiatives (probability, triggers)│
└──────────────────────────────────────────────────────────┘
```

---

## Структура модуля персонажа

```
personas/[id]/
├── INDEX.json                    # Манифест: версия, модули, совместимые сценарии
├── core/
│   └── IDENTITY.json             # Визуальная сигнатура, анатомический якорь
├── psychology/
│   ├── BASE.json                 # Core conflict, стыд, триггеры, копинг
│   ├── ATTACHMENT.json           # Стиль привязанности
│   ├── AROUSAL.json              # Сексуальное возбуждение
│   ├── PLASTICITY.json           # Пластичность
│   └── TEC.json                # Тревога, эмоция, когниция
├── speech/
│   └── SPEECH_MATRIX.json        # ⭐ Речевая матрица 14×6 (новое!)
├── autonomous/
│   ├── INITIATIVE.json           # ⭐ Инициативы NPC (новое!)
│   ├── ACTIVITIES.json           # ⭐ Активности (новое!)
│   └── TEMPLATES.json            # ⭐ Шаблоны сообщений (новое!)
├── dynamics/
│   ├── REACTION_PATTERNS.json    # Как реагирует на действия
│   ├── LEVEL_LOCK_MATRIX.json    # Level locks (LLM)
│   ├── EMOTIONAL_INFLUENCE_MATRIX.json
│   └── CONFLICT_RESOLUTION_MATRIX.json
├── memory/
│   ├── TRUST.json                # Доверие по персонажам
│   ├── ATTRACTION.json           # Влечение
│   ├── FLAGS.json                # Флаги событий
│   ├── HISTORY.json              # История взаимодействий
│   └── EMOTIONAL_ANCHORS.json    # Эмоциональные якоря
├── relationships/
│   └── MATRIX.json               # Матрица отношений
├── environment/
│   ├── STATE_TRIGGERS.json       # Триггеры состояния
│   └── SPATIAL_BEHAVIOR.json    # Пространственное поведение
├── safety/
│   └── PROTOCOL.json             # Безопасность, STOP, hard limits
├── visual/
│   ├── PROMPT_BASE.json          # Базовый промпт для генерации
│   └── GENERATION_HISTORY.json   # История генераций
├── sexology/
│   ├── RESPONSE_CYCLE.json       # Сексуальный цикл ответа
│   ├── EROTIC_SCRIPTS.json       # Эротические скрипты
│   ├── DYSPHORIA_AND_SHAME.json  # Дисфория и стыд
│   └── FANTASY_VS_REALITY.json   # Фантазия vs реальность
├── levels/
│   ├── U1-A.json ... U7-B.json   # 14 подуровней (VSCNO, internal_state, ad_availability)
└── meta/
    └── META.json                 # Chat display name, algorithms, volume
```

---

## Speech Matrix v2.0

Каждый подуровень (U1-A ... U7-B) имеет 6 параметров:

| Параметр | Описание | Пример U2-A | Пример U4-B |
|----------|----------|-------------|-------------|
| **ton** | Тон речи | «хриплый, вульгарный, сексуальный» | «раскрепощённый, уязвимый, восторженный» |
| **tempo** | Темп/ритм | «средний, рваный» | «ускоренный, с дыханием» |
| **vocabulary** | Лексика | «вульгарный, 'кричи', 'ещё'» | «поэтичный, чувственный, 'почему'» |
| **thought_length** | Длина мысли | «короткие 3-5 слов» | «длинные 8-10 слов» |
| **action_detail** | Действия тела | «поправляет волосы, кусает губу» | «прижимается, руки трясутся» |
| **signature_phrases** | Образцовые фразы | 5 фраз на уровень | 5 фраз на уровень |

**Важно:** фразы — это **ОБРАЗЦЫ СТИЛЯ**, не готовые реплики. LLM генерирует новые фразы, но в том же тоне, темпе, лексике.

---

## Autonomous Initiatives v2.0

Персонажи могут действовать **без команды пользователя** при AG≥3.

Структура INITIATIVE.json:
```json
{
  "initiative_types": {
    "shy_approach": {
      "description": "Прячется, выглядывает",
      "probability_by_ag": {"AG1": 0.1, "AG2": 0.2, "AG3": 0.3, "AG4": 0.4},
      "triggers": ["user_nearby", "safe_space"],
      "VSCNO_mapping": {"U1-A": "U1-B", "U2-A": "U2-B"}
    }
  },
  "initiative_rules": {
    "default_ag": "AG1",
    "max_initiatives_per_scene": 2,
    "cooldown_seconds": 45,
    "priority": ["shy_approach", "observation_report"]
  }
}
```

---

## Сценарий: как он описывает игру

Сценарий — это **не диалоги**, а **структура**:
- `phases/` — фазы (P1: вход, P2: парная, P3: бассейн...)
- `characters/ROLES.json` — кто участвует, их роли, целевые уровни
- `environment/ATMOSPHERE.json` — температура, влажность, звук, свет
- `dynamics/CROSS_CHARACTER.json` — как персонажи влияют друг на друга
- `safety/SAFETY.json` — проверки безопасности

---

## Как добавить нового персонажа

1. Создать папку `personas/new_id/`
2. Создать `INDEX.json` с манифестом
3. Создать `core/IDENTITY.json`, `psychology/BASE.json`
4. Создать `levels/U1-A.json` ... `U7-B.json`
5. Создать `speech/SPEECH_MATRIX.json` (см. Kira как образец)
6. Создать `autonomous/INITIATIVE.json`, `ACTIVITIES.json`, `TEMPLATES.json`
7. Добавить в `relationships/MATRIX.json`
8. Добавить в `safety/PROTOCOL.json`
9. Обновить `INDEX.json` → добавить `sauna_extended` в `compatible_scenarios`

---

## Как добавить новый сценарий

1. Создать папку `scenarios/my_scenario/`
2. Создать `core/INDEX.json` — манифест
3. Создать `scenes/` — фазы
4. Создать `characters/ROLES.json` — кто участвует
5. Создать `structure/` — timeline, locations
6. Создать `environment/ATMOSPHERE.json`
7. Создать `safety/SAFETY.json`
8. Создать `dynamics/CROSS_CHARACTER.json`
9. Создать `audit_scenario.py` — аудитор

---

## Готовые персонажи (5/10)

| Персонаж | Описание | Готовность |
|----------|----------|------------|
| Kira | Стальная бабочка, тревожный стиль | ✅ Speech + Initiatives + Activities |
| Marina | Солнечная пикси, робкая, нежная | ✅ Speech + Initiatives + Activities |
| Sergey | Молчаливый зеркало, саркастичный | ✅ Speech + Initiatives + Activities |
| Maksim | Мягкий великан, fearful-avoidant | ✅ Speech + Initiatives + Activities |
| Andrey Senior | Авторитетный, философский, 50+ | ✅ Speech + Initiatives + Activities |
| Andrey Junior | Молодой, беспечный | ❌ Нужен speech + initiatives |
| Olga | Незнакомка, интрига | ❌ Нужен speech + initiatives |
| Egor | Брат Сергея, защитник | ❌ Нужен speech + initiatives |
| Female User | Женский аватар | ❌ Не требуется |
| User | Пользователь | ❌ Не требуется |

---

## Чейнлог (последние 6 коммитов)

```
5b7500a feat: modular prompt builder + updated v3.sh + Kira initiative fix + P2 steam JSON fix
74b05ca feat: update runtime_loader v2.3 to load speech and initiative modules
31a91b1 feat: speech matrices + autonomous initiatives for all 4 sauna personas
52ee9b9 persona(kira): add speech matrix + initiative system + richer autonomy
94105b6 test: add S8 Scenario Auditor + PASS report for sauna_extended
29427b0 scenario: add modular sauna_extended v3.0.0 with Andrey Senior
```

---

## Ссылки

- `BUILD_COMMANDS.md` — команды для сборки промптов
- `scripts/python/build_prompt_modular.py` — сборщик промпта
- `scripts/python/runtime_loader.py` — загрузчик модульных персонажей
- `personas/` — все персонажи
- `scenarios/sauna_extended/` — сценарий сауны

---

*Документ: README_MODULAR.md*
*Версия: v3.0.0*
*Дата: 2025-06-19*
