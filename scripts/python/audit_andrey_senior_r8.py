#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8 Auditor: personas/andrey_senior/ vs ANDREY_SENIOR_MODULE_v1.2.json"""

import json
import os
from pathlib import Path

ROOT = Path("c:/DEV/Narrative/voyage-narrative-engine")
SRC = ROOT / "personas" / "ANDREY_SENIOR_MODULE_v1.2.json"
MOD = ROOT / "personas" / "andrey_senior"
REPORT = ROOT / "AUDIT_REPORT_ANDREY_SENIOR_R8.md"

VSCNO_AXES = ["ВЛ", "СТ", "НЖ", "ОГ"]
AD_CODES = ["ФС", "ЛС", "СП", "СЛ", "КН", "ПД", "ДР", "ПУ", "ПР", "ВС"]
SUBLEVELS = [
    "У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А",
    "У4-Б", "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б",
]

ISSUES = []
WARNINGS = []


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def add_issue(section, msg):
    ISSUES.append(f"[{section}] {msg}")


def add_warning(section, msg):
    WARNINGS.append(f"[{section}] {msg}")


def check_structural_integrity(src, mod):
    index = load_json(mod / "INDEX.json")
    required = [k for k, v in index["modules"].items() if v.get("required", False)]
    missing = []
    for rel in required:
        if not (mod / rel).exists():
            missing.append(rel)
    if missing:
        add_issue("A.STRUCTURAL", f"Missing required files: {missing}")
    else:
        print("  A.STRUCTURAL: OK")

    # Validate all JSON
    bad = []
    for root, dirs, files in os.walk(mod):
        for fn in files:
            if fn.endswith(".json"):
                p = Path(root) / fn
                try:
                    load_json(p)
                except Exception as e:
                    bad.append(f"{p.relative_to(mod)}: {e}")
    if bad:
        add_issue("B.JSON", "Invalid JSON files:\n" + "\n".join(bad))
    else:
        print("  B.JSON: OK")


def check_vscno(src, mod):
    errors = 0
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        vscno = data.get("vscno", {})
        total = sum(vscno.get(k, 0) for k in VSCNO_AXES)
        if total != 10:
            add_issue("C.VSCNO", f"{sl}: sum={total} (expected 10)")
            errors += 1
        for k in VSCNO_AXES:
            val = vscno.get(k, -1)
            if val < 0 or val > 4:
                add_issue("C.VSCNO", f"{sl}: {k}={val} (expected [0,4])")
                errors += 1
    if errors == 0:
        print("  C.VSCNO: OK")

    # Attachment-style consistency check
    base = load_json(mod / "psychology" / "ATTACHMENT.json")
    style = base["attachment_sexuality"]["style"]
    if style == "anxious-preoccupied":
        # Check if СТ is elevated on early levels
        low_st_count = 0
        for sl in ["У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б"]:
            fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
            data = load_json(mod / "levels" / fname)
            st = data["vscno"].get("СТ", 0)
            if st < 3:
                low_st_count += 1
        if low_st_count >= 4:
            add_warning("C.VSCNO",
                f"attachment style is '{style}' but СТ is low (<3) on {low_st_count}/6 early sublevels. "
                f"Typical anxious-preoccupied profile expects СТ 3-4 on early levels. "
                f"This may be an [ADAPTED] artifact from v1.2.")


def check_internal_state(src, mod):
    errors = 0
    keys = ["desire", "anxiety", "desire_tension", "frustration"]
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        state = data.get("internal_state", {})
        for k in keys:
            val = state.get(k, -1)
            if val < 0 or val > 10:
                add_issue("D.INTERNAL_STATE", f"{sl}: {k}={val} (expected [0,10])")
                errors += 1
    if errors == 0:
        print("  D.INTERNAL_STATE: OK")


def check_ad(src, mod):
    errors = 0
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        ad = data.get("ad_availability", {})
        available = set(ad.get("available", []))
        forbidden = set(ad.get("forbidden", []))
        dominant = ad.get("dominant", "")
        # No invalid codes
        union = available | forbidden
        extra = union - set(AD_CODES)
        if extra:
            add_issue("E.AD", f"{sl}: unknown AD codes: {extra}")
            errors += 1
        # No overlap
        if available & forbidden:
            add_issue("E.AD", f"{sl}: overlap available/forbidden: {available & forbidden}")
            errors += 1
        # Dominant in available
        if dominant and dominant not in available:
            add_issue("E.AD", f"{sl}: dominant '{dominant}' not in available")
            errors += 1
    if errors == 0:
        print("  E.AD: OK")


def check_tec(src, mod):
    tec = load_json(mod / "psychology" / "TEC.json")
    expected = ["TEC_001", "TEC_002", "TEC_003", "TEC_004", "TEC_005", "TEC_006", "TEC_007", "TEC_008"]
    missing = [k for k in expected if k not in tec["tec_mechanics"]]
    if missing:
        add_issue("F.TEC", f"Missing TEC entries: {missing}")
    else:
        print("  F.TEC: OK")


