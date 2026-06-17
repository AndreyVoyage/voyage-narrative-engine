# AGENTS.md — Voyage Narrative Engine

> **Читать сначала.** Этот файл — единый источник правды для AI-агентов, работающих с репозиторием Voyage Narrative Engine (VNE).
> Если инструкции здесь противоречат `README.md` или другим файлам — приоритет у этого файла.

---

## Общее описание проекта

**Voyage Narrative Engine (VNE)** — спецификационный репозиторий процедурного генератора интерактивных романтических/эротических сценариев с глубокой психологической детализацией персонажей.

**Главная задача:** персонажи создаются через каскадный pipeline ролей R1–R8, хранятся в модульной структуре `personas/[name]/`, но при сборке runtime-сценария собираются в единый монофайл (JSON или COMPACT Markdown), который вместе с `PRELOAD_VNE_v3.2.1.md` загружается в чат LLM для ведения игры.

**Тип репозитория:** спецификационный. Здесь почти нет исполняемого кода. Основные артефакты — Markdown-спецификации, JSON-схемы, промпты ролей и модули персонажей.

**Рабочий язык:** русский для всего narrative-контента, механик, комментариев и внутриигрового текста. Идентификаторы кода и имён файлов — на английском или транслите.

---

## Что этот проект НЕ является

- ❌ Не `framework-voyage-v2`, не "AI-Native Engineering Operating System", не generic Python framework.
- ❌ Не веб-сервис — нет HTTP API, Docker, Kubernetes.
- ❌ Не игра с рендерером — визуалы генерируются отдельными image-generation промптами.
- ❌ Не полностью автоматизированный runtime — пользователь копирует собранный монофайл в чат с LLM.
- ❌ Не Python/Node/Rust/Go приложение — нет `pyproject.toml`, `package.json`, `Cargo.toml`.

---

## Источники правды (по приоритету)

1. `AGENTS.md` (этот файл)
2. `docs/VOYAGE_MASTER_DOCUMENT_v3.md`
3. `core/` — baseline-таблицы:
   - `core/VSCNO_BASELINE_TABLE.md`
   - `core/AD_AVAILABILITY_MATRIX.md`
   - `core/INTERNAL_STATE_BASELINE.md`
   - `core/MEMORY_BASELINE_TABLE.md`
4. `docs/01_MODULAR_ARCHITECTURE_v2.2.md`
5. `docs/02_MODULE_SPECS_v2.2.md`
6. `docs/03_ASSEMBLY_GUIDE_v2.1.md`
7. `docs/07_PERSONA_MODULAR_ARCHITECTURE.md`
8. `schemas/persona_schema_v3_2_VOYAGE.json`

**Не доверяй `README.md` как источнику архитектуры** — он может быть устаревшим.

---

## Структура репозитория

```
voyage-narrative-engine/
├── AGENTS.md                           # ← этот файл
├── README.md                           # быстрый старт для людей (может быть устаревшим)
├── core/                               # baseline-таблицы (VSCNO, AD, internal_state, memory)
├── docs/                               # архитектура, спецификации, глоссарий
├── governance/                         # автономия, safety-протоколы
├── knowledge/                          # cross-persona правила, TEC-словарь, JSON Schema
├── launch/                             # документация ролей R1–R6 для AI
├── legacy/                             # устаревшие артефакты
├── living_world/                       # proactive/offline события
├── personas/                           # модули персонажей
│   ├── KIRA_MODULE_v15.json            # монолит (runtime)
│   ├── SERGEY_MODULE_v4.json           # монолит (runtime)
│   └── kira/                           # модульная структура (разработка)
├── roles/                              # промпты ролей R1–R8 и вспомогательных ролей
├── scenarios/                          # сценарии для runtime
├── schemas/                            # JSON Schema
├── scripts/                            # bash/python/termux скрипты
├── sessions/                           # артефакты сессий
└── state/                              # стартовые state-шаблоны
```

### Важно: две параллельные системы модулей

1. **Монолитные JSON-модули** (`personas/*.json`) — используются для runtime в LLM-чате.
2. **Модульная директория** (`personas/kira/...`) — целевая архитектура для разработки, ещё не подключена к активным сборщикам.

---

## Роли (R1–R8)

