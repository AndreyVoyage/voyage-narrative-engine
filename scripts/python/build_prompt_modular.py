#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Modular Prompt Builder v1.0
Собирает промпт из модульного сценария + модульных персонажей.

Usage:
    python build_prompt_modular.py [scenario_id] [mode] [variant]
    
Examples:
    python build_prompt_modular.py sauna_extended standard
    python build_prompt_modular.py sauna_extended compact
    python build_prompt_modular.py sauna_extended extended AG3
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

REPO_DIR = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REPO_DIR / "scenarios"
PERSONAS_DIR = REPO_DIR / "personas"
OUTPUT_FILE = REPO_DIR / "PROMPT_MODULAR.txt"

sys.path.insert(0, str(REPO_DIR / "scripts" / "python"))
from runtime_loader import load_modular_persona

# =============================================================================
# ЗАГРУЗКА СЦЕНАРИЯ
# =============================================================================

def load_scenario(scenario_id: str) -> dict:
    """Загружает модульный сценарий из scenarios/[id]/"""
    scenario_dir = SCENARIOS_DIR / scenario_id
    if not scenario_dir.exists():
        raise FileNotFoundError(f"Scenario not found: {scenario_dir}")
    
    # Load core index
    index_path = scenario_dir / "core" / "INDEX.json"
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    
    # Load phases
    phases = {}
    scenes_dir = scenario_dir / "scenes"
    if scenes_dir.exists():
        for phase_file in sorted(scenes_dir.glob("*.json")):
            with open(phase_file, "r", encoding="utf-8") as f:
                phase_data = json.load(f)
                phase_name = phase_file.stem
                phases[phase_name] = phase_data
    
    # Load characters/roles
    roles_path = scenario_dir / "characters" / "ROLES.json"
    roles = {}
    if roles_path.exists():
        with open(roles_path, "r", encoding="utf-8") as f:
            roles = json.load(f)
    
    # Load structure
    structure = {}
    for name in ["phases", "timeline", "locations"]:
        path = scenario_dir / "structure" / f"{name}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                structure[name] = json.load(f)
    
    # Load branches
    branches_path = scenario_dir / "branches" / "BRANCHES.json"
    branches = {}
    if branches_path.exists():
        with open(branches_path, "r", encoding="utf-8") as f:
            branches = json.load(f)
    
    # Load environment
    env_path = scenario_dir / "environment" / "ATMOSPHERE.json"
    atmosphere = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            atmosphere = json.load(f)
    
    # Load safety
    safety_path = scenario_dir / "safety" / "SAFETY.json"
    safety = {}
    if safety_path.exists():
        with open(safety_path, "r", encoding="utf-8") as f:
            safety = json.load(f)
    
    # Load dynamics
    dynamics_path = scenario_dir / "dynamics" / "CROSS_CHARACTER.json"
    dynamics = {}
    if dynamics_path.exists():
        with open(dynamics_path, "r", encoding="utf-8") as f:
            dynamics = json.load(f)
    
    return {
        "id": scenario_id,
        "meta": index,
        "phases": phases,
        "roles": roles,
        "structure": structure,
        "branches": branches,
        "atmosphere": atmosphere,
        "safety": safety,
        "dynamics": dynamics,
    }

# =============================================================================
# СБОРКА ПРОМПТА
# =============================================================================

