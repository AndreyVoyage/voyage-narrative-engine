#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAC v0 service -- core orchestration.

Coordinates Gateway context retrieval, provider calls, ФМДР validation,
and the three-level approval state machine.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Optional

from .contracts import (
    PacApprovalEvent,
    PacApprovalLevel,
    PacGeneration,
    PacRequest,
    PacTrainingExample,
    PacVariant,
    generate_run_id,
    new_uuid,
    utc_now_iso,
    validate_fmdr,
)
from .errors import (
    PacApprovalError,
    PacFmdrError,
    PacGatewayError,
    PacProviderError,
)
from .gateway_adapter import GatewayAdapter
from .storage import PacStorage

# Allowed variant counts
_ALLOWED_VARIANT_COUNTS = frozenset({2, 3})

# Default provider callable (imported lazily to avoid circular deps)
_DEFAULT_PROVIDER_CALLABLE = None


def _get_default_provider():
    global _DEFAULT_PROVIDER_CALLABLE
    if _DEFAULT_PROVIDER_CALLABLE is None:
        from tools.llm_provider import complete as _complete

        _DEFAULT_PROVIDER_CALLABLE = _complete
    return _DEFAULT_PROVIDER_CALLABLE


class PacService:
    """PAC v0 authoring orchestration.

    Dependencies are injected: Gateway adapter, provider callable,
    and storage backend.  This makes the service testable with fakes.
    """

    def __init__(
        self,
        gateway: GatewayAdapter,
        provider_callable: Optional[Callable[..., str]] = None,
        storage: Optional[PacStorage] = None,
    ) -> None:
        self._gateway = gateway
        self._provider = provider_callable or _get_default_provider()
        self._storage = storage or PacStorage()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def gateway(self) -> GatewayAdapter:
        return self._gateway

    @property
    def storage(self) -> PacStorage:
        return self._storage

    # -- Generation ----------------------------------------------------

    def generate(self, request: PacRequest) -> PacGeneration:
        """Generate 2-3 scene variants for one target persona.

        Steps:
        1. Validate variant count.
        2. Retrieve canon context through Gateway.
        3. Assemble provider request.
        4. Call provider with explicit provider/model.
        5. Parse variants from response.
        6. Validate ФМДР for each variant.
        7. Return immutable generation evidence.
        """
        if request.variant_count not in _ALLOWED_VARIANT_COUNTS:
            raise PacFmdrError(
                f"variant_count must be 2 or 3, got {request.variant_count}"
            )

        # Retrieve canon context.
        canon_snapshot = self._gateway.build_canon_snapshot(
            request.character_id, request.level
        )
        authoring_context = self._gateway.get_authoring_context(
            request.character_id, request.level
        )

        # Assemble system prompt.
        system_prompt = _assemble_system_prompt(request, authoring_context)

        # Build user message requesting 2-3 ФМДР variants.
        user_message = _assemble_user_message(request)

        # Call provider explicitly.
        try:
            raw_response = self._provider(
                messages=[{"role": "user", "content": user_message}],
                provider=request.provider,
                model=request.model,
                system=system_prompt,
                params=None,
            )
        except Exception as exc:
            raise PacProviderError(
                f"provider call failed: {exc}"
            ) from exc

        # Parse and validate variants.
        variants = _parse_variants(raw_response, request.variant_count)

        run_id = generate_run_id()
        created_at = utc_now_iso()

        generation = PacGeneration(
            run_id=run_id,
            request=request,
            variants=tuple(variants),
            created_at=created_at,
            canon_snapshot=canon_snapshot,
            system_prompt=system_prompt,
        )

        # Persist raw evidence.
        self._storage.save_raw(generation)
        # Create initial run manifest.
        self._storage.save_run_manifest(
            run_id,
            {
                "run_id": run_id,
                "created_at": created_at,
                "character_id": request.character_id,
                "approval_state": "generated",
            },
        )

        return generation

    # -- Approvals -----------------------------------------------------

    def accept_draft(
        self, run_id: str, variant_index: int, approved_output: str
    ) -> PacApprovalEvent:
        """Accept one variant as a working draft (ACCEPT_DRAFT).

        Effects:
        - Saves draft evidence.
        - Updates run manifest.
        - Does NOT write to dataset or canon.
        """
        _require_generation_exists(self._storage, run_id)
        _require_not_already(self._storage, run_id, "draft")

        # Validate variant index.
        raw = self._storage.load_raw(run_id)
        variant_count = len(raw.get("variants", []))
        if variant_index < 0 or variant_index >= variant_count:
            raise PacApprovalError(
                f"variant_index {variant_index} out of range "
                f"[0, {variant_count})"
            )

        # Save draft.
        self._storage.save_draft(run_id, variant_index, approved_output)
        self._storage.save_run_manifest(
            run_id,
            {
                "run_id": run_id,
                "approval_state": "draft_accepted",
                "variant_index": variant_index,
                "accepted_at": utc_now_iso(),
            },
        )

        return PacApprovalEvent(
            run_id=run_id,
            level=PacApprovalLevel.ACCEPT_DRAFT,
            variant_index=variant_index,
        )

    def approve_scene(self, run_id: str) -> PacApprovalEvent:
        """Approve the accepted draft for scene use (APPROVE_SCENE).

        Effects:
        - Saves approved scene evidence.
        - Updates run manifest.
        - Does NOT write to dataset or canon.
        """
        _require_draft_exists(self._storage, run_id)
        _require_not_already(self._storage, run_id, "scene")

        draft = self._storage.load_draft(run_id)
        raw = self._storage.load_raw(run_id)

        scene_data = {
            "run_id": run_id,
            "character_id": raw["request"]["character_id"],
            "level": raw["request"]["level"],
            "situation": raw["request"]["situation"],
            "approved_output": draft["approved_output"],
            "approved_at": utc_now_iso(),
        }
        self._storage.save_approved_scene(run_id, scene_data)
        self._storage.save_run_manifest(
            run_id,
            {
                "run_id": run_id,
                "approval_state": "scene_approved",
                "scene_approved_at": utc_now_iso(),
            },
        )

        return PacApprovalEvent(
            run_id=run_id,
            level=PacApprovalLevel.APPROVE_SCENE,
        )

    def approve_dataset(
        self,
        run_id: str,
        provenance: str = "human-edited",
        authoring_session_id: Optional[str] = None,
    ) -> PacApprovalEvent:
        """Approve the scene for dataset inclusion (APPROVE_DATASET).

        Effects:
        - Validates schema preconditions.
        - Builds a ``PacTrainingExample``.
        - Appends one idempotent record to ``training_dataset.jsonl``.
        - Does NOT write to canon.

        This is the ONLY action that writes to the dataset.
        Idempotent: repeated calls for the same run_id do not append
        duplicate lines (storage enforces this by example_id).
        """
        _require_scene_approved(self._storage, run_id)
        # Allow re-approval at dataset level (idempotent).
        # Only block if state is BEFORE scene_approved.
        manifest = {}
        if self._storage.run_manifest_exists(run_id):
            manifest = self._storage.load_run_manifest(run_id)
        current = manifest.get("approval_state", "generated")
        # "generated" and "draft_accepted" must not reach here.
        if current in ("generated", "draft_accepted"):
            raise PacApprovalError(
                f"cannot approve dataset: run {run_id!r} is at state {current!r}"
            )

        draft = self._storage.load_draft(run_id)
        raw = self._storage.load_raw(run_id)
        scene = self._storage.load_approved_scene(run_id)

        request_data = raw["request"]
        variant_index = draft["variant_index"]
        variants = raw["variants"]
        variant = variants[variant_index]

        # Reuse existing example_id when this run was already dataset-approved
        existing_example_id = manifest.get("example_id")
        example_id = existing_example_id or new_uuid()
        session_id = authoring_session_id or new_uuid()

        # The approved output is the training target.
        approved_output = draft["approved_output"]

        # Determine was_edited from provenance.
        was_edited = provenance != "model-raw-approved"

        example = PacTrainingExample(
            example_id=example_id,
            created_at=utc_now_iso(),
            character_id=request_data["character_id"],
            scene_id=None,
            authoring_session_id=session_id,
            provider=request_data["provider"],
            model=request_data["model"],
            canon_snapshot=raw["canon_snapshot"],
            context={
                "level": request_data["level"],
                "situation": request_data["situation"],
                "author_instruction": request_data["author_instruction"],
                "fmdr_required": True,
            },
            model_output_raw=variant["raw_text"],
            approved_output=approved_output,
            provenance=provenance,
            edit_metrics={"was_edited": was_edited},
            gates={
                "fmdr_valid": variant["fmdr_valid"],
                "speech_uniqueness_pass": True,
                "canon_reviewed_by_human": True,
            },
        )

        # Validate enum values.
        enum_errors = example.validate_enum_values()
        if enum_errors:
            raise PacApprovalError(
                f"dataset record validation failed: {'; '.join(enum_errors)}"
            )

        # Append to dataset (idempotent).
        self._storage.append_dataset(example)

        self._storage.save_run_manifest(
            run_id,
            {
                "run_id": run_id,
                "approval_state": "dataset_approved",
                "dataset_approved_at": utc_now_iso(),
                "example_id": example_id,
            },
        )

        return PacApprovalEvent(
            run_id=run_id,
            level=PacApprovalLevel.APPROVE_DATASET,
            example_id=example_id,
        )

    # -- Query ---------------------------------------------------------

    def get_approval_state(self, run_id: str) -> str:
        """Return the current approval state for a run.

        Returns one of: ``"generated"``, ``"draft_accepted"``,
        ``"scene_approved"``, ``"dataset_approved"``, or ``"unknown"``.
        """
        if self._storage.run_manifest_exists(run_id):
            manifest = self._storage.load_run_manifest(run_id)
            return manifest.get("approval_state", "generated")
        if self._storage.dataset_contains(run_id):
            return "dataset_approved"
        return "unknown"

    def list_characters(self) -> list[dict[str, str]]:
        """List all available characters through Gateway."""
        return self._gateway.list_characters()


