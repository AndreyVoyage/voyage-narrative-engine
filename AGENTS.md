# AGENTS.md — Voyage Narrative Engine

> **Читать сначала.** Этот файл — единый источник правды для AI-агентов, работающих с репозиторием Voyage Narrative Engine (VNE).
> Если инструкции здесь противоречат `README.md`, `README_MODULAR.md`, `BUILD_COMMANDS.md` или другим файлам — приоритет у этого файла.

---

## Общее описание проекта

**Voyage Narrative Engine (VNE)** — спецификационный репозиторий для процедурной генерации интерактивных романтических/эротических narrative-сценариев с глубокой психологической детализацией персонажей.

**Главная задача:** персонажи и сценарии создаются через каскадный pipeline ролей R1–R8, хранятся в модульной структуре `personas/[id]/`, а при сборке runtime-сценария собираются в монофайл (JSON или COMPACT Markdown), который загружается в чат LLM для ведения игры.

**Управление разработкой:** VNE является managed project под Voyage Framework — external dev-OS для задач, quality gates и аудита. Framework не является story runtime и не смешивается с VNE persona pipeline.

**Тип репозитория:** спецификационный. Основные артефакты — Markdown-спецификации, JSON-модули, промпты ролей и модули персонажей. Исполняемый код — только вспомогательные Python- и Bash-утилиты для сборки, валидации и постобработки сессий.

**Три слоя (не смешивать в одной задаче):**
1. **VNE Content / Persona / Narrative Runtime** — `personas/`, `scenarios/`, `roles/` (R1–R8), `core/`. Runtime: пользователь копирует собранный промпт в LLM-чат.
2. **Voyage Framework Dev-OS** — `.voyage/` (config scaffold), `tools/vne_adapter.py` (pass-through shim). External dev-OS, не story runtime.
3. **N5 RenPy / JSON Technical Track** — `novel/`, `docs/narrative/`, `tools/vne_to_renpy/`. Active shadow track, не formalized в `.voyage/project.yaml`.

**Рабочий язык:** русский для всего narrative-контента, механик, комментариев и внутриигрового текста. Идентификаторы кода и имён файлов — на английском или транслите.

---

## Что этот проект НЕ является

- ❌ Не веб-сервис — нет HTTP API, Docker, Kubernetes.

- ❌ Не игра с рендерером — визуалы генерируются отдельными image-generation промптами.
- ❌ Не полностью автоматизированный runtime — пользователь копирует собранный монофайл в чат с LLM.
- ❌ Не Python/Node/Rust/Go приложение в корне — в корне нет `pyproject.toml`, `package.json`, `Cargo.toml`.
- ❌ Не generic AI-OS — VNE использует Voyage Framework как external dev-OS для управления задачами и quality gates, но Framework не является частью repo и не является story runtime.

---

## Integration Boundary: три слоя VNE

VNE repo содержит три orthogonal слоя. Агент должен знать, в каком слое он работает, и не смешивать их.

### Слой 1: VNE Content / Persona / Narrative Runtime
- Персонажи (`personas/`), сценарии (`scenarios/`), роли (`roles/` R1–R8), core baseline (`core/`).
- Runtime: пользователь копирует собранный промпт в LLM-чат (Kimi mobile, 200K tokens).
- Главный инструмент: `build_prompt_modular.py`.
- Не требует Framework для работы.

### Слой 2: Voyage Framework Dev-OS
- External dev-OS для управления задачами, quality gates, аудитом.
- `.voyage/` — tracked config scaffold (`project.yaml`, `roles.yaml`, `task_templates`).
- `tools/vne_adapter.py` — optional pass-through shim (fallback на прямые Python-скрипты).
- Chronicler/events не инициализированы в этом clone.
- Framework ≠ story runtime. Framework не генерирует narrative.

### Слой 3: N5 RenPy / JSON Technical Track
- Ren'Py проект в `novel/`, JSON contract в `docs/narrative/`.
- Shadow track: активен фактически, но не formalized в `.voyage/project.yaml`.
- Отдельный pipeline от persona/runtime.