def format_speech_matrix(speech_matrix: dict, signature_patterns: dict) -> str:
    """Форматирует речевую матрицу для промпта"""
    lines = []
    lines.append("## РЕЧЕВАЯ МАТРИЦА (Speech Matrix)")
    lines.append("")
    
    # Signature patterns
    if signature_patterns:
        lines.append("### Signature Patterns (ключевые паттерны речи):")
        for pattern_name, description in signature_patterns.items():
            lines.append(f"- **{pattern_name}**: {description}")
        lines.append("")
    
    # Matrix levels (only key levels for brevity)
    key_levels = ["U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A", "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A"]
    lines.append("### Speech Matrix by Level:")
    lines.append("")
    
    for level in key_levels:
        if level not in speech_matrix:
            continue
        data = speech_matrix[level]
        lines.append(f"#### {level}")
        lines.append(f"- **Тон**: {data.get('ton', '')}")
        lines.append(f"- **Темп**: {data.get('tempo', '')}")
        lines.append(f"- **Словарь**: {data.get('vocabulary', '')}")
        lines.append(f"- **Длина мысли**: {data.get('thought_length', '')}")
        lines.append(f"- **Детальность действий**: {data.get('action_detail', '')}")
        
        # Signature phrases
        phrases = data.get('signature_phrases', [])
        if phrases:
            lines.append(f"- **Фразы-ключи**: {phrases[0]}")
            if len(phrases) > 1:
                lines.append(f"  - {phrases[1]}")
        
        # Action-speech pairs (first 2)
        pairs = data.get('action_speech_pairs', [])
        if pairs:
            lines.append(f"- **Пример**: [{pairs[0]['action']}] → \"{pairs[0]['speech']}\"")
        
        lines.append("")
    
    return "\n".join(lines)

def format_initiatives(initiative_data: dict) -> str:
    """Форматирует инициативы для промпта"""
    lines = []
    lines.append("## АВТОНОМНЫЕ ИНИЦИАТИВЫ (Autonomous Initiatives)")
    lines.append("")
    
    initiative_types = initiative_data.get("initiative_types", {})
    for name, data in initiative_types.items():
        lines.append(f"### {name}")
        lines.append(f"- **Описание**: {data.get('description', '')}")
        
        # AG probabilities
        prob = data.get("probability_by_ag", {})
        if prob:
            probs = ", ".join([f"AG{k[-1]}={v}" for k, v in prob.items()])
            lines.append(f"- **Вероятности**: {probs}")
        
        # Triggers
        triggers = data.get("triggers", [])
        if triggers:
            lines.append(f"- **Триггеры**: {', '.join(triggers)}")
        
        lines.append("")
    
    # Rules
    rules = initiative_data.get("initiative_rules", {})
    if isinstance(rules, dict) and rules:
        lines.append("### Правила инициатив:")
        # Description if present
        desc = rules.get("description", "")
        if desc:
            lines.append(f"- **Описание**: {desc}")
        # Rules list if present
        rules_list = rules.get("rules", [])
        if rules_list:
            for rule in rules_list:
                lines.append(f"- {rule}")
        # Standard fields
        if "default_ag" in rules:
            lines.append(f"- **AG по умолчанию**: {rules.get('default_ag', 'AG1')}")
        if "max_initiatives_per_scene" in rules:
            lines.append(f"- **Макс инициатив/сцену**: {rules.get('max_initiatives_per_scene', 1)}")
        if "cooldown_seconds" in rules:
            lines.append(f"- **Cooldown**: {rules.get('cooldown_seconds', 60)} сек")
        lines.append("")
    elif isinstance(rules, list) and rules:
        lines.append("### Правила инициатив:")
        for rule in rules:
            lines.append(f"- {rule}")
        lines.append("")
    
    return "\n".join(lines)

def format_activities(activities_data: dict) -> str:
    """Форматирует активности для промпта"""
    lines = []
    lines.append("## АКТИВНОСТИ ПЕРСОНАЖА (Activities)")
    lines.append("")
    
    activities = activities_data.get("activities", {})
    
    # Handle dict format (new personas: marina, sergey, maksim, andrey)
    if isinstance(activities, dict):
        for name, data in activities.items():
            lines.append(f"- **{name}**: {data.get('description', '')}")
            lines.append(f"  Длительность: {data.get('duration_seconds', 0)}с, Прерываемо: {data.get('interruptible', True)}")
    
    # Handle list format (Kira's older schema)
    elif isinstance(activities, list):
        for act in activities:
            if isinstance(act, dict):
                act_id = act.get('id', 'unknown')
                act_name = act.get('name', act_id)
                lines.append(f"- **{act_name}**: {act.get('description', '')}")
                lines.append(f"  Локация: {act.get('location', 'any')}, Вероятность: {act.get('probability', 0)}")
    
    lines.append("")
    return "\n".join(lines)

