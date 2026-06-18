# HANDOFF_R7: ANDREY_SENIOR_MODULE_v1.2 → personas/andrey_senior/

## Результат
- Модульная структура создана: `personas/andrey_senior/` (12 подпапок, 35+ JSON-файлов).
- Версия модуля: `2.0.0` (major bump после R7).
- Источник: `personas/ANDREY_SENIOR_MODULE_v1.2.json`.

## Маппинг блоков
| Блок монолита | Модуль(и) |
|---------------|-----------|
| Б0 Identity | `core/IDENTITY.json` |
| Б1 Levels (speech_profile + dynamic_visuals + vscno + internal_state + ad) | `levels/U1-A.json` … `levels/U7-B.json` |
| Б2 Psychology | `psychology/BASE.json`, `ATTACHMENT.json`, `AROUSAL.json`, `PLASTICITY.json`, `TEC.json` |
| Б3 Sexology | `sexology/RESPONSE_CYCLE.json`, `EROTIC_SCRIPTS.json`, `DYSPHORIA_AND_SHAME.json`, `FANTASY_VS_REALITY.json` |
| Б4 Visual | `visual/PROMPT_BASE.json`, `GENERATION_HISTORY.json` |
| Б5 Dynamics | `dynamics/REACTION_PATTERNS.json`, `LEVEL_LOCK_MATRIX.json`, `EMOTIONAL_INFLUENCE_MATRIX.json`, `CONFLICT_RESOLUTION_MATRIX.json` |
| Б6 Memory | `memory/TRUST.json`, `ATTRACTION.json`, `FLAGS.json`, `HISTORY.json`, `EMOTIONAL_ANCHORS.json` |
| Б7 Relationships | `relationships/MATRIX.json` |
| Б8 Environment | `environment/STATE_TRIGGERS.json`, `environment/SPATIAL_BEHAVIOR.json` (stub) |
| Safety | `safety/PROTOCOL.json` |
| Autonomous | `autonomous/ACTIVITIES.json`, `autonomous/TEMPLATES.json` |
| Meta | `meta/META.json` |

## Известные проблемы / `[NEEDS_DATA]`
1. `environment/SPATIAL_BEHAVIOR.json` — создан как stub; проксемика не была явно задана в v1.2.
2. VSCNO-профиль в v1.2 заявлен как `anxious-preoccupied`, но `СТ` на У1–У3 низкий (2–3 вместо ожидаемых 3–4). Передано R8 Auditor для регистрации.
3. `visual/GENERATION_HISTORY.json` пуст — заполняется после генераций.

## Следующий шаг
Запустить **R8 Auditor**: валидация против `schemas/persona_schema_v3_2_VOYAGE.json` и оригинального монолита.