### Role Namespaces (не смешивать)
| Namespace | Роли | Где описаны | Назначение |
|-----------|------|-------------|------------|
| Narrative R1–R8 | Interviewer, Psychologist, Sexologist... | `roles/ROLE_*` | Создание персонажей |
| Support | Session Finalizer, State Manager, Visual Extractor... | `roles/ROLE_*` | Вспомогательные narrative-роли |
| Dev-OS | `vne_canon_guard`, `vne_qa`, `vne_renpy_adapter`... | `.voyage/roles.yaml` | Управление задачами разработки |
| Engineering | Ren'Py Engine Specialist | `docs/narrative/roles/` | N5 implementation expertise |

**Важно:** `roles/` содержит **18+ файлов**, не только R1–R8. Перед созданием новой роли агент обязан проверить существующие role-файлы. AGENTS.md-запрет «не плодить роли» относится к narrative pipeline, а не к dev/workflow-ролям.
Полный role registry — отдельная задача Q1, не P0B.

### Cross-layer rules
1. Не запускать `voyage init` без явного approval.
2. Не коммитить `.voyage/*.db`, `.voyage/*.jsonl`, `.voyage/audit*`.
3. Не смешивать persona/runtime task с N5 RenPy task.
4. Не добавлять `pyproject.toml` в корень VNE.
5. Не formalize N5 в `.voyage/project.yaml` без отдельного approval / отдельной задачи.

---
## Источники правды (по приоритету)

1. `AGENTS.md` (этот файл).
2. `.voyage/project.yaml` — project config, canonical sources, quality gates.
2a. `FRAMEWORK_VNE_INTEGRATION.md` — boundary между VNE и Voyage Framework.
3. `docs/VOYAGE_MASTER_PLAN_v1.0.md` — стратегия развития, дорожная карта, приоритеты.
4. `docs/VOYAGE_MASTER_DOCUMENT_v3.md` — архитектурная vision.
4a. `docs/narrative/NARRATIVE_ROADMAP.md` — N5 RenPy/JSON track roadmap.
4b. `docs/narrative/N5F_HYBRID_JSON_PATH_DECISION.md` — JSON contract decision.
4c. `docs/narrative/NARRATIVE_FUTURE_TRACKS_v1.md` — future tracks: Character Aside, Voice Layer, N6 planning.
5. `core/` — baseline-таблицы:
   - `core/VSCNO_BASELINE_TABLE.md`
   - `core/AD_AVAILABILITY_MATRIX.md`
   - `core/INTERNAL_STATE_BASELINE.md`
   - `core/MEMORY_BASELINE_TABLE.md`
6. `docs/01_MODULAR_ARCHITECTURE_v2.2.md`
7. `docs/02_MODULE_SPECS_v2.2.md`
8. `docs/03_ASSEMBLY_GUIDE_v2.1.md`
9. `docs/07_PERSONA_MODULAR_ARCHITECTURE.md`
10. `schemas/persona_schema_v3_2_VOYAGE.json`

**LEGACY (не использовать как источник правды):**
- `SPEC_PART_1_2.md` — заменён на `docs/01_MODULAR_ARCHITECTURE_v2.2.md` + `docs/VOYAGE_MASTER_DOCUMENT_v3.md`.
- `SPEC_PART_3.md` — заменён на `docs/VOYAGE_MASTER_DOCUMENT_v3.md` + `docs/03_ASSEMBLY_GUIDE_v2.1.md`.
- `PRELOAD_VNE_v3.2.1.md` — устарел; текущий runtime использует `build_prompt_modular.py`.

**Не доверяй `README.md` и `README_MODULAR.md` как источнику архитектуры** — они могут быть устаревшими.

---

## Структура репозитория

