#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- Slice 4 provider boundary (mock/deterministic only).

Thin, pilot-scoped wrapper over the existing, unmodified
``tools.llm_provider.complete()`` (plan §4/§5 ``provider_boundary.py``,
spec §5.10). Slice 4 is strictly OFFLINE: the only supported provider is
``"mock"`` -- the deterministic, network-free provider already shipped in
``tools/llm_provider.py``. Any other provider name (real cloud vendors,
local endpoints, or any future name) fails CLOSED at construction with
``ProviderBoundaryError``; there is no fallback to a real provider anywhere
in this module (TD-14; real provider use is deferred to Slice 6 under a
separate owner authorization, TD-1).

The boundary fixes provider/model/params for one run (frozen
``ProviderConfig`` -- no silent per-call drift) and exposes the exact
triple for the provenance manifest (plan §12).

It also provides the two Slice 4 DI adapters that bind the mock provider
to the existing Slice 2 injection points in ``memory_gate.py``
(``InterpretationProposalFn`` / ``GistProposalFn``). The adapters parse the
deterministic mock completion into the structured S2 contract types; given
the mock provider's determinism, identical inputs always produce identical
structured outputs.

This module performs no network I/O of its own, reads no environment
variables, imports no SDK, and writes nothing. Importing it has no side
effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from tools import llm_provider

from .contracts import ContractValidationError
from .memory_gate import (
    CharacterInterpretation,
    CharacterPerception,
    GistProposalFn,
    InterpretationProposalFn,
    WorldEvent,
)

# The only provider Slice 4 is authorized to use (TD-14: mock/deterministic
# only; unsupported provider => fail closed, never a fallback).
SUPPORTED_PROVIDER = "mock"

# Fixed model identifier recorded for provenance when the mock provider is
# used. The mock provider is model-agnostic (its digest payload uses "mock"
# when no model is given); pinning this string keeps the manifest honest
# about what actually produced the generations.
MOCK_MODEL_ID = "mock-deterministic"


class ProviderBoundaryError(RuntimeError):
    """Fail-closed error for any unsupported (non-mock) provider request or
    structurally invalid boundary input. There is deliberately NO fallback
    path to a real provider: network-capable providers are out of Slice 4
    scope entirely (TD-1/TD-14)."""


