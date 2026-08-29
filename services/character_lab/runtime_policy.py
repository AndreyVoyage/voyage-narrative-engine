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

KIRA_BETA_V1_CURRENT = "KIRA_BETA_V1_CURRENT"
BETA_V1_VARIANT_VERSION = 1


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

    def persist(self, *, session, user_message: str, response: str):
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
        # Beta v1 has no scene support (Slice 3). scene is ignored.
        del scene
        prior = self.select_memory(runtime_context, session_id)
        system = self._build_system_prompt(runtime_context, prior)
        messages = (
            ({"role": "system", "content": system},)
            + tuple(history)
            + ({"role": "user", "content": user_message},)
        )
        manifest = AssemblyManifest(
            variant_id=self.variant_id,
            variant_version=self.variant_version,
            items=tuple(self._build_items(runtime_context, prior, history, user_message)),
        )
        return ContextAssembly(messages=messages, manifest=manifest)

    def _build_items(self, ctx, prior, history, user_message):
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

    def persist(self, *, session, user_message: str, response: str):
        user_event = session.record_runtime_event("USER_MESSAGE", user_message)
        char_event = session.record_runtime_event("CHARACTER_MESSAGE", response)
        return (user_event, char_event)
