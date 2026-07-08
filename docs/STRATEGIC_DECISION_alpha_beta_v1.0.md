# VOYAGE STRATEGIC DECISION — α/β Track Alignment v1.1
**Date:** 2026-07-08  
**Status:** ✅ DECIDED — "C сейчас / дверь в D потом"  
**Decided by:** Product Owner + Orchestrator  
**Review date:** 2026-10-01  

---

## 1. The Decision

**α (RenPy Visual Novel)** и **β (LLM Persona Pipeline)** развиваются **раздельно и чисто**, с общим лором, но независимыми runtime. Конвергенция запланирована через **Character Aside** (персистентный LLM-чат внутри игры) на **N6**.

| Track | Status | Runtime | Canonical source |
|-------|--------|---------|------------------|
| **α** | Active development | RenPy `.rpa` | `novel/` — hardcoded `.rpy` scenes |
| **β** | Active development | LLM chat (Kimi/DeepSeek/local) | `personas/<name>/` — модульные файлы |

**Монофайл** (`*_MODULE_v*.json`) = **build artifact**, собирается из модульных `personas/<name>/`. Источник правды — модульная структура.

---

## 2. Product Identity: "C сейчас / дверь в D потом"

### 2.1 Сейчас (Q3 2026): Dual-product (C)

- [x] **C. Dual-product** — α и β — отдельные продукты с общей вселенной. Каждый имеет свой release cycle, пользователя и runtime.
- RenPy = игра с визуальной новеллой, спрайтами, музыкой.
- LLM chat = глубокие психологические персонажи, сценарии, модульная архитектура.
- Ни один трек не является "legacy" или "demo" для другого.

### 2.2 Будущее (N6+): Конвергенция через Character Aside (D-door)

- **Character Aside** (Трек A из `NARRATIVE_FUTURE_TRACKS_v1.md`) — пауза сцены → приватный чат с персонажем через LLM API (локальный предпочтителен для взрослого контента).
- Персонаж помнит канон до текущего момента **и** прошлые заходы в "параллельный мир".
- Aside **не пишет** во `flags/relationships/scenario` (изоляция).
- Персонаж **не знает будущего** (защита от памяти при откате save).
- Транскрипты хранятся отдельно, суммаризируются.
- Это **флагманская фича конвергенции** — α получает β-контент без слияния runtime.

---

## 3. Source of Truth

| Артефакт | Источник правды | Примечание |
|----------|----------------|------------|
| Персонаж (психология) | `personas/<name>/` — модульные файлы | R1–R8 pipeline, 16+ подпапок |
| Персонаж (runtime) | `*_MODULE_v*.json` — монофайл | Собирается из модульных; build artifact |
| Сценарий (игра) | `novel/` — `.rpy` скрипты | Hardcoded, вручную |
| Сценарий (чат) | `scenarios/*.json` | LLM runtime загружает как контекст |
| Лор/канон | `shared/lore/` или `docs/` | Общий для α и β |
| Character Aside | `personas/<name>/` + runtime memory | Берёт психологию из β, но живёт в α |

---

## 4. Repository Structure

**Mono-repo with strict directories** (текущая структура сохраняется):

```
voyage-narrative-engine/
├── novel/              # α — RenPy visual novel
├── personas/           # β — модульные персонажи (источник правды)
├── roles/              # β — промпты R1–R8
├── scenarios/          # β — LLM-чат сценарии
├── scripts/            # shared — утилиты (R8, сборщики, экспортеры)
├── docs/               # shared — канон, решения, гайды
└── shared/lore/        # shared — лор-байбл (при создании)
```

---

## 5. Technical Debt — Status Update

| Debt | Было | Стало | Статус |
|------|------|-------|--------|
| Dual persona storage | Модульные + монофайл — не synced | Модульные = источник; монофайл = build | Решено §3 |
| Feature branch divergence | `feature/persona-v2-patches` не в main | Будет merged после зелёного R8 | В процессе |
| R8 Auditor scope | Флаговал sig-vs-asp как дубликаты | R8 v1.0 игнорирует sig-vs-asp by design | Решено — новый скрипт |
| Workspace vs repo | Два источника во время разработки | Workspace = draft; repo = canonical | Принято как процесс |
| Commit discipline | CRLF + add-all риск | Feature branches + поимённый add | Принято как процесс |

---

## 6. Blocked Actions — Now Unblocked

| Action | Было заблокировано | Статус |
|--------|-------------------|--------|
| Merge `feature/persona-v2-patches` → `main` | Неизвестно, β — legacy или нет | ✅ Разблокировано — β признан |
| Reassembly монофайлов | Неизвестен источник правды | ✅ Разблокировано — модульные = source |
| RenPy N6+ планирование | Неизвестен приоритет α vs β | ✅ Разблокировано — α primary, β active |
| R8 Auditor deployment | Scope зависел от α vs β | ✅ Разблокировано — аудит β-контента |
| Character Aside дизайн | Неизвестно, возможна ли конвергенция | ✅ Разблокировано — явная дверь на N6 |

---

## 7. Character Aside — Architectural Notes

**Из `NARRATIVE_FUTURE_TRACKS_v1.md` — Трек A: Persistent Character Aside**

- **Триггер:** Пользователь нажимает "Поговорить с [персонаж]" во время сцены.
- **Изоляция:** Aside НЕ модифицирует `flags`, `relationships`, `scenario` основной игры.
- **Память:** Персонаж помнит канон до текущего момента + прошлые aside-сессии (summary).
- **Безопасность:** При откате save — aside-транскрипты помечаются как "from future", персонаж их не видит.
- **LLM:** Локальный API предпочтителен (Ollama/LM Studio) для взрослого контента без цензуры.
- **Персонаж:** Загружается из `personas/<name>/` (β) → runtime snapshot для aside.

---

## 8. Next Steps

1. **R8-green** → merge `feature/persona-v2-patches` → `main`
2. **RenPy N6 planning** — включить Character Aside как milestone
3. **Q4 2026 review** — оценить: открыть дверь D (конвергенция) или укрепить C (разделение)

---

*Decided by Product Owner + Orchestrator under Voyage Framework v4.0.0*  
*Effective: 2026-07-08 | Review: 2026-10-01*
