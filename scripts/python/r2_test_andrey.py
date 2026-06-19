#!/usr/bin/env python3
# Prototype R2 pipeline test for ANDREY_SENIOR_MODULE_v1.2.json
# Extracts sections 6 (VSCNO), 7 (Internal State), 8 (AD), validates and compresses.

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = REPO / "personas" / "ANDREY_SENIOR_MODULE_v1.2.json"
OUTPUT_DIR = REPO


def load_input():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_vscno(vscno_by_sublevel):
    errors = []
    for sublevel, data in vscno_by_sublevel.items():
        vl = data.get("ВЛ")
        st = data.get("СТ")
        nz = data.get("НЖ")
        og = data.get("ОГ")
        if any(v is None for v in (vl, st, nz, og)):
            errors.append(f"{sublevel}: missing axis")
            continue
        if not all(0 <= v <= 4 for v in (vl, st, nz, og)):
            errors.append(f"{sublevel}: axis out of [0,4] -> {vl},{st},{nz},{og}")
        if vl + st + nz + og != 10:
            errors.append(f"{sublevel}: sum != 10 -> {vl}+{st}+{nz}+{og}={vl+st+nz+og}")
    return errors


def validate_internal_state(internal_state_by_sublevel):
    errors = []
    for sublevel, data in internal_state_by_sublevel.items():
        for key in ("desire", "anxiety", "desire_tension", "frustration"):
            val = data.get(key)
            if val is None:
                errors.append(f"{sublevel}: missing {key}")
            elif not (0 <= val <= 10):
                errors.append(f"{sublevel}: {key}={val} out of [0,10]")
    return errors


def validate_ad(ad_by_sublevel):
    errors = []
    warnings = []
    valid_codes = {"ФС", "ЛС", "СП", "СЛ", "КН", "ПД", "ДР", "ПУ", "ПР", "ВС"}
    baseline = {
        "У1-А": {"available": {"ПД", "ПУ"}, "forbidden": {"ФС", "ЛС", "ПР"}},
        "У1-Б": {"available": {"ПД", "ПУ", "КН"}, "forbidden": {"ФС", "ЛС"}},
        "У2-А": {"available": {"ПД", "ПУ", "КН", "ФС"}, "forbidden": {"ЛС", "ПР"}},
        "У2-Б": {"available": {"КН", "ФС", "ЛС"}, "forbidden": {"ПР", "СЛ"}},
        "У3-А": {"available": {"ПУ", "ПД", "СП"}, "forbidden": {"ПР", "ФС"}},
        "У3-Б": {"available": {"КН", "ФС", "ЛС", "ПР"}, "forbidden": {"ПУ", "ПД"}},
        "У4-А": {"available": {"ФС", "ЛС", "ПР", "СЛ"}, "forbidden": {"ПУ", "ПД"}},
        "У4-Б": {"available": {"ФС", "ЛС", "ПР", "СЛ", "КН", "СП", "ДР", "ВС"}, "forbidden": {"ПУ", "ПД"}},
        "У5-А": {"available": {"ПУ", "ФС", "СП", "КН"}, "forbidden": {"СЛ", "ПР"}},
        "У5-Б": {"available": {"ФС", "ЛС", "КН", "ВС"}, "forbidden": {"СЛ"}},
        "У6-А": {"available": {"СП", "СЛ", "ПР"}, "forbidden": {"ФС", "ЛС"}},
        "У6-Б": {"available": {"ВС", "ДР"}, "forbidden": {"ФС", "ЛС", "ПР", "СЛ", "ПУ", "ПД", "КН", "СП"}},
        "У7-А": {"available": {"СЛ", "ПР", "ФС"}, "forbidden": {"ПУ", "ПД", "ВС"}},
        "У7-Б": {"available": {"СЛ", "ПР", "ФС"}, "forbidden": {"ПУ", "ПД", "ВС", "СП"}},
    }
    for sublevel, data in ad_by_sublevel.items():
        avail = set(data.get("available", []))
        forb = set(data.get("forbidden", []))
        is_adapted = "[ADAPTED]" in str(data.get("source", ""))
        if not avail.issubset(valid_codes):
            errors.append(f"{sublevel}: invalid available codes {avail - valid_codes}")
        if not forb.issubset(valid_codes):
            errors.append(f"{sublevel}: invalid forbidden codes {forb - valid_codes}")
        if sublevel in baseline:
            base = baseline[sublevel]
            if avail != base["available"]:
                missing = base["available"] - avail
                msg = f"{sublevel}: baseline available {missing} differs"
                if is_adapted:
                    warnings.append(f"{msg} ([ADAPTED] marked)")
                else:
                    errors.append(f"{msg} without [ADAPTED]")
            if forb != base["forbidden"]:
                missing_forb = base["forbidden"] - forb
                msg = f"{sublevel}: baseline forbidden {missing_forb} differs"
                if is_adapted:
                    warnings.append(f"{msg} ([ADAPTED] marked)")
                else:
                    errors.append(f"{msg} without [ADAPTED]")
    return errors, warnings


