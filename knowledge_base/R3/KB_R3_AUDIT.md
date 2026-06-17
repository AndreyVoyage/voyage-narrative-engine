# KB_R3_AUDIT.md
# Knowledge Base: Аудит R3 (Sexologist)
# Назначение: проверка SEXOLOGY_[NAME]_v1.md перед передачей R4
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## СЕКЦИИ АУДИТА R3

### A. КОНСИСТЕНТНОСТЬ С R2 — КРИТИЧЕСКИЙ

```
□ TEC_005.primary = стиль привязанности из R2 (anxious/avoidant/secure/disorganized/ambivalent).
□ Shadow Desires связаны с травмой из R2 (не выдуманы).
□ Aftercare-need логичен: anxious → высокий (7–9), avoidant → низкий (1–3), secure → средний (5–6).
□ SPON/RESP/MIX соответствует психологии: anxious → RESP, avoidant → SPON/MIX, secure → MIX.
```

### B. ПОЛНОТА TEC

```
□ 8 TEC JSON присутствуют (TEC_001–TEC_008).
□ TEC_M_001–003 присутствуют, если gender=male (или по запросу).
□ Каждый TEC имеет поля: primary, triggers[], contexts[], notes.
□ validation_required = true для всех TEC.
```

### C. SHADOW DESIRES

```
□ Shadow Desires не противоречат публичной роли персонажа.
□ Shadow Desires связаны с травмой/когнитивными искажениями из R2.
□ Нет новых травм, которых не было в R2.
□ Shadow Desires влияют на VSCNO (подавленное желание = СТ↑ или ОГ↑).
```

### D. AFTERCARE

```
□ Aftercare-need ∈ [0,10] для каждого подуровня.
□ На У7-А aftercare-need высокий (8–9) — интеграция/aftercare как суть.
□ На У5-А aftercare-need низкий (2–4) — пик страсти, не aftercare.
□ На У3-Б aftercare-need высокий (8–9) — регрессия, grounding нужен.
□ Aftercare-need не противоречит стилю привязанности (anxious → высокий, avoidant → низкий).
```

### E. БЕЗОПАСНОСТЬ

```
□ Нет графического описания насилия (hard limit).
□ Нет несовершеннолетних (hard limit).
□ Не-консенсуальность помечена как [CONSENT_VIOLATION] или отсутствует (hard limit).
□ Soft limits (публичное унижение) помечены и имеют aftercare-plan.
```

### F. ФОРМАТ

```
□ SEXOLOGY_[NAME]_v1.md — Markdown, не JSON.
□ 8 TEC JSON встроены в Markdown.
□ Shadow Desires — текстовые описания, не JSON.
□ Aftercare-need — таблица 14 подуровней.
□ Confidence Matrix — 5 элементов (режим A) или 15×5 (режим B/C).
```

---

## ИТОГОВЫЙ РЕЗУЛЬТАТ

```
AUDIT REPORT: SEXOLOGY_[NAME]_v1
Date: [YYYY-MM-DD]

CRITICAL (A): [ ] PASS / [ ] FAIL
HIGH (B+C): [ ] PASS / [ ] FAIL
MEDIUM (D+E): [ ] PASS / [ ] FAIL
FORMAT (F): [ ] PASS / [ ] FAIL

Статус: [ ] ГОТОВ К ПЕРЕДАЧЕ R4 / [ ] ТРЕБУЕТ ИСПРАВЛЕНИЙ
```

---

*KB_R3_AUDIT.md | Voyage Narrative Engine | 2026-06-16*
