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
import argparse
from pathlib import Path
from datetime import datetime

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

REPO_DIR = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REPO_DIR / "scenarios"
PERSONAS_DIR = REPO_DIR / "personas"
DEFAULT_OUTPUT_FILE = REPO_DIR / "reports" / "prompts" / "PROMPT_MODULAR.txt"

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
    
    # Load markdown scenes
    md_scenes = {}
    scenes_dir = scenario_dir / "scenes"
    if scenes_dir.exists():
        for md_file in scenes_dir.glob("*.md"):
            with open(md_file, "r", encoding="utf-8") as f:
                md_scenes[md_file.stem] = f.read()
    
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
        "md_scenes": md_scenes,
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
    
    # Visual Anchors (for image generation)
    visual = persona.get("visual_data", {})
    if visual and isinstance(visual, dict):
        lines.append("## ВИЗУАЛЬНЫЕ ЯКОРЯ (Visual Anchors for Image Generation)")
        prompt_base = visual.get("prompt_base", "")
        if prompt_base:
            lines.append(f"**Базовый промпт:** {prompt_base}")
        style = visual.get("style", "")
        if style:
            lines.append(f"**Стиль:** {style}")
        sig = visual.get("visual_signature", "")
        if sig:
            lines.append(f"**Визуальная сигнатура:** {sig}")
        variations = visual.get("prompt_variations", {})
        if variations:
            lines.append("**Вариации:**")
            for vname, vprompt in variations.items():
                lines.append(f"- {vname}: {vprompt}")
        anti = visual.get("anti_prompts", [])
        if anti:
            lines.append(f"**Anti-prompts:** {', '.join(anti)}")
        lines.append("")
    
    return "\n".join(lines)

