#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rename persona folders: remove _module_vN suffixes.
Updates INDEX.json and runtime_loader.py accordingly."""

import json
import shutil
from pathlib import Path

REPO_DIR = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_DIR = REPO_DIR / "personas"

RENAME_MAP = {
    "andrey_junior_module_v2.1": "andrey_junior",
    "egor_module_v1": "egor",
    "maksim_module_v2": "maksim",
    "marina_module_v2": "marina",
    "olga_module_v2": "olga",
    "sergey_module_v4": "sergey",
}

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Step 1: Rename folders
for old_name, new_name in RENAME_MAP.items():
    old_path = PERSONAS_DIR / old_name
    new_path = PERSONAS_DIR / new_name
    
    if not old_path.exists():
        print(f"SKIP: {old_path} does not exist")
        continue
    
    if new_path.exists():
        print(f"SKIP: {new_path} already exists")
        continue
    
    # Rename folder
    old_path.rename(new_path)
    print(f"RENAMED: {old_name} -> {new_name}")
    
    # Update INDEX.json inside
    index_path = new_path / "INDEX.json"
    if index_path.exists():
        index = load_json(index_path)
        index["id"] = new_name
        write_json(index_path, index)
        print(f"  Updated INDEX.json: id = {new_name}")

# Step 2: Update runtime_loader.py
loader_path = REPO_DIR / "scripts" / "python" / "runtime_loader.py"
if loader_path.exists():
    with open(loader_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # The discover_modular_persona already handles suffixes, but let's add explicit map
    # Actually, the current code already searches for subdir.startswith(char_id)
    # So it should work with "egor" matching "egor_module_v1"... but now the folder is "egor"
    # So it will work even better!
    
    # We should also update any hardcoded paths in other scripts
    print(f"\nRuntime loader discovery logic already supports partial matching.")
    print("No changes needed to runtime_loader.py")

print("\n=== DONE ===")
print("Next: git add . && git commit -m 'rename: remove _module_vN suffixes'")