def format_relationships(rel_matrix: dict) -> str:
    """Форматирует матрицу отношений"""
    lines = []
    lines.append("## ОТНОШЕНИЯ (Relationships)")
    lines.append("")
    
    relationships = rel_matrix.get("relationships", {})
    for target_id, rel in relationships.items():
        trust = rel.get("trust", 0)
        attraction = rel.get("attraction", 0)
        label = rel.get("relationship_label", "")
        desc = rel.get("description", "")
        lines.append(f"- **{target_id}**: доверие={trust}, влечение={attraction}, {label} — {desc}")
    
    lines.append("")
    return "\n".join(lines)

def build_persona_section(persona: dict) -> str:
    """Собирает секцию одного персонажа"""
    lines = []
    lines.append(f"# ПЕРСОНАЖ: {persona.get('name', 'Unknown').upper()} (ID: {persona.get('id', '')})")
    lines.append(f"Версия: {persona.get('version', '')}")
    lines.append("")
    
    # Psychology (brief)
    psych = persona.get("psychology", {})
    if psych:
        core = psych.get("core", {})
        if core:
            lines.append("## ПСИХОЛОГИЯ")
            lines.append(f"- **Конфликт**: {core.get('core_conflict', 'N/A')}")
            lines.append(f"- **Тайное желание**: {core.get('secret_desire', 'N/A')}")
            lines.append(f"- **Сенсорный регистр**: {core.get('sensory_register', 'N/A')}")
            lines.append("")
    
    # Speech Matrix
    speech_matrix = persona.get("speech_matrix", {})
    signature_patterns = persona.get("speech_signature_patterns", {})
    if speech_matrix:
        lines.append(format_speech_matrix(speech_matrix, signature_patterns))
    
    # Initiatives
    auto = persona.get("autonomous", {})
    initiative_data = auto if isinstance(auto, dict) and "initiative_types" in auto else {}
    if initiative_data and isinstance(initiative_data, dict):
        lines.append(format_initiatives(initiative_data))
    
    # Activities
    activities_data = auto if isinstance(auto, dict) and "activities" in auto else {}
    if activities_data and isinstance(activities_data, dict):
        try:
            lines.append(format_activities(activities_data))
        except Exception as e:
            lines.append(f"<!-- Error formatting activities: {e} -->")
            lines.append("")
    
    # Relationships
    rel = persona.get("relationships", {})
    if rel and isinstance(rel, dict):
        lines.append(format_relationships(rel))
    
    # Levels (VSCNO summary)
    vscno = persona.get("vscno_by_sublevel", {})
    if vscno:
        lines.append("## VSCNO (по подуровням)")
        lines.append("| Уровень | ВЛ | СТ | НЖ | ОГ |")
        lines.append("|---------|----|----|----|----|")
        for level in sorted(vscno.keys()):
            vals = vscno[level]
            vl = vals.get("ВЛ", "?")
            st = vals.get("СТ", "?")
            nz = vals.get("НЖ", "?")
            og = vals.get("ОГ", "?")
            lines.append(f"| {level} | {vl} | {st} | {nz} | {og} |")
        lines.append("")
    
    return "\n".join(lines)