def generate_psychology_full(module, vscno, internal_state, ad):
    lines = []
    lines.append("# PSYCHOLOGY_ANDREY_SENIOR_TEST.md")
    lines.append("# Prototype R2 output — sections 6, 7, 8 only")
    lines.append(f"# Source: {INPUT_FILE.name}")
    lines.append(f"# Persona: {module['name']} | Archetype: {module['psychology'].get('core_conflict', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1-5. [STUB] Attachment / Cognitive Distortions / IFS / Regression / Resources")
    lines.append("> These sections are stubbed for the prototype test. Full generation requires R1 PORTRAIT input.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. VSCNO-матрица (14 подуровней)")
    lines.append("")
    lines.append("| Подуровень | ВЛ | СТ | НЖ | ОГ | Сумма | Примечание |")
    lines.append("|------------|----|----|----|----|-------|------------|")
    order = ["У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А", "У4-Б",
             "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б"]
    for sl in order:
        d = vscno[sl]
        s = d["ВЛ"] + d["СТ"] + d["НЖ"] + d["ОГ"]
        note = d.get("source", "").replace("[ADAPTED]", "🟡").replace("[CORE]", "🟢")
        lines.append(f"| {sl} | {d['ВЛ']} | {d['СТ']} | {d['НЖ']} | {d['ОГ']} | {s} | {note} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Internal State (14 подуровней)")
    lines.append("")
    lines.append("| Подуровень | desire | anxiety | desire_tension | frustration | Примечание |")
    lines.append("|------------|--------|---------|----------------|-------------|------------|")
    for sl in order:
        d = internal_state[sl]
        note = d.get("source", "").replace("[ADAPTED]", "🟡").replace("[CORE]", "🟢")
        lines.append(f"| {sl} | {d['desire']} | {d['anxiety']} | {d['desire_tension']} | {d['frustration']} | {note} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. AD-карта (14 подуровней)")
    lines.append("")
    lines.append("| Подуровень | Доступные АД | Запрещённые АД | Доминантный | Примечание |")
    lines.append("|------------|--------------|----------------|-------------|------------|")
    for sl in order:
        d = ad[sl]
        avail = ", ".join(d["available"])
        forb = ", ".join(d["forbidden"])
        dom = d.get("dominant", "-")
        note = d.get("source", "").replace("[ADAPTED]", "🟡").replace("[CORE]", "🟢")
        lines.append(f"| {sl} | {avail} | {forb} | {dom} | {note} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9-14. [STUB] Memory / Safety / Relational / TEC / Confidence / Metadata")
    lines.append("> Stubbed for prototype. See full module for these sections.")
    lines.append("")
    return "\n".join(lines)


def generate_compact(vscno, internal_state, ad):
    lines = []
    lines.append("# PSYCHOLOGY_ANDREY_SENIOR_TEST_COMPACT.md")
    lines.append("# R2 COMPACT output — _linear_table + _base_delta")
    lines.append("")
    lines.append("## 1. VSCNO + AD (_linear_table)")
    lines.append("<!-- _linear_table: VSCNO_AD -->")
    lines.append("| У | ВЛ | СТ | НЖ | ОГ | Доступные АД | Запрещённые АД |")
    lines.append("|---|----|----|----|----|--------------|----------------|")
    order = ["У1-А", "У1-Б", "У2-А", "У2-Б", "У3-А", "У3-Б", "У4-А", "У4-Б",
             "У5-А", "У5-Б", "У6-А", "У6-Б", "У7-А", "У7-Б"]
    for sl in order:
        v = vscno[sl]
        a = ad[sl]
        avail = ", ".join(a["available"])
        forb = ", ".join(a["forbidden"])
        lines.append(f"| {sl.replace('У', '')} | {v['ВЛ']} | {v['СТ']} | {v['НЖ']} | {v['ОГ']} | {avail} | {forb} |")
    lines.append("<!-- _end_linear_table -->")
    lines.append("")
    lines.append("## 2. Internal State (_base_delta)")
    lines.append("<!-- _base_delta: INTERNAL_STATE -->")
    base = internal_state["У1-А"]
    lines.append(f"**Базовый профиль (У1-А):** desire={base['desire']}, anxiety={base['anxiety']}, tension={base['desire_tension']}, frustration={base['frustration']}")
    lines.append("")
    lines.append("| У | Δ desire | Δ anxiety | Δ tension | Δ frustration | Итого |")
    lines.append("|---|----------|-----------|-----------|---------------|-------|")
    for sl in order:
        d = internal_state[sl]
        if sl == "У1-А":
            deltas = (0, 0, 0, 0)
        else:
            deltas = (
                d["desire"] - base["desire"],
                d["anxiety"] - base["anxiety"],
                d["desire_tension"] - base["desire_tension"],
                d["frustration"] - base["frustration"],
            )
        def fmt(n):
            return f"{n:+d}"
        total = f"{d['desire']},{d['anxiety']},{d['desire_tension']},{d['frustration']}"
        lines.append(f"| {sl.replace('У', '')} | {fmt(deltas[0])} | {fmt(deltas[1])} | {fmt(deltas[2])} | {fmt(deltas[3])} | {total} |")
    lines.append("<!-- _end_base_delta -->")
    lines.append("")
    return "\n".join(lines)


