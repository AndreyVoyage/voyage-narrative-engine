#!/usr/bin/env python3
# check_consistency.py — Voyage Visual Consistency Checker v0.1 (stub)
# Заглушка для будущей автоматической проверки консистентности лиц.
# Сейчас работает в ручном режиме: сравнивает пути к файлам и выдаёт рекомендации.

import json
import sys
import os
from pathlib import Path

USAGE = '''
Usage: python check_consistency.py <character_id> <new_image_path> [reference_image_path]

Example:
  python check_consistency.py KIRA_MODULE_v14 /path/to/new_kira.png /path/to/reference_kira.png

If reference_image_path is omitted, uses the last successful reference from generation_history.
'''

def load_character_module(character_id):
    """Load character JSON module from personas/ directory."""
    repo_dir = Path.home() / "voyage-narrative-engine"
    module_path = repo_dir / "personas" / f"{character_id}.json"

    if not module_path.exists():
        print(f"[ERROR] Module not found: {module_path}")
        print(f"[INFO] Searched in: {repo_dir / 'personas'}")
        sys.exit(1)

    with open(module_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_reference_image(module, explicit_path=None):
    """Get reference image path: explicit or from generation_history."""
    if explicit_path:
        return Path(explicit_path)

    visual_data = module.get("visual_data", {})
    ref_path = visual_data.get("reference_image")

    if ref_path and Path(ref_path).exists():
        return Path(ref_path)

    # Try last successful generation
    history = visual_data.get("generation_history", [])
    for entry in reversed(history):
        if entry.get("result") == "success" and entry.get("consistency_check") in ["manual_pass", "auto_pass"]:
            # Try to reconstruct path from session_id
            session_id = entry.get("session_id", "unknown")
            repo_dir = Path.home() / "voyage-narrative-engine"
            candidate = repo_dir / "assets" / "images" / "character_sessions" / module["id"].split("_")[0].lower() / f"{session_id}.png"
            if candidate.exists():
                return candidate

    return None

def manual_check_guide(module, new_image_path, reference_path):
    """Print manual comparison guide."""
    anatomic = module.get("visual_data", {}).get("anatomic_anchor", {})
    signature = anatomic.get("visual_signature", "N/A")

    print("=" * 60)
    print("Voyage Visual Consistency Check — Manual Mode")
    print("=" * 60)
    print()
    print(f"Character: {module.get('name', 'Unknown')} ({module.get('id', 'N/A')})")
    print(f"Visual Signature: {signature}")
    print()
    print("Anatomic Anchor (check these features on BOTH images):")
    print("-" * 60)

    features = [
        ("Face Shape", anatomic.get("face_shape", "N/A")),
        ("Eyes", anatomic.get("eyes", {}).get("shape", "N/A") + ", " + anatomic.get("eyes", {}).get("color", "N/A")),
        ("Nose", anatomic.get("nose", "N/A")),
        ("Lips", anatomic.get("lips", "N/A")),
        ("Jaw", anatomic.get("jaw", "N/A")),
        ("Skin", anatomic.get("skin_texture", "N/A")),
    ]

    for label, value in features:
        print(f"  [{label:12}] {value}")

    distinguishing = anatomic.get("distinguishing_features", [])
    if distinguishing:
        print()
        print("Distinguishing Features (CRITICAL — must match exactly):")
        for feat in distinguishing:
            print(f"  • {feat}")

    print()
    print("-" * 60)
    print(f"Reference Image: {reference_path}")
    print(f"New Image:       {new_image_path}")
    print()
    print("Manual Check Steps:")
    print("  1. Open both images side by side")
    print("  2. Compare face shape, eye shape/color, nose, lips, jaw")
    print("  3. Check distinguishing features (moles, scars, asymmetries)")
    print("  4. Check age indicators (wrinkles, skin texture)")
    print()
    print("Result Options:")
    print("  [pass]  — Face is consistent, minor variations acceptable (lighting, angle)")
    print("  [fail]  — Face is different, needs prompt correction")
    print("  [review] — Uncertain, needs second opinion")
    print()
    print("If [pass]: update generation_history with 'consistency_check': 'manual_pass'")
    print("If [fail]: adjust prompt — add 'same face', 'identical person', strengthen anatomic details")
    print()

def update_generation_history(module_id, new_image_path, result, notes=""):
    """Stub: would update JSON module with new generation entry."""
    print(f"[STUB] Would update {module_id} generation_history:")
    print(f"  result: {result}")
    print(f"  image: {new_image_path}")
    print(f"  notes: {notes}")
    print()
    print("[INFO] To implement auto-update, run:")
    print(f"  python update_generation_history.py {module_id} {result}")

def main():
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    character_id = sys.argv[1]
    new_image_path = Path(sys.argv[2])
    reference_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    if not new_image_path.exists():
        print(f"[ERROR] New image not found: {new_image_path}")
        sys.exit(1)

    module = load_character_module(character_id)
    ref = get_reference_image(module, reference_path)

    if not ref:
        print("[WARN] No reference image found. Using anatomic_anchor for manual check.")
        print("[INFO] Consider setting reference_image in module or providing explicit path.")
    else:
        print(f"[INFO] Reference image: {ref}")

    manual_check_guide(module, new_image_path, ref or "N/A")

    # Interactive result (stub)
    print("[STUB] Auto-check not implemented (requires CLIP/ResNet).")
    print("[STUB] Please perform manual check and provide result:")
    print()
    print("Run: python check_consistency.py KIRA_MODULE_v14 /path/to/new.png /path/to/ref.png")
    print("Then update generation_history manually or via future script.")

if __name__ == "__main__":
    main()
