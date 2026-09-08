# EVOLUTION OPERATOR FLOW V1

Реализован поверх `EVOLUTION CANDIDATE V1` (база `1f5ab7b40cb068d565763e2cfbc6a60715c333dd`).

## Поведение

В Character Lab React, в режиме `local`, раздел «Состояние» содержит очередь
предложений. Оператор может вручную сохранить предложение, увидеть его причину,
ID событий-оснований, уверенность и темп, затем указать своё имя/ID и одобрить либо
отклонить предложение. Есть фильтры ожидающих, одобренных, отклонённых и всех
предложений. После решения перечитываются очередь и Runtime State.

Поддерживаются `RELATIONSHIP` / `PSYCHOLOGY`, `SET` / `ADJUST`.
`AUTHOR_ONLY` можно рассматривать и отклонять, но нельзя применять.
`FAST` / `MEDIUM` / `SLOW` — метаданные, без таймеров и автоматического применения.
Основания задаются явно; V1 проверяет непустые уникальные ID, но не извлекает,
не загружает и не подтверждает содержимое этих событий.

## Хранение и атомарность

`EvolutionCandidateStore` добавляет две таблицы в существующий файл
`<workspace>/runtime_state.sqlite3`: `evolution_candidates` и `evolution_decisions`.
Таблицы создаются лениво через `CREATE TABLE IF NOT EXISTS`; существующие события
не мигрируются. Память, сцены и Accepted Package не изменяются.

Предложение хранится как неизменяемый JSON payload. Решение добавляется один раз;
первичный ключ `(subject_id, candidate_id)` исключает повторное решение.
Статус выводится из решения. Решение сохраняет оператора, комментарий, время и ID
созданного события Runtime State (для REJECT — null).

Approve работает в `BEGIN IMMEDIATE` на соединении `RuntimeStateBackend`:
проверка PENDING → существующий workflow → `record_set` / `record_adjust` →
запись решения → единый commit. Вложенные записи используют savepoint.
Сбой на любом шаге откатывает событие и решение; предложение остаётся PENDING.
Конкурирующие решения сериализуются; повторное решение получает конфликт.
ADJUST читает актуальное значение внутри транзакции, без предварительного расчёта
и без обрезания результата по границам. Нет инициализации ключа — нет ADJUST.

Исходный `EvolutionCandidateWorkflow` остаётся доступным как helper в памяти.
Lab использует durable store, который переиспользует его правила проверки и решения.
Это не второй набор правил эволюции.

## HTTP

Локальное расширение Character Lab; протокол Character Core не расширен.

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/workspaces/{workspaceId}/evolution/candidates` | Все кандидаты, решения и ссылки на события |
| POST | `/api/evolution/candidates` | Ручное создание PENDING |
| POST | `/api/evolution/candidates/decision` | Явное APPROVE / REJECT |

Создание: `workspaceId`, `domain`, `key`, `operation`, `reason`, `basisEventIds`,
`confidence`, `timescale`, `proposedValue` для SET либо `proposedDelta` для ADJUST.
ID и время кандидата задаёт backend. Решение: `workspaceId`, `candidateId`,
`decision`, `decidedBy`, необязательный `reason`. Неизвестные поля отклоняются.
Ответы кандидатов используют имена полей доменной модели в snake_case;
`decision` содержит сохранённые данные решения, `state_event_id` связывает его
с журналом. GET возвращает `{ "candidates": [...] }`.

Ошибки: 400 — неверный ввод / запрещённый кандидат, 404 — неизвестная рабочая
область или кандидат в её пределах, 409 — повторное решение или конфликт с
текущим Runtime State. Ошибка хранения — 500 с существующим общим сообщением.

Сервер сохраняет существующий loopback-only режим. `decidedBy` — явная атрибуция
оператора, не новая система аутентификации. Mock-клиент не имитирует durable flow;
панель доступна в local-режиме.

## Проверка

Из корня репозитория:

```powershell
py -m pytest tests/character_runtime/test_evolution_candidate.py tests/character_runtime/test_evolution_store.py tests/character_runtime/test_runtime_state.py tests/character_lab/test_evolution_operator.py tests/character_lab/test_runtime_state_lab.py tests/character_lab/test_rel_psy_evolution.py tests/character_lab/test_react_transport.py tests/character_lab/test_character_service_adapter.py -q
```

Из `apps/character_lab_react`: `npm run check`, `npm run build`.
Focused tests проверяют повторное открытие DB, перезапуск HTTP-сервера, сохранение
атрибуции и provenance, отсутствие мутации на create/reject, конфликт повторного
решения, конкурентные approvals, rollback при сбое записи решения, live ADJUST,
неверный ввод, AUTHOR_ONLY и изоляцию workspace/subject. В новых HTTP-тестах
provider factory запрещена assertion-ом.

Для ручного прогона: запустить существующий React HTTP-сервер и
`npm run dev:local`; открыть «Состояние» → «Добавить предложение вручную»;
создать SET для `PSYCHOLOGY/stress`, указать основания и уверенность; ввести
оператора; одобрить и проверить значение; новое предложение отклонить и проверить,
что значение сохранилось. Перезапустить сервер и выбрать ту же рабочую область:
кандидаты и решения должны сохраниться.

LLM proposer, вызовы внешних провайдеров, auto-approval, confidence auto-apply и
автоматическое создание из диалога не добавлены.
