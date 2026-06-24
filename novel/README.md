# VNE RenPy MVP Runbook

## Что это

Минимальный играбельный прототип (MVP) визуальной новеллы на движке RenPy,
собранный из контентного ядра VNE. Проект живёт в `novel/`, данные — в
`scenarios/`. Exporter и smoke-check находятся в `tools/` и `scripts/python/`.

## Текущий статус

- Первая играбельная сцена работает: SC_003 «Тихий охотник» (gym night)
- Preview exporter: монолитные JSON SC_003–013 → `.rpy`, 11/11 PASS
- Quality gate `renpy_exporter` подключён к `tools/vne_adapter.py gates`
- Stable baseline: `f4e808f7483d7a5519694dc1ffc6f8eca1f7231f`

## Как запустить RenPy MVP

```powershell
& "C:/DEV/Narrative/renpy-8.5.3-sdk/renpy.exe" "C:/DEV/Narrative/voyage-narrative-engine/novel"
```

Движок найдёт `game/` внутри `novel/` и запустит `script.rpy`.
Для выхода используй диалог подтверждения (экран `yesno_prompt`).

Текущие playable-файлы (не изменять без отдельного RN-задания):

```
novel/game/definitions.rpy
novel/game/options.rpy
novel/game/script.rpy
novel/game/screens.rpy
```

## Как проверить exporter

Экспорт одного сценария в `.rpy` preview:

```powershell
C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe `
  tools/vne_to_renpy/exporter.py `
  scenarios/SCENARIO_003_GYM_NIGHT.json `
  --output reports/renpy/SC_003.rpy
```

Ключевые файлы экспортера:

```
tools/vne_to_renpy/exporter.py
scripts/python/check_renpy_exporter.py
```

Поддерживаются только монолитные сценарии с `choice_points` (SC_003–013).
Модульный формат (`sauna_extended/`, `.md`-сцены) не поддерживается.

## Как запустить smoke-check

Проверяет SC_003–013: 11 сценариев, все условия (narrator define, LF, UTF-8,
локаль, отсутствие прямой речи персонажей вместо prose).

```powershell
C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe `
  scripts/python/check_renpy_exporter.py
```

Ожидаемый результат: `Summary: 11 passed, 0 failed`

## Как запустить gates

Все gate-группы:

```powershell
C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe tools/vne_adapter.py gates
```

Только RenPy gate:

```powershell
C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe tools/vne_adapter.py gates --gate renpy_exporter
```

Dry-run (без выполнения):

```powershell
C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe tools/vne_adapter.py gates --dry-run
```

Текущие gate-группы (порядок выполнения):

```
runtime
prompt
schema
retrospective
persona_audit
renpy_exporter
```

## Что нельзя коммитить

Следующие файлы gitignored и должны оставаться вне VCS:

```
reports/renpy/          # preview .rpy, генерируются exporter-ом
novel/game/cache/       # RenPy bytecode cache
novel/game/saves/       # сохранения игрока
novel/game/*.rpyc       # скомпилированные .rpy
novel/log.txt
novel/traceback.txt
novel/errors.txt
.voyage/tasks.db        # Framework runtime state
```

## Текущий stable baseline

```
f4e808f7483d7a5519694dc1ffc6f8eca1f7231f  feat(gates): add renpy_exporter quality gate
4faf1eb  test(renpy): add exporter smoke check script
0d1eed5  fix(renpy): harden scenario preview exporter output
dad68c4  feat(renpy): add monolithic scenario preview exporter
7b41b58  fix(renpy): add minimal quit confirmation screen
6539b79  feat(renpy): add minimal gym night playable scene
```

## Следующие возможные шаги

- **RN-3**: написать authored-диалоги для SC_003 вместо prose-заглушек
- **RN-EXT**: поддержка multi-CP сценариев и модульного формата в exporter
- **RN-GATE**: дополнительная проверка RenPy `.rpy` синтаксиса в gate
