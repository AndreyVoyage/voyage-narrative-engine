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

from services.character_core.dimensions import (
    DimensionSet,
    interpret_state_entry,
    semantic_state_line,
)

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

# Bounded working-context policy (OD-MEM-EVO-10). Applied to the GROUNDING /
# working-memory layer only -- NOT to the live conversation ``history``, which
# is assembled separately. "Whichever limit is reached first"; newest eligible
# causal events are preferred (the single newest line is always kept for
# continuity, then older lines are added only while within BOTH bounds).
GROUNDED_V2_RAW_MEMORY_MAX_EVENTS = 20
GROUNDED_V2_RAW_MEMORY_MAX_CHARS = 6000
GROUNDED_V2_CONSOLIDATED_MAX_RECORDS = 20
GROUNDED_V2_CONSOLIDATED_MAX_CHARS = 6000

# Consolidated Memory (approved, active, workspace-scoped user reports).
_GROUNDED_V2_CONSMEM_HEADER = (
    "КОНСОЛИДИРОВАННАЯ ПАМЯТЬ (сообщено собеседником в прошлых сессиях этой "
    "рабочей области — не независимо подтверждённые факты)"
)
_GROUNDED_V2_CONSMEM_LINE_PREFIX = "- [USER_REPORT] "
_GROUNDED_V2_CONSMEM_CONFLICT_SUFFIX = "  [ПРОТИВОРЕЧИЕ: есть несогласованная запись]"
_GROUNDED_V2_CONSMEM_FOOTER = (
    "Это устойчивая память со слов собеседника из прошлых сессий этой рабочей "
    "области; провенанс сохранён. Это не независимо подтверждённая истина, и "
    "противоречия здесь не разрешаются автоматически."
)

# Point-in-time epistemic context (GROUNDED v2 ONLY). This is a VISIBILITY
# FILTER over material the pipeline already selected/supplied -- never a new
# retrieval engine and never a way past the raw working-context bounds above.
# Character Core / the epistemic bridge make every visibility decision; this
# module only renders what they report visible.
_GROUNDED_V2_EPI_HEADER = (
    "ЭПИСТЕМИЧЕСКИЙ КОНТЕКСТ (что персонажу доступно знать/считать на текущий "
    "причинный момент)"
)
_GROUNDED_V2_EPI_KIND_PREFIX = {
    "WORLD_FACT": "[WORLD_FACT] ",
    "USER_REPORT": "[USER_REPORT] ",
    "CHARACTER_BELIEF": "[CHARACTER_BELIEF] ",
    "CHARACTER_INTERPRETATION": "[CHARACTER_INTERPRETATION] ",
}
_GROUNDED_V2_EPI_FOOTER = (
    "Типы не смешиваются: WORLD_FACT — доступное этому персонажу состояние "
    "мира; USER_REPORT — со слов, не независимо подтверждённая истина; "
    "CHARACTER_BELIEF — во что верит этот персонаж, может быть ошибочно; "
    "CHARACTER_INTERPRETATION — истолкование персонажа, не объективный факт. "
    "Противоречия здесь не разрешаются: WORLD_FACT не заменяет убеждение, а "
    "убеждение — факт. Но если доступный WORLD_FACT прямо противоречит "
    "собственному убеждению персонажа и важен для текущего ответа или "
    "действия, не игнорируй ни одну из сторон: убеждение остаётся "
    "субъективным состоянием персонажа, а доступный WORLD_FACT персонаж "
    "учитывает в непосредственном ответе или действии. Персонаж может "
    "естественно проявить удивление, сомнение или желание проверить; молча "
    "переписывать убеждение при этом не требуется."
)


def _bounded_newest(items, *, rendered_len, max_items, max_chars):
    """Keep the newest ``items`` (input is oldest->newest) within BOTH a count
    and a rendered-character budget, then return them back in oldest->newest
    order. The single newest item is always kept (conversational/grounding
    continuity); older items are added only while both limits still hold."""
    kept = []
    total = 0
    for idx, item in enumerate(reversed(list(items))):
        line_len = rendered_len(item)
        if idx > 0 and (len(kept) >= max_items or total + line_len > max_chars):
            break
        kept.append(item)
        total += line_len
    kept.reverse()
    return kept

_GROUNDED_V2_STATE_HEADER = "ПОДТВЕРЖДЁННОЕ ТЕКУЩЕЕ СОСТОЯНИЕ"
_GROUNDED_V2_STATE_FOOTER = (
    "Эти факты оператор явно подтвердил как текущее состояние. Они дополняют "
    "контекст, но не переписывают Принятое описание персонажа."
)

