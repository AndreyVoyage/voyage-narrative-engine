#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сравнение ключей: монолит vs модуль (проверка потерь данных)"""

import json
import sys
from pathlib import Path

REPO_DIR = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_DIR = REPO_DIR / "personas"

sys.path.insert(0, str(REPO_DIR / "scripts" / "python"))
from runtime_loader import load_modular_persona

OUTPUT = REPO_DIR / "data_comparison.txt"
f = open(OUTPUT, "w", encoding="utf-8")

def out(*args):
    print(*args, file=f)

def get_all_keys(d, prefix=""):
    """Рекурсивно получает все ключи из словаря."""
    keys = set()
    if isinstance(d, dict):
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            keys.add(full_key)
            if isinstance(v, (dict, list)) and k not in ["generation_history", "history", "activities", "emotional_anchors", "trust_levels", "attraction_levels"]:
                keys.update(get_all_keys(v, full_key))
    return keys

def load_monolith(char_id):
    """Загружает оригинальный монолит."""
    candidates = list(PERSONAS_DIR.glob(f"{char_id}*.json"))
    if not candidates:
        return None
    with open(candidates[0], "r", encoding="utf-8") as f:
        return json.load(f)

out("=== СРАВНЕНИЕ ДАННЫХ: Монолит vs Модуль ===\n")

for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.name):
    if not subdir.is_dir():
        continue
    
    index = subdir / "INDEX.json"
    if not index.exists():
        continue
    
    char_id = subdir.name
    
    monolith = load_monolith(char_id)
    if not monolith:
        out(f"{char_id}: Монолит не найден, пропускаем")
        continue
    
    module = load_modular_persona(char_id)
    if not module:
        out(f"{char_id}: Модуль не загрузился, пропускаем")
        continue
    
    mono_keys = get_all_keys(monolith)
    mod_keys = get_all_keys(module)
    
    lost = mono_keys - mod_keys
    added = mod_keys - mono_keys
    
    out(f"\n{char_id}:")
    out(f"  Монолит ключей: {len(mono_keys)}")
    out(f"  Модуль ключей:  {len(mod_keys)}")
    out(f"  Потеряно:       {len(lost)}")
    out(f"  Добавлено:      {len(added)}")
    
    if lost:
        out(f"  Потерянные ключи (первые 10):")
        for k in sorted(lost)[:10]:
            out(f"    - {k}")
    
    if added:
        out(f"  Добавленные ключи (первые 10):")
        for k in sorted(added)[:10]:
            out(f"    + {k}")
    
    if not lost and not added:
        out(f"  ✅ Полное совпадение!")
    elif not lost:
        out(f"  ⚠️  Только добавлены новые ключи (структурные)")
    else:
        out(f"  ❌ Есть потери!")

out("\n=== ГОТОВО ===")
f.close()
print(f"Results saved to: {OUTPUT}")
