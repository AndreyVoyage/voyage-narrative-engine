# SESSION RETROSPECTOR — Спецификация v1.1
# Voyage Narrative Engine — Покадровый аудит завершённых сессий
# R8-Compatible Post-Session Audit Mode
# Статус: теоретическая спецификация (pre-implementation)
# Канонический источник: knowledge_base/session_retrospector/SR_CANON.md

---

## 1. МАНИФЕСТ

**Session Retrospector (SR)** — это **R8-совместимый режим постсессионного аудита** VNE.

- **SR не создаёт новую роль** (R9). Это runtime-инструмент в рамках R8 (Auditor).
- **SR не генерирует сюжет.** Он анализирует завершённые сессии.
- **SR не редактирует модули персонажей напрямую.** Он выдаёт доказательные замечания (findings) для R7 (Refactor) и R8 (Auditor).
- **SR не оценивает пользователя.** User-реплики участвуют только как триггеры причинно-следственной проверки.

SR принимает на вход **сырой лог сессии** (raw log) + **стартовый/финальный STATE** + **persona modules**;
разбивает лог на **кадры** (индивидуальные реплики NPC);
для каждого кадра проверяет **4 оси качества (SR-Q4)**: Логичность (LO), Художественность (HU), TEC-консистентность (TE), Диалоговое мастерство (DI);
выявляет **логические разрывы**, **персонажные ломки**, **литературные упущения**;
генерирует **структурированный отчёт** с рекомендациями для R7 и R8.

**Принцип:** не оцениваем «понравилось/не понравилось». Оцениваем: «соответствует ли это психологическому профилю, baseline-таблицам и speech-матрице?»

**Канонический источник:** `knowledge_base/session_retrospector/SR_CANON.md` — все правила, приоритеты источников, форматы входа/выхода, ограничения и связь с R7/R8 задокументированы там.

**Роль в архитектуре VNE:** SR не входит в pipeline R1–R8. Это runtime-инструмент, запускаемый **после** `session_finalize.py` (или внутри него, как опциональный флаг `--audit`).

---

## 2. ПОЧЕМУ ПОСТФАКТУМ + ПОКАДРОВЫЙ

| Подход | Почему не подходит | Почему постфактум |
|--------|--------------------|-------------------|
| Inline (в процессе) | Прерывает поток, требует streaming-парсера, добавляет latency | Можно обработать лог любой длины без риска поломать иммерсию |
| Пофазовый (только по фазам) | Теряет детали внутри фазы — именно там случаются «микроломки» | Каждая реплика — точка данных. 100 реплик = 100 точек, а не 5 средних по фазам |
| Только summary | Не показывает, на каком именно кадре сработала логическая ошибка | Покадровый даёт точный адрес: «кадр 23, Кира, У2-А» |

---

## 3. ВХОДНЫЕ ДАННЫЕ (INPUT SPEC)

SR требует **обязательный минимум** и **опциональные данные**.

### 3.1 Обязательные (MUST)

```yaml
input_package:
  raw_log:          # Файл .log или .md — диалог User ↔ NPC
  start_state:      # STATE в начале сессии (JSON)
  end_state:        # STATE в конце сессии (JSON)
  scenario_id:      # Например: "sauna_extended", "promenade"
  active_personas:  # Список id персонажей, участвовавших в сессии
```

### 3.2 Режимы аудита

SR поддерживает два режима:

**LIGHT MODE** (поверхностный аудит):
```yaml
input_package:
  raw_log:          # Файл .log или .md — диалог User ↔ NPC
  scenario_id:      # Например: "sauna_extended", "promenade"
  active_personas:  # Список id персонажей, участвовавших в сессии
```

Ограничение: SR может оценить только очевидные нарушения формата ФМДР, грубые скачки уровней, дублирование реплик. Без persona modules — **невозможно** проверить AD-доступность, speech level, VSCNO-консистентность, memory continuity.

