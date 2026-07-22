# N9 — PERSONA AUTHORING COMPANION (PAC) — PREFLIGHT (P0)

> **MODE: READ-ONLY / DOCUMENTATION ONLY.** Документ ничего не реализует и не меняет код.
> Фиксирует цель, архитектуру (переиспользование готового), flywheel, правила защиты канона,
> поправки к исходному концепту и фазовый план — до написания кода.
>
> **Статус:** P0 PREFLIGHT v1.1 — OWNER DECISIONS RATIFIED. IMPLEMENTATION (v0) READY FOR DELEGATED PROMPT.
> **Дата:** 2026-07-22 (v1.1 — ратифицированы owner-решения + JSONL-схема + 3-уровневое одобрение + acceptance-критерии v0)
> **Опора:** `NARRATIVE_DECISIONS_v1.md` §1–§2, `N7_CANONICAL_STATUS_CLOSEOUT_v1.md`,
> `N6_CHARACTER_ASIDE_CONTRACT.md`.
> **Связанные документы (пакет N9 + Character Evolution):**
> - `PAC_TRAINING_DATASET_SCHEMA_v1.md` — формальная схема `pac-training-example-v1`.
> - `CHARACTER_EVOLUTION_SANDBOX_CONCEPT_v1.md` — концепция неканонической песочницы эволюции (PROPOSED).
> - `PAC_CHARACTER_EVOLUTION_DECISION_REGISTER_v1.md` — регистр всех решений (D-N9: 5 ратифицировано; D-CES: 10 pending).
> - `PAC_CHARACTER_EVOLUTION_PARALLEL_DEVELOPMENT_MAP_v1.md` — карта параллельной разработки треков.
> - `PAC_CHARACTER_EVOLUTION_KNOWLEDGE_CAPTURE_v1.md` — сохранение идей, обоснований и заменённых подходов.
> **Границы:** Narrative / authoring-домен. НЕ Voyage Framework automation.

---

## 0. Что это и позиционирование

**Persona Authoring Companion (PAC)** — интерактивный инструмент, где нейросеть выступает не как
финальный продукт для игрока, а как **соавтор для разработчика**: помогает писать каноничные,
психологически достоверные сценарии в характере персонажа и **попутно накапливает выверенный датасет**
для будущего дообучения голоса (N8).

**Позиционирование в роадмапе:**

- PAC — **β-трек (authoring)**, а не игровой рантайм. Здесь MCP уместен (внешний редактор/Cline).
- PAC стоит **выше по течению от N8 (Persona Voice Model):** N8 заблокирован данными (реальных реплик
  Киры ~50–110); PAC — это машина, которая производит недостающий корпус. `PAC → корпус → разблокирует N8`.
- PAC переиспользует **уже построенное** (N7 Gateway, N6 память/провайдер) — это не стройка с нуля.

---

## 1. Ключевое разделение: «память» ≠ «обучение»

Два процесса, которые легко спутать; PAC держит их раздельно:

| | Оперативная память | Глубокое обучение (fine-tune) |
|---|---|---|
| **Когда** | здесь и сейчас, каждый turn | периодически, пакетно (напр. при 1000+ выверенных примерах) |
| **Что меняется** | запись в БД/файл сессии | веса модели (LoRA-адаптер) |
| **Механизм** | `session memory` (non-canon) | curated JSONL → облачный/локальный fine-tune → GGUF |
| **Стоимость** | ~0 | отдельный осознанный этап (N8) |

Разговор с персонажем **не переобучает** модель — он наполняет память. Веса меняются только отдельным
пакетным дообучением из **одобренных** диалогов.

---

## 2. Архитектура — переиспользуем готовое

Четыре компонента; три из четырёх уже существуют.

### А. Источник истины персонажа — READ-ONLY (готово, N7)
- `personas/<id>/` (модульная «ДНК»: психология, речь, триггеры, ФМДР) + `knowledge_base/` (теория).
- Доступ — **через существующий `services/persona_gateway`** (`read_module(character_id, module_id)` с
  allowlist по INDEX, provenance, защитой от traversal). **НЕ писать новый `read_persona_module()`.**
- Внешняя MCP-дверь для Cline = это **N7 P2 (MCP-адаптер над Gateway, read-only)**, а не отдельный сервер.

### Б. Память сессии авторства — CONTROLLED WRITE, non-canon (новое, малое)
- Хранит историю *твоих* писательских сессий: черновик сцены, принятые решения, настроение, достигнутый
  уровень. **Изолирована, неканонична.** Опирается на паттерн `tools/aside_memory_store.py`.
- **v0: файлы (JSONL/JSON).** SQLite/PostgreSQL — апгрейд *после* v0, если понадобится масштаб.
- Записывать сюда можно — но это **не** канон и **никогда** не пишет в `personas/`, `scenarios/`, `v2_*`.

