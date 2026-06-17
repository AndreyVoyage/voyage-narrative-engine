# KB_R6_AUDIT.md
# Knowledge Base: Роль 6 — Audit Checklist
# Назначение: Валидация структуры Persona Module (R6 Assembly)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. СТРУКТУРА АУДИТА (5 секций)

### СЕКЦИЯ 1: Корневая структура

**Проверки:**
- [ ] INDEX.json существует и валиден (JSON).
- [ ] INDEX.json содержит: module_name, version, created, roles (R1–R6), sublevels (14 штук).
- [ ] ASSEMBLY.md существует и описывает workflow.
- [ ] HANDOFF_R6.md существует (может быть пустым до R7).
- [ ] HUMAN/ и AUTONOMOUS/ и META/ существуют.

**Критичные ошибки:**
- Пропущен INDEX.json.
- INDEX.json не содержит sublevels или roles.
- Неверный JSON (syntax error).

---

### СЕКЦИЯ 2: HUMAN контейнер (9 папок)

**Проверки:**
- [ ] core/ содержит: PORTRAIT.md, VSCNO.md, IDENTITY.json, COMPACT.md.
- [ ] levels/ содержит 14 папок: U1-A … U7-B.
- [ ] Каждая папка U-X содержит: PREVIOUS.md, CURRENT.md, FUTURE.md.
- [ ] psychology/ содержит: TRAUMA.md, SPEECH_PATTERNS.md, COMPACT.md.
- [ ] sexology/ содержит: TEC.md, SCENARIOS.md, COMPACT.md.
- [ ] visual/ содержит: ANCHOR.json, SIGNATURE.md, DYNAMIC.md, COMPACT.md.
- [ ] dynamics/ содержит: MOVEMENT.md, AGGRESSION.md, COMPACT.md.
- [ ] memory/ содержит: ANCHORS.md, TRIGGERS.md, ASSOCIATIONS.md.
- [ ] relationships/ содержит: INDEX.json, минимум 1 [Name].json.
- [ ] environment/ содержит: LOCATIONS.md, FLORA_FAUNA.md, COMPACT.md.
- [ ] safety/ содержит: VRI_MONITOR.md, SAFE_CODES.md, ESCALATION.md.

**Критичные ошибки:**
- Пропущена папка (например, safety/).
- Пропущен файл в папке (например, COMPACT.md).
- Папка levels/ не содержит 14 подпапок.
- relationships/ пуст (нет ни одного отношения).

---

### СЕКЦИЯ 3: PREVIOUS / CURRENT / FUTURE (14 папок)

**Проверки:**
- [ ] PREVIOUS.md содержит 1 ФМДР + визуал предыдущего подуровня.
- [ ] CURRENT.md содержит 2 ФМДР + визуал текущего подуровня.
- [ ] FUTURE.md содержит 3 ФМДР + визуал следующего подуровня.
- [ ] ФМДР валидны: мысль (1–2 предложения), действие (физика), речь (диалог или молчание).
- [ ] Визуал ссылается на существующий подуровень (например, U3-A PREVIOUS → U2-A).
- [ ] Нет фантазий: только данные из R1–R5.

**Критичные ошибки:**
- ФМДР без речи (или без мысли).
- Визуал ссылается на несуществующий подуровень.
- Содержит данные, не подтверждённые R1–R5.

---

### СЕКЦИЯ 4: RELATIONSHIPS (Отношения)

**Проверки:**
- [ ] INDEX.json содержит список отношений (массив строк).
- [ ] Каждый [Name].json валиден (JSON).
- [ ] Каждый JSON содержит: with, scene, tone, history, current_status, power_dynamic, triggers, vscno_influence, tec_codes.
- [ ] scene — snake_case, одно слово.
- [ ] tone — 2–3 токена, snake_case.
- [ ] current_status — один из 14 подуровней.
- [ ] vscno_influence — сумма Δ = 0 (не меняет общую сумму ВСЦНО).
- [ ] tec_codes — массив из 1–3 кодов, каждый ∈ {ФС, ЛС, СП, СЛ, КН, ПД, ДР, ПУ, ПР, ВС}.

**Критичные ошибки:**
- Пропущено поле with или current_status.
- vscno_influence меняет сумму ВСЦНО (например, ВЛ: +2, СТ: +2 → сумма ≠ 10).
- Неканонический TEC-код (например, «АБ» вместо «ФС»).

---

### СЕКЦИЯ 5: Cross-role консистентность

**Проверки:**
- [ ] Данные R1 (портрет) совпадают в core/PORTRAIT.md и visual/ANCHOR.json (face, eyes, hair).
- [ ] ВСЦНО в core/VSCNO.md совпадает с psychology/TRAUMA.md (высокая СТ → тревожность).
- [ ] TEC в sexology/TEC.md совпадает с relationships/ (если relationship с тоном «passionate» → TEC содержит СП или СЛ).
- [ ] Signature items в visual/ANCHOR.json совпадают с dynamics/MOVEMENT.md (например, «adjusts sleeves» → movement type «hand gesture»).
- [ ] Safety/SAFE_CODES.md не противоречит VSCNO (например, сейф-код «жёлтый» = ПД, но если ВСЦНО на У7-Б → ПД неактивен).

**Критичные ошибки:**
- Противоречие между R1 и R5 (цвет глаз разный).
- Противоречие между R2 и R3 (высокая СТ, но TEC показывает амбивалентность вместо конфликта).
- Противоречие между R3 и relationships (passionate tone, но TEC нет СП/СЛ).

---

## 2. ФОРМАТ ОТЧЁТА АУДИТА

```
AUDIT_R6_[PersonaName]_[Version]_[Timestamp]

=== Root Structure ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== HUMAN Container ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== PREVIOUS/CURRENT/FUTURE ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Relationships ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Cross-role Consistency ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== ИТОГ ===
Critical: 0 / Warning: 1 / PASS
```

---

## 3. ПРИМЕР АУДИТА (Андрей Старший v1.2)

```
AUDIT_R6_AndreySenior_v1.2_2026-06-16

=== Root Structure ===
Status: PASS
INDEX.json valid. ASSEMBLY.md present. HANDOFF_R6.md present.

=== HUMAN Container ===
Status: PASS
All 9 folders present. All 14 sublevels present. COMPACT.md in each.

=== PREVIOUS/CURRENT/FUTURE ===
Status: PASS
All 14×3 files present. FMDR valid (thought/action/speech). Visuals canonical.

=== Relationships ===
Status: PASS
3 relationships: Elena (U3-B), Igor (U1-A), Masha (U7-A).
All JSON valid. VSCNO influence sums to 0. TEC codes canonical.

=== Cross-role Consistency ===
Status: PASS
R1 face matches R5 anchor. R2 VSCNO matches R3 TEC (U3-A: high ST → TEC = conflict).
R5 signature items match R6 dynamics. Safety codes match VSCNO levels.

=== ИТОГ ===
Critical: 0 | Warning: 0 | PASS
```

---

*KB_R6_AUDIT.md | Voyage Narrative Engine | 2026-06-16*
