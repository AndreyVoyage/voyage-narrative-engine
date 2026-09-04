#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core release metadata + the Core/Package/Runtime-data boundary.

Per OD-CHAR-CORE-RELEASE-01(A): Character Core and Character Package have
independent versions; Runtime/User data is separate from both. This module
gives that boundary a small, machine-readable, machine-TESTABLE shape:

- :class:`CoreReleaseInfo` -- what a Character Core release IS (name,
  independent version, contract version, recognized vs. currently supported
  session purposes, resolved capabilities);
- :data:`CHARACTER_CORE_RELEASE_BOUNDARY` -- what a Character Core release
  MAY vs. MUST NOT contain.

This is a classification/descriptor only -- NOT a build/package pipeline. No
physical release artifact is produced here.

Standard library only. Must not import ``services.character_lab`` or
``services.character_runtime``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .contract import SessionPurpose

__all__ = [
    "CORE_NAME",
    "CORE_VERSION",
    "CONTRACT_VERSION",
    "RELEASE_FORMAT_VERSION",
    "CoreReleaseInfo",
    "build_core_release_info",
    "ReleaseArtifactCategory",
    "ReleaseBoundary",
    "CHARACTER_CORE_RELEASE_BOUNDARY",
]

#: Pre-release boundary identity. Independent from any Character Package
#: version and from any runtime/user data. Do NOT call this 1.0 merely
#: because the boundary now exists -- there is no built/tested release yet.
CORE_NAME = "character-core"
CORE_VERSION = "0.1.0-dev"

#: Version of the CharacterService / CharacterDebugService contract SHAPE
#: (see ``contract.py``), independent from ``CORE_VERSION``.
CONTRACT_VERSION = "0.1.0-dev"

#: Version of the release-descriptor format itself (``CoreReleaseInfo`` /
#: ``ReleaseBoundary`` shape), independent from both of the above.
RELEASE_FORMAT_VERSION = "1"


@dataclass(frozen=True)
class CoreReleaseInfo:
    """Machine-readable Character Core release descriptor.

    ``source_commit`` is deliberately optional and is never hard-coded here:
    a real release/build step may materialize it later (e.g. from
    ``git rev-parse HEAD`` at build time); this pre-release boundary slice
    does not invent a future commit SHA.
    """

    core_name: str
    core_version: str
    contract_version: str
    release_format_version: str
    recognized_session_purposes: Tuple[str, ...]
    supported_session_purposes: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    source_commit: Optional[str] = None

    def __post_init__(self) -> None:
        unsupported = set(self.supported_session_purposes) - set(
            self.recognized_session_purposes
        )
        if unsupported:
            raise ValueError(
                f"supported_session_purposes contains unrecognized value(s): "
                f"{sorted(unsupported)}"
            )


def build_core_release_info(
    *,
    supported_session_purposes,
    capabilities,
    source_commit: Optional[str] = None,
) -> CoreReleaseInfo:
    """Build a :class:`CoreReleaseInfo` for the current adapter/release.

    ``recognized_session_purposes`` is always the FULL :class:`SessionPurpose`
    vocabulary; only ``supported_session_purposes`` varies per adapter -- the
    distinction between "recognized" and "currently supported" purposes is
    the whole point of this descriptor (Contract v1 supports only TESTING).
    """
    return CoreReleaseInfo(
        core_name=CORE_NAME,
        core_version=CORE_VERSION,
        contract_version=CONTRACT_VERSION,
        release_format_version=RELEASE_FORMAT_VERSION,
        recognized_session_purposes=tuple(p.value for p in SessionPurpose),
        supported_session_purposes=tuple(
            p.value if isinstance(p, SessionPurpose) else p
            for p in supported_session_purposes
        ),
        capabilities=tuple(capabilities),
        source_commit=source_commit,
    )


# --------------------------------------------------------------------------
# Explicit release-boundary classification (Core vs Package vs Runtime data)
# --------------------------------------------------------------------------


class ReleaseArtifactCategory(Enum):
    """What kind of thing a piece of Character Core project content is, for
    the sole purpose of classifying it in/out of a Character Core release."""

    # Eligible for a Character Core release.
    RUNTIME_MECHANISM = "RUNTIME_MECHANISM"
    SERVICE_CONTRACT = "SERVICE_CONTRACT"
    CONTEXT_POLICY_MECHANISM = "CONTEXT_POLICY_MECHANISM"
    RELEASE_METADATA = "RELEASE_METADATA"

    # NEVER eligible for a Character Core release.
    ACCEPTED_CHARACTER_PACKAGE = "ACCEPTED_CHARACTER_PACKAGE"
    RUNTIME_MEMORY_DB = "RUNTIME_MEMORY_DB"
    RUNTIME_STATE_DB = "RUNTIME_STATE_DB"
    WORKSPACE_DATA = "WORKSPACE_DATA"
    SESSION_DATA = "SESSION_DATA"
    SCENE_DATA = "SCENE_DATA"
    TURN_CAPTURE = "TURN_CAPTURE"
    USER_DATA = "USER_DATA"


@dataclass(frozen=True)
class ReleaseBoundary:
    """The Character Core release boundary: included vs. excluded artifact
    categories. Deliberately exhaustive -- an unclassified category is a
    fail-closed error, never silently treated as includable."""

    included: Tuple[ReleaseArtifactCategory, ...]
    excluded: Tuple[ReleaseArtifactCategory, ...]

    def eligible(self, category: ReleaseArtifactCategory) -> bool:
        if category in self.excluded:
            return False
        if category in self.included:
            return True
        raise ValueError(f"unclassified release artifact category: {category!r}")


CHARACTER_CORE_RELEASE_BOUNDARY = ReleaseBoundary(
    included=(
        ReleaseArtifactCategory.RUNTIME_MECHANISM,
        ReleaseArtifactCategory.SERVICE_CONTRACT,
        ReleaseArtifactCategory.CONTEXT_POLICY_MECHANISM,
        ReleaseArtifactCategory.RELEASE_METADATA,
    ),
    excluded=(
        ReleaseArtifactCategory.ACCEPTED_CHARACTER_PACKAGE,
        ReleaseArtifactCategory.RUNTIME_MEMORY_DB,
        ReleaseArtifactCategory.RUNTIME_STATE_DB,
        ReleaseArtifactCategory.WORKSPACE_DATA,
        ReleaseArtifactCategory.SESSION_DATA,
        ReleaseArtifactCategory.SCENE_DATA,
        ReleaseArtifactCategory.TURN_CAPTURE,
        ReleaseArtifactCategory.USER_DATA,
    ),
)
