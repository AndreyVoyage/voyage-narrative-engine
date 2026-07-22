# PAC Training Dataset Schema — `pac-training-example-v1`

> **Статус:** OWNER_RATIFIED (D-N9-4)
> **Дата:** 2026-07-22
> **Канонический идентификатор схемы:** `pac-training-example-v1`
> **Опора:** `N9_PERSONA_AUTHORING_COMPANION_PREFLIGHT_v1.md` §9, D-N9-4.
> **Назначение:** Формальное описание формата записей тренировочного датасета PAC v0 — `training_dataset.jsonl`. Этот документ является единственным source of truth для схемы датасета.

---

## 1. Общие правила

- **Формат файла:** UTF-8 JSONL, один объект JSON на строку, без trailing запятых.
- **Запись только через APPROVE_DATASET.** Никакая другая операция (ACCEPT_DRAFT, APPROVE_SCENE, выбор варианта моделью) не добавляет запись в датасет.
- **Append-only.** После записи строка не редактируется и не удаляется из main-файла.
- **v0-упрощение:** В `training_dataset.jsonl` хранятся **только** примеры с `quality_status = "approved"`. Отклонённые (rejected) и помещённые в карантин (quarantined) кандидаты в v0 **не** попадают в основной файл. Отдельный sidecar-лог для аудита — DEFERRED.
- **Без секретов.** В датасет не записываются API-ключи, системные промпты провайдера, пароли, токены.
- **Без мутации канона.** Запись в датасет не изменяет `personas/`, `scenarios/`, `knowledge_base/`, `v2_*` или любой другой канонический контент.

---

## 2. Структура записи

```json
{
  "schema_version": "pac-training-example-v1",
  "example_id": "uuid-v4",
  "created_at": "2026-07-22T12:00:00Z",
  "character_id": "kira",
  "scene_id": null,
  "authoring_session_id": "uuid-v4",
  "provider": "local",
  "model": "model-id",
  "canon_snapshot": {
    "source_commit": "41b794c29dd73f78dae27d613a149a231ba46519",
    "modules": [
      {
        "module_id": "speech_matrix.U3-A",
        "content_hash": "sha256:abc123...",
        "provenance": "gateway-v1"
      }
    ]
  },
  "context": {
    "level": "U3-A",
    "situation": "Кира видит Сергея после долгой разлуки",
    "author_instruction": "больше напряжения, сдержанная радость",
    "fmdr_required": true
  },
  "model_output_raw": "(Мысли: неужели это он...) → *Кира замирает на месте, сердце колотится* → «Сергей?..»",
  "approved_output": "(Мысли: он вернулся... и я не знаю, рада ли) → *Кира замирает, пальцы сжимаются в кулак — она не даёт себе броситься к нему* → «Сергей...»",
  "provenance": "human-edited",
  "quality_status": "approved",
  "edit_metrics": {
    "was_edited": true
  },
  "gates": {
    "fmdr_valid": true,
    "speech_uniqueness_pass": true,
    "canon_reviewed_by_human": true
  }
}
```

---

## 3. Поля — подробно

### 3.1. Обязательные поля

| Поле | Тип | Описание |
|------|-----|----------|
| `schema_version` | string, enum | Всегда `"pac-training-example-v1"`. |
| `example_id` | string, UUID v4 | Уникальный идентификатор примера. |
| `created_at` | string, ISO-8601 | Время создания примера (UTC). |
| `character_id` | string | Идентификатор персонажа, для которого создан пример. |
| `authoring_session_id` | string, UUID v4 | Идентификатор авторской сессии. Все примеры одной сессии разделяют этот ID. |
| `provider` | string, enum | `"local"` или `"cloud"`. Выбирается человеком **перед** запуском генерации. |
| `model` | string | Идентификатор модели (например, `"deepseek-v4-pro"`, `"kimi"`). |
| `canon_snapshot` | object | Снимок канонического контекста, использованного при генерации. |
| `context` | object | Контекст генерации: уровень, ситуация, инструкция автора. |
| `model_output_raw` | string | Сырой вывод модели — сохранён для аудита и измерения правок. |
| `approved_output` | string | Финальный одобренный текст. **Только он** идёт в обучающую выборку N8. |
| `provenance` | string, enum | Происхождение текста. |
| `quality_status` | string, enum | Статус качества. |
| `edit_metrics` | object | Метрики редактирования. |
| `gates` | object | Пройденные гейты качества. |

### 3.2. Опциональные поля

| Поле | Тип | Описание |
|------|-----|----------|
| `scene_id` | string или null | Идентификатор сцены, если пример привязан к конкретной сцене. `null` — не привязан. |

### 3.3. `canon_snapshot.modules[]`

| Поле | Тип | Описание |
|------|-----|----------|
| `module_id` | string | Идентификатор модуля (например, `"speech_matrix.U3-A"`, `"psychology.core"`). |
| `content_hash` | string | Хеш содержимого модуля — **берётся из `ModuleResult` provenance, возвращаемого Persona Gateway.** Не вычисляется вручную. |
| `provenance` | string | Источник хеша. В v0 — `"gateway-v1"` (предоставлен N7 Persona Gateway). |

