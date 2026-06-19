#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R7 Refactor: ANDREY_SENIOR_MODULE_v1.2.json → personas/andrey_senior/"""

import json
import os
from pathlib import Path

ROOT = Path("c:/DEV/Narrative/voyage-narrative-engine")
SRC = ROOT / "personas" / "ANDREY_SENIOR_MODULE_v1.2.json"
DST = ROOT / "personas" / "andrey_senior"

SUBFOLDERS = [
    "core",
    "levels",
    "psychology",
    "sexology",
    "visual",
    "dynamics",
    "memory",
    "relationships",
    "environment",
    "safety",
    "autonomous",
    "meta",
]


def load_src():
    with open(SRC, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_identity(m):
    return {
        "id": m["id"].replace("_MODULE_v1.2", "").lower().replace("_", "_"),
        "name": m["name"],
        "version": "1.0.0",
        "source_module": m["id"],
        "source_version": m["version"],
        "compatible_vne": m.get("compatible_vne", "2.1.0"),
        "level_system": m.get("level_system", "U"),
        "archetype": m.get("archetype", "protector_playful_switch"),
        "persona_type": m.get("persona_type", "user_proxy"),
        "age_bracket": m.get("age_bracket", "senior"),
        "variables": m["variables"],
        "anatomic_anchor": m["visual_data"]["anatomic_anchor"],
        "visual_signature": m["visual_data"]["visual_signature"],
    }


def build_level(m, sublevel):
    speech = m["speech_profile"].get(sublevel, {})
    return {
        "level_id": sublevel,
        "speech_profile": speech,
        "dynamic_visuals": m["dynamic_visuals"].get(sublevel, ""),
        "vscno": m["vscno_by_sublevel"].get(sublevel, {}),
        "internal_state": m["internal_state_by_sublevel"].get(sublevel, {}),
        "ad_availability": m["ad_by_sublevel"].get(sublevel, {}),
    }


def build_psychology_base(m):
    p = m["psychology"]
    return {
        "module_id": "BASE",
        "version": "1.0.0",
        "core_conflict": p["core_conflict"],
        "core_paradox": p["core_paradox"],
        "secret_desire": p["secret_desire"],
        "shame_layers": p["shame_layers"],
        "sensory_register": p["sensory_register"],
        "trauma_anchor": p["trauma_anchor"],
    }


def build_psychology_attachment(m):
    p = m["psychology"]
    return {
        "module_id": "ATTACHMENT",
        "version": "1.0.0",
        "attachment_sexuality": p["attachment_sexuality"],
    }


def build_psychology_arousal(m):
    p = m["psychology"]
    return {
        "module_id": "AROUSAL",
        "version": "1.0.0",
        "responsive_desire": p["responsive_desire"],
        "arousal_specificity": p["arousal_specificity"],
    }


def build_psychology_plasticity(m):
    p = m["psychology"]
    return {
        "module_id": "PLASTICITY",
        "version": "1.0.0",
        "erotic_plasticity": p["erotic_plasticity"],
    }


def build_psychology_tec(m):
    p = m["psychology"]
    return {
        "module_id": "TEC",
        "version": "1.0.0",
        "tec_mechanics": p["tec_mechanics"],
    }


def build_sexology_response_cycle(m):
    p = m["psychology"]
    i = m["intimacy_preferences"]
    return {
        "module_id": "RESPONSE_CYCLE",
        "version": "1.0.0",
        "responsive_desire": p["responsive_desire"],
        "arousal_specificity": p["arousal_specificity"],
        "pacing": i["pacing"],
    }


def build_sexology_erotic_scripts(m):
    p = m["psychology"]
    i = m["intimacy_preferences"]
    return {
        "module_id": "EROTIC_SCRIPTS",
        "version": "1.0.0",
        "erotic_plasticity": p["erotic_plasticity"],
        "archetypes": i["archetypes"],
        "switch_context": i["switch_context"],
        "bdsm_interest": i["bdsm_interest"],
    }


def build_sexology_dysphoria_and_shame(m):
    return {
        "module_id": "DYSPHORIA_AND_SHAME",
        "version": "1.0.0",
        "shame_layers": m["psychology"]["shame_layers"],
        "receiving_preferences": m["safety"]["receiving_preferences"],
    }


def build_sexology_fantasy_vs_reality(m):
    return {
        "module_id": "FANTASY_VS_REALITY",
        "version": "1.0.0",
        "secret_desire": m["psychology"]["secret_desire"],
        "ideal_ending": m["intimacy_preferences"]["ideal_ending"],
    }


def build_visual_prompt_base(m):
    v = m["visual_data"]
    return {
        "module_id": "PROMPT_BASE",
        "version": "1.0.0",
        "prompt_base": v["prompt_base"],
        "signature_features": v["signature_features"],
        "anti_prompts": v["anti_prompts"],
        "visual_signature": v["visual_signature"],
        "anatomic_anchor_last_verified": v["anatomic_anchor_last_verified"],
        "reference_image": v["reference_image"],
    }


def build_visual_generation_history(m):
    return {
        "module_id": "GENERATION_HISTORY",
        "version": "1.0.0",
        "generation_history": m["visual_data"]["generation_history"],
    }


def build_dynamics_reaction_patterns(m):
    return {
        "module_id": "REACTION_PATTERNS",
        "version": "1.0.0",
        "reaction_patterns": m["reaction_patterns"],
    }


def build_dynamics_level_lock(m):
    return {
        "module_id": "LEVEL_LOCK_MATRIX",
        "version": "1.0.0",
        "level_lock_matrix": m["cross_persona_sync"]["level_lock_matrix"],
    }


def build_dynamics_emotional_influence(m):
    return {
        "module_id": "EMOTIONAL_INFLUENCE_MATRIX",
        "version": "1.0.0",
        "emotional_influence_matrix": m["cross_persona_sync"]["emotional_influence_matrix"],
    }


def build_dynamics_conflict_resolution(m):
    return {
        "module_id": "CONFLICT_RESOLUTION_MATRIX",
        "version": "1.0.0",
        "conflict_resolution_matrix": m["cross_persona_sync"]["conflict_resolution_matrix"],
    }


def build_memory_trust(m):
    return {
        "module_id": "TRUST",
        "version": "1.0.0",
        "trust_levels": m["memory"]["trust_levels"],
    }


def build_memory_attraction(m):
    return {
        "module_id": "ATTRACTION",
        "version": "1.0.0",
        "attraction_levels": m["memory"]["attraction_levels"],
    }


def build_memory_flags(m):
    return {
        "module_id": "FLAGS",
        "version": "1.0.0",
        "flags": m["memory"]["flags"],
    }


def build_memory_history(m):
    return {
        "module_id": "HISTORY",
        "version": "1.0.0",
        "history": m["memory"]["history"],
    }


def build_memory_emotional_anchors(m):
    return {
        "module_id": "EMOTIONAL_ANCHORS",
        "version": "1.0.0",
        "emotional_anchors": m["memory"]["emotional_anchors"],
    }


def build_relationships_matrix(m):
    return {
        "module_id": "MATRIX",
        "version": "1.0.0",
        "relationships": m["relationships"],
    }


def build_environment_state_triggers(m):
    return {
        "module_id": "STATE_TRIGGERS",
        "version": "1.0.0",
        "state_triggers": m["state_triggers"],
    }


def build_environment_spatial_behavior(m):
    return {
        "module_id": "SPATIAL_BEHAVIOR",
        "version": "1.0.0",
        "spatial_behavior": {
            "note": "[NEEDS_DATA] Проксемика и пространственное поведение не были явно заданы в монолите v1.2.",
            "default": "комфортно на расстоянии 0.5–1.5 м на начальных уровнях, сокращает дистанцию при флирте и физическом контакте",
        },
    }


def build_safety_protocol(m):
    s = m["safety"]
    return {
        "module_id": "PROTOCOL",
        "version": "1.0.0",
        "stop_words": s["stop_words"],
        "default_mode": s["default_mode"],
        "hard_limits": s["hard_limits"],
        "soft_limits": s["soft_limits"],
        "safety_check_points": s["safety_check_points"],
        "ag_max": s["ag_max"],
        "peak_explosion_note": s["peak_explosion_note"],
        "emergency_phrase": s["emergency_phrase"],
    }


def build_autonomous_activities(m):
    return {
        "module_id": "ACTIVITIES",
        "version": "1.0.0",
        "activities": m["autonomous"]["activities"],
    }


def build_autonomous_templates(m):
    return {
        "module_id": "TEMPLATES",
        "version": "1.0.0",
        "message_templates_by_sublevel": m["autonomous"]["message_templates_by_sublevel"],
        "message_templates": m["autonomous"]["message_templates"],
    }


def build_meta(m):
    meta = dict(m["meta"])
    meta.update({
        "chat_display_name": m["chat_display_name"],
        "persona_type": m["persona_type"],
        "age_bracket": m["age_bracket"],
        "algorithms": m["algorithms"],
        "format": m["format"],
        "volume": m["volume"],
        "scenarios": m["scenarios"],
        "engagement": m["engagement"],
        "transition_state": m["transition_state"],
    })
    return {
        "module_id": "META",
        "version": "1.0.0",
        "meta": meta,
    }


def create_index(modules):
    return {
        "id": "andrey_senior",
        "name": "Андрей",
        "version": "2.0.0",
        "schema_version": "1.0.0",
        "default_level": "U1-A",
        "default_ag_level": 1,
        "compatible_scenarios": [
            "sauna_quartet",
            "sauna_trio",
            "promenade",
            "evening_walk",
            "cafe_date",
            "home_visit",
            "olga_solo_hunt",
        ],
        "modules": {path: {"version": "1.0.0", "required": required}
                    for path, required in modules},
        "dependencies": {
            "persona_schema": "v3_2_VOYAGE.json",
            "source_monolith": "ANDREY_SENIOR_MODULE_v1.2.json",
            "state_template": "STATE_TEMPLATE_v2.json",
        },
    }


def create_assembly():
    return """# ASSEMBLY: Андрей Старший (ANDREY_SENIOR_MODULE_v1.2 → modular v2.0.0)

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
"""


def create_handoff_r7():
    return """# HANDOFF_R7: ANDREY_SENIOR_MODULE_v1.2 → personas/andrey_senior/

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
"""


def main():
    print(f"R7 Refactor: {SRC} -> {DST}")
    m = load_src()

    # Ensure clean destination
    if DST.exists():
        print(f"  Destination exists, cleaning: {DST}")
        for item in DST.iterdir():
            if item.is_dir():
                import shutil
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        DST.mkdir(parents=True, exist_ok=True)

    for sf in SUBFOLDERS:
        (DST / sf).mkdir(parents=True, exist_ok=True)

    # Write modular files
    write_json(DST / "core" / "IDENTITY.json", build_identity(m))

    sublevels = [
        "У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А",
        "У4-Б", "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б",
    ]
    for sl in sublevels:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        write_json(DST / "levels" / fname, build_level(m, sl))

    write_json(DST / "psychology" / "BASE.json", build_psychology_base(m))
    write_json(DST / "psychology" / "ATTACHMENT.json", build_psychology_attachment(m))
    write_json(DST / "psychology" / "AROUSAL.json", build_psychology_arousal(m))
    write_json(DST / "psychology" / "PLASTICITY.json", build_psychology_plasticity(m))
    write_json(DST / "psychology" / "TEC.json", build_psychology_tec(m))

    write_json(DST / "sexology" / "RESPONSE_CYCLE.json", build_sexology_response_cycle(m))
    write_json(DST / "sexology" / "EROTIC_SCRIPTS.json", build_sexology_erotic_scripts(m))
    write_json(DST / "sexology" / "DYSPHORIA_AND_SHAME.json", build_sexology_dysphoria_and_shame(m))
    write_json(DST / "sexology" / "FANTASY_VS_REALITY.json", build_sexology_fantasy_vs_reality(m))

    write_json(DST / "visual" / "PROMPT_BASE.json", build_visual_prompt_base(m))
    write_json(DST / "visual" / "GENERATION_HISTORY.json", build_visual_generation_history(m))

    write_json(DST / "dynamics" / "REACTION_PATTERNS.json", build_dynamics_reaction_patterns(m))
    write_json(DST / "dynamics" / "LEVEL_LOCK_MATRIX.json", build_dynamics_level_lock(m))
    write_json(DST / "dynamics" / "EMOTIONAL_INFLUENCE_MATRIX.json", build_dynamics_emotional_influence(m))
    write_json(DST / "dynamics" / "CONFLICT_RESOLUTION_MATRIX.json", build_dynamics_conflict_resolution(m))

    write_json(DST / "memory" / "TRUST.json", build_memory_trust(m))
    write_json(DST / "memory" / "ATTRACTION.json", build_memory_attraction(m))
    write_json(DST / "memory" / "FLAGS.json", build_memory_flags(m))
    write_json(DST / "memory" / "HISTORY.json", build_memory_history(m))
    write_json(DST / "memory" / "EMOTIONAL_ANCHORS.json", build_memory_emotional_anchors(m))

    write_json(DST / "relationships" / "MATRIX.json", build_relationships_matrix(m))

    write_json(DST / "environment" / "STATE_TRIGGERS.json", build_environment_state_triggers(m))
    write_json(DST / "environment" / "SPATIAL_BEHAVIOR.json", build_environment_spatial_behavior(m))

    write_json(DST / "safety" / "PROTOCOL.json", build_safety_protocol(m))

    write_json(DST / "autonomous" / "ACTIVITIES.json", build_autonomous_activities(m))
    write_json(DST / "autonomous" / "TEMPLATES.json", build_autonomous_templates(m))

    write_json(DST / "meta" / "META.json", build_meta(m))

    # INDEX
    modules = [
        ("core/IDENTITY.json", True),
        ("psychology/BASE.json", True),
        ("psychology/ATTACHMENT.json", False),
        ("psychology/AROUSAL.json", False),
        ("psychology/PLASTICITY.json", False),
        ("psychology/TEC.json", False),
        ("sexology/RESPONSE_CYCLE.json", False),
        ("sexology/EROTIC_SCRIPTS.json", False),
        ("sexology/DYSPHORIA_AND_SHAME.json", False),
        ("sexology/FANTASY_VS_REALITY.json", False),
        ("visual/PROMPT_BASE.json", True),
        ("visual/GENERATION_HISTORY.json", True),
        ("dynamics/REACTION_PATTERNS.json", False),
        ("dynamics/LEVEL_LOCK_MATRIX.json", False),
        ("dynamics/EMOTIONAL_INFLUENCE_MATRIX.json", False),
        ("dynamics/CONFLICT_RESOLUTION_MATRIX.json", False),
        ("memory/TRUST.json", True),
        ("memory/ATTRACTION.json", True),
        ("memory/FLAGS.json", True),
        ("memory/HISTORY.json", True),
        ("memory/EMOTIONAL_ANCHORS.json", False),
        ("relationships/MATRIX.json", True),
        ("environment/STATE_TRIGGERS.json", False),
        ("environment/SPATIAL_BEHAVIOR.json", False),
        ("safety/PROTOCOL.json", True),
        ("autonomous/ACTIVITIES.json", True),
        ("autonomous/TEMPLATES.json", True),
        ("meta/META.json", True),
    ]
    for sl in sublevels:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        modules.append((f"levels/{fname}", True))

    write_json(DST / "INDEX.json", create_index(modules))

    # ASSEMBLY.md
    with open(DST / "ASSEMBLY.md", "w", encoding="utf-8") as f:
        f.write(create_assembly())

    # HANDOFF_R7.md
    with open(DST / "HANDOFF_R7.md", "w", encoding="utf-8") as f:
        f.write(create_handoff_r7())

    # Validate JSON
    errors = []
    for root, dirs, files in os.walk(DST):
        for fn in files:
            if fn.endswith(".json"):
                p = Path(root) / fn
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        json.load(f)
                except Exception as e:
                    errors.append(f"{p.relative_to(DST)}: {e}")

    if errors:
        print("  JSON validation ERRORS:")
        for e in errors:
            print(f"    {e}")
        raise SystemExit(1)

    file_count = sum(1 for _ in DST.rglob("*") if _.is_file())
    print(f"  Done. Files created: {file_count}")
    print(f"  Folders: {len(SUBFOLDERS)}")


if __name__ == "__main__":
    main()
