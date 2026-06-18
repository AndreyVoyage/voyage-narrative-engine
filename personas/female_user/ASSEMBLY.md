# ASSEMBLY: Девушка (FEMALE_USER_MODULE → modular v2.0.0)

> Инструкция для LLM/движка: как собрать контекст пользователя из модульных JSON.

## Базовая сборка (всегда)
1. `core/IDENTITY.json` — кто пользователь (role, pace, risk_tolerance, language)
2. `psychology/BASE.json` — роль в треугольнике, мотивация, якорь Киры
3. `safety/PROTOCOL.json` — стоп-слова, emergency_response, cooldown_phrase
4. `environment/STATE_TRIGGERS.json` — триггерные слова героини

## Runtime сборка (из state)
- `memory/TRUST.json`, `memory/ATTRACTION.json`, `memory/FLAGS.json`, `memory/HISTORY.json`, `memory/EMOTIONAL_ANCHORS.json`
- `meta/META.json` — interaction, preferences

## Уровневая сборка
- Героиня не имеет собственных уровней; `levels/U1-A.json` … `U7-B.json` созданы как пустые шаблоны для совместимости со State Manager.

## Правила сборки
- Safety > All: стоп-слова вызывают `immediate_aftercare`.
- Триггеры из `environment/STATE_TRIGGERS.json` перехватываются до narrative-генерации.
- `meta/META.json` определяет формат, объём, тон, роль и предпочтения.
