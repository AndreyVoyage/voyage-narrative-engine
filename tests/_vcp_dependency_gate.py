"""Central pinned-VCP dependency identity gate for hard-gated publication tests.

Replaces the former silent ``pytest.importorskip("voyage_character_platform")``
with a HARD gate: a missing, miswired, wrong-origin or stale VCP dependency now
fails at collection instead of skipping.

The gate proves the identity chain:
    tracked provenance source_commit
      -> wheel_sha256
      -> installed distribution voyage-character-platform 0.1.0
      -> module resolved from the pinned Lab VCP env site-packages
      -> no live VCP source checkout, no ambient install, no stale wheel.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_PATH = LAB_ROOT / "build" / "provenance" / "vcp_shared_core_provenance.json"
OUTPUT_ROOT = LAB_ROOT / "build" / "output"

PINNED_SOURCE_COMMIT = "ccade9e0ef943f63fec703b7ed5b436d7520324a"
DEPENDENCY_NAME = "voyage-character-platform"
DEPENDENCY_VERSION = "0.1.0"
PROVENANCE_SCHEMA_VERSION = "vcp_shared_core_provenance/1.0"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PinnedVcpDependencyError(RuntimeError):
    """The imported VCP is missing, miswired, wrong-origin or stale."""


def _load_provenance() -> dict:
    if not PROVENANCE_PATH.is_file():
        raise PinnedVcpDependencyError(
            f"VCP provenance not found: {PROVENANCE_PATH}. "
            "Run build/scripts/build_vcp_shared_core.py first."
        )
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def _is_within(path: Path, root: Path) -> bool:
    path, root = path.resolve(), root.resolve()
    return path == root or root in path.parents


def pinned_vcp_identity() -> dict:
    """Return and verify the exact pinned dependency identity (raise on mismatch)."""
    provenance = _load_provenance()
    for key, expected in (
        ("schema_version", PROVENANCE_SCHEMA_VERSION),
        ("dependency_name", DEPENDENCY_NAME),
        ("dependency_version", DEPENDENCY_VERSION),
        ("source_repository", "voyage-character-platform"),
        ("source_commit", PINNED_SOURCE_COMMIT),
    ):
        if provenance.get(key) != expected:
            raise PinnedVcpDependencyError(
                f"Provenance {key} mismatch: expected {expected!r}, got {provenance.get(key)!r}"
            )
    wheel_sha256 = provenance.get("wheel_sha256")
    if not isinstance(wheel_sha256, str) or not _SHA256_RE.match(wheel_sha256):
        raise PinnedVcpDependencyError(f"Provenance wheel_sha256 malformed: {wheel_sha256!r}")
    wheel_filename = provenance.get("wheel_filename")
    if not isinstance(wheel_filename, str) or not wheel_filename.endswith(".whl"):
        raise PinnedVcpDependencyError(f"Provenance wheel_filename malformed: {wheel_filename!r}")

    import voyage_character_platform as vcp

    try:
        dist = importlib.metadata.distribution(DEPENDENCY_NAME)
    except importlib.metadata.PackageNotFoundError as exc:
        raise PinnedVcpDependencyError(
            f"Distribution {DEPENDENCY_NAME!r} is not installed"
        ) from exc

    if dist.metadata["Name"] != DEPENDENCY_NAME or dist.version != DEPENDENCY_VERSION:
        raise PinnedVcpDependencyError(
            f"Wrong distribution: {dist.metadata['Name']} {dist.version}"
        )

    module_file = Path(vcp.__file__).resolve()
    # Reject live VCP source checkout (sibling repo path carries the repo name).
    if "voyage-character-platform" in module_file.parts:
        raise PinnedVcpDependencyError(f"VCP imported from live source checkout: {module_file}")
    # Reject any import not resolved from a site-packages directory.
    if "site-packages" not in module_file.parts:
        raise PinnedVcpDependencyError(f"VCP imported from outside site-packages: {module_file}")
    # Reject an ambient / globally installed copy: the pinned VCP must live
    # under the gitignored generated area build/output/.
    if not _is_within(module_file, OUTPUT_ROOT):
        raise PinnedVcpDependencyError(f"VCP imported from outside build/output/: {module_file}")
    # Reject a stale/foreign wheel: installed archive hash must match provenance.
    direct_url = json.loads(dist.read_text("direct_url.json") or "{}")
    if direct_url.get("dir_info", {}).get("editable", False):
        raise PinnedVcpDependencyError("VCP installed editable from source")
    archive_hash = direct_url.get("archive_info", {}).get("hashes", {}).get("sha256")
    if archive_hash != wheel_sha256:
        raise PinnedVcpDependencyError(
            "Installed VCP wheel hash differs from provenance "
            f"(installed={archive_hash!r}, provenance={wheel_sha256!r})"
        )

    if not callable(getattr(vcp, "verify_package_v1", None)):
        raise PinnedVcpDependencyError("verify_package_v1 is not exposed by the installed VCP")

    return {
        "dependency_name": DEPENDENCY_NAME,
        "dependency_version": DEPENDENCY_VERSION,
        "source_commit": provenance["source_commit"],
        "wheel_filename": wheel_filename,
        "wheel_sha256": wheel_sha256,
        "module_file": module_file,
        "dist_name": dist.metadata["Name"],
        "dist_version": dist.version,
    }


def require_pinned_vcp() -> dict:
    """Hard gate: raise unless the pinned VCP is present and correctly wired.

    Returns the verified identity dict. Called at module level by every
    hard-gated publication test module so a missing/wrong/stale VCP fails at
    collection instead of silently skipping.
    """
    return pinned_vcp_identity()