def check_cross_persona_sync(src, mod):
    matrix = load_json(mod / "relationships" / "MATRIX.json")
    rels = set(matrix["relationships"].keys())
    expected_rels = {"kira", "marina", "olga", "andrey_junior"}
    if rels != expected_rels:
        add_issue("G.CROSS_PERSONA", f"Relationships mismatch: got {rels}, expected {expected_rels}")
    else:
        print("  G.CROSS_PERSONA (relationships): OK")

    level_lock = load_json(mod / "dynamics" / "LEVEL_LOCK_MATRIX.json")
    expected_pairs = {"ANDREY_SENIOR_KIRA", "ANDREY_SENIOR_MARINA", "ANDREY_SENIOR_OLGA",
                      "ANDREY_SENIOR_ANDREY_JUNIOR", "KIRA_MARINA"}
    pairs = set(level_lock["level_lock_matrix"].keys())
    if pairs != expected_pairs:
        add_issue("G.CROSS_PERSONA", f"Level-lock pairs mismatch: got {pairs}, expected {expected_pairs}")
    else:
        print("  G.CROSS_PERSONA (level_lock): OK")


def check_safety(src, mod):
    safety = load_json(mod / "safety" / "PROTOCOL.json")
    if not safety.get("stop_words"):
        add_issue("H.SAFETY", "stop_words empty")
    if not safety.get("hard_limits"):
        add_issue("H.SAFETY", "hard_limits empty")
    if safety.get("ag_max", 0) < 1:
        add_issue("H.SAFETY", f"ag_max invalid: {safety.get('ag_max')}")
    if not ISSUES or "H.SAFETY" not in [i.split("]")[0] for i in ISSUES]:
        print("  H.SAFETY: OK")


def check_data_integrity(src, mod):
    """Reassemble key fields and compare to source monolith."""
    mismatches = []

    # VSCNO by sublevel
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        mod_vscno = data.get("vscno", {})
        src_vscno = src["vscno_by_sublevel"].get(sl, {})
        for k in VSCNO_AXES:
            if mod_vscno.get(k) != src_vscno.get(k):
                mismatches.append(f"vscno.{sl}.{k}: mod={mod_vscno.get(k)} src={src_vscno.get(k)}")

    # Internal state
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        mod_state = data.get("internal_state", {})
        src_state = src["internal_state_by_sublevel"].get(sl, {})
        for k in ["desire", "anxiety", "desire_tension", "frustration"]:
            if mod_state.get(k) != src_state.get(k):
                mismatches.append(f"internal_state.{sl}.{k}: mod={mod_state.get(k)} src={src_state.get(k)}")

    # AD
    for sl in SUBLEVELS:
        fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
        data = load_json(mod / "levels" / fname)
        mod_ad = data.get("ad_availability", {})
        src_ad = src["ad_by_sublevel"].get(sl, {})
        if set(mod_ad.get("available", [])) != set(src_ad.get("available", [])):
            mismatches.append(f"ad.{sl}.available mismatch")
        if set(mod_ad.get("forbidden", [])) != set(src_ad.get("forbidden", [])):
            mismatches.append(f"ad.{sl}.forbidden mismatch")
        if mod_ad.get("dominant") != src_ad.get("dominant"):
            mismatches.append(f"ad.{sl}.dominant: mod={mod_ad.get('dominant')} src={src_ad.get('dominant')}")

    # Relationships
    rel_mod = load_json(mod / "relationships" / "MATRIX.json")["relationships"]
    rel_src = src["relationships"]
    if rel_mod != rel_src:
        mismatches.append("relationships/MATRIX.json mismatch")

    if mismatches:
        add_issue("I.DATA_INTEGRITY", "Mismatches against source monolith:\n- " + "\n- ".join(mismatches))
    else:
        print("  I.DATA_INTEGRITY: OK")


def check_test_assembly(src, mod):
    """Simulate assembly: load all required modules into one dict."""
    try:
        assembled = {}
        assembled["identity"] = load_json(mod / "core" / "IDENTITY.json")
        assembled["psychology_base"] = load_json(mod / "psychology" / "BASE.json")
        assembled["safety"] = load_json(mod / "safety" / "PROTOCOL.json")
        assembled["relationships"] = load_json(mod / "relationships" / "MATRIX.json")
        for sl in SUBLEVELS:
            fname = sl.replace("У", "U").replace("А", "A").replace("Б", "B") + ".json"
            assembled[f"level_{sl}"] = load_json(mod / "levels" / fname)
        print("  J.TEST_ASSEMBLY: OK")
    except Exception as e:
        add_issue("J.TEST_ASSEMBLY", f"Assembly failed: {e}")


def generate_report():
    status = "PASS" if not ISSUES else "FAIL"
    lines = [
        "# AUDIT_REPORT_ANDREY_SENIOR_R8.md",
        "",
        f"**Overall Status:** {status}",
        f"**Date:** auto-generated",
        f"**Source Monolith:** `personas/ANDREY_SENIOR_MODULE_v1.2.json`",
        f"**Modular Target:** `personas/andrey_senior/`",
        "",
        "## Scope",
        "Structural integrity, JSON validity, VSCNO, Internal State, AD availability, TEC, Cross-Persona Sync, Safety, Data Integrity, Test Assembly.",
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
        "Модульная структура корректно отражает исходный монолит." if status == "PASS" else "Модульная структура содержит ошибки и требует исправления.",
    ])

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport written: {REPORT}")


def main():
    print("R8 Auditor: ANDREY_SENIOR modular structure")
    src = load_json(SRC)

    check_structural_integrity(src, MOD)
    check_vscno(src, MOD)
    check_internal_state(src, MOD)
    check_ad(src, MOD)
    check_tec(src, MOD)
    check_cross_persona_sync(src, MOD)
    check_safety(src, MOD)
    check_data_integrity(src, MOD)
    check_test_assembly(src, MOD)

    generate_report()

    if ISSUES:
        print("\nAUDIT FAILED")
        raise SystemExit(1)
    else:
        print("\nAUDIT PASSED")


if __name__ == "__main__":
    main()
