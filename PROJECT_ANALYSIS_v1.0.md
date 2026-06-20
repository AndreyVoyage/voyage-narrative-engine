# Анализ Voyage Narrative Engine (VNE)
**Дата:** 2026-06-20  
**Анализатор:** AI-агент по AGENTS.md  
**Объект:** репозиторий `voyage-narrative-engine` (корневой путь `C:\DEV\Narrative\voyage-narrative-engine`)

---

## 1. Резюме

Проект находится в **переходном состоянии** от монолитных JSON-модулей к модульной директорийной архитектуре `personas/[name]/`. Основные архитектурные документы (`AGENTS.md`, `core/*`, `docs/01-12`, `knowledge_base/`) **актуальны и консистентны**. Роли R1–R8 присутствуют и задокументированы. Модульная структура для 9 персонажей (kira, andrey_senior, andrey_junior, sergey, marina, maksim, egor, olga, female_user, user) создана, **но не подключена к автоматической сборке** (AGENTS.md, раздел «Известные проблемы»).

**Критических блокеров нет**, но выявлено **7 категорий проблем**, включая нарушения JSON Schema, устаревшие пути в скриптах сборки, дублирование схем и неполноту legacy-модулей.

---

## 2. Что работает корректно

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| **AGENTS.md** | ✅ Актуален | Приоритетный источник правды, версия 2026-06-17 |
| **Core Baseline** | ✅ Консистентен | VSCNO, AD, Internal State, Memory — суммы и связи корректны |
| **Роли R1–R8** | ✅ Присутствуют | Файлы на месте, версии соответствуют AGENTS.md |
| **Модульная структура** | ✅ Создана | 10 персонажей с `INDEX.json`, `ASSEMBLY.md`, подпапками |
| **JSON-валидность монолитов** | ✅ | Все `.json` в `personas/` парсятся без ошибок |
| **VSCNO в полных модулях** | ✅ | Kira, Sergey, Maksim, Marina, Egor — сумма = 10 |
| **Safety-протоколы** | ✅ Не ослаблены | `governance/` на месте, стоп-слова и Autonomy Governor сохранены |
| **Имена файлов** | ✅ Без пробелов | Проверка по всему репозиторию — пробелов нет |
| **Knowledge Base (R1–R6, S1–S8, Narrative)** | ✅ 25 файлов | Статус Complete по `STATUS.md` |

---

## 3. Проблемы и конфликты

### 3.1 `[CONFLICT]` Нарушения JSON Schema в монолитных модулях

Файл `schemas/persona_schema_v3_2_VOYAGE.json` требует:
- `id`: `^[A-Z_]+_v[0-9]+$`
- `version`: `^[0-9]+\.[0-9]+\.[0-9]+$`
- Поля: `internal_state`, `visual_data`, `memory`, `algorithms`, `safety`, `format`, `volume`, `engagement`, `transition_state`, `scenarios`, `vscno`
- `vscno` сумма = 10

| Модуль | Проблема | Статус |
|--------|----------|--------|
| `ANDREY_SENIOR_MODULE_v1.1.json` | `id` содержит точку (`v1.1`) | ❌ Не соответствует `^[A-Z_]+_v[0-9]+$` |
| `ANDREY_SENIOR_MODULE_v1.2.json` | `id` содержит точку (`v1.2`) | ❌ Не соответствует `^[A-Z_]+_v[0-9]+$` |
| `ANDREY_JUNIOR_MODULE_v2.1.json` | `id` содержит точку (`v2.1`); VSCNO сумма = **9** | ❌ Нарушение id + VSCNO |
| `OLGA_MODULE_v2_FIXED.json` | Имя файла `_v2_FIXED`, но `id` = `OLGA_MODULE_v2`; VSCNO сумма = **8** | ❌ Рассинхрон имени + VSCNO |
| `FEMALE_USER_MODULE.json` | `id` = `FEMALE_USER_001` (не `^[A-Z_]+_v[0-9]+$`); отсутствуют `internal_state`, `visual_data`, `algorithms`, `engagement`, `transition_state`, `scenarios`, `vscno` | ❌ Сильно неполный |
| `USER_MODULE.json` | `id` = `user_default` (не `^[A-Z_]+_v[0-9]+$`); отсутствуют `internal_state`, `visual_data`, `algorithms`, `engagement`, `transition_state`, `scenarios`, `vscno` | ❌ Сильно неполный |

