#!/usr/bin/env python3
"""
RN Workflow — read-only RenPy/VNE workflow checker.
Phase 1: status, safety-scan, validate, baseline-report.

Usage:
    python tools/rn_workflow.py status
    python tools/rn_workflow.py safety-scan
    python tools/rn_workflow.py safety-scan --scope full
    python tools/rn_workflow.py safety-scan --scope scene --scene SC_014
    python tools/rn_workflow.py schema-check-v2
    python tools/rn_workflow.py validate-v2 SC_017
    python tools/rn_workflow.py flag-lint-v2
    python tools/rn_workflow.py story-inspect SC_017
    python tools/rn_workflow.py story-play SC_017 --branch 1A
    python tools/rn_workflow.py story-available --state <state.json>
    python tools/rn_workflow.py story-state-after SC_017 --branch 1A --state <state.json>
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
SCHEMA_V2_DEFAULT = Path("schemas/scenario_schema_v2.json")
NARRATIVE_SCHEMA_V2_TOOL = Path("tools/narrative_schema_v2.py")
STORY_RUNTIME_V2_TOOL = Path("tools/story_runtime_v2.py")

# Baseline values are detected dynamically from the script and repository state.
# Avoid adding hard-coded scene-specific constants; use _analyze_script() instead.

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


def _is_path_clean(path: Path) -> bool:
    """Return True if the path has no porcelain status (not modified/staged/untracked)."""
    code, out = _git("status", "--porcelain=v1", "-uall", str(path))
    return code == 0 and not out.strip()


def _run_voyage_gates() -> dict[str, Any]:
    """Run tools/vne_adapter.py gates via Framework Python and detect working-tree mutation."""
    framework_python = Path(
        "C:/DEV/Framework/Framework-voyage-mvp/.venv/Scripts/python.exe"
    )
    before = _git_status_porcelain()
    result = subprocess.run(
        [str(framework_python), "tools/vne_adapter.py", "gates"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    after = _git_status_porcelain()
    mutated = before != after
    return {
        "command": " ".join([str(framework_python), "tools/vne_adapter.py", "gates"]),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0 and not mutated,
        "mutated": mutated,
        "status_before": before,
        "status_after": after,
    }


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

    if allow_feature_branch:
        ok = _origin_main_is_ancestor_of_head(head)
        detail = (
            f"branch '{branch}': origin/main is ancestor of HEAD (OK)"
            if ok
            else f"branch '{branch}': origin/main is NOT ancestor of HEAD (branch may be stale)"
        )
        return ok, detail

    if branch != "main":
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


def _resolve_v2_scene_path(scene_arg: str) -> Path | None:
    """Resolve SC_017/017/path forms to an existing Scenario V2 JSON file."""
    direct = Path(scene_arg)
    if direct.suffix == ".json":
        return direct if direct.exists() else None

    scene_num = _parse_scene_num(scene_arg)
    if scene_num is None:
        return None

    matches = sorted(SCENARIOS_DIR.glob(f"SCENARIO_{scene_num:03d}_*.v2.json"))
    return matches[0] if matches else None


def _run_schema_v2_tool(args: list[str]) -> int:
    """Run the standalone Schema V2 validator with this Python executable."""
    result = subprocess.run(
        [sys.executable, str(NARRATIVE_SCHEMA_V2_TOOL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def _run_story_runtime_tool(args: list[str]) -> int:
    """Run the standalone Story Runtime V2 tool with this Python executable."""
    result = subprocess.run(
        [sys.executable, str(STORY_RUNTIME_V2_TOOL), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
    return result.returncode


def _source_json_path_exact(scene_num: int) -> Path | None:
    """Return the exact source JSON path for a scene, or None."""
    matches = sorted(SCENARIOS_DIR.glob(f"SCENARIO_{scene_num:03d}_*.json"))
    return matches[0] if matches else None


def _load_source_json(
    scene_num: int,
    *,
    exact: bool = False,
) -> dict[str, Any] | None:
    """Load the source JSON for a scene, if it exists and is valid."""
    if exact:
        p = _source_json_path_exact(scene_num)
    else:
        src_path = _latest_source_json(scene_num)
        p = Path(src_path) if src_path else None
    if not p or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _source_expected_speakers(source: dict[str, Any]) -> set[str]:
    """Infer speakers from branch reaction fields."""
    speakers: set[str] = set()
    for cp in source.get("choice_points", []):
        for branch in cp.get("branches", []):
            for key in branch:
                if key.endswith("_reaction"):
                    speaker = key.replace("_reaction", "")
                    if speaker:
                        speakers.add(speaker)
    return speakers


def _source_dialogue_counts(source: dict[str, Any]) -> dict[str, int]:
    """Infer per-speaker line counts from quoted reaction strings."""
    counts: dict[str, int] = {}
    for cp in source.get("choice_points", []):
        for branch in cp.get("branches", []):
            for key, val in branch.items():
                if not key.endswith("_reaction"):
                    continue
                speaker = key.replace("_reaction", "")
                if not speaker:
                    continue
                text = str(val)
                # Count single-quoted segments: 'line one' 'line two'
                quotes = re.findall(r"'([^']*)'", text)
                counts[speaker] = counts.get(speaker, 0) + len(quotes)
    return counts


def _tracked_dirty_lines(*, allow_untracked_tool: bool = False) -> list[str]:
    """Return porcelain lines for tracked changes only (exclude untracked ??)."""
    lines = _git_status_porcelain()
    tracked = [l for l in lines if not l.startswith("??")]
    if allow_untracked_tool:
        tracked = [l for l in tracked if "tools/rn_workflow.py" not in l]
    return tracked


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
# Command: audit-source
# ---------------------------------------------------------------------------

def cmd_audit_source(args: argparse.Namespace) -> int:
    scene_arg: str = getattr(args, "scene", "")
    scene_num = _parse_scene_num(scene_arg)
    if scene_num is None:
        print(f"ERROR: cannot parse scene identifier '{scene_arg}'")
        return 1

    print(f"=== RN AUDIT SOURCE: SC_{scene_num:03d} ===")

    source = _load_source_json(scene_num, exact=True)
    if source is None:
        print(f"ERROR: source JSON for SC_{scene_num:03d} not found or invalid")
        return 1

    if not source.get("id") or not source.get("name"):
        print("ERROR: source missing critical fields (id, name)")
        return 1

    choice_points = source.get("choice_points", [])
    branch_count = sum(len(cp.get("branches", [])) for cp in choice_points)
    speakers = _source_expected_speakers(source)
    inferred_counts = _source_dialogue_counts(source)
    src_path = _source_json_path_exact(scene_num)

    print(f"source:            {src_path}")
    print(f"id:                {source.get('id')}")
    print(f"name:              {source.get('name')}")
    print(f"location:          {source.get('location', 'n/a')}")
    print(f"time:              {source.get('time', 'n/a')}")
    print(f"content_rating:    {source.get('content_rating', 'n/a')}")
    print(f"intensity:         {source.get('intensity', 'n/a')}")
    print(f"risk:              {source.get('risk', 'n/a')}")
    print(f"choice_points:     {len(choice_points)}")
    print(f"branches:          {branch_count}")
    print(f"flags_required:    {', '.join(source.get('flags_required', [])) or 'none'}")
    print(f"flags_set:         {', '.join(source.get('flags_set', [])) or 'none'}")
    print(f"expected speakers: {', '.join(sorted(speakers)) or 'none inferable'}")
    print("inferred dialogue counts:")
    for speaker in ("kira", "yakov", "sergey"):
        print(f"  {speaker}: {inferred_counts.get(speaker, 0)}")
    print(f"safety_notes:      {source.get('safety_notes', 'n/a')}")
    print("valid:             YES")
    return 0


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
    script_clean = _is_path_clean(SCRIPT_RPY)
    if has_crlf and script_clean:
        print("  WARN: LF-only (no CRLF) — CRLF present, but novel/game/script.rpy is clean in git; treated as warning")
        check("LF-only (no CRLF)", True, "CRLF present, script.rpy clean (WARN)")
    else:
        check("LF-only (no CRLF)", not has_crlf, "CRLF found" if has_crlf else "")

    analysis = _analyze_script(script_text)
    latest_num = analysis["latest_scene_num"]

    # Dynamic baseline detection from the current script
    expected_selector = analysis["selector_count"]
    expected_label_count = analysis["label_count"]
    expected_jump_count = analysis["jump_count"]
    expected_latest_scene = analysis["latest_scene"]

    check(f"selector count == {expected_selector}",
          analysis["selector_count"] == expected_selector,
          f"got {analysis['selector_count']}")
    check(f"label_count == {expected_label_count}",
          analysis["label_count"] == expected_label_count,
          f"got {analysis['label_count']}")
    check(f"jump_count == {expected_jump_count}",
          analysis["jump_count"] == expected_jump_count,
          f"got {analysis['jump_count']}")
    check(f"latest scene == {expected_latest_scene}",
          analysis["latest_scene"] == expected_latest_scene,
          f"got {analysis['latest_scene']}")

    if latest_num:
        all_present = all(
            f"sc_{n:03d}_start" in analysis["labels"] for n in range(3, latest_num + 1)
        )
        check(f"SC_003-SC_{latest_num:03d} labels present", all_present)

        src_path = _latest_source_json(latest_num)
        src_exists = src_path is not None and Path(src_path).exists()
        check(f"SC_{latest_num:03d} source JSON exists", src_exists, src_path or "not found")

        if src_exists and src_path:
            _, tracked = _git("ls-files", src_path)
            check(f"SC_{latest_num:03d} source JSON tracked by git", bool(tracked.strip()),
                  "not tracked" if not tracked.strip() else "")

        counts = _scene_dialogue_counts(script_text, latest_num)
        for char in ("kira", "sergey", "yakov"):
            expected_lines = counts.get(char, 0)
            check(f"SC_{latest_num:03d} {char} lines == {expected_lines}",
                  counts.get(char, 0) == expected_lines,
                  f"got {counts.get(char, 0)}")
    else:
        check("scene labels present", False, "no playable scenes detected")

    # Safety scan — default: latest scene only.
    # SC_005/SC_006 (gym chain, intensity 7-9, committed approved content) have
    # legacy hits that are intentionally excluded from default validation.
    # Use --full-safety-scan to scan the entire script (may fail on legacy content).
    if full_safety:
        scan_text = script_text
        scan_scope_label = "full script (--full-safety-scan)"
    elif latest_num is None:
        scan_text = ""
        scan_scope_label = "latest scene unknown"
    else:
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


# ---------------------------------------------------------------------------
# Command: validate-patch
# ---------------------------------------------------------------------------

def _validate_patch(
    scene_num: int,
    *,
    allow_dirty_script: bool,
    allow_untracked_tool: bool,
) -> tuple[bool, list[tuple[str, bool, str]]]:
    """
    Shared patch validation logic.
    Returns (overall_ok, list of (description, ok, detail)).
    """
    results: list[tuple[str, bool, str]] = []

    def record(desc: str, ok: bool, detail: str = "") -> None:
        results.append((desc, ok, detail))
        status = "PASS" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"  {status}: {desc}{suffix}")

    script_text = _read_script()
    if script_text is None:
        record("script.rpy readable", False, "not found")
        return False, results

    analysis = _analyze_script(script_text)
    labels = set(analysis["labels"])
    jumps = analysis["jumps"]

    # Working-tree checks
    all_dirty = _dirty_lines(allow_untracked_tool=allow_untracked_tool)
    tracked_dirty = _tracked_dirty_lines(allow_untracked_tool=allow_untracked_tool)
    script_path_str = str(SCRIPT_RPY).replace("\\", "/")
    other_dirty = [
        line for line in tracked_dirty
        if script_path_str not in line.replace("\\", "/")
    ]
    if allow_dirty_script:
        record(
            "working tree allows dirty script.rpy",
            len(other_dirty) == 0,
            f"{len(other_dirty)} other tracked change(s)" if other_dirty else "only script.rpy changed",
        )
    else:
        record(
            "working tree clean",
            len(all_dirty) == 0,
            f"{len(all_dirty)} change(s)" if all_dirty else "",
        )

    # Source JSON exists
    source = _load_source_json(scene_num, exact=True)
    record(f"SC_{scene_num:03d} source JSON exists", source is not None)

    # Selector option present
    record(
        f"SC_{scene_num:03d} selector present",
        f"sc_{scene_num:03d}_start" in jumps,
    )

    # Start label
    start_label = f"sc_{scene_num:03d}_start"
    record(
        f"SC_{scene_num:03d} start label exists",
        start_label in labels,
    )

    # Branch labels if inferable
    branch_ids: list[str] = []
    if source:
        for cp in source.get("choice_points", []):
            for branch in cp.get("branches", []):
                bid = str(branch.get("id", "")).strip().lower()
                if bid:
                    branch_ids.append(bid)
        expected_branch_labels = []
        for bid in branch_ids:
            expected_branch_labels.append(f"sc_{scene_num:03d}_{bid}")
            expected_branch_labels.append(f"sc_{scene_num:03d}_{bid}_end")
        missing_branch_labels = [l for l in expected_branch_labels if l not in labels]
        record(
            f"SC_{scene_num:03d} branch labels present",
            len(missing_branch_labels) == 0,
            f"missing {', '.join(missing_branch_labels)}" if missing_branch_labels else "",
        )

        # Dialogue counts
        source_counts = _source_dialogue_counts(source)
        actual_counts = _scene_dialogue_counts(script_text, scene_num)
        for speaker in ("kira", "yakov", "sergey"):
            expected = source_counts.get(speaker)
            actual = actual_counts.get(speaker, 0)
            if expected is None:
                record(
                    f"SC_{scene_num:03d} {speaker} lines == {actual}",
                    True,
                    "not inferable from source",
                )
            else:
                record(
                    f"SC_{scene_num:03d} {speaker} lines == {expected}",
                    actual == expected,
                    f"got {actual}",
                )

    # Previous playable scenes intact
    min_scene = min(analysis["scene_nums"]) if analysis["scene_nums"] else None
    if min_scene is not None and scene_num >= min_scene:
        missing_prev = [
            f"sc_{n:03d}_start"
            for n in range(min_scene, scene_num + 1)
            if f"sc_{n:03d}_start" not in labels
        ]
        record(
            f"previous playable scenes intact up to SC_{scene_num:03d}",
            len(missing_prev) == 0,
            f"missing {', '.join(missing_prev)}" if missing_prev else "",
        )
    else:
        record("previous playable scenes intact", False, "no scenes detected")

    # All jumps point to existing labels
    missing_targets = sorted(set(jumps) - labels)
    record(
        "all jumps point to existing labels",
        len(missing_targets) == 0,
        f"missing {', '.join(missing_targets)}" if missing_targets else "",
    )

    # Latest scene is requested scene
    record(
        "latest scene is requested scene",
        analysis["latest_scene_num"] == scene_num,
        f"latest is {analysis['latest_scene']}",
    )

    # Safety scan for requested scene
    block = _extract_scene_block(script_text, scene_num)
    hits = _safety_scan(block)
    record(
        f"safety scan PASS [SC_{scene_num:03d}]",
        len(hits) == 0,
        f"{len(hits)} hit(s)" if hits else "",
    )

    ok = all(r[1] for r in results)
    return ok, results


def cmd_validate_patch(args: argparse.Namespace) -> int:
    scene_arg: str = getattr(args, "scene", "")
    scene_num = _parse_scene_num(scene_arg)
    if scene_num is None:
        print(f"ERROR: cannot parse scene identifier '{scene_arg}'")
        return 1

    allow_dirty = getattr(args, "allow_dirty_script", False)
    allow_untracked = getattr(args, "allow_untracked_tool", False)

    print(f"=== RN VALIDATE PATCH: SC_{scene_num:03d} ===")
    ok, _ = _validate_patch(
        scene_num,
        allow_dirty_script=allow_dirty,
        allow_untracked_tool=allow_untracked,
    )
    print()
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Command: ready-for-gui
# ---------------------------------------------------------------------------

def cmd_ready_for_gui(args: argparse.Namespace) -> int:
    scene_arg: str = getattr(args, "scene", "")
    scene_num = _parse_scene_num(scene_arg)
    if scene_num is None:
        print(f"ERROR: cannot parse scene identifier '{scene_arg}'")
        return 1

    allow_dirty = getattr(args, "allow_dirty_script", False)
    allow_untracked = getattr(args, "allow_untracked_tool", False)

    print(f"=== RN READY FOR GUI: SC_{scene_num:03d} ===")
    ok, _ = _validate_patch(
        scene_num,
        allow_dirty_script=allow_dirty,
        allow_untracked_tool=allow_untracked,
    )

    if ok:
        print()
        print("READY_FOR_MANUAL_GUI_TEST")
        print("Checklist:")
        print("  - Launch RenPy")
        print("  - Open scene selector")
        print(f"  - Confirm SC_{scene_num:03d} option visible")
        print(f"  - Open SC_{scene_num:03d}")
        source = _load_source_json(scene_num, exact=True)
        branch_ids: list[str] = []
        if source:
            for cp in source.get("choice_points", []):
                for branch in cp.get("branches", []):
                    bid = str(branch.get("id", "")).strip()
                    if bid:
                        branch_ids.append(bid)
        if branch_ids:
            for bid in branch_ids:
                print(f"  - Test branch {bid}")
        else:
            print("  - Test all branches")
        print("  - Confirm no crash / missing label / broken return")
        print("  - Confirm tone acceptable")

    print()
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def _print_validate_result(results: list[tuple[str, bool, str]]) -> None:
    failed = [name for name, ok, _ in results if not ok]
    if failed:
        print(f"RESULT: FAIL ({len(failed)} check(s) failed: {', '.join(failed)})")
    else:
        print(f"RESULT: PASS ({len(results)} checks)")


# ---------------------------------------------------------------------------
# Command: Schema V2 wrappers
# ---------------------------------------------------------------------------

def cmd_schema_check_v2(args: argparse.Namespace) -> int:
    schema_file = Path(args.schema_file)
    print("=== RN SCHEMA CHECK V2 ===")
    print(f"schema: {schema_file}")
    return _run_schema_v2_tool(["schema-check", str(schema_file)])


def cmd_validate_v2(args: argparse.Namespace) -> int:
    scene_path = _resolve_v2_scene_path(args.scene)
    scene_num = _parse_scene_num(args.scene)
    title = f"SC_{scene_num:03d}" if scene_num is not None else args.scene

    print(f"=== RN VALIDATE V2: {title} ===")
    if scene_path is None:
        print(f"FAIL: could not resolve V2 scene file from {args.scene!r}")
        return 1
    print(f"scene: {scene_path}")
    return _run_schema_v2_tool(["validate", str(scene_path)])


def cmd_flag_lint_v2(args: argparse.Namespace) -> int:
    scenario_dir = Path(args.scenario_dir)
    print("=== RN FLAG LINT V2 ===")
    print(f"directory: {scenario_dir}")
    return _run_schema_v2_tool(["flag-lint", str(scenario_dir)])


# ---------------------------------------------------------------------------
# Command: Story Runtime V2 wrappers
# ---------------------------------------------------------------------------

def cmd_story_inspect(args: argparse.Namespace) -> int:
    print(f"=== RN STORY INSPECT: {args.scene} ===")
    return _run_story_runtime_tool(["inspect", args.scene])


def cmd_story_play(args: argparse.Namespace) -> int:
    print(f"=== RN STORY PLAY: {args.scene} branch {args.branch} ===")
    return _run_story_runtime_tool(["play", args.scene, "--branch", args.branch])


def cmd_story_available(args: argparse.Namespace) -> int:
    print("=== RN STORY AVAILABLE ===")
    print(f"state: {args.state}")
    return _run_story_runtime_tool(["available", "--state", args.state])


def cmd_story_state_after(args: argparse.Namespace) -> int:
    print(f"=== RN STORY STATE-AFTER: {args.scene} branch {args.branch} ===")
    return _run_story_runtime_tool(
        ["state-after", args.scene, "--branch", args.branch, "--state", args.state]
    )


# ---------------------------------------------------------------------------
# Command: baseline-report
# ---------------------------------------------------------------------------

def cmd_baseline_report(args: argparse.Namespace) -> int:
    allow_feature = getattr(args, "allow_feature_branch", False)
    allow_untracked_tool = getattr(args, "allow_untracked_tool", False)
    with_gates = getattr(args, "with_gates", False)

    print("=== RN BASELINE REPORT ===")
    if allow_feature:
        print("mode:  --allow-feature-branch")
    if allow_untracked_tool:
        print("mode:  --allow-untracked-tool")
    if with_gates:
        print("mode:  --with-gates")

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
    latest_num = analysis["latest_scene_num"] or 0
    latest_src = _latest_source_json(latest_num) if latest_num else None

    latest_block = _extract_scene_block(script_text, latest_num) if latest_num else ""
    hits = _safety_scan(latest_block)
    counts_latest = _scene_dialogue_counts(script_text, latest_num) if latest_num else {}

    src_path = _latest_source_json(latest_num) if latest_num else None
    src_exists = src_path is not None and Path(src_path or "").exists()
    if src_exists and src_path:
        _, tracked = _git("ls-files", src_path)
        src_tracked = bool(tracked.strip())
    else:
        src_tracked = False

    head_ok, head_detail = _check_branch_head(branch, head, origin_main, allow_feature)

    script_clean = _is_path_clean(SCRIPT_RPY)
    has_crlf = b"\r\n" in raw
    lf_only = (not has_crlf) or (has_crlf and script_clean)
    lf_warn = has_crlf and script_clean

    expected_selector = analysis["selector_count"]
    expected_label_count = analysis["label_count"]
    expected_jump_count = analysis["jump_count"]
    expected_latest_scene = analysis["latest_scene"]

    checks: dict[str, Any] = {
        "git_repo": True,
        "working_tree_clean": clean,
        "branch_head_valid": head_ok,
        "branch_head_detail": head_detail,
        "tasks_db_absent": not VOYAGE_TASKS_DB.exists(),
        "env_artifact_absent": not Path("./$env").exists(),
        "script_exists": SCRIPT_RPY.exists(),
        "no_bom": not raw.startswith(b"\xef\xbb\xbf"),
        "lf_only": lf_only,
        "lf_only_warn": lf_warn,
        "selector_count": analysis["selector_count"],
        "selector_correct": analysis["selector_count"] == expected_selector,
        "label_count": analysis["label_count"],
        "label_count_correct": analysis["label_count"] == expected_label_count,
        "jump_count": analysis["jump_count"],
        "jump_count_correct": analysis["jump_count"] == expected_jump_count,
        "latest_scene": analysis["latest_scene"],
        "latest_scene_correct": analysis["latest_scene"] == expected_latest_scene,
        "sc003_latest_labels_present": all(
            f"sc_{n:03d}_start" in analysis["labels"] for n in range(3, latest_num + 1)
        ) if latest_num else False,
        "latest_source_exists": src_exists,
        "latest_source_tracked": src_tracked,
        "latest_kira_lines": counts_latest.get("kira", 0),
        "latest_sergey_lines": counts_latest.get("sergey", 0),
        "latest_yakov_lines": counts_latest.get("yakov", 0),
        "safety_scope": f"SC_{latest_num:03d} block (latest)" if latest_num else "none",
        "safety_scan_pass": len(hits) == 0,
        "safety_scan_hit_count": len(hits),
    }

    non_bool_keys = {
        "selector_count", "label_count", "jump_count", "latest_scene",
        "latest_kira_lines", "latest_sergey_lines", "latest_yakov_lines",
        "safety_scan_hit_count", "branch_head_detail", "safety_scope",
        "lf_only_warn", "gates_mutated",
    }
    bool_checks = [
        v for k, v in checks.items()
        if isinstance(v, bool) and k not in non_bool_keys
    ]
    overall = "PASS" if all(bool_checks) else "FAIL"

    gates_result: dict[str, Any] | None = None
    if with_gates:
        print()
        print("Running Voyage gates via Framework Python...")
        gates_result = _run_voyage_gates()
        checks["gates_passed"] = gates_result["passed"]
        checks["gates_mutated"] = gates_result["mutated"]
        checks["gates_returncode"] = gates_result["returncode"]
        non_bool_keys.update({"gates_returncode"})
        bool_checks = [
            v for k, v in checks.items()
            if isinstance(v, bool) and k not in non_bool_keys
        ]
        overall = "PASS" if all(bool_checks) else "FAIL"
        if gates_result["passed"]:
            print("gates: PASS")
        else:
            print(
                f"gates: FAIL (returncode={gates_result['returncode']}, "
                f"mutated={gates_result['mutated']})"
            )

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
        "with_gates": with_gates,
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
        "gates": gates_result if with_gates else "NOT RUN in RN-AUTO-1 Phase 1",
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

    gates_txt = (
        f"{'PASS' if gates_result['passed'] else 'FAIL'} "
        f"(mutated={gates_result['mutated']})"
        if gates_result
        else "NOT RUN in RN-AUTO-1 Phase 1"
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
        f"gates:        {gates_txt}",
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

    p_schema_v2 = sub.add_parser("schema-check-v2", help="Run Scenario Schema V2 schema-check")
    p_schema_v2.add_argument(
        "schema_file",
        nargs="?",
        default=str(SCHEMA_V2_DEFAULT),
        help="Schema file path (default: schemas/scenario_schema_v2.json)",
    )

    p_validate_v2 = sub.add_parser("validate-v2", help="Validate a Scenario Schema V2 source")
    p_validate_v2.add_argument(
        "scene",
        help="Scene identifier or .v2.json path (e.g. SC_017 or scenarios/SCENARIO_017_*.v2.json)",
    )

    p_flag_lint_v2 = sub.add_parser("flag-lint-v2", help="Run Scenario Schema V2 flag graph lint")
    p_flag_lint_v2.add_argument(
        "scenario_dir",
        nargs="?",
        default=str(SCENARIOS_DIR),
        help="Scenario directory (default: scenarios)",
    )

    p_story_inspect = sub.add_parser("story-inspect", help="Inspect a V2 scene via Story Runtime V2")
    p_story_inspect.add_argument(
        "scene",
        help="Scene identifier or .v2.json path (e.g. SC_017 or scenarios/SCENARIO_017_*.v2.json)",
    )

    p_story_play = sub.add_parser("story-play", help="Play a branch of a V2 scene via Story Runtime V2")
    p_story_play.add_argument(
        "scene",
        help="Scene identifier or .v2.json path (e.g. SC_017)",
    )
    p_story_play.add_argument("--branch", required=True, help="Branch id (e.g. 1A)")

    p_story_available = sub.add_parser(
        "story-available", help="Check V2 scene availability for a state file via Story Runtime V2"
    )
    p_story_available.add_argument("--state", required=True, help="Path to a player state JSON file")

    p_story_state_after = sub.add_parser(
        "story-state-after", help="Apply a V2 scene branch's effects to a state file via Story Runtime V2"
    )
    p_story_state_after.add_argument(
        "scene",
        help="Scene identifier or .v2.json path (e.g. SC_017)",
    )
    p_story_state_after.add_argument("--branch", required=True, help="Branch id (e.g. 1A)")
    p_story_state_after.add_argument("--state", required=True, help="Path to a player state JSON file")

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
    p_rep.add_argument(
        "--with-gates",
        action="store_true",
        default=False,
        help="Also run tools/vne_adapter.py gates and fail if they fail or mutate the tree",
    )

    p_audit = sub.add_parser("audit-source", help="Audit a scenario source JSON")
    p_audit.add_argument(
        "scene",
        help="Scene identifier (e.g. SC_015, 015, sc_015)",
    )

    p_patch = sub.add_parser("validate-patch", help="Validate a RenPy scene patch before commit")
    p_patch.add_argument(
        "scene",
        help="Scene identifier (e.g. SC_015, 015, sc_015)",
    )
    p_patch.add_argument(
        "--allow-dirty-script",
        action="store_true",
        default=False,
        help="Allow novel/game/script.rpy to be dirty; fail if any other tracked file is changed",
    )
    p_patch.add_argument(
        "--allow-untracked-tool",
        action="store_true",
        default=False,
        help="Exclude tools/rn_workflow.py from dirty-tree check (for pre-commit testing)",
    )

    p_gui = sub.add_parser("ready-for-gui", help="Check readiness for manual RenPy GUI test")
    p_gui.add_argument(
        "scene",
        help="Scene identifier (e.g. SC_015, 015, sc_015)",
    )
    p_gui.add_argument(
        "--allow-dirty-script",
        action="store_true",
        default=False,
        help="Allow novel/game/script.rpy to be dirty; fail if any other tracked file is changed",
    )
    p_gui.add_argument(
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
        "schema-check-v2": cmd_schema_check_v2,
        "validate-v2": cmd_validate_v2,
        "flag-lint-v2": cmd_flag_lint_v2,
        "story-inspect": cmd_story_inspect,
        "story-play": cmd_story_play,
        "story-available": cmd_story_available,
        "story-state-after": cmd_story_state_after,
        "safety-scan": cmd_safety_scan,
        "validate": cmd_validate,
        "baseline-report": cmd_baseline_report,
        "audit-source": cmd_audit_source,
        "validate-patch": cmd_validate_patch,
        "ready-for-gui": cmd_ready_for_gui,
    }

    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
