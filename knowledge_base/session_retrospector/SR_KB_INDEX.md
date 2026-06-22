# SR_KB_INDEX.md
# Session Retrospector — Knowledge Base Index
# Карта всей базы знаний, используемой SR
# Версия: 1.0.0 | Дата: 2026-06-20

---

## 1. НАЗНАЧЕНИЕ

Этот файл — **карта** всей базы знаний Session Retrospector. Он не содержит правил напрямую, но указывает:
- какие KB-файлы существуют;
- за что каждый отвечает;
- приоритет (P0–P7) по SR_CANON.md §4;
- статус: готов / в разработке / не создан.

SR при загрузке читает `SR_KB_INDEX.md` первым делом, чтобы знать, какие источники доступны.

---

## 2. СТРУКТУРА БАЗЫ ЗНАНИЙ

```
knowledge_base/session_retrospector/
├── SR_KB_INDEX.md              ← Этот файл (карта)
├── SR_Q4_SCORECARD.md          ← Рубрики оценки по 4 осям
├── SR_ESCALATION_RULES.md      ← Правила проверки переходов подуровней
├── SR_DIALOGUE_AUDIT.md        ← Правила аудита speech profile и ФМДР
├── SR_LITERARY_AUDIT.md        ← Правила оценки художественности
├── SR_MEMORY_CONTINUITY.md     ← Правила проверки памяти и якорей
├── SR_ROOT_CAUSE_CLASSIFICATION.md ← Классификация причин дефектов
├── SR_CONFLICT_RESOLUTION.md   ← Процедуры разрешения конфликтов
├── SR_FEWSHOT_GOOD_FRAMES.md  ← Эталонные кадры (score 4+)
├── SR_FEWSHOT_BAD_FRAMES.md   ← Анти-эталонные кадры (score 0+)
└── SR_CHANGELOG.md            ← История изменений KB
```

---

## 3. ТАБЛИЦА KB-ФАЙЛОВ

| # | Файл | Отвечает за | Приоритет | Статус | Комментарий |
|---|------|------------|-----------|--------|-------------|
| 1 | `SR_CANON.md` | Главный источник истины: назначение, форматы, правила, приоритеты | P1 | ✅ Ready | Создан 2026-06-20 |
| 2 | `SR_KB_INDEX.md` | Карта KB (этот файл) | P1 | ✅ Ready | Создан 2026-06-20 |
| 3 | `SR_Q4_SCORECARD.md` | Рубрики оценки LO, HU, TE, DI | P1 | 📝 Pending | Требует создания |
| 4 | `SR_ESCALATION_RULES.md` | Правила U?-A → U?-B, допустимые скачки, триггеры | P5 | 📝 Pending | Синтез из VSCNO_BASELINE + AD_MATRIX |
| 5 | `SR_DIALOGUE_AUDIT.md` | Speech level, catchphrase, фрагментация, мета-диалог | P4 | 📝 Pending | Зависит от SPEECH_MATRIX |
| 6 | `SR_LITERARY_AUDIT.md` | Show-don't-tell, сенсорика, ритм, повторы | P6 | 📝 Pending | Зависит от KB_NARRATIVE_FMDR_EXAMPLES |
| 7 | `SR_MEMORY_CONTINUITY.md` | Emotional anchors, trust, attraction, history gaps | P5 | 📝 Pending | Синтез из MEMORY_BASELINE_TABLE |
| 8 | `SR_ROOT_CAUSE_CLASSIFICATION.md` | Расширенная классификация причин | P1 | 📝 Pending | Создать расширение §10 SR_CANON |
| 9 | `SR_CONFLICT_RESOLUTION.md` | Процедуры при противоречии источников | P1 | 📝 Pending | Расширение §13 SR_CANON |
| 10 | `SR_FEWSHOT_GOOD_FRAMES.md` | 5-10 эталонных кадров с разбором | P6 | 📝 Pending | Нужен golden dataset |
| 11 | `SR_FEWSHOT_BAD_FRAMES.md` | 5-10 анти-эталонных кадров с разбором | P6 | 📝 Pending | Нужен golden dataset |
| 12 | `SR_CHANGELOG.md` | История версий KB | P1 | 📝 Pending | Вести по аналогии с CHANGELOG |

---

