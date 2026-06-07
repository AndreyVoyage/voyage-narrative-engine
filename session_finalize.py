#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Session Finalizer v1.0
Один файл — весь pipeline после сессии:
  1. Парсит лог сессии
  2. Обновляет STATE и MEMORY (State Manager)
  3. Генерирует литературный рассказ (Narrative Editor)
  4. Генерирует визуальные промпты (Visual Extractor + Physiognomist)
  5. Обновляет JSON-модули персонажей
  6. Делает git commit

Usage:
  python session_finalize.py --log ~/voyage-narrative-engine/sessions/raw/session_2026-06-08.log --scenario sauna_quartet

Requirements: Python 3.7+ (только стандартная библиотека)
"""

import json
import re
import os
import sys
import argparse
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

REPO_DIR = Path.home() / "voyage-narrative-engine"
SESSIONS_DIR = REPO_DIR / "sessions"
PERSONAS_DIR = REPO_DIR / "personas"
STATE_DIR = REPO_DIR / "state"
ASSETS_DIR = REPO_DIR / "assets" / "images"

# Подуровни и их speech-признаки (для автоопределения уровня из лога)
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
    }
}

# VSCNO инвариант: ВЛ + СТ + НЖ + ОГ = 10
VSCNO_DEFAULTS = {
    "kira": {"ВЛ": 2, "СТ": 1, "НЖ": 2, "ОГ": 1},
    "sergey": {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2},
    "marina": {"ВЛ": 1, "СТ": 2, "НЖ": 4, "ОГ": 3},
}

# Lighting map по подуровням
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
}

# =============================================================================
# УТИЛИТЫ
# =============================================================================

def error(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)

def info(msg):
    print(f"[INFO] {msg}")

def warn(msg):
    print(f"[WARN] {msg}")

def ensure_dirs():
    """Создаёт все необходимые папки."""
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

def load_persona(char_id):
    """Загружает JSON-модуль персонажа."""
    path = PERSONAS_DIR / f"{char_id}.json"
    if not path.exists():
        error(f"Persona not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_persona(char_id, data):
    """Сохраняет JSON-модуль с бэкапом."""
    path = PERSONAS_DIR / f"{char_id}.json"
    backup = PERSONAS_DIR / f"{char_id}.json.bak"
    if path.exists():
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    info(f"  Saved persona: {path}")

def parse_log(log_path):
    """Парсит лог сессии на реплики."""
    with open(log_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    entries = []
    current_actor = None
    current_text = []

    for line in lines:
        line = line.strip()
        if not line:
            if current_actor and current_text:
                entries.append({
                    "actor": current_actor,
                    "text": " ".join(current_text)
                })
                current_actor = None
                current_text = []
            continue

        # Определяем актора
        if line.startswith("Пользователь:") or line.startswith("User:"):
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = "user"
            current_text = [line.split(":", 1)[1].strip()]
        elif re.search(r"^(Кира|Kira)[\s\(]", line, re.IGNORECASE):
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = "kira"
            current_text = [line]
        elif re.search(r"^(Сергей|Sergey)[\s\(]", line, re.IGNORECASE):
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = "sergey"
            current_text = [line]
        elif re.search(r"^(Марина|Marina)[\s\(]", line, re.IGNORECASE):
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = "marina"
            current_text = [line]
        elif re.search(r"^(Максим|Maksim)[\s\(]", line, re.IGNORECASE):
            if current_actor and current_text:
                entries.append({"actor": current_actor, "text": " ".join(current_text)})
            current_actor = "maksim"
            current_text = [line]
        else:
            if current_actor:
                current_text.append(line)

    if current_actor and current_text:
        entries.append({"actor": current_actor, "text": " ".join(current_text)})

    return entries

def extract_mnemonics(text):
    """Извлекает мнемоники из текста."""
    mnemos = {}
    # Уровни
    m = re.search(r"[УU](\\d)-[АAB]", text, re.IGNORECASE)
    if m:
        mnemos["level"] = f"U{m.group(1)}-A" if m.group(2) in "АA" else f"U{m.group(1)}-B"
    m = re.search(r"S(\d)", text, re.IGNORECASE)
    if m:
        mnemos["level_sergey"] = f"S{m.group(1)}"
    # VSCNO
    m = re.search(r"ВЛ(\d).*?СТ(\d).*?НЖ(\d).*?ОГ(\d)", text, re.IGNORECASE)
    if m:
        mnemos["vscno"] = {
            "ВЛ": int(m.group(1)),
            "СТ": int(m.group(2)),
            "НЖ": int(m.group(3)),
            "ОГ": int(m.group(4))
        }
    # Команды
    if re.search(r"СТОП|ХВАТИТ|PAUSE|STOP", text, re.IGNORECASE):
        mnemos["stop"] = True
    return mnemos

def detect_level_from_text(char_id, text):
    """Определяет подуровень персонажа по тексту."""
    text_lower = text.lower()
    sigs = LEVEL_SIGNATURES.get(char_id, {})
    scores = {}
    for level, keywords in sigs.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > 0:
            scores[level] = score
    if scores:
        return max(scores, key=scores.get)
    return None

def extract_fmdr(text):
    """Извлекает ФМДР из текста: (Мысли), *Действия*, «Речь»."""
    thoughts = re.findall(r"\(([^)]+)\)", text)
    actions = re.findall(r"\*([^*]+)\*", text)
    speech = re.findall(r"«([^»]+)»", text)
    return {
        "thoughts": thoughts,
        "actions": actions,
        "speech": speech
    }

# =============================================================================
# STATE MANAGER
# =============================================================================

class StateManager:
    def __init__(self, entries, scenario_id="unknown"):
        self.entries = entries
        self.scenario_id = scenario_id
        self.state = {
            "session_id": f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M')}",
            "scenario_id": scenario_id,
            "turn_count": len(entries),
            "characters": {},
            "user": {"choices_made": [], "flags": {}},
            "audit_log": []
        }
        self.changes = defaultdict(lambda: {
            "desire_delta": 0, "anxiety_delta": 0, "desire_tension_delta": 0,
            "frustration_delta": 0, "flags": [], "level_changes": []
        })

    def process(self):
        info("[State Manager] Processing log...")
        for i, entry in enumerate(self.entries):
            actor = entry["actor"]
            text = entry["text"]
            mnemos = extract_mnemonics(text)
            fmdr = extract_fmdr(text)

            # User commands
            if actor == "user":
                self.state["user"]["choices_made"].append(text[:100])
                if mnemos.get("vscno"):
                    for char in ["kira", "sergey", "marina"]:
                        if char not in self.state["characters"]:
                            self.state["characters"][char] = self._init_char(char)
                        self.state["characters"][char]["vscno"] = mnemos["vscno"]
                continue

            # Character entries
            char_id = actor
            if char_id not in self.state["characters"]:
                self.state["characters"][char_id] = self._init_char(char_id)

            char_state = self.state["characters"][char_id]

            # Detect level
            detected = detect_level_from_text(char_id, text)
            if detected and detected != char_state.get("current_level"):
                char_state["previous_level"] = char_state.get("current_level", "unknown")
                char_state["current_level"] = detected
                self.changes[char_id]["level_changes"].append({
                    "turn": i,
                    "from": char_state["previous_level"],
                    "to": detected,
                    "trigger": text[:80]
                })
                self.state["audit_log"].append({
                    "turn": i,
                    "event": "LEVEL_TRANSITION",
                    "actor": char_id,
                    "from": char_state["previous_level"],
                    "to": detected
                })

            # Update internal_state from FMDR
            self._update_from_fmdr(char_id, fmdr, text)

            # Check for flags
            self._detect_flags(char_id, text, fmdr)

            # Stop command
            if mnemos.get("stop"):
                char_state["emergency_stop"] = True
                self.state["audit_log"].append({
                    "turn": i,
                    "event": "EMERGENCY_STOP",
                    "actor": char_id
                })

        # Finalize
        for char_id in self.state["characters"]:
            self._clamp_metrics(char_id)

        info(f"[State Manager] Done. Turns: {self.state['turn_count']}, Levels changed: {sum(len(c['level_changes']) for c in self.changes.values())}")
        return self.state

    def _init_char(self, char_id):
        defaults = VSCNO_DEFAULTS.get(char_id, {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2})
        return {
            "current_level": "unknown",
            "previous_level": "unknown",
            "internal_state": {"desire": 0, "anxiety": 2, "desire_tension": 0, "frustration": 0},
            "vscno": defaults.copy(),
            "flags": [],
            "emergency_stop": False
        }

    def _update_from_fmdr(self, char_id, fmdr, text):
        text_lower = text.lower()
        ch = self.changes[char_id]

        # Physiological arousal
        if any(w in text_lower for w in ["покраснел", "краснеет", "румянец", "blush"]):
            ch["desire_delta"] += 1
            ch["desire_tension_delta"] += 1
        if any(w in text_lower for w in ["дрожь", "тремор", "замер", "замирает", "tremor", "freeze"]):
            ch["anxiety_delta"] += 1
            ch["desire_tension_delta"] += 1
        if any(w in text_lower for w in ["дыхание", "вздох", " breath", "sigh"]):
            ch["desire_delta"] += 1
        if any(w in text_lower for w in ["улыб", "smile", "смеётся", "laugh"]):
            ch["desire_delta"] += 1
            ch["anxiety_delta"] -= 1
        if any(w in text_lower for w in ["отстран", "отводит", "отходит", "withdraw", "distance"]):
            ch["frustration_delta"] += 1
            ch["desire_delta"] -= 1
        if any(w in text_lower for w in ["приближается", "касается", "touch", "lean"]):
            ch["desire_delta"] += 2
            ch["anxiety_delta"] += 1
        if any(w in text_lower for w in ["плач", "слёзы", "cry", "tear"]):
            ch["anxiety_delta"] += 2
            ch["frustration_delta"] += 1
        if any(w in text_lower for w in ["хочу", "want", "желан", "desire"]):
            ch["desire_delta"] += 2
        if any(w in text_lower for w in ["не надо", "не должна", "не могу", "stop", "can't"]):
            ch["desire_tension_delta"] += 1
            ch["anxiety_delta"] += 1

    def _detect_flags(self, char_id, text, fmdr):
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
        self.changes[char_id]["flags"].extend(flags)

    def _clamp_metrics(self, char_id):
        char = self.state["characters"][char_id]
        ch = self.changes[char_id]
        for key in ["desire", "anxiety", "desire_tension", "frustration"]:
            char["internal_state"][key] = max(0, min(10, char["internal_state"][key] + ch[f"{key}_delta"]))
        # VSCNO invariant check
        vscno = char["vscno"]
        total = sum(vscno.values())
        if total != 10:
            warn(f"  {char_id}: VSCNO sum={total} != 10 (ВЛ{vscno['ВЛ']} СТ{vscno['СТ']} НЖ{vscno['НЖ']} ОГ{vscno['ОГ']})")
        char["flags"] = list(set(self.changes[char_id]["flags"]))

    def generate_memory_update(self):
        """Генерирует MEMORY_UPDATE.json."""
        updates = []
        for char_id, char_state in self.state["characters"].items():
            module_id = f"{char_id.upper()}_MODULE_v14" if char_id == "kira" else f"{char_id.upper()}_MODULE_v4"
            if char_id == "marina":
                module_id = "MARINA_MODULE_v2"

            updates.append({
                "character": char_id,
                "module_path": f"personas/{module_id}.json",
                "memory_changes": {
                    "trust_levels": {},  # Would need user interaction analysis
                    "attraction_levels": {},
                    "history.push": {
                        "session_id": self.state["session_id"],
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "scene": self.state["scenario_id"],
                        "key_events": char_state["flags"],
                        "mood_after": f"desire={char_state['internal_state']['desire']}, anxiety={char_state['internal_state']['anxiety']}"
                    },
                    "flags": {f: True for f in char_state["flags"]}
                }
            })
        return updates

# =============================================================================
# NARRATIVE EDITOR
# =============================================================================

class NarrativeEditor:
    def __init__(self, entries, state, scenario_id="unknown"):
        self.entries = entries
        self.state = state
        self.scenario_id = scenario_id

    def generate(self):
        info("[Narrative Editor] Generating story...")
        lines = []
        lines.append(f"# Сессия: {self.scenario_id}")
        lines.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Ходов:** {self.state['turn_count']}")
        lines.append("")

        # Character states at start
        lines.append("## Начальное состояние")
        for char_id, char_state in self.state["characters"].items():
            level = char_state.get("current_level", "unknown")
            lines.append(f"- **{char_id.capitalize()}:** уровень `{level}`, desire={char_state['internal_state']['desire']}, anxiety={char_state['internal_state']['anxiety']}")
        lines.append("")

        # Story body
        lines.append("## Рассказ")
        lines.append("")

        current_para = []
        for entry in self.entries:
            actor = entry["actor"]
            text = entry["text"]

            if actor == "user":
                # Skip technical commands, convert actions to prose
                if re.match(r"^(ВЛ|СТ|НЖ|ОГ|У\d|АД|СТОП|ХВАТИТ|PAUSE)", text, re.IGNORECASE):
                    continue
                # Convert user action to 3rd person
                user_text = self._user_to_prose(text)
                if user_text:
                    current_para.append(user_text)
            else:
                # Character FMDR to prose
                char_prose = self._fmdr_to_prose(actor, text)
                if char_prose:
                    current_para.append(char_prose)

            # Paragraph break every 2-3 entries or on empty
            if len(current_para) >= 2:
                lines.append(" ".join(current_para))
                lines.append("")
                current_para = []

        if current_para:
            lines.append(" ".join(current_para))

        # Final states
        lines.append("")
        lines.append("## Финальное состояние")
        for char_id, char_state in self.state["characters"].items():
            level = char_state.get("current_level", "unknown")
            prev = char_state.get("previous_level", "unknown")
            lines.append(f"- **{char_id.capitalize()}:** `{prev}` → `{level}`, desire={char_state['internal_state']['desire']}, anxiety={char_state['internal_state']['anxiety']}, tension={char_state['internal_state']['desire_tension']}")

        return "\n".join(lines)

    def _user_to_prose(self, text):
        text = text.strip()
        if text.startswith("Я ") or text.startswith("я "):
            return "Он " + text[2:]
        if text.startswith("Пусть ") or text.startswith("пусть "):
            return text[6:].capitalize() + "."
        return f"Он {text}."

    def _fmdr_to_prose(self, actor, text):
        fmdr = extract_fmdr(text)
        name = actor.capitalize()
        parts = []

        # Thoughts
        for thought in fmdr["thoughts"]:
            parts.append(f"*«{thought}», — подумала {name}.*")

        # Actions
        for action in fmdr["actions"]:
            parts.append(f"{name} {action}.")

        # Speech
        for speech in fmdr["speech"]:
            parts.append(f"— «{speech}», — сказала {name}.")

        # If no FMDR found, treat as plain text
        if not parts:
            # Clean up technical prefixes
            clean = re.sub(r"^(Кира|Сергей|Марина|Максим)[\s\(].*?[:\)]", "", text, flags=re.IGNORECASE).strip()
            if clean:
                parts.append(clean)

        return " ".join(parts)

# =============================================================================
# VISUAL EXTRACTOR + PHYSIOGNOMIST
# =============================================================================

class VisualPipeline:
    def __init__(self, entries, state, personas):
        self.entries = entries
        self.state = state
        self.personas = personas
        self.moments = []

    def extract(self):
        info("[Visual Extractor] Extracting key moments...")
        for i, entry in enumerate(self.entries):
            actor = entry["actor"]
            text = entry["text"]
            if actor == "user":
                continue

            fmdr = extract_fmdr(text)
            level = self.state["characters"].get(actor, {}).get("current_level", "unknown")

            # Score visual richness
            score = 0
            visual_keywords = ["покраснел", "краснеет", "румянец", "дрожь", "тремор", "замер",
                             "пот", "мокрый", "влажный", "пар", "steam", "sweat", "wet",
                             "улыб", "smile", "глаза", "eyes", "взгляд", "gaze",
                             "плечи", "осанка", "posture", "shoulder",
                             "волосы", "hair", "платье", "dress", "полотенце", "towel"]
            text_lower = text.lower()
            for kw in visual_keywords:
                if kw in text_lower:
                    score += 1

            # Level transitions are high priority
            if self.state["characters"].get(actor, {}).get("previous_level") != level and level != "unknown":
                score += 5

            if score >= 3:
                self.moments.append({
                    "turn": i,
                    "actor": actor,
                    "level": level,
                    "text": text,
                    "fmdr": fmdr,
                    "score": score
                })

        # Sort by score, take top 8
        self.moments.sort(key=lambda x: x["score"], reverse=True)
        self.moments = self.moments[:8]
        info(f"[Visual Extractor] Found {len(self.moments)} key moments")
        return self.moments

    def generate_prompts(self):
        info("[Visual Physiognomist] Generating prompts...")
        lines = []
        lines.append(f"# Визуальные промпты — {self.state['session_id']}")
        lines.append("")

        for i, moment in enumerate(self.moments, 1):
            actor = moment["actor"]
            level = moment["level"]
            persona = self.personas.get(actor, {})
            visual_data = persona.get("visual_data", {})
            anatomic = visual_data.get("anatomic_anchor", {})
            signature = anatomic.get("visual_signature", "")

            # Scene description from moment
            scene_desc = self._moment_to_scene(moment)

            # Lighting from level
            lighting = LIGHTING_MAP.get(level, "soft diffused natural light")

            # Camera based on intimacy
            camera = "85mm lens, f/1.8, close-up portrait, eye level, shallow depth of field"
            if "групп" in scene_desc.lower() or "все трое" in scene_desc.lower() or "three" in scene_desc.lower():
                camera = "35mm lens, f/2.8, medium shot, slightly low angle"

            # Build prompt
            prompt_parts = [
                "Portrait" if "group" not in scene_desc.lower() else "Scene",
                signature,
                scene_desc,
                lighting,
                camera,
                "photorealistic, 8k, cinematic color grading, hyperdetailed skin texture, natural pores, no makeup, film grain subtle"
            ]
            prompt = ", ".join(filter(None, prompt_parts))

            # Negative prompt
            negative = "anime, cartoon, 3d render, distorted anatomy, extra limbs, bad hands, text, watermark, blonde hair, excessive makeup, different face, old, wrinkles, plastic skin, blurry, low quality"

            lines.append(f"## Момент {i}: {actor.capitalize()} ({level})")
            lines.append(f"**Текст:** {moment['text'][:120]}...")
            lines.append(f"**Описание:** {scene_desc}")
            lines.append("")
            lines.append("### Qwen / Stable Diffusion")
            lines.append(f"```")
            lines.append(prompt)
            lines.append(f"```")
            lines.append("")
            lines.append("### Negative")
            lines.append(f"```")
            lines.append(negative)
            lines.append(f"```")
            lines.append("")
            lines.append("### Midjourney")
            lines.append(f"```")
            mj_prompt = prompt + " --ar 4:3 --v 6 --style raw"
            lines.append(mj_prompt)
            lines.append(f"```")
            lines.append("")

        return "\n".join(lines)

    def _moment_to_scene(self, moment):
        actor = moment["actor"]
        fmdr = moment["fmdr"]
        text = moment["text"]

        # Extract actions as scene description
        actions = fmdr["actions"]
        if actions:
            scene = ", ".join(actions)
        else:
            # Fallback: extract visual sentences
            sentences = re.split(r"[.!?]", text)
            visual_sents = [s for s in sentences if any(kw in s.lower() for kw in ["покраснел", "дрожь", "пот", "волосы", "глаза", "улыб", "осанк", "плечи"])]
            scene = ", ".join(visual_sents[:2]) if visual_sents else f"{actor} in scene"

        # Add location context
        if "сауна" in text.lower() or "пар" in text.lower() or "steam" in text.lower():
            scene += ", sauna, steam, wooden interior"
        if "бассейн" in text.lower() or "pool" in text.lower():
            scene += ", pool, water, wet skin"
        if "комната отдыха" in text.lower() or "rest" in text.lower():
            scene += ", rest room, soft dim lights, tea"

        return scene

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Voyage Session Finalizer — один файл, весь pipeline")
    parser.add_argument("--log", required=True, help="Путь к логу сессии (.log или .txt)")
    parser.add_argument("--scenario", default="unknown", help="ID сценария (например, sauna_quartet)")
    parser.add_argument("--repo", default=str(REPO_DIR), help="Путь к репозиторию (default: ~/voyage-narrative-engine)")
    parser.add_argument("--no-git", action="store_true", help="Не делать git commit")
    args = parser.parse_args()

    globals()['REPO_DIR'] = Path(args.repo)
    globals()['SESSIONS_DIR'] = REPO_DIR / "sessions"
    globals()['PERSONAS_DIR'] = REPO_DIR / "personas"
    globals()['STATE_DIR'] = REPO_DIR / "state"
    globals()['ASSETS_DIR'] = REPO_DIR / "assets" / "images"

    log_path = Path(args.log)
    if not log_path.exists():
        error(f"Log file not found: {log_path}")

    info(f"=== Voyage Session Finalizer v1.0 ===")
    info(f"Log: {log_path}")
    info(f"Scenario: {args.scenario}")
    info(f"Repo: {REPO_DIR}")

    # 0. Ensure dirs
    ensure_dirs()

    # 1. Parse log
    info("\n[1/5] Parsing log...")
    entries = parse_log(log_path)
    info(f"  Entries: {len(entries)}")

    # 2. State Manager
    info("\n[2/5] State Manager...")
    sm = StateManager(entries, args.scenario)
    state = sm.process()

    # 3. Load personas
    info("\n[3/5] Loading personas...")
    personas = {}
    for char in ["kira", "sergey", "marina", "maksim"]:
        try:
            personas[char] = load_persona(f"{char.upper()}_MODULE_v14" if char == "kira" else f"{char.upper()}_MODULE_v4" if char == "sergey" else f"{char.upper()}_MODULE_v2")
            info(f"  Loaded: {char}")
        except SystemExit:
            warn(f"  Skipped: {char} (module not found)")

    # 4. Narrative Editor
    info("\n[4/5] Narrative Editor...")
    ne = NarrativeEditor(entries, state, args.scenario)
    story = ne.generate()

    # 5. Visual Pipeline
    info("\n[5/5] Visual Extractor + Physiognomist...")
    vp = VisualPipeline(entries, state, personas)
    vp.extract()
    visuals = vp.generate_prompts()

    # 6. Save outputs
    session_id = state["session_id"]
    info(f"\nSaving outputs for session: {session_id}")

    # STATE_UPDATE
    state_path = SESSIONS_DIR / "state" / f"STATE_UPDATE_{session_id}.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    info(f"  → {state_path}")

    # MEMORY_UPDATE
    memory = sm.generate_memory_update()
    memory_path = SESSIONS_DIR / "memory" / f"MEMORY_UPDATE_{session_id}.json"
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    info(f"  → {memory_path}")

    # STORY
    story_path = SESSIONS_DIR / "stories" / f"STORY_{session_id}.md"
    with open(story_path, "w", encoding="utf-8") as f:
        f.write(story)
    info(f"  → {story_path}")

    # VISUALS
    visuals_path = SESSIONS_DIR / "visuals" / f"VISUAL_PROMPTS_{session_id}.md"
    with open(visuals_path, "w", encoding="utf-8") as f:
        f.write(visuals)
    info(f"  → {visuals_path}")

    # 7. Update personas (apply memory changes)
    info("\nUpdating personas...")
    for update in memory:
        char = update["character"]
        if char not in personas:
            continue
        persona = personas[char]
        mem_changes = update["memory_changes"]

        # Update history
        if "history.push" in mem_changes:
            if "history" not in persona.get("memory", {}):
                persona.setdefault("memory", {})["history"] = []
            persona["memory"]["history"].append(mem_changes["history.push"])

        # Update flags
        if "flags" in mem_changes:
            persona.setdefault("memory", {}).setdefault("flags", {})
            persona["memory"]["flags"].update(mem_changes["flags"])

        # Save
        module_id = persona.get("id", f"{char.upper()}_MODULE")
        save_persona(module_id, persona)

    # 8. Git
    if not args.no_git:
        info("\nGit commit...")
        try:
            subprocess.run(["git", "add", "sessions/", "personas/"], cwd=REPO_DIR, check=True)
            subprocess.run(["git", "commit", "-m", 
                f"session: {session_id} {args.scenario}\nauto: state, story, visuals, memory updates"],
                cwd=REPO_DIR, check=True)
            info("  Git commit done")
        except subprocess.CalledProcessError as e:
            warn(f"  Git failed: {e}")

    info("\n=== DONE ===")
    info(f"Session: {session_id}")
    info(f"Outputs in: {SESSIONS_DIR}")
    info("\nNext steps:")
    info("  1. Review story:  less " + str(story_path))
    info("  2. Review visuals: less " + str(visuals_path))
    info("  3. Check state:   less " + str(state_path))
    info("  4. Generate images using prompts from visuals file")
    info("  5. Push to git:   git push origin main")

if __name__ == "__main__":
    main()
