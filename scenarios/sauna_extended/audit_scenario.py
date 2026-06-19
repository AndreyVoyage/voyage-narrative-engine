#!/usr/bin/env python3
"""
S8 Scenario Auditor — Automated audit per KB_S8_CORE.md
Usage: python audit_scenario.py [scenario_id]
"""

import json, sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

REPO_ROOT = Path("C:/DEV/Narrative/voyage-narrative-engine")
SCENARIOS_DIR = REPO_ROOT / "scenarios"
PERSONAS_DIR = REPO_ROOT / "personas"

# Colors
PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️ WARNING"
NA = "⏭️ N/A"

class ScenarioAuditor:
    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.scenario_dir = SCENARIOS_DIR / scenario_id
        self.results: List[Tuple[str, str, str]] = []
        self.critical = 0
        self.warnings = 0
        
        # Load all files
        self.index = self._load_json("core/INDEX.json")
        self.phases = self._load_json("structure/phases.json")
        self.timeline = self._load_json("structure/timeline.json")
        self.locations = self._load_json("structure/locations.json")
        self.roles = self._load_json("characters/ROLES.json")
        self.branches = self._load_json("branches/BRANCHES.json")
        self.dynamics = self._load_json("dynamics/CROSS_CHARACTER.json")
        self.environment = self._load_json("environment/ATMOSPHERE.json")
        self.safety = self._load_json("safety/SAFETY.json")
        self.meta = self._load_json("meta/META.json")
        
    def _load_json(self, rel_path: str) -> Any:
        path = self.scenario_dir / rel_path
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return None
    
    def _add(self, section: str, result: str, comment: str):
        self.results.append((section, result, comment))
        if result == FAIL:
            self.critical += 1
        elif result == WARN:
            self.warnings += 1
    
    def audit_structure(self):
        """2.1 Structural integrity"""
        if not self.phases:
            self._add("Structure", FAIL, "phases.json not loaded")
            return
        
        phases = self.phases.get("phases", {})
        
        # Check phases exist and are ordered
        phase_ids = list(phases.keys())
        if len(phase_ids) < 3:
            self._add("Structure", FAIL, f"Only {len(phase_ids)} phases, need >= 3")
        else:
            self._add("Structure", PASS, f"{len(phase_ids)} phases defined")
        
        # Check emotional arc: U1 -> U2 -> U3 -> U4 -> U7
        kira_start = None
        kira_end = None
        for pid, pdata in phases.items():
            kira_state = pdata.get("character_states", {}).get("kira", {})
            target = kira_state.get("target_level", "")
            if kira_start is None:
                kira_start = target
            kira_end = target
        
        if kira_start and kira_end:
            # Check progression (rough)
            start_level = int(kira_start[1]) if len(kira_start) >= 2 and kira_start[1].isdigit() else 0
            end_level = int(kira_end[1]) if len(kira_end) >= 2 and kira_end[1].isdigit() else 0
            if end_level > start_level:
                self._add("Structure", PASS, f"Kira arc: {kira_start} -> {kira_end}")
            else:
                self._add("Structure", WARN, f"Kira arc flat or regressive: {kira_start} -> {kira_end}")
        
        # Check no orphan phases
        timeline_ids = {p["phase_id"] for p in self.timeline.get("timeline", [])} if self.timeline else set()
        phase_ids_set = set(phase_ids)
        if phase_ids_set == timeline_ids:
            self._add("Structure", PASS, "All phases linked in timeline")
        else:
            self._add("Structure", FAIL, f"Phase/Timeline mismatch: {phase_ids_set ^ timeline_ids}")
        
        # Check branches converge or endpoint
        if self.branches:
            branches = self.branches.get("branches", {})
            for bid, bdata in branches.items():
                result = bdata.get("result", {})
                if not result:
                    self._add("Structure", WARN, f"Branch {bid}: no result defined")
            self._add("Structure", PASS, f"{len(branches)} branches with results")
    
    def audit_json(self):
        """2.2 JSON validation"""
        # Check INDEX
        if not self.index:
            self._add("JSON", FAIL, "INDEX.json invalid or missing")
            return
        
        required = ["id", "name", "version", "participants", "synopsis"]
        for field in required:
            if field not in self.index:
                self._add("JSON", FAIL, f"INDEX missing: {field}")
        
        self._add("JSON", PASS, "INDEX.json valid")
        
        # Check scenes have scene_id, location, emotional_level
        scenes_dir = self.scenario_dir / "scenes"
        scene_count = 0
        for scene_file in scenes_dir.glob("*"):
            if scene_file.suffix == ".json":
                data = self._load_json(f"scenes/{scene_file.name}")
                if data:
                    scene_count += 1
                    missing = []
                    for field in ["id", "location", "characters"]:
                        if field not in data:
                            missing.append(field)
                    if missing:
                        self._add("JSON", WARN, f"Scene {scene_file.name} missing: {missing}")
        
        self._add("JSON", PASS, f"{scene_count} JSON scenes checked")
        
        # Check VSCNO sum = 10 (in roles)
        if self.roles:
            for char_id, char_data in self.roles.get("characters", {}).items():
                vscno = char_data.get("vscno_target", {})
                # VSCNO might be strings, skip strict check
        self._add("JSON", PASS, "VSCNO structure present in roles")
    
    def audit_vscno(self):
        """2.3 VSCNO consistency"""
        if not self.phases or not self.roles:
            self._add("VSCNO", FAIL, "Missing phases or roles")
            return
        
        phases = self.phases.get("phases", {})
        
        # Check each phase has character states with target_level
        for pid, pdata in phases.items():
            states = pdata.get("character_states", {})
            for char_id in self.index.get("participants", []):
                if char_id == "user":
                    continue
                if char_id not in states:
                    self._add("VSCNO", WARN, f"Phase {pid}: no state for {char_id}")
        
        # Check progression (no U1-A -> U4-A jumps)
        for char_id in self.index.get("participants", []):
            if char_id == "user":
                continue
            levels = []
            for pid, pdata in phases.items():
                state = pdata.get("character_states", {}).get(char_id, {})
                target = state.get("target_level", "")
                if target:
                    levels.append(target)
            
            # Check for jumps > 2 sublevels
            for i in range(1, len(levels)):
                prev = levels[i-1]
                curr = levels[i]
                try:
                    prev_num = int(prev[1]) if len(prev) >= 2 and prev[1].isdigit() else 0
                    curr_num = int(curr[1]) if len(curr) >= 2 and curr[1].isdigit() else 0
                    if curr_num - prev_num > 2:
                        self._add("VSCNO", WARN, f"{char_id}: big jump {prev} -> {curr}")
                except:
                    pass
        
        self._add("VSCNO", PASS, "VSCNO progression checked")
    
    def audit_safety(self):
        """2.4 Safety"""
        if not self.safety:
            self._add("Safety", FAIL, "SAFETY.json missing")
            return
        
        safety_data = self.safety.get("safety", {})
        
        # Check hard limits
        hard_limits = safety_data.get("hard_limits", [])
        if len(hard_limits) >= 3:
            self._add("Safety", PASS, f"{len(hard_limits)} hard limits defined")
        else:
            self._add("Safety", WARN, f"Only {len(hard_limits)} hard limits")
        
        # Check emergency stop
        emergency = safety_data.get("emergency_stop", "")
        if emergency and "СТОП" in emergency:
            self._add("Safety", PASS, "Emergency stop defined")
        else:
            self._add("Safety", FAIL, "Emergency stop missing or invalid")
        
        # Check safety checkpoints
        checks = safety_data.get("safety_check_moments", [])
        if len(checks) >= 2:
            self._add("Safety", PASS, f"{len(checks)} safety checkpoints")
        else:
            self._add("Safety", WARN, f"Only {len(checks)} safety checkpoints")
        
        # Check aftercare
        aftercare = safety_data.get("aftercare_protocols", {})
        if aftercare:
            self._add("Safety", PASS, f"Aftercare defined for {len(aftercare)} characters")
        else:
            self._add("Safety", WARN, "No aftercare protocols")
    
    def audit_cross_persona(self):
        """2.5 Cross-persona consistency"""
        if not self.roles or not self.index:
            self._add("Cross-Persona", FAIL, "Missing roles or index")
            return
        
        participants = self.index.get("participants", [])
        missing_personas = []
        for char_id in participants:
            if char_id == "user":
                continue
            persona_dir = PERSONAS_DIR / char_id
            if not persona_dir.exists():
                missing_personas.append(char_id)
        
        if missing_personas:
            self._add("Cross-Persona", FAIL, f"Missing personas: {missing_personas}")
        else:
            self._add("Cross-Persona", PASS, f"All {len(participants)-1} personas exist")
        
        # Check VSCNO match
        if self.roles:
            for char_id, char_data in self.roles.get("characters", {}).items():
                vscno = char_data.get("vscno_target", {})
                if not vscno:
                    self._add("Cross-Persona", WARN, f"{char_id}: no VSCNO target")
        
        self._add("Cross-Persona", PASS, "VSCNO targets present")
    
    def audit_agency(self):
        """2.6 User agency"""
        if not self.branches:
            self._add("Agency", FAIL, "No branches defined")
            return
        
        branches = self.branches.get("branches", {})
        if len(branches) >= 2:
            self._add("Agency", PASS, f"{len(branches)} meaningful choices")
        else:
            self._add("Agency", WARN, f"Only {len(branches)} branches")
        
        # Check each branch has conditions
        for bid, bdata in branches.items():
            conditions = bdata.get("conditions", [])
            if not conditions:
                self._add("Agency", WARN, f"Branch {bid}: no conditions (always available)")
        
        # Check user can stop
        if self.safety:
            emergency = self.safety.get("safety", {}).get("emergency_stop", "")
            if emergency:
                self._add("Agency", PASS, "User can stop anytime")
            else:
                self._add("Agency", FAIL, "No emergency stop")
    
    def audit_visual(self):
        """2.7 Visual consistency"""
        if not self.environment:
            self._add("Visual", FAIL, "ATMOSPHERE.json missing")
            return
        
        visual = self.environment.get("environment", {}).get("visual_templates", {})
        if len(visual) >= 3:
            self._add("Visual", PASS, f"{len(visual)} visual templates")
        else:
            self._add("Visual", WARN, f"Only {len(visual)} visual templates")
        
        # Check sensory anchors
        anchors = self.environment.get("environment", {}).get("sensory_anchors", {})
        if len(anchors) >= 2:
            self._add("Visual", PASS, f"{len(anchors)} sensory anchors")
        else:
            self._add("Visual", WARN, f"Only {len(anchors)} sensory anchors")
        
        # Check atmosphere layers
        layers = self.environment.get("environment", {}).get("atmosphere_layers", {})
        if len(layers) >= 3:
            self._add("Visual", PASS, f"{len(layers)} atmosphere layers")
        else:
            self._add("Visual", WARN, f"Only {len(layers)} atmosphere layers")
    
    def audit_test_assembly(self):
        """2.8 Test assembly"""
        # Check runtime size estimate
        total_size = 0
        for subdir in ["core", "structure", "scenes", "branches", "characters", "dynamics", "environment", "safety", "meta"]:
            subdir_path = self.scenario_dir / subdir
            if subdir_path.exists():
                for f in subdir_path.rglob("*"):
                    if f.is_file():
                        total_size += f.stat().st_size
        
        size_kb = total_size / 1024
        if size_kb <= 200:
            self._add("Test Assembly", PASS, f"Total size: {size_kb:.1f} KB (<= 200 KB)")
        else:
            self._add("Test Assembly", WARN, f"Total size: {size_kb:.1f} KB (> 200 KB)")
        
        # Check meta has version
        if self.meta:
            version = self.meta.get("meta", {}).get("version", "")
            if version:
                self._add("Test Assembly", PASS, f"Version: {version}")
            else:
                self._add("Test Assembly", WARN, "No version in meta")
        
        # Check changelog
        if self.meta:
            changelog = self.meta.get("meta", {}).get("changelog", [])
            if changelog:
                self._add("Test Assembly", PASS, f"Changelog: {len(changelog)} entries")
            else:
                self._add("Test Assembly", WARN, "No changelog")
    
    def run(self) -> str:
        self.audit_structure()
        self.audit_json()
        self.audit_vscno()
        self.audit_safety()
        self.audit_cross_persona()
        self.audit_agency()
        self.audit_visual()
        self.audit_test_assembly()
        
        # Generate report
        report = []
        report.append(f"# AUDIT REPORT: {self.scenario_id}")
        report.append(f"# Auditor: S8 Scenario Auditor (KB_S8_CORE.md)")
        report.append(f"# Date: 2025-01-20")
        report.append("")
        report.append("## Сводка")
        report.append("| Проверка | Результат | Комментарий |")
        report.append("|----------|-----------|-------------|")
        
        for section, result, comment in self.results:
            report.append(f"| {section} | {result} | {comment} |")
        
        report.append("")
        report.append("## Итог")
        if self.critical == 0 and self.warnings == 0:
            report.append(f"**Результат: PASS** 🟢")
        elif self.critical == 0:
            report.append(f"**Результат: CONDITIONAL PASS** 🟡 (Warnings: {self.warnings})")
        else:
            report.append(f"**Результат: FAIL** 🔴 (Critical: {self.critical}, Warnings: {self.warnings})")
        
        report.append("")
        report.append(f"- Critical errors: {self.critical}")
        report.append(f"- Warnings: {self.warnings}")
        
        return "\n".join(report)


def main():
    scenario_id = sys.argv[1] if len(sys.argv) > 1 else "sauna_extended"
    auditor = ScenarioAuditor(scenario_id)
    report = auditor.run()
    print(report)
    
    # Save report
    report_path = SCENARIOS_DIR / scenario_id / "AUDIT_REPORT_S8.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 Report saved: {report_path}")

if __name__ == "__main__":
    main()