def build_scenario_section(scenario: dict) -> str:
    """Собирает секцию сценария"""
    lines = []
    meta = scenario.get("meta", {})
    lines.append(f"# СЦЕНАРИЙ: {meta.get('name', 'Unknown')} (ID: {meta.get('id', '')})")
    lines.append(f"Версия: {meta.get('version', '')}")
    lines.append(f"Синопсис: {meta.get('synopsis', '')}")
    lines.append("")
    
    # Participants
    participants = meta.get("participants", [])
    if participants:
        lines.append(f"**Участники**: {', '.join(participants)}")
    lines.append(f"**AG Range**: {meta.get('ag_range', 'AG1-AG4')}")
    lines.append(f"**POV Switching**: {meta.get('pov_switching', 'no')}")
    lines.append(f"**NPC-to-NPC**: {meta.get('npc_to_npc', 'no')}")
    lines.append("")
    
    # Phases
    phases = scenario.get("phases", {})
    if phases:
        lines.append("## ФАЗЫ СЦЕНАРИЯ")
        lines.append("")
        for phase_name, phase_data in phases.items():
            lines.append(f"### {phase_name}")
            desc = phase_data.get("description", "")
            if desc:
                lines.append(f"{desc}")
            chars = phase_data.get("characters_present", [])
            if chars:
                lines.append(f"**Персонажи**: {', '.join(chars)}")
            loc = phase_data.get("location", "")
            if loc:
                lines.append(f"**Локация**: {loc}")
            lines.append("")
    
    # Roles
    roles = scenario.get("roles", {})
    if roles and "characters" in roles:
        lines.append("## РОЛИ ПЕРСОНАЖЕЙ В СЦЕНАРИИ")
        lines.append("")
        for char_id, role_data in roles["characters"].items():
            lines.append(f"### {char_id}")
            lines.append(f"- **Роль**: {role_data.get('role', '')}")
            lines.append(f"- **Описание**: {role_data.get('description', '')}")
            lines.append(f"- **Уровень**: {role_data.get('target_level_start', '')} → {role_data.get('target_level_end', '')}")
            lines.append("")
    
    # Atmosphere
    atmosphere = scenario.get("atmosphere", {})
    if atmosphere:
        lines.append("## АТМОСФЕРА")
        env = atmosphere.get("environment", {})
        if env:
            lines.append(f"- **Температура**: {env.get('temperature', 'N/A')}")
            lines.append(f"- **Влажность**: {env.get('humidity', 'N/A')}")
            lines.append(f"- **Освещение**: {env.get('lighting', 'N/A')}")
            lines.append(f"- **Звук**: {env.get('sound', 'N/A')}")
        lines.append("")
    
    # Safety
    safety = scenario.get("safety", {})
    if safety:
        lines.append("## БЕЗОПАСНОСТЬ СЦЕНАРИЯ")
        checks = safety.get("safety_checks", {})
        for check, status in checks.items():
            lines.append(f"- **{check}**: {status}")
        lines.append("")
    
    return "\n".join(lines)

def build_instructions(scenario_id: str, mode: str, ag_level: str) -> str:
    """Собирает инструкции для LLM"""
    lines = []
    lines.append("# ИНСТРУКЦИИ ДЛЯ LLM")
    lines.append("")
    lines.append(f"## Режим работы: {mode.upper()}")
    lines.append(f"## Сценарий: {scenario_id}")
    lines.append(f"## AG Level: {ag_level}")
    lines.append("")
    
    lines.append("""## ПРАВИЛА ГЕНЕРАЦИИ РЕЧИ

Для КАЖДОГО персонажа используй его РЕЧЕВУЮ МАТРИЦУ (Speech Matrix):
- Тон — определяет эмоциональный окрас (хриплый, робкий, авторитетный)
- Темп — определяет ритм (медленный, рваный, ускоренный)
- Словарь — ограничивает лексику (вульгарный, поэтичный, примитивный)
- Длина мысли — сколько слов в фразе (короткие 1-3, длинные 8-12)
- Детальность действий — что делает телом во время речи

Фразы-ключи — это ОБРАЗЦЫ, а не готовые реплики. Генерируй НОВЫЕ фразы в том же стиле.

## ПРАВИЛА АВТОНОМНОСТИ NPC

При AG≥3 персонажи МОГУТ действовать без команды пользователя:
- Каждая инициатива имеет probability_by_ag — шанс срабатывания
- Триггеры определяют, когда инициатива активируется
- VSCNO_mapping показывает, как действие меняет состояние персонажа
- Инициативы записываются в Event Log

## ФОРМАТ ВЫВОДА (ФМДР)

Каждый ответ ДОЛЖЕН содержать:
1. **Действия персонажа** (физические, мимика, поза)
2. **Речь персонажа** (в стиле его Speech Matrix)
3. **Мысли персонажа** (если POV позволяет)
4. **VSCNO обновление** (если состояние изменилось)

## КОМАНДЫ ПОЛЬЗОВАТЕЛЯ

- УX-А/Б — переключить уровень (например, У2-А)
- ТГX — изменить тревогу
- АД [код] — активировать драйвер
- Г [0-4] — изменить AG (0=пассив, 4=полная автономия)
- СТОП — мгновенный сброс всех персонажей на безопасные уровни
- [AUTO_VISUAL] — генерация визуального описания в конце ответа
""")
    
    return "\n".join(lines)

