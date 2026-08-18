#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP-facing provider adapter (outer boundary, NOT under services/crp_authoring/).

Translates a validated ``ProviderConfig`` into a plain
``Callable[[list], str]`` matching ``executor.ProviderCallable`` exactly, by
delegating to the generic OpenAI-compatible transport in ``tools.llm_provider``.

``services/crp_authoring/`` never imports this module -- the architecture-boundary
test forbids any provider import under that tree. The future CLI/orchestrator
wires ``execute_role_task(provider_callable=...)``; the adapter lives here, next
to ``llm_provider.py``, outside the CRP domain for exactly that reason.

No retry, no fallback provider/model, no secret value is ever stored.
``credential_env`` holds only an environment-variable NAME; the value is read
once, at call time, inside ``llm_provider._complete_cloud`` (fail-closed when
absent/empty).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping

from llm_provider import complete


# Structural/transport/security controls that ``extra_params`` must never
# override. Overriding any of these would bypass the validated ProviderConfig
# or the transport's own control plane.
_RESERVED_PARAM_KEYS = frozenset({
    "base_url",
    "credential_env",
    "timeout_s",
    "api_key",
    "messages",
    "model",
})


class ProviderConfigError(ValueError):
    """Fail-closed provider-config validation error."""


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable provider configuration. Holds no secret value.

    ``credential_env`` is the NAME of the environment variable that holds the
    credential. ``extra_params`` is frozen to a read-only mapping on
    construction.
    """

    provider_id: str
    model: str
    base_url: str
    credential_env: str
    timeout_s: float
    max_tokens: int
    json_mode: bool = False
    extra_params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.provider_id, "provider_id")
        _require_non_empty(self.model, "model")
        _require_non_empty(self.base_url, "base_url")
        _require_non_empty(self.credential_env, "credential_env")

        if isinstance(self.timeout_s, bool) or not isinstance(self.timeout_s, (int, float)):
            raise ProviderConfigError("timeout_s must be a number")
        if self.timeout_s <= 0:
            raise ProviderConfigError("timeout_s must be greater than zero")

        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int):
            raise ProviderConfigError("max_tokens must be an int")
        if self.max_tokens <= 0:
            raise ProviderConfigError("max_tokens must be greater than zero")

        if not isinstance(self.json_mode, bool):
            raise ProviderConfigError("json_mode must be a bool")

        if not isinstance(self.extra_params, Mapping):
            raise ProviderConfigError("extra_params must be a mapping")
        for key in self.extra_params:
            if key in _RESERVED_PARAM_KEYS:
                raise ProviderConfigError(
                    f"extra_params must not override reserved key {key!r}"
                )

        object.__setattr__(self, "extra_params", MappingProxyType(dict(self.extra_params)))


def build_provider_callable(config: ProviderConfig) -> Callable[[list], str]:
    """Return a ``Callable[[list], str]`` matching ``executor.ProviderCallable``.

    The returned callable is a one-shot provider invocation: no retry, no
    fallback, no provider/model substitution. It returns exactly the plain
    assistant text from the underlying OpenAI-compatible transport.
    """
    if not isinstance(config, ProviderConfig):
        raise TypeError("config must be a ProviderConfig instance")

    def provider_callable(messages: list) -> str:
        params: dict[str, Any] = {
            "base_url": config.base_url,
            "credential_env": config.credential_env,
            "timeout_s": config.timeout_s,
            "max_tokens": config.max_tokens,
        }
        for key, value in config.extra_params.items():
            params[key] = value
        if config.json_mode:
            # OpenAI-compatible JSON-mode request. Provider-facing only; does
            # not touch RoleResult/RoleClaim schema shape.
            params["response_format"] = {"type": "json_object"}

        return complete(
            messages,
            provider="cloud",
            model=config.model,
            params=params,
        )

    return provider_callable


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProviderConfigError(f"{field_name} must be a non-empty string")