#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic compact renderer for Accepted Character grounding (Grounded v2).

Projects an ``AcceptedCharacter.package`` into a plain-text grounding block that
``GroundedV2Policy`` injects as its own system segment. It uses ONLY the
distilled candidate sections plus ``contradictions`` and ``unknowns`` -- never
the raw ``claims`` collection, never an LLM, never invented facts. Output is a
pure deterministic function of the frozen package: same package -> same string.

Design rules (KIRA_GROUNDED_V2):

- no raw JSON dump;
- no fabricated facts (every line is verbatim package text);
- no LLM selection;
- empty candidate maps / empty sections are omitted (no boilerplate);
- contradictions are preserved, never resolved;
- unknowns are preserved as "not established", never rewritten to a stronger
  claim.
"""

from __future__ import annotations

from typing import Any

#: One-line marker so the block is unmistakably Accepted Character grounding.
GROUNDING_HEADER = "ПРИНЯТЫЙ ПЕРСОНАЖ / ACCEPTED CHARACTER GROUNDING"

_GROUNDING_PREAMBLE = (
    "Ниже — принятое (Accepted) описание персонажа: только достоверно принятые "
    "сведения из утверждённого пакета. Опирайся на них.\n"
    "Разделы «НЕИЗВЕСТНО / НЕ УСТАНОВЛЕНО» и «ПРОТИВОРЕЧИЯ» очерчивают границы "
    "знания: не превращай их в утверждаемые факты и ничего не выдумывай сверх "
    "принятого описания."
)

# (package attribute, human section label). Fixed, deterministic order.
_CANDIDATE_SECTIONS = (
    ("identity_biography_candidate", "БИОГРАФИЯ И ЛИЧНОСТЬ / IDENTITY & BIOGRAPHY"),
    ("psychology_candidate", "ПСИХОЛОГИЯ / PSYCHOLOGY"),
    ("behavior_candidate", "ПОВЕДЕНИЕ / BEHAVIOR"),
    ("relationships_candidate", "ОТНОШЕНИЯ / RELATIONSHIPS"),
    ("boundaries_candidate", "ГРАНИЦЫ / BOUNDARIES"),
    ("intimacy_candidate", "ИНТИМНОСТЬ / INTIMACY"),
    ("voice_candidate", "РЕЧЬ / VOICE"),
)

# Non-canonical confidence gets a compact honest marker so a lower-confidence
# line is never read as an established fact.
_CONFIDENCE_SUFFIX = {
    "PROBABLE": " (вероятно)",
    "POSSIBLE": " (возможно)",
    "CONTRADICTORY": " (спорно)",
    "UNKNOWN": " (не установлено)",
}


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))


def _claim_text(claim: Any) -> str:
    return str(getattr(claim, "claim", "")).strip()


def _claim_line(claim: Any) -> str:
    suffix = _CONFIDENCE_SUFFIX.get(_enum_value(getattr(claim, "confidence", "")), "")
    return f"- {_claim_text(claim)}{suffix}"


def _render_candidate_map(mapping: Any) -> list:
    lines: list = []
    for section in sorted(mapping.keys()):
        rendered: list = []
        seen: set = set()
        for claim in mapping[section]:
            text = _claim_text(claim)
            if not text or text in seen:
                continue
            seen.add(text)
            rendered.append(_claim_line(claim))
        if rendered:
            lines.append(f"[{section}]")
            lines.extend(rendered)
    return lines


def render_accepted_grounding(package: Any) -> str:
    """Return the deterministic Accepted Character grounding block."""
    parts: list = [
        GROUNDING_HEADER,
        "",
        (
            f"Источник: package_id={package.package_id}, "
            f"package_version={package.package_version}, "
            f"status={_enum_value(package.status)}."
        ),
        _GROUNDING_PREAMBLE,
    ]

    for attr, label in _CANDIDATE_SECTIONS:
        mapping = getattr(package, attr, {}) or {}
        body = _render_candidate_map(mapping)
        if body:
            parts.append("")
            parts.append(f"## {label}")
            parts.extend(body)

    contradictions = tuple(getattr(package, "contradictions", ()) or ())
    if contradictions:
        parts.append("")
        parts.append(
            "## ПРОТИВОРЕЧИЯ / CONTRADICTIONS (держать оба полюса, не разрешать)"
        )
        for record in sorted(
            contradictions, key=lambda x: getattr(x, "contradiction_id", "")
        ):
            parts.append(f"- {str(getattr(record, 'description', '')).strip()}")

    unknowns = tuple(getattr(package, "unknowns", ()) or ())
    if unknowns:
        parts.append("")
        parts.append(
            "## НЕИЗВЕСТНО / НЕ УСТАНОВЛЕНО (не выдумывать как факт)"
        )
        for unknown in sorted(unknowns, key=lambda x: getattr(x, "claim_id", "")):
            parts.append(f"- {str(getattr(unknown, 'claim', '')).strip()}")

    return "\n".join(parts)


def grounding_char_length(package: Any) -> int:
    """Approximate rendered character length of the grounding block."""
    return len(render_accepted_grounding(package))
