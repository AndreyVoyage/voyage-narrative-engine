#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 1 static baseline (control-arm) adapter.

Thin wrapper around ``tools.aside_context_builder.build_context()``,
called completely unmodified, to satisfy PD-10 (the frozen 4-module
static baseline: ``core/IDENTITY.json`` + ``psychology/BASE.json`` +
``speech/SPEECH_MATRIX.json`` + ``relationships/MATRIX.json``). Adds no
logic beyond forwarding its arguments -- output is byte-identical to
calling ``build_context()`` directly with the same arguments.

This module never imports ``context_assembler.py`` and never accepts a
P3State/P4State parameter: the baseline arm is P3/P4-blind by
construction (``build_context()`` reads ``relationships/MATRIX.json``
directly from disk on every call and has no state-injection parameter at
all). This physical non-convergence with the CIS arm is the causal
control required by spec §16.
"""

from __future__ import annotations

from typing import Any, Optional

from tools import aside_context_builder

# Fixed pilot character id (spec PD-1), duplicated here as a local literal
# rather than imported from tools/cis_pilot/source_loader.py -- this
# module's only Slice 1 dependency is tools.aside_context_builder (plan
# §14), kept independent of the source-loading code path.
_CHARACTER_ID = "kira"


def build_baseline_messages(
    canon_snapshot: dict[str, Any],
    aside_memory: Optional[dict[str, Any]],
    player_message: str,
    *,
    character_id: str = _CHARACTER_ID,
) -> list[dict[str, str]]:
    """Build baseline control-arm messages.

    Forwards its arguments to ``aside_context_builder.build_context()``
    unmodified -- this function adds no logic of its own. Output is
    byte-identical to calling ``build_context()`` directly with the same
    arguments.
    """
    return aside_context_builder.build_context(
        character_id, canon_snapshot, aside_memory, player_message
    )
