#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 0 package.

Slice 0 scope only: internal pilot data contracts, read-only provenance
utilities, and a read-only source loader for the frozen P0/P3/P4/ME-1/ME-2/
baseline snapshot (per ``CIS_KIRA_PILOT_SPECIFICATION_v0.1_2026-08-05.md``
and ``CIS_KIRA_PILOT_IMPLEMENTATION_PLAN_2026-08-06.md`` Slice 0). No
context assembly, no gates, no provider calls, no CLI, and no runtime
output belong here -- those are later slices, not yet authorized.

Importing this package performs no I/O, no Git calls, and loads no source
data; it only exposes names.
"""

from __future__ import annotations

from .contracts import (
    ALLOWED_P4_STATES,
    BaselineSourceSet,
    ContractValidationError,
    MemoryEventSource,
    P0Snapshot,
    P3State,
    P4State,
    PilotSourceSnapshot,
    SourceArtifact,
)
from .provenance import ProvenanceError
from .source_loader import CHARACTER_ID, SourceLoaderError, load_pilot_source_snapshot

__all__ = [
    "ALLOWED_P4_STATES",
    "BaselineSourceSet",
    "CHARACTER_ID",
    "ContractValidationError",
    "MemoryEventSource",
    "P0Snapshot",
    "P3State",
    "P4State",
    "PilotSourceSnapshot",
    "ProvenanceError",
    "SourceArtifact",
    "SourceLoaderError",
    "load_pilot_source_snapshot",
]
