#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix missing data: добавляет потерянные ключи из монолита в модульную структуру."""

import json
import sys
from pathlib import Path

REPO_DIR = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_DIR = REPO_DIR / "personas"

sys.path.insert(0, str(REPO_DIR / "scripts" / "python"))
from runtime_loader import load_modular_persona

OUTPUT = REPO_DIR / "fix_missing_report.txt"
f = open(OUTPUT, "w", encoding="utf-8")

def out(*args):
    print(*args, file=f)

def load_monolith(char_id):
    """Загружает оригинальный монолит."""
    candidates = list(PERSONAS_DIR.glob(f"{char_id}*.json"))
    if not candidates:
        return None
    with open(candidates[0], "r", encoding="utf-8") as f:
        return json.load(f)

def find_value(data, key_path):
    """Находит значение по пути ключей (например, '_anchors.AD')."""
    parts = key_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

out("=== FIX MISSING DATA ===\n")

for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.name):
    if not subdir.is_dir():
        continue
    
    index = subdir / "INDEX.json"
    if not index.exists():
        continue
    
    char_id = subdir.name
    monolith = load_monolith(char_id)
    if not monolith:
        continue
    
    # Критичные потерянные ключи и их маппинг
    critical_fixes = {
        "_anchors": ("psychology", "ANCHORS.json"),
        "interaction": ("meta", "META_INTERACTION.json"),
        "preferences": ("meta", "META_PREFERENCES.json"),
        "algorithms": ("levels", "ALGORITHMS.json"),
    }
    
    fixed_any = False
    
    for key, (folder, filename) in critical_fixes.items():
        if key in monolith:
            target = subdir / folder / filename
            if not target.exists():
                write_json(target, {
                    "module_id": filename.replace(".json", ""),
                    "version": "1.0.0",
                    "source": "fix_missing_data.py",
                    "note": f"Добавлен из монолита, был потерян при R7 миграции",
                    key: monolith[key]
                })
                out(f"{char_id}: Created {folder}/{filename} with '{key}'")
                fixed_any = True
    
    # Специальные фиксы для dynamic_visuals (maksim, marina, sergey)
    if "dynamic_visuals" in monolith:
        dv = monolith["dynamic_visuals"]
        # Проверяем, есть ли dynamic_visuals в levels
        has_dv_in_levels = False
        for sl in ["U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A", "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B"]:
            lvl = subdir / "levels" / f"{sl}.json"
            if lvl.exists():
                try:
                    d = load_json(lvl)
                    if d.get("dynamic_visuals"):
                        has_dv_in_levels = True
                        break
                except:
                    pass
        
        if not has_dv_in_levels:
            # Создаем visual/DYNAMIC_VISUALS.json
            target = subdir / "visual" / "DYNAMIC_VISUALS.json"
            write_json(target, {
                "module_id": "DYNAMIC_VISUALS",
                "version": "1.0.0",
                "source": "fix_missing_data.py",
                "note": "Добавлены из монолита, были потеряны при R7 миграции",
                "dynamic_visuals": dv
            })
            out(f"{char_id}: Created visual/DYNAMIC_VISUALS.json")
            fixed_any = True
    
    # Специальные фиксы для cross_persona_sync (andrey_junior, andrey_senior, olga)
    if "cross_persona_sync" in monolith:
        target = subdir / "dynamics" / "CROSS_PERSONA_SYNC.json"
        if not target.exists():
            write_json(target, {
                "module_id": "CROSS_PERSONA_SYNC",
                "version": "1.0.0",
                "source": "fix_missing_data.py",
                "note": "Добавлен из монолита, был потерян при R7 миграции",
                "cross_persona_sync": monolith["cross_persona_sync"]
            })
            out(f"{char_id}: Created dynamics/CROSS_PERSONA_SYNC.json")
            fixed_any = True
    
    # Добавляем age_bracket, compatible_vne в core/IDENTITY если отсутствуют
    identity = subdir / "core" / "IDENTITY.json"
    if identity.exists() and ("age_bracket" in monolith or "compatible_vne" in monolith):
        try:
            id_data = load_json(identity)
            changed = False
            for key in ["age_bracket", "compatible_vne"]:
                if key in monolith and key not in id_data:
                    id_data[key] = monolith[key]
                    changed = True
            if changed:
                write_json(identity, id_data)
                out(f"{char_id}: Updated core/IDENTITY.json (age_bracket, compatible_vne)")
                fixed_any = True
        except:
            pass
    
    if not fixed_any:
        out(f"{char_id}: No critical fixes needed")

out("\n=== DONE ===")
out(f"Report saved to: {OUTPUT}")
f.close()
print(f"Fix report saved to: {OUTPUT}")
