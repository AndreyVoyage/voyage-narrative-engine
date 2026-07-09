# NARRATIVE HANDOFF — Kimi Work Operating Pack

> **Назначение.** Пакет для передачи разработки в **Kimi Work**: (A) story-plan оставшихся фаз,
> (B) правила Kimi Work + строгий промпт-шаблон для Kimi Code, (C) audit-checklist для контрольного чата.
> **Роли:** контрольный чат (архитектор/аудитор, владелец правил и roadmap) → **Kimi Work** (оркестратор,
> пишет строгие промпты) → **Kimi Code** (локальный исполнитель в репо).
>
> **Статус:** v1 | **Дата:** 2026-07-08 | **main на момент передачи:** `4932b72` (validate PASS, R8 green).
> **Опора:** `NARRATIVE_DECISIONS_v1.md`, `NARRATIVE_ROADMAP.md`, `N6_CHARACTER_ASIDE_CONTRACT.md`, `NARRATIVE_FUTURE_TRACKS_v1.md`.

---

## A. STORY PLAN — что сделано и что осталось

### Сделано (в `main`)
```
N0 docs/decisions · N1 Schema V2 + validator · N2 Story Runtime · N3 Renderer/exporter (preview) ·
N4 Player Experience MVP · V0 Voyage boundary · N5A–N5J playable bridge + static validation + reachable launcher +
hybrid path + live/dev contract + mock loader + freshness · β persona v2 patches (Olga/Andrey Jr) + R8 green ·
N6 offline foundation (contract + LLMProvider + aside_context_builder + aside_memory_store) + N6e first playable Aside (mock).
```

### Осталось — фазы (порядок = приоритет; каждая = отдельная маленькая задача)

**Трек Aside (конвергенция, продолжение N6):**
- **N6f** — реальный локальный LLM (Ollama) за настройкой вместо mock в Aside; персистентная память подключена к RenPy save/load (отдельный namespace); опция reset. *Зависит от:* N6a–N6e (готово). *Guardrail:* канон по-прежнему не пишется; cloud — опционально, local предпочтителен для взрослого контента.
- **N6g** — polish Aside: выбор персонажа в UI, in-fiction рамка, суммаризация памяти при росте контекста.

**Трек авторских инструментов (из обсуждения PO):**
- **Dev in-place edit (roadmap N5)** — редактирование ТЕКСТА beat'а в игре (`speech/action/thought/narration/emotion`) → write-back в JSON → hot-reload. Только текст; структура (флаги/ветки) — под полной валидацией, позже.
- **Structural edit** — добавление/правка веток/флагов в игре, с flag-lint + branch-continuity. Позже, отдельной фазой.
- **Variations A/B** — авторские варианты beat'ов (детерминированный выбор) + Director-генерация вариантов (LLM ассистирует авторингу, сохраняется в JSON). Переиспользует `llm_provider` + `aside_context_builder`.

**Трек контента:**
- **Content migration** — SC_003–027 → V2 малыми партиями (faithful split, без выдумывания мыслей), генерация `.rpy`, затем промоушен V2-пути из dev/test в player-facing.

**Поздние треки:**
- **Media/Visual layer** — фото (schema `visual_scene_id`/`stills`/`visual_cue` уже есть) + видео + authoring-инструмент.
- **Voice layer** — canon voice assets (offline TTS по `beat_id`) + aside dynamic voice; абстракция `VoiceProvider`; local TTS предпочтителен.
- **Story Setup** — pre-game персонализация маршрутов (отложено; направление задаётся in-scene выборами).

> **Явно НЕ делать:** live-LLM, влияющий на канонические выборы/поведение (ломает детерминизм — только по отдельному осознанному решению PO); SC_028 без задачи; массовую переработку текста SC_020–027 до schema-стабилизации.

---

## B. ПРАВИЛА KIMI WORK + СТРОГИЙ ПРОМПТ-ШАБЛОН для Kimi Code

### Правила Kimi Work (оркестратор)
1. **Одна задача = один маленький scoped-промпт** для Kimi Code. Не смешивать фичи.
2. **Никогда не коммитить в `main` напрямую.** Всегда feature-ветка + push ветки + STOP перед merge.
3. **Merge в `main` — только после аудита контрольным чатом.** Kimi Work merge сам не инициирует без ревью.
4. **stdlib-only** для новых Python-инструментов, если явно не одобрено иное. Без `pip install`.
5. **Канон-инварианты держать всегда:** не менять `scenarios/*`, `personas/*`, `scenes_v2_generated.rpy`, SC_003–018 селектор без явной задачи; Aside/Dev-edit не пишут канон вне разрешённых полей.
6. **Не изобретать роли/механики/архитектуру.** Противоречие → пометить и вернуть в контрольный чат, не «чинить» самому.
7. **Эскалация в контрольный чат** при: merge в main, смене источника правды, архитектурном решении, новом внешнем сервисе/зависимости, любом расхождении с roadmap.
8. **Kimi Code держать в узде:** каждый промпт — строго по шаблону ниже.

