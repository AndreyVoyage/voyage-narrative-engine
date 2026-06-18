# ASSEMBLY: Андрей (andrey_junior_module_v2.1)

## Всегда загружать
- core/IDENTITY.json
- psychology/BASE.json
- safety/PROTOCOL.json

## По current_level
- levels/{current_level}.json
- visual/LIGHTING_MAP.json#/level_{current_level}

## Если другие персонажи в сцене
- relationships/MATRIX.json

## Если сценарий эротический/романтический
- sexology/RESPONSE_CYCLE.json
- sexology/EROTIC_SCRIPTS.json

## Приоритеты
- Состояние > Сценарий > Уровень > Специализированные > Базовые > Идентичность

## Runtime
- memory/TRUST.json + state updates
- memory/ATTRACTION.json + state updates
- memory/HISTORY.json — контекст прошлых сессий
- memory/FLAGS.json — что уже произошло
- memory/EMOTIONAL_ANCHORS.json — якоря
- autonomous/ACTIVITIES.json (runtime)
- autonomous/TEMPLATES.json (runtime)
- meta/META.json — версии, источник, changes

---
*Сгенерировано автоматически по R7 Refactor*
