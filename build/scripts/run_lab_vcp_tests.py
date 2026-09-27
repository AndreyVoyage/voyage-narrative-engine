"""Run the hard-gated VCP publication tests against the pinned Lab VCP env.

Offline. Uses the base interpreter's pytest (the only offline pytest available
in this environment) while forcing ``voyage_character_platform`` to resolve from
the pinned Lab VCP env's site-packages. This is NOT ambient PYTHONPATH: the
pinned site-packages directory is inserted at the front of ``sys.path``
programmatically after the wheel is hash-verified against the tracked
provenance, and every hard-gated test module enforces the identity gate
(module origin, distribution name/version, wheel hash vs provenance), so a live
source checkout, an ambient install or a stale wheel fails closed.

The base interpreter must remain free of a global VCP install: this runner
refuses to run if ``voyage_character_platform`` is already resolvable from
outside the pinned env.

USAGE (from the Lab repository root):
  py build/scripts/run_lab_vcp_tests.py ^
      tests/character_publication ^
      tests/character_lab_application/test_native_release_e2e.py ^
      tests/character_lab_application/test_release_publication_facade.py ^
      tests/ui/character_lab/test_native_authoring_e2e.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_PATH = LAB_ROOT / "build" / "provenance" / "vcp_shared_core_provenance.json"
LAB_VCP_ENV_SITE = LAB_ROOT / "build" / "output" / "lab_vcp_env" / "Lib" / "site-packages"
WHEEL_PATH = LAB_ROOT / "build" / "output" / "vcp_shared_core" / (
    "voyage_character_platform-0.1.0-py3-none-any.whl"
)


def _fail(message: str) -> "None":
    sys.exit(f"RUN LAB VCP TESTS FAILED (fail closed): {message}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _enforce_prequisites() -> dict:
    if not PROVENANCE_PATH.is_file():
        _fail(f"VCP provenance not found: {PROVENANCE_PATH}. "
              "Run build/scripts/build_vcp_shared_core.py first.")
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    if provenance.get("source_commit") != "ccade9e0ef943f63fec703b7ed5b436d7520324a":
        _fail(f"Provenance source_commit mismatch: {provenance.get('source_commit')!r}")

    # The base interpreter must NOT already resolve VCP from anywhere else.
    spec = importlib.util.find_spec("voyage_character_platform")
    if spec is not None and spec.origin is not None:
        origin = Path(spec.origin).resolve()
        env_site_resolved = LAB_VCP_ENV_SITE.resolve()
        if not (origin == env_site_resolved or env_site_resolved in origin.parents):
            _fail(f"Base interpreter already resolves VCP outside the pinned env: {origin}")

    if not (LAB_VCP_ENV_SITE / "voyage_character_platform").is_dir():
        _fail(f"Lab VCP env not bootstrapped: {LAB_VCP_ENV_SITE}. "
              "Run build/scripts/bootstrap_lab_vcp_env.py first.")

    if not WHEEL_PATH.is_file():
        _fail(f"Pinned VCP wheel missing: {WHEEL_PATH}")
    actual = _sha256_file(WHEEL_PATH)
    if actual != provenance.get("wheel_sha256"):
        _fail(f"Wheel SHA-256 mismatch: {actual} != {provenance.get('wheel_sha256')}")

    # Scrub ambient PYTHONPATH for the test process (no env-var authority).
    for name in ("PYTHONPATH", "PYTHONHOME"):
        os.environ.pop(name, None)

    return provenance


def main(argv=None) -> int:
    provenance = _enforce_prequisites()

    # Force the pinned env's site-packages to be the VCP import authority.
    sys.path.insert(0, str(LAB_VCP_ENV_SITE.resolve()))

    print("=" * 70)
    print("LAB VCP PUBLICATION TESTS (pinned dependency)")
    print(f"Source commit:  {provenance['source_commit']}")
    print(f"Wheel SHA-256:  {provenance['wheel_sha256']}")
    print(f"VCP authority:  {LAB_VCP_ENV_SITE}")
    print("Network:        DISABLED")
    print("=" * 70)
    print()

    import pytest

    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        args = [
            "tests/character_publication",
            "tests/character_lab_application/test_native_release_e2e.py",
            "tests/character_lab_application/test_release_publication_facade.py",
            "tests/ui/character_lab/test_native_authoring_e2e.py",
        ]
    return pytest.main(args)


if __name__ == "__main__":
    sys.exit(main())
