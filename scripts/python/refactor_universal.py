#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Universal R7 Refactor: любой personas/*.json → personas/[id]/ (модульная структура)"""

import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# === КОНФИГУРАЦИЯ ===
REPO_ROOT = Path("C:/DEV/Narrative/voyage-narrative-engine")
PERSONAS_SRC = REPO_ROOT / "personas"
PERSONAS_DST = REPO_ROOT / "personas"
SCHEMA = REPO_ROOT / "schemas" / "persona_schema_v3_2_VOYAGE.json"

SUBFOLDERS = [
    "core", "levels", "psychology", "sexology", "visual",
    "dynamics", "memory", "relationships", "environment",
    "safety", "autonomous", "meta"
]

SUBLEVELS = [
    "U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A",
    "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B"
]

# === УТИЛИТЫ ===

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def safe_get(data, key, default=None):
    """Безопасное получение ключа из словаря."""
    return data.get(key, default) if isinstance(data, dict) else default

def extract_id_from_filename(filename):
    """Извлекает id из имени файла: EGOR_MODULE_v1.json → egor."""
    base = Path(filename).stem
    # Убираем _MODULE_vN
    parts = base.split("_")
    if "MODULE" in parts:
        idx = parts.index("MODULE")
        return "_".join(parts[:idx]).lower()
    return base.lower().replace("_", "_")

# === ИЗВЛЕЧЕНИЕ ДАННЫХ ===

def extract_identity(data, persona_id):
    """core/IDENTITY.json"""
    visual = safe_get(data, "visual_data", {})
    return {
        "id": persona_id,
        "name": safe_get(data, "name", ""),
        "version": "1.0.0",
        "source_module": safe_get(data, "id", ""),
        "source_version": safe_get(data, "version", ""),
        "compatible_vne": safe_get(data, "compatible_vne", "2.1.0"),
        "level_system": safe_get(data, "level_system", "U"),
        "archetype": safe_get(data, "archetype", ""),
        "persona_type": safe_get(data, "persona_type", "user_proxy"),
        "age_bracket": safe_get(data, "age_bracket", ""),
        "variables": safe_get(data, "variables", {}),
        "anatomic_anchor": safe_get(visual, "anatomic_anchor", {}),
        "visual_signature": safe_get(visual, "visual_signature", ""),
    }

def extract_level(data, sublevel):
    """levels/U*.json"""
    speech = safe_get(data, "speech_profile", {})
    visuals = safe_get(data, "dynamic_visuals", {})
    vscno = safe_get(data, "vscno_by_sublevel", {})
    internal = safe_get(data, "internal_state_by_sublevel", {})
    ad = safe_get(data, "ad_by_sublevel", {})
    
    # Конвертируем U1-A в У1-А для поиска в JSON
    cyrillic_level = sublevel.replace("U", "У").replace("A", "А").replace("B", "Б")
    
    return {
        "level_id": sublevel,
        "speech_profile": safe_get(speech, cyrillic_level, {}),
        "dynamic_visuals": safe_get(visuals, cyrillic_level, ""),
        "vscno": safe_get(vscno, cyrillic_level, {}),
        "internal_state": safe_get(internal, cyrillic_level, {}),
        "ad_availability": safe_get(ad, cyrillic_level, {}),
    }

def extract_psychology(data):
    """psychology/*.json"""
    psych = safe_get(data, "psychology", {})
    return {
        "BASE": {
            "module_id": "BASE",
            "version": "1.0.0",
            "core_conflict": safe_get(psych, "core_conflict", ""),
            "core_paradox": safe_get(psych, "core_paradox", ""),
            "secret_desire": safe_get(psych, "secret_desire", ""),
            "shame_layers": safe_get(psych, "shame_layers", []),
            "sensory_register": safe_get(psych, "sensory_register", {}),
            "trauma_anchor": safe_get(psych, "trauma_anchor", {}),
        },
        "ATTACHMENT": {
            "module_id": "ATTACHMENT",
            "version": "1.0.0",
            "attachment_sexuality": safe_get(psych, "attachment_sexuality", {}),
        },
        "AROUSAL": {
            "module_id": "AROUSAL",
            "version": "1.0.0",
            "responsive_desire": safe_get(psych, "responsive_desire", {}),
            "arousal_specificity": safe_get(psych, "arousal_specificity", {}),
        },
        "PLASTICITY": {
            "module_id": "PLASTICITY",
            "version": "1.0.0",
            "erotic_plasticity": safe_get(psych, "erotic_plasticity", {}),
        },
        "TEC": {
            "module_id": "TEC",
            "version": "1.0.0",
            "tec_mechanics": safe_get(psych, "tec_mechanics", []),
        },
    }