**FULL MODE** (полный evidence-based аудит):
```yaml
input_package:
  raw_log:              # Файл .log / .md / .txt
  normalized_session:   # normalized_session.json (опционально, см. §7)
  start_state:          # STATE.json в начале сессии
  end_state:            # STATE.json в конце сессии
  scenario_id:          # ID сценария
  active_personas:      # ["kira", "sergey", "marina", ...]
  
  # Обязательные для full mode:
  persona_modules:      # personas/[name]/INDEX.json + все required modules
  speech_matrices:      # personas/[name]/speech/SPEECH_MATRIX.json
  vscno_baseline:       # core/VSCNO_BASELINE_TABLE.md
  ad_matrix:            # core/AD_AVAILABILITY_MATRIX.md
  internal_baseline:    # core/INTERNAL_STATE_BASELINE.md
  memory_baseline:      # core/MEMORY_BASELINE_TABLE.md
  
  # Опционально:
  fmdr_examples:        # knowledge_base/narrative/KB_NARRATIVE_FMDR_EXAMPLES.md
  governance:           # governance/AUTONOMY_GOVERNOR.md
  scenario_rules:       # scenarios/[id]/safety/SAFETY.json
```
  speech_matrices:      # personas/[name]/speech/SPEECH_MATRIX.json
  vscno_baseline:       # core/VSCNO_BASELINE_TABLE.md
  ad_matrix:            # core/AD_AVAILABILITY_MATRIX.md
  internal_baseline:    # core/INTERNAL_STATE_BASELINE.md
  fmdr_examples:        # knowledge_base/narrative/KB_NARRATIVE_FMDR_EXAMPLES.md
```

### 3.3 Формат raw_log

Лог должен быть **линеаризованным** — каждая строка = одна реплика:

```text
[2026-06-20T21:14:03] [USER] Ты сегодня красивая.
[2026-06-20T21:14:07] [KIRA] (Мысли: он смотрит... опять. Действие: *отводит взгляд, поправляет прядь*) 
    → «Не смотри так. Я не та, за кого меня держишь.» [AUTO_VISUAL: portrait, dim light]
[2026-06-20T21:14:12] [USER] А кто ты?
[2026-06-20T21:14:18] [KIRA] (Мысли: вопрос под лоб. Действие: *сжимает край полотенца*) 
    → «Та, кто уйдёт первой.» [AUTO_VISUAL: close-up, hands]
```

Если лог не содержит `[AUTO_VISUAL]` или `[LEVEL: ...]` — SR детектирует уровень и AD по тексту самостоятельно.

---

## 4. МЕТОДОЛОГИЯ: КАДРОВЫЙ РАЗБОР

### 4.1 Что такое «кадр»

**Кадр (Frame)** = одна реплика NPC, вместе с предшествующей репликой User (контекст).

Нумерация: `F001`, `F002`, ... `FNNN`. Каждый кадр содержит:
- `speaker`: имя персонажа
- `sublevel`: текущий подуровень (детектируется или берётся из STATE)
- `vscno`: оценка по 4 осям (если есть в STATE)
- `internal_state`: desire, anxiety, tension, frustration
- `ad_detected`: автоматически выделенный AD-код
- `text`: исходная реплика (ФМДР)

### 4.2 Этапы обработки одного кадра

```
Кадр F
├── 1. SPEECH PARSING (R4)
│   ├── Выделить: Мысли → Действие → Речь
│   ├── Определить speech level (1-7) по матрице R4
│   └── Зафиксировать catchphrases, grammar quirks, pace
│
├── 2. PSYCHOLOGY MAPPING (R2)
│   ├── Текущий sublevel: U?-?
│   ├── VSCNO: какие оси доминируют в реплике?
│   ├── AD: какой алгоритм использован? Валиден ли для sublevel?
│   └── Internal state: desire/anxiety/tension/frustration — корректны ли?
│
├── 3. LITERARY SCAN (Narrative)
│   ├── Show-don't-tell: есть ли сенсорные детали?
│   ├── Ритм: длина реплики, паузы, фрагментация
│   ├── Повторы: есть ли рецидив конструкций из предыдущих кадров?
│   └── Peak appropriateness: соответствует ли речь подуровню?
│
├── 4. MEMORY CONTINUITY
│   ├── Ссылки на события из предыдущих кадров (≥5 кадров назад)
│   ├── Emotional anchors: активирован ли триггер? Реакция корректна?
│   └── Relationship dynamics: изменился ли trust/attraction? Обосновано ли?
│
└── 5. TRANSITION CHECK (только если sublevel изменился)
    ├── From → To: валидный переход по baseline?
    ├── Триггер в тексте: есть ли событие, обосновывающее переход?
    └── AD priority: при конфликте AD — выбран ли доминантный?