### 3.4. `canon_snapshot.source_commit`

- **Тип:** string (40-char hex SHA-1).
- **Источник:** `git rev-parse HEAD` в начале авторской сессии.
- **Отличие от `content_hash`:** `source_commit` — это **сессионный** идентификатор состояния репозитория. `content_hash` — **покомпонентный** хеш модуля.

### 3.5. `context`

| Поле | Тип | Описание |
|------|-----|----------|
| `level` | string | Уровень сцены (например, `"U3-A"`, `"U4"`). |
| `situation` | string | Описание ситуации. |
| `author_instruction` | string | Инструкция автора модели. |
| `fmdr_required` | boolean | Требовался ли формат ФМДР. В v0 практически всегда `true`. |

### 3.6. `edit_metrics`

| Поле | Тип | Описание |
|------|-----|----------|
| `was_edited` | boolean | Был ли `model_output_raw` отредактирован человеком. В v0 — минимальная метрика. Расширенные метрики (diff ratio, edit distance) — DEFERRED. |

### 3.7. `gates`

| Поле | Тип | Описание |
|------|-----|----------|
| `fmdr_valid` | boolean | Прошёл ли вывод валидацию формата ФМДР. |
| `speech_uniqueness_pass` | boolean | Прошёл ли проверку уникальности речи (R8-аудитор). |
| `canon_reviewed_by_human` | boolean | Просмотрен ли пример человеком на соответствие канону. |

---

## 4. Enum-значения

### 4.1. `provider`

| Значение | Описание |
|----------|----------|
| `"local"` | Локальная модель. Предпочтительно для adult/чувствительного контента. |
| `"cloud"` | Облачная модель. Выбирается осознанно, не автоматически. |

### 4.2. `provenance`

| Значение | Описание |
|----------|----------|
| `"human-written"` | Текст полностью написан человеком без модельной генерации. |
| `"human-edited"` | Модельный вывод отредактирован человеком. |
| `"model-raw-approved"` | Сырой вывод модели одобрен без правок. Используется осторожно — рискует впечатать дефекты базовой модели в N8. |

### 4.3. `quality_status`

| Значение | Описание |
|----------|----------|
| `"approved"` | Пример прошёл APPROVE_DATASET. Единственное значение в v0 main-датасете. |
| `"rejected"` | (DEFERRED) Пример отклонён. Не хранится в v0 main-датасете. |
| `"quarantined"` | (DEFERRED) Пример помещён в карантин для дополнительного ревью. Не хранится в v0 main-датасете. |

---

## 5. Правила валидации

1. **`schema_version`** — точно `"pac-training-example-v1"`.
2. **`example_id`**, **`authoring_session_id`** — валидный UUID v4.
3. **`created_at`** — валидный ISO-8601 с timezone (рекомендуется UTC).
4. **`provider`** ∈ `{"local", "cloud"}`.
5. **`provenance`** ∈ `{"human-written", "human-edited", "model-raw-approved"}`.
6. **`quality_status`** ∈ `{"approved"}` (v0 main-датасет). `"rejected"` и `"quarantined"` — допустимы только в sidecar-логах (DEFERRED).
7. **`fmdr_*`** — ключи используют `fmdr_`, не `fmrd_`.
8. **`model_output_raw`** ≠ пустая строка. (Может быть равен `approved_output` при provenance = `model-raw-approved`.)
9. **`approved_output`** ≠ пустая строка.
10. **`canon_snapshot.modules`** — непустой массив; каждый элемент содержит `module_id` и `content_hash`.
11. **`source_commit`** — 40 символов, шестнадцатеричный.
12. **JSONL** — одна строка = один объект, без лишних пробелов между объектами, без запятых между строками.

---

## 6. Отличие `model_output_raw` от `approved_output`

| | `model_output_raw` | `approved_output` |
|---|---|---|
| **Назначение** | Аудит, сравнение, измерение правок, выявление дефектов модели. | Обучающая цель для N8. |
| **Когда записывается** | Всегда, при каждом ACCEPT_DRAFT. | Только при APPROVE_DATASET. |
| **Используется ли для N8** | **Нет.** Никогда автоматически. | **Да.** Только `approved_output`. |
| **Может ли быть равен `approved_output`** | Да — при provenance = `model-raw-approved`. | Да. |

---

## 7. Отличие provenance от quality_status

**provenance** — _как_ получен финальный текст (кто создал/редактировал).

**quality_status** — _пригоден ли_ для обучающей выборки.

Эти два измерения **независимы**:
- `human-written` текст может быть `rejected` (не подходит стилистически).
- `model-raw-approved` может быть `approved` (если модель выдала идеальный результат, который прошёл все гейты).
- `human-edited` — наиболее ожидаемое сочетание для approved-примеров.

