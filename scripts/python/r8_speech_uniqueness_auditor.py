#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R8 Speech Uniqueness Auditor v1.0

Deterministic batch auditor for VNE persona speech uniqueness at U4+ sublevels.

Checks:
- Cross-persona exact duplicates (BLOCKER if found in U4+ sublevels)
- Cross-sublevel exact duplicates within a persona (BLOCKER if found in U4+ sublevels)
- Forbidden anti-template phrases (BLOCKER if found in any U4+ sublevel)
- Ignores sig-vs-asp duplicates WITHIN the same sublevel (by design)

Usage:
    python r8_speech_uniqueness_auditor.py [--repo-root PATH] [--output PATH]

Exit codes:
    0 = PASS (no blockers)
    1 = FAIL (blockers found)
    2 = ERROR (script/runtime error)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"

PEAK_SUBLEVELS = [
    "U4-A", "U4-B", "U5-A", "U5-B", "U6-A", "U6-B", "U7-A", "U7-B",
]

FORBIDDEN_PHRASES = [
    "не потому что должен",
    "я — твой. не потому что должен",
    "я твой. не потому что должен",
]

SPEECH_SOURCES = [
    ("signature_phrases", "sig"),
    ("speech_samples", "samples"),
    ("narrative_notes", "notes"),
    ("aftercare_speech", "aftercare"),
]


def extract_phrases(matrix: dict, sublevel: str) -> list[tuple[str, str]]:
    """Extract (phrase, source_tag) from a sublevel, excluding action_speech_pairs speech."""
    if sublevel not in matrix:
        return []
    
    sl_data = matrix[sublevel]
    results = []
    
    for field_key, source_tag in SPEECH_SOURCES:
        val = sl_data.get(field_key)
        if isinstance(val, list):
            for p in val:
                if isinstance(p, str) and p.strip():
                    results.append((p.strip(), source_tag))
        elif isinstance(val, str) and val.strip():
            results.append((val.strip(), source_tag))
    
    # action_speech_pairs: extract action descriptions separately (for reference)
    # But do NOT extract speech from ASP — those are by-design paired with sig
    for pair in sl_data.get("action_speech_pairs", []):
        action = pair.get("action", "")
        if action and isinstance(action, str):
            # We store action descriptions separately, not as speech
            pass
    
    # compliments: only if they are NOT just repeating sig phrases
    for k, v in sl_data.get("compliments", {}).items():
        if isinstance(v, str) and v.strip():
            results.append((v.strip(), f"comp_{k}"))
    
    return results


def audit_persona(path: Path) -> dict[str, Any]:
    """Audit a single persona SPEECH_MATRIX.json."""
    data, err = load_json(path)
    if err:
        return {"error": err}
    
    matrix = data.get("matrix", {})
    persona_name = data.get("persona_id", path.parent.parent.name)
    
    # Per-sublevel phrase extraction
    sublevel_phrases = {}  # sublevel -> [(phrase, source)]
    for sl in PEAK_SUBLEVELS:
        sublevel_phrases[sl] = extract_phrases(matrix, sl)
    
    # Find forbidden phrases
    forbidden = []  # [(sublevel, source, phrase)]
    for sl in PEAK_SUBLEVELS:
        for phrase, source in sublevel_phrases[sl]:
            p_lower = phrase.lower()
            for fp in FORBIDDEN_PHRASES:
                if fp in p_lower:
                    forbidden.append((sl, source, phrase))
    
    # Find cross-sublevel duplicates (same persona, different sublevels)
    # Exclude sig-vs-asp within same sublevel (they are intentional)
    cross_sublevel = []
    seen = {}  # normalized_phrase -> (sublevel, source)
    for sl in PEAK_SUBLEVELS:
        for phrase, source in sublevel_phrases[sl]:
            key = phrase.lower().strip()
            if key in seen:
                prev_sl, prev_src = seen[key]
                if prev_sl != sl:  # Only cross-sublevel, not same-sublevel
                    cross_sublevel.append((phrase, prev_sl, prev_src, sl, source))
            else:
                seen[key] = (sl, source)
    
    return {
        "persona": persona_name,
        "forbidden_count": len(forbidden),
        "forbidden": forbidden,
        "cross_sublevel_count": len(cross_sublevel),
        "cross_sublevel": cross_sublevel,
    }


def audit_all(repo_root: Path) -> dict[str, Any]:
    """Audit all personas in the repository."""
    personas_dir = repo_root / "personas"
    if not personas_dir.exists():
        return {"error": "personas/ directory not found"}
    
    speech_files = sorted(
        personas_dir.rglob("SPEECH_MATRIX.json"),
        key=lambda p: p.parent.parent.name,
    )
    
    results = []
    all_phrases = {}  # normalized -> [(persona, sublevel, source)]
    
    for sf in speech_files:
        persona_result = audit_persona(sf)
        results.append(persona_result)
        
        # Collect for cross-persona check
        persona_name = persona_result["persona"]
        for sl in PEAK_SUBLEVELS:
            for phrase, source in extract_phrases(json.load(open(sf, "r", encoding="utf-8")).get("matrix", {}), sl):
                key = phrase.lower().strip()
                if key not in all_phrases:
                    all_phrases[key] = []
                all_phrases[key].append((persona_name, sl, source))
    
    # Cross-persona duplicates
    cross_persona = []
    for phrase, occurrences in all_phrases.items():
        personas_seen = set(o[0] for o in occurrences)
        if len(personas_seen) > 1:
            cross_persona.append((phrase, occurrences))
    
    # Overall verdict
    has_blockers = (
        any(r["forbidden_count"] > 0 for r in results) or
        any(r["cross_sublevel_count"] > 0 for r in results) or
        len(cross_persona) > 0
    )
    
    return {
        "version": VERSION,
        "repo_root": str(repo_root),
        "personas_audited": len(results),
        "peak_sublevels": PEAK_SUBLEVELS,
        "has_blockers": has_blockers,
        "cross_persona_duplicates": {
            "count": len(cross_persona),
            "items": [
                {
                    "phrase": p[:200],
                    "occurrences": [
                        {"persona": o[0], "sublevel": o[1], "source": o[2]}
                        for o in occs
                    ],
                }
                for p, occs in cross_persona
            ],
        },
        "per_persona": results,
    }


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    except OSError as e:
        return None, f"read error: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="R8 Speech Uniqueness Auditor")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: 2 levels above script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    args = parser.parse_args()
    
    try:
        result = audit_all(args.repo_root)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    
    indent = 2 if args.pretty else None
    output = json.dumps(result, ensure_ascii=False, indent=indent)
    
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    
    return 1 if result["has_blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())
