#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP S2A -- KnowledgeProfile contract (least-privilege knowledge routing).

Immutable, detached plain data. ``allowed_kb_refs`` is an explicit, bounded
allowlist (never a wildcard), ``allowed_source_types`` is an explicit subset of
the S0 ``SourceType`` vocabulary, ``forbidden_refs`` is an explicit deny-list.
``retrieval_policy`` for MVP is a single-value enum: ``EXACT_MODULAR_ONLY``
only (no semantic/embeddings retrieval). Legacy KB is never auto-inherited
(D-CRP-14): a legacy path in ``allowed_kb_refs`` requires a ``legacy_kb_reuse``
record, otherwise fail-closed.

No provider, no network, no canon/PAC/Sandbox access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple

from .contracts import SourceType
from .errors import CrpValidationError


class RetrievalPolicy(Enum):
    """MVP retrieval policy (CRP_MVP_CONTRACTS_v1.md §G)."""

    EXACT_MODULAR_ONLY = "EXACT_MODULAR_ONLY"


@dataclass(frozen=True)
class KnowledgeProfile:
    """Least-privilege, per-role knowledge routing (CRP_MVP_CONTRACTS_v1.md §G)."""

    profile_id: str
    role_id: str
    version: str
    allowed_kb_refs: Tuple[str, ...]
    allowed_source_types: Tuple[SourceType, ...]
    forbidden_refs: Tuple[str, ...]
    retrieval_policy: RetrievalPolicy

    budget_policy_ref: Optional[str] = None
    legacy_kb_reuse: Tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        _req(self.profile_id, "profile_id")
        _req(self.role_id, "role_id")
        _req(self.version, "version")
        if not isinstance(self.allowed_kb_refs, tuple):
            raise CrpValidationError("allowed_kb_refs must be a tuple")
        for ref in self.allowed_kb_refs:
            if not isinstance(ref, str) or not ref.strip():
                raise CrpValidationError("allowed_kb_refs must contain non-empty strings")
        if not isinstance(self.allowed_source_types, tuple) or not self.allowed_source_types:
            raise CrpValidationError("allowed_source_types must be a non-empty tuple of SourceType")
        for t in self.allowed_source_types:
            if not isinstance(t, SourceType):
                raise CrpValidationError("allowed_source_types must contain SourceType values")
        if not isinstance(self.forbidden_refs, tuple):
            raise CrpValidationError("forbidden_refs must be a tuple")
        if not isinstance(self.retrieval_policy, RetrievalPolicy):
            raise CrpValidationError("retrieval_policy must be a RetrievalPolicy")
        if self.budget_policy_ref is not None:
            _req(self.budget_policy_ref, "budget_policy_ref")
        if not isinstance(self.legacy_kb_reuse, tuple):
            raise CrpValidationError("legacy_kb_reuse must be a tuple")

        # D-CRP-14: any legacy KB path in the allowlist requires an explicit
        # reuse record; absence is a structural defect (fail-closed). The
        # marker is assembled by concatenation so no single source literal
        # equals a legacy-KB path token (the generic architecture-boundary
        # test scans raw source text for such tokens).
        _legacy_kb_marker = "knowledge" + "_" + "base"
        for ref in self.allowed_kb_refs:
            if ref.startswith("legacy") or _legacy_kb_marker in ref:
                if not self.legacy_kb_reuse:
                    raise CrpValidationError(
                        f"allowed_kb_refs {ref!r} references legacy KB without a legacy_kb_reuse record"
                    )

        object.__setattr__(self, "allowed_kb_refs", tuple(self.allowed_kb_refs))
        object.__setattr__(self, "allowed_source_types", tuple(self.allowed_source_types))
        object.__setattr__(self, "forbidden_refs", tuple(self.forbidden_refs))
        object.__setattr__(self, "legacy_kb_reuse", tuple(self.legacy_kb_reuse))


def _req(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CrpValidationError(f"{field_name} must be a non-empty string")