def build_scenario_section(scenario: dict) -> str:
    """Собирает ПОЛНУЮ секцию сценария (все модули)"""
    lines = []
    meta = scenario.get("meta", {})
    lines.append(f"# СЦЕНАРИЙ: {meta.get('name', 'Unknown')} (ID: {meta.get('id', '')})")
    lines.append(f"Версия: {meta.get('version', '')}")
    lines.append(f"Синопсис: {meta.get('synopsis', '')}")
    lines.append("")
    
    participants = meta.get("participants", [])
    if participants:
        lines.append(f"**Участники**: {', '.join(participants)}")
    lines.append(f"**AG Range**: {meta.get('ag_range', 'AG1-AG4')}")
    lines.append(f"**POV Switching**: {meta.get('pov_switching', 'no')}")
    lines.append(f"**NPC-to-NPC**: {meta.get('npc_to_npc', 'no')}")
    lines.append("")
    
    # Locations
    locations = scenario.get("structure", {}).get("locations", {})
    if locations:
        loc = locations.get("location", {})
        if loc:
            lines.append("## ЛОКАЦИИ (Locations)")
            lines.append(f"Название: {loc.get('name', '')}")
            lines.append(f"Тип: {loc.get('type', '')}")
            lines.append(f"Этажи: {loc.get('floors', '')}")
            lines.append(f"Температура: {loc.get('temperature_range', '')}")
            lines.append(f"Освещение: {loc.get('lighting', '')}")
            lines.append(f"Атмосфера: {loc.get('atmosphere', '')}")
            lines.append(f"Звук: {loc.get('soundscape', '')}")
            lines.append("")
            anchors = loc.get("sensory_anchors", {})
            if anchors:
                lines.append("### Сенсорные якоря:")
                for name, desc in anchors.items():
                    lines.append(f"- **{name}**: {desc}")
                lines.append("")
        time = locations.get("time", {})
        if time:
            lines.append("### Время:")
            lines.append(f"- Сезон: {time.get('season', '')}")
            lines.append(f"- Время суток: {time.get('time_of_day', '')}")
            lines.append(f"- Начало: {time.get('start_time', '')}")
            lines.append(f"- Конец: {time.get('end_time', '')}")
            lines.append(f"- Нарративное: {time.get('narrative_time', '')}")
            lines.append("")
    
    # Timeline
    timeline = scenario.get("structure", {}).get("timeline", {})
    timeline_items = timeline.get("timeline", [])
    if timeline_items:
        lines.append("## ТАЙМЛАЙН (Timeline)")
        for item in timeline_items:
            lines.append(f"### {item.get('phase_id', '')}: {item.get('name', '')}")
            lines.append(f"- Длительность: {item.get('duration_minutes', 0)} мин")
            lines.append(f"- Локация: {item.get('location', '')}")
            lines.append(f"- Описание: {item.get('description', '')}")
            lines.append(f"- Ожидаемое настроение: {item.get('expected_mood', '')}")
            flags = item.get('flags_set', [])
            if flags:
                lines.append(f"- Флаги: {', '.join(flags)}")
            lines.append("")
    
    # Phases (detailed with triggers & character states)
    phases = scenario.get("structure", {}).get("phases", {})
    phases_data = phases.get("phases", {})
    if phases_data:
        lines.append("## ДЕТАЛЬНЫЕ ФАЗЫ (Phases with Triggers & Character States)")
        for phase_id, phase in phases_data.items():
            lines.append(f"### {phase_id}: {phase.get('name', '')}")
            lines.append(f"- Длительность: {phase.get('duration_minutes', 0)} мин")
            lines.append(f"- Локация: {phase.get('location', '')}")
            lines.append(f"- Описание: {phase.get('description', '')}")
            lines.append(f"- Ожидаемое настроение: {phase.get('expected_mood', '')}")
            lines.append(f"- POV правила: {phase.get('pov_rules', '')}")
            
            char_states = phase.get("character_states", {})
            if char_states:
                lines.append("- **Состояния персонажей:**")
                for char, state in char_states.items():
                    lines.append(f"  - {char}: target={state.get('target_level','')}, desire_delta={state.get('desire_delta',0)}, anxiety_delta={state.get('anxiety_delta',0)}")
            
            triggers = phase.get("triggers", [])
            if triggers:
                lines.append("- **Триггеры:**")
                for t in triggers:
                    lines.append(f"  - [{t.get('type','')}] → {t.get('target','')}: {t.get('effect','')}")
            
            safety_checks = phase.get("safety_checks", [])
            if safety_checks:
                lines.append(f"- **Safety checks:** {', '.join(safety_checks)}")
            
            flags = phase.get("flags_set", [])
            if flags:
                lines.append(f"- **Флаги:** {', '.join(flags)}")
            lines.append("")
    
    # Markdown scenes
    md_scenes = scenario.get("md_scenes", {})
    if md_scenes:
        lines.append("## РАСШИРЕННЫЕ СЦЕНЫ (Extended Markdown Scenes)")
        for name, content in md_scenes.items():
            lines.append(f"### {name}")
            lines.append(content)
            lines.append("")
    
    # Roles
    roles = scenario.get("roles", {})
    if roles and "characters" in roles:
        lines.append("## РОЛИ ПЕРСОНАЖЕЙ В СЦЕНАРИИ")
        for char_id, role_data in roles["characters"].items():
            lines.append(f"### {char_id}")
            lines.append(f"- **Роль**: {role_data.get('role', '')}")
            lines.append(f"- **Описание**: {role_data.get('description', '')}")
            lines.append(f"- **Уровень**: {role_data.get('target_level_start', '')} → {role_data.get('target_level_end', '')}")
            lines.append("")
    
    # Branches
    branches = scenario.get("branches", {})
    branches_data = branches.get("branches", {})
    if branches_data:
        lines.append("## ВЕТКИ СЦЕНАРИЯ (Branches)")
        for bid, bdata in branches_data.items():
            lines.append(f"### {bid}: {bdata.get('name', '')}")
            lines.append(f"- **Описание**: {bdata.get('description', '')}")
            lines.append(f"- **Триггер**: {bdata.get('trigger', '')}")
            lines.append(f"- **Условия**: {', '.join(bdata.get('conditions', []))}")
            result = bdata.get("result", {})
            if result:
                lines.append("- **Результаты:**")
                for char, res in result.items():
                    lines.append(f"  - {char}: {res}")
            fmdr = bdata.get("fmdr_climax", "")
            if fmdr:
                lines.append(f"- **FMDR Climax:** {fmdr}")
            safety_after = bdata.get("safety_aftercare", "")
            if safety_after:
                lines.append(f"- **Aftercare:** {safety_after}")
            lines.append("")
    
    # Dynamics
    dynamics = scenario.get("dynamics", {})
    dynamics_data = dynamics.get("dynamics", {})
    if dynamics_data:
        lines.append("## ДИНАМИКА МЕЖДУ ПЕРСОНАЖАМИ (Cross-Character Dynamics)")
        for pair, ddata in dynamics_data.items():
            lines.append(f"### {pair}")
            lines.append(f"- **Динамика**: {ddata.get('dynamic', '')}")
            lines.append(f"- **Описание**: {ddata.get('description', '')}")
            stages = ddata.get("stages", [])
            if stages:
                lines.append("- **Стадии:**")
                for st in stages:
                    lines.append(f"  - {st.get('stage','')} ({st.get('phase','')}): {st.get('description','')}")
            mechanics = ddata.get("key_mechanics", [])
            if mechanics:
                lines.append("- **Механики:**")
                for m in mechanics:
                    lines.append(f"  - {m}")
            triangles = ddata.get("triangles", [])
            if triangles:
                lines.append(f"- **Треугольники:** {', '.join(triangles)}")
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
        hard_limits = safety.get("hard_limits", [])
        if hard_limits:
            lines.append(f"- **Hard limits:** {', '.join(hard_limits)}")
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


