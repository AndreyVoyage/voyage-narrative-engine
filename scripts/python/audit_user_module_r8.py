#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8 Auditor: personas/user/ vs USER_MODULE.json"""

import json
import os
from pathlib import Path

ROOT = Path("c:/DEV/Narrative/voyage-narrative-engine")
SRC = ROOT / "personas" / "USER_MODULE.json"
MOD = ROOT / "personas" / "user"
REPORT = ROOT / "AUDIT_REPORT_user.md"

SUBLEVELS = [
    "У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А",
    "У4-Б", "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б",
]
VSCNO_AXES = ["ВЛ", "СТ", "НЖ", "ОГ"]

ISSUES = []
WARNINGS = []


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_issue(section, msg):
    ISSUES.append(f"[{section}] {msg}")


def add_warning(section, msg):
    WARNINGS.append(f"[{section}] {msg}")


def sublevel_filename(sl):
    return sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"


def main():
    print("R8 Auditor: USER modular structure")
    src = load_json(SRC)

    # A. Structural integrity
    index = load_json(MOD / "INDEX.json")
    required = [k for k, v in index["modules"].items() if v.get("required", False)]
    missing = [r for r in required if not (MOD / r).exists()]
    if missing:
        add_issue("A.STRUCTURAL", f"Missing required files: {missing}")
    else:
        print("  A.STRUCTURAL: OK")

    # B. JSON validity
    bad = []
    for root, dirs, files in os.walk(MOD):
        for fn in files:
            if fn.endswith(".json"):
                p = Path(root) / fn
                try:
                    load_json(p)
                except Exception as e:
                    bad.append(f"{p.relative_to(MOD)}: {e}")
    if bad:
        add_issue("B.JSON", "Invalid JSON files:\n" + "\n".join(bad))
    else:
        print("  B.JSON: OK")

    # C. VSCNO sum = 10 (skip empty, warn if partial)
    vscno_present = False
    for sl in SUBLEVELS:
        data = load_json(MOD / "levels" / sublevel_filename(sl))
        vscno = data.get("vscno", {})
        if not vscno:
            continue
        vscno_present = True
        total = sum(vscno.get(k, 0) for k in VSCNO_AXES)
        if total != 10:
            add_warning("C.VSCNO", f"{sl}: sum={total} (expected 10)")
        for k in VSCNO_AXES:
            val = vscno.get(k, -1)
            if val < 0 or val > 4:
                add_issue("C.VSCNO", f"{sl}: {k}={val} (expected [0,4])")
    if not vscno_present:
        add_warning("C.VSCNO", "No VSCNO data in level files (USER_MODULE has no per-sublevel VSCNO).")
    if not any(i.startswith("[C.VSCNO]") for i in ISSUES):
        print("  C.VSCNO: OK (no critical errors)")

    # D. Safety
    safety = load_json(MOD / "safety" / "PROTOCOL.json")
    if not safety.get("stop_words"):
        add_issue("D.SAFETY", "stop_words empty")
    if not safety.get("emergency_response"):
        add_issue("D.SAFETY", "emergency_response empty")
    if not safety.get("cooldown_phrase"):
        add_warning("D.SAFETY", "cooldown_phrase empty")
    if not any(i.startswith("[D.SAFETY]") for i in ISSUES):
        print("  D.SAFETY: OK")

    # E. Data integrity — key fields preserved
    identity = load_json(MOD / "core" / "IDENTITY.json")
    mismatches = []
    if identity.get("name") != src.get("name"):
        mismatches.append(f"name: mod={identity.get('name')} src={src.get('name')}")
    env = load_json(MOD / "environment" / "STATE_TRIGGERS.json")
    if env.get("triggers") != src.get("triggers"):
        mismatches.append("triggers mismatch")
    safety_mod = load_json(MOD / "safety" / "PROTOCOL.json")
    src_safety = src.get("safety", {})
    if safety_mod.get("stop_words") != src_safety.get("stop_words"):
        mismatches.append("stop_words mismatch")
    if safety_mod.get("emergency_response") != src_safety.get("emergency_response"):
        mismatches.append("emergency_response mismatch")
    if mismatches:
        add_issue("E.DATA_INTEGRITY", "Mismatches:\n- " + "\n- ".join(mismatches))
    else:
        print("  E.DATA_INTEGRITY: OK")

    # F. Test assembly
    try:
        load_json(MOD / "core" / "IDENTITY.json")
        load_json(MOD / "psychology" / "BASE.json")
        load_json(MOD / "safety" / "PROTOCOL.json")
        load_json(MOD / "environment" / "STATE_TRIGGERS.json")
        load_json(MOD / "INDEX.json")
        print("  F.TEST_ASSEMBLY: OK")
    except Exception as e:
        add_issue("F.TEST_ASSEMBLY", f"Assembly failed: {e}")

    # Report
    status = "PASS" if not ISSUES else "FAIL"
    lines = [
        "# AUDIT_REPORT_user.md",
        "",
        f"**Overall Status:** {status}",
        f"**Source Monolith:** `personas/USER_MODULE.json`",
        f"**Modular Target:** `personas/user/`",
        "",
        "## Summary",
        f"- Critical Issues: {len(ISSUES)}",
        f"- Warnings: {len(WARNINGS)}",
        "",
        "## Issues",
    ]
    if ISSUES:
        for i in ISSUES:
            lines.append(f"- {i}")
    else:
        lines.append("- None")

    lines.extend(["", "## Warnings"])
    if WARNINGS:
        for w in WARNINGS:
            lines.append(f"- {w}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Conclusion",
        "Модульная структура корректно отражает исходный USER_MODULE." if status == "PASS" else "Модульная структура содержит ошибки.",
    ])

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport written: {REPORT}")

    if ISSUES:
        print("AUDIT FAILED")
        raise SystemExit(1)
    else:
        print("AUDIT PASSED")


if __name__ == "__main__":
    main()