**Рекомендация:** для `user_default` и `female_user` либо сделать отдельную упрощённую схему, либо дополнить до `v3_2_VOYAGE`. Для остальных — исправить `id` (убрать точки, привести к `v1`, `v2` и т.д.) и пересчитать VSCNO.

### 3.2 `[CONFLICT]` Дублирование и рассинхрон JSON Schema

Существует **две** схемы:
- `schemas/persona_schema_v3_2_VOYAGE.json` — `additionalProperties: true` (мягкая)
- `knowledge/schemas/persona_schema_v3.2.json` — `additionalProperties: false`, требует `autonomous`, `state_triggers`, `regression_triggers`

Это приводит к неопределённости: валидировать по какой схеме? `AGENTS.md` указывает на `schemas/persona_schema_v3_2_VOYAGE.json` как источник правды, но `knowledge/schemas/` — более строгая.

**Рекомендация:** слить в единый файл, удалить дубль из `knowledge/schemas/` или явно задокументировать различие.

### 3.3 `[CONFLICT]` Устаревшие пути в скриптах сборки

| Скрипт | Устаревший путь | Реальное положение |
|--------|------------------|-------------------|
| `tools/assemble.sh` | `core/VOYAGE_NARRATIVE_CORE.md` | **Отсутствует** |
| `tools/assemble.sh` | `personas/KIRA_MODULE.json` | **Отсутствует** (есть `KIRA_MODULE_v15.json`) |
| `tools/assemble.sh` | `personas/SERGEY_MODULE.json` | **Отсутствует** (есть `SERGEY_MODULE_v4.json`) |
| `build_prompt_v3.sh` | `core/VOYAGE_NARRATIVE_CORE_v2.md` | **Отсутствует** |
| `build_prompt_v3.sh` | `personas/KIRA_MODULE_v12.json` | **Отсутствует** (v15) |
| `build_prompt_v3.sh` | `personas/SERGEY_MODULE_v3.json` | **Отсутствует** (v4) |
| `build_prompt_v3.sh` | `personas/MARINA_MODULE_v1.1.json` | **Отсутствует** (v2) |
| `build_prompt_v3.sh` | `personas/MAXIM_MODULE_v1.json` | **Отсутствует** (MAKSIM_MODULE_v2.json) |
| `build_prompt_v3.sh` | `memory/MEMORY_PROTOCOL_v2.md` | **Отсутствует** |
| `build_prompt_v3.sh` | `visual/QWEN_ADAPTER_v2.md` | **Отсутствует** |
| `build_prompt_v3.sh` | `scenarios/SCENARIO_MARINA.json` | **Отсутствует** |
| `build_prompt_v3.sh` | `living_world/PROACTIVE_MODE.md` | **Отсутствует** (есть `LIVING_WORLD.md`) |

**Рекомендация:** провести аудит всех `.sh` и обновить пути, либо задокументировать, что `build_prompt_v3.sh` — legacy, и использовать `build_prompt_modular.sh` + `build_prompt_modular.py`.

### 3.4 `[CONFLICT]` Артефакт `docs/08_INDEX.md` вместо `08_INDEX.json`

Файл `docs/08_INDEX.md` содержит JSON-контент для `INDEX.json` Киры, но:
- Сохранён как `.md`, а не `.json`
- Версия внутри `2.1.0`, тогда как актуальный `personas/kira/INDEX.json` = `2.2.0`

**Рекомендация:** удалить или переименовать в `08_INDEX.json` и обновить версию до `2.2.0`.

### 3.5 `[CONFLICT]` Рассинхрон `knowledge/` и `knowledge_base/`

`AGENTS.md` описывает структуру с `knowledge/` (cross-persona, TEC, schema). Фактически:
- `knowledge/` — содержит `rules/`, `schemas/`, `tec/` (3 файла)
- `knowledge_base/` — содержит 25 KB-файлов по ролям R1–R6, S1–S8, Narrative

`STATUS.md` отслеживает `knowledge_base/`. `AGENTS.md` не упоминает `knowledge_base/`. Это не нарушение, но создаёт двойственность.

**Рекомендация:** в `AGENTS.md` добавить `knowledge_base/` как официальную директорию.

### 3.6 `[CONFLICT]` `roles/` содержит роли, не перечисленные в AGENTS.md

