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
**Date:** 2026-07-08  
**Status:** DRAFT — awaiting decision by Product Owner  
**Context:** Two parallel development tracks in voyage-narrative-engine repository  

---

## 1. The Question

VNE repository currently contains **two decoupled tracks** that share no runtime dependency but compete for attention, architecture decisions, and canonical truth:

| Track | Name | What it is | Current state | Primary output |
|-------|------|-----------|---------------|----------------|
| **α** | RenPy Visual Novel | Python/RenPy game engine with branching narrative, sprites, backgrounds, music | N5 complete, N6+ in planning | `novel/` — playable `.rpa` builds |
| **β** | LLM Persona Pipeline | Modular psychological persona specs + chat scenarios for LLM runtime (Kimi/DeepSeek) | 10 personas modular, roles R1-R8, scenarios library | `personas/`, `roles/`, `scenarios/` — monofiles for chat |

**Core conflict:** `personas/` modules (β) are **not consumed** by RenPy (α). RenPy scenes are hardcoded in `.rpy` scripts with manual dialogue. The two tracks are technically independent but live in the same repo, creating confusion about "what is the product."

---

## 2. Decision Required

### 2.1 Product Identity (choose one)

- [ ] **A. α-primary (RenPy game)** — β is legacy support / content source that feeds into α via future VNE→RenPy exporter. Personas in `personas/` become source material for RenPy characters. LLM chat is prototyping tool, not final product.
- [ ] **B. β-primary (LLM chat platform)** — α is experimental side-track. Final product is LLM-driven interactive chat with deep personas. RenPy is a "demo" or "preview" format.
- [ ] **C. Dual-product (both independent)** — α and β are separate products sharing lore/universe but not runtime. Each has its own canonical source, release cycle, and user.
- [ ] **D. α→β convergence (single engine)** — Future: RenPy becomes the visual layer, LLM becomes the narrative generation backend. One product with two faces. (Long-term, speculative.)

### 2.2 Source of Truth for Personas (depends on 2.1)

If **A or D** (RenPy primary or converged):
- Persona canonical source = **modular `personas/<name>/` files** → exported to RenPy character definitions + sprite metadata
- Monofile (`KIRA_MODULE_v15.json`) = **build artifact**, not source
- Workspace drafts → modular files → RenPy `.rpy` characters

If **B** (LLM primary):
- Persona canonical source = **monofile JSON** (what loads into chat)
- Modular `personas/<name>/` = development structure, but monofile = truth
- Risk: drift between modular parts and monofile (already happening)

If **C** (dual):
- Each track has **its own persona representation**
- No automatic sync required; manual lore bible keeps consistency
- Overhead: maintaining two persona formats

### 2.3 Repository Structure (depends on 2.1+2.2)

| Option | Structure | Impact |
|--------|-----------|--------|
| Mono-repo (current) | Both in `voyage-narrative-engine/` | Shared git history, but confusion about what to commit where |
| Split repo | `voyage-narrative-engine` (β) + `voyage-renpy-novel` (α) | Clean separation, but lore sync becomes manual |
| Mono-repo with strict dirs | `novel/` for α, `personas/` for β, `shared/lore/` for common | Discipline required; clear boundaries |

---

## 3. Current Technical Debt from Not Deciding

| Debt | Symptom | Risk |
|------|---------|------|
| Dual persona storage | Modular `personas/olga/` + monofile `OLGA_MODULE_v3.json` — not synced | User edits one, runtime uses other → silent bugs |
| Feature branch divergence | `feature/persona-v2-patches` has content not in `main` | β advances without α awareness |
| R8 Auditor scope | R8 built for β uniqueness, not applicable to α | False blockers, wasted review time |
| Workspace vs repo | Workspace drafts (8 files) copied to repo only after approval | Two sources of truth during development |
| Commit discipline | CRLF noise + "add all" risk | Accidental commits of unrelated changes |

---

## 4. Immediate Actions Blocked by This Decision

| Action | Blocked because... |
|--------|-------------------|
| Merge `feature/persona-v2-patches` → `main` | Without product identity, merge is premature accumulation |
| Reassembly of monofiles | Source of truth unknown: modular files or monofile? |
| RenPy N6+ development | If α is primary, prioritize; if β is primary, α is secondary |
| R8 Auditor deployment | Scope depends on whether we audit for chat (β) or game (α) |
| Resource allocation | Which track gets deep focus vs maintenance mode? |

---

## 5. Recommendation (by Orchestrator, non-binding)

**Option A (α-primary) with Option C fallback for 6 months.**

Rationale:
- RenPy produces a **shippable artifact** (game build). LLM chat is a research/iteration tool.
- Market for indie visual novels is proven; market for LLM persona chat is undefined.
- α has clear milestones (N6, N7, N8...); β is open-ended.
- Persona depth developed in β **can** feed RenPy characters via exporter (future).

**Transition plan:**
1. Declare α primary for Q3 2026.
2. β enters "maintenance + selective export" mode: new personas created only if needed for RenPy cast.
3. Modular `personas/` = canonical for psychology; monofile = deprecated (build artifact).
4. Build lightweight VNE→RenPy exporter (character definitions + sprite metadata) as shared tool.
5. Revisit decision in Q4 2026 based on RenPy reception + LLM platform readiness.

---

## 6. How to Decide

Reply with:
- **Choice (A/B/C/D)** for 2.1
- **Preferred source of truth** for 2.2
- **Any modifications** to recommendation in §5
- **Timeline** for decision review (suggested: 2026-10-01)

Once decided, this document becomes `docs/STRATEGIC_DECISION_alpha_beta_v1.0.md` and gates all subsequent architectural choices.

---

*Draft by Orchestrator under Voyage Framework v4.0.0*  
*Blocked by: Product Owner decision required*