_GROUNDED_V2_REL_HEADER = "ПОДТВЕРЖДЁННОЕ СОСТОЯНИЕ ОТНОШЕНИЙ"
_GROUNDED_V2_PSY_HEADER = "ПОДТВЕРЖДЁННОЕ ПСИХОЛОГИЧЕСКОЕ СОСТОЯНИЕ"
_GROUNDED_V2_NUMERIC_FOOTER = (
    "Это текущие подтверждённые оператором значения времени выполнения "
    "(шкала -100..+100). Это не неизменный канон персонажа."
)

_DOMAIN_FACT = "FACT"
_DOMAIN_RELATIONSHIP = "RELATIONSHIP"
_DOMAIN_PSYCHOLOGY = "PSYCHOLOGY"

# (domain, manifest kind, per-line kind, block header, block footer).
_GROUNDED_V2_STATE_SEGMENTS = (
    (_DOMAIN_FACT, "system.runtime_state", "system.runtime_state_line",
     _GROUNDED_V2_STATE_HEADER, _GROUNDED_V2_STATE_FOOTER),
    (_DOMAIN_RELATIONSHIP, "system.relationship_state", "system.relationship_state_line",
     _GROUNDED_V2_REL_HEADER, _GROUNDED_V2_NUMERIC_FOOTER),
    (_DOMAIN_PSYCHOLOGY, "system.psychology_state", "system.psychology_state_line",
     _GROUNDED_V2_PSY_HEADER, _GROUNDED_V2_NUMERIC_FOOTER),
)


