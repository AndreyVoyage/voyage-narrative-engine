# Character Aside — операционный runbook

> Практическое руководство для диагностики Character Aside и аналогичных
> Ren'Py + LLM интеграций. Основано на реальном расследовании, задокументированном в
> `ASIDE_ENGINEERING_POSTMORTEM_2026-07.md`.

## Канонический event chain

Финальная JSONL-инструментация (`_vne_aside_trace`/`_vne_aside_worker_trace`, активна
только при `config.developer == True`) пишет события в этом порядке при штатной работе:

```text
ui_submit
message_capture
history_write
worker_dispatch
worker_start
provider_result   ИЛИ   provider_error
main_thread_callback_queued
main_thread_callback
final_history_write
```

Каждое событие несёт `ts`, `event`, `pid`, `thread`, плюс контекстные поля (`provider`,
`pending`, `history_len`, `history_last`; чувствительные строки — `msg`, `reply_preview`,
`history_last`, `error` — редактированы до `<redacted:N chars>`).

**Ожидаемое распределение по потокам:**

```text
ui_submit, message_capture, history_write, worker_dispatch   → MainThread
worker_start, provider_result/provider_error                 → НЕ MainThread (worker)
main_thread_callback_queued                                  → НЕ MainThread (worker, до диспетчеризации)
main_thread_callback, final_history_write                    → MainThread
```

## "Пользователь ввёл текст — ничего не появилось": что проверять первым

Порядок проверки — от дешёвого/быстрого к дорогому, не наоборот:

1. **Есть ли `HANDLER_ENTER`/`ui_submit` в JSONL вообще?** Если нет — Send/Enter не
   долетел до handler'а. Смотри следующий раздел.
2. **Есть ли `message_capture` с непустым `msg`?** Если `ui_submit` есть, а
   `message_capture` пуст/отсутствует — проблема в чтении screen variable, не в самом
   action.
3. **Есть ли `history_write`?** Если да — `store.aside_chat_history` реально пополняется
   на уровне state. Значит проблема (если есть) — визуальная, не pipeline.
4. **Виден ли текст на экране, при этом `history_write` подтверждён?** Это отдельный,
   не сводимый к трейсу вопрос — JSONL не видит экран (см. ниже "diagnose без overlay").
5. **Только если всё вышеперечисленное подтверждено** — переходить к проверке
   worker/provider (следующие разделы).

## Как определить, сработал ли Send/Enter

Проверить `HANDLER_ENTER`/`ui_submit` в свежем JSONL-логе после клика/Enter. Если
события нет вообще:
- не предполагать focus/sensitive-проблему без runtime evidence — статически input
  action в Ren'Py 8.5.3 SDK (`Input.event()`, ветка `input_enter`) вызывает `self.action`
  безусловно, если он задан;
- проверить, не тестируется ли **устаревший запущенный процесс** (см. раздел про PID
  ниже) — самая частая причина "код исправлен, но эффекта нет".

## Как определить, была ли записана history

`history_write` в JSONL с корректным `history_len`/`history_last` — прямое
доказательство. Если событие отсутствует, но `message_capture` присутствует — искать
разрыв между чтением сообщения и его записью в `store.aside_chat_history` (guard-условия,
исключения до записи).

## Как определить, стартовал ли worker

`worker_start` в JSONL, поле `thread` **не равно** `"MainThread"`. Отсутствие
`worker_start` при наличии `worker_dispatch` означает, что `renpy.invoke_in_thread` не
был вызван или упал до старта потока (например, ошибка построения/валидации snapshot —
проверить `[LLM ERROR] Cannot prepare worker payload: ...` в видимой истории).

## Как отделить provider-ошибку от UI render-ошибки

- `provider_error` в JSONL с непустым `error` → ошибка на уровне LLM-провайдера
  (сеть/таймаут/невалидный ответ). Это НЕ баг рендера.
- Отсутствие `provider_error`/`provider_result`, но UI пуст → это, вероятнее всего,
  render-дефект (layout/substitution), не provider. Не чинить provider-код по этому
  симптому.
- Наличие `final_history_write` с корректным `history_last`, но текст всё равно не
  виден глазом → однозначно render-дефект. Смотри раздел про quick geometry test.

## Как проверить thread ownership callback'а

`main_thread_callback` и `final_history_write` должны иметь `thread: "MainThread"`.
Если хотя бы одно из них показывает воркер-поток — граница потоков нарушена, callback
вызывается не через `renpy.invoke_in_main_thread`, это архитектурный регресс, требующий
немедленного фикса (см. ADR).

## Как диагностировать local timeout

1. Проверить время между `worker_start` и `provider_result`/`provider_error` в JSONL —
   это фактическая латентность запроса.
2. Если `provider_error` с `error` вида `"connection timed out"` при времени около
   30 секунд — таймаут, вероятно, не дошёл до 120 (проверить, что `aside.rpy` передаёт
   `params={"timeout_s": 120}` и что `_complete_local`/`_post_json` реально используют
   его, а не игнорируют).
3. Быстрый CLI-смок без ожидания полного timeout:

   ```powershell
   & "C:\DEV\Narrative\renpy-8.5.3-sdk\lib\py3-windows-x86_64\python.exe" `
     tools\llm_provider.py complete --provider local --message "TIMEOUT_PROBE" --param timeout_s=1
   ```

   Быстрый `"ERROR: connection timed out"` (а не зависание/долгое ожидание) доказывает,
   что параметр `timeout_s` реально доходит до `urllib.request.urlopen(timeout=...)`.

## Как работать с динамическим текстом, содержащим квадратные скобки

Любой `text`-displayable, показывающий текст, который не является литералом,
написанным разработчиком (LLM-ответы, `[LLM ERROR] ...`, пользовательский ввод),
**обязан** иметь `substitute False`:

```renpy
text line:
    substitute False
    color "#d8d8e8"
