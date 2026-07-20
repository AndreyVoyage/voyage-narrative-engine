# N7 CANONICAL STATUS CLOSEOUT v1

> **Дата:** 2026-07-20
> **Вердикт:** CANONICAL CLOSEOUT
> **Назначение:** Фиксация канонического статуса N7 Persona Data Gateway
>   по состоянию на 2026-07-20. Этот документ фиксирует канонический статус N7
>   и связанных future-треков на указанную дату. Последующие изменения требуют
>   отдельной авторизации владельца и обновления канонической документации.

---

## 1. Завершённые треки (CLOSED / COMPLETE)

### P1a-S1 — Read-only domain core (только Kira, с тестами)

| Поле | Значение |
|------|----------|
| **Статус** | AUTHORIZED AND COMPLETE |
| **Commit** | `b5fb3640838ae8528bd0466681cb448465ba6997` |
| **Описание** | Read-only доменное ядро Persona Data Gateway: фасад над `personas/kira/` с программным API, provenance и юнит-тестами. Только одна персона (Kira). |

### P1b Option A — Multi-character expansion (все модульные персонажи)

| Поле | Значение |
|------|----------|
| **Статус** | AUTHORIZED AND COMPLETE |
| **Commit** | `863f339f015f56cc1bdec3813897e5fa44f0aee7` |
| **Описание** | Расширение Gateway на всех персонажей, поддержанных модульным persona registry на момент завершения P1b Option A. |

### Nika manifest compatibility correction

| Поле | Значение |
|------|----------|
| **Статус** | AUTHORIZED AND COMPLETE |
| **Commit** | `015f53126ba10f78f73414b1c9ed8376e179fa14` |
| **Описание** | Исправление совместимости INDEX.json манифеста для персонажа Nika после multi-character expansion. |

### N6 Character Aside integration (в origin/main)

| Поле | Значение |
|------|----------|
| **Статус** | CLOSED AND INTEGRATED |
| **Commit** | `afa7a13cec300b1c5917acf52c4d5300f8724d21` |
| **Описание** | N6 Character Aside — локальный read-only интерфейс общения с persona через LLM, с безопасной границей между фоновым worker и главным потоком Ren'Py. Интегрирован в origin/main. N6 commits: `8ca63fb` (configurable provider timeouts), `695c840` (thread-safe character aside), `afa7a13` (engineering documentation). |

---

## 2. Persona Gateway верификация

| Поле | Значение |
|------|----------|
| **Последний подтверждённый результат** | 138 tests PASS |
| **Статус зафиксирован в closeout** | 2026-07-20 |

Gateway использует модульные `personas/<id>/` с `INDEX.json` как allowlist.

---

## 3. Запланированные, но НЕ авторизованные треки

### P2 — MCP adapter

| Поле | Значение |
|------|----------|
| **Статус** | PLANNED, NOT AUTHORIZED |
| **Описание** | MCP stdio adapter для Cline/VS Code authoring: read-only tools, без write. MCP adapter — transport-only, не содержит persona business logic. |
| **Требуется** | Отдельная авторизация владельца. |

### P3 — RenPy adapter

| Поле | Значение |
|------|----------|
| **Статус** | NOT STARTED, NOT AUTHORIZED |
| **Описание** | Ren'Py adapter: Aside использует domain-API in-process (НЕ MCP). |
| **Требуется** | Отдельная авторизация владельца. |

### N8 — Persona Voice Model

| Поле | Значение |
|------|----------|
| **Статус** | FUTURE, NOT AUTHORIZED |
| **Описание** | Голосовая модель персонажа (canon voice assets + aside dynamic voice, VoiceProvider). |
| **Требуется** | Отдельная авторизация владельца. |

---

## 4. Важные примечания

- **Delegated prompts** (промпты, делегированные исполнителю) являются execution evidence — **не импортируются** в данный документ.
- **LOCAL_STORAGE reports** (отчёты о состоянии локального хранилища) являются execution evidence — **не импортируются** в данный документ.
- **Реализация P2, P3, N8** требует отдельной авторизации владельца. Настоящий документ не даёт разрешения на их имплементацию.
- **Канонический статус N7 P1 закрыт.** Дальнейшие изменения N7-домена (P2, P3, N8) должны проводиться через отдельные задачи с явной авторизацией владельца, с опорой на настоящий closeout-документ.

---

## 5. Ссылки

- **Preflight-документ:** `docs/narrative/N7_PERSONA_DATA_GATEWAY_PREFLIGHT_v1.md` — архитектурный preflight, выполнивший свою верификационную роль. **Superseded** настоящим closeout.
- **Roadmap:** `docs/narrative/NARRATIVE_ROADMAP.md` — текущий статус N7 зафиксирован в §10.
- **AGENTS.md:** `AGENTS.md` — источник правды, включает ссылку на настоящий документ (пункт 4d).

---

*Конец N7 CANONICAL STATUS CLOSEOUT v1.*
