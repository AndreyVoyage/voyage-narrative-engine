#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_finalize.py — Финализация сессии Voyage Narrative Engine

Функции:
  1. Загружает state (state/current_state.json)
  2. Загружает активную persona (personas/{name}_MODULE.json)
  3. Обновляет persona: память, отношения, эмоциональные метрики
  4. Сохраняет лог сессии в sessions/raw/YYYY-MM-DD_HH-MM_{persona}.json
  5. Генерирует summary сессии
  6. Сбрасывает state для новой сессии
  7. Опционально: git commit + push

Использование:
  python3 session_finalize.py                    # авто из state
  python3 session_finalize.py --persona KIRA       # явно
  python3 session_finalize.py --no-git             # без git
  python3 session_finalize.py --dry-run            # только показать
"""

import json
import os
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================
REPO_ROOT = Path(__file__).parent.resolve()
STATE_FILE = REPO_ROOT / "state" / "current_state.json"
PERSONAS_DIR = REPO_ROOT / "personas"
SESSIONS_DIR = REPO_ROOT / "sessions" / "raw"
STATE_BACKUP_DIR = REPO_ROOT / "state" / "backup"

# =============================================================================
# UTILS
# =============================================================================
def log(msg, level="INFO"):
    colors = {"INFO": "\033[36m", "OK": "\033[32m", "WARN": "\033[33m", "ERR": "\033[31m", "RESET": "\033[0m"}
    print(f"{colors.get(level, '')}[{level}]{colors['RESET']} {msg}")

def load_json(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    log(f"Сохранено: {path}", "OK")

def run_git(cmd, cwd=None):
    try:
        result = subprocess.run(["git"] + cmd, cwd=cwd or str(REPO_ROOT), capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "git не найден"

# =============================================================================
# PERSONA UPDATE ENGINE
# =============================================================================
def update_persona_memory(persona, state):
    events = state.get("events_log", [])
    memory = persona.get("memory", {})
    if not isinstance(memory, dict):
        memory = {"episodes": [], "facts": [], "relationship_milestones": []}
    episodes = memory.get("episodes", [])
    facts = memory.get("facts", [])
    milestones = memory.get("relationship_milestones", [])
    for event in events:
        etype = event.get("type", "unknown")
        content = event.get("content", "")
        impact = event.get("impact", 0)
        if etype == "dialogue" and abs(impact) >= 3:
            episodes.append({"timestamp": event.get("timestamp", datetime.now().isoformat()), "content": content[:500], "impact": impact, "emotion": event.get("emotion", "neutral")})
        elif etype == "discovery":
            facts.append({"timestamp": event.get("timestamp", datetime.now().isoformat()), "fact": content[:300], "category": event.get("category", "general")})
        elif etype == "milestone":
            milestones.append({"timestamp": event.get("timestamp", datetime.now().isoformat()), "milestone": content[:300], "relationship_delta": impact})
    memory["episodes"] = episodes[-50:]
    memory["facts"] = facts[-100:]
    memory["relationship_milestones"] = milestones[-30:]
    persona["memory"] = memory
    return persona

def update_relationship_metrics(persona, state):
    rel = persona.get("relationship", {})
    if not isinstance(rel, dict):
        rel = {}
    changes = state.get("relationship_changes", {})
    for key, delta in changes.items():
        current = rel.get(key, 50)
        new_val = max(0, min(100, current + delta))
        rel[key] = new_val
        log(f"  Отношение '{key}': {current} → {new_val} (Δ{delta:+.0f})")
    persona["relationship"] = rel
    return persona

def update_emotional_state(persona, state):
    events = state.get("events_log", [])
    if not events:
        return persona
    emotions = persona.get("emotional_state", {})
    if not isinstance(emotions, dict):
        emotions = {}
    total_impact = sum(e.get("impact", 0) for e in events)
    avg_impact = total_impact / len(events) if events else 0
    emotions["session_avg_impact"] = round(avg_impact, 2)
    emotions["last_session_date"] = datetime.now().isoformat()
    emotions["dominant_emotion"] = state.get("dominant_emotion", emotions.get("dominant_emotion", "neutral"))
    persona["emotional_state"] = emotions
    return persona

def update_vscno(persona, state):
    vscno = persona.get("VSCNO", {})
    if not isinstance(vscno, dict):
        return persona
    total = sum(vscno.values()) if vscno else 0
    if total != 10 and vscno:
        log(f"WARN: VSCNO сумма = {total} (ожидалось 10). Корректирую.", "WARN")
        if total > 0:
            factor = 10 / total
            vscno = {k: round(v * factor, 2) for k, v in vscno.items()}
        persona["VSCNO"] = vscno
    return persona

# =============================================================================
# SESSION ARCHIVE
# =============================================================================
def archive_session(state, persona_name):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{ts}_{persona_name}.json"
    path = SESSIONS_DIR / filename
    archive = {
        "meta": {"archived_at": datetime.now().isoformat(), "persona": persona_name, "session_id": state.get("session_id", "unknown"), "duration_minutes": state.get("duration_minutes", 0)},
        "state_snapshot": state
    }
    save_json(path, archive)
    return path

def generate_summary(state, persona_name):
    events = state.get("events_log", [])
    changes = state.get("relationship_changes", {})
    lines = ["=" * 60, f"  SESSION SUMMARY — {persona_name}", f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}", "=" * 60, "", f"Событий: {len(events)}", f"Изменений в отношениях: {len(changes)}", ""]
    if changes:
        lines.append("Изменения отношений:")
        for k, v in changes.items():
            lines.append(f"  • {k}: {v:+.0f}")
        lines.append("")
    if events:
        lines.append("Ключевые события:")
        for e in events[-10:]:
            lines.append(f"  [{e.get('type','?')}] {e.get('content','')[:80]}...")
        lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)

# =============================================================================
# STATE RESET
# =============================================================================
def reset_state(state, persona_name):
    return {
        "session_id": f"{persona_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "active_persona": persona_name,
        "session_start": datetime.now().isoformat(),
        "events_log": [],
        "relationship_changes": {},
        "dominant_emotion": "neutral",
        "duration_minutes": 0,
        "version": state.get("version", "1.0")
    }

# =============================================================================
# MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Финализация сессии Voyage Narrative Engine")
    parser.add_argument("--persona", type=str, help="Имя persona (авто из state)")
    parser.add_argument("--no-git", action="store_true", help="Не выполнять git commit/push")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет сделано")
    args = parser.parse_args()

    log("=== Voyage Session Finalizer ===")
    state = load_json(STATE_FILE)
    if not state:
        log(f"State не найден: {STATE_FILE}", "ERR")
        sys.exit(1)
    persona_name = args.persona or state.get("active_persona", "UNKNOWN")
    log(f"Persona: {persona_name}")

    persona_path = PERSONAS_DIR / f"{persona_name}_MODULE.json"
    persona = load_json(persona_path)
    if not persona:
        log(f"Persona не найдена: {persona_path}", "ERR")
        sys.exit(1)
    log(f"Загружена persona: {persona_path}")

    if args.dry_run:
        log("DRY-RUN: изменения не будут сохранены", "WARN")

    log("Обновление памяти...")
    persona = update_persona_memory(persona, state)
    log("Обновление отношений...")
    persona = update_relationship_metrics(persona, state)
    log("Обновление эмоционального состояния...")
    persona = update_emotional_state(persona, state)
    log("Проверка VSCNO...")
    persona = update_vscno(persona, state)

    log("Архивирование сессии...")
    archive_path = archive_session(state, persona_name)
    summary = generate_summary(state, persona_name)
    summary_path = SESSIONS_DIR / f"{archive_path.stem}_SUMMARY.txt"
    if not args.dry_run:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        log(f"Summary: {summary_path}", "OK")
    print("\n" + summary + "\n")

    if not args.dry_run:
        save_json(persona_path, persona)
        STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = STATE_BACKUP_DIR / f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(backup_path, state)
        new_state = reset_state(state, persona_name)
        save_json(STATE_FILE, new_state)

    if not args.no_git and not args.dry_run:
        log("Git commit & push...")
        run_git(["add", "."])
        rc, out, err = run_git(["status", "--short"])
        if out.strip():
            rc, out, err = run_git(["commit", "-m", f"session: finalize {persona_name} @ {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
            if rc == 0:
                rc, out, err = run_git(["push", "origin", "main"])
                log("Push OK" if rc == 0 else f"Push failed: {err}", "OK" if rc == 0 else "ERR")
            else:
                log(f"Commit failed: {err}", "ERR")
        else:
            log("Нет изменений для коммита", "WARN")

    log("=== Финализация завершена ===", "OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