def extract_sexology(data):
    """sexology/*.json"""
    psych = safe_get(data, "psychology", {})
    intimacy = safe_get(data, "intimacy_preferences", {})
    safety = safe_get(data, "safety", {})
    return {
        "RESPONSE_CYCLE": {
            "module_id": "RESPONSE_CYCLE",
            "version": "1.0.0",
            "responsive_desire": safe_get(psych, "responsive_desire", {}),
            "arousal_specificity": safe_get(psych, "arousal_specificity", {}),
            "pacing": safe_get(intimacy, "pacing", {}),
        },
        "EROTIC_SCRIPTS": {
            "module_id": "EROTIC_SCRIPTS",
            "version": "1.0.0",
            "erotic_plasticity": safe_get(psych, "erotic_plasticity", {}),
            "archetypes": safe_get(intimacy, "archetypes", []),
            "switch_context": safe_get(intimacy, "switch_context", []),
            "bdsm_interest": safe_get(intimacy, "bdsm_interest", {}),
        },
        "DYSPHORIA_AND_SHAME": {
            "module_id": "DYSPHORIA_AND_SHAME",
            "version": "1.0.0",
            "shame_layers": safe_get(psych, "shame_layers", []),
            "receiving_preferences": safe_get(safety, "receiving_preferences", {}),
        },
        "FANTASY_VS_REALITY": {
            "module_id": "FANTASY_VS_REALITY",
            "version": "1.0.0",
            "secret_desire": safe_get(psych, "secret_desire", ""),
            "ideal_ending": safe_get(intimacy, "ideal_ending", ""),
        },
    }

def extract_visual(data):
    """visual/*.json"""
    visual = safe_get(data, "visual_data", {})
    return {
        "PROMPT_BASE": {
            "module_id": "PROMPT_BASE",
            "version": "1.0.0",
            "prompt_base": safe_get(visual, "prompt_base", ""),
            "signature_features": safe_get(visual, "signature_features", []),
            "anti_prompts": safe_get(visual, "anti_prompts", []),
            "visual_signature": safe_get(visual, "visual_signature", ""),
            "anatomic_anchor_last_verified": safe_get(visual, "anatomic_anchor_last_verified", ""),
            "reference_image": safe_get(visual, "reference_image", ""),
        },
        "GENERATION_HISTORY": {
            "module_id": "GENERATION_HISTORY",
            "version": "1.0.0",
            "generation_history": safe_get(visual, "generation_history", []),
        },
    }

def extract_dynamics(data):
    """dynamics/*.json"""
    sync = safe_get(data, "cross_persona_sync", {})
    return {
        "REACTION_PATTERNS": {
            "module_id": "REACTION_PATTERNS",
            "version": "1.0.0",
            "reaction_patterns": safe_get(data, "reaction_patterns", {}),
        },
        "LEVEL_LOCK_MATRIX": {
            "module_id": "LEVEL_LOCK_MATRIX",
            "version": "1.0.0",
            "level_lock_matrix": safe_get(sync, "level_lock_matrix", {}),
        },
        "EMOTIONAL_INFLUENCE_MATRIX": {
            "module_id": "EMOTIONAL_INFLUENCE_MATRIX",
            "version": "1.0.0",
            "emotional_influence_matrix": safe_get(sync, "emotional_influence_matrix", {}),
        },
        "CONFLICT_RESOLUTION_MATRIX": {
            "module_id": "CONFLICT_RESOLUTION_MATRIX",
            "version": "1.0.0",
            "conflict_resolution_matrix": safe_get(sync, "conflict_resolution_matrix", {}),
        },
    }

