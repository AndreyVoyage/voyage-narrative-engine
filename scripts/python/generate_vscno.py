#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate VSCNO for all personas based on psychology (R2 rules)."""

import json
from pathlib import Path

REPO_DIR = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_DIR = REPO_DIR / "personas"

SUBLEVELS = [
    ("U1-A", "У1-А"), ("U1-B", "У1-Б"), ("U2-A", "У2-А"), ("U2-B", "У2-Б"),
    ("U3-A", "У3-А"), ("U3-B", "У3-Б"), ("U4-A", "У4-А"), ("U4-B", "У4-Б"),
    ("U5-A", "У5-А"), ("U5-B", "У5-Б"), ("U6-A", "У6-А"), ("U6-B", "У6-Б"),
    ("U7-A", "У7-А"), ("U7-B", "У7-Б")
]

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def detect_pattern(psychology):
    """Detect attachment pattern from psychology."""
    core = psychology.get("core_conflict", "").lower()
    attachment = psychology.get("attachment_sexuality", {})
    
    if "тревож" in core or "анксиоз" in core or "anxious" in str(attachment).lower():
        return "anxious"
    elif "избега" in core or "avoidant" in str(attachment).lower() or "avoid" in core:
        return "avoidant"
    elif "secure" in str(attachment).lower() or "безопас" in core:
        return "secure"
    else:
        return "anxious"  # default