```
voyage-narrative-engine/
├── AGENTS.md                         # ← этот файл
├── README.md                         # быстрый старт для людей (может быть устаревшим)
├── README_MODULAR.md                 # модульная архитектура (может быть устаревшим)
├── BUILD_COMMANDS.md                 # команды сборки промптов
├── .voyage/                          # project config + dev roles (tracked scaffold, not active DB)
│   ├── project.yaml                  # canonical sources, quality gates, tracks
│   ├── roles.yaml
│   └── task_templates/
├── core/                             # baseline-таблицы (VSCNO, AD, internal_state, memory)
├── docs/                             # архитектурные спецификации и гайды
│   └── narrative/                    # N5/N6 narrative architecture, JSON contract, roadmap
│       ├── NARRATIVE_ROADMAP.md
│       ├── NARRATIVE_FUTURE_TRACKS_v1.md
│       ├── N5F_HYBRID_JSON_PATH_DECISION.md
│       ├── N5G_LIVE_DEV_JSON_CONTRACT.md
│       ├── roles/RENPY_ENGINE_SPECIALIST.md
│       └── ...
├── personas/                         # персонажи: монолитные JSON + модульные директории
├── scenarios/                        # сценарии: монолитные JSON/MD + модульные директории
├── state/                            # стартовые state-шаблоны
├── sessions/                         # артефакты сессий
├── roles/                            # промпты ролей R1–R8 и вспомогательных ролей
├── governance/                       # safety, autonomy, hard limits
├── living_world/                     # proactive/offline события
├── knowledge_base/                   # Knowledge Base для ролей R1–R6 + Narrative
├── schemas/                          # JSON Schema для persona-модулей
├── scripts/                          # вспомогательные скрипты
│   ├── python/                       # Python-утилиты (сборка, загрузка, аудит, тесты)
│   ├── termux/                       # Android/Termux скрипты
│   ├── build_prompt.sh               # legacy generic builder
│   └── update_state.sh               # legacy state updater
├── tools/                            # exporters, adapters
│   ├── vne_adapter.py                # адаптер к Framework CLI (optional pass-through shim)
│   └── vne_to_renpy/                 # RenPy exporter (N5 track)
├── runtime_tools/                    # runtime prompts и инструменты
├── novel/                            # N5 RenPy MVP проект (active technical track)
│   └── game/                         # .rpy файлы, options.rpy, script.rpy
├── visual_prompts/                   # Image generation prompts для персонажей
├── archive/                          # legacy: монолиты, старые версии
├── build_prompt_modular.sh           # текущий shell-враппер для сборки
├── build_prompt_v2_legacy.sh         # legacy сборщик монолитов
├── build_prompt.sh                   # symlink на legacy
├── session_finalize.py               # [LEGACY] финализатор сессий (монолиты only)
├── integration_test.py               # интеграционные тесты
└── ...                               # прочие legacy-скрипты и артефакты
```

### Важно: две параллельные системы модулей

1. **Монолитные JSON-модули** (`personas/*.json`) — runtime-файлы для загрузки в LLM-чат. Используются `session_finalize.py` и legacy-сборщиками.
2. **Модульные директории** (`personas/[id]/...`) — целевая архитектура разработки. Используются `runtime_loader.py`, `build_prompt_modular.py`, `test_runtime_all.py`. **Модульные персоны пока не подключены к `session_finalize.py`.**

---

## Технологический стек

| Слой | Технология | Назначение |
|------|-----------|------------|
| Спецификации | Markdown (`.md`) | Правила системы, механики, гайды, narrative-сценарии |
| Конфиги | JSON (`.json`) | Модули персонажей, состояние сессии, сценарии |
| Сборка | Bash (`.sh`) + Python 3 | `build_prompt_modular.py`, `runtime_loader.py`, `session_finalize.py` |
| Runtime | Внешний LLM (Kimi, Claude, GPT...) | Пользователь копирует собранный промпт в чат |
| Валидация | Python 3 | Проверка модулей, сценариев, интеграционные тесты |
| VCS | Git | Версионирование immutable core, mutable personas и state |

**В корне VNE нет пакетных конфигов** (`pyproject.toml`, `package.json`, `Cargo.toml`). Voyage Framework устанавливается как external dev-OS (отдельный clone).

---

## Команды сборки и запуска

### Собрать runtime-промпт (текущий способ)

```bash
# Один файл
py scripts/python/build_prompt_modular.py sauna_extended standard AG3

# Отдельные файлы (рекомендуется для игры в чате)
py scripts/python/build_prompt_modular.py sauna_extended standard AG3 --separate
# или
bash build_prompt_modular.sh sauna_extended standard AG3 --separate
```