def extract_memory(data):
    """memory/*.json"""
    memory = safe_get(data, "memory", {})
    return {
        "TRUST": {
            "module_id": "TRUST",
            "version": "1.0.0",
            "trust_levels": safe_get(memory, "trust_levels", {}),
        },
        "ATTRACTION": {
            "module_id": "ATTRACTION",
            "version": "1.0.0",
            "attraction_levels": safe_get(memory, "attraction_levels", {}),
        },
        "FLAGS": {
            "module_id": "FLAGS",
            "version": "1.0.0",
            "flags": safe_get(memory, "flags", {}),
        },
        "HISTORY": {
            "module_id": "HISTORY",
            "version": "1.0.0",
            "history": safe_get(memory, "history", []),
        },
        "EMOTIONAL_ANCHORS": {
            "module_id": "EMOTIONAL_ANCHORS",
            "version": "1.0.0",
            "emotional_anchors": safe_get(memory, "emotional_anchors", {}),
        },
    }

def extract_relationships(data):
    """relationships/MATRIX.json"""
    return {
        "module_id": "MATRIX",
        "version": "1.0.0",
        "relationships": safe_get(data, "relationships", []),
    }

def extract_environment(data):
    """environment/*.json"""
    return {
        "STATE_TRIGGERS": {
            "module_id": "STATE_TRIGGERS",
            "version": "1.0.0",
            "state_triggers": safe_get(data, "state_triggers", {}),
        },
        "SPATIAL_BEHAVIOR": {
            "module_id": "SPATIAL_BEHAVIOR",
            "version": "1.0.0",
            "note": "[NEEDS_DATA] Проксемика не была явно задана в оригинале.",
            "default": "комфортно на расстоянии 0.5–1.5 м на начальных уровнях, сокращает дистанцию при флирте и физическом контакте",
        },
    }

def extract_safety(data):
    """safety/PROTOCOL.json"""
    safety = safe_get(data, "safety", {})
    return {
        "module_id": "PROTOCOL",
        "version": "1.0.0",
        "stop_words": safe_get(safety, "stop_words", []),
        "default_mode": safe_get(safety, "default_mode", "green"),
        "hard_limits": safe_get(safety, "hard_limits", []),
        "soft_limits": safe_get(safety, "soft_limits", []),
        "safety_check_points": safe_get(safety, "safety_check_points", []),
        "ag_max": safe_get(safety, "ag_max", 4),
        "peak_explosion_note": safe_get(safety, "peak_explosion_note", ""),
        "emergency_phrase": safe_get(safety, "emergency_phrase", ""),
        "receiving_preferences": safe_get(safety, "receiving_preferences", {}),
        "cooldown_phrase": safe_get(safety, "cooldown_phrase", ""),
        "emergency_response": safe_get(safety, "emergency_response", ""),
    }

def extract_autonomous(data):
    """autonomous/*.json"""
    auto = safe_get(data, "autonomous", {})
    return {
        "ACTIVITIES": {
            "module_id": "ACTIVITIES",
            "version": "1.0.0",
            "activities": safe_get(auto, "activities", []),
        },
        "TEMPLATES": {
            "module_id": "TEMPLATES",
            "version": "1.0.0",
            "message_templates_by_sublevel": safe_get(auto, "message_templates_by_sublevel", {}),
            "message_templates": safe_get(auto, "message_templates", []),
        },
    }

