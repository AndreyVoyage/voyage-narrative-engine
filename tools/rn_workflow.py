#!/usr/bin/env python3
"""
RN Workflow — read-only RenPy/VNE workflow checker.
Phase 1: status, safety-scan, validate, baseline-report.

Usage:
    python tools/rn_workflow.py status
    python tools/rn_workflow.py safety-scan
    python tools/rn_workflow.py safety-scan --scope full
    python tools/rn_workflow.py safety-scan --scope scene --scene SC_014
    python tools/rn_workflow.py validate
    python tools/rn_workflow.py validate --allow-feature-branch
    python tools/rn_workflow.py validate --allow-feature-branch --allow-untracked-tool
    python tools/rn_workflow.py baseline-report
    python tools/rn_workflow.py baseline-report --allow-feature-branch
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_RPY = Path("novel/game/script.rpy")
SCENARIOS_DIR = Path("scenarios")
REPORTS_DIR = Path("reports/renpy")
VOYAGE_TASKS_DB = Path(".voyage/tasks.db")

EXPECTED_SELECTOR = 12
EXPECTED_LABEL_COUNT = 85
EXPECTED_JUMP_COUNT = 84
EXPECTED_LATEST_SCENE = "SC_014"
EXPECTED_LATEST_SCENE_NUM = 14
SC014_EXPECTED_KIRA = 3
SC014_EXPECTED_SERGEY = 3
SC014_EXPECTED_YAKOV = 0
SC014_MARKER = "Забери меня"  # "Забери меня"

FORBIDDEN_TERMS = [
    "груд",          # груд
    "бедра",    # бедра
    "бёдра",    # бёдра
    "бёдрах",  # бёдрах
    "между её ног",  # между её ног
    "стон",          # стон
    "возбужд",  # возбужд
    "поцелуй",  # поцелуй
    "целует",         # целует
    "кожа к коже",  # кожа к коже
    "сексу",    # сексу
    "эрот",          # эрот
    "желание в теле",  # желание в теле
    "силой",    # силой
    "застав",  # застав
    "удерж",    # удерж
    "не отпуска",  # не отпуска
    "постель",   # постель
    "кровать",   # кровать
    "раздет",         # раздет
    "ты моя",              # ты моя
    "ты — моя",       # ты — моя
    "Ты моя",              # Ты моя
    "Ты — моя",       # Ты — моя
    "не отдам",  # не отдам
    "Я — не отдам",  # Я — не отдам
    "то, что моё",         # то, что моё
    "твоё право выбрать",  # твоё право выбрать
]


# ---------------------------------------------------------------------------
# Encoding setup
# ---------------------------------------------------------------------------

def _configure_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_encoding()


# ---------------------------------------------------------------------------
# Git helpers (all read-only)
# ---------------------------------------------------------------------------

def _git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip()


def _git_branch() -> str:
    _, out = _git("branch", "--show-current")
    return out


def _git_head() -> str:
    _, out = _git("rev-parse", "HEAD")
    return out


def _git_origin_main() -> str:
    code, out = _git("rev-parse", "origin/main")
    return out if code == 0 else "UNKNOWN"


def _git_status_porcelain() -> list[str]:
    _, out = _git("status", "--porcelain=v1", "-uall")
    return [line for line in out.splitlines() if line.strip()]


def _is_clean(*, allow_untracked_tool: bool = False) -> bool:
    lines = _git_status_porcelain()
    if allow_untracked_tool:
        lines = [l for l in lines if "tools/rn_workflow.py" not in l]
    return len(lines) == 0


def _dirty_lines(*, allow_untracked_tool: bool = False) -> list[str]:
    lines = _git_status_porcelain()
    if allow_untracked_tool:
        lines = [l for l in lines if "tools/rn_workflow.py" not in l]
    return lines


def _is_gitignored(path: str) -> bool:
    code, _ = _git("check-ignore", "-q", path)
    return code == 0


def _origin_main_is_ancestor_of_head(head: str) -> bool:
    """Return True if origin/main is an ancestor of HEAD (feature branch check)."""
    code, _ = _git("merge-base", "--is-ancestor", "origin/main", head)
    return code == 0


# ---------------------------------------------------------------------------
# Branch / HEAD validation
# ---------------------------------------------------------------------------

def _check_branch_head(
    branch: str,
    head: str,
    origin_main: str,
    allow_feature_branch: bool,
) -> tuple[bool, str]:
    """
    Return (ok, description) for branch/HEAD relationship check.

    Rules:
    - main: HEAD must == origin/main (strict)
    - feature/*: if allow_feature_branch, origin/main must be ancestor of HEAD
    - other branches: always fail unless explicitly extended later
    """
    if branch == "main":
        ok = head == origin_main
        detail = (
            f"HEAD == origin/main ({head[:8]})"
            if ok
            else f"HEAD ({head[:8]}) != origin/main ({origin_main[:8]})"
        )
        return ok, detail

    if branch.startswith("feature/") and allow_feature_branch:
        ok = _origin_main_is_ancestor_of_head(head)
        detail = (
            "feature branch: origin/main is ancestor of HEAD (OK)"
            if ok
            else "feature branch: origin/main is NOT ancestor of HEAD (branch may be stale)"
        )
        return ok, detail

    if not allow_feature_branch and branch != "main":
        return False, (
            f"branch '{branch}' is not 'main' and --allow-feature-branch not set"
        )

    return False, f"branch '{branch}' not supported without explicit --allow-feature-branch"


# ---------------------------------------------------------------------------
# Script analysis
# ---------------------------------------------------------------------------

def _read_script() -> str | None:
    if not SCRIPT_RPY.exists():
        return None
    try:
        return SCRIPT_RPY.read_text(encoding="utf-8")
    except Exception:
        return None


def _analyze_script(text: str) -> dict[str, Any]:
    labels = re.findall(r"^label\s+([A-Za-z0-9_]+)\s*:", text, flags=re.M)
    jumps = re.findall(r"\bjump\s+([A-Za-z0-9_]+)", text)

    scene_nums = sorted(set(
        int(m.group(1))
        for m in re.finditer(r"\bjump\s+sc_(\d+)_start\b", text)
    ))

    selector_count = len(scene_nums)
    latest_scene_num = max(scene_nums) if scene_nums else None
    latest_scene = f"SC_{latest_scene_num:03d}" if latest_scene_num else None

    if scene_nums:
        playable_range = f"SC_{min(scene_nums):03d}–SC_{max(scene_nums):03d}"
    else:
        playable_range = "none"

    return {
        "label_count": len(labels),
        "jump_count": len(jumps),
        "labels": labels,
        "jumps": jumps,
        "scene_nums": scene_nums,
        "selector_count": selector_count,
        "latest_scene": latest_scene,
        "latest_scene_num": latest_scene_num,
        "playable_range": playable_range,
    }


def _latest_source_json(scene_num: int | None) -> str | None:
    if scene_num is None:
        return None
    matches = sorted(SCENARIOS_DIR.glob(f"SCENARIO_{scene_num:03d}_*.json"))
    if matches:
        return str(matches[0])
    all_matches = sorted(SCENARIOS_DIR.glob("SCENARIO_[0-9][0-9][0-9]_*.json"))
    return str(all_matches[-1]) if all_matches else None


def _extract_scene_block(text: str, scene_num: int) -> str:
    """Return all script text belonging to scene labels sc_NNN_*."""
    prefix = f"sc_{scene_num:03d}"
    start_match = re.search(
        rf"^label\s+{re.escape(prefix)}_start\s*:", text, re.M
    )
    if not start_match:
        return ""
    after_start = text[start_match.start():]
    end_pos = len(after_start)
    for m in re.finditer(r"^label\s+(\w+)\s*:", after_start, re.M):
        if m.start() == 0:
            continue
        if not m.group(1).startswith(prefix):
            end_pos = m.start()
            break
    return after_start[:end_pos]


def _scene_dialogue_counts(text: str, scene_num: int) -> dict[str, int]:
    block = _extract_scene_block(text, scene_num)
    if not block:
        return {}
    counts: dict[str, int] = {}
    for char in ("kira", "sergey", "yakov", "narrator"):
        counts[char] = len(re.findall(rf'^\s+{char}\s+"', block, re.M))
    return counts


def _parse_scene_num(scene_arg: str) -> int | None:
    """Parse scene identifier: SC_014, 014, sc_014, 14 → 14."""
    s = scene_arg.strip().upper()
    s = re.sub(r"^SC_?", "", s)
    try:
        return int(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Safety scan
# ---------------------------------------------------------------------------

def _safety_scan(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for term in FORBIDDEN_TERMS:
            if term in line:
                hits.append({
                    "term": term,
                    "line": i,
                    "preview": line.strip()[:120],
                })
    return hits


# ---------------------------------------------------------------------------
# Command: status
# ---------------------------------------------------------------------------

def cmd_status(_args: argparse.Namespace) -> int:
    print("=== RN WORKFLOW STATUS ===")

    branch = _git_branch()
    head = _git_head()
    origin_main = _git_origin_main()
    status_lines = _git_status_porcelain()
    clean = len(status_lines) == 0
    tasks_db = VOYAGE_TASKS_DB.exists()
    env_artifact = Path("./$env").exists()

    print(f"branch:            {branch}")
    print(f"HEAD:              {head}")
    print(f"origin/main:       {origin_main}")
    print(f"HEAD==origin/main: {'YES' if head == origin_main else 'NO'}")
    print(f"clean:             {'YES' if clean else 'NO'}")
    if not clean:
        for line in status_lines:
            print(f"  {line}")
    print(f".voyage/tasks.db:  {'EXISTS' if tasks_db else 'absent'}")
    print(f"literal ./$env:    {'EXISTS' if env_artifact else 'absent'}")

    script_text = _read_script()
    if script_text is None:
        print("ERROR: script.rpy not found or not readable")
        return 1

    analysis = _analyze_script(script_text)
    latest_src = _latest_source_json(analysis["latest_scene_num"])

    print()
    print(f"selector options:  {analysis['selector_count']}")
    print(f"playable range:    {analysis['playable_range']}")
    print(f"label_count:       {analysis['label_count']}")
    print(f"jump_count:        {analysis['jump_count']}")
    print(f"latest scene:      {analysis['latest_scene'] or 'none'}")
    print(f"latest source JSON:{' ' + latest_src if latest_src else ' none'}")

    return 0


# ---------------------------------------------------------------------------
# Command: safety-scan
# ---------------------------------------------------------------------------

def cmd_safety_scan(args: argparse.Namespace) -> int:
    scope: str = getattr(args, "scope", "latest")
    scene_arg: str | None = getattr(args, "scene", None)

    print("=== RN SAFETY SCAN ===")

    script_text = _read_script()
    if script_text is None:
        print("ERROR: script.rpy not found or not readable")
        return 1

    analysis = _analyze_script(script_text)

    if scope == "full":
        scan_text = script_text
        scan_label = "full script"
        print(f"scope:   full ({len(script_text)} chars)")
    elif scope == "scene":
        if scene_arg is None:
            print("ERROR: --scope scene requires --scene <SC_XXX>")
            return 1
        scene_num = _parse_scene_num(scene_arg)
        if scene_num is None:
            print(f"ERROR: cannot parse scene identifier '{scene_arg}'")
            return 1
        scan_text = _extract_scene_block(script_text, scene_num)
        if not scan_text:
            print(f"ERROR: scene block SC_{scene_num:03d} not found in script")
            return 1
        scan_label = f"SC_{scene_num:03d} block"
        print(f"scope:   scene = SC_{scene_num:03d} ({len(scan_text)} chars)")
    else:  # default: latest
        latest_num = analysis["latest_scene_num"]
        if latest_num is None:
            print("ERROR: could not detect latest scene")
            return 1
        scan_text = _extract_scene_block(script_text, latest_num)
        scan_label = f"SC_{latest_num:03d} block (latest)"
        print(f"scope:   latest = SC_{latest_num:03d} ({len(scan_text)} chars)")
        print(f"note:    use --scope full to scan entire script.rpy")

    hits = _safety_scan(scan_text)

    if not hits:
        print(f"PASS: no forbidden terms found in {scan_label}")
        return 0

    print(f"FAIL: {len(hits)} forbidden term(s) found in {scan_label}")
    for h in hits:
        line_label = f"line {h['line']}" if scope != "latest" else f"block-line {h['line']}"
        print(f"  term={h['term']!r}  {line_label}  preview={h['preview']!r}")
    return 1


# ---------------------------------------------------------------------------
# Command: validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    allow_feature = getattr(args, "allow_feature_branch", False)
    allow_untracked_tool = getattr(args, "allow_untracked_tool", False)
    full_safety = getattr(args, "full_safety_scan", False)

    print("=== RN VALIDATE ===")
    if allow_feature:
        print("mode:  --allow-feature-branch")
    if allow_untracked_tool:
        print("mode:  --allow-untracked-tool")

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"  {status}: {name}{suffix}")

    # Git repo
    code, _ = _git("rev-parse", "--git-dir")
    check("git repo", code == 0)

    # Working tree clean
    dirty = _dirty_lines(allow_untracked_tool=allow_untracked_tool)
    clean = len(dirty) == 0
    dirty_desc = f"{len(dirty)} change(s)" if dirty else ""
    if allow_untracked_tool and dirty:
        dirty_desc += " (tools/rn_workflow.py excluded)"
    check("working tree clean", clean, dirty_desc)

    # Branch / HEAD check
    branch = _git_branch()
    head = _git_head()
    origin_main = _git_origin_main()
    head_ok, head_detail = _check_branch_head(branch, head, origin_main, allow_feature)
    check("branch/HEAD valid", head_ok, head_detail)

    # Sentinel files
    check(".voyage/tasks.db absent", not VOYAGE_TASKS_DB.exists())
    check("literal ./$env absent", not Path("./$env").exists())

    # script.rpy
    check("script.rpy exists", SCRIPT_RPY.exists())

    script_text = _read_script()
    if script_text is None:
        check("script.rpy UTF-8 readable", False, "cannot read file")
        print()
        _print_validate_result(results)
        return 1

    check("script.rpy UTF-8 readable", True)

    raw = SCRIPT_RPY.read_bytes()
    bom_present = raw.startswith(b"\xef\xbb\xbf")
    check("no BOM", not bom_present, "BOM detected" if bom_present else "")

    has_crlf = b"\r\n" in raw
    check("LF-only (no CRLF)", not has_crlf, "CRLF found" if has_crlf else "")

    analysis = _analyze_script(script_text)

    check("selector count == 12",
          analysis["selector_count"] == EXPECTED_SELECTOR,
          f"got {analysis['selector_count']}")
    check("label_count == 85",
          analysis["label_count"] == EXPECTED_LABEL_COUNT,
          f"got {analysis['label_count']}")
    check("jump_count == 84",
          analysis["jump_count"] == EXPECTED_JUMP_COUNT,
          f"got {analysis['jump_count']}")
    check("latest scene == SC_014",
          analysis["latest_scene"] == EXPECTED_LATEST_SCENE,
          f"got {analysis['latest_scene']}")

    all_present = all(
        f"sc_{n:03d}_start" in analysis["labels"] for n in range(3, 15)
    )
    check("SC_003-SC_014 labels present", all_present)

    src_path = _latest_source_json(14)
    src_exists = src_path is not None and Path(src_path).exists()
    check("SC_014 source JSON exists", src_exists, src_path or "not found")

    if src_exists and src_path:
        _, tracked = _git("ls-files", src_path)
        check("SC_014 source JSON tracked by git", bool(tracked.strip()),
              "not tracked" if not tracked.strip() else "")

    counts = _scene_dialogue_counts(script_text, 14)
    check("SC_014 kira lines == 3",
          counts.get("kira", 0) == SC014_EXPECTED_KIRA,
          f"got {counts.get('kira', 0)}")
    check("SC_014 sergey lines == 3",
          counts.get("sergey", 0) == SC014_EXPECTED_SERGEY,
          f"got {counts.get('sergey', 0)}")
    check("SC_014 yakov lines == 0",
          counts.get("yakov", 0) == SC014_EXPECTED_YAKOV,
          f"got {counts.get('yakov', 0)}")

    check(f"SC_014 marker present", SC014_MARKER in script_text)

    # Safety scan — default: latest scene only.
    # SC_005/SC_006 (gym chain, intensity 7-9, committed approved content) have
    # legacy hits that are intentionally excluded from default validation.
    # Use --full-safety-scan to scan the entire script (may fail on legacy content).
    if full_safety:
        scan_text = script_text
        scan_scope_label = "full script (--full-safety-scan)"
    else:
        latest_num = analysis["latest_scene_num"] or EXPECTED_LATEST_SCENE_NUM
        scan_text = _extract_scene_block(script_text, latest_num)
        scan_scope_label = f"SC_{latest_num:03d} block (latest; use --full-safety-scan for full)"

    hits = _safety_scan(scan_text)
    check(f"safety scan PASS [{scan_scope_label}]",
          len(hits) == 0,
          f"{len(hits)} hit(s)" if hits else "")

    print()
    _print_validate_result(results)
    print("gates: NOT RUN in RN-AUTO-1 Phase 1")
    return 0 if all(ok for _, ok, _ in results) else 1


def _print_validate_result(results: list[tuple[str, bool, str]]) -> None:
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"RESULT: FAIL ({len(failed)} check(s) failed: {', '.join(failed)})")
    else:
        print(f"RESULT: PASS ({len(results)} checks)")


# ---------------------------------------------------------------------------
# Command: baseline-report
# ---------------------------------------------------------------------------

def cmd_baseline_report(args: argparse.Namespace) -> int:
    allow_feature = getattr(args, "allow_feature_branch", False)
    allow_untracked_tool = getattr(args, "allow_untracked_tool", False)

    print("=== RN BASELINE REPORT ===")
    if allow_feature:
        print("mode:  --allow-feature-branch")
    if allow_untracked_tool:
        print("mode:  --allow-untracked-tool")

    # Verify gitignore before any writes
    if not _is_gitignored("reports/renpy/") and not _is_gitignored("reports/renpy/test.json"):
        print("STOP: reports/renpy is not gitignored")
        return 1

    branch = _git_branch()
    head = _git_head()
    origin_main = _git_origin_main()
    dirty = _dirty_lines(allow_untracked_tool=allow_untracked_tool)
    clean = len(dirty) == 0

    script_text = _read_script()
    if script_text is None:
        print("STOP: script.rpy not found or not readable")
        return 1

    raw = SCRIPT_RPY.read_bytes()
    analysis = _analyze_script(script_text)
    latest_src = _latest_source_json(analysis["latest_scene_num"])

    latest_num = analysis["latest_scene_num"] or EXPECTED_LATEST_SCENE_NUM
    latest_block = _extract_scene_block(script_text, latest_num)
    hits = _safety_scan(latest_block)
    counts_014 = _scene_dialogue_counts(script_text, 14)

    src_path = _latest_source_json(14)
    src_exists = src_path is not None and Path(src_path or "").exists()
    if src_exists and src_path:
        _, tracked = _git("ls-files", src_path)
        src_tracked = bool(tracked.strip())
    else:
        src_tracked = False

    head_ok, head_detail = _check_branch_head(branch, head, origin_main, allow_feature)

    checks: dict[str, Any] = {
        "git_repo": True,
        "working_tree_clean": clean,
        "branch_head_valid": head_ok,
        "branch_head_detail": head_detail,
        "tasks_db_absent": not VOYAGE_TASKS_DB.exists(),
        "env_artifact_absent": not Path("./$env").exists(),
        "script_exists": SCRIPT_RPY.exists(),
        "no_bom": not raw.startswith(b"\xef\xbb\xbf"),
        "lf_only": b"\r\n" not in raw,
        "selector_count": analysis["selector_count"],
        "selector_correct": analysis["selector_count"] == EXPECTED_SELECTOR,
        "label_count": analysis["label_count"],
        "label_count_correct": analysis["label_count"] == EXPECTED_LABEL_COUNT,
        "jump_count": analysis["jump_count"],
        "jump_count_correct": analysis["jump_count"] == EXPECTED_JUMP_COUNT,
        "latest_scene": analysis["latest_scene"],
        "latest_scene_correct": analysis["latest_scene"] == EXPECTED_LATEST_SCENE,
        "sc003_sc014_labels_present": all(
            f"sc_{n:03d}_start" in analysis["labels"] for n in range(3, 15)
        ),
        "sc014_source_exists": src_exists,
        "sc014_source_tracked": src_tracked,
        "sc014_kira_lines": counts_014.get("kira", 0),
        "sc014_sergey_lines": counts_014.get("sergey", 0),
        "sc014_yakov_lines": counts_014.get("yakov", 0),
        "sc014_kira_correct": counts_014.get("kira", 0) == SC014_EXPECTED_KIRA,
        "sc014_sergey_correct": counts_014.get("sergey", 0) == SC014_EXPECTED_SERGEY,
        "sc014_yakov_correct": counts_014.get("yakov", 0) == SC014_EXPECTED_YAKOV,
        "sc014_marker_present": SC014_MARKER in script_text,
        "safety_scope": f"SC_{latest_num:03d} block (latest)",
        "safety_scan_pass": len(hits) == 0,
        "safety_scan_hit_count": len(hits),
    }

    non_bool_keys = {
        "selector_count", "label_count", "jump_count", "latest_scene",
        "sc014_kira_lines", "sc014_sergey_lines", "sc014_yakov_lines",
        "safety_scan_hit_count", "branch_head_detail", "safety_scope",
    }
    bool_checks = [
        v for k, v in checks.items()
        if isinstance(v, bool) and k not in non_bool_keys
    ]
    overall = "PASS" if all(bool_checks) else "FAIL"

    timestamp = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "tool": "rn_workflow",
        "version": "0.1.0",
        "phase": "Phase 1",
        "timestamp": timestamp,
        "branch": branch,
        "HEAD": head,
        "origin_main": origin_main,
        "branch_head_valid": head_ok,
        "branch_head_detail": head_detail,
        "allow_feature_branch": allow_feature,
        "allow_untracked_tool": allow_untracked_tool,
        "working_tree_clean": clean,
        "working_tree_status": dirty,
        "selector_count": analysis["selector_count"],
        "playable_range": analysis["playable_range"],
        "label_count": analysis["label_count"],
        "jump_count": analysis["jump_count"],
        "latest_scene": analysis["latest_scene"],
        "latest_source_json": latest_src,
        "checks": checks,
        "safety_scan": {
            "scope": f"SC_{latest_num:03d} block (latest)",
            "pass": len(hits) == 0,
            "hit_count": len(hits),
            "hits": hits,
        },
        "gates": "NOT RUN in RN-AUTO-1 Phase 1",
        "overall": overall,
    }

    head_short = head[:8] if head else "unknown"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORTS_DIR / f"rn_baseline_report_{head_short}.json"
    txt_path = REPORTS_DIR / f"rn_baseline_report_{head_short}.txt"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    txt_lines = [
        "=== RN BASELINE REPORT ===",
        f"timestamp:    {timestamp}",
        f"branch:       {branch}",
        f"HEAD:         {head}",
        f"origin/main:  {origin_main}",
        f"branch/HEAD:  {'PASS' if head_ok else 'FAIL'} ({head_detail})",
        f"clean:        {'YES' if clean else 'NO'}",
        f"selector:     {analysis['selector_count']}",
        f"range:        {analysis['playable_range']}",
        f"label_count:  {analysis['label_count']}",
        f"jump_count:   {analysis['jump_count']}",
        f"latest scene: {analysis['latest_scene']}",
        f"latest src:   {latest_src}",
        f"safety scope: SC_{latest_num:03d} block (latest)",
        f"safety scan:  {'PASS' if len(hits) == 0 else f'FAIL ({len(hits)} hits)'}",
        "gates:        NOT RUN in RN-AUTO-1 Phase 1",
        f"OVERALL:      {overall}",
    ]

    txt_path.write_text(
        "\n".join(txt_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # Verify reports are NOT showing up in git status
    status_after = _git_status_porcelain()
    report_leaked = [
        line for line in status_after
        if "reports/renpy" in line or "rn_baseline_report" in line
    ]
    if report_leaked:
        print("STOP: report files leaked into git status -- not properly gitignored")
        for line in report_leaked:
            print(f"  {line}")
        json_path.unlink(missing_ok=True)
        txt_path.unlink(missing_ok=True)
        return 1

    for line in txt_lines:
        print(line)
    print()
    print(f"report written: {json_path}")
    print(f"report written: {txt_path}")

    return 0 if overall == "PASS" else 1


# ---------------------------------------------------------------------------
# Main / argument parser
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rn_workflow",
        description="RN Workflow -- read-only RenPy/VNE workflow checker (Phase 1)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show current playable baseline status")

    p_scan = sub.add_parser("safety-scan", help="Scan script.rpy for forbidden terms")
    p_scan.add_argument(
        "--scope",
        choices=["latest", "full", "scene"],
        default="latest",
        help="Scan scope: latest=latest scene block (default), full=entire script, scene=specific scene",
    )
    p_scan.add_argument(
        "--scene",
        default=None,
        help="Scene identifier for --scope scene (e.g. SC_014, 014, sc_014)",
    )

    p_val = sub.add_parser("validate", help="Run all validation checks")
    p_val.add_argument(
        "--allow-feature-branch",
        action="store_true",
        default=False,
        help="Allow validation on feature/* branches (checks origin/main is ancestor)",
    )
    p_val.add_argument(
        "--allow-untracked-tool",
        action="store_true",
        default=False,
        help="Exclude tools/rn_workflow.py from dirty-tree check (for pre-commit testing)",
    )
    p_val.add_argument(
        "--full-safety-scan",
        action="store_true",
        default=False,
        help="Scan entire script.rpy for forbidden terms (may fail on legacy gym content)",
    )

    p_rep = sub.add_parser("baseline-report", help="Run validate and write baseline report")
    p_rep.add_argument(
        "--allow-feature-branch",
        action="store_true",
        default=False,
        help="Allow report on feature/* branches (checks origin/main is ancestor)",
    )
    p_rep.add_argument(
        "--allow-untracked-tool",
        action="store_true",
        default=False,
        help="Exclude tools/rn_workflow.py from dirty-tree check (for pre-commit testing)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "status": cmd_status,
        "safety-scan": cmd_safety_scan,
        "validate": cmd_validate,
        "baseline-report": cmd_baseline_report,
    }

    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
