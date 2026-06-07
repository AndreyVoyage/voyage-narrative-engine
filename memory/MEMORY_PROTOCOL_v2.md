# MEMORY PROTOCOL v2.0

> **Назначение:** Память сессий, суммаризация, символизация и proactive events для Voyage Engine v2.0.

---

## EVENT LOG (JSON)

```json
{
  "events": [
    {
      "id": "EV_001",
      "timestamp": "2026-06-07T20:15:00Z",
      "scene": "gym_stretching",
      "characters": ["К", "С", "Я"],
      "kira_level": "U2-A",
      "kira_sublevel": "A",
      "kira_mode": "shy_to_bitch",
      "sergey_level": "S2",
      "sergey_role": "catalyst",
      "flags_set": ["kira_first_unconscious_smile"],
      "flags_unset": [],
      "emotional_anchor": "ты мой финиш",
      "summary": "Сергей смотрел в зеркало на К. К поправила волосы, не заметив. Улыбнулась. Сергей записал это. Пользователь видел всё.",
      "fmdr_excerpt": "(Я просто... улыбнулась. Потому что вспомнила. Не из-за вас. Ну, может, чуть-чуть из-за вас. *смеётся* Забудьте.)",
      "proactive": false,
      "told_to_user": true
    }
  ]
}
```

---

## СУММАРИЗАЦИЯ

Когда Event Log > 20 событий:
1. AI генерирует `SUMMARY.md` (3-5 абзацев ключевых моментов).
2. Event Log архивируется в `EVENT_LOG_ARCHIVE.json`.
3. Новый Event Log начинается с `flags` и `memory` из summary.

### Формат SUMMARY.md

```markdown
# Сессия [date] — [kira_mode] — [highest_sublevel_reached]

## Ключевые моменты
- [3-5 абзацев с эмоциональными якорями]

## Флаги (активные)
- [список активных флагов]

## Травматические триггеры (сработавшие)
- [список]

## Регрессии (если были)
- [from → to, trigger]

## Символ-код
S[last_id]:[mode]:[highest_sublevel]:[chars]:[last_location]:[last_action]:[result]
```

---

## СИМВОЛИЗАЦИЯ v2.0

Каждая сцена кодируется:
```
S[id]:[mode]:[from_sublevel]→[to_sublevel]:[chars]:[location]:[action]:[result]
```

Примеры:
```
S001:shy:U1-A→U1-B:K+Y:gym:first_blush:gaze_3sec
S012:shy:U2-A→U2-B:K+S+Y:bar:first_provocation:unconscious
S024:shy:U2-B→U3-A:K+S+Y:bar:shock_named:sergey_catalyst_gaze
S038:shy:U3-A→U3-A:K+Y:home:shower_cry:user_found
S045:shy:U3-A→U3-B:K+Y:home:admission_alone:text_sent
S056:shy:U3-B→U4-A:K+S+Y:gym:unstopped_touch:waist
S067:shy:U4-A→U4-B:K+Y:home:ritual_goodbye:safety_confirmed
S078:shy:U4-B→U5-A:K+S+Y:bar:bitch_mask:tested
S089:shy:U5-A→U5-B:K+Y:club:bitch_true:internalized
S090:shy:U5-B→U6-A:K+Y:hotel:command:absolute
S091:shy:U6-A→U6-B:K+Y:hotel:overload:logic_break
S092:shy:U6-B→U7-A:K+Y:home:repentance:unexpected_care
S093:shy:U7-A→U7-B:K+Y:home:integration:morning_after
```

---

## PROACTIVE EVENTS LOG

```json
{
  "proactive_events": [
    {
      "id": "PE_001",
      "timestamp": "2026-06-07T22:00:00Z",
      "trigger": "offline_30min",
      "character": "kira",
      "sublevel": "U1-A",
      "mode": "shy_to_bitch",
      "message": "Милый, я... я не знаю, зачем пишу. Просто... ты молчишь.",
      "told_to_user": false,
      "visual_generated": false
    }
  ]
}
```

---

## ПРОТОКОЛ USER_RETURNED

1. Загрузить `CORE` + `PERSONAS` + `STATE` + `PROACTIVE.events_log` (последние 1-3 events).
2. Кира рассказывает о произошедшем **естественно**, в формате ФМДР.
3. Не перечислять события списком — интегрировать в повествование.
4. Пометить рассказанные events как `told_to_user = true`.
5. Сбросить `proactive_count_since_last_session` в 0.
6. Обновить `user_activity.last_message_timestamp` и `offline_duration_minutes`.

---

## GIT WORKFLOW (Termux)

```bash
# После каждой сессии:
cd ~/voyage-narrative-engine
git add state/STATE.json memory/EVENT_LOG.json
git commit -m "Session [date]: [highest_sublevel] [flags_set]"
git push origin main
```

---

## ВЕРСИОНИРОВАНИЕ

- `CORE.md` — версионируется по semver (v2.0.0).
- `KIRA_MODULE.json` — v12.0.0.
- `SERGEY_MODULE.json` — v3.0.0.
- `STATE_TEMPLATE.json` — v2.0.0.
- `SCENARIO_SHY_BLOOM.json` — v1.0.0.
- `MEMORY_PROTOCOL.md` — v2.0.0.
