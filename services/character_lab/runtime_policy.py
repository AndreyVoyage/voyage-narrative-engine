#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab RuntimePolicy / Character Variant abstraction (Slice 1).

A Variant is: same AcceptedCharacter + named/versioned runtime/context/memory
policy. V1 implements exactly one policy, ``KIRA_BETA_V1_CURRENT``, which is a
frozen reproduction of the current committed ``tools/kira_chat_cli.py``
provider-context behavior. It does NOT inject full package claim content and it
does NOT change legacy memory ordering (OD-CL-02). Scene support is not present
in this slice.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from . import provenance as _provenance
from .grounding import render_accepted_grounding
from .scene import render_scene_block, scene_hash

KIRA_BETA_V1_CURRENT = "KIRA_BETA_V1_CURRENT"
BETA_V1_VARIANT_VERSION = 1

KIRA_GROUNDED_V2 = "KIRA_GROUNDED_V2"
GROUNDED_V2_VARIANT_VERSION = 1

#: Reserved-but-disabled variant id (no policy, never selectable in V1).
EXPERIMENTAL_VARIANT_ID = "EXPERIMENTAL"


@dataclass(frozen=True)
class AssemblyItem:
    """One manifest item mapping request text back to its source."""

    kind: str
    text: str
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssemblyManifest:
    """Deterministic assembly manifest produced by the SAME context-assembly op."""

    variant_id: str
    variant_version: int
    items: tuple


@dataclass(frozen=True)
class ContextAssembly:
    """The provider messages plus their assembly manifest."""

    messages: tuple
    manifest: AssemblyManifest


def manifest_to_jsonable(manifest: AssemblyManifest) -> dict:
    """Serialize a manifest to a canonical JSON-safe dict."""
    return {
        "variant_id": manifest.variant_id,
        "variant_version": manifest.variant_version,
        "items": [
            {"kind": item.kind, "text": item.text, "meta": dict(item.meta)}
            for item in manifest.items
        ],
    }


def build_assembly_hash(manifest: AssemblyManifest) -> str:
    """Deterministic canonical hash of a manifest's content."""
    payload = manifest_to_jsonable(manifest)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RuntimePolicy:
    """Minimal Variant contract: identity + context assembly + persistence.

    Package loading, acceptance verification, provider configuration, workspace
    management, and UI state are intentionally NOT this object's responsibility.
    """

    variant_id: str
    variant_version: int

    def select_memory(self, runtime_context: Mapping[str, Any], session_id: str):
        raise NotImplementedError

    def assemble_context(
        self,
        *,
        runtime_context: Mapping[str, Any],
        session_id: str,
        history: list,
        user_message: str,
        scene=None,
    ) -> ContextAssembly:
        raise NotImplementedError

    def persist(self, *, session, user_message: str, response: str, memory=None):
        raise NotImplementedError


# Frozen Beta v1 prompt fragments -- must match tools/kira_chat_cli.py exactly.
_BETA_V1_ROLE_LINE = "Ты — Кира, персонаж. Отвечай от лица персонажа на русском языке."
_BETA_V1_CLOSING_LINE = "Используй только известную тебе информацию о собеседнике."