### Строгий промпт-шаблон для Kimi Code
```
KIMI CODE TASK — <ID>: <краткая цель> (branch only, no merge)

STRICT: делай ТОЛЬКО перечисленные шаги. Do NOT use sub-agents, do NOT browse,
do NOT infer/start next tasks, do NOT reformat unrelated code, do NOT do extra work.
STOP and return BLOCKED on any mismatch.

Repo: C:/DEV/Narrative/voyage-narrative-engine

1) Preconditions (STOP on mismatch): main==origin/main==<HASH>; tree clean.
2) Branch: git switch -c feature/<name>
3) Спецификация: <ровно какие файлы создать/изменить; что делают>
4) Guardrails: stdlib-only; канон (scenarios/personas/scenes_v2_generated/SC-селектор) не трогать;
   <feature-specific: Aside не пишет v2_*; Dev-edit только текстовые поля; и т.п.>
5) DoD: <py_compile; функциональные проверки; детерминизм; rn_workflow validate --allow-feature-branch PASS;
   grep-guard'ы; счётчики не изменились (script.rpy label_count == 113 и т.п.)>
6) Diff scope guard: git status --porcelain — ровно ожидаемые файлы, без .rpyc/cache/лишнего.
7) Commit + push branch (NO merge, main не трогать):
   git add <поимённо>; git commit -m "<msg>"; git push -u origin feature/<name>
8) Return report: DoD построчно; список изменённых файлов; commit hash; pushed branch;
   main/origin == <HASH> (нетронут). Если STOP — на каком guard'е и что увидел.
```

**Merge-промпт (отдельно, после аудита):** ff-only, scope-guard на ожидаемые файлы, `validate` PASS, `main`==`origin/main`.

**Известный transient:** `rn_workflow validate` без флага падает на feature-ветке по политике «branch is not main» — использовать `validate --allow-feature-branch` до push; после push обычный `validate` PASS.

---

## C. AUDIT-CHECKLIST для контрольного чата (по вехам)

**Когда:** после закрытия каждой фазы / до и после merge в `main` / периодически. Триггер — логическая веха, не таймер.

**Чек-лист (read-only; git — на стороне исполнителя):**
```
[ ] main == origin/main; working tree clean; HEAD зафиксирован (записать hash).
[ ] Дифф фазы vs предыдущего baseline = ровно ожидаемые файлы (нет лишних/junk/.rpyc в трекинге).
[ ] Нет накопления untracked-мусора; временные файлы вне репо.
[ ] Канон непротиворечив: NARRATIVE_DECISIONS/ROADMAP/контракты не задвоены и не конфликтуют.
[ ] Scope не ушёл от roadmap (нет незапланированных фич/файлов/ролей).
[ ] rn_workflow validate PASS; schema-check-v2 / validate-v2 SC_017 PASS.
[ ] Инварианты держатся: script.rpy label_count == 113; scenes_v2_generated не тронут (если не было RN-задачи);
    aside.rpy/Dev-edit не пишут канон вне разрешённого; R8 green по персонам.
[ ] Персона-источник = модульные personas/<name>/ (монофайл = build artifact, не редактируется напрямую).
[ ] Guardrails фичи выполнены (Aside: no canon write-back, past-only, time-travel guard, isolated memory).
```

**Реакция на находки:** дрейф/лишние файлы/противоречие канона → задача на исправление отдельным scoped-промптом; не продолжать новые фичи до устранения.

---

## Быстрый старт для Kimi Work
1. Прочитать: `NARRATIVE_DECISIONS_v1.md`, `NARRATIVE_ROADMAP.md`, `N6_CHARACTER_ASIDE_CONTRACT.md`, этот файл.
2. Взять следующую фазу из §A (рекомендуется **N6f**).
3. Сформировать один строгий Kimi-Code-промпт по шаблону §B.
4. После отчёта — вернуть в контрольный чат на аудит (§C) перед merge.

> Коммит этого документа — через стандартный workflow, отдельным docs-коммитом.
