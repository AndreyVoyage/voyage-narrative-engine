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
from typing import Callable, Optional, Sequence

from services.character_core.epistemics import EpistemicEnvelope
from services.character_runtime import (
    RuntimeMemoryBackend,
    RuntimeSession,
    load_accepted_character,
)
from services.character_runtime.consolidated_memory import ConsolidatedMemoryBackend
from services.character_runtime.state import RuntimeStateBackend
from services.crp_authoring import compute_package_hash

from .epistemic_bridge import build_runtime_epistemic_context
from .package_extensions import load_character_dimension_set
from .runtime_policy import KIRA_GROUNDED_V2, RuntimePolicy, build_assembly_hash
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

    @staticmethod
    def _load_runtime_state(state_root: Optional[Path], subject_id: str) -> list:
        """Current operator-confirmed state as plain dicts (empty when no DB)."""
        if state_root is None:
            return []
        backend = RuntimeStateBackend(Path(state_root), subject_id)
        try:
            entries = backend.load_current_state(subject_id)
        finally:
            backend.close()
        return [
            {
                "domain": e.domain,
                "key": e.key,
                "value": e.value,
                "source_kind": e.source_kind,
                "source_ref": e.source_ref,
                "seq": e.seq,
                "event_id": e.event_id,
                "created_at": e.created_at,
            }
            for e in entries
        ]

    @staticmethod
    def _load_consolidated_records(memory_root: Path, subject_id: str) -> tuple:
        """Active (non-superseded) APPROVED Consolidated Memory records as the
        real ``ConsolidatedMemoryRecord`` objects, for the epistemic bridge
        (which needs the domain objects, not dicts). Read-only."""
        backend = ConsolidatedMemoryBackend(Path(memory_root), subject_id)
        try:
            return tuple(backend.load_active_records(subject_id))
        finally:
            backend.close()

    @staticmethod
    def _select_epistemic_runtime_inputs(
        bounded_raw_events, active_consolidated_records, events_by_id: dict
    ) -> tuple:
        """The deterministic MINIMAL ``RuntimeEvent`` sequence handed to the
        epistemic bridge: the already-bounded Grounded raw working-context
        events, PLUS only the specific source/basis events the active
        consolidated records need to resolve their original causal ``seq``.

        No unrelated historical event is admitted merely because it exists.
        Exact ``event_id`` dedupe (a consolidated-basis event already inside
        the bounded raw set is not added twice); bounded-raw order is kept,
        then any extra basis events in record order. A basis event that is not
        resolvable here is simply not added -- the bridge then fails closed on
        that record (``missing_basis_event``), which is the preserved
        behavior; ``seq`` is never guessed.
        """
        seen: set = set()
        out: list = []
        for event in bounded_raw_events:
            if event.event_id not in seen:
                seen.add(event.event_id)
                out.append(event)
        for record in active_consolidated_records:
            for basis_id in record.basis_event_ids:
                if basis_id in seen:
                    continue
                event = events_by_id.get(basis_id)
                if event is not None:
                    seen.add(basis_id)
                    out.append(event)
        return tuple(out)

    @staticmethod
    def _load_consolidated_memory(memory_root: Path, subject_id: str) -> list:
        """Active (non-superseded) APPROVED Consolidated Memory records for this
        workspace, as plain dicts. Read-only; opens and closes its own
        connection to the shared per-workspace ``runtime_memory.sqlite3``."""
        backend = ConsolidatedMemoryBackend(Path(memory_root), subject_id)
        try:
            records = backend.load_active_records(subject_id)
            in_conflict = backend.active_conflict_record_ids(subject_id)
        finally:
            backend.close()
        return [
            {
                "record_id": r.record_id,
                "source_event_id": r.source_event_id,
                "basis_event_ids": list(r.basis_event_ids),
                "memory_kind": r.memory_kind,
                "epistemic_kind": r.epistemic_kind,
                "provenance": r.provenance,
                "holder_id": r.holder_id,
                "meaning": r.meaning,
                "seq": r.seq,
                "in_conflict": r.record_id in in_conflict,
            }
            for r in records
        ]

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
        state_root: Optional[Path] = None,
        explicit_epistemic_envelopes: Sequence[EpistemicEnvelope] = (),
        epistemic_at_seq: Optional[int] = None,
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
            runtime_context = dict(session.build_runtime_context())
            # Additive keys for grounded variants. Beta v1 ignores them, so its
            # assembled context / manifest / request bytes stay unchanged.
            runtime_context["accepted_package"] = accepted.package
            prior_events = tuple(backend.load_events_causal(subject_id))
            runtime_context["causal_memory"] = [
                {
                    "event_id": e.event_id,
                    "session_id": e.session_id,
                    "event_type": e.event_type,
                    "meaning": e.meaning,
                    "created_at": e.created_at,
                    "seq": e.seq,
                    "provenance": e.provenance,
                }
                for e in prior_events
            ]
            # Explicitly operator-confirmed Runtime State (own per-workspace DB).
            # Additive + already REMOVE-filtered; Beta v1 ignores this key.
            runtime_context["runtime_state"] = self._load_runtime_state(
                state_root, subject_id
            )
            # Grounded v2 ONLY: attach the character's versioned
            # dimension-semantics extension (RELATIONSHIP / PSYCHOLOGY meaning),
            # hash-bound to THIS Accepted Package. Absent extension -> the key
            # is left unset and Character Core falls back to raw numeric
            # rendering. Beta v1 never receives this key.
            if getattr(policy, "variant_id", None) == KIRA_GROUNDED_V2:
                dimension_set = load_character_dimension_set(
                    subject_id, accepted.source_candidate_hash
                )
                if dimension_set is not None:
                    runtime_context["dimension_definitions"] = dimension_set
                # Approved, active Consolidated Memory for THIS workspace only
                # (shares the per-workspace memory DB; Beta v1 never gets this
                # key). Raw Event Log is untouched.
                runtime_context["consolidated_memory"] = self._load_consolidated_memory(
                    Path(memory_root), subject_id
                )
                # Point-in-time epistemic visibility (Grounded v2 ONLY). ``at_seq``
                # is the causal position of THIS turn: the seq the current user
                # event will be persisted at == max(existing causal seq) + 1
                # (single-process runtime). ``epistemic_at_seq`` overrides it for
                # historical replay / tests -- production always passes None and
                # the live causal point is computed here. NOT wall-clock, NOT a
                # session count, NOT approval order, NOT an array index.
                prior_seqs = [e.seq for e in prior_events if e.seq is not None]
                at_seq = (
                    int(epistemic_at_seq)
                    if epistemic_at_seq is not None
                    else ((max(prior_seqs) + 1) if prior_seqs else 1)
                )
                # BOUNDED bridge input (architectural gate): the epistemic layer
                # is a VISIBILITY FILTER, not a retrieval engine. Its
                # runtime-event input is ONLY (a) the already-bounded Grounded
                # raw working context -- reusing ``policy.select_memory`` so the
                # 20-event / 6000-char / causal-order rules are NOT reimplemented
                # -- plus (b) the specific source/basis events the active
                # consolidated records need for causal-seq resolution. Unrelated
                # historical events never become epistemic candidates.
                active_records = self._load_consolidated_records(
                    Path(memory_root), subject_id
                )
                events_by_id = {e.event_id: e for e in prior_events}
                bounded_raw = [
                    events_by_id[d["event_id"]]
                    for d in policy.select_memory(runtime_context, session.session_id)
                    if d.get("event_id") in events_by_id
                ]
                bridge_runtime_events = self._select_epistemic_runtime_inputs(
                    bounded_raw, active_records, events_by_id
                )
                runtime_context["epistemic_at_seq"] = at_seq
                runtime_context["epistemic_perceiver_id"] = subject_id
                runtime_context["epistemic_snapshot"] = build_runtime_epistemic_context(
                    subject_id=subject_id,
                    runtime_events=bridge_runtime_events,
                    consolidated_records=active_records,
                    explicit_envelopes=tuple(explicit_epistemic_envelopes or ()),
                    perceiver_id=subject_id,
                    at_seq=at_seq,
                )
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
