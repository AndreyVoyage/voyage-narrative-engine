#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Session Retrospector v0.2 deterministic repo status reports.

This module reports repository and gate metadata only. It intentionally does
not implement SR-Q4 scoring or deep raw session log analytics yet.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


VERSION = "0.2.0"
STATUS = "repo_status_report_ready"
GATE_NAMES = ("runtime", "prompt", "schema", "retrospective")
REPORT_DIRS = {
    "runtime": Path("reports/runtime"),
    "prompts": Path("reports/prompts"),
    "retrospective": Path("reports/retrospective"),
}
LIMITATIONS = [
    "Session Retrospector v0.2 reports repository and gate metadata only.",
    "It does not implement SR-Q4 scoring.",
    "It does not perform deep raw session log analysis.",
    "It does not call LLMs or external services.",
]
RECOMMENDED_NEXT_PHASE = (
    "Phase 2C: add smoke tests and full gate verification for Session Retrospector v0.2"
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_git(repo_root: Path, args: list[str], no_git: bool = False) -> tuple[bool, str]:
    if no_git:
        return False, ""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def collect_repo_status(repo_root: Path, no_git: bool) -> dict[str, Any]:
    branch_ok, branch = run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], no_git)
    head_ok, head = run_git(repo_root, ["rev-parse", "HEAD"], no_git)
    origin_ok, origin_head = run_git(repo_root, ["rev-parse", "origin/main"], no_git)
    status_ok, status_text = run_git(repo_root, ["status", "--porcelain=v1", "-uall"], no_git)

    status_short = status_text.splitlines() if status_ok and status_text else []
    return {
        "root": str(repo_root),
        "branch": branch if branch_ok else "",
        "head": head if head_ok else "",
        "origin_head": origin_head if origin_ok else "",
        "head_equals_origin": bool(head and origin_head and head == origin_head),
        "clean": status_ok and not status_short,
        "status_short": status_short,
    }


def collect_latest_commits(repo_root: Path, count: int, no_git: bool) -> list[str]:
    count = max(0, count)
    if count == 0:
        return []
    ok, output = run_git(repo_root, ["log", "--oneline", "--decorate", "-n", str(count)], no_git)
    return output.splitlines() if ok and output else []


def extract_gate_config(repo_root: Path) -> dict[str, list[str]]:
    gates = {name: [] for name in GATE_NAMES}
    project_yaml = repo_root / ".voyage" / "project.yaml"
    if not project_yaml.exists():
        return gates

    lines = project_yaml.read_text(encoding="utf-8", errors="replace").splitlines()
    in_quality_gates = False
    current_gate = ""

    for line in lines:
        stripped = line.strip()
        if stripped == "quality_gates:":
            in_quality_gates = True
            continue
        if not in_quality_gates:
            continue
        if stripped and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            candidate = stripped[:-1]
            current_gate = candidate if candidate in gates else ""
            continue
        if current_gate and stripped.startswith("- "):
            gates[current_gate].append(stripped[2:].strip())

    return gates


def detect_reports(repo_root: Path) -> dict[str, list[str]]:
    reports: dict[str, list[str]] = {}
    for name, rel_dir in REPORT_DIRS.items():
        directory = repo_root / rel_dir
        if not directory.exists():
            reports[name] = []
            continue
        files = [
            path.relative_to(repo_root).as_posix()
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ]
        reports[name] = files
    return reports


def build_report(repo_root: Path, include_commits: int, no_git: bool) -> dict[str, Any]:
    return {
        "tool": "session_retrospector",
        "version": VERSION,
        "status": STATUS,
        "repo": collect_repo_status(repo_root, no_git),
        "gates": extract_gate_config(repo_root),
        "reports": detect_reports(repo_root),
        "latest_commits": collect_latest_commits(repo_root, include_commits, no_git),
        "limitations": LIMITATIONS,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    repo = report["repo"]
    lines = [
        "# Session Retrospector v0.2",
        "",
        "## Repository Status",
        f"- Root: {repo['root']}",
        f"- Branch: {repo['branch'] or 'unknown'}",
        f"- HEAD: {repo['head'] or 'unknown'}",
        f"- origin/main: {repo['origin_head'] or 'unknown'}",
        f"- HEAD equals origin/main: {'YES' if repo['head_equals_origin'] else 'NO'}",
        f"- Working tree clean: {'YES' if repo['clean'] else 'NO'}",
    ]
    if repo["status_short"]:
        lines.append("- Status entries:")
        lines.extend(f"  - {entry}" for entry in repo["status_short"])

    lines.extend(["", "## Gate Configuration"])
    for gate_name in GATE_NAMES:
        commands = report["gates"].get(gate_name, [])
        lines.append(f"- {gate_name}:")
        if commands:
            lines.extend(f"  - `{command}`" for command in commands)
        else:
            lines.append("  - not configured")

    lines.extend(["", "## Generated Reports Detected"])
    for report_name, files in report["reports"].items():
        lines.append(f"- {report_name}:")
        if files:
            lines.extend(f"  - {file_path}" for file_path in files)
        else:
            lines.append("  - none")

    lines.extend(["", "## Latest Commits"])
    if report["latest_commits"]:
        lines.extend(f"- {commit}" for commit in report["latest_commits"])
    else:
        lines.append("- none")

    lines.extend(["", "## Known Limitations"])
    lines.extend(f"- {item}" for item in report["limitations"])

    lines.extend(["", "## Recommended Next Phase", f"- {report['recommended_next_phase']}", ""])
    return "\n".join(lines)


def render_report(report: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return render_json(report)
    return render_markdown(report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Session Retrospector v0.2 deterministic repo status reports."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Session Retrospector v{VERSION}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect metadata and validate the CLI without writing files.",
    )
    parser.add_argument(
        "--output",
        help="Optional report output path. No report is written unless provided.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output report format when --output is provided.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(default_repo_root()),
        help="Repository root path. Defaults to auto-detected VNE root.",
    )
    parser.add_argument(
        "--include-commits",
        type=int,
        default=5,
        help="Number of latest commits to include.",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip git commands and use fallback repository metadata.",
    )
    return parser


def print_status(report: dict[str, Any], dry_run: bool) -> None:
    repo = report["repo"]
    print("Session Retrospector v0.2")
    print("Status: repo status report ready")
    print(f"Repository: {repo['root']}")
    print(f"Branch: {repo['branch'] or 'unknown'}")
    print(f"Clean: {'YES' if repo['clean'] else 'NO'}")
    if dry_run:
        print("Dry run: no files written")
    else:
        print("No retrospective report generated because --output was not provided")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = build_report(repo_root, args.include_commits, args.no_git)

    if args.dry_run:
        print_status(report, dry_run=True)
        return 0

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_report(report, args.format), encoding="utf-8")
        print(f"Session Retrospector v0.2 report written: {output_path}")
        return 0

    print_status(report, dry_run=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