**Результат `--separate`:**
- `PROMPT_SCENARIO.txt` — сценарий, загружать первым.
- `PROMPT_KIRA.txt`, `PROMPT_MARINA.txt`, `PROMPT_SERGEY.txt`, `PROMPT_MAKSIM.txt`, `PROMPT_ANDREY_SENIOR.txt` — персонажи.
- `TRIGGER_GUIDE.txt` — правила триггерной подгрузки.

**Режимы:** `standard` (AG3), `compact` (AG1), `extended` (AG4).

### Загрузить и проверить модульную персону

```bash
py scripts/python/runtime_loader.py andrey_senior
```

### Проверить всех модульных персонажей

```bash
py scripts/python/test_runtime_all.py
```

### Проверить модульный сценарий

```bash
py scenarios/sauna_extended/scenario_validator.py sauna_extended
```

### [LEGACY] Финализировать сессию (только для монолитных JSON)

```bash
# Пробный прогон
py session_finalize.py --log sessions/raw/session.log --scenario sauna_quartet --dry-run --verbose

# Сохранить артефакты
py session_finalize.py --log sessions/raw/session.log --scenario sauna_quartet
```

> **Важно:** `session_finalize.py` ожидает плоскую структуру из монолитных JSON. Для модульных персон используй `build_prompt_modular.py`.

**Выход:** `sessions/state/`, `sessions/memory/`, `sessions/stories/`, `sessions/visuals/`.

### Интеграционные тесты

```bash
py integration_test.py
```

### Проверить JSON-синтаксис

```bash
py -m json.tool personas/KIRA_MODULE_v15.json > nul && echo OK
py -m json.tool schemas/persona_schema_v3_2_VOYAGE.json > nul && echo OK
```

**Важно:** на Windows команды `py ...` требуют `PYTHONIOENCODING=utf-8`, если в выводе есть кириллица/эмодзи.

---

## Организация кода

### `personas/`

- **Монолитные JSON:** `KIRA_MODULE_v15.json`, `SERGEY_MODULE_v4.json`, `MARINA_MODULE_v2.json`, `MAKSIM_MODULE_v2.json`, `ANDREY_SENIOR_MODULE_v1.2.json`, `ANDREY_JUNIOR_MODULE_v2.1.json`, `EGOR_MODULE_v1.json`, `OLGA_MODULE_v2_FIXED.json`, `USER_MODULE.json`, `FEMALE_USER_MODULE.json`.
- **Модульные директории:** `kira/`, `marina/`, `sergey/`, `maksim/`, `andrey_senior/`, `andrey_junior/`, `egor/`, `olga/`, `user/`, `female_user/`.

Каждая модульная персона содержит `INDEX.json` (манифест) и **минимум 12 поддиректорий**. Эталон полной структуры — `personas/kira/` (16+ поддиректорий). Не все персонажи имеют полный набор; optional-модули (`speech/`, `dynamics/`, `memory/`) gracefully пропускаются `runtime_loader.py`.

### `scenarios/`

- **Монолитные:** `SCENARIO_SAUNA_QUARTET.json`, `SCENARIO_SAUNA_QUINTET.json`, `SCENARIO_SHY_BLOOM.json`, `SCENARIO_003_GYM_NIGHT.json` ... `SCENARIO_013_HOME_MESSAGE.json` и др.
- **Модульные:** `sauna_extended/`, `sportcomplex_triad/`, `promenade/`.

Модульный сценарий содержит: `core/INDEX.json`, `structure/`, `scenes/`, `characters/`, `dynamics/`, `environment/`, `branches/`, `safety/`, `meta/`.

### `core/`

Baseline-таблицы, от которых зависят все модули:
- `VSCNO_BASELINE_TABLE.md` — шкала ВЛ/СТ/НЖ/ОГ.
- `AD_AVAILABILITY_MATRIX.md` — матрица алгоритмов действий (АД).
- `INTERNAL_STATE_BASELINE_TABLE.md` — внутренние метрики.
- `MEMORY_BASELINE_TABLE.md` — базовые значения памяти.

