# KB_R5_AUDIT.md
# Knowledge Base: Роль 5 — Audit Checklist
# Назначение: Валидация выходных данных R5 (Anatomic Anchor, Visual Signature, Dynamic Visuals)
# Версия: 1.0 | Voyage Narrative Engine | 2026-06-16

---

## 1. СТРУКТУРА АУДИТА (5 секций)

### СЕКЦИЯ 1: Anatomic Anchor (L1)

**Проверки:**
- [ ] Содержит 10+ блоков (face_shape, forehead, chin, overall, eyes, nose, lips, skin, hair, body, signature_items).
- [ ] Каждый блок — JSON-объект с полями, не просто текст.
- [ ] Eyes содержит: color, shape, gaze, signature, pupil_dynamics.
- [ ] Signature items уникальны (не дублируют других персонажей).
- [ ] Height/weight указаны (если human).
- [ ] Нет противоречий: например, «clean-shaven» + «beard».

**Критичные ошибки (фейл):**
- Пропущен блок eyes или body.
- Повторяющиеся signature items с другим персонажем.
- Противоречивые данные (цвет глаз меняется).

**Пример (Андрей):**
```json
{
  "face_shape": {"shape": "oval", "jaw": "strong square", "character": "warm protector"},
  "eyes": {"color": "bright blue", "shape": "almond", "gaze": "warm observant", "signature": "medium upper lid", "pupil_dynamics": "dilate on stress"}
}
```

---

### СЕКЦИЯ 2: Visual Signature (L2)

**Проверки:**
- [ ] Одна строка, 100–200 слов.
- [ ] Без эмоциональных оценок («красивый», «привлекательный» заменены на «handsome», «athletic»).
- [ ] Без контекста («в баре», «на пляже»).
- [ ] Без динамики («улыбается», «смотрит»).
- [ ] Порядок: волосы → глаза → лицо → кожа → тело → особенности → одежда.
- [ ] Включает height/weight (если human).

**Критичные ошибки:**
- Эмоциональные оценки в строке.
- Динамические глаголы (smiling, looking).
- Контекстные прилагательные (bar, beach).

**Пример PASS:**
```
handsome athletic man 38yo, 180cm/85kg, light ash-blond short dense hair...
```

**Пример FAIL:**
```
beautiful man sitting at the bar, smiling warmly, wearing a blue shirt...
```

---

### СЕКЦИЯ 3: Dynamic Visuals (14×7)

**Проверки:**
- [ ] Ровно 14 строк (U1-A … U7-B).
- [ ] Каждая строка — JSON с 7 параметрами.
- [ ] Blush ∈ [0, 4].
- [ ] Sweat ∈ [0, 4].
- [ ] Pupils — одно из: normal, slightly_dilated, dilated, max_dilated, constricted, pinpoint.
- [ ] Lighting — одно из 7 значений Lighting Map.
- [ ] Clothing/posture/micro_expression — snake_case, 3–5 токенов.

**Критичные ошибки:**
- Пропущен подуровень.
- Blush/sweat > 4 или < 0.
- Неканонический lighting (не из Lighting Map).
- Повторяющиеся posture между подуровнями (должны быть разными).

---

### СЕКЦИЯ 4: Связь с предыдущими ролями

**Проверки:**
- [ ] Pupil dynamics соответствуют ВСЦНО (СТ↑ → dilated, ОГ↑ → constricted).
- [ ] Blush/sweat логичны для уровня (У4-А → blush 3, sweat 1; У6-А → blush 4, sweat 3).
- [ ] Lighting соответствует эмоциональному тону (У4-А → dramatic, У7-Б → soft).
- [ ] Signature items не противоречат TEC (R3) — например, «expensive watch» = СП, не ПД.

---

### СЕКЦИЯ 5: Консистентность между персонажами

**Проверки:**
- [ ] Нет дублирования signature items (если у Андрея «expensive watch», у Егора — «tapping fingers»).
- [ ] Разные visual signatures (Андрей — warm, Egor — predatory).
- [ ] Разные lighting preferences (Андрей — warm amber, Egor — cold blue).

---

## 2. ФОРМАТ ОТЧЁТА АУДИТА

```
AUDIT_R5_[PersonaName]_[Version]_[Timestamp]

=== Anatomic Anchor ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Visual Signature ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Dynamic Visuals ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Cross-role Consistency ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== Inter-persona Uniqueness ===
Status: PASS / FAIL / WARNING
Issues: [список]

=== ИТОГ ===
Critical: 0 / Warning: 1 / PASS
```

---

## 3. ПРИМЕР АУДИТА (Андрей Старший v1.2)

```
AUDIT_R5_AndreySenior_v1.2_2026-06-16

=== Anatomic Anchor ===
Status: PASS
All 10 blocks present. Eyes include pupil_dynamics. Signature items unique.

=== Visual Signature ===
Status: PASS
112 words, no emotions, no context, no dynamics. Order correct.

=== Dynamic Visuals ===
Status: PASS
14 rows, 7 params each. Blush/sweat ∈ [0,4]. Lighting canonical.

=== Cross-role Consistency ===
Status: PASS
Pupil dynamics match VSCNO (U4-A: dilated, U6-B: constricted).
Blush/sweat match emotional intensity (U4-A: 3/1, U6-A: 4/3).

=== Inter-persona Uniqueness ===
Status: PASS
No overlap with Egor (watch vs tapping fingers, warm vs cold).

=== ИТОГ ===
Critical: 0 | Warning: 0 | PASS
```

---

*KB_R5_AUDIT.md | Voyage Narrative Engine | 2026-06-16*
