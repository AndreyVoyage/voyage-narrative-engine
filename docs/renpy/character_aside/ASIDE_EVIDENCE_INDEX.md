# Character Aside — индекс доказательной базы

> Индекс, не копия. Ссылки ниже указывают на файлы в
> `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\` — это **локальное, приватное** хранилище,
> которое может не существовать на другой машине или в другом клоне репозитория.
>
> **LOCAL_STORAGE evidence is local/private and may not exist on another machine.**
> Ни один из перечисленных файлов не копируется в Git. Канонические факты, которые они
> подтверждают, зафиксированы в `ASIDE_ARCHITECTURE.md` и
> `ASIDE_ENGINEERING_POSTMORTEM_2026-07.md` — эти два документа самодостаточны и не
> требуют доступа к `LOCAL_STORAGE`.

## Легенда статусов

| Статус | Значение |
|---|---|
| `CURRENT EVIDENCE` | Описывает состояние, актуальное прямо сейчас (финальные коммиты, push). |
| `FINAL QA` | Последний независимый read-only аудит, чей вердикт принят как основание для commit/push. |
| `HISTORICAL` | Ценный контекст расследования; не источник текущих архитектурных фактов. |
| `SUPERSEDED` | Конкретные технические выводы документа позже опровергнуты/заменены — читать только как урок, не как факт. |

## Финальные коммиты и remote

| Факт | Значение |
|---|---|
| Commit (provider) | `8ca63fb` — `fix(llm): support configurable provider timeouts` |
| Commit (aside) | `695c840` — `fix(renpy): finalize thread-safe character aside` |
| Remote branch | `origin/feature/aside-input-diagnostics` |
| Push evidence | `ASIDE_FIRST_PUSH_RESULT.md` (см. таблицу ниже) |

## Индекс отчётов

| Файл | Дата/время | Роль/назначение | Статус | Каноничный факт | Предупреждение |
|---|---|---|---|---|---|
| `ASIDE_INPUT_FIX_REPORT.md` | 10.07 00:13 | Ранняя попытка починки submit-цепочки | `SUPERSEDED` | — | Механизм ввода той версии не используется в финальном коде. |
| `ASIDE_UI_RUNTIME_FIX_REPORT.md` | 10.07 00:31 | Ранний runtime-фикс UI | `SUPERSEDED` | — | Предшествует финальной архитектуре. |
| `ASIDE_BOTTOM_ANCHORED_LAYOUT_FIX_REPORT.md` | 10.07 00:40 | Ранний layout-фикс | `SUPERSEDED` | — | Layout полностью переработан позже (absolute positioning, `ysize`). |
| `ASIDE_SINGLE_INPUT_FOCUS_FIX_REPORT.md` | 10.07 00:51 | Фикс единственного input/focus | `HISTORICAL` | Единственный editable input — устойчивый инвариант с этого момента. | — |
| `ASIDE_LLM_INFINITE_LOOP_WATCHDOG_FIX_REPORT.md` | 10.07 01:43 | `renpy.not_infinite_loop`-based watchdog | `SUPERSEDED` | — | Полностью заменено настоящим `renpy.invoke_in_thread` воркером. |
| `ASIDE_EXPLICIT_INPUT_CHANGED_SUBMIT_FIX_REPORT.md` | 10.07 06:36 | `changed`-callback submit попытка | `SUPERSEDED` | — | Не используется в финальном `ScreenVariableInputValue`-подходе. |
| `ASIDE_LLM_ASYNC_THREAD_FIX_REPORT.md` | 10.07 07:32 | Первое введение async-потока | `SUPERSEDED` | Async-архитектура как направление подтвердилась. | Конкретная реализация (без detached snapshot) заменена. |
| `ASIDE_TEXT_INTERPOLATION_FIX_REPORT.md` | 10.07 12:03 | Ранний interpolation-фикс | `HISTORICAL` | Первое столкновение с проблемой substitution в Ren'Py `text`. | Не покрывал все runtime-строки; полное решение — позже. |
| `ASIDE_CANONICAL_INPUT_RETURN_FIX_REPORT.md` | 10.07 12:33 | Попытка через `Return`/`call_screen` | `SUPERSEDED` | — | Финальная архитектура не использует `call_screen`-return для submit. |
| `ASIDE_ACTUAL_CODE_DIAGNOSTIC_REPORT.md` | 10.07 13:01 | Диагностика фактического кода | `HISTORICAL` | — | — |
| `ASIDE_SCREEN_VARIABLE_INPUT_FIX_REPORT.md` | 10.07 13:08 | Введение `ScreenVariableInputValue` | `HISTORICAL` | Механизм ввода, доживший до финальной версии. | Точная реализация вокруг него менялась ещё несколько раз. |
| `ASIDE_DIRECT_SCREEN_SEND_FIX_REPORT.md` | 10.07 13:17 | Прямой screen-send вариант | `SUPERSEDED` | — | — |
| `ASIDE_AFTER_DIRECT_SEND_ACTUAL_CODE_REPORT.md` | 10.07 15:47 | Пост-фикс диагностика | `HISTORICAL` | — | — |
| `ASIDE_RUNTIME_SCREEN_VALUE_CAPTURE_FIX_REPORT.md` | 10.07 15:58 | Runtime-захват screen value | `HISTORICAL` | Подход `renpy.get_screen_variable` в момент action — дожил до финала. | — |
| `ASIDE_LIVE_SCREEN_VALUE_FIX_REPORT.md` | 10.07 16:04 | Live screen value фикс | `SUPERSEDED` | — | — |
| `ASIDE_CONFIGURABLE_OLLAMA_TIMEOUT_REPORT.md` | 10.07 18:32 | Первое введение `timeout_s` в provider | `SUPERSEDED` | Идея configurable timeout подтвердилась. | Конкретная сигнатура `_post_json` этой версии была без типизации/keyword-only — исправлено позже commit'ом `8ca63fb`. |
| `CLAUDE_ASIDE_ROOT_CAUSE_AUDIT.md` | 11.07 08:07 | Построчный аудит ввода против Ren'Py SDK | `HISTORICAL` | Статически input/action/handler цепочка корректна; ввод не был первопричиной наблюдаемого симптома. | Гипотеза "stale-процесс" была одной из нескольких, не единственной причиной. |
| `ASIDE_UI_FILE_LOG_DIAGNOSTIC_REPORT.md` | 11.07 08:57 | JSONL-доказательство полного pipeline | `HISTORICAL` | На момент проверки: Enter/Send/worker/provider/callback работали end-to-end, включая реальные ответы Ollama. | Не доказывал визуальный рендер — история могла быть заполнена в `store`, но не видна на экране (см. следующие отчёты). |
| `ASIDE_HISTORY_RENDER_TREE_AUDIT.md` | 12.07 18:20 | Статический аудит geometry/render-tree | `HISTORICAL` | Geometry (760×360 history frame) статически валидна; классификация R7 — "not proven, требуется mirror". | Не нашёл фактическую причину невидимости — это сделал следующий отчёт. |
| `ASIDE_HISTORY_MIRROR_PROOF_REPORT.md` | 12.07 21:51 | Mirror/overlay эксперименты | `HISTORICAL` | **Ключевое открытие**: `SyntaxError` из-за substitution в `[LLM ERROR] ...`; `substitute False` — необходимое условие. | Экспериментальный mirror/overlay-код не входит в финальную реализацию. |
| `ASIDE_FINAL_DIFF_QA_AUDIT.md` | 12.07 22:40 | Строгий read-only аудит после render-фикса | `HISTORICAL` | Подтвердил: normal history/composer/input/provider routing работают; **FAIL** по transitive `store`-доступу воркера; provider-сигнатура деградировала. | FAIL по store-доступу и сигнатуре — оба зафиксированы и позже устранены; не читать как текущий блокер. |
| `ASIDE_WORKER_THREAD_ISOLATION_REPORT.md` | 12.07 22:45 | Первая реализация detached snapshot | `SUPERSEDED` | Детэч-архитектура (`_vne_build_aside_turn_snapshot` и т.д.) как направление подтвердилась. | Конкретная версия trace-writer этого коммита ещё содержала утечку `renpy.config.savedir` в воркер — найдено следующим отчётом. |
| `ASIDE_THREAD_ISOLATION_INDEPENDENT_QA.md` | 12.07 23:01 | Независимая QA изоляции (1-й проход) | `SUPERSEDED` | Подтвердил устранение прямого/транзитивного `store`-доступа. | Вердикт **T2** (утечка `renpy.config.savedir` через trace-writer) — устранено следующей парой отчётов; не читать как актуальный статус. |
| `ASIDE_WORKER_TRACE_PATH_ISOLATION_REPORT.md` | 12.07 23:48 | Фикс T2: изоляция trace-пути | `HISTORICAL` | Введены `_vne_aside_trace_path_main_thread`/`_vne_aside_trace_write_at_path`/`_vne_aside_worker_trace`. | Runtime evidence в этом отчёте содержит PID, не совпадающий с фактически запущенным процессом — уточнено в следующем отчёте. |
| `ASIDE_TRACE_PATH_ISOLATION_INDEPENDENT_QA.md` | 13.07 00:07 | Независимая QA изоляции (финальная) | `FINAL QA` | **Вердикт T5**: оба worker-графа (turn/provider, trace-writer) статически доказаны свободными от `store`/`renpy.config`/screen variables; runtime thread-evidence подтверждён для mock и local. | PID provenance классифицирован как P2 (принято как неблокирующая оговорка владельцем проекта). |
| `LLM_PROVIDER_TYPED_SIGNATURE_REPORT.md` | 13.07 00:19 | Восстановление typed keyword-only `_post_json` | `HISTORICAL` | Финальная сигнатура `_post_json` зафиксирована в commit `8ca63fb`. | — |
| `LLM_PROVIDER_TYPED_SIGNATURE_INDEPENDENT_QA.md` | 13.07 00:20 | Независимая QA сигнатуры | `FINAL QA` | Подтверждено: единственные call sites уже были keyword-compliant; поведение не изменилось; local=120s/cloud=30s/no-fallback сохранены. | — |
| `ASIDE_SELECTIVE_STAGING_COMMIT_PLAN.md` | 13.07 00:28 | План selective staging (до выполнения) | `SUPERSEDED` | Рекомендованный порядок provider→aside был принят. | Это только план; фактический результат — в `ASIDE_SELECTIVE_COMMITS_RESULT.md`. |
| `ASIDE_SELECTIVE_COMMITS_RESULT.md` | 13.07 00:35 | Результат двух локальных коммитов | `CURRENT EVIDENCE` | Коммиты `8ca63fb`/`695c840` созданы в этом порядке; staged set пуст после; unrelated dirty state не тронут. | — |
| `ASIDE_PRE_PUSH_AUDIT.md` | 13.07 10:49 | Read-only pre-push аудит | `CURRENT EVIDENCE` | Divergence против `origin/main`: ровно 2 исходящих коммита, ровно 2 файла; вердикт `PUSH_BLOCKED_NO_UPSTREAM` (организационный, не архитектурный блокер). | — |
| `ASIDE_FIRST_PUSH_RESULT.md` | 13.07 22:25 | Результат первого push | `CURRENT EVIDENCE` | `origin/feature/aside-input-diagnostics` создана; upstream установлен; divergence `0 0`; `origin/main` не тронут. | — |

## Приоритет источников (повтор из README)

1. Финальный закоммиченный код.
2. `FINAL QA` отчёты (`ASIDE_TRACE_PATH_ISOLATION_INDEPENDENT_QA.md`,
   `LLM_PROVIDER_TYPED_SIGNATURE_INDEPENDENT_QA.md`) и `CURRENT EVIDENCE` (последние три
   строки таблицы).
3. Финальный runtime evidence (JSONL, локально, не в Git).
4. `HISTORICAL` отчёты — контекст расследования.
5. `SUPERSEDED` отчёты — читать только как урок ("что не сработало"), никогда как
   источник текущего факта.

Полные тексты JSONL-событий (`aside_internal_trace.jsonl`) не копируются ни в Git, ни в
этот индекс — они остаются локальным runtime-артефактом в
`C:\DEV\Narrative\LOCAL_STORAGE\renpy_saves\vne_dev\`.