### `state/`

Шаблоны состояния сессии: `STATE_TEMPLATE_v2.json` (основной), `STATE_TEMPLATE.json`, `STATE_TEMPLATE_PROMENADE.json`, `STATE_TEMPLATE_QUINTET_v1.json`, `POST_ACT1.json`, `WORKING.json`.

### `sessions/`

Артефакты сессий:
- `raw/` — сырые логи чатов.
- `state/` — обновлённые state-файлы.
- `memory/` — обновления memory-модулей.
- `stories/` — литературные рассказы.
- `visuals/` — промпты для генерации картинок.
- `analysis/` — ретроспективы и анализы.

### `scripts/python/`

- `build_prompt_modular.py` — основной сборщик промптов.
- `runtime_loader.py` — загрузчик модульных персон.
- `test_runtime_all.py` — тест загрузки всех модульных персон.
- `session_retrospector.py` — offline regex-based session analysis (retrospective).
- `refactor_universal.py` — миграция монолита → модули.
- `fix_missing_data.py` — починка потерянных ключей.
- `analyze_sizes.py` — сравнение размеров.
- `generate_vscno.py` — генерация VSCNO.
- `audit_*_r8.py` — R8-аудиторы персон.
- `mia_validator.py` — Module Integrity Auditor.
- `check_consistency.py` — заглушка для проверки визуальной консистентности.

### `tools/`

- `vne_adapter.py` — адаптер для интеграции с Framework CLI (optional pass-through shim).
- `vne_to_renpy/` — RenPy exporter (N5 track).

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
| R7 Refactor | `roles/ROLE_7_REFACTOR_v1.0_PROMPT.md` | ✅ |
| R8 Auditor | `roles/ROLE_8_AUDITOR_v1.0_PROMPT.md` | ✅ |

Дополнительные роли: `COMP`, `V`, `SE`, `NE`, `SM`, `PA`, `TD`, `GCA`, `IE`, `MIA` — используются только в существующих файлах, новые роли не создавать.

**Dev-роли (Voyage Framework layer):** `vne_canon_guard`, `vne_retrospector_dev`, `vne_renpy_adapter`, `vne_qa`, `vne_schema_engineer` — описаны в `.voyage/roles.yaml`. Они управляют задачами разработки и **НЕ равны** narrative-ролям R1–R8. Не путать namespace.

---

## Конвенции

### Имена файлов

- **Пробелы в именах файлов недопустимы.** Всегда используй `_` или `-`.
- Примеры правильных имён:
  - `ROLE_6_MODULAR_ARCHITECT_v2.3.md` ✅
  - `07_PERSONA_MODULAR_ARCHITECTURE.md` ✅
- Примеры deprecated / orphaned:
  - `ROLE_6_PERSONA_ARCHITECT_v2.2_PROMPT.md` ❌ (deprecated, используй v2.3)

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

## Тестирование и качество

### Quality gates (из `.voyage/project.yaml`)

```bash
# Runtime — загрузка всех модульных персон
py scripts/python/test_runtime_all.py

# Prompt — сборка промпта
py scripts/python/build_prompt_modular.py sauna_extended standard AG3

# Schema — валидация JSON Schema
py -m json.tool schemas/persona_schema_v3_2_VOYAGE.json

# Retrospective — offline session analysis
py scripts/python/session_retrospector.py --help
```

### Рекомендуемый pre-commit чеклист

1. Проверить JSON-синтаксис изменённых файлов:
   ```bash
   py -m json.tool <файл>.json > nul && echo OK
   ```
2. Запустить загрузку всех модульных персон:
   ```bash
   py scripts/python/test_runtime_all.py
   ```
3. Запустить валидацию активного сценария:
   ```bash
   py scenarios/sauna_extended/scenario_validator.py sauna_extended
   ```
4. Запустить интеграционные тесты:
   ```bash
   py integration_test.py
   ```
5. Проверить, что VSCNO суммируется в 10.
6. Проверить, что нет пробелов в именах новых файлов.
7. Обновить `AGENTS.md`, если изменилась архитектура или команды.

