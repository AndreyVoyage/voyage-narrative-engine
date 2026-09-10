#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Product-facing IMAGE_GENERATION readiness (Slice D).

A small, **provider-call-free** verdict the Companion UI shows before offering
"Создать изображение..." / "Кадр по контексту". It inspects only:

* the stored IMAGE_GENERATION role assignment,
* the provider/model registry (capabilities are authoritative; UNKNOWN is never
  upgraded to TRUE),
* whether the provider credential is present (through the existing secure vault
  seam -- never decrypted here),
* whether the character has an ACTIVE local visual snapshot.

It performs no network I/O and never exposes a credential, an Authorization
header, a filesystem path, or a Canon path. `unverified=True` preserves the
registry fact that a configured model has not been live-verified -- this module
never performs that verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .provider_registry import (
    CAP_CHARACTER_REFERENCE,
    CAP_IMAGE_TO_IMAGE,
    MODEL_UNVERIFIED,
    ROLE_IMAGE_GENERATION,
    ProviderRegistryError,
    require_model_supported,
)
from .provider_resolution import (
    READINESS_CREDENTIAL_MISSING,
    READINESS_NOT_CONFIGURED,
    READINESS_UNSUPPORTED,
    resolve_role_config,
)

STATUS_READY = "READY"
STATUS_ROLE_UNASSIGNED = "ROLE_UNASSIGNED"
STATUS_PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
STATUS_MODEL_UNSUPPORTED = "MODEL_UNSUPPORTED"
STATUS_CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
STATUS_REFERENCE_CONDITIONING_UNSUPPORTED = "REFERENCE_CONDITIONING_UNSUPPORTED"
STATUS_UNVERIFIED_CAPABILITY = "UNVERIFIED_CAPABILITY"
STATUS_ACTIVE_SNAPSHOT_MISSING = "ACTIVE_SNAPSHOT_MISSING"

ALL_STATUSES = (
    STATUS_READY,
    STATUS_ROLE_UNASSIGNED,
    STATUS_PROVIDER_NOT_CONFIGURED,
    STATUS_MODEL_UNSUPPORTED,
    STATUS_CREDENTIAL_MISSING,
    STATUS_REFERENCE_CONDITIONING_UNSUPPORTED,
    STATUS_UNVERIFIED_CAPABILITY,
    STATUS_ACTIVE_SNAPSHOT_MISSING,
)

#: status -> stable frontend i18n key (the UI maps these to localized copy)
_MESSAGE_KEY = {
    STATUS_READY: "image.readiness.ready",
    STATUS_ROLE_UNASSIGNED: "image.readiness.roleUnassigned",
    STATUS_PROVIDER_NOT_CONFIGURED: "image.readiness.providerNotConfigured",
    STATUS_MODEL_UNSUPPORTED: "image.readiness.modelUnsupported",
    STATUS_CREDENTIAL_MISSING: "image.readiness.credentialMissing",
    STATUS_REFERENCE_CONDITIONING_UNSUPPORTED: "image.readiness.referenceUnsupported",
    STATUS_UNVERIFIED_CAPABILITY: "image.readiness.unverifiedCapability",
    STATUS_ACTIVE_SNAPSHOT_MISSING: "image.readiness.activeSnapshotMissing",
}


@dataclass(frozen=True)
class ImageGenerationReadiness:
    status: str
    ready: bool
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    #: registry says the configured model is not live-verified (still usable)
    unverified: bool = False
    reason_code: Optional[str] = None
    message_key: str = "image.readiness.ready"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "ready": self.ready,
            "providerId": self.provider_id,
            "modelId": self.model_id,
            "unverified": self.unverified,
            "reasonCode": self.reason_code,
            "messageKey": self.message_key,
        }


def _blocked(status: str, provider_id: Optional[str] = None, model_id: Optional[str] = None) -> ImageGenerationReadiness:
    return ImageGenerationReadiness(
        status=status,
        ready=False,
        provider_id=provider_id,
        model_id=model_id,
        reason_code=status,
        message_key=_MESSAGE_KEY[status],
    )


def evaluate_image_generation_readiness(
    settings,
    vault,
    *,
    snapshot_store=None,
    character_id: Optional[str] = None,
) -> ImageGenerationReadiness:
    """Compute readiness without any provider/network call.

    ``settings`` / ``vault`` are the existing Companion ``CompanionSettings`` and
    ``CredentialVault``; either being ``None`` means "no configured role".
    ``snapshot_store`` + ``character_id`` add the per-character active-snapshot
    check (both required for it to run).
    """
    if settings is None or vault is None:
        return _blocked(STATUS_ROLE_UNASSIGNED)

    rc = resolve_role_config(ROLE_IMAGE_GENERATION, settings, vault)
    provider_id = rc.get("providerId")
    model_id = rc.get("modelId")
    readiness = rc.get("readiness")

    if not provider_id or not model_id or readiness == READINESS_NOT_CONFIGURED:
        return _blocked(STATUS_ROLE_UNASSIGNED)
    if readiness == READINESS_UNSUPPORTED:
        return _blocked(STATUS_MODEL_UNSUPPORTED, provider_id, model_id)
    if readiness == READINESS_CREDENTIAL_MISSING or (
        rc.get("credentialRequired") and not rc.get("providerConnected")
    ):
        return _blocked(STATUS_CREDENTIAL_MISSING, provider_id, model_id)

    try:
        _entry, model = require_model_supported(provider_id, model_id, ROLE_IMAGE_GENERATION)
    except ProviderRegistryError:
        return _blocked(STATUS_MODEL_UNSUPPORTED, provider_id, model_id)

    # Companion character generation is reference-conditioned: the model must be
    # able to take reference images. Explicit False blocks; UNKNOWN is allowed
    # only when a capability flag backs it (never upgraded to TRUE).
    if model.supports_reference_image is False:
        return _blocked(STATUS_REFERENCE_CONDITIONING_UNSUPPORTED, provider_id, model_id)
    ref_ok = (
        model.supports_reference_image is True
        or model.supports_image_to_image is True
        or CAP_IMAGE_TO_IMAGE in model.capabilities
        or CAP_CHARACTER_REFERENCE in model.capabilities
    )
    if not ref_ok:
        return _blocked(STATUS_UNVERIFIED_CAPABILITY, provider_id, model_id)

    if character_id and snapshot_store is not None:
        try:
            active = snapshot_store.read_active_version(character_id)
        except Exception:  # noqa: BLE001 -- a corrupt pointer is "no usable snapshot"
            active = None
        if not active:
            return _blocked(STATUS_ACTIVE_SNAPSHOT_MISSING, provider_id, model_id)

    return ImageGenerationReadiness(
        status=STATUS_READY,
        ready=True,
        provider_id=provider_id,
        model_id=model_id,
        unverified=(model.status == MODEL_UNVERIFIED),
        reason_code=None,
        message_key=_MESSAGE_KEY[STATUS_READY],
    )
