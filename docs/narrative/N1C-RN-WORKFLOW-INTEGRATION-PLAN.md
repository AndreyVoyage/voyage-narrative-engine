# N1C — План интеграции команд Schema V2 в `tools/rn_workflow.py`

> **ID:** N1C-RN-WORKFLOW-INTEGRATION-PLAN
> **Статус:** план (read-only; implementation не выполняется)
> **Дата:** 2026-06-27
> **База:** `main` @ `e87af3983f2ea6585ac8912304b181f536365dae`
> **Язык:** русский (технический документ)
> **Запреты N1C:** не трогать `vne_adapter.py`, существующие сценарии, RenPy-файлы, `.voyage`; не менять поведение `validate`; не делать V2 lint-предупреждения ошибками.

---

## 1. Контекст

После слияния N1B в `main` доступен самостоятельный валидатор Schema V2:

```bash
py tools/narrative_schema_v2.py schema-check schemas/scenario_schema_v2.json
py tools/narrative_schema_v2.py validate scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json
py tools/narrative_schema_v2.py flag-lint scenarios
```

`tools/rn_workflow.py` — единый workflow-чекер RenPy/VNE. Чтобы операторы и автоматизация могли вызывать V2-проверки из привычной точки входа, планируется добавить три thin-wrapper команды в `rn_workflow.py`, не изменяя существующих команд.

---

## 2. Scope

Только `tools/rn_workflow.py`.

Добавляемые артефакты:
- три новые CLI-команды;
- вспомогательные функции для разрешения пути V2-файла и запуска подпроцесса;
- обновление docstring/usage в шапке файла.

Не добавляем:
- новые роли, треки, задачи в `.voyage`;
- изменения `tools/narrative_schema_v2.py`;
- изменения JSON-схемы или сценариев;
- интеграцию V2 в `cmd_validate` / `cmd_baseline-report` по умолчанию.

---

## 3. Предлагаемые команды

### 3.1 `schema-check-v2`

```bash
py tools/rn_workflow.py schema-check-v2
py tools/rn_workflow.py schema-check-v2 schemas/scenario_schema_v2.json
```

- Без аргумента использует `schemas/scenario_schema_v2.json`.
- Обёртывает `tools/narrative_schema_v2.py schema-check <schema_file>`.
- Exit code: `0` при PASS, `1` при FAIL.
- Вывод: заголовок `=== RN SCHEMA CHECK V2 ===`, путь к схеме, stdout/stderr валидатора.

### 3.2 `validate-v2`

```bash
py tools/rn_workflow.py validate-v2 SC_017
py tools/rn_workflow.py validate-v2 scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json
```

- Аргумент `<scene>` может быть:
  - идентификатором сцены (`SC_017`, `017`, `sc_017`) — резолвится в первый подходящий файл `scenarios/SCENARIO_017_*.v2.json`;
  - прямым путём к `.v2.json`.
- Если файл не найден — `FAIL` с пояснением.
- Обёртывает `tools/narrative_schema_v2.py validate <scene_file>`.
- Exit code: `0` при PASS, `1` при FAIL.
- Вывод: заголовок `=== RN VALIDATE V2: SC_017 ===`, resolved path, stdout/stderr валидатора.

### 3.3 `flag-lint-v2`

```bash
py tools/rn_workflow.py flag-lint-v2
py tools/rn_workflow.py flag-lint-v2 scenarios
```

- Без аргумента использует `scenarios`.
- Обёртывает `tools/narrative_schema_v2.py flag-lint <scenario_dir>`.
- **Предупреждения не превращаются в ошибки.** Exit code `0` сохраняется, если валидатор вернул `0`.
- Вывод: заголовок `=== RN FLAG LINT V2 ===`, directory, stdout/stderr валидатора.
- Известное pre-existing поведение: `flag-lint` сообщает о 292 флагах, которые выставляются, но нигде не требуются. Это ожидаемый WARN, не FAIL.

---

## 4. Реализационный подход

### 4.1 Запуск валидатора

Использовать `subprocess.run` с `sys.executable`, чтобы гарантировать тот же интерпретатор и не зависеть от `py`-лаунчера внутри Python-процесса:

```python
result = subprocess.run(
    [sys.executable, "tools/narrative_schema_v2.py", *argv],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
```

Stdout/stderr валидатора передаются в stdout `rn_workflow.py` (или печатаются построчно с отступом). Exit code возвращается как есть.

### 4.2 Разрешение пути сцены

