# N6B — ASIDE v2 — PARALLEL MEMORY & TRANSITION — PREFLIGHT (v1)

> **Статус:** PROPOSED / DOCUMENTATION PREFLIGHT — **IMPLEMENTATION NOT AUTHORIZED.**
> Фиксирует авторские решения (DECIDED) по слою «параллельная память + переход» поверх работающего
> N6 Character Aside, **сверенные с фактическим кодом** (пометки EXISTING / PARTIAL / PROPOSED).
> Кода не пишет, ветку не размораживает.
> **Дата:** 2026-07-31
> **База кода аудита:** main `653f52f`. Cloud-провайдер + scene_context-мост — на **незамёрженной**
> ветке `vne-rn-aside-runtime-context` @ `9b00ede`; **модель памяти в обеих идентична**.
> **Инвариант:** non-canon by default — Aside видит канон, не пишет его; **никогда** не пишет `v2_*`;
> past-only контекст.
> **Опора:** `N6_CHARACTER_ASIDE_CONTRACT.md` (CLOSED, не переписывать), `N7_CANONICAL_STATUS_CLOSEOUT_v1.md`,
> `core/AD_AVAILABILITY_MATRIX.md`, `SCENARIO_SCHEMA_V2_SPEC.md`, `tools/aside_memory_store.py`,
> `tools/aside_context_builder.py`, `novel/game/aside.rpy`.

> **Implementation status update — 2026-08-01:** Slice 1
> (`MEMORY IDENTITY & SAFETY FOUNDATION`) был отдельно авторизован владельцем,
> реализован в code commit
> `86bb5f7bf2351cfb43272d2d09f8fab9e1e30b17`,
> интегрирован в `origin/main` через docs-chain commit
> `0895b37d161e82f0a1664c8d70902e599cf13316`
> (fast-forward, без merge commit, без force push).
> Targeted tests 33/33 PASS; full suite 246/246 PASS.
> Corrected live verdict A1: persistence, identity/world isolation, provenance,
> Reset и scoped Wipe подтверждены; semantic recall реальной LLM не подтверждён
> (mock provider, non-blocking limitation).
> Slice 2 и все последующие этапы НЕ авторизованы.
> Runtime branch `9b00ede` остаётся отдельным integration gate.
> Общий статус `DOCUMENTATION PREFLIGHT / IMPLEMENTATION NOT AUTHORIZED`
> продолжает относиться к неавторизованным последующим slices и не отменяет
> отдельную авторизацию Slice 1.
> Исторический preflight и план Stage 0–8 сохраняются без изменений.
> D-ASD решения не переоткрываются.

---

## 0. Контекст

MVP scene-context закрыт и заморожен (`9b00ede`): Кира получает сцену/beat/локацию/присутствующих и
past-only события; блок входит в облачный запрос. Это **первая половина** модели «двух параллелей».
Этот документ проектирует **вторую половину** — собственную персистентную память Киры, отдельные
отношения с игроком, эмоциональную инерцию перехода, защиту от спойлеров при откате — и **честно
разделяет**, что уже в коде, что частично, что только задумано.

---

## 1. Модель двух планов памяти (асимметрична — не смешивать)

| План | Направление | Политика |
|---|---|---|
| **CANON_WORLD** | канон → Aside, read-only, past-only | Aside читает, не пишет |
| **ASIDE_WORLD** | Aside → Aside, контролируемая запись | развивается только внутри Aside |
| **USER_CLAIM** | слова игрока | хранятся как заявление, **не** факт канона |

Канон первичен; Aside — неканонная боковая ветка, видит канон, но не пишет. Разговор с игроком **не**
меняет канонические отношения (Кира↔Яков).

---

## 2. Ратифицированный пакет (OWNER-DECIDED)