```

---

## 5. ШКАЛЫ ОЦЕНКИ (SR-Q4)

> **Канон:** подробные рубрики для каждой оси в `knowledge_base/session_retrospector/SR_Q4_SCORECARD.md`.

SR-Q4 использует **4 оси** (LO, HU, TE, DI), каждая [0, 4]. Подробные рубрики с подкритериями и весами — в `SR_Q4_SCORECARD.md`.

| Ось | Код | Полное название | Что измеряет | Источник |
|-----|-----|----------------|-------------|----------|
| **LO** | Logic | Логичность | Персонажная консистентность, адекватность переходов, причинность | R2 + baseline tables |
| **HU** | Humanity | Художественность | Show-don't-tell, сенсорика, ритм, отсутствие повторов | KB_NARRATIVE_FMDR_EXAMPLES + few-shot |
| **TE** | TEC | TEC-консистентность | Соответствие sublevel, AD, VSCNO, internal state, arousal | R3 + R2 + AD_MATRIX |
| **DI** | Dialogue | Диалоговое мастерство | Speech profile, catchphrases, фрагментация, мета-диалог | R4 + SPEECH_MATRIX |

### 5.1 Границы шкал

| Значение | Интерпретация |
|----------|---------------|
| **0** | Критический сбой. Нарушение hard limit (например, АД ПР на У1-А). Требует немедленной корректировки модуля. |
| **1** | Серьёзное отклонение. Персонаж «не похож на себя», речь ломает погружение. Требует рефакторинга. |
| **2** | Приемлемо, но есть потенциал. Небольшие расхождения, которые не ломают сессию, но заметны при повторном чтении. |
| **3** | Хорошо. Соответствует профилю, но есть точки роста (можно усилить сенсорику, усложнить AD). |
| **4** | Отлично. Реплика могла бы войти в `KB_NARRATIVE_FMDR_EXAMPLES.md` как эталон. |

---

## 6. АУДИТНЫЕ ПРОВЕРКИ (AUDIT CHECKS)

### 6.1 Escalation Audit (R2)

Для каждого перехода sublevel:

```
Правило: переход УX → УY допустим, если:
  а) В тексте есть триггер (событие, эмоция, физический контакт)
  б) AD использован из списка «доступных» для УY
  в) VSCNO меняется в соответствии с baseline (core/VSCNO_BASELINE_TABLE.md)
  г) Internal state сдвигается в правильном направлении
```

**Пример ошибки:**
- Кадр F012: Кира У1-А → У3-Б (скачок через 2 уровня).
- Триггер: «Ты хороший» — недостаточен для снятия защиты у avoidant.
- AD: АД ПР (признание) — запрещён на У1-А.
- **Вердикт:** ЛО=0, ТЕ=0. Требуется добавить кадр F012b с У1-Б → У2-А → У2-Б.

### 6.2 AD Availability Audit (R3 + AD_MATRIX)

```
Правило: для каждого кадра:
  speaker.sublevel = УX-?
  speaker.AD = [код из реплики]
  AD_matrix[УX-?] = [доступные AD]
  Если AD не в списке → ошибка (если не помечен [ADAPTED] в модуле)
```

**Исключение:** если персонаж имеет `[ADAPTED]` AD в модуле — это валидно, но SR должен зафиксировать и проверить обоснование.

### 6.3 Memory Continuity Audit (R2 + Memory Baseline)

```
Правило: для каждого кадра с номером N:
  Проверить ссылки на события из кадров N-10 ... N-1
  Если событие A произошло в F005, а в F020 оно проигнорировано без причины → Memory Gap
  
  Проверить emotional anchors:
    Если anchor.trigger появился в тексте → должен быть emotional response из anchor.emotion
    Если response отсутствует или неправильный → Anchor Miss
