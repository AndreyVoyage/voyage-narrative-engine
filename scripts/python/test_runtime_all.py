#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runtime Loader Test: все 10 персонажей
Пишет результаты в test_results_runtime.json (UTF-8)
"""

import json
import sys
import traceback
from pathlib import Path

# Добавляем путь к runtime_loader
sys.path.insert(0, str(Path(__file__).parent))
from runtime_loader import load_modular_persona, validate_modular_persona, discover_modular_persona

REPO_DIR = Path(__file__).resolve().parent.parent.parent
PERSONAS_DIR = REPO_DIR / "personas"

RESULTS = []

for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.name):
    if not subdir.is_dir():
        continue
    
    index = subdir / "INDEX.json"
    if not index.exists():
        continue
    
    char_id = subdir.name
    print(f"Testing: {char_id}")
    
    result = {
        "id": char_id,
        "folder": str(subdir.name),
        "load": "PENDING",
        "error": None,
        "validation": {},
        "stats": {}
    }
    
    try:
        persona = load_modular_persona(char_id)
        if persona:
            result["load"] = "PASS"
            result["stats"] = {
                "name": persona.get("name", ""),
                "version": persona.get("version", ""),
                "levels_count": len(persona.get("levels", {})),
                "vscno_count": len(persona.get("vscno_by_sublevel", {})),
                "has_safety": "safety" in persona,
                "has_core": "anatomic_anchor" in persona,
            }
            result["validation"] = validate_modular_persona(persona)
        else:
            result["load"] = "FAIL"
            result["error"] = "load_modular_persona returned None"
    except Exception as e:
        result["load"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)}"
        result["traceback"] = traceback.format_exc()
    
    RESULTS.append(result)
    status = result["load"]
    print(f"  -> {status}")

# Сохраняем результаты
output = REPO_DIR / "test_results_runtime.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=2)

print(f"\nResults saved to: {output}")
print(f"Total tested: {len(RESULTS)}")
print(f"PASS: {sum(1 for r in RESULTS if r['load'] == 'PASS')}")
print(f"FAIL: {sum(1 for r in RESULTS if r['load'] == 'FAIL')}")