@dataclass(frozen=True)
class ProviderConfig:
    """The fixed provider/model/params triple for one run (plan §12).

    Frozen at construction and immutable afterwards: every completion in a
    run uses exactly this triple, and the same triple is recorded verbatim
    in the provenance manifest. ``params`` is normalized to an immutable
    mapping in ``__post_init__``.
    """

    provider: str
    model: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ContractValidationError("provider must be a non-empty string")
        if self.provider.strip().lower() != SUPPORTED_PROVIDER:
            raise ProviderBoundaryError(
                f"provider {self.provider!r} is not supported in Slice 4: only "
                f"{SUPPORTED_PROVIDER!r} (deterministic, offline) is authorized; "
                "real/local/cloud providers require separate owner authorization "
                "(Slice 6, TD-1) -- failing closed, no fallback"
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise ContractValidationError("model must be a non-empty string")
        if not isinstance(self.params, Mapping):
            raise ContractValidationError("params must be a mapping")
        for key in self.params:
            if not isinstance(key, str):
                raise ContractValidationError("params keys must be strings")
        object.__setattr__(self, "provider", self.provider.strip().lower())
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    def provenance_metadata(self) -> dict[str, Any]:
        """The exact provider/model/params triple, as a plain JSON-ready
        dict (params sorted by key for deterministic serialization)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "params": {key: self.params[key] for key in sorted(self.params)},
        }


class PilotProviderBoundary:
    """One run's fixed binding to the deterministic mock provider.

    Construction validates and freezes the ``ProviderConfig``; ``complete``
    forwards to ``tools.llm_provider.complete()`` unmodified with exactly
    the frozen triple. No other provider can ever be reached through this
    class: the config constructor fails closed before any call is made.
    """

    def __init__(
        self,
        *,
        provider: str = SUPPORTED_PROVIDER,
        model: str = MOCK_MODEL_ID,
        params: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._config = ProviderConfig(
            provider=provider, model=model, params=dict(params or {})
        )

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def provenance_metadata(self) -> dict[str, Any]:
        """Provider/model/params exactly as used for every call this run."""
        return self._config.provenance_metadata()

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return one deterministic mock completion for ``messages``.

        Delegates to the existing, unmodified ``tools.llm_provider.complete``
        with the frozen provider/model/params. The mock provider is offline
        and deterministic (SHA-256-digest stub output): identical messages
        always yield identical completions.
        """
        return llm_provider.complete(
            messages,
            provider=self._config.provider,
            model=self._config.model,
            params=dict(self._config.params),
        )


def default_boundary() -> PilotProviderBoundary:
    """The standard Slice 4 boundary: mock provider, fixed model, no params."""
    return PilotProviderBoundary()


# ---------------------------------------------------------------------------
# Slice 2 DI adapters (InterpretationProposalFn / GistProposalFn)
# ---------------------------------------------------------------------------
#
# The mock completion has the stable shape::
#
#     [MOCK] (<role>) <truncated prompt snippet> :: <10-char sha256 digest>
#
# The adapters extract the trailing digest (deterministic per input) and
# build the structured Slice 2 contract values from it. The digest-derived
# payload can never equal the Russian objective event text, so the CIS-Q6
# "event text != memory gist" invariant is preserved by construction; the
# S2 gate re-validates it anyway (fail closed).


def _mock_completion_digest(completion: str) -> str:
    """Extract the trailing deterministic digest from a mock completion.

    Fail closed on an unexpected shape -- the boundary never guesses."""
    if not isinstance(completion, str) or not completion.strip():
        raise ProviderBoundaryError("mock completion must be a non-empty string")
    head, sep, tail = completion.rpartition(" :: ")
    if not sep or not head.startswith("[MOCK]") or not tail.strip():
        raise ProviderBoundaryError(
            f"unexpected mock completion shape (expected '[MOCK] ... :: <digest>'): "
            f"{completion[:80]!r}"
        )
    return tail.strip()


def make_interpretation_proposal_fn(
    boundary: PilotProviderBoundary,
) -> InterpretationProposalFn:
    """Build a ``memory_gate.InterpretationProposalFn`` backed by the mock
    provider (deterministic).

    The returned callable renders the (WorldEvent, CharacterPerception) pair
    into a provider message, completes it through ``boundary``, and parses
    the deterministic mock completion into a ``CharacterInterpretation``
    tagged ``belief`` (never ``fact``). Linkage fields (``character_id``,
    ``world_event_id``) are taken from the inputs, never from the
    completion, so the S2 layer-linkage invariants hold structurally.
    """
    if not isinstance(boundary, PilotProviderBoundary):
        raise ProviderBoundaryError("boundary must be a PilotProviderBoundary instance")

    def propose(world_event: WorldEvent, perception: CharacterPerception) -> CharacterInterpretation:
        if not isinstance(world_event, WorldEvent):
            raise ProviderBoundaryError("world_event must be a WorldEvent instance")
        if not isinstance(perception, CharacterPerception):
            raise ProviderBoundaryError("perception must be a CharacterPerception instance")
        prompt = (
            "interpretation-proposal\n"
            f"event_id: {world_event.event_id}\n"
            f"objective: {world_event.objective_text}\n"
            f"noticed: {perception.noticed}"
        )
        completion = boundary.complete([{"role": "user", "content": prompt}])
        digest = _mock_completion_digest(completion)
        return CharacterInterpretation(
            character_id=perception.character_id,
            world_event_id=world_event.event_id,
            meaning=f"mock-interpretation:{digest}",
            emotional_coloring=f"mock-coloring:{digest}",
        )

    return propose


def make_gist_proposal_fn(boundary: PilotProviderBoundary) -> GistProposalFn:
    """Build a ``memory_gate.GistProposalFn`` backed by the mock provider
    (deterministic).

    The returned callable renders the full three-layer input into a provider
    message, completes it through ``boundary``, and parses the deterministic
    mock completion into a gist string. The gist is digest-derived and can
    therefore never equal the objective event text (CIS-Q6).
    """
    if not isinstance(boundary, PilotProviderBoundary):
        raise ProviderBoundaryError("boundary must be a PilotProviderBoundary instance")

    def propose(
        world_event: WorldEvent,
        perception: CharacterPerception,
        interpretation: CharacterInterpretation,
    ) -> str:
        if not isinstance(interpretation, CharacterInterpretation):
            raise ProviderBoundaryError(
                "interpretation must be a CharacterInterpretation instance"
            )
        prompt = (
            "gist-proposal\n"
            f"event_id: {world_event.event_id}\n"
            f"objective: {world_event.objective_text}\n"
            f"noticed: {perception.noticed}\n"
            f"meaning: {interpretation.meaning}"
        )
        completion = boundary.complete([{"role": "user", "content": prompt}])
        return f"mock-gist:{_mock_completion_digest(completion)}"

    return propose