| Роль | Файл | Статус |
|------|------|--------|
| R1 Persona Interviewer | `roles/ROLE_1_PERSONA_INTERVIEWER_v1.4_PROMPT.md` | ✅ |
| R2 Persona Psychologist | `roles/ROLE_2_PERSONA_PSYCHOLOGIST_v1.4_PROMPT.md` | ✅ |
| R3 Persona Sexologist | `roles/ROLE_3_PERSONA_SEXOLOGIST_v2.3_PROMPT.md` | ✅ |
| R4 Persona Linguist | `roles/ROLE_4_PERSONA_LINGUIST_v1.3_PROMPT.md` | ✅ |
| R5 Persona Physiognomist | `roles/ROLE_5_PERSONA_PHYSIOGNOMIST_v1.3_PROMPT.md` | ✅ |
| R6 Modular Architect | `roles/ROLE_6_MODULAR_ARCHITECT_v2.3.md` | ✅ |
| R7 Refactor | `roles/ROLE_7_REFACTOR_v1.0_PROMPT.md` | ⏳ (требуется создать/дописать) |
| R8 Auditor | `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md` | ⏳ (требуется создать/дописать) |

Дополнительные роли: `COMP`, `V`, `SE`, `NE`, `SM`, `PA`, `TD`, `GCA`, `IE`, `MIA` — используются только в существующих файлах, новые роли не создавать.

---

## Запреты (строго)

1. **Не создавать новые роли** — используй только существующие R1–R8, COMP, V, SE, NE, SM, PA, TD, GCA, IE, MIA.
2. **Не придумывать новые механики** — все формулы, форматы, блоки — только из существующих спецификаций.
3. **Не менять архитектуру** — если видишь противоречие, зафиксируй как `[CONFLICT]` и предложи уточнить, не исправляй сам.
4. **Не добавлять исполняемый код** (Python-пакеты, CI/CD, `pyproject.toml`, `package.json`) без явного разрешения — это спецификационный репозиторий.
5. **Не удалять файлы** без `[CONFLICT]`-метки и объяснения.
6. **Не доверять `README.md`** как источнику архитектуры.
7. **Не ослаблять safety-протоколы** — они описаны в `governance/` и встроены в модули.

---

## Конвенции

### Имена файлов

- **Пробелы в именах файлов недопустимы.** Всегда используй `_` или `-`.
- Примеры правильных имён:
  - `ROLE_6_MODULAR_ARCHITECT_v2.3.md` ✅
  - `07_PERSONA_MODULAR_ARCHITECTURE.md` ✅
  - `ROLE_6_MODULAR_ARCHITECT v2.3.md` ❌
  - `07_PERSONA_MODULAR_ARCHITECTURE .md` ❌

### VSCNO шкала

- **Канон:** значения `ВЛ`, `СТ`, `НЖ`, `ОГ` ∈ [0, 4], сумма = 10.
- **Устарело:** шкала [0, 10] — встречается в старых модулях, при миграции приводить к [0, 4].

### Формат ФМДР

Стандартный вывод LLM в runtime:
```
(Мысли: …) → *Действия: …* → «Речь: …»
```

### Версионирование

- Semantic versioning: `MAJOR.MINOR.PATCH`.
- При изменении persona-модуля — бампнуть его `version`.
- При изменении core baseline-таблиц — обновить версию в заголовке и `core_version` в state-файлах.
- При изменении state-файла — обновить `timestamp` ISO-8601.

---

## Проверки перед коммитом

1. Проверить JSON-синтаксис:
   ```bash
   python3 -m json.tool personas/KIRA_MODULE_v15.json > /dev/null && echo "OK"
   ```
2. Запустить интеграционные тесты:
   ```bash
   python3 integration_test.py
   ```
3. Убедиться, что VSCNO суммируется в 10.
4. Убедиться, что нет пробелов в именах новых файлов.
5. Убедиться, что `AGENTS.md` не противоречит изменениям.

---

## Безопасность

- **Стоп-слова:** `СТОП`, `ХВАТИТ`, `КРАСНАЯ КАРТОЧКА` — немедленная деэскалация.
- **Autonomy Governor:** `Г0`–`Г4` контролирует инициативу NPC.
- **U6:** переход на уровень U6 может требовать явного подтверждения в зависимости от AG.
- **Hard limits:** не-консенсуальное насилие, принуждение, несовершеннолетние — блокируются.

**Не удалять, не ослаблять и не обходить safety-механизмы.**

---

## Известные проблемы репозитория

- Скрипты сборки (`tools/assemble.sh`, `build_prompt_v3.sh`) ссылаются на устаревшие пути. Перед использованием проверять существование файлов.
- Модульная структура `personas/kira/` пока не подключена к автоматической сборке runtime-промпта.
- `README.md` содержит устаревшие ссылки на файлы.

---

*Последнее обновление: 2026-06-17*