---

## 8. Предусловия для APPROVE_DATASET

1. Человек явно выполнил `APPROVE_DATASET` для данного примера.
2. `approved_output` не пуст.
3. Все гейты (`fmdr_valid`, `speech_uniqueness_pass`, `canon_reviewed_by_human`) = `true`.
4. `model_output_raw` сохранён (даже если равен `approved_output`).
5. Канонический снапшот (`canon_snapshot`) содержит хеши всех потреблённых модулей.

---

## 9. Примеры (валидные и невалидные)

### 9.1. Минимальный валидный пример

```json
{"schema_version":"pac-training-example-v1","example_id":"550e8400-e29b-41d4-a716-446655440000","created_at":"2026-07-22T12:00:00Z","character_id":"kira","scene_id":null,"authoring_session_id":"550e8400-e29b-41d4-a716-446655440001","provider":"local","model":"deepseek-v4-pro","canon_snapshot":{"source_commit":"41b794c29dd73f78dae27d613a149a231ba46519","modules":[{"module_id":"speech_matrix.U3-A","content_hash":"sha256:abc123def456","provenance":"gateway-v1"}]},"context":{"level":"U3-A","situation":"встреча","author_instruction":"сдержанно","fmdr_required":true},"model_output_raw":"(Мысли) → *Действие* → «Речь»","approved_output":"(Мысли: он здесь) → *Кира застыла* → «Ты...»","provenance":"human-edited","quality_status":"approved","edit_metrics":{"was_edited":true},"gates":{"fmdr_valid":true,"speech_uniqueness_pass":true,"canon_reviewed_by_human":true}}
```

### 9.2. Невалидный пример — пустой `approved_output`

```json
{"schema_version":"pac-training-example-v1","example_id":"550e8400-e29b-41d4-a716-446655440002","created_at":"2026-07-22T12:00:00Z","character_id":"kira","scene_id":null,"authoring_session_id":"550e8400-e29b-41d4-a716-446655440003","provider":"local","model":"deepseek-v4-pro","canon_snapshot":{"source_commit":"41b794c29dd73f78dae27d613a149a231ba46519","modules":[{"module_id":"speech_matrix.U3-A","content_hash":"sha256:abc123def456","provenance":"gateway-v1"}]},"context":{"level":"U3-A","situation":"встреча","author_instruction":"сдержанно","fmdr_required":true},"model_output_raw":"(Мысли) → *Действие* → «Речь»","approved_output":"","provenance":"human-edited","quality_status":"approved","edit_metrics":{"was_edited":true},"gates":{"fmdr_valid":true,"speech_uniqueness_pass":true,"canon_reviewed_by_human":true}}
```

> **Ошибка:** `approved_output` — пустая строка. Нарушает правило: `approved_output` не может быть пустым.

### 9.3. Невалидный пример — неверный ключ `fmrd_`

```json
{"schema_version":"pac-training-example-v1","example_id":"550e8400-e29b-41d4-a716-446655440004","created_at":"2026-07-22T12:00:00Z","character_id":"kira","scene_id":null,"authoring_session_id":"550e8400-e29b-41d4-a716-446655440005","provider":"local","model":"deepseek-v4-pro","canon_snapshot":{"source_commit":"41b794c29dd73f78dae27d613a149a231ba46519","modules":[{"module_id":"speech_matrix.U3-A","content_hash":"sha256:abc123def456","provenance":"gateway-v1"}]},"context":{"level":"U3-A","situation":"встреча","author_instruction":"сдержанно","fmdr_required":true},"model_output_raw":"(Мысли) → *Действие* → «Речь»","approved_output":"(Мысли: он здесь) → *Кира застыла* → «Ты...»","provenance":"human-edited","quality_status":"approved","edit_metrics":{"was_edited":true},"gates":{"fmrd_valid":true,"speech_uniqueness_pass":true,"canon_reviewed_by_human":true}}
```

> **Ошибка:** Ключ `fmrd_valid` — должен быть `fmdr_valid`.

---

## 10. Что НЕ хранится в датасете

- ❌ Системные промпты провайдера.
- ❌ API-ключи, токены, пароли.
- ❌ Embeddings, векторные представления.
- ❌ Token-рейтинги, перплексии, логиты.
- ❌ Сложная аналитика качества (DEFERRED для v0).
- ❌ Результаты, не получившие `APPROVE_DATASET`.
- ❌ Автоматически сгенерированные метаданные без человеческого одобрения.

---

## 11. Версионирование схемы

| Версия | Дата | Изменения |
|--------|------|-----------|
| `pac-training-example-v1` | 2026-07-22 | Начальная версия. D-N9-4 ратифицирована. |

При изменении схемы:
1. Новый `schema_version` (например, `pac-training-example-v2`).
2. Обратная совместимость — по возможности.
3. Старые данные либо мигрируются, либо остаются с пометкой о версии схемы.

---

*Конец PAC_TRAINING_DATASET_SCHEMA_v1.md*