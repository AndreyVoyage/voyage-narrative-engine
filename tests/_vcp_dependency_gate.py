"""Central pinned-VCP dependency identity gate for hard-gated publication tests.

Replaces the former silent ``pytest.importorskip("voyage_character_platform")``
with a HARD gate: a missing, miswired, wrong-origin or stale VCP dependency now
fails at collection instead of skipping.

This is now a thin shim delegating to the production-safe gate in
``services.character_lab_application.runtime_environment``, so the exact
pin/origin verification logic has a single source of truth shared by both the
test suite and the desktop application runtime.
"""

from __future__ import annotations

from services.character_lab_application.runtime_environment import (
    PinnedVcpDependencyError,
    pinned_vcp_identity,
)

__all__ = ["PinnedVcpDependencyError", "pinned_vcp_identity", "require_pinned_vcp"]


def require_pinned_vcp() -> dict:
    """Hard gate: raise unless the pinned VCP is present and correctly wired.

    Returns the verified identity dict. Called at module level by every
    hard-gated publication test module so a missing/wrong/stale VCP fails at
    collection instead of silently skipping.
    """
    return pinned_vcp_identity()