```python
def _resolve_v2_scene_path(scene_arg: str) -> Path | None:
    if scene_arg.endswith(".json"):
        p = Path(scene_arg)
        return p if p.exists() else None
    scene_num = _parse_scene_num(scene_arg)
    if scene_num is None:
        return None
    matches = sorted(SCENARIOS_DIR.glob(f"SCENARIO_{scene_num:03d}_*.v2.json"))
    return matches[0] if matches else None
```

### 4.3 Структура изменений в `rn_workflow.py`

1. Импорт `sys` уже есть; дополнительных зависимостей не требуется.
2. Добавить константу `SCHEMA_V2_DEFAULT = Path("schemas/scenario_schema_v2.json")`.
3. Добавить три `cmd_*` функции после существующих команд.
4. Добавить три `sub.add_parser(...)` в `main()` и связать их с диспетчером `dispatch`.
5. Обновить module docstring / usage в шапке файла.

### 4.3 Взаимодействие с `cmd_validate`

`cmd_validate` остаётся без изменений. В будущем (за рамками N1C) можно добавить опциональный флаг `--with-v2`, но сейчас это не делается, чтобы не нарушить constraint «do not change existing validate behavior».

---

## 5. Тестовая стратегия

Перед слиянием N1C необходимо прогнать:

```bash
# 1. Новые команды
py tools/rn_workflow.py schema-check-v2
py tools/rn_workflow.py validate-v2 SC_017
py tools/rn_workflow.py validate-v2 scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json
py tools/rn_workflow.py flag-lint-v2

# 2. Регрессия существующих команд
py tools/rn_workflow.py status
py tools/rn_workflow.py validate
py tools/rn_workflow.py validate --allow-feature-branch
py tools/rn_workflow.py baseline-report
py tools/rn_workflow.py audit-source SC_017
py tools/rn_workflow.py validate-patch SC_017 --allow-dirty-script
py tools/rn_workflow.py ready-for-gui SC_017 --allow-dirty-script
```

Критерии:
- Все новые команды возвращают `0` на ожидаемых данных.
- `validate-v2 SC_017` PASS.
- `flag-lint-v2` возвращает `0` и печатает WARN о 292 флагах.
- `validate`/`baseline-report`/`audit-source`/`validate-patch`/`ready-for-gui` ведут себя идентично N1B.
- Рабочее дерево после прогона (кроме gitignored `reports/renpy/`) не изменяется.

---

## 6. Acceptance criteria

1. `py tools/rn_workflow.py schema-check-v2` PASS на `schemas/scenario_schema_v2.json`.
2. `py tools/rn_workflow.py validate-v2 SC_017` PASS на `scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json`.
3. `py tools/rn_workflow.py flag-lint-v2` завершается с `0` и не превращает предупреждения в ошибки.
4. Существующие команды `rn_workflow.py` не изменили поведение.
5. `tools/vne_adapter.py`, `scenarios/*.json`, `novel/game/script.rpy`, `.voyage/` не изменены.
6. Не добавлены внешние зависимости; оба инструмента остаются stdlib-only.

---

## 7. Риски и смягчение

| Риск | Влияние | Смягчение |
|------|---------|-----------|
| Подпроцессная обёртка усложняет парсинг вывода | низкое | Не парсим вывод; только проксируем stdout и exit code. |
| Имя V2-файла изменится (например, `SCENARIO_017.v2.json`) | низкое | Резолв по glob `SCENARIO_NNN_*.v2.json`; при необходимости обновить glob. |
| Оператор ожидает, что `flag-lint-v2` станет жёсткой проверкой | среднее | Документ и вывод явно говорят `WARN`; exit code `0`. |
| Регрессия `cmd_validate` при добавлении подпарсеров | низкое | Минимальные добавления в `dispatch`; прогон регрессии. |
| `sys.executable` на Windows указывает не на `py`, а на конкретный python.exe | низкое | Это корректно; `tools/narrative_schema_v2.py` stdlib-only и запускается любым Python 3. |

---

## 8. Зависимости и разблокировки

- **Blocked by:** N1B (schema v2, validator, SC_017 V2 sample в `main`).
- **Unlocks:** N2 (live JSON runtime), поскольку N1C даёт операторам удобный способ валидировать V2-источники перед их использованием в runtime.

---

## 9. Следующий шаг

Если план одобрен — запустить реализацию N1C: небольшой PR/ветка, изменяющая только `tools/rn_workflow.py`, с обязательным прогоном тестов из §5.
