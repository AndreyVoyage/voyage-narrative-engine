#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""``RealCompanionImageGenerator`` -- the backend that plugs the Slice B visual
pipeline + the Slice C provider adapter into the EXISTING
:class:`~services.character_companion.image_jobs.ImageJobService` lifecycle.

It conforms exactly to the existing ``CompanionImageGenerator`` protocol
(``advance(job, *, images_dir) -> ImageJob``):

* ``QUEUED`` -> ``GENERATING``  -- no provider call, no visual work.
* ``GENERATING`` -> load active ``CharacterLocalSnapshot`` -> build
  ``VisualContext`` -> build ``ReferenceBundle`` -> render physical block ->
  build ``VisualPromptPackage`` -> exactly ONE ``ImageProviderAdapter.generate``
  -> persist bytes under ``images_dir`` -> ``READY``.
* any failure -> ``FAILED`` with a bounded code. No retry. No fallback.

Construction is explicit-dependency (no globals). This class is NOT the default
release generator -- ``ImageJobService`` still defaults to
``UnavailableImageGenerator`` until Slice D wires product readiness.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..character_import.local_snapshot import CharacterLocalSnapshot, SnapshotStore
from ..credentials import CredentialError, CredentialVault
from ..image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    ImageJob,
)
from ..provider_registry import ROLE_IMAGE_GENERATION, get_provider
from ..provider_resolution import resolve_role_config
from .context import REQUEST_KIND_CONTEXT, REQUEST_KIND_CUSTOM, build_visual_context
from .image_provider_adapter import ImageProviderAdapter
from .prompt import build_visual_prompt
from .provider_errors import (
    ImageGenerationConfigurationError, ImageGenerationError, ImageGenerationResultError,
    ImageGenerationTransportError,
)
from .provider_model import CONTENT_TYPE_TO_EXTENSION, DEFAULT_SIZE, ImageGenerationRequest
from .reference_bundle import build_reference_bundle, validate_reference_bundle_integrity


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _advanced(job: ImageJob, **changes) -> ImageJob:
    row = job.to_row()
    row.update(changes)
    row["updated_at"] = _now_iso()
    return ImageJob.from_row(row)


