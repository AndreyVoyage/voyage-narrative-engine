#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R7 Refactor: USER_MODULE.json -> personas/user/"""

import json
import os
from pathlib import Path

ROOT = Path("c:/DEV/Narrative/voyage-narrative-engine")
SRC = ROOT / "personas" / "FEMALE_USER_MODULE.json"
DST = ROOT / "personas" / "female_user"

SUBFOLDERS = [
    "core", "levels", "psychology", "sexology", "visual", "dynamics",
    "memory", "relationships", "environment", "safety", "autonomous", "meta",
]

SUBLEVELS = [
    "У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А",
    "У4-Б", "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sublevel_filename(sl):
    return sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"


def main():
    print(f"R7 Refactor: {SRC} -> {DST}")
    m = load_json(SRC)

    if DST.exists():
        print(f"  Destination exists, cleaning: {DST}")
        for item in DST.iterdir():
            if item.is_dir():
                import shutil
                shutil.rmtree(item)
            else:
                item.unlink()
    DST.mkdir(parents=True, exist_ok=True)
    for sf in SUBFOLDERS:
        (DST / sf).mkdir(parents=True, exist_ok=True)

    # core/IDENTITY.json
    write_json(DST / "core" / "IDENTITY.json", {
        "id": "female_user",
        "name": m.get("name", "Девушка"),
        "version": "1.0.0",
        "source_module": m.get("id", "FEMALE_USER_001"),
        "source_version": m.get("version", "1.0.0"),
        "variables": m.get("variables", {}),
        "anatomic_anchor": {},
        "visual_signature": "",
    })

    # levels/*.json — пустые шаблоны
    for sl in SUBLEVELS:
        write_json(DST / "levels" / sublevel_filename(sl), {
            "level_id": sl,
            "speech_profile": {},
            "dynamic_visuals": "",
            "vscno": {},
            "internal_state": {},
            "ad_availability": {},
        })

    # psychology
    psych = m.get("psychology", {})
    write_json(DST / "psychology" / "BASE.json", {
        "module_id": "BASE",
        "version": "1.0.0",
        **({"core_conflict": ""} if "core_conflict" not in psych else {}),
        **psych,
    })
    write_json(DST / "psychology" / "ATTACHMENT.json", {"module_id": "ATTACHMENT", "version": "1.0.0"})
    write_json(DST / "psychology" / "AROUSAL.json", {"module_id": "AROUSAL", "version": "1.0.0"})
    write_json(DST / "psychology" / "PLASTICITY.json", {"module_id": "PLASTICITY", "version": "1.0.0"})
    write_json(DST / "psychology" / "TEC.json", {"module_id": "TEC", "version": "1.0.0"})

    # sexology
    for name in ["RESPONSE_CYCLE", "EROTIC_SCRIPTS", "DYSPHORIA_AND_SHAME", "FANTASY_VS_REALITY"]:
        write_json(DST / "sexology" / f"{name}.json", {"module_id": name, "version": "1.0.0"})

    # visual
    write_json(DST / "visual" / "PROMPT_BASE.json", {"module_id": "PROMPT_BASE", "version": "1.0.0"})
    write_json(DST / "visual" / "GENERATION_HISTORY.json", {"module_id": "GENERATION_HISTORY", "version": "1.0.0", "generation_history": []})

    # dynamics
    write_json(DST / "dynamics" / "REACTION_PATTERNS.json", {"module_id": "REACTION_PATTERNS", "version": "1.0.0"})
    write_json(DST / "dynamics" / "LEVEL_LOCK_MATRIX.json", {"module_id": "LEVEL_LOCK_MATRIX", "version": "1.0.0"})
    write_json(DST / "dynamics" / "EMOTIONAL_INFLUENCE_MATRIX.json", {"module_id": "EMOTIONAL_INFLUENCE_MATRIX", "version": "1.0.0"})
    write_json(DST / "dynamics" / "CONFLICT_RESOLUTION_MATRIX.json", {"module_id": "CONFLICT_RESOLUTION_MATRIX", "version": "1.0.0"})

    # memory
    write_json(DST / "memory" / "TRUST.json", {"module_id": "TRUST", "version": "1.0.0"})
    write_json(DST / "memory" / "ATTRACTION.json", {"module_id": "ATTRACTION", "version": "1.0.0"})
    write_json(DST / "memory" / "FLAGS.json", {"module_id": "FLAGS", "version": "1.0.0"})
    write_json(DST / "memory" / "HISTORY.json", {"module_id": "HISTORY", "version": "1.0.0", "history": []})
    write_json(DST / "memory" / "EMOTIONAL_ANCHORS.json", {"module_id": "EMOTIONAL_ANCHORS", "version": "1.0.0", "emotional_anchors": []})

    # relationships
    write_json(DST / "relationships" / "MATRIX.json", {"module_id": "MATRIX", "version": "1.0.0"})

    # environment
    write_json(DST / "environment" / "STATE_TRIGGERS.json", {
        "module_id": "STATE_TRIGGERS",
        "version": "1.0.0",
        "triggers": m.get("triggers", {}),
    })
    write_json(DST / "environment" / "SPATIAL_BEHAVIOR.json", {
        "module_id": "SPATIAL_BEHAVIOR",
        "version": "1.0.0",
        "spatial_behavior": {
            "note": "[NEEDS_DATA] Проксемика не задана в USER_MODULE.json.",
        },
    })

    # safety
    s = m.get("safety", {})
    write_json(DST / "safety" / "PROTOCOL.json", {
        "module_id": "PROTOCOL",
        "version": "1.0.0",
        "stop_words": s.get("stop_words", []),
        "emergency_response": s.get("emergency_response", ""),
        "cooldown_phrase": s.get("cooldown_phrase", ""),
        "auto_deescalate": s.get("auto_deescalate", False),
    })

    # autonomous
    write_json(DST / "autonomous" / "ACTIVITIES.json", {"module_id": "ACTIVITIES", "version": "1.0.0", "activities": []})
    write_json(DST / "autonomous" / "TEMPLATES.json", {"module_id": "TEMPLATES", "version": "1.0.0"})

    # meta
    meta = {
        "role": m.get("role", ""),
        "interaction": m.get("interaction", {}),
        "preferences": m.get("preferences", {}),
    }
    write_json(DST / "meta" / "META.json", {"module_id": "META", "version": "1.0.0", "meta": meta})

    # INDEX.json
    modules = [
        ("core/IDENTITY.json", True),
        ("psychology/BASE.json", True),
        ("safety/PROTOCOL.json", True),
        ("environment/STATE_TRIGGERS.json", True),
        ("meta/META.json", True),
    ]
    for sl in SUBLEVELS:
        modules.append((f"levels/{sublevel_filename(sl)}", True))
    optional = [
        "psychology/ATTACHMENT.json", "psychology/AROUSAL.json", "psychology/PLASTICITY.json", "psychology/TEC.json",
        "sexology/RESPONSE_CYCLE.json", "sexology/EROTIC_SCRIPTS.json", "sexology/DYSPHORIA_AND_SHAME.json", "sexology/FANTASY_VS_REALITY.json",
        "visual/PROMPT_BASE.json", "visual/GENERATION_HISTORY.json",
        "dynamics/REACTION_PATTERNS.json", "dynamics/LEVEL_LOCK_MATRIX.json", "dynamics/EMOTIONAL_INFLUENCE_MATRIX.json", "dynamics/CONFLICT_RESOLUTION_MATRIX.json",
        "memory/TRUST.json", "memory/ATTRACTION.json", "memory/FLAGS.json", "memory/HISTORY.json", "memory/EMOTIONAL_ANCHORS.json",
        "relationships/MATRIX.json", "environment/SPATIAL_BEHAVIOR.json",
        "autonomous/ACTIVITIES.json", "autonomous/TEMPLATES.json",
    ]
    for opt in optional:
        modules.append((opt, False))

    write_json(DST / "INDEX.json", {
        "id": "female_user",
        "name": m.get("name", "Девушка"),
        "version": "2.0.0",
        "schema_version": "1.0.0",
        "default_level": "U1-A",
        "default_ag_level": 1,
        "compatible_scenarios": [],
        "modules": {path: {"version": "1.0.0", "required": required} for path, required in modules},
        "dependencies": {
            "persona_schema": "v3_2_VOYAGE.json",
            "source_monolith": "USER_MODULE.json",
        },
    })

    # ASSEMBLY.md
    assembly = """# ASSEMBLY: Девушка (FEMALE_USER_MODULE → modular v2.0.0)

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
"""
    with open(DST / "ASSEMBLY.md", "w", encoding="utf-8") as f:
        f.write(assembly)

    # JSON validation
    errors = []
    for root, dirs, files in os.walk(DST):
        for fn in files:
            if fn.endswith(".json"):
                p = Path(root) / fn
                try:
                    load_json(p)
                except Exception as e:
                    errors.append(f"{p.relative_to(DST)}: {e}")
    if errors:
        print("  JSON ERRORS:")
        for e in errors:
            print(f"    {e}")
        raise SystemExit(1)

    file_count = sum(1 for _ in DST.rglob("*") if _.is_file())
    print(f"  Done. Files created: {file_count}")


if __name__ == "__main__":
    main()
