#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thin Character Lab runtime-service boundary (Slice 1).

Composes the existing Character Runtime, acceptance gate, RuntimeMemoryBackend,
and an injected provider callable without reimplementing them. Provides:

- ``resolve(...)`` -> read-only ``LoadedState``;
- ``turn(...)`` -> structured ``TurnResult``.

No HTTP server, no UI, no acceptance mutation, no package writer path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from services.character_runtime import (
    RuntimeMemoryBackend,
    RuntimeSession,
    load_accepted_character,
)
from services.crp_authoring import compute_package_hash

from .runtime_policy import RuntimePolicy, build_assembly_hash
from .scene import scene_hash as _compute_scene_hash
from .turn_capture import TurnCapture


def _scene_hash_or_none(scene):
    return _compute_scene_hash(scene) if scene is not None else None

ProviderCallable = Callable[[list], str]
ProviderFactory = Callable[[Optional[Callable[[dict], None]]], ProviderCallable]

_PROVIDER_ATTRIBUTION_FIELDS = (
    "provider_id",
    "model",
    "base_url",
    "timeout_s",
    "max_tokens",
    "json_mode",
    "response_format",
    "extra_params",
    "credential_env",
)


@dataclass(frozen=True)
class LoadedState:
    character_id: str
    acceptance_id: str
    acceptance_decision: str
    accepted_source_hash: str
    runtime_loaded_package_hash: str
    hash_match: bool
    package_id: str
    package_version: int
    package_status: str
    variant_id: str
    variant_version: int
    session_id: str
    provider_id: str
    model: str


@dataclass(frozen=True)
class TurnResult:
    turn_id: str
    session_id: str
    character_id: str
    variant_id: str
    variant_version: int
    accepted_source_hash: str
    package_hash_after: str
    package_hash_unchanged: bool
    user_message: str
    response: str
    messages: tuple
    assembly_hash: str
    request_hash: Optional[str] = None
    response_metadata: dict = field(default_factory=dict)
    persisted_event_ids: tuple = ()
    provider: dict = field(default_factory=dict)
    scene_id: Optional[str] = None
    scene_hash: Optional[str] = None
    scene_present: bool = False


def build_provider_attribution(provider_info: Optional[dict]) -> dict:
    info = dict(provider_info or {})
    attribution = {}
    for key in _PROVIDER_ATTRIBUTION_FIELDS:
        if key in info:
            attribution[key] = info[key]
    attribution.setdefault("attempt_count", 1)
    attribution["retry"] = "none"
    attribution["fallback"] = "none"
    return attribution


def extract_response_metadata(data: Optional[dict]) -> dict:
    if not isinstance(data, dict):
        return {}
    meta: dict = {}
    if "id" in data:
        meta["response_id"] = data["id"]
    if "model" in data:
        meta["provider_reported_model"] = data["model"]
    if "usage" in data:
        meta["usage"] = data["usage"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        finish_reason = choices[0].get("finish_reason")
        if finish_reason is not None:
            meta["finish_reason"] = finish_reason
    return meta


class RuntimeService:
    """Composition boundary for the accepted character + policy + memory + provider."""

    def __init__(self, *, acceptance_root, source_loader) -> None:
        self._acceptance_root = Path(acceptance_root)
        self._source_loader = source_loader

    def resolve(
        self,
        subject_id: str,
        *,
        policy: RuntimePolicy,
        provider_id: str,
        model: str,
        session_id: Optional[str] = None,
    ) -> LoadedState:
        accepted = load_accepted_character(
            subject_id,
            acceptance_root=self._acceptance_root,
            source_loader=self._source_loader,
        )
        loaded_hash = compute_package_hash(accepted.package)
        return LoadedState(
            character_id=subject_id,
            acceptance_id=accepted.acceptance_id,
            acceptance_decision="HUMAN_APPROVED",
            accepted_source_hash=accepted.source_candidate_hash,
            runtime_loaded_package_hash=loaded_hash,
            hash_match=(loaded_hash == accepted.source_candidate_hash),
            package_id=accepted.package.package_id,
            package_version=accepted.package.package_version,
            package_status=accepted.package.status.value,
            variant_id=policy.variant_id,
            variant_version=policy.variant_version,
            session_id=session_id or f"session-{uuid.uuid4().hex}",
            provider_id=provider_id,
            model=model,
        )

    def turn(
        self,
        subject_id: str,
        *,
        policy: RuntimePolicy,
        history: list,
        user_message: str,
        provider: ProviderCallable,
        memory_root: Path,
        session_id: Optional[str] = None,
        provider_info: Optional[dict] = None,
        capture: Optional[TurnCapture] = None,
        turn_id: Optional[str] = None,
        provider_factory: Optional[ProviderFactory] = None,
        scene=None,
    ) -> TurnResult:
        accepted = load_accepted_character(
            subject_id,
            acceptance_root=self._acceptance_root,
            source_loader=self._source_loader,
        )
        sid = session_id or f"session-{uuid.uuid4().hex}"
        backend = RuntimeMemoryBackend(Path(memory_root), subject_id)
        session = RuntimeSession(accepted, backend, sid)
        try:
            runtime_context = session.build_runtime_context()
            assembly = policy.assemble_context(
                runtime_context=runtime_context,
                session_id=session.session_id,
                history=history,
                user_message=user_message,
                scene=scene,
            )
            assembly_hash = build_assembly_hash(assembly.manifest)
            tid = turn_id or f"turn-{uuid.uuid4().hex}"
            attribution = build_provider_attribution(provider_info)

            recorder = None
            if capture is not None:
                recorder = capture.recorder(
                    turn_id=tid,
                    manifest=assembly.manifest,
                    assembly_hash=assembly_hash,
                    attribution=attribution,
                )
            effective_provider = (
                provider_factory(recorder) if provider_factory is not None else provider
            )
            response = effective_provider(list(assembly.messages))

            events = policy.persist(
                session=session,
                user_message=user_message,
                response=response,
                memory=backend,
            )
            package_hash_after = compute_package_hash(accepted.package)

            request_hash = None
            response_metadata: dict = {}
            if capture is not None:
                request_hash = capture.read_request_hash(tid)
                response_metadata = extract_response_metadata(capture.read_response(tid))

            return TurnResult(
                turn_id=tid,
                session_id=session.session_id,
                character_id=subject_id,
                variant_id=policy.variant_id,
                variant_version=policy.variant_version,
                accepted_source_hash=accepted.source_candidate_hash,
                package_hash_after=package_hash_after,
                package_hash_unchanged=(package_hash_after == accepted.source_candidate_hash),
                user_message=user_message,
                response=response,
                messages=assembly.messages,
                assembly_hash=assembly_hash,
                request_hash=request_hash,
                response_metadata=response_metadata,
                persisted_event_ids=tuple(e.event_id for e in events),
                provider=attribution,
                scene_id=getattr(scene, "scene_id", None),
                scene_hash=_scene_hash_or_none(scene),
                scene_present=scene is not None,
            )
        finally:
            session.close()
