"""
Standalone smoke-check for the VNE → RenPy preview exporter.

Runs the exporter CLI against SC_003–013 and validates each output.

Usage (from repo root):
    python scripts/python/check_renpy_exporter.py [--output-dir reports/renpy]

Exit code 0 = all pass, non-zero = one or more failures.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCENARIOS = [
    "SCENARIO_003_GYM_NIGHT.json",
    "SCENARIO_004_GYM_STRETCH.json",
    "SCENARIO_005_GYM_SQUAT.json",
    "SCENARIO_006_GYM_PEAK.json",
    "SCENARIO_007_GYM_AFTERCARE.json",
    "SCENARIO_008_HOME_EMBRACE.json",
    "SCENARIO_009_HOME_MORNING.json",
    "SCENARIO_010_HOME_NIGHT.json",
    "SCENARIO_011_HOME_MORNING2.json",
    "SCENARIO_012_HOME_KITCHEN.json",
    "SCENARIO_013_HOME_MESSAGE.json",
]

REQUIRED_TOKENS = [
    "define narrator = Character(None)",
    "label start:",
    "menu:",
    "label scene_end:",
    "return",
]

BAD_DIALOGUE = ['kira "', 'sergey "', 'yakov "']

SC003_EXTRA = [
    'define kira = Character("Кира")',
    'define sergey = Character("Сергей")',
    "Зал",
    "Ночь",
    "label branch_1a:",
    "label branch_1b:",
    "label branch_1c:",
]


def _scenario_id(filename: str) -> str | None:
    m = re.match(r"SCENARIO_(\d{3})_", filename)
    return f"SC_{m.group(1)}" if m else None


def check_output(path: Path, sc_id: str) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        raw = path.read_bytes()
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"read error: {exc}"]

    if raw.startswith(b"\xef\xbb\xbf"):
        failures.append("BOM detected")
    if b"\r\n" in raw:
        failures.append("CRLF line endings detected")

    missing = [t for t in REQUIRED_TOKENS if t not in text]
    if missing:
        failures.append(f"missing tokens: {missing}")

    bad = [d for d in BAD_DIALOGUE if d in text]
    if bad:
        failures.append(f"reaction prose emitted as character dialogue: {bad}")

    if sc_id == "SC_003":
        missing_extra = [t for t in SC003_EXTRA if t not in text]
        if missing_extra:
            failures.append(f"SC_003 extra tokens missing: {missing_extra}")

    return failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-check VNE → RenPy exporter against SC_003–013."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/renpy"),
        help="Directory for generated .rpy previews (default: reports/renpy)",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    exporter = REPO_ROOT / "tools" / "vne_to_renpy" / "exporter.py"
    scenarios_dir = REPO_ROOT / "scenarios"

    print("=== RenPy Exporter Smoke Check ===")

    passed = 0
    failed = 0

    for name in SCENARIOS:
        sc_id = _scenario_id(name)
        if sc_id is None:
            print(f"SKIP {name}  (could not extract scenario ID)")
            failed += 1
            continue

        src = scenarios_dir / name
        out = output_dir / f"{sc_id}.rpy"

        result = subprocess.run(
            [sys.executable, str(exporter), str(src), "--output", str(out)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"{sc_id} FAIL  export failed (exit {result.returncode})")
            if result.stderr.strip():
                print(f"  stderr: {result.stderr.strip()}")
            failed += 1
            continue

        failures = check_output(out, sc_id)
        if failures:
            print(f"{sc_id} FAIL  {'; '.join(failures)}")
            failed += 1
        else:
            rel = out.relative_to(REPO_ROOT) if out.is_absolute() else out
            print(f"{sc_id} PASS  {rel}")
            passed += 1

    print(f"\nSummary: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