class GroundedV2Policy(RuntimePolicy):
    """Accepted Character grounding + honest user-reported causal memory.

    Consumes two keys ``RuntimeService.turn`` adds to the runtime context that
    Beta v1 ignores: ``accepted_package`` (rendered via
    :func:`render_accepted_grounding`) and ``causal_memory`` (durable events in
    causal ``seq`` order, each with a provenance label).

    Assembly order: (1) core runtime instruction, (2) Accepted Character
    grounding, (3) FACT Runtime State, (4) RELATIONSHIP state, (5) PSYCHOLOGY
    state, (6) causal user-reported memory, (7) Scene when active, (8) the
    current user input -- each included only when non-empty. Numeric domains
    are rendered verbatim from operator-confirmed values; this policy performs
    no autonomous evolution, no chain-of-thought, no decision layer.
    """

    variant_id = KIRA_GROUNDED_V2
    variant_version = GROUNDED_V2_VARIANT_VERSION

    def select_memory(self, runtime_context, session_id):
        # Honest factual memory only: USER_STATED events, in causal seq order.
        # CHARACTER_UTTERANCE and LEGACY_UNCLASSIFIED (incl. NULL provenance)
        # are never surfaced as established factual grounding. Then bound the
        # working-memory layer (OD-MEM-EVO-10): newest 20 events / 6000 chars.
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
        return _bounded_newest(
            selected,
            rendered_len=lambda e: len(
                _GROUNDED_V2_MEMORY_LINE_PREFIX + str(e.get("meaning", "")).strip()
            ),
            max_items=GROUNDED_V2_RAW_MEMORY_MAX_EVENTS,
            max_chars=GROUNDED_V2_RAW_MEMORY_MAX_CHARS,
        )

    def select_consolidated(self, runtime_context):
        # Approved, active, workspace-scoped Consolidated Memory records
        # (RuntimeService injects them for Grounded v2 only). Deterministic
        # order by approval seq; bounded newest 20 records / 6000 chars.
        records = list(runtime_context.get("consolidated_memory") or [])
        records.sort(
            key=lambda r: (
                r["seq"] if r.get("seq") is not None else 0,
                r.get("record_id") or "",
            )
        )
        return _bounded_newest(
            records,
            rendered_len=lambda r: len(
                _GROUNDED_V2_CONSMEM_LINE_PREFIX + str(r.get("meaning", "")).strip()
            ),
            max_items=GROUNDED_V2_CONSOLIDATED_MAX_RECORDS,
            max_chars=GROUNDED_V2_CONSOLIDATED_MAX_CHARS,
        )

    def _memory_block(self, selected) -> str:
        lines = [_GROUNDED_V2_MEMORY_HEADER]
        for e in selected:
            lines.append(
                _GROUNDED_V2_MEMORY_LINE_PREFIX + str(e.get("meaning", "")).strip()
            )
        return "\n".join(lines)

    @staticmethod
    def _consolidated_line(record) -> str:
        suffix = (
            _GROUNDED_V2_CONSMEM_CONFLICT_SUFFIX if record.get("in_conflict") else ""
        )
        return (
            _GROUNDED_V2_CONSMEM_LINE_PREFIX
            + str(record.get("meaning", "")).strip()
            + suffix
        )

    def _consolidated_block(self, selected) -> str:
        lines = [_GROUNDED_V2_CONSMEM_HEADER, ""]
        for r in selected:
            lines.append(self._consolidated_line(r))
        lines.append("")
        lines.append(_GROUNDED_V2_CONSMEM_FOOTER)
        return "\n".join(lines)

    # ---------------------------------------------- point-in-time epistemics
    #
    # ``runtime_context["epistemic_snapshot"]`` is an ``EpistemicContextSnapshot``
    # from ``RuntimeService.turn`` (Grounded v2 only). When absent -- e.g. a
    # test that calls ``assemble_context`` directly, or Beta v1 -- NOTHING here
    # runs and the request is byte-identical to before. This method never
    # compares seqs or perceiver ids itself; it consumes the Core selector's
    # already-computed ``visible_envelopes``.

    @staticmethod
    def _epistemic_apply(runtime_context, snapshot, selected_mem, selected_consolidated):
        """Return ``(mem, consolidated, extra, stats)`` after applying the
        visibility snapshot to the ALREADY-BOUNDED raw / consolidated
        selections and computing the additional epistemic segment.
        """
        visible = tuple(getattr(snapshot, "visible_envelopes", ()) or ())
        visible_report_source_ids: set = set()
        for env in visible:
            if env.epistemic_kind.value == "USER_REPORT":
                visible_report_source_ids.update(env.basis_event_ids)

        # (1) visibility filter: a raw / consolidated USER_REPORT survives only
        #     if its projected envelope is visible to the perceiver at at_seq.
        mem_pre, cons_pre = list(selected_mem), list(selected_consolidated)
        mem = [e for e in mem_pre if e.get("event_id") in visible_report_source_ids]
        consolidated = [
            r for r in cons_pre if r.get("source_event_id") in visible_report_source_ids
        ]
        raw_hidden = len(mem_pre) - len(mem)
        cons_hidden = len(cons_pre) - len(consolidated)

        # (2) exact-source prompt de-duplication (deterministic identity only,
        #     no fuzzy/semantic match): if the same approved source would appear
        #     as BOTH a raw line and a delivered consolidated line, keep the
        #     consolidated one (bridge precedence) and drop the raw line.
        delivered_cons_src = {r.get("source_event_id") for r in consolidated}
        before_dedup = len(mem)
        mem = [e for e in mem if e.get("event_id") not in delivered_cons_src]
        dedup_removed = before_dedup - len(mem)

        # (3) additional epistemic segment: visible envelopes NOT already
        #     represented by a delivered raw / consolidated line. A USER_REPORT
        #     backed by a real prior runtime event that fell OUTSIDE the working
        #     bounds is NOT resurrected here (bounds stay authoritative).
        delivered_src = {e.get("event_id") for e in mem} | delivered_cons_src
        all_prior_ids = {
            e.get("event_id") for e in (runtime_context.get("causal_memory") or ())
        }
        extra: list = []
        seen_keys: set = set()
        for env in visible:
            kind = env.epistemic_kind.value
            basis = tuple(env.basis_event_ids)
            if kind == "USER_REPORT":
                if all(b in delivered_src for b in basis):
                    continue  # already delivered via raw / consolidated
                if any(b in all_prior_ids for b in basis):
                    continue  # bounded-out runtime event -- do not resurrect
            key = (kind, env.meaning, basis)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            extra.append(env)

        stats = {
            "at_seq": runtime_context.get("epistemic_at_seq"),
            "perceiver_id": runtime_context.get("epistemic_perceiver_id"),
            "raw_hidden_by_visibility": raw_hidden,
            "consolidated_hidden_by_visibility": cons_hidden,
            "raw_dropped_exact_source_dedup": dedup_removed,
            "visible_envelope_count": len(visible),
        }
        return mem, consolidated, tuple(extra), stats

    @staticmethod
    def _epistemic_line(env) -> str:
        prefix = _GROUNDED_V2_EPI_KIND_PREFIX.get(env.epistemic_kind.value, "[?] ")
        return prefix + str(env.meaning).strip()

    def _epistemic_block(self, envelopes) -> str:
        lines = [_GROUNDED_V2_EPI_HEADER, ""]
        for env in envelopes:
            lines.append(self._epistemic_line(env))
        lines.append("")
        lines.append(_GROUNDED_V2_EPI_FOOTER)
        return "\n".join(lines)

    def select_state(self, runtime_context):
        # Current operator-confirmed Runtime State only. Already REMOVE-filtered
        # and sorted by (domain, key) by the backend; re-sorted here for a
        # deterministic block regardless of caller.
        entries = list(runtime_context.get("runtime_state") or [])
        entries.sort(key=lambda e: (e.get("domain") or "", e.get("key") or ""))
        return entries

    @staticmethod
    def _domain_entries(entries, domain):
        return [e for e in entries if (e.get("domain") or _DOMAIN_FACT) == domain]

    @staticmethod
    def _resolve_dimension_set(runtime_context):
        """Optional package-declared dimension semantics for this turn.

        Returns a validated :class:`DimensionSet` when the runtime context
        carries ``dimension_definitions`` (a ``DimensionSet`` or a list of
        loader-neutral mappings), else ``None``. Nothing in the current
        pipeline populates this key, so current KIRA turns take the ``None``
        path and render exactly as before -- a future versioned Character
        Package supplies the definitions.
        """
        return DimensionSet.coerce(runtime_context.get("dimension_definitions"))

    @staticmethod
    def _state_line(entry, *, dimension_set=None, domain=None) -> str:
        key = str(entry.get("key", "")).strip()
        value = str(entry.get("value", "")).strip()
        if dimension_set is not None and domain in (_DOMAIN_RELATIONSHIP, _DOMAIN_PSYCHOLOGY):
            # Enriched only when a definition actually resolves; otherwise the
            # helper returns the identical raw "- key: value" line (Core never
            # fabricates meaning from the id).
            return semantic_state_line(domain, key, value, dimension_set)
        return f"- {key}: {value}"

    def _domain_block(self, header, footer, entries, *, dimension_set=None, domain=None) -> str:
        lines = [header, ""]
        for entry in entries:
            lines.append(self._state_line(entry, dimension_set=dimension_set, domain=domain))
        lines.append("")
        lines.append(footer)
        return "\n".join(lines)

    # Backwards-compatible FACT-only renderer (kept for existing callers/tests).
    def _state_block(self, entries) -> str:
        return self._domain_block(
            _GROUNDED_V2_STATE_HEADER, _GROUNDED_V2_STATE_FOOTER, entries
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
        package = runtime_context.get("accepted_package")
        grounding = render_accepted_grounding(package) if package is not None else ""
        accepted_source_hash = runtime_context.get("source_candidate_hash")
        selected_state = self.select_state(runtime_context)
        dimension_set = self._resolve_dimension_set(runtime_context)
        selected_mem = self.select_memory(runtime_context, session_id)
        memory_block = self._memory_block(selected_mem) if selected_mem else None
        selected_consolidated = self.select_consolidated(runtime_context)

        epistemic_extra = ()
        epistemic_stats = None
        snapshot = runtime_context.get("epistemic_snapshot")
        if snapshot is not None:
            (
                selected_mem,
                selected_consolidated,
                epistemic_extra,
                epistemic_stats,
            ) = self._epistemic_apply(
                runtime_context, snapshot, selected_mem, selected_consolidated
            )
            memory_block = self._memory_block(selected_mem) if selected_mem else None

        consolidated_block = (
            self._consolidated_block(selected_consolidated)
            if selected_consolidated
            else None
        )
        epistemic_block = (
            self._epistemic_block(epistemic_extra) if epistemic_extra else None
        )

        system_messages = [{"role": "system", "content": _GROUNDED_V2_CORE_INSTRUCTION}]
        if grounding:
            system_messages.append({"role": "system", "content": grounding})
        # Deterministic order: FACT state, then RELATIONSHIP, then PSYCHOLOGY.
        for domain, _kind, _line_kind, header, footer in _GROUNDED_V2_STATE_SEGMENTS:
            domain_entries = self._domain_entries(selected_state, domain)
            if domain_entries:
                system_messages.append({
                    "role": "system",
                    "content": self._domain_block(
                        header, footer, domain_entries,
                        dimension_set=dimension_set, domain=domain,
                    ),
                })
        if memory_block is not None:
            system_messages.append({"role": "system", "content": memory_block})
        if consolidated_block is not None:
            system_messages.append({"role": "system", "content": consolidated_block})
        if epistemic_block is not None:
            system_messages.append({"role": "system", "content": epistemic_block})
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
                    dimension_set,
                    selected_consolidated,
                    epistemic_extra,
                    epistemic_stats,
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
        dimension_set=None,
        selected_consolidated=None,
        epistemic_extra=(),
        epistemic_stats=None,
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
        for domain, kind, line_kind, header, footer in _GROUNDED_V2_STATE_SEGMENTS:
            domain_entries = self._domain_entries(selected_state, domain)
            if not domain_entries:
                continue
            semantic_domain = domain in (_DOMAIN_RELATIONSHIP, _DOMAIN_PSYCHOLOGY)
            items.append(
                AssemblyItem(
                    kind,
                    self._domain_block(
                        header, footer, domain_entries,
                        dimension_set=dimension_set, domain=domain,
                    ),
                    {
                        "domain": domain,
                        "entry_count": len(domain_entries),
                        "source": "OPERATOR_CONFIRMED",
                        "semantics": (
                            "PACKAGE_DEFINED"
                            if (semantic_domain and dimension_set is not None)
                            else "RAW"
                        ),
                    },
                )
            )
            for entry in domain_entries:
                meta = {
                    "domain": entry.get("domain"),
                    "key": entry.get("key"),
                    "seq": entry.get("seq"),
                    "event_id": entry.get("event_id"),
                    "source_kind": entry.get("source_kind"),
                }
                if semantic_domain and dimension_set is not None:
                    interp = interpret_state_entry(
                        domain, entry.get("key", ""), entry.get("value", ""), dimension_set
                    )
                    if interp is not None and interp.band is not None:
                        meta["band"] = interp.band.value
                        meta["semantic_meaning"] = interp.meaning
                items.append(
                    AssemblyItem(
                        line_kind,
                        self._state_line(
                            entry, dimension_set=dimension_set, domain=domain
                        ),
                        meta,
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
        if selected_consolidated:
            items.append(
                AssemblyItem(
                    "system.consolidated_memory",
                    self._consolidated_block(selected_consolidated),
                    {
                        "record_count": len(selected_consolidated),
                        "epistemic_kind": "USER_REPORT",
                        "order": "seq",
                        "conflict_count": sum(
                            1 for r in selected_consolidated if r.get("in_conflict")
                        ),
                    },
                )
            )
            for r in selected_consolidated:
                items.append(
                    AssemblyItem(
                        "system.consolidated_memory_line",
                        self._consolidated_line(r),
                        {
                            "record_id": r.get("record_id"),
                            "source_event_id": r.get("source_event_id"),
                            "basis_event_ids": list(r.get("basis_event_ids") or []),
                            "epistemic_kind": r.get("epistemic_kind"),
                            "provenance": r.get("provenance"),
                            "memory_kind": r.get("memory_kind"),
                            "holder_id": r.get("holder_id"),
                            "in_conflict": bool(r.get("in_conflict")),
                            "seq": r.get("seq"),
                            "provenance_display": "user-reported (remembered)",
                        },
                    )
                )
        if epistemic_extra:
            stats = epistemic_stats or {}
            items.append(
                AssemblyItem(
                    "system.epistemic_context",
                    self._epistemic_block(epistemic_extra),
                    {
                        "line_count": len(epistemic_extra),
                        "at_seq": stats.get("at_seq"),
                        "perceiver_id": stats.get("perceiver_id"),
                        "kinds": sorted({e.epistemic_kind.value for e in epistemic_extra}),
                        "raw_hidden_by_visibility": stats.get("raw_hidden_by_visibility"),
                        "consolidated_hidden_by_visibility": stats.get(
                            "consolidated_hidden_by_visibility"
                        ),
                        "raw_dropped_exact_source_dedup": stats.get(
                            "raw_dropped_exact_source_dedup"
                        ),
                        "visibility_source": "CHARACTER_CORE_SELECTOR",
                    },
                )
            )
            for env in epistemic_extra:
                items.append(
                    AssemblyItem(
                        "system.epistemic_context_line",
                        self._epistemic_line(env),
                        {
                            "epistemic_kind": env.epistemic_kind.value,
                            "basis_event_ids": list(env.basis_event_ids),
                            "provenance": env.provenance,
                            "holder_id": env.holder_id,
                            "confidence": env.confidence,
                            "valid_from_seq": env.valid_from_seq,
                            "valid_to_seq": env.valid_to_seq,
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