```
D-ASD-01  Профили: у каждого профиля игрока — отдельная память.                          DECIDED
D-ASD-02  Персонажи: свои отношения/роль/воспоминания; не знают о встречах с другими.     DECIDED
D-ASD-03  Роли: можно задать per-character или одну на всех; роль = заявление, не приказ. DECIDED
D-ASD-04  Смена роли: явная, персонаж помнит прежнюю и реагирует; есть режим «исправление
          профиля задним числом» (без разыгрывания как события).                          DECIDED
D-ASD-05  Образ пользователя: общий базовый профиль + per-character настройки; игрок сам
          решает, что раскрыть сразу, что постепенно.                                     DECIDED
D-ASD-06  Самостоятельность: персонаж по своей психологии может сомневаться, проверять,
          отказываться, принимать/отвергать роль (вариант C).                             DECIDED
D-ASD-07  Два мира: в сценарии не помнит Aside; при вызове помнит оба.                     DECIDED
D-ASD-08  Переход: авто; сначала инерция состояния сцены, затем осознание + восстановление
          памяти/отношений Aside.                                                          DECIDED
D-ASD-09  Состояние перехода: эмоции/уровни из сценария и runtime, НЕ угадываются моделью;
          учитываются интенсивность, последнее действие, незавершённое намерение.          DECIDED
D-ASD-10  Психология перехода: скорость осознания зависит от персонажа (Кира при страсти/
          страхе/агрессии дольше по инерции).                                             DECIDED
D-ASD-11  Кнопка реакции: поле ввода доступно сразу; отдельная кнопка запускает реакцию
          персонажа на перенос без сообщения игрока.                                       DECIDED
D-ASD-12  Отношения с игроком: развиваются независимо от канона (доверие/близость/
          настороженность/привязанность/конфликты/нерешённые темы).                        DECIDED
D-ASD-13  Prompt: не весь архив — недавний разговор + значимые воспоминания + сводка
          отношений + незавершённые темы + состояние входа.                                DECIDED
D-ASD-14  Архив: полная история хранится скрыто (восстановление/аудит/ре-суммаризация).    DECIDED
D-ASD-15  Слова игрока хранятся как USER_CLAIM, не канон.                                   DECIDED
D-ASD-16  Откат: память встреч/отношений сохраняется, будущие канон-события не раскрываются.DECIDED
D-ASD-17  Reset Aside: только текущее окно; полное забывание — отдельная команда + подтв.  DECIDED
D-ASD-18  Хранилище v1: SQLite + FTS5 + структурированное ранжирование; embeddings — позже.DECIDED
D-ASD-19  Суммаризация: по мере роста — компактные значимые воспоминания + сводка.          DECIDED
D-ASD-20  Aside и CES: хранилища раздельны; позже — общий низкоуровневый SQLite-механизм,
          без смешения данных.                                                             DECIDED
```

**Гейтинг (ратифицировано):**

```
D-ASD-G  Гейтинг ИНТЕНСИВНОСТИ entry_state через AD-матрицу + уровень отношений.          DECIDED
         Интенсивность и доступность действия в Aside ОБЯЗАНЫ проходить через AD-матрицу +
         уровень отношений — та же ось availability, что и в каноне. D-ASD-06 закрывает
         волю персонажа (не авто-согласие); D-ASD-G — доступность действия по уровню. Обе
         обязательны. Aside не может превышать canon-availability текущего уровня.
```

**Все решения Aside v2 закрыты (D-ASD-01…20 + D-ASD-G). Открытых пунктов нет.**

---

## 3. Аудит существующего кода (EXISTING / PARTIAL / PROPOSED)

### EXISTING — уже работает
- **Изолированная JSON-память.** `config.savedir/vne_aside_memory/private_chats/<slot>/<character>/sessions/*.json` + `memory_summary.json`. Backend — **JSON, не SQLite** (`aside_memory_store.py:26,204-212,253-257`; live-root `aside.rpy:236-238`).
- **Персистентность через перезапуск игры** (файлы на диске в savedir).
- **Инжект прошлых сессий в промпт**: `summary` + `recent(20)` (`aside.rpy:275-286`; `aside_context_builder.py:74-84`; `RECENT_LIMIT=20`, `SUMMARY_LIMIT=4000` — `memory_store.py:27-28`).
- **Time-travel guard на уровне сессии**: `load_memory` фильтрует `progress_index ≤ progress` (`memory_store.py:64-68`).
- **Past-only канон-снимок**: flags/completed_scenes/levels/relationships/content_rating (`aside.rpy:213-231`; ключи `context_builder.py:29-38`).
- **Атомарная запись** (tmp+replace, `memory_store.py:253-257`); запись **только после успешного reply** (`aside.rpy:293-320`).
- **Трейс с редактом** чувствительных полей `{msg, reply_preview, history_last, error}` — metadata-only (`aside.rpy:67`).
- **Авторские эмоц-поля в SCHEMA_V2 JSON** (но НЕ в runtime): beat `emotion` (`SPEC:119`), scene `intensity` 0–10 (`:48`), `emotional_anchors[]` (`:53`), `characters[].state_start/end` (`:78`).