# --- Режим SEPARATE: отдельные файлы на каждого персонажа + триггерная подгрузка ---

from datetime import datetime

def build_separate(scenario_id: str, mode: str = "standard", ag_level: str = "AG3"):
    """
    Собирает сценарий и каждого персонажа в ОТДЕЛЬНЫЕ файлы.
    Создаёт:
      - PROMPT_SCENARIO.txt
      - PROMPT_[char_id].txt (для каждого персонажа)
      - TRIGGER_GUIDE.txt (инструкции для LLM по триггерной подгрузке)
    """
    repo_dir = REPO_DIR
    scenario = load_scenario(scenario_id)
    participants = scenario.get("meta", {}).get("participants", [])
    npc_ids = [c for c in participants if c != "user"]
    
    built_files = []
    
    # 1. SCENARIO — отдельный файл
    scenario_lines = []
    scenario_lines.append("=" * 80)
    scenario_lines.append("Voyage Narrative Engine — Scenario Prompt (STANDALONE)")
    scenario_lines.append(f"Scenario: {scenario_id} | Mode: {mode} | AG: {ag_level}")
    scenario_lines.append(f"Built: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    scenario_lines.append("=" * 80)
    scenario_lines.append("")
    scenario_lines.append("# INSTRUCTIONS FOR LLM: Load this FIRST. Then load personas on demand via triggers.")
    scenario_lines.append("# Each persona has a TRIGGER_CODE listed below. When trigger fires, load the persona file.")
    scenario_lines.append("")
    scenario_lines.append(build_scenario_section(scenario))
    
    # Add trigger map inside scenario
    scenario_lines.append("## TRIGGER MAP (Persona Loading Codes)")
    scenario_lines.append("When a trigger fires, load the corresponding persona file into context:")
    for char_id in npc_ids:
        scenario_lines.append(f"- **[LOAD_{char_id.upper()}]** → Load PROMPT_{char_id.upper()}.txt")
    scenario_lines.append("")
    scenario_lines.append("## КОМАНДЫ ПОЛЬЗОВАТЕЛЯ")
    scenario_lines.append("- УX-А/Б — переключить уровень")
    scenario_lines.append("- ТГX — изменить тревогу")
    scenario_lines.append("- АД [код] — активировать драйвер")
    scenario_lines.append("- Г [0-4] — изменить AG")
    scenario_lines.append("- СТОП — мгновенный сброс")
    scenario_lines.append("")
    scenario_lines.append("=" * 80)
    scenario_lines.append("END OF SCENARIO PROMPT")
    scenario_lines.append("=" * 80)
    
    scenario_text = "\n".join(scenario_lines)
    scenario_path = repo_dir / "PROMPT_SCENARIO.txt"
    with open(scenario_path, "w", encoding="utf-8") as f:
        f.write(scenario_text)
    built_files.append(("PROMPT_SCENARIO.txt", len(scenario_text)))
    
    # 2. PERSONAS — каждый в отдельный файл, ПОЛНЫЙ (не сокращённый)
    for char_id in npc_ids:
        persona = load_modular_persona(char_id)
        if not persona:
            continue
        
        plines = []
        plines.append("=" * 80)
        plines.append(f"Voyage Narrative Engine — Persona Prompt: {persona.get('name', char_id).upper()}")
        plines.append(f"ID: {char_id} | Version: {persona.get('version', '')} | AG: {ag_level}")
        plines.append(f"Built: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        plines.append("=" * 80)
        plines.append("")
        plines.append(f"# INSTRUCTIONS FOR LLM: This is persona '{char_id}'. Load ONLY after scenario is loaded.")
        plines.append(f"# TRIGGER CODE: [LOAD_{char_id.upper()}]")
        plines.append("")
        
        # FULL persona data — same as build_persona_section but with ALL levels
        plines.append(build_persona_section_full(persona))
        
        # Trigger-based activation rules
        plines.append("## ТРИГГЕРНАЯ АКТИВАЦИЯ (Trigger-Based Loading)")
        plines.append(f"This persona activates when:")
        plines.append(f"- Scenario phase includes this character")
        plines.append(f"- User interacts with this character")
        plines.append(f"- Cross-character dynamics involve this character (see TRIGGER_GUIDE.txt)")
        plines.append(f"- NPC-to-NPC interaction triggers this character's initiative")
        plines.append("")
        
        plines.append("=" * 80)
        plines.append(f"END OF PERSONA PROMPT: {char_id.upper()}")
        plines.append("=" * 80)
        
        ptext = "\n".join(plines)
        ppath = repo_dir / f"PROMPT_{char_id.upper()}.txt"
        with open(ppath, "w", encoding="utf-8") as f:
            f.write(ptext)
        built_files.append((f"PROMPT_{char_id.upper()}.txt", len(ptext)))
    
    # 3. TRIGGER GUIDE — инструкции для LLM
    tlines = []
    tlines.append("=" * 80)
    tlines.append("Voyage Narrative Engine — Trigger-Based Loading Guide")
    tlines.append("This file tells the LLM WHEN and HOW to load persona modules.")
    tlines.append("=" * 80)
    tlines.append("")
    tlines.append("## ПРИНЦИП РАБОТЫ")
    tlines.append("1. Сначала загружается PROMPT_SCENARIO.txt (сценарий + триггер-карта).")
    tlines.append("2. LLM ведёт игру с минимальным контекстом (сценарий + текущие персонажи).")
    tlines.append("3. Когда срабатывает триггер — LLM загружает соответствующий PROMPT_[ID].txt.")
    tlines.append("4. Загруженный персонаж остаётся в контексте до конца сессии или до команды СТОП.")
    tlines.append("5. Это позволяет не перегружать контекст сразу всеми 5 персонажами.")
    tlines.append("")
    tlines.append("## ТРИГГЕРЫ ЗАГРУЗКИ ПЕРСОНАЖЕЙ")
    tlines.append("")
    
    # Extract triggers from scenario phases
    phases_data = scenario.get("structure", {}).get("phases", {}).get("phases", {})
    for phase_id, phase in phases_data.items():
        triggers = phase.get("triggers", [])
        char_states = phase.get("character_states", {})
        for trig in triggers:
            t_type = trig.get("type", "")
            t_target = trig.get("target", "")
            t_effect = trig.get("effect", "")
            # Determine which persona to load
            for char_id in npc_ids:
                if char_id in t_target or char_id in t_effect.lower():
                    tlines.append(f"- **[{phase_id}]** trigger `{t_type}` → target `{t_target}` → **LOAD [LOAD_{char_id.upper()}]** (PROMPT_{char_id.upper()}.txt)")
                    tlines.append(f"  Effect: {t_effect}")
        # Also load by character presence in phase
        for char_id, state in char_states.items():
            if char_id in npc_ids:
                tlines.append(f"- **[{phase_id}]** character_state `{char_id}` → target `{state.get('target_level','')}` → **LOAD [LOAD_{char_id.upper()}]**")
    
    tlines.append("")
    tlines.append("## РУЧНЫЕ КОМАНДЫ ЗАГРУЗКИ (для пользователя)")
    tlines.append("Пользователь может вручную загрузить персонажа командой:")
    for char_id in npc_ids:
        tlines.append(f"- **ЗАГРУЗИ {char_id.upper()}** → LLM загружает PROMPT_{char_id.upper()}.txt в контекст")
    tlines.append("")
    tlines.append("## АВТОМАТИЧЕСКАЯ ВЫГРУЗКА")
    tlines.append("Персонаж автоматически выгружается из контекста если:")
    tlines.append("- Пользователь покидает локацию, где персонаж отсутствует")
    tlines.append("- Прошло более 30 минут без упоминания персонажа (AG≥3)")
    tlines.append("- Команда ВЫГРУЗИ [ID]")
    tlines.append("")
    tlines.append("=" * 80)
    tlines.append("END OF TRIGGER GUIDE")
    tlines.append("=" * 80)
    
    ttext = "\n".join(tlines)
    tpath = repo_dir / "TRIGGER_GUIDE.txt"
    with open(tpath, "w", encoding="utf-8") as f:
        f.write(ttext)
    built_files.append(("TRIGGER_GUIDE.txt", len(ttext)))
    
    return built_files

def build_persona_section_full(persona: dict) -> str:
    """Собирает ПОЛНУЮ секцию персонажа (без сокращений)"""
    lines = []
    lines.append(f"# ПЕРСОНАЖ: {persona.get('name', 'Unknown').upper()} (ID: {persona.get('id', '')})")
    lines.append(f"Версия: {persona.get('version', '')}")
    lines.append("")
    
    # Core / Identity
    core = persona.get("anatomic_anchor", {})
    if core:
        lines.append("## CORE / IDENTITY")
        for k, v in core.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    
    # Psychology (FULL)
    psych = persona.get("psychology", {})
    if psych:
        lines.append("## ПСИХОЛОГИЯ (Полная)")
        for section, data in psych.items():
            if isinstance(data, dict):
                lines.append(f"### {section}")
                for k, v in data.items():
                    lines.append(f"- **{k}**: {v}")
            else:
                lines.append(f"- **{section}**: {data}")
        lines.append("")
    
    # Speech Matrix (FULL — все уровни)
    speech_matrix = persona.get("speech_matrix", {})
    signature_patterns = persona.get("speech_signature_patterns", {})
    if speech_matrix:
        lines.append("## РЕЧЕВАЯ МАТРИЦА (Speech Matrix — ALL LEVELS)")
        lines.append("")
        if signature_patterns:
            lines.append("### Signature Patterns:")
            for pn, pd in signature_patterns.items():
                lines.append(f"- **{pn}**: {pd}")
            lines.append("")
        lines.append("### All Levels:")
        for level in sorted(speech_matrix.keys()):
            data = speech_matrix[level]
            lines.append(f"#### {level}")
            lines.append(f"- **Тон**: {data.get('ton', '')}")
            lines.append(f"- **Темп**: {data.get('tempo', '')}")
            lines.append(f"- **Словарь**: {data.get('vocabulary', '')}")
            lines.append(f"- **Длина мысли**: {data.get('thought_length', '')}")
            lines.append(f"- **Детальность действий**: {data.get('action_detail', '')}")
            phrases = data.get('signature_phrases', [])
            if phrases:
                lines.append(f"- **Фразы-ключи**: {phrases}")
            pairs = data.get('action_speech_pairs', [])
            if pairs:
                for p in pairs:
                    lines.append(f"- **Пример**: [{p.get('action','')}] → \"{p.get('speech','')}\"")
            lines.append("")
    
    # Initiatives (FULL)
    auto = persona.get("autonomous", {})
    initiative_data = auto if isinstance(auto, dict) and "initiative_types" in auto else {}
    if initiative_data:
        lines.append(format_initiatives(initiative_data))
    
    # Activities (FULL)
    activities_data = auto if isinstance(auto, dict) and "activities" in auto else {}
    if activities_data:
        lines.append(format_activities(activities_data))
    
    # Relationships (FULL)
    rel = persona.get("relationships", {})
    if rel and isinstance(rel, dict):
        lines.append(format_relationships(rel))
    
    # VSCNO (FULL — all levels)
    vscno = persona.get("vscno_by_sublevel", {})
    if vscno:
        lines.append("## VSCNO (ПО ВСЕМ ПОДУРОВНЯМ)")
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
    
    # Levels (FULL — all 14 sublevels)
    levels = persona.get("levels", {})
    if levels:
        lines.append("## LEVELS (Полные данные по 14 подуровням)")
        for level in sorted(levels.keys()):
            lvl = levels[level]
            lines.append(f"### {level}")
            for k, v in lvl.items():
                if isinstance(v, dict):
                    lines.append(f"- **{k}**:")
                    for vk, vv in v.items():
                        lines.append(f"  - {vk}: {vv}")
                else:
                    lines.append(f"- **{k}**: {v}")
            lines.append("")
    
    # Visual Anchors (FULL — for image generation)
    visual = persona.get("visual_data", {})
    if visual and isinstance(visual, dict):
        lines.append("## ВИЗУАЛЬНЫЕ ЯКОРЯ (Visual Anchors for Image Generation)")
        prompt_base = visual.get("prompt_base", "")
        if prompt_base:
            lines.append(f"**Базовый промпт:** {prompt_base}")
        style = visual.get("style", "")
        if style:
            lines.append(f"**Стиль:** {style}")
        sig = visual.get("visual_signature", "")
        if sig:
            lines.append(f"**Визуальная сигнатура:** {sig}")
        variations = visual.get("prompt_variations", {})
        if variations:
            lines.append("**Вариации:**")
            for vname, vprompt in variations.items():
                lines.append(f"- {vname}: {vprompt}")
        anti = visual.get("anti_prompts", [])
        if anti:
            lines.append(f"**Anti-prompts:** {', '.join(anti)}")
        lines.append("")
    
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Voyage modular prompt from a scenario and personas."
    )
    parser.add_argument("scenario_id", help="Scenario id, e.g. sauna_extended")
    parser.add_argument("mode", nargs="?", default="standard", help="Build mode")
    parser.add_argument("ag_level", nargs="?", default="AG3", help="Autonomy governor level")
    parser.add_argument("--separate", action="store_true", help="Build separate prompt files")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_FILE.relative_to(REPO_DIR)),
        help="Single-file output path, relative to repo root unless absolute",
    )
    return parser.parse_args(argv)