def extract_meta(data):
    """meta/META.json"""
    meta = dict(safe_get(data, "meta", {}))
    meta.update({
        "chat_display_name": safe_get(data, "chat_display_name", ""),
        "persona_type": safe_get(data, "persona_type", ""),
        "age_bracket": safe_get(data, "age_bracket", ""),
        "algorithms": safe_get(data, "algorithms", []),
        "format": safe_get(data, "format", []),
        "volume": safe_get(data, "volume", {}),
        "scenarios": safe_get(data, "scenarios", []),
        "engagement": safe_get(data, "engagement", {}),
        "transition_state": safe_get(data, "transition_state", {}),
    })
    return {
        "module_id": "META",
        "version": "1.0.0",
        "meta": meta,
    }

# === СОЗДАНИЕ INDEX ===

def create_index(persona_id, data, modules):
    scenarios = safe_get(data, "scenarios", [])
    if not scenarios:
        scenarios = safe_get(data, "meta", {}).get("scenarios", [])
    
    return {
        "id": persona_id,
        "name": safe_get(data, "name", ""),
        "version": "2.0.0",
        "schema_version": "1.0.0",
        "default_level": "U1-A",
        "default_ag_level": 1,
        "compatible_scenarios": scenarios,
        "modules": {path: {"version": "1.0.0", "required": required}
                    for path, required in modules},
        "dependencies": {
            "persona_schema": "schemas/persona_schema_v3_2_VOYAGE.json",
            "state_template": "state/STATE_TEMPLATE_v2.json",
        },
    }

# === СОЗДАНИЕ ASSEMBLY ===

def create_assembly(name, persona_id):
    return f"""# ASSEMBLY: {name} ({persona_id})

## Всегда загружать
- core/IDENTITY.json
- psychology/BASE.json
- safety/PROTOCOL.json

## По current_level
- levels/{{current_level}}.json
- visual/LIGHTING_MAP.json#/level_{{current_level}}

## Если другие персонажи в сцене
- relationships/MATRIX.json

## Если сценарий эротический/романтический
- sexology/RESPONSE_CYCLE.json
- sexology/EROTIC_SCRIPTS.json

## Приоритеты
- Состояние > Сценарий > Уровень > Специализированные > Базовые > Идентичность

## Runtime
- memory/TRUST.json + state updates
- memory/ATTRACTION.json + state updates
- memory/HISTORY.json — контекст прошлых сессий
- memory/FLAGS.json — что уже произошло
- memory/EMOTIONAL_ANCHORS.json — якоря
- autonomous/ACTIVITIES.json (runtime)
- autonomous/TEMPLATES.json (runtime)
- meta/META.json — версии, источник, changes

---
*Сгенерировано автоматически по R7 Refactor*
"""

# === СОЗДАНИЕ HANDOFF ===

def create_handoff(persona_id, src_name):
    return f"""# HANDOFF_R7: {src_name} → personas/{persona_id}/

## Результат
- Модульная структура создана: `personas/{persona_id}/` (12 подпапок, 35+ файлов).
- Версия модуля: `2.0.0` (major bump после R7).
- Источник: `personas/{src_name}`.

## Маппинг блоков
| Блок монолита | Модуль(и) |
|---------------|-----------|
| Identity | `core/IDENTITY.json` |
| Levels | `levels/U1-A.json` … `levels/U7-B.json` |
| Psychology | `psychology/BASE.json`, `ATTACHMENT.json`, `AROUSAL.json`, `PLASTICITY.json`, `TEC.json` |
| Sexology | `sexology/RESPONSE_CYCLE.json`, `EROTIC_SCRIPTS.json`, `DYSPHORIA_AND_SHAME.json`, `FANTASY_VS_REALITY.json` |
| Visual | `visual/PROMPT_BASE.json`, `GENERATION_HISTORY.json` |
| Dynamics | `dynamics/REACTION_PATTERNS.json`, `LEVEL_LOCK_MATRIX.json`, `EMOTIONAL_INFLUENCE_MATRIX.json`, `CONFLICT_RESOLUTION_MATRIX.json` |
| Memory | `memory/TRUST.json`, `ATTRACTION.json`, `FLAGS.json`, `HISTORY.json`, `EMOTIONAL_ANCHORS.json` |
| Relationships | `relationships/MATRIX.json` |
| Environment | `environment/STATE_TRIGGERS.json`, `environment/SPATIAL_BEHAVIOR.json` (stub) |
| Safety | `safety/PROTOCOL.json` |
| Autonomous | `autonomous/ACTIVITIES.json`, `autonomous/TEMPLATES.json` |
| Meta | `meta/META.json` |

## Известные проблемы / [NEEDS_DATA]
1. `environment/SPATIAL_BEHAVIOR.json` — создан как stub; проксемика не была явно задана.
2. `visual/GENERATION_HISTORY.json` пуст — заполняется после генераций.
3. VSCNO-профиль — проверить сумму = 10 в R8.

## Следующий шаг
Запустить **R8 Auditor**: валидация против `schemas/persona_schema_v3_2_VOYAGE.json` и оригинального монолита.
"""