class RealCompanionImageGenerator:
    """Real, network-capable image generator. Bind explicitly; never a default."""

    name = "real-openai-compat"

    def __init__(
        self,
        *,
        data_root: Path,
        settings_store,
        credential_vault: CredentialVault,
        adapter: ImageProviderAdapter,
        snapshot_store: Optional[SnapshotStore] = None,
        size: str = DEFAULT_SIZE,
        quality: Optional[str] = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._settings_store = settings_store
        self._vault = credential_vault
        self._adapter = adapter
        self._snapshots = snapshot_store or SnapshotStore(self._data_root)
        self._size = size
        self._quality = quality

    # ----------------------------------------------------------- protocol
    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        if job.state == STATE_QUEUED:
            return _advanced(job, state=STATE_GENERATING)     # no provider call
        if job.state != STATE_GENERATING:
            return job                                        # terminal -> untouched
        try:
            return self._generate(job, images_dir=Path(images_dir))
        except ImageGenerationError as exc:
            if isinstance(exc, ImageGenerationTransportError) and exc.diagnostic is not None:
                context = dict(job.context or {})
                context["failure"] = exc.diagnostic.to_dict()
                return _advanced(job, state=STATE_FAILED, error=exc.code, context=context)
            return _advanced(job, state=STATE_FAILED, error=str(getattr(exc, "code", "image_generation_failed")))
        except Exception as exc:  # noqa: BLE001 -- bounded; never leak internals/secrets
            code = getattr(exc, "code", exc.__class__.__name__)
            return _advanced(job, state=STATE_FAILED, error=str(code))

    # ----------------------------------------------------------- internals
    def _generate(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        settings = self._settings_store.load()
        role_config = resolve_role_config(ROLE_IMAGE_GENERATION, settings, self._vault)

        provider_id = (role_config.get("providerId") or "").strip()
        model_id = (role_config.get("modelId") or "").strip()
        if not provider_id or not model_id:
            raise ImageGenerationConfigurationError(
                "no IMAGE_GENERATION model is assigned", code="image_generation_role_unassigned"
            )

        snapshot = self._load_active_snapshot(job.character_id)
        snapshot_dir = self._snapshots.version_dir(job.character_id, snapshot.snapshot_version)

        visual_context = self._build_context(job, snapshot)
        reference_bundle = build_reference_bundle(snapshot=snapshot, snapshot_dir=snapshot_dir)
        validate_reference_bundle_integrity(reference_bundle)

        package = build_visual_prompt(
            visual_context=visual_context,
            reference_bundle=reference_bundle,
            physical=snapshot.physical,
            alias=job.character_id,
        )

        endpoint_kind = "conditioned" if reference_bundle.references else "text"
        request = ImageGenerationRequest(
            character_id=job.character_id,
            character_snapshot_version=snapshot.snapshot_version,
            prompt_text=package.prompt_text,
            provider_id=provider_id,
            model_id=model_id,
            endpoint_kind=endpoint_kind,
            size=self._size,
            quality=self._quality,
        )

        base_url = settings.base_urls.get(provider_id) or get_provider(provider_id).default_base_url
        api_key = self._resolve_key(role_config, provider_id)

        try:
            image = self._adapter.generate(
                request=request,
                reference_bundle=reference_bundle,
                role_config=role_config,
                base_url=base_url,
                api_key=api_key,
            )
        except ImageGenerationTransportError as exc:
            if exc.diagnostic is None:
                raise
            # Идентичность вызова берём из уже разрешённой роли, не из ответа.
            diagnostic = replace(
                exc.diagnostic, provider=provider_id, model=model_id,
                secrets=(api_key, job.prompt or "", package.prompt_text),
            )
            raise ImageGenerationTransportError(
                "image provider HTTP request failed", diagnostic=diagnostic
            ) from None

        result_ref = self._persist(images_dir, job.job_id, image)
        context = dict(job.context or {})
        context["result"] = {
            "provider": provider_id,
            "model": image.model,
            "endpointKind": endpoint_kind,
            "payloadSha256": image.payload_sha256,
            "visualPromptHash": package.content_hash,
            "visualContextHash": package.visual_context_hash,
            "referenceBundleHash": package.reference_bundle_hash,
            "snapshotVersion": snapshot.snapshot_version,
        }
        return _advanced(job, state=STATE_READY, result_ref=result_ref, error=None, context=context)

    def _load_active_snapshot(self, character_id: str) -> CharacterLocalSnapshot:
        try:
            return self._snapshots.load_active_snapshot(character_id)
        except Exception as exc:  # SnapshotError family -- fail closed, no Canon fallback
            raise ImageGenerationConfigurationError(
                f"no usable active local snapshot for {character_id!r}",
                code="image_generation_active_snapshot_missing",
            ) from exc

    def _build_context(self, job: ImageJob, snapshot: CharacterLocalSnapshot):
        if job.kind == KIND_CUSTOM:
            return build_visual_context(
                snapshot=snapshot,
                request_kind=REQUEST_KIND_CUSTOM,
                explicit_description=job.prompt,
            )
        if job.kind == KIND_CONTEXT:
            ctx = job.context or {}
            return build_visual_context(
                snapshot=snapshot,
                request_kind=REQUEST_KIND_CONTEXT,
                scene=ctx.get("scene"),
                recent_messages=ctx.get("recentMessages"),
            )
        raise ImageGenerationConfigurationError(f"unsupported image job kind {job.kind!r}")

    def _resolve_key(self, role_config: dict, provider_id: str) -> str:
        if not role_config.get("credentialRequired"):
            return ""
        try:
            return self._vault.resolve(provider_id)
        except CredentialError as exc:
            raise ImageGenerationConfigurationError(
                f"no stored credential for provider {provider_id!r}",
                code="image_generation_credential_missing",
            ) from exc

    def _persist(self, images_dir: Path, job_id: str, image) -> str:
        ext = CONTENT_TYPE_TO_EXTENSION.get(image.content_type)
        if ext is None:
            raise ImageGenerationResultError(
                f"unsupported result content type {image.content_type!r}"
            )
        if not image.payload:
            raise ImageGenerationResultError("generated image payload is empty")
        images_dir.mkdir(parents=True, exist_ok=True)
        final = images_dir / f"{job_id}.{ext}"
        staging = images_dir / f".{job_id}.{uuid.uuid4().hex}.tmp"
        try:
            staging.write_bytes(image.payload)
            os.replace(staging, final)
        finally:
            if staging.exists():
                staging.unlink(missing_ok=True)
        return f"images/{job_id}.{ext}"