def resolve_output_path(output: str) -> Path:
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = REPO_DIR / output_path
    return output_path


def main():
    args = parse_args(sys.argv[1:])

    scenario_id = args.scenario_id
    mode = args.mode
    ag_level = args.ag_level

    # Check for --separate flag
    separate_mode = args.separate

    if separate_mode:
        print(f"Building SEPARATE prompts for: {scenario_id}")
        print(f"Mode: {mode}, AG: {ag_level}")
        print("Each persona gets its own file + scenario + trigger guide.")
        print("")
        
        built_files = build_separate(scenario_id, mode, ag_level)
        
        print("=" * 60)
        print("✓ SEPARATE PROMPTS BUILT")
        print("=" * 60)
        for fname, size in built_files:
            print(f"  {fname}: {size} bytes ({size/1024:.1f} KB)")
        print("")
        print("Next steps:")
        print("  1. Load PROMPT_SCENARIO.txt FIRST")
        print("  2. Load personas on demand via triggers (see TRIGGER_GUIDE.txt)")
        print("  3. Or load all at once if context allows")
        return
    
    # Default: single-file mode
    print(f"Building single-file modular prompt for: {scenario_id}")
    print(f"Mode: {mode}, AG: {ag_level}")
    print("")
    
    prompt = build_prompt(scenario_id, mode, ag_level)
    
    # Write output
    output_file = resolve_output_path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    size = len(prompt)
    lines = prompt.count("\n")
    
    print(f"✓ Prompt built: {output_file}")
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