### PARTIAL — есть частично
- **Изоляция памяти**: `character_id` — да (в пути); `slot` — есть параметр, но **захардкожен `"dev_slot"`** (`aside.rpy:576,715,741`) → фактически один бакет на персонажа; `profile_id` — нет.
- **Слои памяти**: `recent(20)` + наивный concat-summary (`memory_store.py:177-191`); значимое/сводка отношений — нет. Session-`summary` = `f"Player: {msg}"` (`runtime.py:100`), не экстракция.
- **Time-travel guard**: спойлер защищает, но **грубо** — исключает сессию целиком → Кира вовсе забывает встречу (конфликт с D-ASD-16).

### PROPOSED — только задумано (кода нет)
SQLite/FTS5 backend · `profile_id` и составной ключ изоляции · provenance-поля `CANON_WORLD/ASIDE_WORLD/USER_CLAIM` · memory-extractor значимого (importance/emotional_weight/event_type/дедуп) · `aside_relationship_state` (trust/closeness/wariness/role_trust/unresolved_topics) · `entry_state_snapshot` с affect · `declared_user_role`/`character_accepted_role`/`role_trust` · `ASIDE_TRANSITION_REACTION` как отдельный turn-тип · «remember-but-redact» guard при откате · Reset только окна + подтверждение полного wipe · суммаризация · embeddings.

---

## 4. Два бага против принятой модели (EXISTING, требуют исправления в v1)

- **Reset = полный wipe без подтверждения.** Кнопка «Reset Aside» вызывает `reset_memory` → `shutil.rmtree(base)` (`aside.rpy:336-341` → `memory_store.py:113-118`), удаляя всю долговременную память + чистя историю (`:344`). Противоречит **D-ASD-17**. В v1: Reset = только текущее окно; полный wipe — отдельная команда + подтверждение.
- **`slot` захардкожен `"dev_slot"`** (`aside.rpy:576,715,741`) → нет реальной изоляции per-save/profile. Противоречит **D-ASD-01**. В v1: составной ключ `profile_id + character_id + world`.

---

## 5. Целевая архитектура памяти (v1)

**Хранилище (D-ASD-18):** SQLite + FTS5, ключ изоляции `profile_id + character_id + world`
(UNIQUE-констрейнт + обязательные фильтры в каждом чтении). Embeddings — поздний слой при
достаточном объёме (согласовано с N7/D-CES/research: сначала лексика/структура).

**Слои (D-ASD-13):**
1. **Краткосрочный хвост** — последние сообщения текущей встречи + небольшой хвост недавних (расширение существующего `recent`).
2. **Значимые воспоминания** (эпизодические) — записи с `memory_id, profile_id, character_id, world, role_of_user, event_type, summary, importance, emotional_weight, created_at, source_scene_id, source_beat_id, timeline_reference`.
3. **Сводка отношений** — компактная `aside_relationship_state` (D-ASD-12), **отдельно** от канонических `v2_relationships`.
4. **Скрытый архив** (D-ASD-14) — сырой транскрипт для аудита/восстановления; в промпт целиком **не** уходит.

**Ранжирование извлечения:** смысловая близость (позже) + важность + эмоц. вес + недавность +
текущая тема + роль пользователя; обязательные фильтры `profile_id`, `character_id`, `world`,
`spoiler_allowed=false`.

**entry_state_snapshot (D-ASD-09, детерминизм).** Источник affect — авторские поля SCHEMA_V2
(`beat.emotion` + `scene.intensity` + `emotional_anchors`) + runtime-уровни, **без LLM-угадывания**.
Минимальный increment: пробросить `emotion`/`intensity` в runtime-переменные через **exporter**
(сейчас снимок их не захватывает). Снимок неизменяем, фиксирует момент перехода; несёт последнее
действие и незавершённое намерение.