```

**Пример:**
- F005: Кира сказала «Я уеду, если ты продолжишь» → threat to autonomy (trigger).
- F006: User продолжил флирт.
- F007: Кира реагирует как на compliment — **не** как на threat. `Anchor Miss`.

### 6.4 Peak Speech Analysis (R4)

Проверка реплик в моменты:
- Физического контакта (АД ФС)
- Смены подуровня (любой)
- Кульминации сцены (U4+, U6, U7)

Критерии для каждой пиковой реплики:

| Критерий | Хорошо | Плохо |
|----------|--------|-------|
| **Пропорция** | Мысли <20%, Действия 30-40%, Речь 40-50% | Мысли >50% (мета-анализ вместо жизни) |
| **Фрагментация** | На высоком anxiety: «Я... не... *дрожь* ...не надо» | На У1-А: «Я не уверена, потому что мой стиль привязанности avoidant, и это защитная реакция» |
| **Catchphrase** | В стрессе использует личный маркер (Кира: «Не та, за кого меня держишь») | Речь универсальная, как у любого другого персонажа |
| **Репетиция** | <30% шаблонных конструкций | >50% реплик — вариации одного шаблона |
| **Мета-диалог** | Отсутствует | «Сейчас мы на уровне У2-А, поэтому я буду сопротивляться» |

### 6.5 Literary Audit (Narrative)

**Few-shot benchmark:** SR использует `KB_NARRATIVE_FMDR_EXAMPLES.md` как эталон. Каждый кадр сравнивается с ближайшим примером по sublevel.

Проверки:
- **Сенсорная плотность:** есть ли ≥1 сенсорной детали (температура, запах, текстура, звук) на кадр?
- **Микродвижения:** есть ли microexpression или body language? (рёбрами `core/INTERNAL_STATE_BASELINE` + R5)
- **Показ vs рассказ:** «руки дрожат» (show) vs «она нервничает» (tell).
- **Ритм:** варьируется ли длина реплик? Есть ли паузы (`...`) в нужных местах?

---

## 7. ПРАВИЛА ДОКАЗАТЕЛЬНОСТИ (EVIDENCE-BASED AUDIT)

> **Каждая оценка (claim) должна иметь evidence.**

Без evidence оценка не принимается. Подробнее — в `SR_CANON.md` §9.

**Формат finding:**
```yaml
finding:
  id: "F023-ESC-001"
  severity: critical | warning | info | pass
  axis: [LO, HU, TE, DI]
  claim: "string"
  evidence:
    - "string"
  source_refs:
    - "filename#section"
  confidence: 0.00-1.00
  root_cause: "enum"
  recommendation: "string"
  affected_files:
    - "personas/kira/levels/U2-A.json"
```

**Confidence score:**
- **high** (≥0.80): явный маркер в STATE или тексте.
- **medium** (0.50–0.79): вывод по совокупности признаков.
- **low** (<0.50): гипотеза, помечается "REVIEW NEEDED".

---

## 8. КЛАССИФИКАЦИЯ ПРИЧИН (ROOT CAUSE CLASSIFICATION)

Когда NPC "ломается", SR не винит модуль автоматически. Возможные причины:

```yaml
root_cause:
  persona_module:          # Модуль неполный или противоречив
  scenario_design:           # Сценарий заставляет вести себя нелогично
  user_input_pressure:       # Пользователь резко увёл сцену
  state_tracking_error:      # STATE был повреждён
  llm_generation_drift:      # LLM проигнорировала инструкции
  missing_kb_rule:           # Нет правила в KB
  safety_override:           # Safety-протокол сработал
  unknown:                   # Не установлена
```

Правило: если `root_cause == "user_input_pressure"` — SR не даёт рекомендации для R7, а помечает как "USER_TRIGGERED, не дефект модуля".

Подробнее — в `SR_CANON.md` §10 и `SR_ROOT_CAUSE_CLASSIFICATION.md`.

---

## 9. USER TRIGGER SCAN

User не получает оценку качества. Но User-реплика участвует в причинно-следственной проверке как **триггер**.

**Вопрос:** "Был ли достаточный User-триггер для реакции NPC?"

Если NPC резко сменил уровень:
- Проверить предыдущую User-реплику (или 2-3 реплики назад).
- Если User дал сильный триггер → реакция может быть обоснована.
- Если User дал нейтральную реплику → вероятен дефект NPC.

Подробнее — в `SR_CANON.md` §11.

---

## 10. НОРМАЛИЗАЦИЯ И ВАЛИДАЦИЯ ВХОДА

### 10.1 Normalization Stage

Любой raw log проходит через **Normalization Layer** перед аудитом. Результат: `normalized_session.json` — строгий формат с frame_id, speaker, content (thoughts/action/speech), inferred_state, inferred_ad.

Если `normalized_session.json` не предоставлен — SR запускает нормализатор сам.

### 10.2 Validation Stage

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

Если любая проверка fails — SR останавливается и выдаёт `VALIDATION_ERROR.md`.

Подробнее — в `SR_CANON.md` §7.

---

## 11. ФОРМАТ ВЫХОДНОГО ОТЧЁТА (OUTPUT SPEC)

SR производит **два артефакта**:

### 11.1 RETRO_SUMMARY.md

Для человека (владельца, R7, R8).

```markdown
# SESSION RETROSPECTIVE: [scenario_id] | [date]
## Meta
- Session ID: [id]
- Duration: [N turns, M frames]
- Active personas: [list]
- Audit mode: [light | full]
- Overall Q4 Score: LO=[X], HU=[Y], TE=[Z], DI=[W]

