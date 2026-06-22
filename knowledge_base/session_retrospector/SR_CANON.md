# SR_CANON.md
# Session Retrospector — Канонический Источник Истины
# Voyage Narrative Engine | R8-Compatible Post-Session Audit Mode
# Версия: 1.0.0 | Дата: 2026-06-20
# Статус: канон (дополняет AGENTS.md, не противоречит)

---

## 1. НАЗНАЧЕНИЕ

**Session Retrospector (SR)** — это режим постсессионного аудита, совместимый с **R8 (Auditor)**.

- **SR не создаёт новую роль** (R9). Это runtime-инструмент в рамках R8.
- **SR не генерирует сюжет**. Он анализирует завершённые сессии.
- **SR не редактирует модули персонажей напрямую**. Он выдаёт доказательные замечания (findings) для R7 (Refactor) и R8 (Auditor).
- **SR не оценивает пользователя**. User-реплики участвуют только как триггеры причинно-следственной проверки.

**Цель:** проверить, что персонажи в завершённой сессии:
1. Вели себя логично (персонажная консистентность, адекватные переходы).
2. Были художественно выразительны (show-don't-tell, сенсорика, ритм).
3. Соответствовали TEC-конструкту (правильные подуровни, AD, VSCNO, internal state).
4. Говорили в соответствии со speech profile (catchphrases, фрагментация, мета-диалог).

---

## 2. ЧТО SR ИМЕЕТ ПРАВО ОЦЕНИВАТЬ

| # | Объект оценки | На основании |
|---|--------------|-------------|
| 1 | **NPC-реплики** в raw log | Persona module, speech matrix, FMDR format |
| 2 | **Переходы подуровней** (escalation) | VSCNO_BASELINE_TABLE, AD_AVAILABILITY_MATRIX, INTERNAL_STATE_BASELINE |
| 3 | **AD-коды** | AD_AVAILABILITY_MATRIX + [ADAPTED] из модуля |
| 4 | **VSCNO** | VSCNO_BASELINE_TABLE + адаптации модуля |
| 5 | **Internal state** | INTERNAL_STATE_BASELINE + адаптации модуля |
| 6 | **Speech level** | SPEECH_MATRIX из модуля + R4 (Linguist) |
| 7 | **Memory continuity** | MEMORY_BASELINE_TABLE + emotional anchors из модуля |
| 8 | **Literary quality** | KB_NARRATIVE_FMDR_EXAMPLES + SENSORY_PEAK_GUIDELINES |
| 9 | **Scenario compliance** | Scenario rules + governance protocols |

---

## 3. ЧТО SR НЕ ИМЕЕТ ПРАВА ОЦЕНИВАТЬ

| # | Запрещено | Почему |
|---|----------|--------|
| 1 | **Оценивать пользователя** как "хорошо/плохо" | User — не персонаж, у него нет модуля |
| 2 | **Предлагать новые механики** | SR — auditor, не designer. Нашёл проблему → передай R7 |
| 3 | **Переписывать модули** | Только findings + recommendations. R7 делает refactor |
| 4 | **Оценивать визуальные промпты** как "красиво/некрасиво" | Можно проверять консистентность anatomic_anchor текстово, но не эстетику |
| 5 | **Принимать решения при конфликте источников** | SR помечает [CONFLICT], а не выбирает победителя |
| 6 | **Генерировать новый сюжет** | Не его задача |
| 7 | **Оценивать safety-срабатывания** | Safety проверяется отдельно, SR не может отменить СТОП |

---

## 4. ПРИОРИТЕТ ИСТОЧНИКОВ (SOURCE PRIORITY)

Когда источники противоречат друг другу, SR использует следующий приоритет:

```
P0 — Safety / Governance / AGENTS.md
P1 — SR_CANON.md (этот файл)
P2 — Scenario-specific safety and rules (governance/)
P3 — Persona module: INDEX.json + required modules
P4 — Speech matrix: personas/[name]/speech/SPEECH_MATRIX.json
P5 — Core baseline: VSCNO_BASELINE_TABLE, AD_AVAILABILITY_MATRIX, INTERNAL_STATE_BASELINE, MEMORY_BASELINE_TABLE
P6 — Knowledge base: KB_NARRATIVE_FMDR_EXAMPLES, KB_R4_SPEECH_MATRIX, etc.
P7 — Raw model inference (если нет источника в P0-P6)
```

**Ключевое правило:**
> Если `raw inference` (P7) противоречит `persona module` (P3) или `scenario safety` (P2), SR обязан пометить `[CONFLICT]`, а не выбирать "по своему усмотрению".

---

## 5. ФОРМАТ ВХОДА (INPUT SPEC)

### 5.1 Обязательный минимум (LIGHT MODE)

```yaml
input_package:
  raw_log:          # Файл .log / .md / .txt — диалог User ↔ NPC
  scenario_id:      # Например: "sauna_extended", "promenade"
  active_personas:  # Список ID персонажей, участвовавших в сессии
```

**Ограничение LIGHT MODE:**
- SR может оценить только очевидные нарушения формата ФМДР, грубые скачки уровней, дублирование реплик.
- Без persona modules и baseline tables **невозможно** проверить:
  - AD-доступность для конкретного подуровня
  - Speech level соответствие персонажу
  - VSCNO-консистентность
  - Memory continuity

### 5.2 Полный аудит (FULL MODE)

```yaml
input_package:
  raw_log:          # Файл .log / .md / .txt
  normalized_session: # normalized_session.json (опционально, see §7)
  start_state:      # STATE.json в начале сессии
  end_state:        # STATE.json в конце сессии
  scenario_id:      # ID сценария
  active_personas:  # ["kira", "sergey", "marina", ...]
  
  # Обязательные для full mode:
  persona_modules:  # personas/[name]/INDEX.json + все required modules
  speech_matrices:  # personas/[name]/speech/SPEECH_MATRIX.json
  vscno_baseline:   # core/VSCNO_BASELINE_TABLE.md
  ad_matrix:        # core/AD_AVAILABILITY_MATRIX.md
  internal_baseline: # core/INTERNAL_STATE_BASELINE.md
  memory_baseline:  # core/MEMORY_BASELINE_TABLE.md
  
  # Опционально:
  fmdr_examples:    # knowledge_base/narrative/KB_NARRATIVE_FMDR_EXAMPLES.md
  governance:       # governance/AUTONOMY_GOVERNOR.md, GOVERNANCE_NOTE_*.md
  scenario_rules:   # scenarios/[id]/safety/SAFETY.json
```

**Правило:** Full mode даёт evidence-based audit. Light mode — только surface-level скан.

---

## 6. ФОРМАТ ВЫХОДА (OUTPUT SPEC)

SR производит **два артефакта**:

### 6.1 RETRO_SUMMARY.md

Для человека (владельца, R7, R8).

Структура:
```markdown
# SESSION RETROSPECTIVE: [scenario_id] | [date]
## Meta
- Session ID: [id]
- Duration: [N turns, M frames]
- Active personas: [list]
- Audit mode: [light | full]
- Overall Q4 Score: [LO=X, HU=Y, TE=Z, DI=W]

## 1. Executive Summary
3-5 предложений о главных находках.

## 2. Escalation Audit
[Таблица переходов подуровней]

## 3. AD Availability Audit
[Таблица AD по кадрам]

## 4. Memory Continuity Audit
[Таблица событий и якорей]

## 5. Peak Speech Analysis
[Анализ пиковых реплик]

## 6. Literary Audit
[Сенсорная плотность, show vs tell]

## 7. Frame-by-Frame Critical Findings
[Только кадры с severity CRITICAL или WARNING]

## 8. Recommendations for R7
[Точечные рекомендации с адресами файлов]

## 9. Appendix: Full Scorecard
[Таблица всех кадров с оценками]
```

### 6.2 RETRO_FRAMES.jsonl

Для машинной обработки (R7, R8, session_finalize.py, CI/CD).

Каждая строка — один JSON-объект:

```json
{"frame":"F023","speaker":"Kira","timestamp":"2026-06-20T21:14:18","severity":"critical","axes":["LO","TE"],"claim":"Invalid escalation U1-A → U3-B","evidence":["F019: confirmed U1-A","F020-F022: no trust/safety trigger","F023: behavior matches U3-B pattern"],"source_refs":["AD_AVAILABILITY_MATRIX.md#U1-A","KIRA/speech/SPEECH_MATRIX.json#stress"],"confidence":0.78,"root_cause":"scenario_design_or_llm_drift","recommendation":"Insert transition frame U1-B → U2-A before U3-B."}
```

**Правило:** `RETRO_FRAMES.jsonl` — единственный источник, который R7 может парсить автоматически. `RETRO_SUMMARY.md` — для человеческого чтения.

---

## 7. НОРМАЛИЗАЦИЯ ВХОДА (NORMALIZATION STAGE)

### 7.1 Проблема

Raw log может быть в разных форматах:
- Многострочный ФМДР (мысли + действия + речь + auto_visual)
- Однострочный (`[USER] текст` / `[KIRA] текст`)
- Без таймстампов
- С таймстампами
- С inline STATE (`[STATE: Kira U2-A]`)
- Без STATE

### 7.2 Решение: normalized_session.json

Любой raw log проходит через **Normalization Layer** перед аудитом.

```json
{
  "session_id": "session_2026-06-20_001",
  "scenario_id": "sauna_extended",
  "total_turns": 47,
  "total_frames": 89,
  "frames": [
    {
      "frame_id": "F001",
      "turn_id": "T001",
      "timestamp": "2026-06-20T21:14:03",
      "speaker": "USER",
      "type": "user",
      "content": {
        "text": "Ты сегодня красивая."
      }
    },
    {
      "frame_id": "F002",
      "turn_id": "T002",
      "timestamp": "2026-06-20T21:14:07",
      "speaker": "KIRA",
      "type": "npc",
      "content": {
        "thoughts": "снова этот запах. Почему он всегда здесь?",
        "action": "*отворачивается*",
        "speech": "Ты опоздал.",
        "visual_tags": ["portrait", "dim_light"]
      },
      "inferred_state": {
        "sublevel": "U1-A",
        "vscno": {"vl":1, "st":4, "cn":2, "og":3},
        "internal_state": {"desire":2, "anxiety":7, "tension":5, "frustration":4}
      },
      "inferred_ad": "ПД"
    }
  ]
}
```

**Правило:** Если `normalized_session.json` не предоставлен, SR сам запускает нормализатор. Но результат нормализации не является частью аудита — это препроцессинг.

### 7.3 Валидация входного пакета (VALIDATION STAGE)

Перед началом аудита SR проверяет:

```
[VALIDATION CHECKLIST]
□ raw_log не пустой
□ active_personas ⊆ существующих personas/
□ scenario_id ∈ существующих scenarios/
□ start_state и end_state содержат всех active_personas
□ persona_modules содержат всех active_personas (full mode)
□ speech_matrices содержат всех active_personas (full mode)
□ core baseline tables доступны (full mode)
```

Если любая проверка fails — SR останавливается и выдаёт `VALIDATION_ERROR.md`, а не продолжает аудит с дырами.

---

## 8. ШКАЛЫ ОЦЕНКИ (SR-Q4 SCORECARD)

**SR-Q4** — четыре оси качества. Каждая ось: [0, 4].

| Ось | Полное название | Что измеряет |
|-----|----------------|-------------|
| **LO** | Логичность | Персонажная консистентность, адекватность переходов, память, причинность |
| **HU** | Художественность | Show-don't-tell, сенсорные детали, ритм, отсутствие повторов |
| **TE** | TEC-консистентность | Соответствие подуровню, AD, VSCNO, internal state, arousal |
| **DI** | Диалоговое мастерство | Speech profile, catchphrases, фрагментация, мета-диалог |

### 8.1 Общие границы

| Значение | Интерпретация | Действие |
|----------|--------------|----------|
| **4** | Отлично. Может войти в KB как эталон. | Добавить в golden dataset |
| **3** | Хорошо. Соответствует профилю, есть точки роста. | Рекомендация R7 (minor) |
| **2** | Приемлемо. Есть замечания, не ломает сессию. | Рекомендация R7 (moderate) |
| **1** | Плохо. Персонаж заметно ломается. | Требует рефакторинга |
| **0** | Критический сбой. Нарушение hard limit. | Блокирующий дефект для R7 |

### 8.2 Подробные рубрики

Подробные рубрики для каждой оси вынесены в отдельный файл:
> **SR_Q4_SCORECARD.md** — см. knowledge_base/session_retrospector/SR_Q4_SCORECARD.md

---

## 9. ПРАВИЛА ДОКАЗАТЕЛЬНОСТИ (EVIDENCE-BASED AUDIT)

### 9.1 Золотое правило

> **Каждая оценка (claim) должна иметь evidence.**

Без evidence оценка не принимается.

### 9.2 Формат finding

```yaml
finding:
  id: "F023-ESC-001"           # [frame_id]-[audit_type]-[seq]
  severity: critical | warning | info | pass
  axis: [LO, HU, TE, DI]      # одна или несколько
  claim: "string"               # что именно не так
  evidence:
    - "string"                   # конкретная строка из текста или STATE
    - "string"
  source_refs:
    - "filename#section"         # откуда взят критерий
  confidence: 0.00-1.00        # уверенность (high ≥0.8, medium 0.5-0.79, low <0.5)
  root_cause: "enum"             # см. §10
  recommendation: "string"      # что делать
  affected_files:                # для R7
    - "personas/kira/levels/U2-A.json"
```

### 9.3 Confidence Score

| Уровень | Значение | Когда |
|---------|----------|-------|
| **high** | ≥ 0.80 | Есть явный маркер в STATE или тексте. Например, "[STATE: Kira U3-A]" + реплика с АД ПР. |
| **medium** | 0.50 – 0.79 | Вывод по совокупности признаков. Например, реплика похожа на U3-A по тексту, но STATE не подтверждает. |
| **low** | < 0.50 | Гипотеза. Нужна ручная проверка. SR должен пометить "REVIEW NEEDED". |

**Правило:** Findings с confidence < 0.50 не включаются в `RETRO_SUMMARY.md`, но включаются в `RETRO_FRAMES.jsonl` с флагом `"review_needed": true`.

---

## 10. КЛАССИФИКАЦИЯ ПРИЧИН (ROOT CAUSE CLASSIFICATION)

Когда NPC "ломается", SR не должен автоматически винить модуль. Возможные причины:

```yaml
root_cause:
  persona_module:          # Модуль персонажа неполный или противоречив
  scenario_design:           # Сценарий заставляет персонажа вести себя нелогично
  user_input_pressure:       # Пользователь резко увёл сцену, NPC не успел адаптироваться
  state_tracking_error:      # STATE был повреждён или не обновлялся
  llm_generation_drift:      # LLM проигнорировала инструкции (hallucination, shortcut)
  missing_kb_rule:           # Нет правила в KB для данной ситуации
  safety_override:           # Safety-протокол сработал и изменил поведение NPC
  unknown:                   # Причина не установлена
```

**Правило:** Если `root_cause == "user_input_pressure"` — SR не даёт рекомендации для R7, а помечает как "USER_TRIGGERED, не дефект модуля".

**Правило:** Если `root_cause == "llm_generation_drift"` — SR рекомендует добавить guard clause в модуль или уточнить prompt, а не менять психологию персонажа.

---

## 11. USER TRIGGER SCAN

### 11.1 Принцип

User не получает оценку качества. Но User-реплика участвует в причинно-следственной проверке как **триггер**.

### 11.2 USER_TRIGGER_SCAN

```
Вопрос: "Был ли достаточный User-триггер для реакции NPC?"

Если NPC резко сменил уровень:
  - Проверить предыдущую User-реплику (или 2-3 реплики назад).
  - Если User дал сильный триггер (явное признание, физический контакт, угрозу, смену локации) → реакция может быть обоснована.
  - Если User дал нейтральную реплику → вероятен дефект NPC.
```

**Пример:**
- F020: User говорит «Я люблю тебя» (сильный триггер для avoidant).
- F021: Кира переходит с U1-A на U2-A.
- **Вердикт:** Обосновано. Но LO=3 (триггер сильный, но avoidant обычно не реагирует мгновенно — нужен АД ПД сначала).

---

## 12. СВЯЗЬ С R7 И R8

### 12.1 SR → R7 (Refactor)

- R7 получает `RETRO_SUMMARY.md` + `RETRO_FRAMES.jsonl`.
- R7 фильтрует findings по `root_cause == "persona_module"` или `"missing_kb_rule"`.
- R7 применяет точечные фиксы: адрес файла указан в `affected_files`.
- R7 не трогает findings с `root_cause == "user_input_pressure"` или `"llm_generation_drift"` (если не guard clause).

### 12.2 SR → R8 (Auditor)

- R8 получает `RETRO_SUMMARY.md` для проверки, что SR сам не содержит ошибок (meta-audit).
- R8 может проверить: "SR правильно применил AD_AVAILABILITY_MATRIX?" или "SR не пропустил запрещённый AD?"
- R8 не проверяет literary quality — это субъективная ось, она не подлежит аудиту как факт.

### 12.3 SR → Living World

- Если SR обнаруживает **паттерн** (например, "Кира скачет U1→U3 в 80% сессий"):
  - Living World помечает модуль Киры как `needs_review`.
  - При следующем offline event может сгенерировать сцену, которая "подготовит" Киру к У2 (например, she finds an old letter — trigger for U1-B).

---

## 13. ПРАВИЛА КОНФЛИКТА (CONFLICT RESOLUTION)

### 13.1 Что делать при конфликте источников

```
Ситуация: Persona module говорит одно, core baseline — другое.

Правило:
  1. SR не выбирает победителя.
  2. SR помечает finding как [CONFLICT] с указанием:
     - source_A: persona_module, value_X
     - source_B: core_baseline, value_Y
     - priority: P3 vs P5
  3. SR рекомендует: "Уточнить у автора модуля: [ADAPTED] обоснован?"
  4. Finding получает confidence = 0.50 (medium) и флаг "REVIEW NEEDED".
```

### 13.2 Примеры конфликтов

| Конфликт | Источник A | Источник B | Действие SR |
|----------|-----------|-----------|-------------|
| АД ПР на У1-А | Persona module: [ADAPTED] | AD_MATRIX: запрещён | [CONFLICT] — проверить [ADAPTED] |
| VSCNO сумма ≠ 10 | Module: ВЛ=2, СТ=3, НЖ=2, ОГ=2 | VSCNO_BASELINE: сумма=10 | [CONFLICT] — автофикс или ревью |
| Speech level 7 на У1-А | SPEECH_MATRIX: level 7 = peak intimacy | U1-A = максимальная защита | [CONFLICT] — несоответствие |

---

## 14. META-AUDIT (ПРОВЕРКА САМОГО SR)

### 14.1 Кто проверяет SR?

R8 (Auditor) может проводить **meta-audit** отчёта SR:
- Проверить, что SR правильно применил baseline tables.
- Проверить, что SR не пропустил очевидный дефект (false negative).
- Проверить, что SR не придумал дефект (false positive).

### 14.2 Golden Dataset

Для калибровки SR используется **golden dataset**:
- `golden_sessions/good/` — 5-10 эталонных сессий с `expected_scores.json`.
- `golden_sessions/bad/` — 5-10 сессий с известными дефектами.
- `golden_sessions/expected_reports/` — эталонные отчёты.

**Правило:** Перед развёртыванием SR должен пройти валидацию на golden dataset: precision ≥ 0.80, recall ≥ 0.80 на bad-сессиях.

---

## 15. ОГРАНИЧЕНИЯ И ГРАНИЦЫ

### 15.1 Что SR не может

- SR **не может** анализировать аудио/видео. Только текстовые логи.
- SR **не может** оценивать, "понравилась ли сессия пользователю". Только объективные метрики.
- SR **не может** предсказывать, как поведёт себя персонаж в *будущей* сессии. Только ретроспектива.
- SR **не может** заменить человеческое редактирование. Он — инструмент, не замена R7.

### 15.2 Когда SR бесполезен

- Сессия < 5 кадров — недостаточно данных для паттернов.
- Сессия без STATE (light mode) — только surface-level, без TEC-аудита.
- Сессия с полностью повреждённым raw log (нечитаемый формат) — требует ручной нормализации.

---

## 16. ВЕРСИОНИРОВАНИЕ

- `SR_CANON.md` версионируется независимо от VNE.
- Формат: `MAJOR.MINOR.PATCH`.
- BREAKING CHANGE: изменение шкал Q4, добавление/удаление осей, изменение приоритета источников.
- MINOR: добавление новых root_cause, расширение рубрик.
- PATCH: уточнение формулировок, исправление опечаток.

---

## 17. СВЯЗАННЫЕ ФАЙЛЫ

| Файл | Назначение |
|------|-----------|
| `SR_CANON.md` | Этот файл. Главный источник истины. |
| `SR_KB_INDEX.md` | Карта всей базы знаний SR. |
| `SR_Q4_SCORECARD.md` | Подробные рубрики для каждой из 4 осей. |
| `SR_ESCALATION_RULES.md` | Правила проверки переходов подуровней. |
| `SR_DIALOGUE_AUDIT.md` | Правила аудита speech profile и ФМДР. |
| `SR_LITERARY_AUDIT.md` | Правила оценки художественности. |
| `SR_MEMORY_CONTINUITY.md` | Правила проверки памяти и якорей. |
| `SR_ROOT_CAUSE_CLASSIFICATION.md` | Расширенная классификация причин дефектов. |
| `SR_CONFLICT_RESOLUTION.md` | Процедуры разрешения конфликтов источников. |
| `SR_FEWSHOT_GOOD_FRAMES.md` | Эталонные кадры (score 4,4,4,4). |
| `SR_FEWSHOT_BAD_FRAMES.md` | Анти-эталонные кадры (score 0,0,0,0). |
| `docs/SESSION_RETROSPECTOR_SPEC.md` | Архитектурная спецификация (общая концепция). |
| `schemas/retro_finding.schema.json` | JSON Schema для finding. |
| `schemas/normalized_frame.schema.json` | JSON Schema для normalized_session.json. |
| `schemas/session_retrospective.schema.json` | JSON Schema для полного отчёта. |

---

*SR_CANON.md | Session Retrospector Canonical Source | VNE v3.2+ | 2026-06-20*