## 4. ВНЕШНИЕ ИСТОЧНИКИ (EXTERNAL KB)

Эти файлы **не входят** в `knowledge_base/session_retrospector/`, но SR использует их как P3–P6:

| Приоритет | Источник | Путь | Статус |
|-----------|----------|------|--------|
| P3 | Persona INDEX | `personas/[name]/INDEX.json` | ✅ Существует для 10 персонажей |
| P3 | Persona modules | `personas/[name]/*/` | ✅ Существует |
| P4 | Speech matrix | `personas/[name]/speech/SPEECH_MATRIX.json` | ✅ Для kira, andrey_senior, andrey_junior, marina, egor, olga, maksim, sergey |
| P5 | VSCNO baseline | `core/VSCNO_BASELINE_TABLE.md` | ✅ Ready |
| P5 | AD matrix | `core/AD_AVAILABILITY_MATRIX.md` | ✅ Ready |
| P5 | Internal state | `core/INTERNAL_STATE_BASELINE.md` | ✅ Ready |
| P5 | Memory baseline | `core/MEMORY_BASELINE_TABLE.md` | ✅ Ready |
| P6 | FMDR examples | `knowledge_base/narrative/KB_NARRATIVE_FMDR_EXAMPLES.md` | ✅ Ready |
| P6 | Sensory guidelines | `docs/SENSORY_PEAK_GUIDELINES.md` | ✅ Ready |
| P2 | Governance | `governance/AUTONOMY_GOVERNOR.md` | ✅ Ready |
| P0 | AGENTS.md | `AGENTS.md` | ✅ Ready |

---

## 5. КАК ДОБАВЛЯТЬ НОВЫЕ KB-ФАЙЛЫ

1. Создать файл в `knowledge_base/session_retrospector/`.
2. Добавить запись в эту таблицу (§3).
3. Указать приоритет по SR_CANON.md §4.
4. Обновить `SR_CHANGELOG.md`.
5. Если файл содержит **breaking change** (новая ось, новый root_cause, изменение приоритета) — бампнуть `MAJOR` версию SR_CANON.md.
6. Если файл содержит **новое правило** без ломки старых — бампнуть `MINOR`.
7. Если только примеры или уточнения — бампнуть `PATCH`.

---

## 6. ЗАВИСИМОСТИ МЕЖДУ KB-ФАЙЛАМИ

```
SR_CANON.md
    ├── SR_KB_INDEX.md (эта карта)
    ├── SR_Q4_SCORECARD.md
    │   └── Зависит от: VSCNO_BASELINE, AD_MATRIX, INTERNAL_STATE_BASELINE
    ├── SR_ESCALATION_RULES.md
    │   └── Зависит от: VSCNO_BASELINE, AD_MATRIX, INTERNAL_STATE_BASELINE
    ├── SR_DIALOGUE_AUDIT.md
    │   └── Зависит от: SPEECH_MATRIX (persona-specific), KB_R4_SPEECH_MATRIX
    ├── SR_LITERARY_AUDIT.md
    │   └── Зависит от: KB_NARRATIVE_FMDR_EXAMPLES, SENSORY_PEAK_GUIDELINES
    ├── SR_MEMORY_CONTINUITY.md
    │   └── Зависит от: MEMORY_BASELINE_TABLE, persona memory modules
    ├── SR_ROOT_CAUSE_CLASSIFICATION.md
    │   └── Зависит от: SR_CANON.md §10
    ├── SR_CONFLICT_RESOLUTION.md
    │   └── Зависит от: SR_CANON.md §13
    ├── SR_FEWSHOT_GOOD_FRAMES.md
    │   └── Зависит от: SR_Q4_SCORECARD.md, KB_NARRATIVE_FMDR_EXAMPLES
    └── SR_FEWSHOT_BAD_FRAMES.md
        └── Зависит от: SR_Q4_SCORECARD.md
```

---

## 7. ИСТОРИЯ ВЕРСИЙ

| Версия | Дата | Изменение | Автор |
|--------|------|-----------|-------|
| 1.0.0 | 2026-06-20 | Инициализация. Карта + структура + таблица файлов. | AI-агент |

---

*SR_KB_INDEX.md | Session Retrospector Knowledge Base Index | VNE v3.2+ | 2026-06-20*
