#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Modular Runtime Loader v2.2
Загружает модульную структуру personas/[id]/ в рантайм.

Usage:
  from runtime_loader import load_modular_persona
  persona = load_modular_persona("andrey_senior")
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

# REPO_DIR = корень репозитория (скрипт в scripts/python/, поднимаемся на 2 уровня)
REPO_DIR = Path(__file__).resolve().parent.parent.parent
PERSONAS_DIR = REPO_DIR / "personas"

# =============================================================================
# ОТКРЫТИЕ (DISCOVERY)
# =============================================================================

def discover_modular_persona(char_id: str) -> Optional[Path]:
    """
    Ищет модульную структуру: personas/[id]/INDEX.json
    Возвращает путь к INDEX.json или None.
    """
    # 1. Прямой поиск: personas/[id]/INDEX.json
    direct = PERSONAS_DIR / char_id / "INDEX.json"
    if direct.exists():
        return direct
    
    # 2. Поиск с суффиксами: personas/[id]_module_v*/INDEX.json
    for subdir in sorted(PERSONAS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if subdir.is_dir() and subdir.name.startswith(char_id):
            index = subdir / "INDEX.json"
            if index.exists():
                return index
    
    # 3. Fallback: поиск по ID внутри INDEX.json
    for subdir in PERSONAS_DIR.iterdir():
        if subdir.is_dir():
            index = subdir / "INDEX.json"
            if index.exists():
                try:
                    with open(index, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("id") == char_id or data.get("name", "").lower() == char_id.lower():
                        return index
                except:
                    pass
    
    return None

# =============================================================================
# ЗАГРУЗКА МОДУЛЕЙ
# =============================================================================

def load_module(index_dir: Path, module_path: str) -> Optional[Dict]:
    """Загружает один модуль по пути относительно index_dir."""
    path = index_dir / module_path
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None

def load_modular_persona(char_id: str) -> Optional[Dict]:
    """
    Загружает модульного персонажа: INDEX.json + все модули.
    Возвращает объединённый словарь (как старый монолит).
    """
    index_path = discover_modular_persona(char_id)
    if not index_path:
        return None
    
    index_dir = index_path.parent
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return None
    
    # Базовая структура
    persona = {
        "id": index.get("id", char_id),
        "name": index.get("name", ""),
        "version": index.get("version", "2.0.0"),
        "schema_version": index.get("schema_version", "1.0.0"),
        "default_level": index.get("default_level", "U1-A"),
        "default_ag_level": index.get("default_ag_level", 1),
        "compatible_scenarios": index.get("compatible_scenarios", []),
    }
    
    # Загрузка core
    core = load_module(index_dir, "core/IDENTITY.json")
    if core:
        persona.update({
            "anatomic_anchor": core.get("anatomic_anchor", {}),
            "visual_signature": core.get("visual_signature", ""),
            "archetype": core.get("archetype", ""),
            "persona_type": core.get("persona_type", "user_proxy"),
        })
    
    # Загрузка levels (14 подуровней)
    levels = {}
    for sublevel in [
        "U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A",
        "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B"
    ]:
        lvl = load_module(index_dir, f"levels/{sublevel}.json")
        if lvl:
            cyr = sublevel.replace("U", "У").replace("A", "А").replace("B", "Б")
            levels[cyr] = lvl
    if levels:
        persona["levels"] = levels
        # Извлекаем vscno, internal_state, ad
        persona["vscno_by_sublevel"] = {}
        persona["internal_state_by_sublevel"] = {}
        persona["ad_by_sublevel"] = {}
        for cyr, lvl in levels.items():
            vscno = lvl.get("vscno", {})
            if vscno:
                persona["vscno_by_sublevel"][cyr] = vscno
            internal = lvl.get("internal_state", {})
            if internal:
                persona["internal_state_by_sublevel"][cyr] = internal
            ad = lvl.get("ad_availability", {})
            if ad:
                persona["ad_by_sublevel"][cyr] = ad
    
    # Загрузка psychology
    psych = {}
    for name in ["BASE", "ATTACHMENT", "AROUSAL", "PLASTICITY", "TEC"]:
        mod = load_module(index_dir, f"psychology/{name}.json")
        if mod:
            psych.update(mod)
    if psych:
        persona["psychology"] = psych
    
    # Загрузка sexology
    sex = {}
    for name in ["RESPONSE_CYCLE", "EROTIC_SCRIPTS", "DYSPHORIA_AND_SHAME", "FANTASY_VS_REALITY"]:
        mod = load_module(index_dir, f"sexology/{name}.json")
        if mod:
            sex.update(mod)
    if sex:
        persona["intimacy_preferences"] = sex
    
    # Загрузка visual
    visual = {}
    for name in ["PROMPT_BASE", "GENERATION_HISTORY"]:
        mod = load_module(index_dir, f"visual/{name}.json")
        if mod:
            visual.update(mod)
    if visual:
        persona["visual_data"] = visual
    
    # Загрузка dynamics
    dynamics = {}
    for name in ["REACTION_PATTERNS", "LEVEL_LOCK_MATRIX", "EMOTIONAL_INFLUENCE_MATRIX", "CONFLICT_RESOLUTION_MATRIX"]:
        mod = load_module(index_dir, f"dynamics/{name}.json")
        if mod:
            dynamics.update(mod)
    if dynamics:
        persona["dynamics"] = dynamics
    
    # Загрузка memory
    memory = {}
    for name in ["TRUST", "ATTRACTION", "FLAGS", "HISTORY", "EMOTIONAL_ANCHORS"]:
        mod = load_module(index_dir, f"memory/{name}.json")
        if mod:
            memory[name.lower()] = mod
    if memory:
        persona["memory"] = memory
    
    # Загрузка relationships
    rel = load_module(index_dir, "relationships/MATRIX.json")
    if rel:
        persona["relationships"] = rel.get("relationships", [])
    
    # Загрузка environment
    env = load_module(index_dir, "environment/STATE_TRIGGERS.json")
    if env:
        persona["state_triggers"] = env.get("state_triggers", {})
    
    # Загрузка safety
    safety = load_module(index_dir, "safety/PROTOCOL.json")
    if safety:
        persona["safety"] = safety
    
    # Загрузка speech
    speech = load_module(index_dir, "speech/SPEECH_MATRIX.json")
    if speech:
        persona["speech_matrix"] = speech.get("matrix", {})
        persona["speech_signature_patterns"] = speech.get("signature_patterns", {})
    
    # Загрузка autonomous
    auto = {}
    for name in ["ACTIVITIES", "TEMPLATES", "INITIATIVE"]:
        mod = load_module(index_dir, f"autonomous/{name}.json")
        if mod:
            auto.update(mod)
    if auto:
        persona["autonomous"] = auto
    
    # Загрузка meta
    meta = load_module(index_dir, "meta/META.json")
    if meta:
        persona["meta"] = meta.get("meta", {})
        persona["chat_display_name"] = meta.get("chat_display_name", "")
        persona["algorithms"] = meta.get("algorithms", [])
        persona["format"] = meta.get("format", [])
        persona["volume"] = meta.get("volume", {})
        persona["scenarios"] = meta.get("scenarios", [])
        persona["engagement"] = meta.get("engagement", {})
    
    return persona

# =============================================================================
# ВАЛИДАЦИЯ
# =============================================================================

def validate_modular_persona(persona: Dict) -> Dict[str, Any]:
    """
    Валидирует загруженного модульного персонажа.
    Возвращает словарь {проверка: (статус, комментарий)}.
    """
    results = {}
    
    # 1. Базовые поля
    required = ["id", "name", "version"]
    missing = [f for f in required if f not in persona or not persona[f]]
    results["basic_fields"] = ("PASS" if not missing else "FAIL", 
                               f"Отсутствуют: {missing}" if missing else "Все поля на месте")
    
    # 2. Levels
    levels = persona.get("levels", {})
    results["levels"] = ("PASS" if len(levels) >= 14 else "FAIL",
                         f"{len(levels)}/14 подуровней" if len(levels) < 14 else "Все 14 подуровней")
    
    # 3. VSCNO
    vscno = persona.get("vscno_by_sublevel", {})
    vscno_ok = True
    vscno_issues = []
    for lvl, vals in vscno.items():
        total = sum(v for v in vals.values() if isinstance(v, (int, float)))
        if total != 10:
            vscno_ok = False
            vscno_issues.append(f"{lvl}: {total}")
    results["vscno"] = ("PASS" if vscno_ok else "WARNING",
                        "Все суммы = 10" if vscno_ok else f"Несоответствия: {vscno_issues[:3]}")
    
    # 4. Safety
    safety = persona.get("safety", {})
    has_stop = bool(safety.get("stop_words", []))
    has_emergency = bool(safety.get("emergency_phrase", "") or safety.get("emergency_response", ""))
    has_hard = bool(safety.get("hard_limits", []))
    safety_ok = has_stop and has_emergency and has_hard
    results["safety"] = ("PASS" if safety_ok else "WARNING",
                       "Все протоколы на месте" if safety_ok else "Некоторые поля отсутствуют")
    
    # 5. Core
    core_ok = bool(persona.get("anatomic_anchor", {}))
    results["core"] = ("PASS" if core_ok else "FAIL", "anatomic_anchor загружен" if core_ok else "Отсутствует")
    
    # 6. Speech Matrix
    speech_matrix = persona.get("speech_matrix", {})
    has_speech = len(speech_matrix) >= 10  # минимум 10 уровней
    results["speech"] = ("PASS" if has_speech else "FAIL",
                         f"{len(speech_matrix)} подуровней речевой матрицы" if speech_matrix else "Отсутствует SPEECH_MATRIX.json")
    
    # 7. Autonomous Initiative
    auto = persona.get("autonomous", {})
    has_initiative = bool(auto.get("initiative_types", {}))
    has_activities = bool(auto.get("activities", {}))
    has_templates = bool(auto.get("message_templates", {}))
    auto_ok = has_initiative and has_activities and has_templates
    results["autonomous"] = ("PASS" if auto_ok else "WARNING",
                             f"INITIATIVE: {'yes' if has_initiative else 'no'}, ACTIVITIES: {'yes' if has_activities else 'no'}, TEMPLATES: {'yes' if has_templates else 'no'}")
    
    return results

# =============================================================================
# ТЕСТОВЫЙ ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python runtime_loader.py <char_id>")
        print("Example: python runtime_loader.py andrey_senior")
        sys.exit(1)
    
    char_id = sys.argv[1]
    print(f"Loading modular persona: {char_id}")
    
    persona = load_modular_persona(char_id)
    if not persona:
        print(f"ERROR: Persona '{char_id}' not found")
        sys.exit(1)
    
    print(f"Loaded: {persona['name']} (v{persona['version']})")
    print(f"Levels: {len(persona.get('levels', {}))}")
    print(f"VSCNO entries: {len(persona.get('vscno_by_sublevel', {}))}")
    print(f"Safety: {'yes' if 'safety' in persona else 'no'}")
    
    print("\nValidation:")
    results = validate_modular_persona(persona)
    for check, (status, comment) in results.items():
        print(f"  [{status}] {check}: {comment}")
    
    overall = all(r[0] == "PASS" for r in results.values())
    print(f"\nOverall: {'PASS' if overall else 'FAIL'}")
