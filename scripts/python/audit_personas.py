#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Persona Audit v0.1

Deterministic stdlib-only batch auditor for Voyage Narrative Engine personas.

Scans modular personas (personas/<id>/INDEX.json) and legacy monolithic persona
files (personas/*MODULE*.json). Reports structural integrity, required fields,
module existence, VSCNO consistency, visual generation readiness, and safety.

Does NOT evaluate narrative quality, psychology, or generate images.
Does NOT modify persona files.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VERSION = "0.1.0"
STATUS = "persona_audit_ready"

SUBLEVELS = [
    "U1-A", "U1-B", "U2-A", "U2-B", "U3-A", "U3-B", "U4-A",
    "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B",
]
VSCNO_AXES = ("ВЛ", "СТ", "НЖ", "ОГ")


@dataclass
class PersonaResult:
    id: str
    kind: str
    path: str
    status: str = "PASS"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    except OSError as e:
        return None, f"read error: {e}"


def discover_modular_personas(repo_root: Path) -> list[tuple[str, Path]]:
    personas_dir = repo_root / "personas"
    found: list[tuple[str, Path]] = []
    if not personas_dir.exists():
        return found
    for subdir in sorted(personas_dir.iterdir(), key=lambda p: p.name):
        if not subdir.is_dir():
            continue
        index = subdir / "INDEX.json"
        if index.exists():
            found.append((subdir.name, index))
    return found


def discover_monoliths(repo_root: Path) -> list[Path]:
    personas_dir = repo_root / "personas"
    if not personas_dir.exists():
        return []
    return sorted(
        [p for p in personas_dir.glob("*MODULE*.json") if p.is_file()],
        key=lambda p: p.name,
    )


def check_required_fields(data: dict[str, Any], result: PersonaResult) -> None:
    for key in ("id", "name", "version"):
        value = data.get(key)
        if not value or not str(value).strip():
            result.errors.append(f"missing required field '{key}'")


def check_index_modules(index_dir: Path, data: dict[str, Any], result: PersonaResult) -> None:
    modules = data.get("modules")
    if modules is None:
        result.warnings.append("INDEX has no 'modules' section; cannot verify required modules")
        return
    if not isinstance(modules, dict):
        result.warnings.append("INDEX 'modules' has unexpected shape; cannot verify required modules")
        return

    missing_required: list[str] = []
    missing_optional: list[str] = []
    for rel_path, meta in modules.items():
        if not isinstance(meta, dict):
            continue
        module_file = index_dir / rel_path
        if module_file.exists():
            continue
        if meta.get("required", False):
            missing_required.append(rel_path)
        else:
            missing_optional.append(rel_path)

    if missing_required:
        result.errors.extend(f"required module missing: {p}" for p in missing_required)
    if missing_optional:
        result.warnings.extend(f"optional module missing: {p}" for p in missing_optional)


def check_levels_vscno(persona_dir: Path, result: PersonaResult) -> None:
    levels_dir = persona_dir / "levels"
    if not levels_dir.exists():
        result.warnings.append("levels directory missing")
        return

    present = {p.stem for p in levels_dir.glob("U?-?.json") if p.is_file()}
    result.checks["levels_present"] = sorted(present)
    missing = [sl for sl in SUBLEVELS if sl not in present]
    if missing:
        result.warnings.append(f"missing level files: {', '.join(missing)}")

    vscno_errors: list[str] = []
    for sublevel in SUBLEVELS:
        path = levels_dir / f"{sublevel}.json"
        if not path.exists():
            continue
        data, err = load_json(path)
        if err:
            result.warnings.append(f"levels/{sublevel}.json: {err}")
            continue
        if not isinstance(data, dict):
            continue
        vscno = data.get("vscno")
        if vscno is None:
            continue
        if not isinstance(vscno, dict):
            result.warnings.append(f"levels/{sublevel}.json: vscno has unexpected shape")
            continue
        total = sum(
            v for k, v in vscno.items()
            if k in VSCNO_AXES and isinstance(v, (int, float))
        )
        if total != 10:
            vscno_errors.append(f"{sublevel}: sum={total}")
        else:
            # also validate ranges
            for axis in VSCNO_AXES:
                val = vscno.get(axis)
                if isinstance(val, (int, float)) and not 0 <= val <= 4:
                    vscno_errors.append(f"{sublevel}: {axis}={val} out of [0,4]")

    if vscno_errors:
        result.errors.extend(f"VSCNO error: {e}" for e in vscno_errors)


def extract_nested_text(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def check_visual_readiness(persona_dir: Path, result: PersonaResult) -> None:
    prompt_base_path = persona_dir / "visual" / "PROMPT_BASE.json"
    visual_anchors_path = persona_dir / "visual" / "VISUAL_ANCHORS.json"
    identity_path = persona_dir / "core" / "IDENTITY.json"

    prompt_base_data, _ = load_json(prompt_base_path) if prompt_base_path.exists() else (None, None)
    visual_anchors_data, _ = load_json(visual_anchors_path) if visual_anchors_path.exists() else (None, None)
    identity_data, _ = load_json(identity_path) if identity_path.exists() else (None, None)

    prompt_base = ""
    if isinstance(prompt_base_data, dict):
        prompt_base = str(prompt_base_data.get("prompt_base", "")).strip()
    if not prompt_base and isinstance(visual_anchors_data, dict):
        prompt_base = str(visual_anchors_data.get("prompt_base", "")).strip()

    anti_prompts: list[str] = []
    if isinstance(prompt_base_data, dict):
        ap = prompt_base_data.get("anti_prompts")
        if isinstance(ap, list):
            anti_prompts = [str(x) for x in ap if str(x).strip()]
    if not anti_prompts and isinstance(visual_anchors_data, dict):
        ap = visual_anchors_data.get("anti_prompts")
        if isinstance(ap, list):
            anti_prompts = [str(x) for x in ap if str(x).strip()]

    anatomic_anchor = extract_nested_text(identity_data, "anatomic_anchor")
    visual_signature_identity = str(extract_nested_text(identity_data, "visual_signature") or "").strip()
    visual_signature_prompt = str(extract_nested_text(prompt_base_data, "visual_signature") or "").strip()
    visual_signature_anchors = str(extract_nested_text(visual_anchors_data, "visual_signature") or "").strip()

    has_anatomic = bool(anatomic_anchor and isinstance(anatomic_anchor, dict) and anatomic_anchor)
    has_visual_signature = bool(
        visual_signature_identity or visual_signature_prompt or visual_signature_anchors
    )

    result.checks["has_prompt_base"] = bool(prompt_base)
    result.checks["has_anti_prompts"] = bool(anti_prompts)
    result.checks["has_anatomic_anchor"] = has_anatomic
    result.checks["has_visual_signature"] = has_visual_signature

    if not prompt_base:
        result.warnings.append("missing non-empty prompt_base in visual/PROMPT_BASE.json or visual/VISUAL_ANCHORS.json")
    if not anti_prompts:
        result.warnings.append("missing or empty anti_prompts")
    if not has_anatomic and not has_visual_signature:
        result.warnings.append("neither anatomic_anchor nor visual_signature is populated")
    elif not has_visual_signature:
        result.warnings.append("visual_signature is empty across visual and core files")


def check_safety(persona_dir: Path, index_data: dict[str, Any], result: PersonaResult) -> None:
    # Determine whether safety is required from INDEX module declarations.
    modules = index_data.get("modules", {}) if isinstance(index_data, dict) else {}
    safety_required = False
    safety_rel_path = ""
    for rel_path, meta in modules.items():
        if not isinstance(meta, dict):
            continue
        if rel_path.lower().startswith("safety/") and meta.get("required", False):
            safety_required = True
            safety_rel_path = rel_path
            break

    safety_files = sorted(persona_dir.glob("safety/*.json"))
    if not safety_files:
        if safety_required:
            result.errors.append(f"required safety module missing: {safety_rel_path}")
        else:
            result.warnings.append("no safety JSON files found")
        return

    safety_data, err = load_json(safety_files[0])
    if err:
        result.warnings.append(f"safety file parse error: {err}")
        return
    if not isinstance(safety_data, dict):
        result.warnings.append("safety file has unexpected shape")
        return

    has_stop = bool(safety_data.get("stop_words"))
    has_emergency = bool(
        safety_data.get("emergency_phrase") or safety_data.get("emergency_response")
    )
    has_hard = bool(safety_data.get("hard_limits"))

    if not (has_stop or has_emergency or has_hard):
        result.warnings.append("safety protocol lacks stop_words, emergency_phrase/response, and hard_limits")


def audit_modular_persona(persona_id: str, index_path: Path) -> PersonaResult:
    persona_dir = index_path.parent
    result = PersonaResult(
        id=persona_id,
        kind="modular",
        path=str(index_path.relative_to(persona_dir.parent.parent)),
    )

    data, err = load_json(index_path)
    if err:
        result.errors.append(err)
        result.status = "FAIL"
        return result
    if not isinstance(data, dict):
        result.errors.append("INDEX.json root is not an object")
        result.status = "FAIL"
        return result

    check_required_fields(data, result)
    index_id = str(data.get("id", "")).strip()
    if index_id and index_id != persona_id:
        result.warnings.append(f"INDEX id '{index_id}' does not match folder '{persona_id}'")

    check_index_modules(persona_dir, data, result)
    check_levels_vscno(persona_dir, result)
    check_visual_readiness(persona_dir, result)
    check_safety(persona_dir, data, result)

    result.status = determine_status(result)
    return result


def audit_monolith(path: Path, repo_root: Path) -> PersonaResult:
    rel_path = path.relative_to(repo_root)
    result = PersonaResult(
        id=path.stem,
        kind="legacy_monolith",
        path=str(rel_path),
    )

    data, err = load_json(path)
    if err:
        result.warnings.append(err)
        result.status = "WARN"
        return result
    if not isinstance(data, dict):
        result.warnings.append("root is not an object")
        result.status = "WARN"
        return result

    for key in ("id", "name", "version"):
        value = data.get(key)
        if not value or not str(value).strip():
            result.warnings.append(f"missing field '{key}'")
        elif key == "id":
            result.id = str(value)

    result.status = determine_status(result)
    return result


def determine_status(result: PersonaResult) -> str:
    if result.errors:
        return "FAIL"
    if result.warnings:
        return "WARN"
    return "PASS"


def build_report(
    repo_root: Path,
    modular_results: list[PersonaResult],
    monolith_results: list[PersonaResult],
    persona_filter: str | None,
) -> dict[str, Any]:
    all_results = modular_results + monolith_results
    if persona_filter:
        all_results = [r for r in all_results if r.id == persona_filter]

    summary = {"total": len(all_results), "pass": 0, "warn": 0, "fail": 0}
    for r in all_results:
        summary[r.status.lower()] += 1

    return {
        "tool": "audit_personas",
        "version": VERSION,
        "status": STATUS,
        "repo_root": str(repo_root),
        "summary": summary,
        "personas": [
            {
                "id": r.id,
                "kind": r.kind,
                "path": r.path,
                "status": r.status,
                "errors": r.errors,
                "warnings": r.warnings,
                "checks": r.checks,
            }
            for r in all_results
        ],
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Batch Persona Audit v0.1",
        "",
        "## Summary",
        "",
        "| Total | PASS | WARN | FAIL |",
        "|---:|---:|---:|---:|",
        f"| {report['summary']['total']} | {report['summary']['pass']} | {report['summary']['warn']} | {report['summary']['fail']} |",
        "",
        "## Personas",
        "",
        "| ID | Kind | Status | Errors | Warnings |",
        "|---|---|---:|---:|---:|",
    ]
    for p in report["personas"]:
        lines.append(
            f"| {p['id']} | {p['kind']} | {p['status']} | {len(p['errors'])} | {len(p['warnings'])} |"
        )

    lines.extend(["", "## Details", ""])
    for p in report["personas"]:
        lines.extend([
            f"### {p['id']}",
            f"- Kind: {p['kind']}",
            f"- Path: {p['path']}",
            f"- Status: {p['status']}",
        ])
        if p["errors"]:
            lines.append("- Errors:")
            lines.extend(f"  - {e}" for e in p["errors"])
        else:
            lines.append("- Errors: none")
        if p["warnings"]:
            lines.append("- Warnings:")
            lines.extend(f"  - {w}" for w in p["warnings"])
        else:
            lines.append("- Warnings: none")
        if p["checks"]:
            lines.append("- Checks:")
            for k, v in p["checks"].items():
                lines.append(f"  - {k}: {v}")
        lines.append("")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch Persona Audit v0.1 for Voyage Narrative Engine.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Batch Persona Audit v{VERSION}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run audit without writing files (default behavior).",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output file path. If omitted, report is printed to stdout.",
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=None,
        help="Audit only the persona with this id.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any persona has WARN or FAIL.",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Repository root path. Defaults to auto-detected VNE root.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else default_repo_root()
    repo_root = repo_root.resolve()

    modular = discover_modular_personas(repo_root)
    monoliths = discover_monoliths(repo_root)

    modular_results = [audit_modular_persona(pid, idx) for pid, idx in modular]
    monolith_results = [audit_monolith(p, repo_root) for p in monoliths]

    report = build_report(repo_root, modular_results, monolith_results, args.persona)

    output_text = render_json(report) if args.format == "json" else render_markdown(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_text)
        # Use a short message safe for any console encoding.
        print(f"Batch Persona Audit v0.1 report written: {output_path}")
    else:
        # Write directly to binary stdout to avoid Windows cp1252 issues.
        sys.stdout.buffer.write(output_text.encode("utf-8"))

    if args.strict:
        if report["summary"]["warn"] > 0 or report["summary"]["fail"] > 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
