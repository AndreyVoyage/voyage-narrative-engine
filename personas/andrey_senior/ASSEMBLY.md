# ASSEMBLY: Андрей Старший (ANDREY_SENIOR_MODULE_v1.2 → modular v2.0.0)

> **КРАТКАЯ ВЕРСИЯ.** Полный алгоритм сборки, приоритеты конфликтов и примеры — см. в `03_ASSEMBLY_GUIDE_v2.1.md` и `VOYAGE_ARCHITECTURE_SPEC_v1.0.md`.

---

## Назначение
Инструкция для LLM и движка: как собрать полный контекст Андрея Старшего из модульных JSON-файлов для конкретной сцены.

## Базовая сборка (всегда)
1. `core/IDENTITY.json` — кто он (возраст, внешность, archetype, anatomic_anchor)
2. `psychology/BASE.json` — почему он такой (травма, core_conflict, shame_layers)
3. `safety/PROTOCOL.json` — где границы (hard/soft limits, safety_check_points, ag_max)

## Уровневая сборка (по текущему уровню)
Если current_level = U2-A:
- `levels/U2-A.json` — speech_profile, dynamic_visuals, vscno, internal_state, ad_availability

## Психологическая сборка (ag_level >= 2)
- `psychology/ATTACHMENT.json` — attachment_sexuality (anxious-preoccupied)
- `psychology/AROUSAL.json` — responsive_desire, arousal_specificity
- `psychology/PLASTICITY.json` — erotic_plasticity (level 8, switch, 4 scripts)
- `psychology/TEC.json` — TEC_001–TEC_008

## Сексологическая сборка (ag_level >= 3 или scene_type = "erotic")
- `sexology/RESPONSE_CYCLE.json` — фазы возбуждения, pacing
- `sexology/EROTIC_SCRIPTS.json` — скрипты, archetypes, switch_context, bdsm_interest
- `sexology/DYSPHORIA_AND_SHAME.json` — слои стыда, receiving_preferences
- `sexology/FANTASY_VS_REALITY.json` — secret_desire vs ideal_ending

## Сценарийная / межперсонажная сборка
- `relationships/MATRIX.json` — Kira, Marina, Olga, Andrey Junior
- `dynamics/LEVEL_LOCK_MATRIX.json` — max/min/blocked уровни для пар
- `dynamics/EMOTIONAL_INFLUENCE_MATRIX.json` — влияние партнёров на internal_state
- `dynamics/CONFLICT_RESOLUTION_MATRIX.json` — паттерны разрешения конфликтов
- `dynamics/REACTION_PATTERNS.json` — реакции на ревность, плач, стервозность, игривость, уязвимость, требование выбора

## Runtime сборка (из state)
- `memory/TRUST.json` + state updates
- `memory/ATTRACTION.json` + state updates
- `memory/HISTORY.json` — контекст прошлых сессий
- `memory/FLAGS.json` — что уже произошло
- `memory/EMOTIONAL_ANCHORS.json` — якоря (count/intensity)

## Автономная сборка (proactive mode)
- `autonomous/ACTIVITIES.json` — вероятностные активности
- `autonomous/TEMPLATES.json` — шаблоны автономных сообщений

## Мета-сборка
- `meta/META.json` — версии, источник, changes, engagement, transition_state

## Правила сборки
1. **Никогда не смешивай уровни.** Только один файл из `levels/`.
2. **VSCNO берётся из state, не из модуля.** Модуль — шаблон, state — текущее.
3. **Memory накладывается поверх.** Если в state trust[kira]=90, а в модуле 85 — используем 90.
4. **Если уровень неизвестен — default U1-A.**
5. **Глубина сборки определяется ag_level.** ag=1 → базовая, ag=2 → +психология, ag=3 → +сексология.
6. **Safety > All.** Если safety/PROTOCOL.json говорит СТОП — всё остальное игнорируется, regression к U4-A.

## Пример полной сборки (U2-A, sauna_quartet, ag_level=2)
```
core/IDENTITY.json
psychology/BASE.json
psychology/ATTACHMENT.json
psychology/AROUSAL.json
psychology/PLASTICITY.json
psychology/TEC.json
levels/U2-A.json
relationships/MATRIX.json
dynamics/LEVEL_LOCK_MATRIX.json
dynamics/EMOTIONAL_INFLUENCE_MATRIX.json
dynamics/CONFLICT_RESOLUTION_MATRIX.json
dynamics/REACTION_PATTERNS.json
environment/STATE_TRIGGERS.json
sexology/RESPONSE_CYCLE.json
sexology/EROTIC_SCRIPTS.json
visual/PROMPT_BASE.json
visual/GENERATION_HISTORY.json
safety/PROTOCOL.json
memory/TRUST.json (runtime)
memory/ATTRACTION.json (runtime)
memory/HISTORY.json (runtime)
memory/FLAGS.json (runtime)
memory/EMOTIONAL_ANCHORS.json (runtime)
autonomous/ACTIVITIES.json (runtime)
autonomous/TEMPLATES.json (runtime)
meta/META.json
```

---
*Сгенерировано автоматически по R7 Refactor: ANDREY_SENIOR_MODULE_v1.2.json → модульная архитектура v2.0.0*