def build_prompt(scenario_id: str, mode: str = "standard", variant: str = "standard", ag_level: str = "AG3") -> str:
    """Главная функция сборки промпта"""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append(f"Voyage Narrative Engine — Modular Prompt")
    lines.append(f"Scenario: {scenario_id} | Mode: {mode} | AG: {ag_level}")
    lines.append(f"Built: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    # 1. Load and build scenario section
    try:
        scenario = load_scenario(scenario_id)
        lines.append(build_scenario_section(scenario))
    except Exception as e:
        lines.append(f"# ОШИБКА ЗАГРУЗКИ СЦЕНАРИЯ: {e}")
        lines.append("")
    
    # 2. Load and build persona sections
    participants = scenario.get("meta", {}).get("participants", []) if 'scenario' in locals() else []
    
    for char_id in participants:
        if char_id == "user":
            continue
        
        persona = load_modular_persona(char_id)
        if persona:
            lines.append(build_persona_section(persona))
        else:
            lines.append(f"# ПЕРСОНАЖ: {char_id} — НЕ НАЙДЕН")
            lines.append("")
    
    # 3. Instructions
    lines.append(build_instructions(scenario_id, mode, ag_level))
    
    # 4. Footer
    lines.append("=" * 80)
    lines.append("END OF PROMPT")
    lines.append("=" * 80)
    
    return "\n".join(lines)

# =============================================================================
# CLI
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python build_prompt_modular.py <scenario_id> [mode] [ag_level]")
        print("Examples:")
        print("  python build_prompt_modular.py sauna_extended standard AG3")
        print("  python build_prompt_modular.py sauna_extended compact AG1")
        print("  python build_prompt_modular.py sauna_extended extended AG4")
        sys.exit(1)
    
    scenario_id = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "standard"
    ag_level = sys.argv[3] if len(sys.argv) > 3 else "AG3"
    
    print(f"Building modular prompt for: {scenario_id}")
    print(f"Mode: {mode}, AG: {ag_level}")
    print("")
    
    prompt = build_prompt(scenario_id, mode, ag_level)
    
    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    size = len(prompt)
    lines = prompt.count("\n")
    
    print(f"✓ Prompt built: {OUTPUT_FILE}")
    print(f"  Size: {size} bytes ({size/1024:.1f} KB)")
    print(f"  Lines: {lines}")
    
    # Check persona loading
    scenario = load_scenario(scenario_id)
    participants = scenario.get("meta", {}).get("participants", [])
    print(f"\nLoaded personas:")
    for char_id in participants:
        if char_id == "user":
            continue
        persona = load_modular_persona(char_id)
        if persona:
            speech_levels = len(persona.get("speech_matrix", {}))
            initiatives = len(persona.get("autonomous", {}).get("initiative_types", {}))
            activities = len(persona.get("autonomous", {}).get("activities", {}))
            print(f"  ✓ {char_id}: speech={speech_levels} levels, initiatives={initiatives}, activities={activities}")
        else:
            print(f"  ✗ {char_id}: NOT FOUND")

if __name__ == "__main__":
    main()
