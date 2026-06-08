# ASSEMBLY: Кира (KIRA_MODULE_v14)

> **КРАТКАЯ ВЕРСИЯ.** Полный алгоритм сборки, приоритеты конфликтов, примеры и спецификация ag_level — см. в `03_ASSEMBLY_GUIDE.md` (документ 03 из 09).

---

## Назначение
Инструкция для LLM и движка: как собрать полный контекст Киры из модульных JSON-файлов для конкретной сцены.

## Базовая сборка (всегда)
1. core/IDENTITY.json — кто она (возраст, внешность, anatomic_anchor)
2. psychology/BASE.json — почему она такая (травма, core_conflict, shame_layers)
3. safety/PROTOCOL.json — где границы (hard/soft limits, regression triggers)

## Уровневая сборка (по текущему уровню)
Если current_level = U3-A:
- levels/U3-A.json — speech_profile, dynamic_visuals, state_triggers, active_defenses, cognitive_distortions, ifs_part
- visual/LIGHTING_MAP.json — lighting для U3-A

## Физиологическая сборка (если есть физическая близость, ag_level >= 2)
- physiology/AROUSAL_SIGNATURES.json — как тело реагирует (пульс, дрожь, румянец)
- physiology/MICROEXPRESSIONS.json — мимика (Ekman)
- physiology/EROGENOUS_MAP.json — зоны возбуждения

## Сексологическая сборка (если сцена эротическая, ag_level >= 3 или scene_type = "erotic")
- sexology/RESPONSE_CYCLE.json — фазы возбуждения (Basson + Masters-Johnson)
- sexology/EROTIC_SCRIPTS.json — типичные сценарии фантазий (Gagnon & Simon)
- sexology/DYSPHORIA_AND_SHAME.json — как стыд мешает
- sexology/FANTASY_VS_REALITY.json — контраст фантазий и реальности

## Сценарийная сборка (по сценарию)
Если scenario = sauna_quartet:
- relationships/MATRIX.json — все 4 персонажа в сцене
- dynamics/RIVALRY_TRIANGLE.json — конкуренция Sergey vs Maksim
- environment/SENSORY_PROCESSING.json — запахи, звуки, текстуры сауны
- environment/SPATIAL_BEHAVIOR.json — проксемика в парилке (зоны личного пространства)

## Runtime сборка (из state)
- memory/TRUST.json + state updates
- memory/ATTRACTION.json + state updates
- memory/HISTORY.json — контекст прошлых сессий
- memory/FLAGS.json — что уже произошло (first_meeting, kissed, etc.)

## Мета-сборка (для литературной глубины, ag_level >= 2)
- meta/ATTRIBUTION_BIAS.json — как она интерпретирует действия других (враждебно или благосклонно)
- meta/UNRELIABLE_NARRATOR.json — когда она врёт себе (denial, rationalization, projection, selective_amnesia)
- meta/COHERENCE_VETO.json — форс-мажорные нарушения паттерна (опьянение, паническая атака)

## Правила сборки
1. **Никогда не смешивай уровни.** Если Кира на U3-A — только U3-A.json.
2. **VSCNO берётся из state, не из модуля.** Модуль — шаблон, state — текущее.
3. **Memory накладывается поверх.** Если в memory trust[user]=80, а в модуле 75 — используем 80.
4. **Если уровень неизвестен — default U1-A.**
5. **Если сценарий неизвестен — default environment.**
6. **Глубина сборки определяется ag_level.** ag=1 → базовая, ag=2 → +психология/физиология, ag=3 → +сексология. См. 03_ASSEMBLY_GUIDE.md, раздел 7.
7. **Safety > All.** Если safety/PROTOCOL.json говорит СТОП — всё остальное игнорируется, regression к U7-A.

## Пример полной сборки (U3-A, sauna_quartet, ag_level=2)
```
core/IDENTITY.json
psychology/BASE.json
psychology/AROUSAL.json
psychology/PLASTICITY.json
psychology/ODSC.json
psychology/ATTACHMENT.json
psychology/DEFENSE_MECHANISMS.json
psychology/IFS_PARTS.json
psychology/COGNITIVE_DISTORTIONS.json
levels/U3-A.json
relationships/MATRIX.json
physiology/AROUSAL_SIGNATURES.json
physiology/MICROEXPRESSIONS.json
sexology/RESPONSE_CYCLE.json
sexology/EROTIC_SCRIPTS.json
dynamics/RIVALRY_TRIANGLE.json
environment/SENSORY_PROCESSING.json
environment/SPATIAL_BEHAVIOR.json
meta/UNRELIABLE_NARRATOR.json
meta/ATTRIBUTION_BIAS.json
visual/PROMPT_BASE.json
visual/LIGHTING_MAP.json
safety/PROTOCOL.json
memory/TRUST.json (runtime)
memory/ATTRACTION.json (runtime)
memory/HISTORY.json (runtime)
memory/FLAGS.json (runtime)
```

---

*Документ 09 из 09. Краткая версия. Полный алгоритм см. в 03_ASSEMBLY_GUIDE.md*