**Блоки промпта (D-ASD-15, провенанс):**
```
[CURRENT CANON WORLD]   past-only канон до вызова
[PARALLEL WORLD MEMORY] значимые прошлые встречи (ASIDE)
[PARALLEL RELATIONSHIP]  как персонаж воспринимает игрока сейчас
[USER CLAIMS]            заявления игрока, помеченные как непроверенные
[ENTRY STATE]           состояние персонажа в секунду переноса
```

**Модель роли (вариант C, D-ASD-03/04/06):** `declared_user_role` (заявление) →
`character_accepted_role` (принял/сомневается/отверг) → `role_trust` (сформированное доверие).
Смена роли — явное залогированное событие, кроме режима «исправление задним числом»
(D-ASD-04). Персонаж вправе не принять роль по своей психологии.

---

## 6. Guardrails

1. Non-canon by default; Aside **никогда** не пишет `v2_*`; канон read-only.
2. **Провенанс обязателен** — CANON/ASIDE/USER_CLAIM как поля, три секции в промпте.
3. **Интенсивность гейтится** через AD-матрицу + уровень (D-ASD-G, ратифицировано) — иначе Aside обходит availability.
4. **Инерция ≠ безусловное согласие** (D-ASD-06): переносится состояние, но не авто-воля.
5. **Изоляция** `profile_id + character_id + world`; память одного профиля/персонажа не попадает другому.
6. **Полный wipe — только по явному подтверждению** (D-ASD-17).
7. Секреты провайдера — никогда в стор/логи/архив; только env/.env.
8. Диагностика и архив — без секретов; трейс уже редактит текст сообщений (`aside.rpy:67`).
9. Мягкая четвёртая стена: диегетическое осознание, без разговоров о коде/промптах/движке.

---

## 7. Риски

```
R1  slot захардкожен "dev_slot" → нет изоляции per-save/profile (баг, §4).
R2  rollback guard всё-или-ничего: конфликт «не спойлить» vs «помнить встречу» (D-ASD-16).
    Нужно тегировать canon-позицию воспоминания и «remember-but-redact», а не исключать сессию.
R3  memory-extractor = LLM → стоимость/недетерминизм/дрейф; в v1 держать простым/детерминированным.
R4  Reset = full rmtree без подтверждения (баг, §4).
R5  гейтинг интенсивности ещё не реализован в коде (решение D-ASD-G ратифицировано);
    до реализации Aside не должен нести интенсивность в обход AD-матрицы.
R6  provenance отсутствует → USER_CLAIM и канон-факт неразличимы в данных.
```

---

## 8. Обязательные runtime-тесты (перед реализацией — все PROPOSED)

close/reopen recall · restart-game recall · load-old-save recall (встреча помнится, будущее скрыто —
R2) · profile isolation · character isolation · provenance isolation · spoiler/time-travel guard ·
**Reset НЕ трёт долговременную память** (сейчас упадёт) · роль пользователя остаётся USER_CLAIM, не
каноном.

---

## 9. Взаимодействие с CES (D-ASD-20)

Aside v2 memory и Character Evolution Sandbox — оба неканонные персистентные хранилища памяти
персонажа. Общий низкоуровневый store-примитив (connection/WAL) допустим позже, но **таблицы/схемы
держать РАЗДЕЛЬНЫМИ** (forbidden coupling из parallel-development-map). Не строить два разных движка
вслепую и не сливать преждевременно.

---

## 10. Buildability / порядок (если/когда авторизуют)

Крупная нарезка V0–V3 заменена на более мелкий и безопасный план этапов 0–8: каждый slice
изолируем, тестируем и авторизуем отдельно. Это снижает риск и упрощает аудит каждого шага.

