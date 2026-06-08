#!/usr/bin/env python3
"""
Migration Integrity Auditor (MIA) - скрипт для проверки модулей персонажа
Сравнивает файлы в personas/{character}/ с ожидаемой структурой и JSON-схемами.
Запуск: python mia_validator.py
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

# ========== КОНФИГУРАЦИЯ ==========
CHARACTER_ID = "kira"                # Имя персонажа для проверки
PERSONAS_ROOT = Path("personas")     # Корень с персонажами

# Ожидаемые модули (упрощённый список; для полной проверки нужно загрузить INDEX.json)
EXPECTED_MODULES = [
    "core/IDENTITY.json",
    "psychology/BASE.json",
    "psychology/AROUSAL.json",
    "psychology/PLASTICITY.json",
    "psychology/ODSC.json",
    "psychology/ATTACHMENT.json",
    "psychology/TACTICS.json",
    "psychology/DEFENSE_MECHANISMS.json",
    "psychology/VALUE_SYSTEM.json",
    "psychology/ATTACHMENT_STYLE_DYNAMIC.json",
    "psychology/AFFECT_REGULATION.json",
    "psychology/IFS_PARTS.json",
    "psychology/COGNITIVE_DISTORTIONS.json",
    "physiology/AROUSAL_SIGNATURES.json",
    "physiology/CORTICAL_ACTIVATION.json",
    "physiology/MICROEXPRESSIONS.json",
    "physiology/EROGENOUS_MAP.json",
    "sexology/RESPONSE_CYCLE.json",
    "sexology/EROTIC_SCRIPTS.json",
    "sexology/DYSPHORIA_AND_SHAME.json",
    "sexology/FANTASY_VS_REALITY.json",
    "relationships/MATRIX.json",
    "dynamics/RIVALRY_TRIANGLE.json",
    "dynamics/CHARACTER_GROWTH_PATH.json",
    "visual/PROMPT_BASE.json",
    "visual/LIGHTING_MAP.json",
    "visual/GENERATION_HISTORY.json",
    "memory/TRUST.json",
    "memory/ATTRACTION.json",
    "memory/HISTORY.json",
    "memory/FLAGS.json",
    "memory/emotional_anchors.json",
    "autonomous/ACTIVITIES.json",
    "autonomous/TEMPLATES.json",
    "meta/ATTRIBUTION_BIAS.json",
    "meta/UNRELIABLE_NARRATOR.json",
    "meta/COHERENCE_VETO.json",
    "environment/SENSORY_PROCESSING.json",
    "environment/SPATIAL_BEHAVIOR.json",
    "evolution/AROUSAL_AS_MOTIVATION.json",
    "attachment/BEHAVIORAL_SYSTEMS.json",
    "sexual_scripts/EROTIC_SCRIPTS.json",
    "trauma_ptsd/THREE_LEVELS.json",
    "safety/PROTOCOL.json"
]

# 14 уровней
LEVELS = [f"U{i}-{lvl}" for i in range(1, 8) for lvl in ["A", "B"]]

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def load_json(file_path: Path) -> Tuple[Any, str]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f), None
    except Exception as e:
        return None, str(e)

def validate_range(value, min_val, max_val, field_name):
    if not isinstance(value, (int, float)):
        return False, f"not a number"
    if value < min_val or value > max_val:
        return False, f"value {value} out of range [{min_val},{max_val}]"
    return True, "ok"

# ========== ОСНОВНАЯ ПРОВЕРКА ==========
def main():
    character_path = PERSONAS_ROOT / CHARACTER_ID
    if not character_path.exists():
        print(f"❌ Папка персонажа не найдена: {character_path}")
        sys.exit(1)

    errors = []
    warnings = []

    # 1. Проверка наличия ожидаемых модулей
    print(f"\n=== Проверка структуры папок {CHARACTER_ID} ===")
    for mod_path in EXPECTED_MODULES:
        full_path = character_path / mod_path
        if not full_path.exists():
            errors.append(f"Отсутствует модуль: {mod_path}")
            print(f"❌ Отсутствует: {mod_path}")
        else:
            print(f"✅ Найден: {mod_path}")

    # 2. Проверка уровней
    print("\n=== Проверка уровней ===")
    for level in LEVELS:
        level_file = character_path / "levels" / f"{level}.json"
        if not level_file.exists():
            errors.append(f"Отсутствует уровень: levels/{level}.json")
            print(f"❌ Отсутствует: {level}.json")
        else:
            data, err = load_json(level_file)
            if err:
                errors.append(f"levels/{level}.json: {err}")
                print(f"❌ levels/{level}.json: {err}")
            else:
                if data.get("level_id") != level:
                    errors.append(f"levels/{level}.json: level_id='{data.get('level_id')}' не совпадает с именем файла")
                if "lighting" not in data:
                    errors.append(f"levels/{level}.json: отсутствует поле 'lighting'")

    # 3. Проверка содержимого ключевых модулей
    print("\n=== Проверка содержимого модулей ===")

    # relationships/MATRIX.json
    matrix_path = character_path / "relationships" / "MATRIX.json"
    if matrix_path.exists():
        data, err = load_json(matrix_path)
        if err:
            errors.append(f"relationships/MATRIX.json: {err}")
        else:
            for char, rel in data.get("relationships", {}).items():
                trust = rel.get("trust")
                attraction = rel.get("attraction")
                if trust is not None:
                    ok, msg = validate_range(trust, 0, 100, "trust")
                    if not ok:
                        errors.append(f"relationships/MATRIX.json: {char}.trust {msg}")
                if attraction is not None:
                    ok, msg = validate_range(attraction, 0, 100, "attraction")
                    if not ok:
                        errors.append(f"relationships/MATRIX.json: {char}.attraction {msg}")

    # visual/PROMPT_BASE.json
    visual_path = character_path / "visual" / "PROMPT_BASE.json"
    if visual_path.exists():
        data, err = load_json(visual_path)
        if err:
            errors.append(f"visual/PROMPT_BASE.json: {err}")
        else:
            if "anti_prompts" in data and not isinstance(data["anti_prompts"], list):
                errors.append("visual/PROMPT_BASE.json: anti_prompts должен быть массивом")

    # safety/PROTOCOL.json
    safety_path = character_path / "safety" / "PROTOCOL.json"
    if safety_path.exists():
        data, err = load_json(safety_path)
        if err:
            errors.append(f"safety/PROTOCOL.json: {err}")
        else:
            if "hard_limits" not in data:
                warnings.append("safety/PROTOCOL.json: нет поля hard_limits (необязательно, но желательно)")

    # Проверка ifs_part ссылочной целостности
    ifs_parts_path = character_path / "psychology" / "IFS_PARTS.json"
    if ifs_parts_path.exists():
        ifs_data, _ = load_json(ifs_parts_path)
        existing_parts = set(ifs_data.get("parts", {}).keys()) if ifs_data else set()
        levels_dir = character_path / "levels"
        for level_file in levels_dir.glob("U*.json"):
            data, _ = load_json(level_file)
            if data and "ifs_part" in data:
                part = data["ifs_part"]
                if part not in existing_parts:
                    errors.append(f"{level_file.name}: ifs_part '{part}' не найдена в IFS_PARTS.json")

    # Итоговый отчёт
    print("\n" + "="*50)
    print(f"ИТОГОВЫЙ ОТЧЁТ MIA для персонажа {CHARACTER_ID}")
    print(f"Ошибок (критические): {len(errors)}")
    print(f"Предупреждений: {len(warnings)}")
    if errors:
        print("\n❌ КРИТИЧЕСКИЕ ОШИБКИ:")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print("\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
        for w in warnings:
            print(f"  - {w}")
    if not errors and not warnings:
        print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО")

if __name__ == "__main__":
    main()