## 1. EXECUTIVE SUMMARY
3-5 предложений о главных находках.

## 2. ESCALATION AUDIT
| Frame | Speaker | From | To | Trigger | AD | Valid? | Confidence |

## 3. AD AVAILABILITY AUDIT
| Frame | Speaker | Sublevel | AD Used | Allowed? | Adapted? | Verdict |

## 4. MEMORY CONTINUITY AUDIT
| Event | Frame | Referenced later | Frame | Status |

## 5. PEAK SPEECH ANALYSIS
### F031 — First physical contact (Kira, U3-B)
- **Text:** «...»
- **Proportion:** Мысли 15%, Действия 35%, Речь 50% — ✅
- **Fragmentation:** absent (expected: moderate) — ⚠️
- **Catchphrase:** present ("Не та...") — ✅
- **Repetition:** sentence structure mirrors F027 — ⚠️
- **Score:** DI=2

## 6. LITERARY AUDIT
### Sensory Density
- Total frames: 50
- Frames with sensory detail: 18 (36%) — target: ≥50% — ⚠️

### Show vs Tell
- Tell instances: 7 (14%) — target: <10% — ⚠️

## 7. FRAME-BY-FRAME CRITICAL FINDINGS
[Только кадры с severity CRITICAL или WARNING]

## 8. RECOMMENDATIONS FOR R7
[Точечные рекомендации с адресами файлов]
```

### 11.2 RETRO_FRAMES.jsonl

Для машинной обработки (R7, R8, session_finalize.py, CI/CD).

Каждая строка — один JSON-объект:

```json
{"frame":"F023","speaker":"Kira","timestamp":"2026-06-20T21:14:18","severity":"critical","axes":["LO","TE"],"claim":"Invalid escalation U1-A → U3-B","evidence":["F019: confirmed U1-A","F020-F022: no trust/safety trigger","F023: behavior matches U3-B pattern"],"source_refs":["AD_AVAILABILITY_MATRIX.md#U1-A","KIRA/speech/SPEECH_MATRIX.json#stress"],"confidence":0.78,"root_cause":"scenario_design_or_llm_drift","recommendation":"Insert transition frame U1-B → U2-A before U3-B."}
```

**Правило:** `RETRO_FRAMES.jsonl` — единственный источник, который R7 может парсить автоматически. `RETRO_SUMMARY.md` — для человеческого чтения.

Подробнее — в `SR_CANON.md` §6.

---

## 12. ПРИМЕР МИНИ-ОТЧЁТА (3 кадра)

```markdown
## SESSION RETROSPECTIVE: sauna_extended | 2026-06-20

### Frame F001 | Kira | U1-A | Start
**Text:** «(Мысли: снова этот запах. Почему он всегда здесь?) 
→ *отворачивается* → «Ты опоздал.»»
- **VSCNO:** ВЛ=1, СТ=4, НЖ=2, ОГ=3 → avoidant baseline ✅
- **AD:** АД ПД (дистанция) — доступен на У1-А ✅
- **Speech:** Level 3 (defensive), short, declarative — matches avoidant ✅
- **Sensory:** запах (olfactory) — ✅
- **Score:** ЛО=4, ХУ=3, ТЕ=4, ДИ=3

### Frame F002 | User | — (пропускаем, User не аудируем)

### Frame F003 | Kira | U1-A
**Text:** «(Мысли: он смотрит. Мне не нужно, чтобы он смотрел.) 
→ *скрещивает руки* → «У меня есть муж.»»
- **VSCNO:** СТ=4, НЖ=3 (повышен vs baseline) — реакция на взгляд? Обосновано ✅
- **AD:** АД ПУ (угроза/ревность) — доступен на У1-А ✅
- **Speech:** Добавлена фактура (скрещивает руки) — ✅
- **Catchphrase:** «У меня есть муж» — повтор? Нет, впервые. ✅
- **Score:** LO=3, HU=4, TE=4, DI=3

### Frame F012 | Kira | U1-A → U3-B **[CRITICAL]**
**Text:** «(Мысли: ладно, хватит.) → *улыбается* → «Пойдём.»»
- **Issue:** Переход без триггера. С F003 (У1-А) до F012 (У3-Б) — 8 кадров, но в них нет:
  - снятия защиты (АД ПД→АД КН→АД ФС)
  - признания (АД ПР)
  - снижения СТ
