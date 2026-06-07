# Voyage Narrative Engine v2.0

AI-Native интерактивная narrative-система с психологически проработанными персонажами.

## Структура

| Папка | Содержимое |
|-------|-----------|
| `core/` | VOYAGE_NARRATIVE_CORE_v2.md — мнемоники, ФМДР, АД, ВСНО |
| `governance/` | AUTONOMY_GOVERNOR_v2.md — AG levels, Safety Checks, Audit Log |
| `visual/` | QWEN_ADAPTER_v2.md — Lighting Map, anatomic anchors, промпты |
| `knowledge/` | TEC_DICTIONARY.md, CROSS_PERSONA_RULES.md, persona_schema_v3.2.json |
| `personas/` | JSON-модули: Кира (v14), Сергей (v4), Максим (v2), Марина (v2) |
| `scenarios/` | SCENARIO_SAUNA_QUARTET.json — сауна вчетвером, 5 фаз |
| `state/` | STATE_TEMPLATE_v2.json — глобальное состояние сессии |
| `roles/` | Промпты для ролей: Persona Analyst, Visual Anatomist |
| `scripts/` | build_prompt.sh, update_state.sh — автоматизация |
| `docs/` | VOYAGE_QUICK_START.md, TEST_PROMPT.md |

## Быстрый старт

```bash
# Собрать PROMPT.txt для сессии
./scripts/build_prompt.sh sauna_quartet kira sergey marina

# Загрузить PROMPT.txt в Kimi/DeepSeek → играть

# После сессии обновить STATE
./scripts/update_state.sh session_notes.txt
```

## Тестирование

См. `docs/TEST_PROMPT.md` — 10 тестов для проверки корректности работы.

## Версия

v2.0.0 | 2026-06-07 | Тесты пройдены ✅