# ----------------------------------------------------------------------
# Prompt assembly
# ----------------------------------------------------------------------


def _assemble_system_prompt(
    request: PacRequest, context: dict
) -> str:
    """Build a deterministic system prompt from canon context.

    The system prompt describes the character using Gateway data and
    instructs the model to produce exactly 2-3 ФМДР variants.
    """
    manifest = context.get("manifest", {})
    modules = context.get("modules", {})

    char_name = manifest.get("name", request.character_id)

    lines = [
        f'Ты — {char_name} (персонаж из вселенной Voyage Narrative Engine).',
        "",
        "Твоя задача: написать ровно {count} варианта реплики/сцены от лица персонажа "
        "в строгом формате ФМДР.".format(count=request.variant_count),
        "",
        "Формат каждого варианта:",
        "  (Мысли: внутренний монолог) → *Действия: описание* → «Речь: прямая речь»",
        "",
        "Каждый вариант начинается с заголовка:",
        "  Вариант 1",
        "  Вариант 2",
        "  Вариант 3",
        "",
        "Ситуация: {situation}".format(situation=request.situation),
        "Указание автора: {instruction}".format(instruction=request.author_instruction),
        "",
    ]

    if modules:
        lines.append("--- Контекст персонажа из канона ---")
        lines.append("")
        for module_id, module_data in sorted(modules.items()):
            if isinstance(module_data, dict):
                lines.append(
                    "[{mod}]: {data}".format(
                        mod=module_id,
                        data=json.dumps(module_data, ensure_ascii=False, indent=2),
                    )
                )
                lines.append("")
        lines.append("--- Конец контекста ---")

    return "\n".join(lines)