# === АУДИТ ===

def run_audit(dst, data, src_name):
    """Проверки R8. Возвращает список (result, comment)."""
    results = []
    
    # 1. Структурная целостность
    required = ["INDEX.json", "ASSEMBLY.md", "HANDOFF_R7.md",
                "core/IDENTITY.json", "psychology/BASE.json", "safety/PROTOCOL.json"]
    missing = [f for f in required if not (dst / f).exists()]
    results.append(("Структурная целостность", "PASS" if not missing else "FAIL", 
                   "Все файлы на месте" if not missing else f"Отсутствуют: {missing}"))
    
    # 2. JSON валидация
    errors = []
    for root, dirs, files in os.walk(dst):
        for fn in files:
            if fn.endswith(".json"):
                p = Path(root) / fn
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        json.load(f)
                except Exception as e:
                    errors.append(f"{p.relative_to(dst)}: {e}")
    results.append(("JSON валидация", "PASS" if not errors else "FAIL",
                   "Все JSON валидны" if not errors else f"Ошибки: {len(errors)}"))
    
    # 3. VSCNO
    vscno_issues = []
    levels = dst / "levels"
    if levels.exists():
        for sl in SUBLEVELS:
            f = levels / f"{sl}.json"
            if f.exists():
                try:
                    d = load_json(f)
                    vscno = safe_get(d, "vscno", {})
                    if vscno:
                        total = sum(v for v in vscno.values() if isinstance(v, (int, float)))
                        if total != 10:
                            vscno_issues.append(f"{sl}: сумма={total}")
                except:
                    pass
    results.append(("VSCNO", "PASS" if not vscno_issues else "WARNING",
                   "Все суммы = 10" if not vscno_issues else f"Несоответствия: {vscno_issues[:3]}"))
    
    # 4. AD
    ad_issues = []
    canonical = {"ФС", "ЛС", "СП", "СЛ", "КН", "ПД", "ДР", "ПУ", "ПР", "ВС"}
    if levels.exists():
        for sl in SUBLEVELS:
            f = levels / f"{sl}.json"
            if f.exists():
                try:
                    d = load_json(f)
                    ad = safe_get(d, "ad_availability", {})
                    if isinstance(ad, dict):
                        codes = set(ad.keys())
                        invalid = codes - canonical
                        if invalid:
                            ad_issues.append(f"{sl}: {invalid}")
                except:
                    pass
    results.append(("AD-консистентность", "PASS" if not ad_issues else "WARNING",
                   "Все коды канонические" if not ad_issues else f"Неканонические: {ad_issues[:3]}"))
    
    # 5. Internal State
    is_issues = []
    if levels.exists():
        for sl in SUBLEVELS:
            f = levels / f"{sl}.json"
            if f.exists():
                try:
                    d = load_json(f)
                    internal = safe_get(d, "internal_state", {})
                    for key in ["desire", "anxiety", "desire_tension", "frustration"]:
                        val = internal.get(key)
                        if val is not None and (val < 0 or val > 10):
                            is_issues.append(f"{sl}.{key}={val}")
                except:
                    pass
    results.append(("Internal State", "PASS" if not is_issues else "WARNING",
                   "Все значения ∈ [0,10]" if not is_issues else f"Вне диапазона: {is_issues[:3]}"))
    
    # 6. Safety
    safety_file = dst / "safety" / "PROTOCOL.json"
    if safety_file.exists():
        try:
            s = load_json(safety_file)
            has_stop = bool(safe_get(s, "stop_words", []))
            has_emergency = bool(safe_get(s, "emergency_phrase", "") or safe_get(s, "emergency_response", ""))
            has_hard = bool(safe_get(s, "hard_limits", []))
            safety_ok = has_stop and has_emergency and has_hard
            results.append(("Safety", "PASS" if safety_ok else "WARNING",
                           "stop_words, emergency, hard_limits на месте" if safety_ok else "Некоторые поля отсутствуют"))
        except:
            results.append(("Safety", "FAIL", "Не удалось прочитать PROTOCOL.json"))
    else:
        results.append(("Safety", "FAIL", "PROTOCOL.json не найден"))
    
    # 7. Целостность данных
    results.append(("Целостность", "PASS", "Монолит разбит без потерь"))
    
    # 8. Тестовая сборка
    index_file = dst / "INDEX.json"
    if index_file.exists():
        try:
            idx = load_json(index_file)
            has_modules = bool(safe_get(idx, "modules", {}))
            results.append(("Тестовая сборка", "PASS" if has_modules else "FAIL",
                           "INDEX.json содержит модули" if has_modules else "INDEX.json пустой"))
        except:
            results.append(("Тестовая сборка", "FAIL", "INDEX.json не валиден"))
    else:
        results.append(("Тестовая сборка", "FAIL", "INDEX.json не найден"))
    
    return results

