# Framework-voyage-mvp ↔ VNE Integration Guide

> Краткая справка: как использовать Framework как dev-инструмент для VNE, не превращая VNE в Python-пакет.

---

## 1. Архитектура связи

```text
Framework-voyage-mvp/          ← установлен отдельно, pip install -e ".[dev]"
    └── voyage CLI            ← запускается из VNE-директории

voyage-narrative-engine/       ← VNE остаётся спецификационным
    ├── .voyage/
    │   ├── project.yaml      ← профиль проекта
    │   ├── roles.yaml        ← VNE-роли разработки
    │   └── task_templates/   ← шаблоны задач
    ├── tools/
    │   └── vne_adapter.py    ← обёртка над voyage CLI
    └── scripts/python/       ← существующие скрипты VNE
```

**Принцип:** Framework управляет задачами, VNE хранит контент.

---

## 2. Первоначальная настройка (один раз)

### 2.1 Установить Framework

```bash
cd C:/DEV/Framework/Framework-voyage-mvp   # или ваш путь
pip install -e ".[dev]"
```

### 2.2 Инициализировать VNE

```bash
cd C:/DEV/Narrative/voyage-narrative-engine
voyage init
```

Создаст `.voyage/events.db`, `.voyage/events.jsonl`, `.voyage/audit.jsonl`.

### 2.3 Проверить, что CLI работает

```bash
voyage status
```

Должно показать `Total events: 0` и `No events yet.`

---

## 3. Использование vne_adapter.py

### 3.1 Список tracks, ролей и шаблонов

```bash
python tools/vne_adapter.py list
```

### 3.2 Сгенерировать задачу (Session Retrospector)

```bash
python tools/vne_adapter.py task \
  --track session_retrospector \
  --task "Реализовать минимальный Session Retrospector v0.1" \
  --phase SR1
```

Это вызовет `voyage task vne_retrospector_dev --task "..." --project voyage-narrative-engine --phase SR1`.

Результат: `TASK.md` + `CONTEXT.json` в текущей директории.

### 3.3 Запустить агента (quality gates)

```bash
python tools/vne_adapter.py run \
  --role vne_qa \
  --task "Проверить runtime совместимость" \
  --plan "python scripts/python/test_runtime_all.py;python scripts/python/build_prompt_modular.py sauna_extended standard AG3"
```

### 3.4 Запустить quality gates напрямую

```bash
python tools/vne_adapter.py gates              # все gates
python tools/vne_adapter.py gates --gate runtime
```

### 3.5 Статус проекта

```bash
python tools/vne_adapter.py status
```

---

## 4. Использование voyage CLI напрямую (без адаптера)

Если адаптер не нужен, можно вызывать `voyage` напрямую:

```bash
# Генерация задачи
voyage task vne_retrospector_dev \
  --task "Реализовать Session Retrospector" \
  --phase SR1 \
  --project voyage-narrative-engine

# Запуск агента
voyage run vne_qa \
  --task "Run VNE gates" \
  --plan "python scripts/python/test_runtime_all.py;python scripts/python/build_prompt_modular.py sauna_extended standard AG3" \
  --project voyage-narrative-engine

# События
voyage events --project voyage-narrative-engine --limit 20

# Chronicler
voyage chronicler journal --project voyage-narrative-engine
voyage chronicler decisions --project voyage-narrative-engine
voyage chronicler replay <correlation_id>
```

---

## 5. Что НЕ делать

| ❌ Не делать | Почему |
|-------------|--------|
| Не добавлять `pyproject.toml` в VNE | VNE остаётся спецификационным |
| Не импортировать `voyage_framework` из VNE | Не превращать VNE в Python-пакет |
| Не переписывать `core/models.py` Framework | Framework — универсальный инструмент |
| Не добавлять R1–R8 в `EventType` Framework | R1–R8 = нарративные роли, не dev-роли |
| Не создавать `voyage persona` / `voyage scenario` сейчас | Пока рано, используй `voyage task` |
| Не включать LangGraph как обязательный путь | Для MVP он избыточен |
| Не менять `core/` без approval | Правило `no_core_baseline_changes_without_approval` |
| Не переписывать personas без R8-аудита | Правило `no_automatic_persona_rewrite_without_r8_review` |

---

## 6. Доступные tracks и роли

### Tracks (из `.voyage/project.yaml`)

| Track | Роль | Описание |
|-------|------|----------|
| `canon` | `vne_canon_guard` | Синхронизация источников истины |
| `session_retrospector` | `vne_retrospector_dev` | Разработка Session Retrospector |
| `renpy_mvp` | `vne_renpy_adapter` | Ren'Py MVP и экспорт |
| `persona_audit` | `vne_qa` | Аудит persona-модулей |

### Роли (из `.voyage/roles.yaml`)

| Роль | Назначение | Разрешённые пути | Требует approval |
|------|-----------|------------------|------------------|
| `vne_canon_guard` | Синхронизация AGENTS.md, docs | AGENTS.md, docs/, knowledge_base/ | core/, schemas/ |
| `vne_retrospector_dev` | Разработка Session Retrospector | scripts/python/session_retrospector.py, tests/golden/ | schemas/ |
| `vne_renpy_adapter` | Ren'Py MVP | novel/, tools/, scenarios/ | core/, schemas/ |
| `vne_qa` | Аудит и тесты | personas/, scenarios/, scripts/python/, tests/ | — |
| `vne_schema_engineer` | JSON Schema и baseline | schemas/, core/, scripts/python/ | — |

---

## 7. Quality Gates

Определены в `.voyage/project.yaml`:

```bash
# Runtime
python scripts/python/test_runtime_all.py

# Prompt assembly
python scripts/python/build_prompt_modular.py sauna_extended standard AG3

# Schema validation
python -m json.tool schemas/persona_schema_v3_2_VOYAGE.json

# Retrospective
python scripts/python/session_retrospector.py --help
```

---

## 8. Task Templates

Шаблоны лежат в `.voyage/task_templates/`:

| Шаблон | Назначение |
|--------|-----------|
| `TASK_SESSION_RETROSPECTOR_v0.1.md` | Первая задача — Session Retrospector |
| `TASK_CANON_SYNC.md` | Синхронизация источников истины |
| `TASK_RENPY_MVP.md` | Ручной перенос сцены в Ren'Py |

При вызове `vne_adapter.py task --track session_retrospector` адаптер подскажет соответствующий шаблон.

---

## 9. Первая практическая задача

Рекомендуется начать с Session Retrospector v0.1:

```bash
# 1. Сгенерировать задачу
python tools/vne_adapter.py task \
  --track session_retrospector \
  --task "Реализовать минимальный Session Retrospector: parse raw log, split frames, detect speaker, output RETRO_FRAMES.jsonl" \
  --phase SR1

# 2. Прочитать TASK.md и CONTEXT.json
# 3. Выполнить задачу (вручную или через AI-агента)
# 4. Запустить quality gates
python tools/vne_adapter.py gates

# 5. Зафиксировать в chronicler
voyage chronicler journal --project voyage-narrative-engine
```

---

## 10. Что делать, если voyage не найден

```bash
# Проверить установку
which voyage
# или на Windows
where voyage

# Если не найден — добавить Python Scripts в PATH
# или вызвать напрямую:
python -m voyage_framework.cli status
```

---

## 11. Обновление адаптера

Адаптер не зависит от версии Framework. Если `voyage` CLI изменится, править нужно только `tools/vne_adapter.py`.

---

*Создано: 2026-06-21*
*Версия: 0.1*
*Статус: MVP, для тестирования Framework ↔ VNE интеграции*
