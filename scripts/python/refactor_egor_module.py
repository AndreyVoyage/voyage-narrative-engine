#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R7 Refactor: EGOR_MODULE_v1.json -> personas/egor/"""

import json
import os
from pathlib import Path

ROOT = Path("c:/DEV/Narrative/voyage-narrative-engine")
SRC = ROOT / "personas" / "EGOR_MODULE_v1.json"
DST = ROOT / "personas" / "egor"

SUBFOLDERS = [
    "core", "levels", "psychology", "sexology", "visual", "dynamics",
    "memory", "relationships", "environment", "safety", "autonomous", "meta",
]

SUBLEVELS = [
    "U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A",
    "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B",
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sublevel_filename(sl):
    return sl + ".json"


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
        "id": "egor",
        "name": m.get("name", "Егор"),
        "version": "1.0.0",
        "source_module": m.get("id", "EGOR_MODULE_v1"),
        "source_version": m.get("version", "1.0.0"),
        "variables": m.get("variables", {}),
        "anatomic_anchor": m.get("visual_data", {}).get("anatomic_anchor", {}),
        "visual_signature": m.get("visual_data", {}).get("visual_signature_string", ""),
    })

    # levels/*.json
    speech_deltas = m.get("speech_profile", {}).get("deltas", {})
    visuals_table = m.get("dynamic_visuals", {}).get("_table", [])
    # convert table to dict keyed by level
    visuals_by_level = {}
    if visuals_table and len(visuals_table) > 1:
        headers = visuals_table[0]
        for row in visuals_table[1:]:
            level_key = row[0]
            visuals_by_level[level_key] = {headers[i]: row[i] for i in range(len(headers))}
    for sl in SUBLEVELS:
        write_json(DST / "levels" / sublevel_filename(sl), {
            "level_id": sl,
            "speech_profile": speech_deltas.get(sl, {}),
            "dynamic_visuals": visuals_by_level.get(sl, {}),
            "vscno": m.get("vscno", {}).get(sl, {}),
            "internal_state": {
                "baseline": m.get("internal_state", {}).get("baseline", {}),
                "delta": m.get("internal_state", {}).get("deltas", {}).get(sl, []),
            },
            "ad_availability": {
                "available": m.get("algorithms", {}).get(sl, []),
            },
        })

    # psychology
    psych = m.get("psychology", {})
    write_json(DST / "psychology" / "BASE.json", {
        "module_id": "BASE",
        "version": "1.0.0",
        "core_conflict": psych.get("core_conflict", ""),
        "trauma": psych.get("trauma", {}),
        "distortions": psych.get("distortions", {}),
        "regression_points": psych.get("regression_points", []),
        "sensory_register": psych.get("sensory_register", ""),
        "shame_tolerance": psych.get("shame_tolerance", ""),
    })
    write_json(DST / "psychology" / "ATTACHMENT.json", {
        "module_id": "ATTACHMENT",
        "version": "1.0.0",
        "attachment_style": psych.get("attachment_style", ""),
        "attachment_base": psych.get("attachment_base", ""),
    })
    write_json(DST / "psychology" / "AROUSAL.json", {
        "module_id": "AROUSAL",
        "version": "1.0.0",
        "modes": m.get("modes", {}),
    })
    write_json(DST / "psychology" / "PLASTICITY.json", {
        "module_id": "PLASTICITY",
        "version": "1.0.0",
        "tec_007": m.get("tec", {}).get("TEC_007", {}),
    })
    write_json(DST / "psychology" / "TEC.json", {
        "module_id": "TEC",
        "version": "1.0.0",
        "tec_mechanics": m.get("tec", {}),
    })

    # sexology
    write_json(DST / "sexology" / "RESPONSE_CYCLE.json", {
        "module_id": "RESPONSE_CYCLE",
        "version": "1.0.0",
        "modes": m.get("modes", {}),
    })
    write_json(DST / "sexology" / "EROTIC_SCRIPTS.json", {
        "module_id": "EROTIC_SCRIPTS",
        "version": "1.0.0",
        "scenarios": m.get("scenarios", []),
    })
    write_json(DST / "sexology" / "DYSPHORIA_AND_SHAME.json", {
        "module_id": "DYSPHORIA_AND_SHAME",
        "version": "1.0.0",
        "shame_tolerance": psych.get("shame_tolerance", ""),
        "soft_limits": m.get("safety", {}).get("soft_limits", []),
        "safeword": m.get("safety", {}).get("safeword", ""),
    })
    write_json(DST / "sexology" / "FANTASY_VS_REALITY.json", {
        "module_id": "FANTASY_VS_REALITY",
        "version": "1.0.0",
        "secret_desire": psych.get("secret_desire", ""),
        "tec_004": m.get("tec", {}).get("TEC_004", {}),
    })

    # visual
    write_json(DST / "visual" / "PROMPT_BASE.json", {
        "module_id": "PROMPT_BASE",
        "version": "1.0.0",
        "anatomic_anchor": m.get("visual_data", {}).get("anatomic_anchor", {}),
        "visual_signature": m.get("visual_data", {}).get("visual_signature_string", ""),
    })
    write_json(DST / "visual" / "GENERATION_HISTORY.json", {
        "module_id": "GENERATION_HISTORY",
        "version": "1.0.0",
        "generation_history": [],
    })

    # dynamics
    write_json(DST / "dynamics" / "REACTION_PATTERNS.json", {
        "module_id": "REACTION_PATTERNS",
        "version": "1.0.0",
        "engagement": m.get("engagement", {}),
        "transition_state": m.get("transition_state", {}),
    })
    write_json(DST / "dynamics" / "LEVEL_LOCK_MATRIX.json", {
        "module_id": "LEVEL_LOCK_MATRIX",
        "version": "1.0.0",
    })
    write_json(DST / "dynamics" / "EMOTIONAL_INFLUENCE_MATRIX.json", {
        "module_id": "EMOTIONAL_INFLUENCE_MATRIX",
        "version": "1.0.0",
    })
    write_json(DST / "dynamics" / "CONFLICT_RESOLUTION_MATRIX.json", {
        "module_id": "CONFLICT_RESOLUTION_MATRIX",
        "version": "1.0.0",
        "regression_triggers": m.get("safety", {}).get("regression_triggers", []),
    })

    # memory
    mem = m.get("memory", {})
    write_json(DST / "memory" / "TRUST.json", {
        "module_id": "TRUST",
        "version": "1.0.0",
        "trust_baseline": mem.get("trust_baseline", {}),
    })
    write_json(DST / "memory" / "ATTRACTION.json", {
        "module_id": "ATTRACTION",
        "version": "1.0.0",
        "attraction_baseline": mem.get("attraction_baseline", {}),
    })
    write_json(DST / "memory" / "FLAGS.json", {
        "module_id": "FLAGS",
        "version": "1.0.0",
        "flags": mem.get("flags", {}),
    })
    write_json(DST / "memory" / "HISTORY.json", {
        "module_id": "HISTORY",
        "version": "1.0.0",
        "history": [],
    })
    write_json(DST / "memory" / "EMOTIONAL_ANCHORS.json", {
        "module_id": "EMOTIONAL_ANCHORS",
        "version": "1.0.0",
        "emotional_anchors": [],
    })

    # relationships
    write_json(DST / "relationships" / "MATRIX.json", {
        "module_id": "MATRIX",
        "version": "1.0.0",
        "relationships": m.get("relationships", {}),
    })

    # environment
    write_json(DST / "environment" / "STATE_TRIGGERS.json", {
        "module_id": "STATE_TRIGGERS",
        "version": "1.0.0",
    })
    write_json(DST / "environment" / "SPATIAL_BEHAVIOR.json", {
        "module_id": "SPATIAL_BEHAVIOR",
        "version": "1.0.0",
        "spatial_behavior": {
            "note": "[NEEDS_DATA] Проксемика не задана в EGOR_MODULE_v1.json.",
        },
    })

    # safety
    s = m.get("safety", {})
    write_json(DST / "safety" / "PROTOCOL.json", {
        "module_id": "PROTOCOL",
        "version": "1.0.0",
        "hard_limits": s.get("hard_limits", []),
        "soft_limits": s.get("soft_limits", []),
        "safeword": s.get("safeword", ""),
        "regression_triggers": s.get("regression_triggers", []),
    })

    # autonomous
    write_json(DST / "autonomous" / "ACTIVITIES.json", {
        "module_id": "ACTIVITIES",
        "version": "1.0.0",
        "activities": [],
    })
    write_json(DST / "autonomous" / "TEMPLATES.json", {
        "module_id": "TEMPLATES",
        "version": "1.0.0",
    })

    # meta
    meta = {
        "_meta": m.get("_meta", {}),
        "_inherit": m.get("_inherit", ""),
        "_anchors": m.get("_anchors", {}),
        "_refs": m.get("_refs", {}),
        "format": m.get("format", ""),
        "volume": m.get("volume", ""),
    }
    write_json(DST / "meta" / "META.json", {"module_id": "META", "version": "1.0.0", "meta": meta})

    # INDEX.json
    modules = [
        ("core/IDENTITY.json", True),
        ("psychology/BASE.json", True),
        ("psychology/ATTACHMENT.json", True),
        ("psychology/AROUSAL.json", True),
        ("psychology/PLASTICITY.json", True),
        ("psychology/TEC.json", True),
        ("sexology/RESPONSE_CYCLE.json", True),
        ("sexology/EROTIC_SCRIPTS.json", True),
        ("sexology/DYSPHORIA_AND_SHAME.json", True),
        ("sexology/FANTASY_VS_REALITY.json", True),
        ("visual/PROMPT_BASE.json", True),
        ("visual/GENERATION_HISTORY.json", True),
        ("dynamics/REACTION_PATTERNS.json", True),
        ("dynamics/LEVEL_LOCK_MATRIX.json", False),
        ("dynamics/EMOTIONAL_INFLUENCE_MATRIX.json", False),
        ("dynamics/CONFLICT_RESOLUTION_MATRIX.json", True),
        ("memory/TRUST.json", True),
        ("memory/ATTRACTION.json", True),
        ("memory/FLAGS.json", True),
        ("memory/HISTORY.json", True),
        ("memory/EMOTIONAL_ANCHORS.json", False),
        ("relationships/MATRIX.json", True),
        ("environment/STATE_TRIGGERS.json", False),
        ("environment/SPATIAL_BEHAVIOR.json", False),
        ("safety/PROTOCOL.json", True),
        ("autonomous/ACTIVITIES.json", False),
        ("autonomous/TEMPLATES.json", False),
        ("meta/META.json", True),
    ]
    for sl in SUBLEVELS:
        modules.append((f"levels/{sublevel_filename(sl)}", True))

    write_json(DST / "INDEX.json", {
        "id": "egor",
        "name": m.get("name", "Егор"),
        "version": "2.0.0",
        "schema_version": "1.0.0",
        "default_level": "U1-A",
        "default_ag_level": m.get("_meta", {}).get("ag_level", 3),
        "compatible_scenarios": [s.get("name", "") for s in m.get("scenarios", [])],
        "modules": {path: {"version": "1.0.0", "required": required} for path, required in modules},
        "dependencies": {
            "persona_schema": "v3_2_VOYAGE.json",
            "source_monolith": "EGOR_MODULE_v1.json",
        },
    })

    # ASSEMBLY.md
    assembly = """# ASSEMBLY: Егор (EGOR_MODULE_v1 -> modular v2.0.0)

> Инструкция для LLM/движка: как собрать полный контекст Егора из модульных JSON.

## Базовая сборка (всегда)
1. `core/IDENTITY.json` — кто он (возраст, внешность, anatomic_anchor)
2. `psychology/BASE.json` — почему он такой (травма, core_conflict, искажения, regression_points)
3. `safety/PROTOCOL.json` — где границы (hard/soft limits, regression_triggers)

## Уровневая сборка (по текущему уровню)
Если current_level = U3-A:
- `levels/U3-A.json` — speech_profile, dynamic_visuals, vscno, internal_state (baseline+delta), ad_availability

## Психологическая сборка (ag_level >= 2)
- `psychology/ATTACHMENT.json` — attachment_style, attachment_base
- `psychology/AROUSAL.json` — modes (desire_type, cycle)
- `psychology/PLASTICITY.json` — TEC_007 пластичность
- `psychology/TEC.json` — TEC_001–TEC_008

## Сексологическая сборка (ag_level >= 3 или scene_type = "erotic")
- `sexology/RESPONSE_CYCLE.json` — desire modes
- `sexology/EROTIC_SCRIPTS.json` — сценарии (Победа над мужем, Считывание, Публичный риск, Овладение, Театральность)
- `sexology/DYSPHORIA_AND_SHAME.json` — shame_tolerance, soft_limits, safeword
- `sexology/FANTASY_VS_REALITY.json` — secret_desire, TEC_004 motives

## Сценарийная / межперсонажная сборка
- `relationships/MATRIX.json` — user, sergey, kira, olga, andrey_st, andrey_ml, marina, maksim
- `dynamics/CONFLICT_RESOLUTION_MATRIX.json` — regression_triggers
- `dynamics/REACTION_PATTERNS.json` — engagement, transition_state

## Runtime сборка (из state)
- `memory/TRUST.json` + state updates
- `memory/ATTRACTION.json` + state updates
- `memory/HISTORY.json` — контекст прошлых сессий
- `memory/FLAGS.json` — битовая маска флагов
- `memory/EMOTIONAL_ANCHORS.json` — якоря

## Мета-сборка
- `meta/META.json` — _meta, _inherit, _anchors, _refs, format, volume

## Правила сборки
1. **Никогда не смешивай уровни.** Только один файл из `levels/`.
2. **VSCNO берётся из state, не из модуля.** Модуль — шаблон, state — текущее.
3. **Memory накладывается поверх.**
4. **Если уровень неизвестен — default U1-A.**
5. **Safety > All.** Hard limits и regression_triggers вызывают de-escalation.
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