---

## Безопасность

- **Стоп-слова:** `СТОП`, `ХВАТИТ`, `КРАСНАЯ КАРТОЧКА` — немедленная деэскалация.
- **Autonomy Governor (AG):** `Г0`–`Г4` контролирует инициативу NPC.
- **U6:** переход на уровень U6 может требовать явного подтверждения в зависимости от AG.
- **Hard limits:** не-консенсуальное насилие, принуждение, несовершеннолетние — блокируются.

**Не удалять, не ослаблять и не обходить safety-механизмы.**

---

## Запреты (строго)

1. **Не создавать новые роли** — используй только существующие R1–R8, COMP, V, SE, NE, SM, PA, TD, GCA, IE, MIA. Перед созданием новой роли проверь `roles/` — там 18+ файлов.
2. **Не придумывать новые механики** — все формулы, форматы, блоки — только из существующих спецификаций.
3. **Не менять архитектуру** — если видишь противоречие, зафиксируй как `[CONFLICT]` и предложи уточнить, не исправляй сам.
4. **Не добавлять пакетные конфиги** (`pyproject.toml`, `package.json`, `Cargo.toml`, `setup.py`) в корень VNE без явного разрешения — это спецификационный репозиторий.
5. **Не удалять файлы** без `[CONFLICT]`-метки и объяснения.
6. **Не доверять `README.md` / `README_MODULAR.md`** как источнику архитектуры.
7. **Не ослаблять safety-протоколы** — они описаны в `governance/` и встроены в модули.

---

## Известные проблемы репозитория

- **Две параллельные системы:** монолитные JSON используются для runtime в LLM-чате и `session_finalize.py`; модульные директории — целевая архитектура, пока не полностью интегрированы в финализатор.
- **`session_finalize.py` и модульные персонажи:** финализатор ожидает плоскую структуру VSCNO из монолитов; при попытке загрузить модульную персону возможен `TypeError`. Перед использованием с модульными персонами требуется адаптация.
- **Legacy-скрипты:** `build_prompt.sh`, `build_prompt_v2_legacy.sh`, `install_voyage_update.sh`, `kira-update-hair.sh`, `update_state.sh`, `scripts/build_prompt.sh` ссылаются на устаревшие пути и монолиты. Перед использованием проверять существование файлов.
- **`README.md` / `README_MODULAR.md`** содержат устаревшие ссылки и статусы персонажей.
- **External Framework dependency:** Voyage Framework устанавливается отдельно (не в repo). `vne_adapter.py` — pass-through shim для CLI; без Framework gates fallback на прямые Python-скрипты. `.voyage/` — tracked config scaffold, not active orchestration DB in this clone (chronicler/events not initialized).
- **N5 shadow track:** N5 RenPy/JSON track активен в `docs/narrative/` и `novel/`, но не formalized в `.voyage/project.yaml` tracks. Это создаёт риск, что агенты не видят N5 при чтении только `.voyage/project.yaml`.

---

## Быстрый старт для AI-агента

```bash
# 1. Проверить, что всё загружается
py scripts/python/test_runtime_all.py

# 2. Проверить сценарий
py scenarios/sauna_extended/scenario_validator.py sauna_extended

# 3. Собрать промпт для игры
py scripts/python/build_prompt_modular.py sauna_extended standard AG3 --separate

# 4. Использовать сгенерированные PROMPT_*.txt в LLM-чате
#    Сначала PROMPT_SCENARIO.txt, затем персонажи по триггерам.

# 5. [LEGACY] Финализатор сессии (только для монолитных JSON)
py session_finalize.py --log sessions/raw/session.log --scenario sauna_quartet
# Для модульных персон используй build_prompt_modular.py
```

---

*Последнее обновление: 2026-07-05*
> Обновлено: Integration Boundary Layer (три слоя VNE), Framework dev-OS clarification, N5 shadow track, role namespaces (R1–R8 vs dev-roles vs engineering roles), legacy cleanup (PRELOAD, SPEC_PART, framework-voyage-mvp references), session_finalize.py marked [LEGACY], session_retrospector.py confirmed existing, corrected file naming convention.