def generate_vscno(pattern, sublevel):
    """Generate VSCNO for a sublevel based on pattern."""
    # Base: all start at 2,2,2,4 (sum=10) - wait, sum must be 10
    # Let's use: ВЛ + СТ + НЖ + ОГ = 10
    # Each axis [0,4]
    
    u_num = int(sublevel[1])
    side = sublevel[-1]  # A or B
    
    if pattern == "anxious":
        # Anxious: high СТ on early levels, high НЖ on late levels
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 3, 3, 1, 3  # barrier: high stress
        elif u_num <= 4:
            ВЛ, СТ, НЖ, ОГ = 4, 2, 2, 2  # adaptive: attraction rises
        elif u_num <= 5:
            ВЛ, СТ, НЖ, ОГ = 3, 2, 3, 2  # peak: passion
        else:
            ВЛ, СТ, НЖ, ОГ = 2, 1, 4, 3  # aftercare: high tenderness
    
    elif pattern == "avoidant":
        # Avoidant: high ОГ on early, high ВЛ on middle, distant on late
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 2, 1, 1, 6  # barrier: high restriction - wait, max 4
        # Fix: max is 4 per axis
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 2, 1, 1, 6  # ERROR, max 4
    
    # Let me recalculate with proper constraints
    # Each axis [0,4], sum=10
    
    if pattern == "anxious":
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 3, 3, 1, 3  # sum=10, barrier: anxious
        elif u_num == 3:
            ВЛ, СТ, НЖ, ОГ = 4, 2, 2, 2  # sum=10, flirt: playful
        elif u_num == 4:
            if side == "A":
                ВЛ, СТ, НЖ, ОГ = 3, 2, 3, 2  # breakthrough: passion rises
            else:
                ВЛ, СТ, НЖ, ОГ = 2, 2, 4, 2  # aftercare: tenderness
        elif u_num == 5:
            ВЛ, СТ, НЖ, ОГ = 3, 2, 2, 3  # peak: mixed
        elif u_num == 6:
            ВЛ, СТ, НЖ, ОГ = 2, 3, 2, 3  # crash: high stress
        else:  # U7
            if side == "A":
                ВЛ, СТ, НЖ, ОГ = 2, 1, 4, 3  # care: high tenderness
            else:
                ВЛ, СТ, НЖ, ОГ = 2, 1, 5, 2  # ERROR: max 4
        # Fix U7-B
        if u_num == 7 and side == "B":
            ВЛ, СТ, НЖ, ОГ = 2, 1, 4, 3  # care: gentle
    
    elif pattern == "avoidant":
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 2, 1, 1, 6  # ERROR
        # Fix: max 4 per axis
        if u_num <= 2:
            ВЛ, СТ, НЖ, ОГ = 2, 1, 1, 6  # Still wrong
    
    # Let me be more careful
    # Max per axis is 4, sum is 10
    # So valid combinations are limited
    
    # Let's use predefined valid combinations for each pattern and level
    
    # Anxious pattern (high stress, high attachment need)
    anxious_map = {
        "U1-A": {"ВЛ": 3, "СТ": 3, "НЖ": 1, "ОГ": 3, "note": "Барьер: тревога, контроль"},
        "U1-B": {"ВЛ": 2, "СТ": 4, "НЖ": 1, "ОГ": 3, "note": "Барьер: макс тревога"},
        "U2-A": {"ВЛ": 4, "СТ": 2, "НЖ": 2, "ОГ": 2, "note": "Адаптив: флирт, снижение тревоги"},
        "U2-B": {"ВЛ": 3, "СТ": 3, "НЖ": 2, "ОГ": 2, "note": "Адаптив: скрытая ревность"},
        "U3-A": {"ВЛ": 4, "СТ": 2, "НЖ": 2, "ОГ": 2, "note": "Флирт: активное влечение"},
        "U3-B": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Флирт: отстранение"},
        "U4-A": {"ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2, "note": "Перелом: страсть + нежность"},
        "U4-B": {"ВЛ": 2, "СТ": 2, "НЖ": 4, "ОГ": 2, "note": "Послеопека: макс нежность"},
        "U5-A": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Пик: смешанные эмоции"},
        "U5-B": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3, "note": "Пик: агрессия от стресса"},
        "U6-A": {"ВЛ": 2, "СТ": 4, "НЖ": 1, "ОГ": 3, "note": "Крах: тревога максимум"},
        "U6-B": {"ВЛ": 1, "СТ": 3, "НЖ": 2, "ОГ": 4, "note": "Диссоциация: отстранение"},
        "U7-A": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: привязанность"},
        "U7-B": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: нежность"},
    }
    
    # Avoidant pattern (high restriction, distant)
    avoidant_map = {
        "U1-A": {"ВЛ": 2, "СТ": 1, "НЖ": 1, "ОГ": 6, "note": "Барьер: макс ограничение"},  # ERROR
    }
    # Fix: max 4 per axis
    # Let me recalculate all
    
    # Avoidant: needs high ОГ early, but max 4
    # U1-A: ОГ=4, ВЛ=2, СТ=1, НЖ=3 → sum=10, but НЖ should be low for avoidant
    # U1-A: ОГ=4, ВЛ=2, СТ=2, НЖ=2 → sum=10, more balanced
    
    avoidant_map = {
        "U1-A": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 4, "note": "Барьер: холод, дистанция"},
        "U1-B": {"ВЛ": 2, "СТ": 1, "НЖ": 2, "ОГ": 5, "note": "Барьер: макс ограничение"},  # ERROR
    }
    # Still wrong. Let me be systematic.
    
    # Valid combinations where sum=10 and each [0,4]:
    # 4,4,2,0 → sum=10
    # 4,3,2,1 → sum=10
    # 4,3,3,0 → sum=10
    # 4,2,2,2 → sum=10
    # 3,3,2,2 → sum=10
    # 3,3,3,1 → sum=10
    # 3,3,4,0 → sum=10
    # 3,2,2,3 → sum=10
    # etc.
    
    # For avoidant pattern:
    # Early: high ОГ (restriction), low НЖ (no tenderness)
    # Middle: ВЛ rises (flirt), ОГ drops
    # Late: distant again
    
    avoidant_map = {
        "U1-A": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 4, "note": "Барьер: холод, дистанция"},
        "U1-B": {"ВЛ": 2, "СТ": 3, "НЖ": 1, "ОГ": 4, "note": "Барьер: агрессия от страха"},
        "U2-A": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Адаптив: интерес, но дистанция"},
        "U2-B": {"ВЛ": 3, "СТ": 2, "НЖ": 1, "ОГ": 4, "note": "Адаптив: отстранение"},
        "U3-A": {"ВЛ": 4, "СТ": 2, "НЖ": 2, "ОГ": 2, "note": "Флирт: влечение прорывается"},
        "U3-B": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Флирт: сдержанность"},
        "U4-A": {"ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2, "note": "Перелом: уязвимость"},
        "U4-B": {"ВЛ": 2, "СТ": 2, "НЖ": 4, "ОГ": 2, "note": "Послеопека: нежность"},
        "U5-A": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Пик: смешанные"},
        "U5-B": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3, "note": "Пик: агрессия"},
        "U6-A": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3, "note": "Крах: паника"},
        "U6-B": {"ВЛ": 1, "СТ": 3, "НЖ": 2, "ОГ": 4, "note": "Диссоциация: полное отстранение"},
        "U7-A": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: удивительно нежная"},
        "U7-B": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: тихая близость"},
    }
    
    # Secure pattern (balanced)
    secure_map = {
        "U1-A": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Барьер: спокойный интерес"},
        "U1-B": {"ВЛ": 2, "СТ": 2, "НЖ": 3, "ОГ": 3, "note": "Барьер: осторожный контакт"},
        "U2-A": {"ВЛ": 4, "СТ": 2, "НЖ": 2, "ОГ": 2, "note": "Адаптив: открытый флирт"},
        "U2-B": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Адаптив: дружелюбие"},
        "U3-A": {"ВЛ": 4, "СТ": 2, "НЖ": 2, "ОГ": 2, "note": "Флирт: уверенный"},
        "U3-B": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Флирт: с игрой"},
        "U4-A": {"ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2, "note": "Перелом: открытая страсть"},
        "U4-B": {"ВЛ": 2, "СТ": 2, "НЖ": 4, "ОГ": 2, "note": "Послеопека: тепло"},
        "U5-A": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "Пик: гармония"},
        "U5-B": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3, "note": "Пик: стресс"},
        "U6-A": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3, "note": "Крах: сдержанная тревога"},
        "U6-B": {"ВЛ": 2, "СТ": 2, "НЖ": 3, "ОГ": 3, "note": "Диссоциация: уход в себя"},
        "U7-A": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: глубокая близость"},
        "U7-B": {"ВЛ": 2, "СТ": 1, "НЖ": 4, "ОГ": 3, "note": "Опека: уют"},
    }
    
    if pattern == "anxious":
        return anxious_map.get(sublevel, {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 4, "note": "default"})
    elif pattern == "avoidant":
        return avoidant_map.get(sublevel, {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 4, "note": "default"})
    else:  # secure
        return secure_map.get(sublevel, {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3, "note": "default"})


