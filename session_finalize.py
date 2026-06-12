#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Session Finalizer v2.1
Исправление критических проблем v2.0:
  - Trust/Attraction читаются из persona.memory (не из internal_state)
  - VSCNO корректируется через max_axis (не через ОГ)
  - Safety gate: Visual Extractor останавливается на СТОП
  - JSON Schema валидация (--validate)
  - Emergency stop в Narrative Editor
  - Пути относительно расположения скрипта (работает из корня репозитория)
  - Graceful error handling без sys.exit

Usage:
  python session_finalize.py --log sessions/raw/session_2026-06-08.log --scenario sauna_quartet
  python session_finalize.py --log session.log --scenario shy_bloom --dry-run --verbose
  python session_finalize.py --log session.log --scenario sauna_quartet --validate
"""

import json
import re
import os
import sys
import argparse
import shutil
import subprocess
import glob
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# =============================================================================
# КОНФИГУРАЦИЯ (относительно расположения скрипта)
# =============================================================================

# REPO_DIR = директория, где лежит этот скрипт (корень репозитория)
REPO_DIR = Path(__file__).resolve().parent
SESSIONS_DIR = REPO_DIR / "sessions"
PERSONAS_DIR = REPO_DIR / "personas"
STATE_DIR = REPO_DIR / "state"
ASSETS_DIR = REPO_DIR / "assets" / "images"
SCHEMA_PATH = REPO_DIR / "schemas" / "persona_schema_v3_2_VOYAGE.json"

# VSCNO defaults (инвариант: сумма = 10)
VSCNO_DEFAULTS = {
    "kira":   {"ВЛ": 2, "СТ": 3, "НЖ": 3, "ОГ": 2},
    "sergey": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 4},
    "marina": {"ВЛ": 1, "СТ": 2, "НЖ": 4, "ОГ": 3},
    "maksim": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3},
    "olga_module_v2": {"ВЛ": 3, "СТ": 1, "НЖ": 1, "ОГ": 3},
    "user_default": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "sergey_module_v4": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 3},
    "sergey_v3": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "sergey_v2": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "maksim_001": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "marina_module_v2": {"ВЛ": 1, "СТ": 2, "НЖ": 4, "ОГ": 3},
    "marina_001": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "maksim_module_v2": {"ВЛ": 3, "СТ": 2, "НЖ": 3, "ОГ": 2},
    "kira_module_v14": {"ВЛ": 2, "СТ": 3, "НЖ": 3, "ОГ": 2},
    "kira_v12": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "kira_v11": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "female_user_001": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "andrey_senior_module": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "andrey_junior_module": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 2},
    "andrey_senior": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3},
    "andrey_junior": {"ВЛ": 2, "СТ": 3, "НЖ": 2, "ОГ": 2},
}

LEVEL_SIGNATURES = {
    "kira": {
        "U1-A": ["не знаю", "может быть", "не уверена", "спокойно", "нейтральн"],
        "U1-B": ["интересно", "неожиданно", "первый блеск", "слегка заинтересован"],
        "U2-A": ["ты меня провоцируешь", "не такая простая", "игрив", "дистанц"],
        "U2-B": ["просто поправила", "тебе жарко", "случайно", "неосознанн"],
        "U3-A": ["не должна так думать", "почему ты смотришь", "дрожь", "покраснел"],
        "U3-B": ["я хочу", "ты мой финиш", "признание", "слёзы на грани"],
        "U4-A": ["не могу", "только не остановись", "пассивное подчинение", "тремор"],
        "U4-B": ["забудь ту девочку", "я выбираю это", "осознанный выбор", "холодная решимость"],
        "U5-A": ["ты ещё не видел", "настоящая меня", "стервозн", "провокации"],
        "U5-B": ["смотри", "запоминай", "ты мой", "миниум слов"],
        "U6-A": ["ползи", "ты заслужил", "докажи", "повелительниц"],
        "U6-B": ["поцелуй мою ногу", "здесь", "публичн", "он мой"],
        "U7-A": ["испортила всё", "ты всё ещё хочешь", "раскаяние", "плач"],
        "U7-B": ["я желанна любая", "целостн", "интегрирован", "моя сила"],
    },
    "sergey": {
        "S1": ["смотрю", "интересно", "не торопись", "нейтральн", "сканирование"],
        "S2": ["ты справишься", "покажи", "зеркало", "подстёгивающий"],
        "S3": ["я рядом", "давай вместе", "союзник", "практическ"],
        "S4": ["не справишься", "заслуживает лучшего", "конкурент", "холодный вызов"],
        "S5": ["ладно", "не надо", "отстранение", "холодность", "отход"],
        "S6": ["всё нормально", "не плачь", "неуклюжая забота", "механическ"],
        "S7": ["хватит", "я ухожу", "не следуй", "полное закрытие"],
    },
    "marina": {
        "U1-A": ["не знаю", "может быть", "вы решайте", "замёрзшая", "невидим"],
        "U1-B": ["правда", "не думала", "интересно", "первый румянец"],
        "U2-A": ["ты смешной", "никогда не думала", "расскажи", "тёпл"],
        "U2-B": ["ты думаешь обо мне", "редко так говорю", "тепло здесь", "любопытств"],
        "U3-A": ["я тебе доверяю", "ты первый", "не уходи", "смеющийся"],
        "U3-B": ["ты мой", "я боюсь но хочу", "только ты", "доверчивый"],
        "U4-A": ["не могу", "только не остановись", "береги меня", "пассивн"],
        "U4-B": ["я хочу", "так как я сказала", "я выбираю тебя", "осознанный"],
        "U5-A": ["не знала что могу", "ещё", "в шоке", "удивлённая собственной смелостью"],
        "U5-B": ["ммм", "так хорошо", "не думай", "естественная сенсуальность"],
        "U6-A": ["а если так", "я рискну", "смеёмся", "игрив"],
        "U6-B": ["мне нужно", "именно так", "я заслужила", "уверенная"],
        "U7-A": ["ты всё ещё хочешь", "испортила всё", "верни как было", "страх потери"],
        "U7-B": ["я цветок", "открываюсь медленно", "целостн", "моя сила"],
    },
    "maksim": {
        "M1": ["ну что", "я принёс", "кто за", "весёлый", "лёгкий"],
        "M2": ["а ты что думаешь", "давайте все вместе", "марина расскажи", "включ"],
        "M3": ["всё хорошо", "я рядом", "ты молодец", "понимаю"],
        "M4": ["ты мне нравишься", "можно", "не торопить", "ты особенная"],
        "M5": ["я здесь", "навсегда", "ты моё счастье", "мы справимся"],
    }
}

LIGHTING_MAP = {
    "U1-A": "soft diffused, natural window light, neutral",
    "U1-B": "warm spot, side light, first interest",
    "U2-A": "warm spot, soft side light, playful",
    "U2-B": "dramatic Rembrandt, high contrast, intrigue",
    "U3-A": "dramatic Rembrandt, high contrast, conflict tension",
    "U3-B": "dramatic shadow, chiaroscuro, breakthrough tears",
    "U4-A": "dramatic shadow, chiaroscuro, surrender",
    "U4-B": "dramatic shadow, chiaroscuro, conscious choice",
    "U5-A": "neon saturated, high contrast, bitch emerges",
    "U5-B": "neon saturated, high contrast, natural dominance",
    "U6-A": "theatrical spotlight, public dominance",
    "U6-B": "theatrical spotlight, public humiliation as art",
    "U7-A": "soft morning, desaturated, repentance",
    "U7-B": "golden hour, warm fill, integration",
    "S1": "cool neutral, observational",
    "S2": "warm spot, side light, challenge",
    "S3": "neutral warm, ally cooperation",
    "S4": "dramatic shadow, cold competition",
    "S5": "flat fluorescent, cold withdrawal",
    "S6": "soft diffused, awkward care",
    "S7": "cold blue, monolithic shutdown",
    "M1": "bright daylight, open energy, social warmth",
    "M2": "warm indoor, connecting, bridge light",
    "M3": "soft golden, caring, supportive",
    "M4": "candle warm, intimate, gentle approach",
    "M5": "warm amber, devoted, committed",
}

SCENARIO_SENSORY = {
    "sauna_quartet": {
        "scents": ["эвкалипт", "берёзовый веник", "пот", "древесина", "шампунь"],
        "temperatures": ["жар 90°C", "контраст холода", "пар", "влажность"],
        "sounds": ["шипение пара", "капли воды", "тихий шёпот", "скрип деревянных полок"],
        "textures": ["гладкое дерево", "мокрое полотенце", "горячий камень", "прохладная плитка"],
    },
    "promenade": {
        "scents": ["осенний воздух", "кофе", "дождь", "листья"],
        "temperatures": ["прохлада", "ветер", "солнечный тёплый угол"],
        "sounds": ["шаги по лужам", "трамвай", "отдалённый смех", "шелест листьев"],
        "textures": ["мокрый асфальт", "шерсть пальто", "холодная рука в перчатке"],
    },
    "cafe_date": {
        "scents": ["свежемолотый кофе", "корица", "выпечка", "ваша колонья"],
        "temperatures": ["тёплый пар от кружки", "прохладный воздух у окна"],
        "sounds": ["стук ложек", "тихая музыка", "шепот бариста", "дождь за окном"],
        "textures": ["гладкая керамика кружки", "тёплый стол", "холодное стекло"],
    },
    "default": {
        "scents": ["ваш аромат", "её духи", "свежий воздух"],
        "temperatures": ["комнатная температура", "тепло от тела рядом"],
        "sounds": ["тишина", "дыхание", "шорох одежды"],
        "textures": ["ткань", "кожа", "дерево"],
    }
}

# =============================================================================
# ЛОГГИРОВАНИЕ
# =============================================================================

VERBOSE = False

def set_verbose(v: bool):
    global VERBOSE
    VERBOSE = v

def log(msg: str, level: str = "INFO"):
    prefix = {"INFO": "[INFO]", "WARN": "[WARN]", "ERROR": "[ERROR]", "DEBUG": "[DEBUG]"}.get(level, "[INFO]")
    print(f"{prefix} {msg}", file=sys.stderr if level in ("WARN", "ERROR") else sys.stdout)

def debug(msg: str):
    if VERBOSE:
        log(msg, "DEBUG")

# =============================================================================
# УТИЛИТЫ
# =============================================================================

def ensure_dirs():
    for d in [
        SESSIONS_DIR / "raw",
        SESSIONS_DIR / "state",
        SESSIONS_DIR / "memory",
        SESSIONS_DIR / "stories",
        SESSIONS_DIR / "visuals",
        ASSETS_DIR / "character_sessions" / "kira",
        ASSETS_DIR / "character_sessions" / "sergey",
        ASSETS_DIR / "character_sessions" / "marina",
        ASSETS_DIR / "character_sessions" / "maksim",
    ]:
        d.mkdir(parents=True, exist_ok=True)
        debug(f"Ensured dir: {d}")

def discover_persona(char_id: str) -> Optional[Path]:
    pattern = PERSONAS_DIR / f"{char_id.upper()}_MODULE_v*.json"
    matches = sorted(glob.glob(str(pattern)), key=lambda p: os.path.getmtime(p), reverse=True)
    if matches:
        return Path(matches[0])
    alt = PERSONAS_DIR / f"{char_id.upper()}_MODULE.json"
    if alt.exists():
        return alt
    return None

def load_persona(char_id: str) -> Optional[Dict]:
    path = discover_persona(char_id)
    if not path or not path.exists():
        log(f"Persona not found for '{char_id}'", "WARN")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "id" not in data or "name" not in data:
            log(f"Persona {path.name} missing required fields (id, name)", "WARN")
        return data
    except json.JSONDecodeError as e:
        log(f"Invalid JSON in {path}: {e}", "ERROR")
        return None

def save_persona(char_id: str, data: Dict):
    path = discover_persona(char_id)
    if not path:
        path = PERSONAS_DIR / f"{char_id.upper()}_MODULE_v1.json"
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f"Saved persona: {path}")
    except Exception as e:
        log(f"Failed to save persona {path}: {e}", "ERROR")

def validate_vscno(vscno: Dict[str, int], char_id: str) -> bool:
    total = sum(vscno.values())
    if total != 10:
        log(f"{char_id}: VSCNO sum={total} != 10 (ВЛ{vscno.get('ВЛ', '?')} СТ{vscno.get('СТ', '?')} НЖ{vscno.get('НЖ', '?')} ОГ{vscno.get('ОГ', '?')})", "WARN")
        return False
    return True

def fix_vscno(vscno: Dict[str, int]) -> Dict[str, int]:
    """Корректирует VSCNO до суммы 10, меняя наиболее гибкие оси."""
    total = sum(vscno.values())
    if total == 10:
        return vscno
    diff = 10 - total
    # 1. Корректируем ось с максимальным значением (наиболее гибкая)
    max_axis = max(vscno, key=vscno.get)
    vscno[max_axis] = max(0, min(4, vscno[max_axis] + diff))
    # 2. Если всё ещё не 10 — корректируем вторую по величине
    total2 = sum(vscno.values())
    if total2 != 10:
        second_axis = sorted(vscno, key=vscno.get, reverse=True)[1]
        vscno[second_axis] += (10 - total2)
        # Гарантируем границы 0-4
        vscno[second_axis] = max(0, min(4, vscno[second_axis]))
    return vscno

def clamp_metric(value: int) -> int:
    return max(0, min(100, value))

def clamp_internal(value: int) -> int:
    return max(0, min(10, value))

def parse_log(log_path: Path) -> List[Dict]:
    with open(log_path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    entries = []
    current_actor = None
    current_text = []
    actor_patterns = [
        (r"^(Пользователь|User|Я|I)[\s:：]", "user"),
        (r"^(Кира|Kira)[\s\(（]", "kira"),
        (r"^(Сергей|Sergey)[\s\(（]", "sergey"),
        (r"^(Марина|Marina)[\s\(（]", "marina"),
        (r"^(Максим|Maksim)[\s\(（]", "maksim"),
    ]
    for line in lines:
        line = line.strip()
        if not line:
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = None
            current_text = []
            continue
        found = False
        for pattern, actor_id in actor_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                if current_actor and current_text:
                    entries.append({"actor": current_actor, "text": " ".join(current_text)})
                current_actor = actor_id
                clean = re.sub(pattern, "", line, flags=re.IGNORECASE).strip()
                current_text = [clean] if clean else []
                found = True
                break
        if not found and current_actor:
            current_text.append(line)
    if current_actor and current_text:
        entries.append({"actor": current_actor, "text": " ".join(current_text)})
    debug(f"Parsed {len(entries)} entries from log")
    return entries

def extract_mnemonics(text: str) -> Dict:
    mnemos = {}
    m = re.search(r"[УU](\d)-([АAB])", text, re.IGNORECASE)
    if m:
        letter = "A" if m.group(2).upper() in ("A", "А") else "B"
        mnemos["level"] = f"U{m.group(1)}-{letter}"
    m = re.search(r"S(\d)", text, re.IGNORECASE)
    if m:
        mnemos["level_sergey"] = f"S{m.group(1)}"
    m = re.search(r"M(\d)", text, re.IGNORECASE)
    if m:
        mnemos["level_maksim"] = f"M{m.group(1)}"
    m = re.search(r"ВЛ(\d).*?СТ(\d).*?НЖ(\d).*?ОГ(\d)", text, re.IGNORECASE)
    if m:
        mnemos["vscno"] = {
            "ВЛ": int(m.group(1)),
            "СТ": int(m.group(2)),
            "НЖ": int(m.group(3)),
            "ОГ": int(m.group(4))
        }
    if re.search(r"СТОП|ХВАТИТ|PAUSE|STOP|НЕТ", text, re.IGNORECASE):
        mnemos["stop"] = True
    return mnemos

def detect_level_from_text(char_id: str, text: str) -> Optional[str]:
    text_lower = text.lower()
    sigs = LEVEL_SIGNATURES.get(char_id, {})
    scores = {}
    for level, keywords in sigs.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[level] = score
    if scores:
        best = max(scores, key=scores.get)
        debug(f"Level detection for {char_id}: {best} (score {scores[best]})")
        return best
    return None

def extract_fmdr(text: str) -> Dict:
    thoughts = re.findall(r"\(([^)]+)\)", text)
    actions = re.findall(r"\*([^*]+)\*", text)
    speech = re.findall(r"«([^»]+)»", text)
    if not speech:
        speech = re.findall(r'"([^"]+)"', text)
    return {"thoughts": thoughts, "actions": actions, "speech": speech}

def detect_phase_from_text(text: str) -> Optional[str]:
    text_lower = text.lower()
    phases = {
        "P1_ENTRANCE": ["вход", "раздевалк", "прихожая", "locker", "entrance"],
        "P2_STEAM": ["парилк", "парная", "steam", "жар", "пар"],
        "P3_POOL": ["бассейн", "облив", "pool", "душ", "water", "вода"],
        "P4_REST": ["комната отдыха", "rest room", "чай", "отдых", "relax"],
        "P5_CLIMAX": ["кульминац", "террас", "terrace", "финал", "climax"],
    }
    for phase, keywords in phases.items():
        if any(kw in text_lower for kw in keywords):
            return phase
    return None

# =============================================================================
# STATE MANAGER v2.1
# =============================================================================

@dataclass
class CharacterState:
    current_level: str = "unknown"
    previous_level: str = "unknown"
    internal_state: Dict[str, int] = field(default_factory=lambda: {
        "desire": 0, "anxiety": 2, "desire_tension": 0, "frustration": 0
    })
    vscno: Dict[str, int] = field(default_factory=lambda: {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2})
    flags: List[str] = field(default_factory=list)
    emergency_stop: bool = False

@dataclass
class SessionState:
    session_id: str = ""
    scenario_id: str = "unknown"
    turn_count: int = 0
    characters: Dict[str, CharacterState] = field(default_factory=dict)
    user: Dict = field(default_factory=lambda: {"choices_made": [], "flags": {}})
    audit_log: List[Dict] = field(default_factory=list)
    phases_detected: List[str] = field(default_factory=list)
    stop_turn: Optional[int] = None

class StateManager:
    def __init__(self, entries: List[Dict], scenario_id: str = "unknown", personas: Dict[str, Dict] = None):
        self.entries = entries
        self.scenario_id = scenario_id
        self.personas = personas or {}
        self.state = SessionState(
            session_id=f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M')}",
            scenario_id=scenario_id,
            turn_count=len(entries)
        )
        self.changes = defaultdict(lambda: {
            "desire_delta": 0, "anxiety_delta": 0, "desire_tension_delta": 0,
            "frustration_delta": 0, "flags": [], "level_changes": [],
            "trust_deltas": {}, "attraction_deltas": {}
        })

    def _init_char(self, char_id: str) -> CharacterState:
        defaults = VSCNO_DEFAULTS.get(char_id, {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2})
        return CharacterState(vscno=defaults.copy())

    def process(self) -> SessionState:
        log("[State Manager] Processing log...")
        for i, entry in enumerate(self.entries):
            actor = entry["actor"]
            text = entry["text"]
            mnemos = extract_mnemonics(text)
            fmdr = extract_fmdr(text)
            phase = detect_phase_from_text(text)

            if actor == "user":
                self.state.user["choices_made"].append(text[:100])
                if mnemos.get("vscno"):
                    for char in ["kira", "sergey", "marina", "maksim", "andrey_junior_module", "andrey_senior_module", "female_user_001", "kira_v11", "kira_v12", "kira_module_v14", "maksim_module_v2", "marina_001", "marina_module_v2", "maksim_001", "sergey_v2", "sergey_v3", "sergey_module_v4", "user_default", "olga_module_v2"]:
                        if char not in self.state.characters:
                            self.state.characters[char] = self._init_char(char)
                        self.state.characters[char].vscno = mnemos["vscno"]
                if phase and phase not in self.state.phases_detected:
                    self.state.phases_detected.append(phase)
                if mnemos.get("stop"):
                    self.state.stop_turn = i
                    for char_state in self.state.characters.values():
                        char_state.emergency_stop = True
                    self.state.audit_log.append({
                        "turn": i, "event": "EMERGENCY_STOP", "actor": "user"
                    })
                continue

            char_id = actor
            if char_id not in self.state.characters:
                self.state.characters[char_id] = self._init_char(char_id)
            char_state = self.state.characters[char_id]
            ch = self.changes[char_id]

            detected = detect_level_from_text(char_id, text)
            if detected and detected != char_state.current_level:
                char_state.previous_level = char_state.current_level
                char_state.current_level = detected
                ch["level_changes"].append({
                    "turn": i, "from": char_state.previous_level, "to": detected, "trigger": text[:80]
                })
                self.state.audit_log.append({
                    "turn": i, "event": "LEVEL_TRANSITION", "actor": char_id,
                    "from": char_state.previous_level, "to": detected
                })

            self._update_from_fmdr(char_id, fmdr, text)
            self._detect_flags(char_id, text, fmdr)
            self._analyze_relationship_deltas(char_id, text, fmdr)

            if phase and phase not in self.state.phases_detected:
                self.state.phases_detected.append(phase)

        for char_id in self.state.characters:
            self._clamp_metrics(char_id)
            self.state.characters[char_id].vscno = fix_vscno(self.state.characters[char_id].vscno)
            validate_vscno(self.state.characters[char_id].vscno, char_id)

        total_level_changes = sum(len(c["level_changes"]) for c in self.changes.values())
        log(f"[State Manager] Done. Turns: {self.state.turn_count}, Levels changed: {total_level_changes}, Phases: {self.state.phases_detected}, Stop at turn: {self.state.stop_turn}")
        return self.state

    def _update_from_fmdr(self, char_id: str, fmdr: Dict, text: str):
        text_lower = text.lower()
        ch = self.changes[char_id]
        if any(w in text_lower for w in ["покраснел", "краснеет", "румянец", "blush"]):
            ch["desire_delta"] += 1; ch["desire_tension_delta"] += 1
        if any(w in text_lower for w in ["дрожь", "тремор", "замер", "замирает", "tremor", "freeze"]):
            ch["anxiety_delta"] += 1; ch["desire_tension_delta"] += 1
        if any(w in text_lower for w in ["дыхание", "вздох", "breath", "sigh"]):
            ch["desire_delta"] += 1
        if any(w in text_lower for w in ["улыб", "smile", "смеётся", "laugh"]):
            ch["desire_delta"] += 1; ch["anxiety_delta"] -= 1
        if any(w in text_lower for w in ["отстран", "отводит", "отходит", "withdraw", "distance"]):
            ch["frustration_delta"] += 1; ch["desire_delta"] -= 1
        if any(w in text_lower for w in ["приближается", "касается", "touch", "lean"]):
            ch["desire_delta"] += 2; ch["anxiety_delta"] += 1
        if any(w in text_lower for w in ["плач", "слёзы", "cry", "tear"]):
            ch["anxiety_delta"] += 2; ch["frustration_delta"] += 1
        if any(w in text_lower for w in ["хочу", "want", "желан", "desire"]):
            ch["desire_delta"] += 2
        if any(w in text_lower for w in ["не надо", "не должна", "не могу", "stop", "can't"]):
            ch["desire_tension_delta"] += 1; ch["anxiety_delta"] += 1
        if any(w in text_lower for w in ["доверяю", "trust", "верю", "believe"]):
            ch["trust_deltas"]["user"] = ch["trust_deltas"].get("user", 0) + 5
        if any(w in text_lower for w in ["люблю", "love", "обожаю", "adore"]):
            ch["attraction_deltas"]["user"] = ch["attraction_deltas"].get("user", 0) + 5

    def _detect_flags(self, char_id: str, text: str, fmdr: Dict):
        text_lower = text.lower()
        flags = []
        if any(w in text_lower for w in ["первый поцелуй", "first kiss", "поцеловал"]):
            flags.append("first_kiss")
        if any(w in text_lower for w in ["номер", "телефон", "phone", "number"]):
            flags.append("phone_exchanged")
        if any(w in text_lower for w in ["пот", "sweat", "мокрый", "wet"]):
            flags.append("sweat_visible")
        if any(w in text_lower for w in ["парилка", "сауна", "sauna", "steam"]):
            flags.append("sauna_visited")
        if any(w in text_lower for w in ["бассейн", "pool", "вода", "water"]):
            flags.append("pool_visited")
        if any(w in text_lower for w in ["комната отдыха", "rest room", "чай", "tea"]):
            flags.append("rest_room_visited")
        if any(w in text_lower for w in ["красное платье", "red dress"]):
            flags.append("red_dress_seen")
        if any(w in text_lower for w in ["забудь ту девочку", "she is gone", "ritual goodbye"]):
            flags.append("kira_ritual_goodbye")
        self.changes[char_id]["flags"].extend(flags)

    def _analyze_relationship_deltas(self, char_id: str, text: str, fmdr: Dict):
        text_lower = text.lower()
        ch = self.changes[char_id]
        trust_signals = [
            ("user", ["ты первый", "я тебе доверяю", "не уходи", "рядом", "first to know", "trust"], 5),
            ("sergey", ["сергей", "sergey"], 2),
            ("marina", ["марина", "marina"], 2),
            ("maksim", ["максим", "maksim"], 2),
        ]
        for target, keywords, delta in trust_signals:
            if any(kw in text_lower for kw in keywords):
                ch["trust_deltas"][target] = ch["trust_deltas"].get(target, 0) + delta
        attraction_signals = [
            ("user", ["хочу", "желан", "ты мой", "beautiful", "attraction", "desire"], 5),
        ]
        for target, keywords, delta in attraction_signals:
            if any(kw in text_lower for kw in keywords):
                ch["attraction_deltas"][target] = ch["attraction_deltas"].get(target, 0) + delta

    def _clamp_metrics(self, char_id: str):
        char = self.state.characters[char_id]
        ch = self.changes[char_id]
        for key in ["desire", "anxiety", "desire_tension", "frustration"]:
            char.internal_state[key] = clamp_internal(char.internal_state[key] + ch[f"{key}_delta"])
        char.flags = list(set(self.changes[char_id]["flags"]))

    def generate_memory_update(self) -> List[Dict]:
        """Генерирует MEMORY_UPDATE с корректным baseline из persona.memory."""
        updates = []
        for char_id, char_state in self.state.characters.items():
            ch = self.changes[char_id]
            persona = self.personas.get(char_id, {})
            mem = persona.get("memory", {})
            current_trust = mem.get("trust_levels", {})
            current_attraction = mem.get("attraction_levels", {})
            module_path = discover_persona(char_id)
            module_name = module_path.name if module_path else f"{char_id.upper()}_MODULE.json"

            trust_updates = {}
            for target, delta in ch["trust_deltas"].items():
                base = current_trust.get(target, 50)
                trust_updates[target] = clamp_metric(base + delta)

            attraction_updates = {}
            for target, delta in ch["attraction_deltas"].items():
                base = current_attraction.get(target, 50)
                attraction_updates[target] = clamp_metric(base + delta)

            updates.append({
                "character": char_id,
                "module_path": f"personas/{module_name}",
                "memory_changes": {
                    "trust_levels": trust_updates,
                    "attraction_levels": attraction_updates,
                    "history.push": {
                        "session_id": self.state.session_id,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "scene": self.state.scenario_id,
                        "phases": self.state.phases_detected,
                        "key_events": char_state.flags,
                        "mood_after": f"desire={char_state.internal_state['desire']}, anxiety={char_state.internal_state['anxiety']}, tension={char_state.internal_state['desire_tension']}"
                    },
                    "flags": {f: True for f in char_state.flags}
                }
            })
        return updates

    def to_dict(self) -> Dict:
        return {
            "session_id": self.state.session_id,
            "scenario_id": self.state.scenario_id,
            "turn_count": self.state.turn_count,
            "phases_detected": self.state.phases_detected,
            "stop_turn": self.state.stop_turn,
            "characters": {
                k: {
                    "current_level": v.current_level,
                    "previous_level": v.previous_level,
                    "internal_state": v.internal_state,
                    "vscno": v.vscno,
                    "flags": v.flags,
                    "emergency_stop": v.emergency_stop,
                }
                for k, v in self.state.characters.items()
            },
            "user": self.state.user,
            "audit_log": self.state.audit_log,
        }

# =============================================================================
# NARRATIVE EDITOR v2.1
# =============================================================================

class NarrativeEditor:
    def __init__(self, entries: List[Dict], state: SessionState, scenario_id: str = "unknown"):
        self.entries = entries
        self.state = state
        self.scenario_id = scenario_id
        self.sensory = SCENARIO_SENSORY.get(scenario_id, SCENARIO_SENSORY["default"])

    def generate(self) -> str:
        log("[Narrative Editor] Generating story...")
        lines = []
        title = self._get_title()
        lines.append(f"# {title}")
        lines.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Сценарий:** {self.scenario_id}")
        lines.append(f"**Ходов:** {self.state.turn_count}")
        if self.state.stop_turn is not None:
            lines.append(f"**⚠️ Emergency Stop:** ход {self.state.stop_turn}")
        lines.append(f"**Фазы:** {', '.join(self.state.phases_detected) or 'не определены'}")
        lines.append("")

        lines.append("## Начальное состояние")
        for char_id, char_state in self.state.characters.items():
            level = char_state.current_level
            lines.append(f"- **{char_id.capitalize()}:** уровень `{level}`, desire={char_state.internal_state['desire']}, anxiety={char_state.internal_state['anxiety']}")
        lines.append("")

        lines.append("## Рассказ")
        lines.append("")

        current_phase = None
        current_chapter_lines = []
        chapter_num = 1
        stop_reached = False

        for i, entry in enumerate(self.entries):
            if self.state.stop_turn is not None and i > self.state.stop_turn:
                stop_reached = True
                break

            actor = entry["actor"]
            text = entry["text"]
            phase = detect_phase_from_text(text)

            if phase and phase != current_phase:
                if current_chapter_lines:
                    lines.append(f"### Глава {chapter_num}: {self._phase_name(current_phase)}")
                    lines.append("")
                    lines.extend(current_chapter_lines)
                    lines.append("")
                    chapter_num += 1
                    current_chapter_lines = []
                current_phase = phase

            if actor == "user":
                if re.match(r"^(ВЛ|СТ|НЖ|ОГ|У\d|АД|СТОП|ХВАТИТ|PAUSE|M\d)", text, re.IGNORECASE):
                    continue
                if re.match(r"^(ВЛ|СТ|НЖ|ОГ)\s*\d", text, re.IGNORECASE):
                    prose = self._vscno_to_prose(text)
                    if prose:
                        current_chapter_lines.append(prose)
                    continue
                user_text = self._user_to_prose(text)
                if user_text:
                    current_chapter_lines.append(user_text)
            else:
                char_prose = self._fmdr_to_prose(actor, text)
                if char_prose:
                    current_chapter_lines.append(char_prose)

        if current_chapter_lines:
            lines.append(f"### Глава {chapter_num}: {self._phase_name(current_phase)}")
            lines.append("")
            lines.extend(current_chapter_lines)
            lines.append("")

        if stop_reached:
            lines.append("> **Сессия прервана командой СТОП. Дальнейшие события не включены в рассказ.**")
            lines.append("")

        lines = self._inject_sensory(lines)

        lines.append("## Финальное состояние")
        for char_id, char_state in self.state.characters.items():
            level = char_state.current_level
            prev = char_state.previous_level
            lines.append(f"- **{char_id.capitalize()}:** `{prev}` → `{level}`, desire={char_state.internal_state['desire']}, anxiety={char_state.internal_state['anxiety']}, tension={char_state.internal_state['desire_tension']}")
        lines.append("")

        lines.append("## Аудит событий")
        for event in self.state.audit_log[:10]:
            lines.append(f"- Ход {event.get('turn', '?')}: {event.get('event', '?')} — {event.get('actor', '?')} ({event.get('from', '?')} → {event.get('to', '?')})")
        lines.append("")

        return "\n".join(lines)

    def _get_title(self) -> str:
        titles = {
            "sauna_quartet": "Сауна. Вечер пятницы",
            "promenade": "Прогулка. Город и мы",
            "cafe_date": "Кафе. Между двумя кружками",
            "shy_bloom": "Распускающийся цветок",
        }
        return titles.get(self.scenario_id, f"Сессия: {self.scenario_id}")

    def _phase_name(self, phase: Optional[str]) -> str:
        names = {
            "P1_ENTRANCE": "Порог",
            "P2_STEAM": "Парилка",
            "P3_POOL": "Вода и контраст",
            "P4_REST": "Комната отдыха",
            "P5_CLIMAX": "Кульминация",
        }
        return names.get(phase, "Продолжение")

    def _vscno_to_prose(self, text: str) -> Optional[str]:
        m = re.search(r"ВЛ(\d).*?СТ(\d).*?НЖ(\d).*?ОГ(\d)", text, re.IGNORECASE)
        if not m:
            return None
        vl, st, nz, og = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        parts = []
        if vl >= 3:
            parts.append("В комнате разлился смех, лёгкий и почти заразительный.")
        elif vl >= 1:
            parts.append("В воздухе витала лёгкая, едва уловимая улыбка.")
        if st >= 3:
            parts.append("Все замерли, погружённые в сосредоточенное ожидание.")
        if nz >= 2:
            parts.append("Что-то тяжёлое повисло в воздухе — не позволяя поднять глаза.")
        if og >= 3:
            parts.append("Незаметно для себя, все дышали в унисон, словно один организм.")
        return " ".join(parts) if parts else None

    def _user_to_prose(self, text: str) -> Optional[str]:
        text = text.strip()
        if text.startswith("Я ") or text.startswith("я "):
            text = text[2:]
        # Морфологическая заглушка: 1-е лицо → 3-е
        text = text.replace("кладу", "кладёт").replace("беру", "берёт").replace("говорю", "говорит")
        text = text.replace("смотрю", "смотрит").replace("иду", "идёт").replace("делаю", "делает")
        text = text.replace("хочу", "хочет").replace("могу", "может").replace("знаю", "знает")
        text = text.replace("люблю", "любит").replace("обнимаю", "обнимает").replace("целую", "целует")
        if text.startswith("Пусть ") or text.startswith("пусть "):
            return text[6:].capitalize() + "."
        if re.match(r"^(ВЛ|СТ|НЖ|ОГ)", text, re.IGNORECASE):
            return None
        return f"Он {text}."

    def _fmdr_to_prose(self, actor: str, text: str) -> str:
        # Удаляем мнемоники уровней перед обработкой
        text = re.sub(r"[УU]\d-[АAB]\s*[:：]?\s*", "", text, flags=re.IGNORECASE)
        fmdr = extract_fmdr(text)
        name = actor.capitalize()
        parts = []
        for thought in fmdr["thoughts"]:
            parts.append(f"*«{thought}», — подумала {name}.*")
        for action in fmdr["actions"]:
            parts.append(f"{name} {action}.")
        for speech in fmdr["speech"]:
            parts.append(f"— «{speech}», — сказала {name}.")
        if not parts:
            clean = re.sub(r"^(Кира|Сергей|Марина|Максим)[\s\(（].*?[:：）)]", "", text, flags=re.IGNORECASE).strip()
            if clean:
                parts.append(clean)
        return " ".join(parts)

    def _inject_sensory(self, lines: List[str]) -> List[str]:
        if not self.sensory:
            return lines
        for i, line in enumerate(lines):
            if line.startswith("### Глава"):
                sensory_block = []
                if self.sensory.get("scents"):
                    sensory_block.append(f"*Запахи:* {', '.join(self.sensory['scents'][:3])}.")
                if self.sensory.get("temperatures"):
                    sensory_block.append(f"*Температура:* {', '.join(self.sensory['temperatures'][:2])}.")
                if self.sensory.get("sounds"):
                    sensory_block.append(f"*Звуки:* {', '.join(self.sensory['sounds'][:3])}.")
                if sensory_block:
                    lines.insert(i + 1, "")
                    lines.insert(i + 2, "> " + " ".join(sensory_block))
                    lines.insert(i + 3, "")
                break
        return lines

# =============================================================================
# VISUAL PIPELINE v2.1 (с Safety Gate)
# =============================================================================

@dataclass
class VisualMoment:
    turn: int
    actor: str
    level: str
    phase: Optional[str]
    text: str
    fmdr: Dict
    score: int
    is_level_transition: bool = False
    is_key_event: bool = False

class VisualPipeline:
    def __init__(self, entries: List[Dict], state: SessionState, personas: Dict[str, Dict]):
        self.entries = entries
        self.state = state
        self.personas = personas
        self.moments: List[VisualMoment] = []

    def extract(self) -> List[VisualMoment]:
        log("[Visual Extractor] Extracting key moments...")
        stop_turn = self.state.stop_turn

        for i, entry in enumerate(self.entries):
            # SAFETY GATE: пропускаем всё после СТОП
            if stop_turn is not None and i > stop_turn:
                debug(f"Skipping turn {i} after emergency stop")
                continue

            actor = entry["actor"]
            text = entry["text"]
            if actor == "user":
                continue

            fmdr = extract_fmdr(text)
            char_state = self.state.characters.get(actor)
            level = char_state.current_level if char_state else "unknown"
            phase = detect_phase_from_text(text)

            score = 0
            visual_keywords = [
                "покраснел", "краснеет", "румянец", "дрожь", "тремор", "замер",
                "пот", "мокрый", "влажный", "пар", "steam", "sweat", "wet",
                "улыб", "smile", "глаза", "eyes", "взгляд", "gaze",
                "плечи", "осанка", "posture", "shoulder",
                "волосы", "hair", "платье", "dress", "полотенце", "towel",
                "кожа", "skin", "губы", "lips", "румянец", "blush",
                "поцелуй", "kiss", "объятие", "embrace", "касание", "touch"
            ]
            text_lower = text.lower()
            for kw in visual_keywords:
                if kw in text_lower:
                    score += 1

            is_transition = False
            if char_state and char_state.previous_level != level and level != "unknown":
                score += 8
                is_transition = True

            is_key = False
            if any(w in text_lower for w in ["первый поцелуй", "first kiss", "поцеловал", "слёзы", "tears", "плач"]):
                score += 5
                is_key = True

            if phase and phase in ["P1_ENTRANCE", "P3_POOL", "P5_CLIMAX"]:
                score += 2

            if score >= 3:
                self.moments.append(VisualMoment(
                    turn=i, actor=actor, level=level, phase=phase,
                    text=text, fmdr=fmdr, score=score,
                    is_level_transition=is_transition, is_key_event=is_key
                ))

        self.moments.sort(key=lambda x: (x.score, x.is_level_transition, x.is_key_event), reverse=True)
        top_moments = self.moments[:10]
        phases_covered = set(m.phase for m in top_moments if m.phase)
        for m in self.moments[10:]:
            if m.phase and m.phase not in phases_covered:
                top_moments.append(m)
                phases_covered.add(m.phase)
            if len(top_moments) >= 12:
                break
        self.moments = top_moments
        log(f"[Visual Extractor] Found {len(self.moments)} key moments (phases covered: {phases_covered})")
        return self.moments

    def generate_prompts(self) -> str:
        log("[Visual Physiognomist] Generating prompts...")
        lines = []
        lines.append(f"# Визуальные промпты — {self.state.session_id}")
        lines.append(f"**Сценарий:** {self.state.scenario_id}")
        lines.append(f"**Всего моментов:** {len(self.moments)}")
        if self.state.stop_turn is not None:
            lines.append(f"**⚠️ Safety Gate:** моменты после хода {self.state.stop_turn} исключены")
        lines.append("")

        for i, moment in enumerate(self.moments, 1):
            actor = moment.actor
            level = moment.level
            persona = self.personas.get(actor, {})
            visual_data = persona.get("visual_data", {})
            anatomic = visual_data.get("anatomic_anchor", {})
            signature = anatomic.get("visual_signature", "")

            scene_desc = self._moment_to_scene(moment)
            lighting = LIGHTING_MAP.get(level, "soft diffused natural light")
            camera = self._select_camera(moment)

            prompt_parts = [
                "Portrait" if "group" not in scene_desc.lower() else "Scene",
                signature,
                scene_desc,
                lighting,
                camera,
                "photorealistic, 8k, cinematic color grading, hyperdetailed skin texture, natural pores, no makeup, film grain subtle"
            ]
            prompt = ", ".join(filter(None, prompt_parts))
            negative = self._build_negative_prompt(actor, visual_data)

            lines.append(f"## Момент {i}: {actor.capitalize()} ({level})")
            lines.append(f"**Фаза:** {moment.phase or 'не определена'}")
            lines.append(f"**Приоритет:** {'🔴 Переход уровня' if moment.is_level_transition else '🔴 Ключевое событие' if moment.is_key_event else '🟡 Сценический'}")
            lines.append(f"**Текст:** {moment.text[:120]}...")
            lines.append(f"**Описание:** {scene_desc}")
            lines.append("")
            lines.append("### Qwen / Stable Diffusion")
            lines.append("```")
            lines.append(prompt)
            lines.append("```")
            lines.append("")
            lines.append("### Negative")
            lines.append("```")
            lines.append(negative)
            lines.append("```")
            lines.append("")
            lines.append("### Midjourney")
            lines.append("```")
            lines.append(prompt + " --ar 4:3 --v 6 --style raw")
            lines.append("```")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _moment_to_scene(self, moment: VisualMoment) -> str:
        actor = moment.actor
        fmdr = moment.fmdr
        text = moment.text
        actions = fmdr["actions"]
        if actions:
            scene = ", ".join(actions)
        else:
            sentences = re.split(r"[.!?]", text)
            visual_sents = [s for s in sentences if any(kw in s.lower() for kw in [
                "покраснел", "дрожь", "пот", "волосы", "глаза", "улыб", "осанк", "плечи",
                "кожа", "губы", "поцелуй", "объятие", "касание", "слёзы", "плач"
            ])]
            scene = ", ".join(visual_sents[:2]) if visual_sents else f"{actor} in scene"
        if "сауна" in text.lower() or "пар" in text.lower() or "steam" in text.lower():
            scene += ", sauna, steam, wooden interior"
        if "бассейн" in text.lower() or "pool" in text.lower():
            scene += ", pool, water, wet skin"
        if "комната отдыха" in text.lower() or "rest" in text.lower():
            scene += ", rest room, soft dim lights, tea"
        if "красное платье" in text.lower() or "red dress" in text.lower():
            scene += ", fitted red dress, signature piece"
        return scene

    def _select_camera(self, moment: VisualMoment) -> str:
        text_lower = moment.text.lower()
        if "групп" in text_lower or "все трое" in text_lower or "three" in text_lower or "four" in text_lower:
            return "35mm lens, f/2.8, medium shot, slightly low angle, group composition"
        if moment.is_level_transition and moment.level in ["U3-A", "U3-B", "S4", "M4"]:
            return "50mm lens, f/1.8, Dutch angle, medium close-up, emotional peak"
        if any(w in text_lower for w in ["глаза", "eyes", "взгляд", "gaze", "румянец", "blush"]):
            return "85mm lens, f/1.4, close-up portrait, eye level, shallow depth of field"
        if any(w in text_lower for w in ["рука", "hand", "касание", "touch", "пот", "sweat"]):
            return "100mm macro, f/2.8, detail shot, texture focus"
        return "85mm lens, f/1.8, close-up portrait, eye level, shallow depth of field"

    def _build_negative_prompt(self, actor: str, visual_data: Dict) -> str:
        base_parts = ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "oversaturated", "plastic skin", "blurry", "low quality"]
        anti = visual_data.get("anti_prompts", [])
        for a in anti:
            if a not in base_parts:
                base_parts.append(a)
        extras = {
            "kira": ["blonde hair", "excessive makeup", "different face", "old", "wrinkles", "different eye color"],
            "marina": ["harsh makeup", "aggressive pose", "different eye color", "muscular", "old"],
            "sergey": ["clean shaven", "baby face", "weak jaw", "different hair color", "anime"],
            "maksim": ["bulky bodybuilder", "aggressive pose", "different hair color", "old"],
        "olga_module_v2": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "excessive makeup", "wrinkled skin"],
        "sergey_module_v4": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark"],
        "marina_module_v2": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "excessive makeup"],
        "maksim_module_v2": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark"],
        "kira_module_v14": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "blonde hair", "excessive makeup"],
        "andrey_senior_module": ["bald head", "shaved head", "receding hairline", "sparse hair", "close-set eyes", "skinny build", "feminine features"],
        "andrey_junior_module": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "excessive muscles", "bodybuilder"],
        "andrey_senior": ["bald head", "shaved head", "receding hairline", "sparse hair", "close-set eyes", "skinny build", "feminine features"],
        "andrey_junior": ["anime", "cartoon", "3d render", "distorted anatomy", "extra limbs", "bad hands", "text", "watermark", "excessive muscles", "bodybuilder", "aged appearance", "facial hair", "beard", "tall height"],
        }
        if actor in extras:
            for e in extras[actor]:
                if e not in base_parts:
                    base_parts.append(e)
        return ", ".join(base_parts)

# =============================================================================
# MODULE API — для импорта из integration_test.py и других скриптов
# =============================================================================

class SessionEngine:
    """
    Пошаговый движок сессии.
    Хранит entries и позволяет добавлять turn за turn'ом,
    пересчитывая состояние через StateManager.
    """
    def __init__(self, scenario_id: str = "unknown", personas: Optional[Dict] = None, initial_entries: Optional[List[Dict]] = None):
        self.scenario_id = scenario_id
        self.personas = personas or {}
        self.entries = initial_entries or []
        self.state_manager: Optional[StateManager] = None
        self._turn_index: int = 0

    def add_turn(self, actor: str, text: str) -> Dict:
        """Добавить один turn и пересчитать состояние."""
        self.entries.append({"actor": actor, "text": text})
        self.state_manager = StateManager(self.entries, self.scenario_id, self.personas)
        self.state = self.state_manager.process()
        self._turn_index = len(self.entries)
        return self.state_manager.to_dict()

    def get_state(self) -> Dict:
        if not self.state_manager:
            return {}
        return self.state_manager.to_dict()

    def get_memory_update(self) -> List[Dict]:
        if not self.state_manager:
            return []
        return self.state_manager.generate_memory_update()

    def get_changes(self) -> Dict:
        if not self.state_manager:
            return {}
        return dict(self.state_manager.changes)


def process_step(state_dict: Optional[Dict], actor: str, text: str, scenario_id: str = "unknown", personas: Optional[Dict] = None) -> Dict:
    """
    Stateless обработка одного turn'а.
    Если state_dict передан, его поля session_id и scenario_id используются
    для continuity, но полный пересчёт происходит только по текущей entry.
    Для накопления истории используйте SessionEngine.
    """
    entries = [{"actor": actor, "text": text}]
    sm = StateManager(entries, scenario_id, personas or {})
    state = sm.process()
    result = sm.to_dict()
    if state_dict:
        result["session_id"] = state_dict.get("session_id", result["session_id"])
        result["scenario_id"] = state_dict.get("scenario_id", result["scenario_id"])
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    global REPO_DIR, SESSIONS_DIR, PERSONAS_DIR, STATE_DIR, ASSETS_DIR

    parser = argparse.ArgumentParser(
        description="Voyage Session Finalizer v2.1 — один файл, весь pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python session_finalize.py --log sessions/raw/session.log --scenario sauna_quartet
  python session_finalize.py --log session.log --scenario promenade --verbose --dry-run
  python session_finalize.py --log session.log --scenario sauna_quartet --validate
        """
    )
    parser.add_argument("--log", required=True, help="Путь к логу сессии (.log или .txt)")
    parser.add_argument("--scenario", default="unknown", help="ID сценария")
    parser.add_argument("--repo", default=str(REPO_DIR), help="Путь к репозиторию (default: директория скрипта)")
    parser.add_argument("--no-git", action="store_true", help="Не делать git commit")
    parser.add_argument("--dry-run", action="store_true", help="Не сохранять файлы, только вывести в stdout")
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод (DEBUG)")
    parser.add_argument("--validate", action="store_true", help="Валидировать persona JSON по schema")
    parser.add_argument("--max-moments", type=int, default=10, help="Максимум визуальных моментов (default: 10)")
    args = parser.parse_args()

    set_verbose(args.verbose)

    REPO_DIR = Path(args.repo)
    SESSIONS_DIR = REPO_DIR / "sessions"
    PERSONAS_DIR = REPO_DIR / "personas"
    STATE_DIR = REPO_DIR / "state"
    ASSETS_DIR = REPO_DIR / "assets" / "images"

    log_path = Path(args.log)
    if not log_path.exists():
        log(f"Log file not found: {log_path}", "ERROR")
        sys.exit(1)

    log(f"=== Voyage Session Finalizer v2.1 ===")
    log(f"Log: {log_path}")
    log(f"Scenario: {args.scenario}")
    log(f"Repo: {REPO_DIR}")
    if args.dry_run:
        log("DRY-RUN MODE: файлы не будут сохранены")

    if not args.dry_run:
        ensure_dirs()

    # 1. Parse log
    log("\n[1/5] Parsing log...")
    entries = parse_log(log_path)
    log(f" Entries: {len(entries)}")
    if not entries:
        log("No entries parsed! Check log format.", "ERROR")
        sys.exit(1)

    # 2. Load personas (до State Manager, чтобы baseline trust/attraction были корректны)
    log("\n[2/5] Loading personas...")
    personas = {}
    for char in ["kira", "sergey", "marina", "maksim", "andrey_junior_module", "andrey_senior_module", "female_user_001", "kira_v11", "kira_v12", "kira_module_v14", "maksim_module_v2", "marina_001", "marina_module_v2", "maksim_001", "sergey_v2", "sergey_v3", "sergey_module_v4", "user_default", "olga_module_v2"]:
        persona = load_persona(char)
        if persona:
            personas[char] = persona
            log(f" Loaded: {char} ({persona.get('id', 'unknown')})")
            vscno = persona.get("vscno", {})
            if vscno:
                validate_vscno(vscno, char)
        else:
            log(f" Skipped: {char} (module not found)", "WARN")

    # 2.5. JSON Schema validation (если запрошено)
    if args.validate:
        log("\n[2.5/5] Validating personas against schema...")
        if SCHEMA_PATH.exists():
            try:
                import jsonschema
                schema = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))
                for char_id, persona in personas.items():
                    try:
                        jsonschema.validate(instance=persona, schema=schema)
                        log(f"  ✓ {char_id}: schema valid")
                    except jsonschema.ValidationError as e:
                        log(f"  ✗ {char_id}: schema error — {e.message}", "ERROR")
            except ImportError:
                log("  jsonschema not installed. Install: pip install jsonschema", "WARN")
        else:
            log(f"  Schema not found at {SCHEMA_PATH}", "WARN")

    # 3. State Manager (с personas для корректного baseline)
    log("\n[3/5] State Manager...")
    sm = StateManager(entries, args.scenario, personas=personas)
    state = sm.process()

    # 4. Narrative Editor
    log("\n[4/5] Narrative Editor...")
    ne = NarrativeEditor(entries, state, args.scenario)
    story = ne.generate()

    # 5. Visual Pipeline (с Safety Gate)
    log("\n[5/5] Visual Extractor + Physiognomist...")
    vp = VisualPipeline(entries, state, personas)
    vp.extract()
    visuals = vp.generate_prompts()

    # 6. Save outputs
    session_id = state.session_id
    if args.dry_run:
        log("\n=== DRY-RUN OUTPUTS ===")
        log("\n--- STATE_UPDATE ---")
        print(json.dumps(sm.to_dict(), ensure_ascii=False, indent=2))
        log("\n--- STORY (first 2000 chars) ---")
        print(story[:2000])
        log("\n--- VISUALS (first 2000 chars) ---")
        print(visuals[:2000])
    else:
        log(f"\nSaving outputs for session: {session_id}")

        state_path = SESSIONS_DIR / "state" / f"STATE_UPDATE_{session_id}.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(sm.to_dict(), f, ensure_ascii=False, indent=2)
        log(f" → {state_path}")

        memory = sm.generate_memory_update()
        memory_path = SESSIONS_DIR / "memory" / f"MEMORY_UPDATE_{session_id}.json"
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
        log(f" → {memory_path}")

        story_path = SESSIONS_DIR / "stories" / f"STORY_{session_id}.md"
        with open(story_path, "w", encoding="utf-8") as f:
            f.write(story)
        log(f" → {story_path}")

        visuals_path = SESSIONS_DIR / "visuals" / f"VISUAL_PROMPTS_{session_id}.md"
        with open(visuals_path, "w", encoding="utf-8") as f:
            f.write(visuals)
        log(f" → {visuals_path}")

        # 7. Update personas
        log("\nUpdating personas...")
        for update in memory:
            char = update["character"]
            if char not in personas:
                continue
            persona = personas[char]
            mem_changes = update["memory_changes"]

            if "history.push" in mem_changes:
                if "history" not in persona.get("memory", {}):
                    persona.setdefault("memory", {})["history"] = []
                persona["memory"]["history"].append(mem_changes["history.push"])

            if "trust_levels" in mem_changes and mem_changes["trust_levels"]:
                persona.setdefault("memory", {}).setdefault("trust_levels", {})
                persona["memory"]["trust_levels"].update(mem_changes["trust_levels"])

            if "attraction_levels" in mem_changes and mem_changes["attraction_levels"]:
                persona.setdefault("memory", {}).setdefault("attraction_levels", {})
                persona["memory"]["attraction_levels"].update(mem_changes["attraction_levels"])

            if "flags" in mem_changes:
                persona.setdefault("memory", {}).setdefault("flags", {})
                persona["memory"]["flags"].update(mem_changes["flags"])

            persona["memory"]["last_scene"] = args.scenario
            save_persona(char, persona)

        # 8. Git
        if not args.no_git:
            log("\nGit commit...")
            try:
                subprocess.run(["git", "add", "sessions/", "personas/"], cwd=REPO_DIR, check=True)
                subprocess.run(["git", "commit", "-m",
                    f"session: {session_id} {args.scenario}\nauto: state, story, visuals, memory updates (v2.1)"],
                    cwd=REPO_DIR, check=True)
                log(" Git commit done")
            except subprocess.CalledProcessError as e:
                log(f" Git failed: {e}", "WARN")
            except FileNotFoundError:
                log(" Git not found in PATH", "WARN")

    log("\n=== DONE ===")
    log(f"Session: {session_id}")
    if not args.dry_run:
        log(f"Outputs in: {SESSIONS_DIR}")
        log("\nNext steps:")
        log(" 1. Review story")
        log(" 2. Review visuals")
        log(" 3. Check state")
        log(" 4. Generate images using prompts from visuals file")
        log(" 5. Push to git: git push origin main")

if __name__ == "__main__":
    main()