### В. Движок генерации — провайдер (готово, N6)
- `tools/llm_provider.py` (mock/local/cloud). Для adult-контента **локальная модель предпочтительна**
  (облачные API могут отказать на откровенных сценах + ты дистиллируешь их стиль — см. §5).
- Выдаёт 2–3 варианта строго в формате ФМДР `(Мысли) → _Действия_ → «Речь»`.

### Г. Интерфейс соавтора — начинаем с минимума
- **v0: CLI / простой чат.** Web-UI с кнопками «Сгенерировать / Утвердить в канон / Отклонить» — позже.

---

## 3. The Authoring Flywheel (ядро идеи)

```
1. Ты задаёшь контекст сцены (персонаж, уровень U*, ситуация).
2. Gateway (read-only) подтягивает нужные модули: speech_matrix.U*, psychology.*, AD.
3. Движок выдаёт 2–3 варианта в ФМДР.
4. Ты правишь лучший под свой вкус ("больше страха для U3-A").
5. Двойная выгода:
   • СЦЕНАРИЙ — одобренный текст идёт в Ren'Py/JSON (канон соблюдён тобой).
   • ДАТАСЕТ — пара (контекст → ТВОЙ одобренный текст) пишется в training_dataset.jsonl.
```

**Почему это разблокирует N8:** ты просто пишешь игру, а система незаметно копит тысячи выверенных
примеров поведения персонажа — тот самый корпус, которого сейчас нет.

**Критично — метка происхождения на каждом примере** (защита от само-дистилляции):
`provenance ∈ {human-written, human-edited, model-raw-approved}`. Сохраняется **отредактированный тобой**
текст, а не сырой вывод. При дообучении (N8) `model-raw-approved` можно взвесить/отфильтровать, чтобы не
впечатать в веса дефекты базовой модели (слабый русский, уклонения).

---

## 4. Правила защиты канона (незыблемо)

1. **ИИ предлагает — человек решает.** Ни строки в сценарий или датасет без явного `Approve`.
2. **Строгий формат ФМДР** как детерминированный гейт: не тот формат → авто-reject и регенерация.
3. **Реюз R8-аудитора** уникальности речи как дополнительного quality-gate на одобряемые реплики.
4. **Запрет записи в ДНК/канон.** ИИ через любой инструмент только **читает** `personas/`, `core/`,
   `knowledge_base/`, `scenarios/`, `v2_*`. Менять их можешь только ты вручную.
5. **Память сессии изолирована и неканонична;** её наличие/содержимое не влияет на игровой канон.

---

## 5. Поправки к исходному концепту PAC (зафиксировано)

1. **Read-side = существующий Gateway, а не новый MCP read-tool.** Исходный `read_persona_module(path)` —
   небезопасный (path traversal) и дублирует N7. Использовать `persona_gateway.read_module(id, module_id)`.
2. **MCP-дверь для Cline = N7 P2**, transport-only, без persona business logic, read-only.
3. **Write-plane только non-canon session memory**, через контролируемую запись; никогда не канон.
4. **Метка provenance** на каждом training-примере (§3).
5. **Облачный движок для adult — с оговоркой:** content-policy отказы + дистилляция чужого стиля;
   локальная модель, вероятно, всё равно нужна.
6. **Не начинать с MCP-сервера** (см. §6): v0 не требует MCP/SQLite/UI.

---

## 6. Фазовый план (reordered — «сначала измерь»)

```
v0  Валидация петли БЕЗ новой инфраструктуры:
    companion system-prompt (ФМДР, 2–3 варианта, вопрос "одобрить/скорректировать?")
    + ручное Approve → append пары в training_dataset.jsonl (с provenance-флагом)
    + факты через существующий Gateway. НЕТ MCP/SQLite/UI.
    Критерий успеха: соавторство "ощущается" полезным; JSONL копит качественные пары.

P1  Session memory (non-canon): персистентная память писательской сессии (файлы),
    паттерн aside_memory_store; изоляция; reset.

P2  MCP-адаптер над Gateway (= N7 P2): read-only tools для Cline/внешнего редактора.

P3  Interface: CLI → простой Web-UI (кнопки generate/approve/reject) — по необходимости.

P4  Scale: SQLite/PostgreSQL для памяти; провенанс-аналитика датасета.

(feeds) N8 — Persona Voice Model: когда корпус накоплен и измерен.
```

**v0 — единственный шаг, который стоит запускать сразу.** Остальное — только после того, как v0 докажет,
что петля работает и материал качественный.

---

## 7. Owner decisions — RATIFIED (v1.1)

```
D-N9-1  PAC как активный β-трек                          APPROVE
D-N9-2  Старт с v0 (без MCP/DB/UI)                        APPROVE
D-N9-3  Движок v0                                         LOCAL-FIRST (см. ниже)
D-N9-4  Схема training_dataset.jsonl                      APPROVE (схема §9)
D-N9-5  Размещение кода                                   APPROVE (домен + тонкий CLI, §11)
```

