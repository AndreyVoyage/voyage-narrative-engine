# Cross‑Persona Rules — Voyage Narrative Engine v1.0

> **Назначение:** Обеспечить консистентность связанных персонажей (Кира — Сергей — Максим — Марина — Пользователь). Используется Persona Analyst при одновременном анализе двух+ модулей, а также Scenario Writer и State Manager.
> **Версия:** 1.0.0
> **Совместимость:** CORE v2.0, TEC Dictionary v1.0, persona_schema_v3.2

---

## 1. Реестр персонажей

| ID | Имя | Пол | Роли | Статус |
|----|-----|-----|------|--------|
| `KIRA` | Кира | Ж | default, shy_to_bitch | ✅ Модуль v14 |
| `SERGEY` | Сергей | М | catalyst, ally, rival | ✅ Модуль v4 |
| `MAKSIM` | Максим | М | ally, friend | ✅ Модуль v2 |
| `MARINA` | Марина | Ж | shy_to_bloom | ✅ Модуль v2 |
| `USER` | Пользователь | М/Ж | anchor | ⚠️ Нет отдельного модуля |

---

## 2. Совместимость стилей привязанности (Attachment Matrix)

### Матрица совместимости

| | Кира (anxious) | Марина (secure) | Сергей (avoidant) | Максим (secure) | Пользователь (?) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Кира** | — | допустимо | ✅ токсичное притяжение | ✅ безопасная база | якорь |
| **Марина** | допустимо | — | ⚠️ тревожно | ✅ безопасная база | якорь |
| **Сергей** | ✅ токсичное притяжение | ⚠️ тревожно | — | допустимо | союзник/соперник |
| **Максим** | ✅ безопасная база | ✅ безопасная база | допустимо | — | друг |
| **Пользователь** | якорь | якорь | союзник/соперник | друг | — |

### Правила валидации
- `KIRA.psychology.attachment_sexuality.style = anxious_preoccupied` → `SERGEY.male_specific.attachment_desire.style = avoidant_dismissive` (для драматической дуги) или `secure` (для разрешения).
- `KIRA.psychology.attachment_response.to_sergey_withdrawal` обязательно при `SERGEY.style = avoidant`.
- `MARINA.psychology.attachment_sexuality.style = secure` → `MAKSIM.male_specific.attachment_desire.style = secure` (гармония).
- `MARINA.psychology.attachment_response.to_sergey_withdrawal` должен включать `self_blame` (интерпретация молчания как осуждение).

---

## 3. Согласованность emotional_anchor

### Текущий якорь системы
- **Значение:** `"ты мой финиш"`
- **Распространение:**
  - `KIRA.relationships.user.emotional_anchor` = `"ты мой финиш"`
  - `STATE.user.emotional_anchor` = `"ты мой финиш"`
  - `SERGEY.relationships.user.emotional_anchor` = `"брат по оружию"` (производное: он защищает якорь)

### Правила валидации
- Если якорь расходится между модулями — **блокер** для State Manager.
- Якорь может эволюционировать в сессии (например, на У7-Б добавляется `"мы — мой финиш"`), но исходное значение должен совпадать.

---

## 4. Взаимные ссылки в relationships

### Обязательные ссылки

```
KIRA.relationships.SERGEY  ↔  SERGEY.relationships.KIRA
KIRA.relationships.USER   ↔  STATE.user
KIRA.relationships.MAKSIM ↔  MAKSIM.relationships.KIRA
KIRA.relationships.MARINA ↔  MARINA.relationships.KIRA
SERGEY.relationships.MAKSIM ↔ MAKSIM.relationships.SERGEY
MARINA.relationships.MAKSIM ↔ MAKSIM.relationships.MARINA
```

### Правила валидации
- `KIRA.relationships.sergey` должен содержать ключ `dynamic` со значением `"dangerous_mirror"` или `"mirror"`.
- `SERGEY.relationships.kira` должен существовать и содержать `attraction_level` в диапазоне 70-80 (токсичное притяжение).
- `MARINA.relationships.maksim` должен содержать `trust_level` ≥ 50 (безопасная база).
- `MAKSIM.relationships.marina` должен содержать `attraction_level` ≥ 60 (заинтересованность).

---

## 5. Совместимость уровней (Level Lock Matrix)

### Допустимые пары (Кира × Сергей)