def main():
    for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.name):
        if not subdir.is_dir():
            continue
        
        index = subdir / "INDEX.json"
        if not index.exists():
            continue
        
        char_id = subdir.name
        print(f"\nProcessing: {char_id}")
        
        # Load psychology
        psych_path = subdir / "psychology" / "BASE.json"
        if not psych_path.exists():
            print(f"  SKIP: no psychology/BASE.json")
            continue
        
        psychology = load_json(psych_path)
        pattern = detect_pattern(psychology)
        print(f"  Pattern: {pattern}")
        
        # Generate VSCNO for each sublevel
        fixed_count = 0
        for eng, cyr in SUBLEVELS:
            level_path = subdir / "levels" / f"{eng}.json"
            if not level_path.exists():
                continue
            
            level_data = load_json(level_path)
            
            # Check if vscno is empty or missing
            vscno = level_data.get("vscno", {})
            if not vscno or not any(v for v in vscno.values() if isinstance(v, (int, float))):
                # Generate new VSCNO
                new_vscno = generate_vscno(pattern, eng)
                level_data["vscno"] = new_vscno
                write_json(level_path, level_data)
                fixed_count += 1
                print(f"    {eng}: {new_vscno['ВЛ']}/{new_vscno['СТ']}/{new_vscno['НЖ']}/{new_vscno['ОГ']} = {sum([new_vscno['ВЛ'], new_vscno['СТ'], new_vscno['НЖ'], new_vscno['ОГ']])}")
        
        print(f"  Fixed: {fixed_count}/14 sublevels")
    
    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