def generate_audit_report(vscno_errors, is_errors, ad_errors, ad_warnings=None):
    ad_warnings = ad_warnings or []
    critical = vscno_errors + is_errors + ad_errors
    status = "PASS" if not critical else "FAIL"
    lines = []
    lines.append("# AUDIT_REPORT_ANDREY_SENIOR_TEST.md")
    lines.append("# Prototype R2 audit — sections 6, 7, 8")
    lines.append("")
    lines.append(f"**Date:** 2026-06-17")
    lines.append(f"**Auditor:** R2 prototype script")
    lines.append(f"**Overall Status:** {status}")
    lines.append("")
    lines.append("## Секция A: VSCNO (CRITICAL)")
    lines.append(f"- Errors: {len(vscno_errors)}")
    if vscno_errors:
        for e in vscno_errors:
            lines.append(f"  - ❌ {e}")
    else:
        lines.append("  - ✅ All 14 sublevels sum to 10, axes in [0,4]")
    lines.append("")
    lines.append("## Секция B: Internal State (CRITICAL)")
    lines.append(f"- Errors: {len(is_errors)}")
    if is_errors:
        for e in is_errors:
            lines.append(f"  - ❌ {e}")
    else:
        lines.append("  - ✅ All values in [0,10]")
    lines.append("")
    lines.append("## Секция C: AD-matrix (CRITICAL)")
    lines.append(f"- Errors: {len(ad_errors)}")
    if ad_errors:
        for e in ad_errors:
            lines.append(f"  - ❌ {e}")
    else:
        lines.append("  - ✅ All codes valid, baseline consistency OK (adaptations marked)")
    if ad_warnings:
        lines.append(f"- Warnings: {len(ad_warnings)}")
        for w in ad_warnings:
            lines.append(f"  - ⚠️ {w}")
    lines.append("")
    lines.append("## Итог")
    lines.append(f"- CRITICAL (A+B+C): {status}")
    lines.append("- Готов к компрессии: " + ("✅ ДА" if status == "PASS" else "❌ НЕТ"))
    lines.append("")
    return "\n".join(lines), status


def main():
    module = load_input()
    vscno = module.get("vscno_by_sublevel", {})
    internal_state = module.get("internal_state_by_sublevel", {})
    ad = module.get("ad_by_sublevel", {})

    vscno_errors = validate_vscno(vscno)
    is_errors = validate_internal_state(internal_state)
    ad_errors, ad_warnings = validate_ad(ad)

    full_md = generate_psychology_full(module, vscno, internal_state, ad)
    compact_md = generate_compact(vscno, internal_state, ad)
    audit_md, status = generate_audit_report(vscno_errors, is_errors, ad_errors, ad_warnings)

    (OUTPUT_DIR / "PSYCHOLOGY_ANDREY_SENIOR_TEST.md").write_text(full_md, encoding="utf-8")
    (OUTPUT_DIR / "PSYCHOLOGY_ANDREY_SENIOR_TEST_COMPACT.md").write_text(compact_md, encoding="utf-8")
    (OUTPUT_DIR / "AUDIT_REPORT_ANDREY_SENIOR_TEST.md").write_text(audit_md, encoding="utf-8")

    print(f"Generated files in {OUTPUT_DIR}:")
    print("  - PSYCHOLOGY_ANDREY_SENIOR_TEST.md")
    print("  - PSYCHOLOGY_ANDREY_SENIOR_TEST_COMPACT.md")
    print("  - AUDIT_REPORT_ANDREY_SENIOR_TEST.md")
    print(f"Audit status: {status}")
    if status != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