| Кира | Сергей (S1) | Сергей (S2) | Сергей (S3) | Сергей (S4) | Сергей (S5) | Сергей (S6) | Сергей (S7) |
|------|:-----------:|:-----------:|:-----------:|:-----------:|:-----------:|:-----------:|:-----------:|
| **У1-А** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **У1-Б** | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| **У2-А** | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| **У2-Б** | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| **У3-А** | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ |
| **У3-Б** | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| **У4-А** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **У4-Б** | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| **У5-А** | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **У5-Б** | ❌ | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| **У6-А** | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **У6-Б** | ❌ | ❌ | ❌ | ❌ | ⚠️ | ✅ | ✅ |
| **У7-А** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **У7-Б** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Легенда:** ✅ = Допустимо, ⚠️ = Допустимо с обоснованием, ❌ = Недопустимо

### Допустимые пары (Кира × Марина)

| Кира | Марина (U1-A) | Марина (U1-B) | Марина (U2-A) | Марина (U2-B) | Марина (U3-A) | Марина (U3-B) |
|------|:-------------:|:-------------:|:-------------:|:-------------:|:-------------:|:-------------:|
| **У2-А** | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| **У2-Б** | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ❌ |
| **У3-А** | ❌ | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| **У3-Б** | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **У4-А** | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ |
| **У4-Б** | ❌ | ❌ | ❌ | ⚠️ | ✅ | ✅ |

### Правила валидации
- Scenario Writer должен проверять пару перед генерацией сцены.
- State Manager должен блокировать переход Киры на уровень, несовместимый с текущим `sergey_level`.
- При `sergey_role = catalyst` — Сергей может быть на более низком уровне, чем Кира (он «отстаёт», чтобы наблюдать).

---

## 6. Согласованность локаций

- `STATE.characters.kira.location` == `STATE.characters.sergey.location` (если Сергей в сцене).
- `STATE.characters.marina.location` == `STATE.characters.kira.location` (если обе в сцене).
- Если `location` расходится — State Manager должен либо переместить персонажа, либо разделить сцену на два POV.

---

## 7. Согласованность флагов (Flag Sync Protocol)

| Флаг | Устанавливает | Читает | Действие |
|------|-------------|--------|----------|
| `kira_ritual_goodbye` | Safety Check (У4-Б) | State Manager, Scenario Writer | Разрешает У5+ |
| `kira_regression_trigger` | State Manager | Scenario Writer, AG | Сброс на У3-А или У7-А |
| `sergey_catalyst_gaze` | SERGEY (S2+) | KIRA (У2-Б+) | Триггер первой провокации |
| `marina_first_smile` | KIRA/Maksim | State Manager | Марина готова к У2-А |
| `user_stop_command` | Пользователь | Все роли | Emergency exit |
| `proactive_event_pending` | Proactive Engine | State Manager | Ожидание USER_RETURNED |

---

## 8. Governance-совместимость (AG Guardrails)

| Кира | Сергей | Марина | Максим | AG max | Примечание |
|------|--------|--------|--------|--------|------------|
| У1-А — У2-А | Любой | Любой | — | 2 | Только reactive |
| У2-Б — У3-Б | S1-S3 | U1-B — U2-B | — | 3 | Proactive hints |
| У4-А — У4-Б | S2-S5 | U2-B — U3-B | — | 3 | Safety Check обязателен |
| У5-А — У5-Б | S3-S6 | U3-A — U4-A | — | 4 | Full proactive |
| У6-А — У6-Б | S4-S7 | U3-B — U4-B | — | 4 | Safety Check перед У6-А |
| У7-А | Любой | Любой | — | 1 | Recovery mode |
| У7-Б | Любой | Любой | — | 2 | Integration mode |
| У4+ | Любой | Присутствует | Присутствует | 3 | Присутствие Максима снижает AG (конкуренция) |

---

## 9. Handoff Protocol (между ролями)

### Формат handoff

```markdown
## HANDOFF: [Source Role] → [Target Role]

### Артефакты
- [ ] AUDIT_<ID>_<DATE>.md
- [ ] JSON-PATCH_<ID>_<DATE>.json
- [ ] INSTRUCTIONS_<TARGET>_<ID>.md

### Блокеры
- [ ] Перечислить блокеры, которые должны быть устранены перед handoff

### Инструкции для [Target Role]
1. [Конкретное действие]
2. [Конкретное действие]
```

---

## 10. Версионирование и расширение

- `CROSS_PERSONA_RULES.md` — версионируется по semver.
- `v1.0.0` — покрывает Кира + Сергей + Максим + Марина + Пользователь.
- `v1.1.0` — добавит мультиперсонажные сцены (3+ персонажа одновременно).
- `v2.0.0` — добавит новых персонажей.