```

Без этого строки вроде `"Kira: [LLM ERROR] connection timed out"` вызывают
`SyntaxError` во время рендера, потому что Ren'Py по умолчанию интерпретирует `[...]`
как substitution-выражение.

## Как тестировать длинный ввод и layout 800×600

В проекте нет `gui.rpy`/`config.screen_width` → действует Ren'Py default 800×600.
Перед тем как считать composer готовым:

1. Ввести длинную строку (>60 символов) в поле Message — убедиться, что `input`
   (`xmaximum`, `pixel_width`, `multiline True`) не выходит за рамки своего `frame`.
2. Убедиться, что кнопки Send/Reset Aside/Close остаются видимы и кликабельны при
   максимально заполненном поле ввода.
3. Проверить, что message-row и action-row (два отдельных `frame` с явными
   `xpos`/`ypos`/`xsize`/`ysize`) не перекрываются — сумма высот + отступ между ними
   должна укладываться в оставшуюся часть 800×600 canvas ниже истории.

## Как отлаживать без добавления видимых overlay поверх modal screen

`screen aside_chat_log` — `modal True`. Видимые debug-overlay (красные рамки, отдельные
`zorder`-экраны) полезны как **временный** diagnostic-инструмент (см. постмортем,
"Failed or incomplete approaches"), но не должны оставаться в финальном коде:

- предпочитать file-only JSONL-трейс (`_vne_aside_trace`) — не рендерится, не может
  сломать layout;
- если визуальный overlay всё же нужен для локализации — использовать отдельный,
  явно поименованный `screen` с высоким `zorder`, `on "show"`/`on "hide"` на основном
  экране, и **обязательно удалить** его в финальном коммите.

## Когда останавливать спекулятивные патчи и добавлять observability

Если один и тот же гипотетический фикс (layout-свойство, input-механизм, provider-параметр)
применяется **второй раз подряд без независимого runtime-подтверждения предыдущего** —
это сигнал остановиться и вставить измеримую, персистентную diagnostic-точку (JSONL
event, а не print/consol-check), прежде чем пробовать третий вариант. Смотри
"Investigation timeline" в постмортеме: смена гипотезы без evidence несколько раз подряд
была основной причиной затянутого расследования.

## Роль-последовательность (governance)

```text
vne_renpy_adapter          — реализация/фикс кода
  → vne_qa                 — независимый read-only аудит (explicit one-task exception,
                              если постоянная роль не владеет всем затронутым деревом)
    → manual runtime acceptance   — реальный запуск, реальные маркеры, визуальное
                                     подтверждение (JSONL не видит экран)
      → selective commit          — явные пути в git add, verify git diff --cached
                                     на каждом шаге
        → pre-push audit          — divergence/outgoing-commits/outgoing-files против
                                     origin до push
```

Каждый переход требует отдельного explicit разрешения владельца проекта; не
объединять шаги (например, commit сразу после implementation без независимой QA)
без явного указания.

## Какой lint считать авторитетным для `.rpy`

Ruff, Pylance и другие generic Python linters **не являются авторитетной проверкой
полного Ren'Py `.rpy`-файла**: screen language не равен обычному Python, поэтому
валидные свойства Ren'Py могут ошибочно отмечаться как проблемы. В этом расследовании
конкретным false positive было свойство `ysize`.

Авторитетная проверка полного `.rpy` — lint локального Ren'Py SDK (команда ниже).
Generic linters при этом остаются полезны для изолированных pure-Python блоков, если
они проверяются отдельно от screen language; утверждать, что Ruff/Pylance бесполезны
во всех контекстах, неверно.

## PowerShell-примеры

**Хвост JSONL-трейса:**

```powershell
Get-Content "C:\DEV\Narrative\LOCAL_STORAGE\renpy_saves\vne_dev\aside_internal_trace.jsonl" -Tail 20 -Encoding UTF8
```

**Только события по потокам (например, проверка thread ownership):**

```powershell
Get-Content "C:\DEV\Narrative\LOCAL_STORAGE\renpy_saves\vne_dev\aside_internal_trace.jsonl" -Encoding UTF8 |
    Select-String '"event": "worker_start"|"event": "main_thread_callback"|"event": "final_history_write"'
```

**Ren'Py lint:**

```powershell
& "C:\DEV\Narrative\renpy-8.5.3-sdk\lib\py3-windows-x86_64\python.exe" `
  "C:\DEV\Narrative\renpy-8.5.3-sdk\renpy.py" `
  "C:\DEV\Narrative\voyage-narrative-engine\novel" `
  lint
```

**Проверка staged-файлов перед коммитом:**

```powershell
git status --short
git diff --cached --name-only
git diff --cached --stat
```

**Проверка divergence с upstream перед push:**

```powershell
git rev-parse --abbrev-ref --symbolic-full-name "@{u}"
git rev-list --left-right --count "@{u}...HEAD"
git log --oneline --decorate "@{u}..HEAD"
```

## Stop conditions

Остановиться и запросить явное решение владельца проекта, а не продолжать
автономно, если:

- один и тот же файл был изменён кем-то ещё между вашими шагами (сверять
  `git diff --stat` перед каждой правкой с ожидаемым состоянием);
- независимая QA даёт FAIL/T2-подобный вердикт — не считать отчёт исполнителя
  достаточным для commit;
- обнаружен посторонний dirty/untracked путь, не относящийся к задаче — не
  stage'ить его "заодно";
- `git diff --check` или Ren'Py lint не проходят — не продолжать до исправления;
- нет upstream-ветки для push — не изобретать remote branch, сообщить и запросить
  разрешение на `-u`.