class BetaV1CurrentPolicy(RuntimePolicy):
    """Frozen historical baseline. Do NOT "improve" it."""

    variant_id = KIRA_BETA_V1_CURRENT
    variant_version = BETA_V1_VARIANT_VERSION

    def select_memory(self, runtime_context, session_id):
        return [
            e for e in runtime_context["runtime_memory"]
            if e["session_id"] != session_id
        ]

    def _build_system_prompt(self, ctx, prior) -> str:
        mem_lines = "\n".join(
            f"- [{e['event_type']}] {e['meaning']}" for e in prior
        ) or "(нет сохранённых воспоминаний)"
        return (
            f"{_BETA_V1_ROLE_LINE}\n"
            f"Персонаж: subject_id={ctx['subject_id']}, "
            f"package_id={ctx['package_id']}, package_version={ctx['package_version']}, "
            f"status={ctx['package_status']}.\n"
            f"source_candidate_hash={ctx['source_candidate_hash']}.\n"
            "Память из предыдущих сессий:\n" + mem_lines + "\n"
            f"{_BETA_V1_CLOSING_LINE}"
        )

    def assemble_context(
        self,
        *,
        runtime_context,
        session_id,
        history,
        user_message,
        scene=None,
    ) -> ContextAssembly:
        # OD-CL-02 / Part C: with NO scene, this is byte-for-byte the historical
        # KIRA_BETA_V1_CURRENT provider context. A scene, when present, is an
        # ADDITIVE, clearly separated system block -- never a rewrite of the
        # historical assembly.
        prior = self.select_memory(runtime_context, session_id)
        system = self._build_system_prompt(runtime_context, prior)
        scene_messages = ()
        if scene is not None:
            scene_messages = ({"role": "system", "content": render_scene_block(scene)},)
        messages = (
            ({"role": "system", "content": system},)
            + scene_messages
            + tuple(history)
            + ({"role": "user", "content": user_message},)
        )
        manifest = AssemblyManifest(
            variant_id=self.variant_id,
            variant_version=self.variant_version,
            items=tuple(
                self._build_items(runtime_context, prior, history, user_message, scene)
            ),
        )
        return ContextAssembly(messages=messages, manifest=manifest)

    def _build_items(self, ctx, prior, history, user_message, scene=None):
        items = []
        items.append(AssemblyItem("system.role_instruction", _BETA_V1_ROLE_LINE, {}))
        package_identity = (
            f"Персонаж: subject_id={ctx['subject_id']}, "
            f"package_id={ctx['package_id']}, package_version={ctx['package_version']}, "
            f"status={ctx['package_status']}."
        )
        items.append(AssemblyItem(
            "system.package_identity",
            package_identity,
            {
                "subject_id": ctx["subject_id"],
                "package_id": ctx["package_id"],
                "package_version": ctx["package_version"],
                "package_status": ctx["package_status"],
            },
        ))
        source_hash_line = f"source_candidate_hash={ctx['source_candidate_hash']}."
        items.append(AssemblyItem(
            "system.package_identity",
            source_hash_line,
            {"accepted_source_hash": ctx["source_candidate_hash"]},
        ))
        if scene is not None:
            items.append(AssemblyItem(
                "system.scene",
                render_scene_block(scene),
                {"scene_id": scene.scene_id, "scene_hash": scene_hash(scene)},
            ))
        for e in prior:
            items.append(AssemblyItem(
                "system.memory_line",
                f"- [{e['event_type']}] {e['meaning']}",
                {
                    "event_id": e.get("event_id"),
                    "session_id": e.get("session_id"),
                    "event_type": e.get("event_type"),
                },
            ))
        for idx, msg in enumerate(history):
            items.append(AssemblyItem(
                f"history.{msg['role']}",
                msg["content"],
                {"turn_index": idx},
            ))
        items.append(AssemblyItem("user.current", user_message, {}))
        return items

    def persist(self, *, session, user_message: str, response: str, memory=None):
        # Part C: event_type strings stay exactly "USER_MESSAGE" /
        # "CHARACTER_MESSAGE" so historical prompt rendering is unchanged.
        # Provenance is a SEPARATE observational label written after the fact;
        # it never reaches Beta v1 provider context.
        user_event = session.record_runtime_event("USER_MESSAGE", user_message)
        char_event = session.record_runtime_event("CHARACTER_MESSAGE", response)
        if memory is not None:
            memory.set_provenance(user_event.event_id, _provenance.USER_STATED)
            memory.set_provenance(char_event.event_id, _provenance.CHARACTER_UTTERANCE)
        return (user_event, char_event)


# --------------------------------------------------------------------------- v2

# Grounded v2 core instruction. It never contains chain-of-thought, a decision
# layer, or relationship-evolution logic -- only framing for the segments below.
_GROUNDED_V2_CORE_INSTRUCTION = (
    "Ты — Кира, персонаж. Отвечай от лица персонажа на русском языке.\n"
    "Ниже отдельным блоком дано принятое описание персонажа (Accepted "
    "Character). Опирайся только на него и на подтверждённые сведения.\n"
    "Блок памяти — это информация со слов собеседника, а не установленные "
    "факты; твои прошлые реплики фактами также не являются.\n"
    "Не выдумывай факты, которых нет в принятом описании, и не превращай "
    "неизвестное или спорное в утверждение."
)

_GROUNDED_V2_MEMORY_HEADER = (
    "ПАМЯТЬ / MEMORY (со слов собеседника — не установленные факты)"
)
_GROUNDED_V2_MEMORY_LINE_PREFIX = "- [со слов собеседника] "

