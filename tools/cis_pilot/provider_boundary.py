#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CIS Kira Pilot -- provider boundary (mock + approved DeepSeek real path).

Thin, pilot-scoped wrapper over the existing, unmodified
``tools.llm_provider.complete()`` (plan §4/§5 ``provider_boundary.py``,
spec §5.10). Two provider modes are supported, and only these two:

* ``"mock"`` -- the deterministic, network-free provider already shipped in
  ``tools/llm_provider.py`` (unchanged Slice 4 behavior).
* ``"cloud"`` -- the approved DeepSeek Official API real path (TD-16 narrow
  code-freeze exception), reached through the existing cloud
  chat-completions side of ``tools.llm_provider.complete()`` with the model
  hard-gated to ``deepseek-v4-pro`` and the base URL bound to
  ``https://api.deepseek.com``.

Any other provider name, any other real model, or any other endpoint fails
CLOSED at construction with ``ProviderBoundaryError``. There is no fallback
between providers, models, or endpoints anywhere in this module.

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

# Default provider: the deterministic offline mock (existing Slice 4
# behavior, preserved unchanged as the default). TD-16 adds one approved
# real path below; no other provider token is ever forwarded.
SUPPORTED_PROVIDER = "mock"

# TD-16 narrow code-freeze exception: the approved real provider is
# DeepSeek Official API, reached through the existing "cloud" token of
# tools.llm_provider.complete() (chat-completions compatible). Model and
# endpoint are hard-gated below; nothing else is authorized.
DEEPSEEK_REAL_PROVIDER = "cloud"
DEEPSEEK_MODEL_ID = "deepseek-v4-pro"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# TD-22A: transport-only timeout for the approved DeepSeek real path (seconds).
# This is consumed by tools.llm_provider as the HTTP timeout and is NOT
# serialized into the outbound request body. No other timeout is authorized.
DEEPSEEK_TIMEOUT_S = 120.0

# The complete set of provider tokens this boundary will ever forward to
# tools.llm_provider.complete(). Anything else fails closed at construction.
_SUPPORTED_PROVIDER_TOKENS = frozenset({SUPPORTED_PROVIDER, DEEPSEEK_REAL_PROVIDER})

# Fixed model identifier recorded for provenance when the mock provider is
# used. The mock provider is model-agnostic (its digest payload uses "mock"
# when no model is given); pinning this string keeps the manifest honest
# about what actually produced the generations.
MOCK_MODEL_ID = "mock-deterministic"


class ProviderBoundaryError(RuntimeError):
    """Fail-closed error for any unsupported provider, unauthorized model or
    endpoint, or structurally invalid boundary input. There is deliberately
    NO fallback between providers, models, or endpoints: a real provider
    must be requested explicitly via the approved DeepSeek path and fails
    closed on any mismatch (TD-1/TD-16)."""


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
        normalized_provider = self.provider.strip().lower()
        if normalized_provider not in _SUPPORTED_PROVIDER_TOKENS:
            raise ProviderBoundaryError(
                f"provider {self.provider!r} is not supported: only "
                f"{sorted(_SUPPORTED_PROVIDER_TOKENS)} are authorized "
                "(mock = deterministic offline stub; cloud = approved "
                "DeepSeek real path); any other provider -- and any "
                "fallback between providers -- fails closed"
            )
        if not isinstance(self.model, str) or not self.model.strip():
            raise ContractValidationError("model must be a non-empty string")
        if not isinstance(self.params, Mapping):
            raise ContractValidationError("params must be a mapping")
        for key in self.params:
            if not isinstance(key, str):
                raise ContractValidationError("params keys must be strings")

        params = dict(self.params)
        model = self.model.strip()

        if normalized_provider == DEEPSEEK_REAL_PROVIDER:
            # Approved real path (TD-16): model hard-gated to
            # deepseek-v4-pro and endpoint bound to https://api.deepseek.com.
            # Any other model or endpoint fails closed; there is no fallback
            # to another model, provider, or endpoint.
            if model != DEEPSEEK_MODEL_ID:
                raise ProviderBoundaryError(
                    f"model {model!r} is not authorized on the approved "
                    f"real provider path: only {DEEPSEEK_MODEL_ID!r} is "
                    "allowed -- failing closed, no fallback"
                )
            if "base_url" in params:
                requested = str(params["base_url"]).rstrip("/")
                if requested != DEEPSEEK_BASE_URL.rstrip("/"):
                    raise ProviderBoundaryError(
                        f"base_url {str(params['base_url'])!r} is not the "
                        f"approved DeepSeek endpoint {DEEPSEEK_BASE_URL!r} "
                        "-- failing closed, no fallback"
                    )
            params["base_url"] = DEEPSEEK_BASE_URL

            # TD-22A: the approved real path carries a fixed transport timeout.
            # A caller may omit it (default applied) or pass exactly the
            # approved value; anything else fails closed. This is NOT the
            # generic timeout acceptance -- only 120.0 is authorized here.
            if "timeout_s" in params:
                try:
                    requested_timeout = float(params["timeout_s"])
                except (TypeError, ValueError):
                    requested_timeout = None
                if requested_timeout != DEEPSEEK_TIMEOUT_S:
                    raise ProviderBoundaryError(
                        f"timeout_s {params['timeout_s']!r} is not the approved "
                        f"DeepSeek timeout {DEEPSEEK_TIMEOUT_S!r} "
                        "-- failing closed, no fallback"
                    )
            params["timeout_s"] = DEEPSEEK_TIMEOUT_S

        object.__setattr__(self, "provider", normalized_provider)
        object.__setattr__(self, "params", MappingProxyType(params))

    def provenance_metadata(self) -> dict[str, Any]:
        """The exact provider/model/params triple, as a plain JSON-ready
        dict (params sorted by key for deterministic serialization)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "params": {key: self.params[key] for key in sorted(self.params)},
        }


class PilotProviderBoundary:
    """One run's fixed binding to its provider (mock or approved DeepSeek).

    Construction validates and freezes the ``ProviderConfig``; ``complete``
    forwards to ``tools.llm_provider.complete()`` unmodified with exactly
    the frozen provider/model/params triple. For the approved DeepSeek real
    path this is provider ``"cloud"`` with model ``deepseek-v4-pro`` and the
    base URL bound to ``https://api.deepseek.com``. No other provider, model,
    or endpoint can ever be reached through this class: the config
    constructor fails closed before any call is made.
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
        """Return one provider completion string for ``messages``.

        Delegates to the existing, unmodified ``tools.llm_provider.complete``
        with the frozen provider/model/params. For ``mock`` this is offline
        and deterministic (SHA-256-digest stub output): identical messages
        always yield identical completions. For the approved DeepSeek real
        path this forwards to the existing cloud chat-completions
        implementation with model ``deepseek-v4-pro`` and base URL
        ``https://api.deepseek.com``. Provider/network errors propagate
        unchanged (fail closed -- never a fallback to mock or another
        provider).
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
