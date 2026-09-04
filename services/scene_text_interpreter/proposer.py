#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scene Text Interpreter v0 -- provider-neutral proposer boundary.

The proposer is the semantic component. The domain contract here is
provider-neutral: it is NOT bound to DeepSeek / OpenAI / Claude / Anthropic.
A real LLM adapter is a SEPARATE authorization; it must implement
``SceneTextProposer`` and nothing downstream changes.

This build ships only offline proposers:

- ``MockProposer``    -- returns a pre-built ``ProposedInterpretation`` verbatim
                         (tests inject good and hallucinated proposals).
- ``FixtureProposer`` -- replays a recorded proposal JSON file. It performs NO
                         network I/O and NO reasoning; it only deserializes a
                         previously captured proposal so the offline CLI proof
                         exercises the real trust boundary
                         (proposal -> deterministic validation -> plan).

No stdlib network module is imported anywhere in this package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from .errors import ProposalSchemaError
from .model import ProposedInterpretation, InterpreterInput


@runtime_checkable
class SceneTextProposer(Protocol):
    """Provider-neutral proposer contract.

    ``provider`` / ``model`` / ``mock`` are recorded verbatim into the plan's
    ``interpreter`` provenance block (non-secret metadata only).
    """

    provider: str
    model: str
    mock: bool

    def propose(self, request: InterpreterInput) -> ProposedInterpretation: ...


class MockProposer:
    """Deterministic in-memory proposer: returns a fixed proposal."""

    def __init__(
        self,
        proposal: ProposedInterpretation,
        *,
        provider: str = "mock",
        model: str = "mock",
    ) -> None:
        if not isinstance(proposal, ProposedInterpretation):
            raise TypeError("proposal must be a ProposedInterpretation")
        self._proposal = proposal
        self.provider = provider
        self.model = model
        self.mock = True

    def propose(self, request: InterpreterInput) -> ProposedInterpretation:  # noqa: ARG002
        return self._proposal


class FixtureProposer:
    """Replay a recorded proposal JSON file (offline stand-in for an LLM).

    Expected file shape::

        {
          "interpreter": {"provider": "...", "model": "...", "mock": true},
          "proposal": { ... ProposedInterpretation.from_dict shape ... }
        }
    """

    def __init__(self, fixture_path: Path) -> None:
        path = Path(fixture_path)
        if not path.exists():
            raise ProposalSchemaError(f"proposal fixture not found: {path}")
        try:
            data: Any = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - fail closed with a clean message
            raise ProposalSchemaError(f"invalid proposal fixture JSON: {exc}") from exc
        if not isinstance(data, Mapping) or "proposal" not in data:
            raise ProposalSchemaError(
                "proposal fixture must be an object with a 'proposal' key"
            )
        meta = data.get("interpreter") or {}
        if not isinstance(meta, Mapping):
            raise ProposalSchemaError("proposal fixture 'interpreter' must be an object")
        self._proposal = ProposedInterpretation.from_dict(data["proposal"])
        self.provider = str(meta.get("provider", "fixture"))
        self.model = str(meta.get("model", "replay"))
        self.mock = bool(meta.get("mock", True))

    def propose(self, request: InterpreterInput) -> ProposedInterpretation:  # noqa: ARG002
        return self._proposal