**D-N9-3 — точная формулировка:**
```
Primary: local            Optional comparison mode: cloud (per-run, осознанно)
Fallback local → cloud: ЗАПРЕЩЁН автоматически            Provider выбирает человек ПЕРЕД запуском
```
Позволяет сравнивать качество, не смешивая происхождение примеров и не отправляя чувствительный
материал в облако без явного решения. Поле `provider` фиксируется в каждом примере.

---

## 8. Трёхуровневое одобрение (одобрение сцены ≠ пригодность для обучения)

```
ACCEPT_DRAFT     — принять вариант в рабочий черновик (ничего не пишется наружу)
APPROVE_SCENE    — разрешить перенос в сценарий (канон правит человек вручную)
APPROVE_DATASET  — разрешить запись training-примера в JSONL
```

Разделены намеренно: сцена может быть хороша сюжетно, но не годиться как training target, и наоборот.
**Инвариант:** запись в `training_dataset.jsonl` происходит **только** при `APPROVE_DATASET`.

Хранение для аудита: `model_output_raw` **и** `approved_output`. В обучающий target идёт **только**
`approved_output` (сырой вариант нужен лишь для измерения объёма правки, не как цель обучения).

---

## 9. Схема training_dataset.jsonl — `pac-training-example-v1` (D-N9-4)

```json
{
  "schema_version": "pac-training-example-v1",
  "example_id": "uuid",
  "created_at": "ISO-8601",
  "character_id": "kira",
  "scene_id": null,
  "authoring_session_id": "uuid",
  "provider": "local",
  "model": "model-id",
  "canon_snapshot": {
    "source_commit": "git-hash",
    "modules": [
      {"module_id": "speech_matrix.U3-A", "content_hash": "sha256:…"},
      {"module_id": "psychology.core",     "content_hash": "sha256:…"},
      {"module_id": "AD",                  "content_hash": "sha256:…"}
    ]
  },
  "context": {"level": "U3-A", "situation": "...", "author_instruction": "...", "fmdr_required": true},
  "model_output_raw": "...",
  "approved_output": "...",
  "provenance": "human-written | human-edited | model-raw-approved",
  "quality_status": "approved",
  "edit_metrics": {"was_edited": true},
  "gates": {"fmdr_valid": true, "speech_uniqueness_pass": true, "canon_reviewed_by_human": true}
}
```

Примечания к схеме:
- `canon_snapshot.modules[].content_hash` — берётся **из provenance, который Gateway уже возвращает**
  (`ModuleResult`), не собирается вручную; `source_commit` = `git rev-parse HEAD` в начале сессии.
- Ключи формата — **`fmdr_*`** (ФМДР), не `fmrd_*`.
- v0-упрощение: в файл пишутся **только** примеры с `APPROVE_DATASET`, поэтому `quality_status` в v0
  фактически = `approved`; `rejected`/`quarantined` в v0 не хранятся (или в отдельный sidecar-лог позже).
- Для v0 НЕ нужны: embeddings, token-рейтинги, SQLite id, сложная аналитика.

---

## 10. Acceptance-критерии v0 (измеримые, вместо «ощущается полезным»)

```
≥ 20–30 завершённых authoring turns;
≥ 10 примеров с APPROVE_DATASET;
валидный ФМДР ≥ 90%;
ручная правка не превращается в полное переписывание большинства ответов;
0 записей без явного APPROVE_DATASET;
0 записей в canon / personas / scenarios со стороны PAC;
training_dataset.jsonl повторно читается и валидируется без ошибок.
```

---

## 11. Размещение кода (уточнение D-N9-5)

```
services/persona_authoring/   — domain/application logic (loop, collector, fmdr-gate, schema)
tools/pac_cli.py              — тонкая CLI-оболочка (transport-independent ядро отдельно от CLI)
local_runs/pac/               — runtime output (JSONL), ВНЕ канона, gitignored
```

Тот же принцип, что в Persona Gateway: доменное ядро не знает про транспорт/интерфейс.
**Заменяет** раннюю прикидку `tools/pac/` из первого delegated-черновика (тот черновик устарел).

---

## 12. Итоговый статус

```
N9 PAC P0: ARCHITECTURALLY SOUND, OWNER DECISIONS RATIFIED (v1.1)
Blocking decision D-N9-4 (schema): RESOLVED
Next: v0 delegated implementation prompt (по §8–§11)
MCP / DB / Web UI: DEFERRED    N8 training: NOT AUTHORIZED
```

Реализация v0 — отдельным строгим delegated-промптом по §8–§11. Настоящий документ разрешения на код
не даёт; он фиксирует, ЧТО и КАК должен построить v0.
