#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""``RealCompanionImageGenerator`` -- the backend that plugs the Slice B visual
pipeline + the Slice C provider adapter into the EXISTING
:class:`~services.character_companion.image_jobs.ImageJobService` lifecycle.

It conforms exactly to the existing ``CompanionImageGenerator`` protocol
(``advance(job, *, images_dir) -> ImageJob``):

* ``QUEUED`` -> ``GENERATING``  -- no provider call, no visual work.
* ``GENERATING`` -> load the creation-time pinned ``CharacterLocalSnapshot`` ->
  load the exact pinned references -> build ``VisualContext`` -> render physical block ->
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
from ..character_import.canon_status import is_production_approved
from ..character_import.hashing import compute_sha256
from ..character_import.reference_importer import sniff_image_format
from ..character_import.reference_manifest import is_valid_relative_path
from ..credentials import CredentialError, CredentialVault
from ..image_readiness import evaluate_image_generation_readiness
from ..image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    PinnedGenerationSpec,
    STATE_FAILED,
    STATE_GENERATING,
    STATE_QUEUED,
    STATE_READY,
    ImageJob,
)
from ..provider_registry import ROLE_IMAGE_GENERATION, get_provider
from ..provider_resolution import resolve_role_config
from ..settings import CompanionSettings, RoleAssignment
from .context import REQUEST_KIND_CONTEXT, REQUEST_KIND_CUSTOM, build_visual_context
from .image_provider_adapter import ImageProviderAdapter
from .prompt import build_visual_prompt
from .provider_errors import (
    ImageGenerationConfigurationError, ImageGenerationError, ImageGenerationResultError,
    ImageGenerationTransportError,
)
from .provider_model import CONTENT_TYPE_TO_EXTENSION, DEFAULT_SIZE, ImageGenerationRequest
from .reference_bundle import build_reference_bundle, validate_reference_bundle_integrity
from .reference_model import (
    FILE_TYPE_TO_CONTENT_TYPE,
    REFERENCE_BUNDLE_SCHEMA_VERSION,
    ReferenceBundle,
    ReferenceEntry,
)

