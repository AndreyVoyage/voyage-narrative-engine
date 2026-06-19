#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Size analysis: modular vs monolith vs PRELOAD"""

import json
from pathlib import Path

REPO_DIR = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_DIR = REPO_DIR / "personas"

# Перенаправляем вывод в файл
OUTPUT = REPO_DIR / "size_analysis.txt"
f = open(OUTPUT, "w", encoding="utf-8")

def out(*args):
    print(*args, file=f)

out("=== SIZE ANALYSIS ===\n")

for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.name):
    if not subdir.is_dir():
        continue
    
    index = subdir / "INDEX.json"
    if not index.exists():
        continue
    
    char_id = subdir.name
    
    # Module size
    module_size = sum(f.stat().st_size for f in subdir.rglob("*") if f.is_file())
    module_files = sum(1 for _ in subdir.rglob("*") if _.is_file())
    
    # Monolith size
    monolith_candidates = list(PERSONAS_DIR.glob(f"{char_id}*.json"))
    monolith_size = 0
    if monolith_candidates:
        monolith_size = monolith_candidates[0].stat().st_size
    
    ratio = module_size / monolith_size if monolith_size else 0
    out(f"{char_id:30s} | Module: {module_size/1024:6.1f} KB ({module_files} files) | Monolith: {monolith_size/1024:6.1f} KB | Ratio: {ratio:.2f}x")

out("\n=== SUMMARY ===")

total_module = sum(sum(f.stat().st_size for f in subdir.rglob("*") if f.is_file()) 
                   for subdir in PERSONAS_DIR.iterdir() if subdir.is_dir() and (subdir / "INDEX.json").exists())
total_monolith = sum(f.stat().st_size for f in PERSONAS_DIR.glob("*.json"))

out(f"Total Module:   {total_module/1024:8.1f} KB")
out(f"Total Monolith: {total_monolith/1024:8.1f} KB")
out(f"Ratio:          {total_module/total_monolith if total_monolith else 0:.2f}x")
out(f"\nPRELOAD target (40%): {total_module * 0.4 / 1024:8.1f} KB")
out(f"PRELOAD target (50%): {total_module * 0.5 / 1024:8.1f} KB")

f.close()
print(f"Results saved to: {OUTPUT}")