_GROUNDED_V2_STATE_HEADER = "ПОДТВЕРЖДЁННОЕ ТЕКУЩЕЕ СОСТОЯНИЕ"
_GROUNDED_V2_STATE_FOOTER = (
    "Эти факты оператор явно подтвердил как текущее состояние. Они дополняют "
    "контекст, но не переписывают Принятое описание персонажа."
)


class GroundedV2Policy(RuntimePolicy):
    """Accepted Character grounding + honest user-reported causal memory.

    Consumes two keys ``RuntimeService.turn`` adds to the runtime context that
    Beta v1 ignores: ``accepted_package`` (rendered via
    :func:`render_accepted_grounding`) and ``causal_memory`` (durable events in
    causal ``seq`` order, each with a provenance label).

    Assembly order: (1) core runtime instruction, (2) Accepted Character
    grounding, (3) operator-confirmed Runtime State (only when non-empty),
    (4) causal user-reported memory, (5) Scene when active, (6) the current
    user input. No chain-of-thought, no decision layer, no relationship
    evolution.
    """

    variant_id = KIRA_GROUNDED_V2
    variant_version = GROUNDED_V2_VARIANT_VERSION

    def select_memory(self, runtime_context, session_id):
        # Honest factual memory only: USER_STATED events, in causal seq order.
        # CHARACTER_UTTERANCE and LEGACY_UNCLASSIFIED (incl. NULL provenance)
        # are never surfaced as established factual grounding.
        events = runtime_context.get("causal_memory") or ()
        selected = [
            e
            for e in events
            if _provenance.normalize(e.get("provenance")) == _provenance.USER_STATED
        ]
        selected.sort(
            key=lambda e: (
                e["seq"] if e.get("seq") is not None else 0,
                e.get("event_id") or "",
            )
        )
        return selected

    def _memory_block(self, selected) -> str:
        lines = [_GROUNDED_V2_MEMORY_HEADER]
        for e in selected:
            lines.append(
                _GROUNDED_V2_MEMORY_LINE_PREFIX + str(e.get("meaning", "")).strip()
            )
        return "\n".join(lines)

    def select_state(self, runtime_context):
        # Current operator-confirmed Runtime State only. Already REMOVE-filtered
        # and sorted by (domain, key) by the backend; re-sorted here for a
        # deterministic block regardless of caller.
        entries = list(runtime_context.get("runtime_state") or [])
        entries.sort(key=lambda e: (e.get("domain") or "", e.get("key") or ""))
        return entries

    @staticmethod
    def _state_line(entry) -> str:
        return f"- {str(entry.get('key', '')).strip()}: {str(entry.get('value', '')).strip()}"

    def _state_block(self, entries) -> str:
        lines = [_GROUNDED_V2_STATE_HEADER, ""]
        for entry in entries:
            lines.append(self._state_line(entry))
        lines.append("")
        lines.append(_GROUNDED_V2_STATE_FOOTER)
        return "\n".join(lines)

    def assemble_context(
        self,
        *,
        runtime_context,
        session_id,
        history,
        user_message,
        scene=None,
    ) -> ContextAssembly:
        package = runtime_context.get("accepted_package")
        grounding = render_accepted_grounding(package) if package is not None else ""
        accepted_source_hash = runtime_context.get("source_candidate_hash")
        selected_state = self.select_state(runtime_context)
        state_block = self._state_block(selected_state) if selected_state else None
        selected_mem = self.select_memory(runtime_context, session_id)
        memory_block = self._memory_block(selected_mem) if selected_mem else None

        system_messages = [{"role": "system", "content": _GROUNDED_V2_CORE_INSTRUCTION}]
        if grounding:
            system_messages.append({"role": "system", "content": grounding})
        if state_block is not None:
            system_messages.append({"role": "system", "content": state_block})
        if memory_block is not None:
            system_messages.append({"role": "system", "content": memory_block})
        if scene is not None:
            system_messages.append(
                {"role": "system", "content": render_scene_block(scene)}
            )

        messages = (
            tuple(system_messages)
            + tuple(history)
            + ({"role": "user", "content": user_message},)
        )
        manifest = AssemblyManifest(
            variant_id=self.variant_id,
            variant_version=self.variant_version,
            items=tuple(
                self._build_items(
                    package,
                    grounding,
                    accepted_source_hash,
                    selected_state,
                    selected_mem,
                    history,
                    user_message,
                    scene,
                )
            ),
        )
        return ContextAssembly(messages=messages, manifest=manifest)

    def _build_items(
        self,
        package,
        grounding,
        accepted_source_hash,
        selected_state,
        selected_mem,
        history,
        user_message,
        scene,
    ):
        items = [
            AssemblyItem(
                "system.role_instruction", _GROUNDED_V2_CORE_INSTRUCTION, {}
            )
        ]
        if grounding:
            items.append(
                AssemblyItem(
                    "system.package_grounding",
                    grounding,
                    {
                        "package_id": getattr(package, "package_id", None),
                        "package_version": getattr(package, "package_version", None),
                        "accepted_source_hash": accepted_source_hash,
                        "rendered_chars": len(grounding),
                        "grounding": "SELECTED",
                    },
                )
            )
        if selected_state:
            items.append(
                AssemblyItem(
                    "system.runtime_state",
                    self._state_block(selected_state),
                    {"entry_count": len(selected_state), "source": "OPERATOR_CONFIRMED"},
                )
            )
            for entry in selected_state:
                items.append(
                    AssemblyItem(
                        "system.runtime_state_line",
                        self._state_line(entry),
                        {
                            "domain": entry.get("domain"),
                            "key": entry.get("key"),
                            "seq": entry.get("seq"),
                            "event_id": entry.get("event_id"),
                            "source_kind": entry.get("source_kind"),
                        },
                    )
                )
        if selected_mem:
            items.append(
                AssemblyItem(
                    "system.memory_grounding",
                    _GROUNDED_V2_MEMORY_HEADER,
                    {"event_count": len(selected_mem), "order": "seq"},
                )
            )
            for e in selected_mem:
                items.append(
                    AssemblyItem(
                        "system.memory_line",
                        _GROUNDED_V2_MEMORY_LINE_PREFIX
                        + str(e.get("meaning", "")).strip(),
                        {
                            "event_id": e.get("event_id"),
                            "seq": e.get("seq"),
                            "session_id": e.get("session_id"),
                            "provenance": _provenance.normalize(e.get("provenance")),
                            "provenance_display": "user-reported",
                        },
                    )
                )
        if scene is not None:
            items.append(
                AssemblyItem(
                    "system.scene",
                    render_scene_block(scene),
                    {"scene_id": scene.scene_id, "scene_hash": scene_hash(scene)},
                )
            )
        for idx, msg in enumerate(history):
            items.append(
                AssemblyItem(f"history.{msg['role']}", msg["content"], {"turn_index": idx})
            )
        items.append(AssemblyItem("user.current", user_message, {}))
        return items

    def persist(self, *, session, user_message: str, response: str, memory=None):
        # Same durable-write contract as Beta v1: append the two dialogue events
        # and attach honest provenance. No row mutation, no schema change.
        user_event = session.record_runtime_event("USER_MESSAGE", user_message)
        char_event = session.record_runtime_event("CHARACTER_MESSAGE", response)
        if memory is not None:
            memory.set_provenance(user_event.event_id, _provenance.USER_STATED)
            memory.set_provenance(char_event.event_id, _provenance.CHARACTER_UTTERANCE)
        return (user_event, char_event)


# ------------------------------------------------------------- policy registry

class UnknownVariantError(ValueError):
    """Raised when a variant id is not a selectable backend policy."""


_POLICY_FACTORIES = {
    KIRA_BETA_V1_CURRENT: BetaV1CurrentPolicy,
    KIRA_GROUNDED_V2: GroundedV2Policy,
}

#: Variant ids the backend will actually instantiate. ``EXPERIMENTAL`` is
#: intentionally absent -- it stays disabled in V1.
SUPPORTED_VARIANT_IDS = tuple(_POLICY_FACTORIES.keys())


def build_policy(variant_id: str) -> RuntimePolicy:
    """Resolve a variant id to a fresh policy instance (backend validated)."""
    if not isinstance(variant_id, str) or not variant_id.strip():
        raise UnknownVariantError("variant_id must be a non-empty string")
    if variant_id == EXPERIMENTAL_VARIANT_ID:
        raise UnknownVariantError("EXPERIMENTAL variant is disabled in V1")
    try:
        factory = _POLICY_FACTORIES[variant_id]
    except KeyError:
        raise UnknownVariantError(f"unknown variant {variant_id!r}") from None
    return factory()
