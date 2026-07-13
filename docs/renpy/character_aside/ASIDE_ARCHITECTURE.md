# Character Aside — финальная архитектура

> Описывает только **финальную, закоммиченную** архитектуру (commit `695c840` для
> `novel/game/aside.rpy`, commit `8ca63fb` для `tools/llm_provider.py`). Промежуточные
> варианты (mirror, overlay, красная отладочная панель, экранная trace-панель) в
> финальном коде отсутствуют и здесь не описываются как архитектура — см. постмортем.

## 0. Главный принцип границы потоков

Ren'Py API (`store`, `renpy.config`, screen variables, любые live-контейнеры) может
читаться и мутироваться **только в главном потоке**. Фоновый worker-поток получает
исключительно detached plain-data snapshot и не имеет обратного пути к Ren'Py API,
кроме одного явно прокинутого пути записи файла. Формальное обоснование — в
`docs/decisions/ADR_RENPY_LLM_THREAD_BOUNDARY.md`.

```text
MAIN THREAD                              WORKER THREAD                MAIN-THREAD CALLBACK
──────────────                           ──────────────                ────────────────────
UI action (Enter/Send)
  → читает store
  → читает provider config
  → строит detached snapshot   ──snapshot (plain dict)──▶
  → валидирует snapshot                  получает snapshot
  → резолвит trace_path                  НЕ читает store
  → invoke_in_thread(worker)             НЕ читает renpy.config
                                          НЕ читает screen variables
                                          вызывает provider (по snapshot)
                                          пишет JSONL через чистый writer
                                          invoke_in_main_thread(callback) ──▶ заменяет "[[thinking...]]"
                                                                              на финальный ответ
                                                                              сбрасывает pending
                                                                              restart_interaction()
```

## 1. Main thread — подготовка хода

Файл: `novel/game/aside.rpy`.

1. `_vne_aside_send_current_message(character_id, save_slot)` — screen action на `input`
   (Enter) и на кнопке Send. Читает `renpy.get_screen_variable("message_text", screen="aside_chat_log")`,
   очищает поле через `renpy.set_screen_variable(...)`.
2. `_vne_aside_send_message(character_id, save_slot, msg)` — добавляет `You: ...` в
   `store.aside_chat_history` (через **reassignment**, не `.append()` — см. §5), проверяет
   `aside_llm_pending` (guard от повторной отправки), затем:
   - строит detached snapshot: `_vne_build_aside_turn_snapshot(character_id, msg, save_slot)`;
   - валидирует его: `_vne_assert_plain_worker_payload(snapshot)`;
   - при ошибке валидации — worker **не запускается**, `pending=False`, видимая
     `[LLM ERROR] Cannot prepare worker payload: ...` строка, `restart_interaction()`;
   - при успехе — `pending=True`, добавляет `"[[thinking...]]"`, вызывает
     `renpy.invoke_in_thread(_vne_aside_worker, snapshot)`.
3. `_vne_build_aside_turn_snapshot(character_id, player_message, save_slot)` — единственное
   место, где строится snapshot. Явно проверяет
   `threading.current_thread() is threading.main_thread()` (`RuntimeError` иначе). Читает:
   - `store.vne_aside_config_provider/base_url/model`;
   - `config.developer` → `diagnostics_enabled` (plain `bool`);
   - `_vne_aside_trace_path_main_thread()` → `trace_path` (plain `str`);
   - `_vne_aside_memory_root()` → `memory_root` (plain `str`);
   - `store.v2_flags/v2_completed_scenes/v2_levels/v2_relationships` — **только чтение**,
     через `sorted(...)`/`dict(...)`/рекурсивный detach-копир — исходные объекты не мутируются.