def _assemble_user_message(request: PacRequest) -> str:
    """Build the user message for the provider."""
    return (
        "Сгенерируй ровно {count} варианта сцены в формате ФМДР.\n"
        "\n"
        "Уровень: {level}\n"
        "Ситуация: {situation}\n"
        "Инструкция: {instruction}\n"
        "\n"
        "Каждый вариант должен начинаться с заголовка 'Вариант N' и содержать "
        "строки (Мысли: ...), *Действия: ...*, «Речь: ...».".format(
            count=request.variant_count,
            level=request.level,
            situation=request.situation,
            instruction=request.author_instruction,
        )
    )


# ----------------------------------------------------------------------
# Variant parsing
# ----------------------------------------------------------------------


def _parse_variants(raw_response: str, expected_count: int) -> list[PacVariant]:
    """Split raw response into numbered variants and validate each.

    Variants are expected to be separated by 'Вариант N' headers.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise PacFmdrError("provider returned empty response")

    # Split on "Вариант N" headers.
    import re

    parts = re.split(r"(?:^|\n)\s*Вариант\s+(\d+)", raw_response.strip())
    # parts[0] is text before first header (empty or prologue)
    # parts[1] is first number, parts[2] is first variant text, etc.

    variants_found: list[tuple[int, str]] = []
    i = 0
    # Skip prologue if present (part before first numbered variant).
    if parts and parts[0].strip():
        # Text before first variant -- skip.
        i = 1

    while i + 1 < len(parts):
        try:
            num = int(parts[i].strip())
        except (ValueError, IndexError):
            i += 1
            continue
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        variants_found.append((num, text))
        i += 2

    if not variants_found:
        raise PacFmdrError(
            "no numbered variants found in provider response; "
            "expected headers like 'Вариант 1', 'Вариант 2', 'Вариант 3'"
        )

    if len(variants_found) != expected_count:
        raise PacFmdrError(
            f"expected {expected_count} variants, found {len(variants_found)}"
        )

    result: list[PacVariant] = []
    for idx, (num, text) in enumerate(variants_found):
        valid, thoughts, actions, speech, error = validate_fmdr(text)
        result.append(
            PacVariant(
                index=idx,
                raw_text=text,
                fmdr_valid=valid,
                thoughts=thoughts,
                actions=actions,
                speech=speech,
                fmdr_error=error,
            )
        )

    return result


# ----------------------------------------------------------------------
# Approval state-machine helpers
# ----------------------------------------------------------------------


def _require_generation_exists(storage: PacStorage, run_id: str) -> None:
    """Raise ``PacApprovalError`` when no raw generation exists for ``run_id``."""
    try:
        storage.load_raw(run_id)
    except Exception:
        raise PacApprovalError(
            f"no generation found for run_id {run_id!r}; run generate first"
        ) from None


def _require_draft_exists(storage: PacStorage, run_id: str) -> None:
    """Raise when no accepted draft exists."""
    if not storage.draft_exists(run_id):
        raise PacApprovalError(
            f"no accepted draft for run_id {run_id!r}; run accept-draft first"
        )


def _require_scene_approved(storage: PacStorage, run_id: str) -> None:
    """Raise when no approved scene exists."""
    if not storage.scene_approved(run_id):
        raise PacApprovalError(
            f"no approved scene for run_id {run_id!r}; run approve-scene first"
        )


def _require_not_already(
    storage: PacStorage, run_id: str, next_step: str
) -> None:
    """Raise when the next approval step has already been completed."""
    manifest = {}
    if storage.run_manifest_exists(run_id):
        manifest = storage.load_run_manifest(run_id)
    current = manifest.get("approval_state", "generated")

    order = {
        "generated": 0,
        "draft_accepted": 1,
        "scene_approved": 2,
        "dataset_approved": 3,
    }

    target_order = {
        "draft": 1,
        "scene": 2,
        "dataset": 3,
    }

    current_order = order.get(current, -1)
    needed = target_order.get(next_step, -1)

    if current_order >= needed:
        raise PacApprovalError(
            f"cannot perform {next_step!r} approval: run {run_id!r} "
            f"is already at state {current!r}"
        )