`AGENTS.md` перечисляет: R1–R8, COMP, V, SE, NE, SM, PA, TD, GCA, IE, MIA. Фактически в `roles/` есть дополнительные файлы:
- `ROLE_6_PERSONA_ARCHITECT_v2.2_PROMPT.md` (вероятно, предыдущая версия R6)
- `ROLE_NARRATIVE_EDITOR_v1.1_PROMPT.md`
- `ROLE_SESSION_FINALIZER_v2.0_PROMPT.md`
- `ROLE_STATE_MANAGER_v1.0_PROMPT.md`
- `ROLE_VISUAL_EXTRACTOR_v1.0_PROMPT.md`
- `ROLE_VISUAL_PHYSIOGNOMIST_v1.0_PROMPT.md`
- `SESSION_EXTRACTOR_AND_EDITOR_v2.1-rc_PROMPT.md`
- `VISUAL_ANATOMIST_PROMPT.md`
- `PERSONA_ANALYST_v1.0_PROMPT.md`
- `DATA_COMPRESSOR_FOR_HANDOFF_v1.0_PROMPT.md`
- `PROMPT_COMPRESSOR_v1.0_PROMPT.md`
- `AGENT_TERMUX_DEPLOY_v2.md`

Это **не запрещено** (они существовали до текущего правила), но создаёт путаницу.

**Рекомендация:** добавить в `AGENTS.md` раздел «Legacy / Дополнительные роли» с перечислением существующих файлов, чтобы не считать их новыми.

### 3.7 `[CONFLICT]` Отсутствие `core/VOYAGE_NARRATIVE_CORE.md` (v2)

Ни `core/VOYAGE_NARRATIVE_CORE.md`, ни `core/VOYAGE_NARRATIVE_CORE_v2.md` не существуют. `build_prompt_v3.sh` и `tools/assemble.sh` пытаются их загрузить. Это делает **legacy-скрипты неработоспособными**.

**Рекомендация:** либо создать `core/VOYAGE_NARRATIVE_CORE.md` как единый baseline, либо задокументировать, что сборка идёт только через `build_prompt_modular.sh`.

---

## 4. Рекомендации по приоритету

| Приоритет | Действие | Затронутые файлы |
|-----------|----------|----------------|
| **P0** | Исправить VSCNO в `ANDREY_JUNIOR_MODULE_v2.1.json` (сумма 9 → 10) и `OLGA_MODULE_v2_FIXED.json` (сумма 8 → 10) | `personas/*.json` |
| **P0** | Дополнить `USER_MODULE.json` и `FEMALE_USER_MODULE.json` до `v3_2_VOYAGE` или создать отдельную упрощённую схему | `personas/USER_MODULE.json`, `personas/FEMALE_USER_MODULE.json` |
| **P1** | Обновить `id` в `ANDREY_SENIOR_*` и `ANDREY_JUNIOR_*` (убрать точки) | `personas/ANDREY_*_MODULE_*.json` |
| **P1** | Синхронизировать/слить JSON-схемы (`schemas/` vs `knowledge/schemas/`) | `schemas/persona_schema_v3_2_VOYAGE.json`, `knowledge/schemas/persona_schema_v3.2.json` |
| **P1** | Обновить `build_prompt_v3.sh` и `tools/assemble.sh` или пометить как `legacy` | `build_prompt_v3.sh`, `tools/assemble.sh` |
| **P2** | Создать `core/VOYAGE_NARRATIVE_CORE.md` (единый runtime baseline) | `core/` |
| **P2** | Привести `docs/08_INDEX.md` в порядок (json + версия) | `docs/08_INDEX.md` |
| **P2** | Задокументировать `knowledge_base/` в `AGENTS.md` | `AGENTS.md` |
| **P3** | Добавить в `AGENTS.md` раздел legacy-ролей | `AGENTS.md`, `roles/` |
| **P3** | Проверить `build_prompt_modular.py` + `runtime_loader.py` на полноту загрузки модульных персон (проверка, что все `required: true` файлы из `INDEX.json` существуют) | `scripts/python/*.py` |

---

## 5. Метрики репозитория

| Метрика | Значение |
|---------|----------|
| Всего файлов (кроме `.git`) | ~260+ |
| Монолитных JSON-модулей | 11 |
| Модульных директорий персон | 10 |
| Ролевых промптов | 25 |
| Документов `docs/` | 32 |
| Core baseline | 4 файла |
| Knowledge base | 25 файлов |
| Сценариев JSON | 20+ |
| Скриптов сборки | 7+ |
| Отсутствующих файлов по скриптам | 12+ |
| Нарушений schema | 6 модулей |
| Несовпадений VSCNO | 2 модуля |

---

*Отчёт сформирован по правилам `AGENTS.md`. Проблемы отмечены как `[CONFLICT]` для последующей обработки.*
