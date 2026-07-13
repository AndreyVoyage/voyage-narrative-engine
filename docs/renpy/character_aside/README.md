# Character Aside — инженерный пакет документации

> **Назначение.** Единая точка входа в документацию N5/N6-фичи **Character Aside** —
> приватного LLM-чата с персонажем внутри Ren'Py-раннера VNE. Этот пакет фиксирует
> **финальную, рабочую** архитектуру и историю её отладки как канонический источник
> для повторного использования в будущих Ren'Py-играх и LLM-интеграциях проекта.

**Technical phase completed: 2026-07-13**

## Статус реализации

Техническая фаза Character Aside (async pipeline, thread isolation, рендер истории,
provider timeout) **завершена и опубликована**, но **не влита в `main`**.

```text
Final commits:
8ca63fb  fix(llm): support configurable provider timeouts
695c840  fix(renpy): finalize thread-safe character aside

Remote branch: origin/feature/aside-input-diagnostics
HEAD:          695c840a277055dd2e9c5d7649878063932493d0
```

Работа находится на feature-ветке и ждёт отдельного решения о merge в `main`. Этот
пакет документации **не утверждает и не подразумевает**, что код уже в `main`.

## Иерархия источников правды

При любом противоречии между документами этого пакета и фактическим кодом —
**побеждает код**. Порядок приоритета:

1. **Финальный закоммиченный код** — `novel/game/aside.rpy` (commit `695c840`),
   `tools/llm_provider.py` (commit `8ca63fb`).
2. **Финальные независимые QA-отчёты** (`docs/renpy/character_aside/ASIDE_EVIDENCE_INDEX.md`
   помечает их как `FINAL QA`).
3. **Финальный runtime evidence** (JSONL-трейс, локальный, вне репозитория — см.
   `ASIDE_EVIDENCE_INDEX.md`).
4. **Промежуточные отчёты** (`HISTORICAL`) — контекст расследования, не источник
   архитектурных фактов.
5. **Устаревшие гипотезы** — сохранены только в постмортеме как урок, не как факт.

Документы этого пакета относятся к уровням 1–3 (канонизированы после сверки с
финальным кодом). Сырые handoff-отчёты в `LOCAL_STORAGE/handoffs/` — это
**подтверждающая доказательная база, не канон архитектуры**; см. предупреждение в
`ASIDE_EVIDENCE_INDEX.md`.

## Документы пакета

| Документ | Назначение |
|---|---|
| [`ASIDE_ARCHITECTURE.md`](ASIDE_ARCHITECTURE.md) | Финальная архитектура: main thread / worker thread / callback, provider routing, рендер истории, observability. |
| [`ASIDE_ENGINEERING_POSTMORTEM_2026-07.md`](ASIDE_ENGINEERING_POSTMORTEM_2026-07.md) | Фактический постмортем: что было симптомом, что вводило в заблуждение, какие подходы не сработали, какие уроки остаются. |
| [`ASIDE_DEBUGGING_RUNBOOK.md`](ASIDE_DEBUGGING_RUNBOOK.md) | Операционный runbook: что проверять первым при "ничего не появилось", канонический event chain, PowerShell-примеры. |
| [`ASIDE_ACCEPTANCE_CHECKLIST.md`](ASIDE_ACCEPTANCE_CHECKLIST.md) | Компактный чеклист приёмки для этой и будущих Ren'Py-LLM интеграций. |
| [`ASIDE_EVIDENCE_INDEX.md`](ASIDE_EVIDENCE_INDEX.md) | Индекс всех handoff-отчётов с классификацией CURRENT/HISTORICAL/SUPERSEDED/FINAL QA. |
| [`../../decisions/ADR_RENPY_LLM_THREAD_BOUNDARY.md`](../../decisions/ADR_RENPY_LLM_THREAD_BOUNDARY.md) | ADR: почему фоновые потоки в Ren'Py-интеграциях не должны трогать `store`/`renpy.config`/screen variables. |
| [`../../workflows/CONTEXT_RETIREMENT_PROTOCOL.md`](../../workflows/CONTEXT_RETIREMENT_PROTOCOL.md) | Общий (не только Aside) протокол сворачивания долгой отладочной работы в документацию + компактную память. |

Локальный (не в репозитории) артефакт: `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\VNE_ASIDE_CONTEXT_CAPSULE.md` — компактная capsule для памяти агента; см. `ASIDE_EVIDENCE_INDEX.md`.

## Поддерживаемые провайдеры (по факту закоммиченного кода)

Согласно `tools/llm_provider.py` (commit `8ca63fb`) и `novel/game/aside.rpy` (commit `695c840`):

- **`mock`** — детерминированный, офлайн, без сети. `provider="mock"` выбирается явно через кнопку Provider в дев-оверлее.
- **`local`** — Ollama-совместимый chat endpoint (`http://localhost:11434/api/chat` по умолчанию), таймаут HTTP-запроса **120 секунд**, задаётся явно из `aside.rpy`.
- **`cloud`** — OpenAI-совместимый chat completions endpoint, требует `OPENAI_API_KEY`; таймаут по умолчанию **30 секунд**. `cloud` реализован в `llm_provider.py`, но **не подключён** к UI Character Aside (Provider-кнопка переключает только `local`/`mock`) — это ограничение, не баг.
- **Автоматического fallback `local → mock` нет.** Ошибка local-провайдера видна игроку как `[LLM ERROR] ...`, никогда не подменяется мок-ответом.

## Известные ограничения

- `cloud`-провайдер не подключён к игровому UI (только `mock`/`local`).
- Dev-overlay ("Aside" кнопка) виден всегда (`config.overlay_screens`), а не только в specific playable-контексте — фича остаётся **dev/test-only**, не подключена к playable selector SC_003–SC_018 (см. `N6_CHARACTER_ASIDE_CONTRACT.md` §7 и заголовок `aside.rpy`).
- `novel/game/options.rpy` (`config.developer = True`) остаётся **преднамеренно незакоммиченным** ("DEFER AND LEAVE DIRTY") — см. `ASIDE_ENGINEERING_POSTMORTEM_2026-07.md`, раздел "Remaining deferred items".
- История чата (`aside_chat_history`) — это UI session log, который **намеренно** обнуляется при каждом входе в Aside (`label aside_dev_entry`/`label aside_quick`); персистентная память ведётся отдельно, файлово, через `tools/aside_memory_store.py`, и не зависит от этого UI-списка.
- PID provenance для одного из runtime-тестов принят как caveat **P2** (сильная корреляция по нескольким независимым сигналам, но не формальное OS-level доказательство родитель/потомок — оба процесса к моменту проверки уже завершились). Не блокирует архитектурный вывод; подробности в постмортеме.

## Явное ограничение области действия этого README

Этот README и весь пакет документации описывают только N6 Character Aside
(`novel/game/aside.rpy`, `tools/llm_provider.py`, `tools/aside_context_builder.py`,
`tools/aside_memory_store.py`). Он не заменяет `AGENTS.md`, `N6_CHARACTER_ASIDE_CONTRACT.md`
или `NARRATIVE_ARCHITECTURE.md` как источники правды по остальным слоям VNE.
