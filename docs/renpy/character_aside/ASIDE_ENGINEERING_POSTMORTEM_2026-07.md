# Character Aside — инженерный постмортем (2026-07)

> Фактический разбор расследования и отладки, не сырой дневник. Основан на финальном
> коде (`695c840`, `8ca63fb`) и цепочке handoff-отчётов в
> `C:\DEV\Narrative\LOCAL_STORAGE\handoffs\` (индекс — `ASIDE_EVIDENCE_INDEX.md`).
> Полные тексты LLM-ответов и промпт-история сюда не переносятся.

## Executive summary

Character Aside — dev/test-only приватный LLM-чат с персонажем внутри Ren'Py. Основной
баг цикла отладки формулировался как «UI ничего не показывает после отправки
сообщения». Расследование заняло несколько итераций, потому что симптом был составным:
как минимум три независимых дефекта (layout, text-substitution crash, thread-boundary
violation) маскировали друг друга и по отдельности давали одинаковую внешнюю картину
«пусто». Финальное состояние (commits `8ca63fb`, `695c840`) proven корректно и
статически, и по runtime-evidence (JSONL-трейс по потокам). Работа опубликована на
`origin/feature/aside-input-diagnostics`, не влита в `main`.

## Initial symptom

После ввода сообщения и Enter/Send: поле ввода не показывало явной ошибки, игра не
зависала, но область истории чата оставалась пустой. Консольная проверка
`store.aside_chat_history` в отдельных прогонах иногда показывала `[]`.

## Why the symptom was misleading

Один и тот же внешний симптом ("пусто") имел минимум три разных первопричины на разных
этапах существования кода:

1. **На раннем этапе** — реальный разрыв в цепочке ввода (несколько последовательных
   попыток с `VariableInputValue`, `Return`, `changed`-callback), из-за которого
   сообщение иногда не попадало в обработчик вообще.
2. **После того, как ввод/worker/provider были доказанно рабочими** (по JSONL-трейсу
   `HANDLER_ENTER → ... → HISTORY_AFTER_REPLY_APPEND`, все события присутствуют,
   `store.aside_chat_history` растёт) — история **логически** заполнена, но **визуально**
   не отображалась. Это был чисто layout/render-дефект, не связанный с pipeline.
3. **После первого layout-фикса (`ymaximum` → `ysize`)** — рендер истории иногда падал
   с `SyntaxError` из-за необработанных квадратных скобок в динамическом тексте
   (`[LLM ERROR] ...`), что тоже выглядело как «ничего не появилось» для наблюдателя, не
   видящего traceback.

Каждый из этих трёх слоёв требовал отдельного доказательства, потому что «нет визуального
результата» — недостаточно специфичный симптом, чтобы отличить проблему ввода от
проблемы рендера от проблемы substitution.

## Investigation timeline (сжато)

1. **Root-cause audit ввода** (`CLAUDE_ASIDE_ROOT_CAUSE_AUDIT.md`) — построчная сверка
   `aside.rpy` с исходниками Ren'Py 8.5.3 SDK (`Input.event()`, `ScreenVariableInputValue`,
   `get_screen_variable`). Статически цепочка ввод→action→handler выглядела корректной;
   выдвинута гипотеза о stale-процессе как причине прошлых отчётов о пустой истории.
2. **Файловая JSONL-инструментация** (`ASIDE_UI_FILE_LOG_DIAGNOSTIC_REPORT.md`) — добавлены
   временные diagnostic-хуки (`_vne_aside_diag`) на весь путь `HANDLER_ENTER → ... →
   FINISH_CALLBACK_EXIT`. На свежем процессе цепочка отработала полностью и дважды
   (mock и local), с реальными ответами Ollama — это закрыло гипотезу «ввод не работает».
3. **Первый layout-фикс** — `frame: ymaximum 360` заменён на `frame: ysize 360` для истории
   чата (обоснование — доказано по исходникам `Window.render()`/`Viewport.render()`:
   `ymaximum` ограничивает только итоговый заявленный размер фрейма **после** рендера
   ребёнка, а не то, что реально предлагается вьюпорту). Диагностика удалена как временная.
4. **История всё ещё была не видна после первого фикса.** Потребовался отдельный
   `ASIDE_HISTORY_RENDER_TREE_AUDIT.md` — статическая проверка geometry/z-order/scrollbar
   не нашла структурного дефекта (760×360 в валидной позиции, контрастные цвета,
   несрезанный `for line in aside_chat_history`).
5. **Mirror/overlay эксперименты** (`ASIDE_HISTORY_MIRROR_PROOF_REPORT.md`) — добавлен
   dev-only mirror-виджет вне исходного viewport, затем полностью отдельный overlay-экран
   с собственным `zorder`. Это изолировало проблему до конкретного механизма: mirror
   немедленно упал с `SyntaxError` на первом реальном (не mock) ответе.
6. **Найдена настоящая причина невидимости**: `SyntaxError: invalid syntax` при попытке
   отрендерить строку `"Kira: [LLM ERROR] connection timed out"` — Ren'Py по умолчанию
   интерпретирует квадратные скобки в `text`-displayable как substitution-выражение.
   Исправление — `substitute False` на runtime-строках.
7. **Финальный рендер истории** — независимая от viewport/mirror-экспериментов
   переработка: прямой `vbox` (не `viewport`), `list(aside_chat_history[-10:])` как
   render-only срез, `text line: substitute False`. Подтверждено `ASIDE_FINAL_DIFF_QA_AUDIT.md`.
8. **Composer/geometry**: input и action-кнопки первоначально не помещались в default
   800×600 canvas проекта (в `novel/game/` нет `gui.rpy`/`config.screen_width`). Composer
   переработан на два отдельных `frame` с явными `xpos`/`ypos`/`xsize`/`ysize`, input
   получил `pixel_width 600`/`xmaximum 600`/`multiline True`.
9. **Обнаружена transitive thread-boundary проблема** — тот же `ASIDE_FINAL_DIFF_QA_AUDIT.md`
   доказал, что несмотря на рабочий UI, `_vne_aside_worker` транзитивно вызывал
   `import store` через старую `_vne_run_aside_turn`. Начата отдельная задача изоляции.
10. **Detached snapshot архитектура** (`ASIDE_WORKER_THREAD_ISOLATION_REPORT.md`) — введены
    `_vne_build_aside_turn_snapshot`, `_vne_assert_plain_worker_payload`,
    `_vne_detach_plain_worker_value`, `_vne_run_aside_turn_from_snapshot`. Прямой и
    транзитивный доступ к `store` из воркера устранён.
11. **Первая независимая QA этой архитектуры** (`ASIDE_THREAD_ISOLATION_INDEPENDENT_QA.md`)
    дала вердикт **T2**: `store`-доступ устранён, но JSONL trace-writer воркера всё ещё
    транзитивно читал `renpy.config.savedir`.
12. **Изоляция trace-пути** (`ASIDE_WORKER_TRACE_PATH_ISOLATION_REPORT.md`) — путь к
    JSONL резолвится один раз на главном потоке (`_vne_aside_trace_path_main_thread`),
    передаётся через snapshot как plain `str`, воркер использует только чистый
    path-agnostic writer.
13. **Повторная независимая QA** дала вердикт **T5** — статическая изоляция полностью
    доказана; единственная оговорка — provenance PID одного из runtime-тестов (см. ниже).
14. **Восстановление типизированной сигнатуры `_post_json`**, **selective commit** (два
    коммита, порядок provider→aside), **pre-push audit**, **первый push** —
    организационно-технические финальные шаги, без изменения архитектуры.

## Proven root causes

| # | Причина | Где доказано |
|---|---|---|
| 1 | `ymaximum` на `frame`, содержащем `yfill`-вьюпорт, не ограничивает то, что реально предлагается вьюпорту при рендере — только итоговый заявленный размер фрейма постфактум. `ysize` (эквивалент `yminimum=ymaximum`) резолвится раньше, до рендера потомка. | Чтение `renpy/display/layout.py: Window.render()`, `renpy/display/viewport.py: Viewport.render()/update_offsets()` в SDK 8.5.3. |
| 2 | Ren'Py `text`-displayable по умолчанию интерпретирует `[...]` в строке как substitution-выражение; непроверенный runtime-текст (LLM-ответы, error-сообщения) может содержать `[...]` и вызывать `SyntaxError` при рендере. | `ASIDE_HISTORY_MIRROR_PROOF_REPORT.md`, воспроизведённый traceback на строке `"Kira: [LLM ERROR] connection timed out"`. |
| 3 | `_vne_aside_worker` транзитивно вызывал `import store` через синхронный call chain (`_vne_run_aside_turn` → `_vne_readonly_canon_snapshot`), несмотря на то что тело самой worker-функции `store` не упоминало. | `ASIDE_FINAL_DIFF_QA_AUDIT.md`, раздел "FAIL — worker/store isolation invariant". |
| 4 | После первой изоляции воркер всё ещё транзитивно читал `renpy.config.savedir` через JSONL trace-writer. | `ASIDE_THREAD_ISOLATION_INDEPENDENT_QA.md`, вердикт T2; независимо переподтверждено в этой же цепочке работ повторным аудитом перед фиксом. |
| 5 | Оригинальный provider-код (`tools/llm_provider.py` на `HEAD` до изменений) не принимал `timeout_s` вообще — HTTP timeout был хардкожен на 30 секунд, из-за чего local-запросы к Ollama (реально занимающие 24–114 сек) систематически завершались `connection timed out`. | Diff `8ca63fb` относительно `git show HEAD~2:tools/llm_provider.py`; runtime evidence в ранних JSONL-трейсах (`provider_error: connection timed out` при 30-секундном таймауте). |

## Failed or incomplete approaches

Хронологически, для UI submit path (до перехода на текущую архитектуру):
`VariableInputValue` → `default_focus` → `Return("send")` → `changed`-callback →
структурированный `("send", msg)` результат из `call_screen` → raw string результат →
`VariableInputValue(returnable=True)` → `ScreenVariableInputValue` → `Return(message_text)` →
прямой `Function(helper, ..., message_text)` → `renpy.get_screen_variable`/
`renpy.set_screen_variable` из runtime screen action (**финальный, рабочий подход**).

Для layout/render:
- Отдельный mirror-виджет вне viewport — подтвердил, что данные доходят, но не сразу
  выявил substitution-баг (первая версия mirror сама упала с тем же `SyntaxError`).
- Полностью отдельный overlay-экран с `zorder 1000` и своим `on "show"/"hide"` —
  использован как diagnostic-инструмент для локализации дефекта до конкретного
  render-механизма, не стал частью финальной архитектуры.
- Видимая экранная trace-панель (текстовые строки событий прямо в screen) — использовалась
  как промежуточный debugging UI, полностью удалена из финального кода в пользу
  file-only observability (см. `ASIDE_ARCHITECTURE.md` §6).

Ничего из перечисленного не осталось в финальном коде — упоминается только как
исторический контекст.

## Final implementation

См. `ASIDE_ARCHITECTURE.md`. Кратко: detached main-thread snapshot → worker без Ren'Py
API → main-thread callback; прямой `vbox` с `substitute False` и срезом `[-10:]` для
рендера; `ysize`-based layout; typed keyword-only `_post_json` с configurable
`timeout_s`; file-only redacted JSONL observability, включаемая только при
`config.developer`.

## Git and governance lessons

- **Порядок коммитов имеет значение при частичной зависимости.** Provider (Commit
  `8ca63fb`) закоммичен раньше Aside (Commit `695c840`), потому что HEAD-версия
  provider не поддерживала `timeout_s` вообще — обратный порядок оставил бы в истории
  коммит, где Aside передаёт `timeout_s=120`, а provider его не читает (тихая деградация
  назад к 30-секундному таймауту в промежуточном состоянии).
- **Selective staging с явными путями (`git add -- <path>`), не `git add -A`/`.`**, на
  каждом шаге верифицировался через `git diff --cached --stat`/`--name-only` — это
  предотвратило непреднамеренное включение параллельно накопленного unrelated dirty
  state (`options.rpy`, `.gitignore`, посторонние Ren'Py-каталоги `VGE`/`VOYAGE`/`VOYAGE_2`).
- **Независимая QA как отдельный, скептический проход** (не просто повтор отчёта
  исполнителя) дважды поймала реальные транзитивные нарушения границы потока
  (`store`, затем `renpy.config`), которые прошли бы незамеченными при поверхностной
  проверке "воркер не упоминает `store` в своём теле".
- **Pre-push audit до push, а не после** — подтвердил точный состав исходящих коммитов
  и файлов через сравнение с `origin/main` до публикации, а не постфактум.

## Lessons for future Ren'Py games

1. Комбинация `ymaximum`-only на фрейме + `yfill`-дочерний `viewport`/контейнер —
   структурно ненадёжный паттерн; для детерминированной высоты нужен `ysize` (или
   `yminimum == ymaximum`) на уровне, откуда высота реально наследуется потомками.
2. Любой `text`-displayable, отображающий недоверенный/динамический текст (LLM-ответы,
   пользовательский ввод, сообщения об ошибках) **обязан** иметь `substitute False`,
   если только текст не оборачивается контролируемым форматированием.
3. Фоновые потоки в Ren'Py (`renpy.invoke_in_thread`) не должны напрямую или
   транзитивно обращаться к `store`, `renpy.config`, screen variables — см. ADR. Проверка
   "функция не упоминает `store` в своём теле" **недостаточна**; нужен анализ полного
   транзитивного call graph, включая вызовы во внешние модули.
4. Для HTTP-интеграций с локальными LLM (Ollama и подобные) закладывать configurable,
   существенно больший timeout, чем стандартные 30 секунд облачных API — наблюдаемая
   латентность реального локального инференса в этом проекте была 24–114 секунд.
5. JSONL-трейс с явным полем `thread` (имя потока) — минимальная, но достаточная
   observability для доказательства пересечения thread boundary без визуального UI.

## Remaining deferred items

- **`novel/game/options.rpy` (`config.developer = True`)** — статус: **DEFER AND LEAVE
  DIRTY**. Решение по этому файлу сознательно отложено как отдельная задача policy-аудита
  (нужно ли `config.developer` глобально включённым для release-сборки, или это только
  acceptance-режим). Файл остаётся модифицированным, но не закоммиченным.
- **`cloud`-провайдер не подключён к UI** — реализован в `tools/llm_provider.py`, но
  Character Aside не предоставляет способ его выбрать (Provider-кнопка переключает
  только `local`/`mock`).
- **Merge в `main`** — не выполнен и не авторизован этим этапом работы.

## Accepted caveat: PID provenance P2

Один из runtime-тестов (независимая QA изоляции trace-пути) содержал два JSONL-хода
(mock, затем local), которые пользователь ассоциировал с конкретным PID запущенного
процесса, но фактический PID в трейсе отличался от заявленного. Независимая проверка
классифицировала это как **P2**: несколько независимых сигналов (точное совпадение длины
двух тестовых сообщений, корректное чередование `provider` mock→local, непрерывность
`history_len` между ходами внутри одной сессии, отсутствие посторонних событий в
промежутке) строго коррелируют и делают данные достоверными, но формального
OS-level доказательства связи родитель/потомок процессов получить не удалось — оба
процесса к моменту проверки уже завершились, ancestry-журналирование (Sysmon/Event ID
4688) не подтверждено как включённое. Владелец проекта принял P2 как **неблокирующую**
оговорку, поскольку оба независимых call graph (turn/provider и trace-writer) уже были
статически доказаны отдельно от этого runtime-теста.