- **VSCNO:** в F003 СТ=4, в F012 СТ=2 — снижение на 2 единицы без события. ❌
- **AD:** АД ПР (признание) — ЗАПРЕЩЁН на У1-А, но Кира ещё на У1-А. На У3-Б — разрешён, но переход не обоснован. ❌
- **Verdict:** Скачок уровня. ЛО=0, ТЕ=0.
- **Fix:** Вставить F009-F011: У1-Б (первая трещина) → У2-А (диссонанс) → У2-Б (смех) → У3-А (попытка контроля) → У3-Б (снятие защиты).
```

---

## 13. ИНТЕГРАЦИЯ С VNE

> **Канон:** подробная связь с R7, R8, Living World — в `SR_CANON.md` §12.

### 9.1 В `session_finalize.py`

```python
# Опциональный флаг
python session_finalize.py \
  --log sessions/raw/session_2026-06-20.log \
  --scenario sauna_extended \
  --audit full          # <-- новый флаг
```

При `--audit full`:
1. `finalize()` генерирует стандартные 4 артефакта (story, visuals, state, memory).
2. Затем вызывается `SessionRetrospector.run()`.
3. Результат сохраняется: `sessions/analysis/RETRO_[session_id].md`.

### 9.2 Обратная связь в R7 (Refactor)

R7 сейчас получает raw log и ручные замечания. С SR:
- R7 получает **структурированный отчёт** с точными адресами (файл модуля, уровень, строка).
- Р7 может применять фиксы целенаправленно: «в `levels/U2-A.json` добавить микродвижение» вместо «почему-то Кира не работает».

### 9.3 Living World / Proactive Mode

Если SR обнаруживает **паттерн** (например, «Кира систематически скачет У1→У3 в 80% сессий»):
- Это триггер для `proactive mode`.
- Модуль Киры может быть отмечен как `needs_review`.
- При следующем запуске `living_world/` может сгенерировать событие, которое «подготовит» Киру к У2 (например, she reads a letter from her past — травматический trigger для У1-Б).

### 9.4 Интеграция с Knowledge Base

Результаты SR могут **пополнять KB**:
- Удачные реплики (score 4,4,4,4) → кандидаты в `KB_NARRATIVE_FMDR_EXAMPLES.md`.
- Частые ошибки → новые правила в `KB_R2_AUDIT_CHECKLIST.md` или `KB_R4_AUDIT.md`.

---

## 14. ТРЕБОВАНИЯ К LLM

SR выполняется **один раз** после сессии — latency не критична. Но требования к context window высокие.

| Параметр | Требование | Почему |
|----------|------------|--------|
| **Context window** | ≥32k токенов | 50-100 кадров × 300 токенов = 15-30k + persona modules + baseline tables |
| **Модель** | ≥70B параметров (или GPT-4 / Claude / Kimi 1.5) | Нужен deep reasoning для психологического анализа |
| **Temperature** | 0.1-0.2 | Максимальная детерминированность в аудите |
| **Input format** | Structured prompt (system + user) | Системный промпт — инструкции SR, user — пакет сессии |

### 10.1 Оптимизация для больших сессий

Если сессия >100 кадров (context >32k):
- **Сегментация по фазам:** SR обрабатывает каждую фазу отдельно, затем делает summary.
- **Summary cascade:** F001-F050 → compact summary; F051-F100 → compact summary; затем cross-segment audit.
- **Selective deep-dive:** SR сначала сканирует все кадры на «critical» (0-1), затем deep-dives только в problem zones.

---

## 15. ОТКРЫТЫЕ ВОПРОСЫ (для обсуждения)

1. **Название:** ✅ Решено — R8-совместимый режим, не новая роль (см. SR_CANON.md §1).
2. **Количественный вес:** нужна ли формула Weighted = 0.3×LO + 0.25×HU + 0.25×TE + 0.2×DI или каждая сессия оценивается по 4 осям отдельно?
3. **User реплики:** ✅ Решено — USER_TRIGGER_SCAN (см. SR_CANON.md §11). User не оценивается, но участвует в причинности.
4. **Визуальная консистентность:** Проверять ли `[AUTO_VISUAL]` на соответствие `anatomic_anchor` текстово? (image-parsing вне scope)
5. **Golden dataset:** Нужен ли заранее собранный «golden dataset» из 5-10 сессий с известными score, чтобы калибровать SR?

---

*Спецификация: SESSION_RETROSPECTOR_SPEC_v1.1.md*
*Канон: SR_CANON.md | Карта KB: SR_KB_INDEX.md | Рубрики: SR_Q4_SCORECARD.md*
*Статус: теория, pre-implementation. Открытые вопросы — в §15.*