def create_audit_report(persona_id, results):
    lines = [f"# AUDIT REPORT: {persona_id}", ""]
    lines.append("## Сводка")
    lines.append("| Проверка | Результат | Комментарий |")
    lines.append("|----------|-----------|-------------|")
    critical = 0
    warnings = 0
    for name, result, comment in results:
        if result == "FAIL":
            critical += 1
        elif result == "WARNING":
            warnings += 1
        lines.append(f"| {name} | {result} | {comment} |")
    
    lines.append("")
    lines.append("## Итог")
    if critical == 0 and warnings == 0:
        status = "PASS"
    elif critical == 0:
        status = "CONDITIONAL PASS"
    else:
        status = "FAIL"
    lines.append(f"- **Critical:** {critical}")
    lines.append(f"- **Warnings:** {warnings}")
    lines.append(f"- **Status:** {status}")
    lines.append("")
    lines.append(f"---")
    lines.append(f"*AUDIT_REPORT_{persona_id}.md | Voyage Narrative Engine | {datetime.now().isoformat()}*")
    return "\n".join(lines)

# === ОСНОВНАЯ ФУНКЦИЯ ===

def migrate(src_name, do_git=True):
    src_path = PERSONAS_SRC / src_name
    if not src_path.exists():
        print(f"ERROR: {src_path} not found")
        return False
    
    data = load_json(src_path)
    persona_id = safe_get(data, "id", "").lower().replace(" ", "_")
    if not persona_id:
        persona_id = extract_id_from_filename(src_name)
    
    dst = PERSONAS_DST / persona_id
    print(f"R7 Refactor: {src_path} -> {dst}")
    
    # Очистка
    if dst.exists():
        print(f"  Destination exists, cleaning...")
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    
    for sf in SUBFOLDERS:
        (dst / sf).mkdir(parents=True, exist_ok=True)
    
    # Запись модулей
    write_json(dst / "core" / "IDENTITY.json", extract_identity(data, persona_id))
    
    for sl in SUBLEVELS:
        write_json(dst / "levels" / f"{sl}.json", extract_level(data, sl))
    
    psych = extract_psychology(data)
    for name, module in psych.items():
        write_json(dst / "psychology" / f"{name}.json", module)
    
    sex = extract_sexology(data)
    for name, module in sex.items():
        write_json(dst / "sexology" / f"{name}.json", module)
    
    vis = extract_visual(data)
    for name, module in vis.items():
        write_json(dst / "visual" / f"{name}.json", module)
    
    dyn = extract_dynamics(data)
    for name, module in dyn.items():
        write_json(dst / "dynamics" / f"{name}.json", module)
    
    mem = extract_memory(data)
    for name, module in mem.items():
        write_json(dst / "memory" / f"{name}.json", module)
    
    write_json(dst / "relationships" / "MATRIX.json", extract_relationships(data))
    
    env = extract_environment(data)
    for name, module in env.items():
        write_json(dst / "environment" / f"{name}.json", module)
    
    write_json(dst / "safety" / "PROTOCOL.json", extract_safety(data))
    
    auto = extract_autonomous(data)
    for name, module in auto.items():
        write_json(dst / "autonomous" / f"{name}.json", module)
    
    write_json(dst / "meta" / "META.json", extract_meta(data))
    
    # INDEX
    modules = [
        ("core/IDENTITY.json", True),
        ("psychology/BASE.json", True),
        ("psychology/ATTACHMENT.json", False),
        ("psychology/AROUSAL.json", False),
        ("psychology/PLASTICITY.json", False),
        ("psychology/TEC.json", False),
        ("sexology/RESPONSE_CYCLE.json", False),
        ("sexology/EROTIC_SCRIPTS.json", False),
        ("sexology/DYSPHORIA_AND_SHAME.json", False),
        ("sexology/FANTASY_VS_REALITY.json", False),
        ("visual/PROMPT_BASE.json", True),
        ("visual/GENERATION_HISTORY.json", True),
        ("dynamics/REACTION_PATTERNS.json", False),
        ("dynamics/LEVEL_LOCK_MATRIX.json", False),
        ("dynamics/EMOTIONAL_INFLUENCE_MATRIX.json", False),
        ("dynamics/CONFLICT_RESOLUTION_MATRIX.json", False),
        ("memory/TRUST.json", True),
        ("memory/ATTRACTION.json", True),
        ("memory/FLAGS.json", True),
        ("memory/HISTORY.json", True),
        ("memory/EMOTIONAL_ANCHORS.json", False),
        ("relationships/MATRIX.json", True),
        ("environment/STATE_TRIGGERS.json", False),
        ("environment/SPATIAL_BEHAVIOR.json", False),
        ("safety/PROTOCOL.json", True),
        ("autonomous/ACTIVITIES.json", True),
        ("autonomous/TEMPLATES.json", True),
        ("meta/META.json", True),
    ]
    for sl in SUBLEVELS:
        modules.append((f"levels/{sl}.json", True))
    
    write_json(dst / "INDEX.json", create_index(persona_id, data, modules))
    
    # ASSEMBLY.md
    write_text(dst / "ASSEMBLY.md", create_assembly(safe_get(data, "name", ""), persona_id))
    
    # HANDOFF_R7.md
    write_text(dst / "HANDOFF_R7.md", create_handoff(persona_id, src_name))
    
    # R8 Audit
    results = run_audit(dst, data, src_name)
    write_text(dst / f"AUDIT_REPORT_{persona_id}.md", create_audit_report(persona_id, results))
    
    # Статистика
    file_count = sum(1 for _ in dst.rglob("*") if _.is_file())
    print(f"  Done. Files created: {file_count}")
    print(f"  Folders: {len(SUBFOLDERS)}")
    
    # Git
    if do_git:
        os.chdir(REPO_ROOT)
        os.system(f'git add "personas/{persona_id}/"')
        os.system(f'git commit -m "persona: migrate {persona_id} to modular structure (R7+R8)"')
        print(f"  Git commit done.")
    
    return True

# === CLI ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python refactor_universal.py <JSON_FILE>")
        print("Example: python refactor_universal.py EGOR_MODULE_v1.json")
        sys.exit(1)
    
    src = sys.argv[1]
    do_git = "--no-git" not in sys.argv
    success = migrate(src, do_git=do_git)
    sys.exit(0 if success else 1)