_EFFECTIVE_CONDITIONED_QUALITY = "low"
_FORMAT_KEY_TO_FILE_TYPE = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


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
        if job.state not in (STATE_QUEUED, STATE_GENERATING):
            return job                                        # terminal -> untouched
        try:
            spec = self._pinned_spec(job)
            if job.state == STATE_QUEUED:
                return _advanced(job, state=STATE_GENERATING)  # validated spec, no provider call
            return self._generate(job, spec=spec, images_dir=Path(images_dir))
        except ImageGenerationError as exc:
            if isinstance(exc, ImageGenerationTransportError) and exc.diagnostic is not None:
                context = dict(job.context or {})
                context["failure"] = exc.diagnostic.to_dict()
                return _advanced(job, state=STATE_FAILED, error=exc.code, context=context)
            return _advanced(job, state=STATE_FAILED, error=str(getattr(exc, "code", "image_generation_failed")))
        except Exception as exc:  # noqa: BLE001 -- bounded; never leak internals/secrets
            code = getattr(exc, "code", exc.__class__.__name__)
            return _advanced(job, state=STATE_FAILED, error=str(code))

    def prepare_generation_spec(self, *, character_id: str) -> PinnedGenerationSpec:
        """Pin the approved identity pack and effective provider request inputs.

        This runs before ``ImageJobService.create_job`` persists QUEUED. It is
        provider-call-free and never resolves the credential value.
        """
        settings = self._settings_store.load()
        readiness = evaluate_image_generation_readiness(
            settings,
            self._vault,
            snapshot_store=self._snapshots,
            character_id=character_id,
        )
        if not readiness.ready:
            code_by_status = {
                "ROLE_UNASSIGNED": "image_generation_role_unassigned",
                "PROVIDER_NOT_CONFIGURED": "image_generation_role_unassigned",
                "MODEL_UNSUPPORTED": "image_generation_unsupported_provider",
                "CREDENTIAL_MISSING": "image_generation_credential_missing",
                "REFERENCE_CONDITIONING_UNSUPPORTED": "image_generation_unsupported_provider",
                "UNVERIFIED_CAPABILITY": "image_generation_unsupported_provider",
                "ACTIVE_SNAPSHOT_MISSING": "image_generation_active_snapshot_missing",
            }
            raise ImageGenerationConfigurationError(
                f"image generation is not ready ({readiness.status})",
                code=code_by_status.get(readiness.status, "image_generation_not_configured"),
            )

        provider_id = (readiness.provider_id or "").strip()
        model_id = (readiness.model_id or "").strip()
        try:
            snapshot = self._snapshots.load_active_snapshot(character_id)
        except Exception as exc:
            raise ImageGenerationConfigurationError(
                f"no usable active local snapshot for {character_id!r}",
                code="image_generation_active_snapshot_missing",
            ) from exc
        if not is_production_approved(str(snapshot.source_canon.get("status") or "")):
            raise ImageGenerationConfigurationError(
                "active visual snapshot is not approved for production",
                code="image_generation_snapshot_not_approved",
            )

        snapshot_dir = self._snapshots.version_dir(character_id, snapshot.snapshot_version)
        reference_bundle = build_reference_bundle(snapshot=snapshot, snapshot_dir=snapshot_dir)
        validate_reference_bundle_integrity(reference_bundle)
        base_url = settings.base_urls.get(provider_id) or get_provider(provider_id).default_base_url
        return PinnedGenerationSpec.from_inputs(
            snapshot=snapshot,
            reference_bundle=reference_bundle,
            provider_id=provider_id,
            model_id=model_id,
            base_url=base_url,
            size=self._size,
            quality=self._quality or _EFFECTIVE_CONDITIONED_QUALITY,
        )

    # ----------------------------------------------------------- internals
    def _generate(
        self, job: ImageJob, *, spec: PinnedGenerationSpec, images_dir: Path
    ) -> ImageJob:
        snapshot = self._load_pinned_snapshot(job, spec)
        snapshot_dir = self._snapshots.version_dir(job.character_id, spec.snapshot_version)

        visual_context = self._build_context(job, snapshot)
        reference_bundle = self._build_pinned_reference_bundle(
            snapshot=snapshot, snapshot_dir=snapshot_dir, spec=spec
        )
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
            character_snapshot_version=spec.snapshot_version,
            prompt_text=package.prompt_text,
            provider_id=spec.provider_id,
            model_id=spec.model_id,
            endpoint_kind=endpoint_kind,
            size=spec.size,
            quality=spec.quality,
        )

        pinned_settings = CompanionSettings(
            roles={ROLE_IMAGE_GENERATION: RoleAssignment(spec.provider_id, spec.model_id)}
        )
        role_config = resolve_role_config(
            ROLE_IMAGE_GENERATION, pinned_settings, self._vault
        )
        api_key = self._resolve_key(role_config, spec.provider_id)

        try:
            image = self._adapter.generate(
                request=request,
                reference_bundle=reference_bundle,
                role_config=role_config,
                base_url=spec.base_url,
                api_key=api_key,
            )
        except ImageGenerationTransportError as exc:
            if exc.diagnostic is None:
                raise
            # Идентичность вызова берём из уже разрешённой роли, не из ответа.
            diagnostic = replace(
                exc.diagnostic, provider=spec.provider_id, model=spec.model_id,
                secrets=(api_key, job.prompt or "", package.prompt_text),
            )
            raise ImageGenerationTransportError(
                "image provider HTTP request failed", diagnostic=diagnostic
            ) from None

        result_ref = self._persist(images_dir, job.job_id, image)
        context = dict(job.context or {})
        context["result"] = {
            "provider": spec.provider_id,
            "model": image.model,
            "endpointKind": endpoint_kind,
            "payloadSha256": image.payload_sha256,
            "visualPromptHash": package.content_hash,
            "visualContextHash": package.visual_context_hash,
            "referenceBundleHash": package.reference_bundle_hash,
            "snapshotVersion": spec.snapshot_version,
        }
        return _advanced(job, state=STATE_READY, result_ref=result_ref, error=None, context=context)

    @staticmethod
    def _pinned_spec(job: ImageJob) -> PinnedGenerationSpec:
        raw = (job.context or {}).get("generationSpec")
        if raw is None:
            raise ImageGenerationConfigurationError(
                "legacy non-terminal image job has no pinned generation specification",
                code="generation_spec_missing",
            )
        try:
            spec = PinnedGenerationSpec.from_dict(raw)
        except (TypeError, ValueError) as exc:
            raise ImageGenerationConfigurationError(
                "pinned generation specification is invalid",
                code="generation_spec_invalid",
            ) from exc
        if spec.character_id != job.character_id:
            raise ImageGenerationConfigurationError(
                "pinned generation specification character mismatch",
                code="generation_spec_invalid",
            )
        return spec

    def _load_pinned_snapshot(
        self, job: ImageJob, spec: PinnedGenerationSpec
    ) -> CharacterLocalSnapshot:
        try:
            snapshot = self._snapshots.load_snapshot(job.character_id, spec.snapshot_version)
        except Exception as exc:
            raise ImageGenerationConfigurationError(
                "pinned visual snapshot is missing or invalid",
                code="generation_spec_snapshot_invalid",
            ) from exc
        actual_hash = snapshot.snapshot_hash or snapshot.compute_hash()
        source = snapshot.source_canon
        source_matches = (
            source.get("status") == spec.source_canon_status
            and source.get("contentHash") == spec.source_canon_content_hash
            and source.get("sourceHash") == spec.source_canon_source_hash
            and source.get("sourceCharacterId") == spec.source_canon_character_id
        )
        if actual_hash != spec.snapshot_hash or not source_matches:
            raise ImageGenerationConfigurationError(
                "pinned visual snapshot provenance changed",
                code="generation_spec_snapshot_mismatch",
            )
        if not is_production_approved(spec.source_canon_status):
            raise ImageGenerationConfigurationError(
                "pinned visual snapshot is not approved for production",
                code="image_generation_snapshot_not_approved",
            )
        return snapshot

    @staticmethod
    def _build_pinned_reference_bundle(
        *, snapshot: CharacterLocalSnapshot, snapshot_dir: Path,
        spec: PinnedGenerationSpec,
    ) -> ReferenceBundle:
        """Load the exact pinned entries without invoking reference selection."""
        by_id = {ref.asset_id: ref for ref in snapshot.references}
        root = Path(snapshot_dir).resolve()
        entries: list[ReferenceEntry] = []
        for pinned in spec.references:
            current = by_id.get(pinned.asset_id)
            if current is None or (
                tuple(current.roles) != pinned.roles
                or current.relative_path != pinned.relative_path
                or current.sha256 != pinned.sha256
                or current.file_type != pinned.file_type
                or current.byte_length != pinned.byte_length
                or current.source_semantic_key != pinned.source_semantic_key
            ):
                raise ImageGenerationConfigurationError(
                    f"pinned reference metadata changed for {pinned.asset_id!r}",
                    code="generation_spec_reference_mismatch",
                )
            if not is_valid_relative_path(pinned.relative_path):
                raise ImageGenerationConfigurationError(
                    f"unsafe pinned reference path for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                )
            full = (Path(snapshot_dir) / pinned.relative_path).resolve()
            try:
                full.relative_to(root)
            except ValueError:
                raise ImageGenerationConfigurationError(
                    f"pinned reference escapes snapshot for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                ) from None
            try:
                payload = full.read_bytes()
            except OSError as exc:
                raise ImageGenerationConfigurationError(
                    f"pinned reference missing for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                ) from exc
            if len(payload) != pinned.byte_length or compute_sha256(payload) != pinned.sha256:
                raise ImageGenerationConfigurationError(
                    f"pinned reference integrity mismatch for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                )
            fmt = sniff_image_format(payload)
            if fmt is None or _FORMAT_KEY_TO_FILE_TYPE.get(fmt) != pinned.file_type:
                raise ImageGenerationConfigurationError(
                    f"pinned reference format mismatch for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                )
            content_type = FILE_TYPE_TO_CONTENT_TYPE.get(pinned.file_type)
            if content_type is None:
                raise ImageGenerationConfigurationError(
                    f"unsupported pinned reference type for {pinned.asset_id!r}",
                    code="generation_spec_reference_invalid",
                )
            entries.append(ReferenceEntry(
                character_id=spec.character_id,
                asset_id=pinned.asset_id,
                roles=pinned.roles,
                relative_path=pinned.relative_path,
                sha256=pinned.sha256,
                byte_length=pinned.byte_length,
                image_format=pinned.file_type,
                content_type=content_type,
                payload=payload,
                source_semantic_key=pinned.source_semantic_key,
            ))
        bundle = ReferenceBundle(
            schema_version=REFERENCE_BUNDLE_SCHEMA_VERSION,
            character_id=spec.character_id,
            character_snapshot_version=spec.snapshot_version,
            references=tuple(entries),
            content_hash="",
        )
        object.__setattr__(bundle, "content_hash", bundle.compute_hash())
        return bundle

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