4. `_vne_detach_plain_worker_value(value, path)` — рекурсивно копирует
   `dict`/`list`/`tuple`/`str`/`int`/`float`/`bool`/`None` в новые built-in контейнеры;
   отклоняет (`TypeError`) всё остальное (в т.ч. Ren'Py revertable-контейнеры).
5. `_vne_assert_plain_worker_payload(value, path)` — независимый рекурсивный валидатор
   того же контракта типов, вызывается дважды: в конце построения snapshot и
   непосредственно перед `invoke_in_thread`.

## 2. Worker thread

```python
def _vne_aside_worker(snapshot):
    character_id = snapshot["character_id"]
    msg = snapshot["player_message"]
    diagnostics_enabled = snapshot["diagnostics_enabled"]
    ...
    turn = _vne_run_aside_turn_from_snapshot(snapshot)   # provider call
    ...
    renpy.invoke_in_main_thread(_vne_aside_finish_reply, character_id, msg, reply)
```

- Единственный источник данных — `snapshot[...]`. Нет `import store`, нет `renpy.config`,
  нет `renpy.get_screen_variable`/`set_screen_variable`.
- `_vne_run_aside_turn_from_snapshot(snapshot)` — worker-safe версия построения хода:
  берёт `memory_root`/`canon`/`provider`/`base_url`/`model` из snapshot, вызывает
  `aside_memory_store.load_memory`/`append_session`, `aside_context_builder.build_context`,
  `llm_provider.complete`. Ни один из этих трёх модулей (`tools/aside_context_builder.py`,
  `tools/aside_memory_store.py`, `tools/llm_provider.py`) не импортирует `renpy`.
- Ошибка провайдера перехватывается локально: `reply = "[LLM ERROR] " + str(exc)`. Игра не
  падает.
- Диагностика (если `diagnostics_enabled`): `_vne_aside_worker_trace(snapshot, event, **fields)`
  → `_vne_aside_trace_write_at_path(snapshot.get("trace_path"), event, payload)`. Путь к
  файлу пришёл из snapshot, **не** резолвится на воркер-потоке.

## 3. Main-thread callback

`_vne_aside_finish_reply(character_id, msg, reply)`, вызывается **только** через
`renpy.invoke_in_main_thread(...)` из воркера:

- убирает **одно, самое последнее** совпадение `"<Character>: [[thinking...]]"` (поиск с
  конца списка, не `while ... remove`, чтобы не задеть маркеры других ходов);
- гарантирует наличие строки `You: <msg>` (реконструирует, если main-thread-мутация не
  выжила из-за restart interaction);
- `store.aside_llm_pending = False`;
- добавляет финальную строку `"<Character>: <reply>"`;
- **всё через reassignment** (`store.aside_chat_history = history`, не `.append()`);
- `renpy.restart_interaction()`.

## 4. Provider routing (`tools/llm_provider.py`, commit `8ca63fb`)

```text
complete(messages, *, provider, model=None, system=None, params=None) -> str
├── provider == "mock"  → _complete_mock   (детерминированный, offline, sha256-digest)
├── provider == "local" → _complete_local  → _post_json(..., timeout_s=<из params, default 30.0>)
└── provider == "cloud" → _complete_cloud  → _post_json(..., timeout_s не передаётся → default 30.0)
```

- `_post_json` — типизированная, keyword-only сигнатура:

  ```python
  def _post_json(
      url: str,
      payload: dict[str, Any],
      *,
      headers: dict[str, str],
      timeout_s: float = 30.0,
  ) -> dict[str, Any]:
  ```

- Local: `aside.rpy` передаёт `params={"base_url": ..., "timeout_s": 120}` — реальный HTTP
  `timeout` у `urllib.request.urlopen` равен **120 секунд**.
- Cloud/default: **30 секунд** (не изменялось).
- **Нет automatic local→mock fallback.** Если `provider == "local"` и запрос падает —
  ошибка пробрасывается как `LLMProviderError`, воркер превращает её в
  `[LLM ERROR] <текст>`. Mock используется **только** при явном выборе `provider="mock"`
  (кнопка Provider в дев-оверлее).
- `timeout_s` исключается из JSON payload, отправляемого в Ollama (`if key not in ("base_url", "timeout_s")`).

## 5. Рендер истории

`screen aside_chat_log`, история — прямой `vbox` (не `viewport`):

```renpy
$ _aside_visible_history = list(aside_chat_history[-10:])

vbox:
    xfill True
    spacing 6

    for line in _aside_visible_history:
        text line:
            substitute False
            color "#d8d8e8"
            xmaximum 740
```

- **Рендерятся только последние 10 записей** (`[-10:]`) — это ограничение отображения,
  не хранения: `store.aside_chat_history` не срезается и не усекается этим кодом.
- **`substitute False` обязателен.** Без него строка вида `"Kira: [LLM ERROR] connection
  timed out"` интерпретируется Ren'Py как substitution-выражение (квадратные скобки),
  что приводит к `SyntaxError` во время рендера. См. постмортем, пункты 5–6.
- История помещена в `frame` с `ysize 360` (не `ymaximum 360` — см. постмортем, пункт про
  layout).
- Message-row и action-row (Send/Reset/Close/Provider) — **отдельные `frame`-блоки** с
  явными `xpos`/`ypos`/`xsize`/`ysize`, размещённые внутри 800×600 canvas (Ren'Py default
  resolution — в проекте нет `gui.rpy`/`config.screen_width`).

## 6. Observability (dev-only)

- `_vne_aside_trace_path_main_thread()` — читает `renpy.config.savedir`; вызывается
  **только** из главного потока (`_vne_aside_trace`, `_vne_build_aside_turn_snapshot`).
- `_vne_aside_trace_write_at_path(trace_path, event, payload)` — чистый файловый writer;
  не читает `renpy.config`/`store`/screen variables; безопасен в любом потоке; при
  невалидном `trace_path` — тихий `return`, без обращения к Ren'Py.
- `_vne_aside_trace(event, **fields)` — main-thread обёртка, добавляет контекст из `store`
  (`provider`, `pending`, `history_len`, `history_last`) перед записью. Никогда не
  вызывается из воркера.
- `_vne_aside_worker_trace(snapshot, event, **fields)` — worker-safe обёртка, берёт
  `trace_path` из snapshot.
- Файл: `aside_internal_trace.jsonl` в `renpy.config.savedir` (вне репозитория, вне Git).
- Чувствительные поля (`msg`, `reply_preview`, `history_last`, `error`) редактируются до
  длины (`"<redacted:N chars>"`) — сырой текст не пишется.
- Активна только при `config.developer == True`.
- Сбой записи (`try/except Exception: pass`) никогда не влияет на provider result или
  диспетчеризацию callback.

## 7. Reset и Close

- `_vne_reset_aside_memory(character_id, save_slot)` — screen action на кнопке
  "Reset Aside". Сбрасывает **только** изолированную Aside-память
  (`tools/aside_memory_store.reset_memory`) и UI-состояние
  (`aside_chat_history`, `aside_input_text`, `aside_llm_pending`). Не трогает `v2_*`.
- `Close` — `Return("__close__")`, обрабатывается в `label aside_chat_loop`.
- `label aside_dev_entry`/`label aside_quick` — **намеренно** обнуляют
  `aside_chat_history` при каждом входе в Aside (UI session log начинается заново);
  персистентная память (файлы через `aside_memory_store`) от этого не зависит.

## 8. Read-only canon invariant

`v2_flags`, `v2_completed_scenes`, `v2_levels`, `v2_relationships` читаются **только** в
`_vne_build_aside_turn_snapshot` (главный поток), только через copy-семантику
(`sorted(list(...))`, `dict(...)`, рекурсивный detach). Ни одного присваивания или
мутирующего вызова (`.add`/`.remove`/`.update`/`[...] =`) для этих переменных в
`aside.rpy` нет — подтверждено grep-проверкой при каждой независимой QA-итерации.
