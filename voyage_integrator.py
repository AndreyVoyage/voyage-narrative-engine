#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re, sys, argparse
from pathlib import Path
from datetime import datetime

def log(msg, level="INFO"):
    prefix = {"INFO":"[INFO]","WARN":"[WARN]","ERROR":"[ERROR]","OK":"[OK]"}.get(level,"[INFO]")
    color = {"INFO":"","WARN":"\033[1;33m","ERROR":"\033[0;31m","OK":"\033[0;32m"}.get(level,"")
    reset = "\033[0m" if color else ""
    print(f"{color}{prefix} {msg}{reset}")

def discover_new_personas(repo_dir, session_finalize_path):
    new_personas = []
    personas_dir = repo_dir / "personas"
    if not personas_dir.exists():
        log("personas/ not found", "ERROR")
        return new_personas
    with open(session_finalize_path, "r", encoding="utf-8") as f:
        finalize_content = f.read()
    for json_file in sorted(personas_dir.glob("*_MODULE*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            log(f"Invalid JSON: {json_file.name} — {e}", "ERROR")
            continue
        char_id = data.get("id", "").lower()
        char_id = re.sub(r'(_module|_v\d+\.\d+)$', '', char_id)
        if not char_id:
            char_id = json_file.stem.lower()
            char_id = re.sub(r'(_module|_v\d+\.\d+)$', '', char_id)
        if char_id not in finalize_content and char_id.replace("_", "") not in finalize_content:
            new_personas.append({"file": json_file, "id": char_id, "data": data, "name": data.get("name", char_id), "version": data.get("version", "?")})
            log(f"New persona: {char_id} ({data.get('name', '?')})", "OK")
    return new_personas

def patch_session_finalize(repo_dir, personas):
    session_finalize = repo_dir / "session_finalize.py"
    with open(session_finalize, "r", encoding="utf-8") as f:
        content = f.read()
    changes = 0
    for p in personas:
        char_id = p["id"]
        data = p["data"]
        vscno = data.get("vscno", {})
        if not vscno:
            vscno = {"ВЛ": 2, "СТ": 2, "НЖ": 2, "ОГ": 2}
        vscno_line = f'"{char_id}": {{"ВЛ": {vscno.get("ВЛ", 2)}, "СТ": {vscno.get("СТ", 2)}, "НЖ": {vscno.get("НЖ", 2)}, "ОГ": {vscno.get("ОГ", 2)}}},'
        if f'"{char_id}":' not in content:
            content = content.replace('"maksim": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3},', '"maksim": {"ВЛ": 3, "СТ": 2, "НЖ": 2, "ОГ": 3},\n    ' + vscno_line)
            log(f"  Added VSCNO for {char_id}", "OK")
            changes += 1
        load_match = re.search(r'for char in \[(.*?)\]:', content)
        if load_match:
            current_list = load_match.group(1)
            if f'"{char_id}"' not in current_list:
                new_list = current_list.rstrip() + f', "{char_id}"'
                content = content.replace(current_list, new_list)
                log(f"  Added {char_id} to loading list", "OK")
                changes += 1
        anti = data.get("visual_data", {}).get("anti_prompts", [])
        if anti:
            try:
                split_idx = content.index("_build_negative_prompt")
                after_func = content[split_idx:]
                if f'"{char_id}":' not in after_func:
                    anti_str = ', '.join([f'"{a}"' for a in anti[:10]])
                    extras_old = '"maksim": ["bulky bodybuilder", "aggressive pose", "different hair color", "old"],'
                    extras_new = extras_old + f'\n        "{char_id}": [{anti_str}],'
                    content = content.replace(extras_old, extras_new)
                    log(f"  Added negative prompts for {char_id}", "OK")
                    changes += 1
            except ValueError:
                pass
    if changes > 0:
        with open(session_finalize, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"session_finalize.py patched ({changes} changes)", "OK")
    else:
        log("session_finalize.py already up to date", "INFO")
    return changes

def patch_readme(repo_dir, personas):
    readme_path = repo_dir / "README.md"
    if not readme_path.exists():
        log("README.md not found, skipping", "WARN")
        return 0
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    changes = 0
    for p in personas:
        char_id = p["id"]
        name = p["name"]
        version = p["version"]
        archetype = p["data"].get("psychology", {}).get("archetype", "") or p["data"].get("archetype", "")
        desc = f"{name} ({archetype})" if archetype else name
        module_id = p["data"].get("id", char_id.upper() + "_MODULE")
        if module_id.upper() in content.upper():
            continue
        last_match = None
        for m in re.finditer(r'├──\s+(\w+_MODULE.*?)\.json\s+#\s*(.*?)\n', content):
            last_match = m
        if last_match:
            insert_pos = last_match.end()
            new_line = f"│   ├── {module_id}.json    # {desc} v{version}\n"
            content = content[:insert_pos] + new_line + content[insert_pos:]
            changes += 1
            log(f"  Added {name} to README", "OK")
    if changes > 0:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"README.md updated ({changes} changes)", "OK")
    return changes

def test_finalize(repo_dir):
    log("Testing session_finalize.py...", "INFO")
    try:
        import subprocess
        result = subprocess.run([sys.executable, str(repo_dir / "session_finalize.py"), "--help"], cwd=str(repo_dir), capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            log("session_finalize.py loads OK", "OK")
            return True
        else:
            log(f"session_finalize.py failed: {result.stderr[:200]}", "ERROR")
            return False
    except Exception as e:
        log(f"Test failed: {e}", "ERROR")
        return False

def main():
    parser = argparse.ArgumentParser(description="Voyage Repo Integrator v1.1")
    parser.add_argument("--repo", default=str(Path.home() / "voyage-narrative-engine"), help="Path to repository")
    parser.add_argument("--llm-prompt", action="store_true", help="Generate LLM prompt")
    args = parser.parse_args()
    repo_dir = Path(args.repo)
    session_finalize = repo_dir / "session_finalize.py"
    log("=== Voyage Repo Integrator v1.1 ===", "INFO")
    log(f"Repo: {repo_dir}", "INFO")
    new_personas = discover_new_personas(repo_dir, session_finalize)
    if not new_personas:
        log("No new personas detected. Repository is up to date.", "OK")
        return 0
    log(f"Found {len(new_personas)} new persona(s) to integrate", "INFO")
    changes = 0
    changes += patch_session_finalize(repo_dir, new_personas)
    changes += patch_readme(repo_dir, new_personas)
    if not test_finalize(repo_dir):
        log("Tests failed! Manual intervention required.", "ERROR")
        return 1
    log(f"Integration complete. Total changes: {changes}", "OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