```
Этап 0  CLEAN IMPLEMENTATION PREFLIGHT (read-only, отдельный чистый worktree):
        - установить фактический актуальный origin/main; подтвердить чистую базу;
        - проверить runtime commit 9b00ede033a3d590f1f3f7267820ae6aa78a59b3, его merge-base и изменения;
        - проверить пересечения с exporter/bracket-escape track;
        - проверить наличие утверждённого N6B; определить точный allowlist первого slice; test plan;
        - кода нет; commit/push/merge нет.

Этап 1  V0 — VERIFY EXISTING MEMORY (без перестройки, доказать поведение тестами):
        - close/reopen recall; restart-game recall; инжект прошлых закрытых Aside-сессий;
        - независимость памяти от Ren'Py-save; фактическое поведение hardcoded dev_slot;
        - фактическое поведение Reset (сейчас full wipe);
        - сохранить честное разделение EXISTING / PARTIAL / PROPOSED.

Этап 2  SLICE 1 — MEMORY IDENTITY & SAFETY FOUNDATION (первый минимальный код):
        - profile_id; изоляция profile_id + character_id + world;
        - provenance CANON_WORLD / ASIDE_WORLD / USER_CLAIM;
        - обычный Reset очищает только окно; полный wipe — отдельная команда с подтверждением;
        - profile/character/provenance isolation tests; regression существующей JSON-памяти.
        БЕЗ: SQLite, emotional transition, role/relationship system, memory extractor, embeddings.

Этап 3  SLICE 2 — SQLITE + FTS5 (после доказанного Slice 1):
        - отдельная SQLite-БД Aside; FTS5; атомарная запись завершённого turn; сырой архив;
        - ключ profile_id + character_id + world; миграция JSON или контролируемое сосуществование;
        - backup/restore contract; Aside и CES — отдельные таблицы/схемы. Embeddings НЕ добавлять.

Этап 4  SLICE 3 — TRANSITION & ENTRY STATE:
        - runtime-проброс авторских beat.emotion / scene.intensity / emotional_anchors;
        - entry_state_snapshot; последнее действие; незавершённое намерение;
        - фаза эмоц./телесной инерции; задержанное осознание перехода; ASIDE_TRANSITION_REACTION;
        - AD-гейтинг после осознания; инерция не повышает отношения и не отменяет волю персонажа.

Этап 5  SLICE 4 — USER PROFILE, ROLE & RELATIONSHIP:
        - профиль пользователя; per-character overrides; постепенное раскрытие;
        - declared_user_role / character_accepted_role / role_trust;
        - явная смена роли + режим исправления профиля задним числом;
        - отдельный aside_relationship_state; отношения Aside не изменяют канон.

Этап 6  SLICE 5 — MEANINGFUL LONG-TERM MEMORY:
        - значимые эпизодические воспоминания; importance; emotional weight; topic tags;
        - unresolved topics; relationship summary; дедупликация; проверяемый extractor;
        - полный архив не инжектируется целиком; extractor никогда не пишет канон.

Этап 7  SLICE 6 — REMEMBER-BUT-REDACT (после загрузки старого save):
        - память встреч/отношений сохраняется; персонаж понимает откат основной линии;
        - будущие канон-события не раскрываются; поздняя встреча не удаляется целиком;
        - spoiler boundary и provenance проверяются тестами. Заменяет нынешний грубый guard.

Этап 8  SLICE 7 — SCALE LAYER (только после накопления реальных данных):
        - автоматическая суммаризация; пересуммаризация из скрытого архива; архивирование;
        - оценка качества SQLite + FTS5; embeddings и векторный поиск только при доказанной
          необходимости; чувство времени в Aside — отдельный будущий increment.
```

**Обязательные границы плана:**

- Каждый этап требует **отдельного preflight**; каждый code slice — **отдельной авторизации владельца**.
- Успешный этап **не** авторизует следующий автоматически.
- Один worktree — один пишущий агент. No push / no merge без отдельного разрешения.
- Runtime MVP branch `9b00ede…` остаётся **замороженной**; интеграция runtime branch — отдельная задача.
- Полный suite, probes под `config.developer` и exporter/bracket audit остаются отдельными integration gates.

---

## 11. Явные границы документа

- Это **preflight**, не контракт. Все решения (D-ASD-01…20 + D-ASD-G) ратифицированы, открытых пунктов нет.
  Код запрещён до **отдельной авторизации реализации** владельцем (ратификация решений ≠ авторизация кода).
- Ветка `vne-rn-aside-runtime-context` **заморожена** на `9b00ede`; документ её не размораживает.
- `N6_CHARACTER_ASIDE_CONTRACT.md` (CLOSED) **не переписывать** — v2 живёт отдельным документом.
- До push/merge MVP-ветки независимо остаются: полный suite, probes `cp_*`/`pe_*` под `config.developer`
  (не удалять), integration/merge preflight + аудит `renpy_v2_playable_exporter.py`.