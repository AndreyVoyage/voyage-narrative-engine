#!/usr/bin/env python3
"""
scenario_validator.py — Validates modular scenario structure for Voyage Engine.

Usage:
    python scenario_validator.py [scenario_id]

If scenario_id is not provided, validates all scenarios in scenarios/.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
REQUIRED_SUBDIRS = ["core", "structure", "scenes", "branches", "characters", "dynamics", "environment", "safety", "meta"]
REQUIRED_FILES = {
    "core": ["INDEX.json"],
    "structure": ["phases.json", "timeline.json", "locations.json"],
    "characters": ["ROLES.json"],
    "dynamics": ["CROSS_CHARACTER.json"],
    "environment": ["ATMOSPHERE.json"],
    "safety": ["SAFETY.json"],
    "meta": ["META.json"]
}


def load_json(path: Path) -> Optional[Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ❌ JSON error in {path}: {e}")
        return None


def validate_scenario(scenario_id: str) -> Dict[str, Any]:
    scenario_dir = SCENARIOS_DIR / scenario_id
    results = {
        "id": scenario_id,
        "valid": True,
        "errors": [],
        "warnings": [],
        "files_checked": 0,
        "files_ok": 0
    }
    
    print(f"\n{'='*60}")
    print(f"Validating scenario: {scenario_id}")
    print(f"{'='*60}")
    
    # 1. Check directory exists
    if not scenario_dir.exists():
        results["valid"] = False
        results["errors"].append(f"Scenario directory not found: {scenario_dir}")
        return results
    
    # 2. Check required subdirectories
    for subdir in REQUIRED_SUBDIRS:
        subdir_path = scenario_dir / subdir
        if not subdir_path.exists():
            results["valid"] = False
            results["errors"].append(f"Missing subdirectory: {subdir}")
        else:
            print(f"  ✅ {subdir}/")
    
    # 3. Check required files
    for subdir, files in REQUIRED_FILES.items():
        for filename in files:
            file_path = scenario_dir / subdir / filename
            results["files_checked"] += 1
            if not file_path.exists():
                results["valid"] = False
                results["errors"].append(f"Missing file: {subdir}/{filename}")
            else:
                data = load_json(file_path)
                if data is not None:
                    results["files_ok"] += 1
                    print(f"  ✅ {subdir}/{filename}")
    
    # 4. Validate INDEX.json
    index_path = scenario_dir / "core" / "INDEX.json"
    if index_path.exists():
        index = load_json(index_path)
        if index:
            required_fields = ["id", "name", "version", "participants", "synopsis"]
            for field in required_fields:
                if field not in index:
                    results["valid"] = False
                    results["errors"].append(f"INDEX.json missing field: {field}")
            if "id" in index and index["id"] != scenario_id:
                results["valid"] = False
                results["errors"].append(f"INDEX.json id mismatch: {index['id']} != {scenario_id}")
            if "participants" in index and len(index["participants"]) < 2:
                results["warnings"].append("INDEX.json participants < 2")
            print(f"  📋 Synopsis: {index.get('synopsis', 'N/A')[:80]}...")
    
    # 5. Validate phases.json vs timeline.json
    phases_path = scenario_dir / "structure" / "phases.json"
    timeline_path = scenario_dir / "structure" / "timeline.json"
    if phases_path.exists() and timeline_path.exists():
        phases = load_json(phases_path)
        timeline = load_json(timeline_path)
        if phases and timeline:
            phase_ids = set(phases.get("phases", {}).keys())
            timeline_ids = {p["phase_id"] for p in timeline.get("timeline", [])}
            if phase_ids != timeline_ids:
                missing_in_phases = timeline_ids - phase_ids
                missing_in_timeline = phase_ids - timeline_ids
                if missing_in_phases:
                    results["valid"] = False
                    results["errors"].append(f"Phases missing in phases.json: {missing_in_phases}")
                if missing_in_timeline:
                    results["valid"] = False
                    results["errors"].append(f"Phases missing in timeline.json: {missing_in_timeline}")
            else:
                print(f"  ✅ Phases/Timeline sync: {len(phase_ids)} phases")
    
    # 6. Validate scenes exist for phases
    scenes_dir = scenario_dir / "scenes"
    if scenes_dir.exists() and phases_path.exists():
        phases = load_json(phases_path)
        if phases:
            for phase_id in phases.get("phases", {}).keys():
                # Look for scene file
                scene_files = list(scenes_dir.glob(f"{phase_id}*"))
                if not scene_files:
                    results["warnings"].append(f"No scene file for phase {phase_id}")
                else:
                    print(f"  ✅ Scene for {phase_id}: {scene_files[0].name}")
    
    # 7. Validate characters in ROLES match participants
    roles_path = scenario_dir / "characters" / "ROLES.json"
    if roles_path.exists() and index_path.exists():
        roles = load_json(roles_path)
        index = load_json(index_path)
        if roles and index:
            role_chars = set(roles.get("characters", {}).keys())
            participants = set(index.get("participants", []))
            if role_chars != participants:
                missing_roles = participants - role_chars
                missing_participants = role_chars - participants
                if missing_roles:
                    results["valid"] = False
                    results["errors"].append(f"Characters without roles: {missing_roles}")
                if missing_participants:
                    results["warnings"].append(f"Roles not in participants: {missing_participants}")
            else:
                print(f"  ✅ Characters/Roles sync: {len(role_chars)} characters")
    
    # 8. Validate safety checks
    safety_path = scenario_dir / "safety" / "SAFETY.json"
    if safety_path.exists():
        safety = load_json(safety_path)
        if safety:
            hard_limits = safety.get("safety", {}).get("hard_limits", [])
            emergency_stop = safety.get("safety", {}).get("emergency_stop", "")
            if not hard_limits:
                results["warnings"].append("Safety: no hard limits defined")
            if not emergency_stop:
                results["warnings"].append("Safety: no emergency stop defined")
            else:
                print(f"  ✅ Safety: {len(hard_limits)} hard limits, emergency stop defined")
    
    # 9. Validate branches
    branches_path = scenario_dir / "branches" / "BRANCHES.json"
    if branches_path.exists():
        branches = load_json(branches_path)
        if branches:
            branch_count = len(branches.get("branches", {}))
            print(f"  ✅ Branches: {branch_count} paths")
    
    # Summary
    print(f"\n{'-'*60}")
    if results["valid"]:
        print(f"  ✅ SCENARIO VALID: {scenario_id}")
    else:
        print(f"  ❌ SCENARIO INVALID: {scenario_id}")
    print(f"  Files checked: {results['files_checked']}, OK: {results['files_ok']}")
    if results["errors"]:
        print(f"  Errors ({len(results['errors'])}):")
        for err in results["errors"]:
            print(f"    - {err}")
    if results["warnings"]:
        print(f"  Warnings ({len(results['warnings'])}):")
        for warn in results["warnings"]:
            print(f"    - {warn}")
    print(f"{'-'*60}")
    
    return results


def main():
    if len(sys.argv) > 1:
        scenario_ids = sys.argv[1:]
    else:
        # Find all scenario directories (exclude legacy files)
        scenario_ids = []
        for item in SCENARIOS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                scenario_ids.append(item.name)
    
    if not scenario_ids:
        print("No scenarios found to validate.")
        sys.exit(1)
    
    print(f"Found {len(scenario_ids)} scenario(s) to validate")
    
    all_results = []
    valid_count = 0
    for sid in sorted(scenario_ids):
        result = validate_scenario(sid)
        all_results.append(result)
        if result["valid"]:
            valid_count += 1
    
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total: {len(all_results)}")
    print(f"  Valid: {valid_count}")
    print(f"  Invalid: {len(all_results) - valid_count}")
    
    if valid_count == len(all_results):
        print(f"\n  ✅ ALL SCENARIOS VALID")
        sys.exit(0)
    else:
        print(f"\n  ❌ SOME SCENARIOS INVALID")
        sys.exit(1)


if __name__ == "__main__":
    main()
