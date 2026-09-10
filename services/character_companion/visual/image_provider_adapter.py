#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion-owned IMAGE_GENERATION provider adapter (Slice C).

One adapter, one provider, one model, one transport call -- NO fallback, NO
implicit alternate provider, NO retry. The provider/model come from the
existing Companion role resolver (:func:`resolve_role_config`) and the existing
registry capability table is authoritative. The credential is an explicit
argument; the adapter never opens the vault and never reads an env var.

Routing:

* ``reference_bundle`` has entries  -> ``POST <base>/v1/images/edits`` multipart
* otherwise                         -> ``POST <base>/v1/images/generations`` JSON

Every configuration / capability failure is raised BEFORE the transport call,
so a rejected request performs exactly zero HTTP calls.
"""

from __future__ import annotations

from typing import Optional

from ..provider_registry import (
    CAP_CHARACTER_REFERENCE,
    CAP_IMAGE_TO_IMAGE,
    ROLE_IMAGE_GENERATION,
    ProviderRegistryError,
    require_model_supported,
)
from ..provider_resolution import (
    READINESS_CREDENTIAL_MISSING,
    READINESS_NOT_CONFIGURED,
    READINESS_UNSUPPORTED,
)
from .provider_errors import (
    ImageGenerationConfigurationError,
    ImageGenerationUnsupportedProviderError,
)
from .provider_model import ENDPOINT_CONDITIONED, ENDPOINT_TEXT, GeneratedImage, ImageGenerationRequest
from .provider_openai import (
    DEFAULT_TIMEOUT_S,
    ImageHttpPost,
    generate_conditioned_image,
    generate_text_to_image,
    reference_inputs_from_bundle,
)
from .reference_model import ReferenceBundle

# readiness verdicts that mean "assigned + credential present + model supports it".
# IMAGE_GENERATION is not a runtime-wired role, so resolve_role_config reports
# READINESS_FUTURE_NOT_WIRED for an otherwise-ready assignment -- that is the
# expected state for a media role invoked explicitly by an image job.
_ACCEPTABLE_READINESS = frozenset({"READY", "FUTURE_NOT_WIRED"})


class ImageProviderAdapter:
    def __init__(
        self, *, http_post: Optional[ImageHttpPost] = None, timeout_s: float = DEFAULT_TIMEOUT_S
    ) -> None:
        self._http_post = http_post
        self._timeout_s = timeout_s

    # -------------------------------------------------------------- generate
    def generate(
        self,
        *,
        request: ImageGenerationRequest,
        reference_bundle: Optional[ReferenceBundle],
        role_config: dict,
        base_url: str,
        api_key: str,
    ) -> GeneratedImage:
        if role_config.get("role") != ROLE_IMAGE_GENERATION:
            raise ImageGenerationConfigurationError("role_config is not for IMAGE_GENERATION")

        provider_id = (role_config.get("providerId") or "").strip()
        model_id = (role_config.get("modelId") or "").strip()
        readiness = role_config.get("readiness")

        if not provider_id or not model_id or readiness == READINESS_NOT_CONFIGURED:
            raise ImageGenerationConfigurationError(
                "no IMAGE_GENERATION model is assigned", code="image_generation_role_unassigned"
            )
        if readiness == READINESS_UNSUPPORTED:
            raise ImageGenerationUnsupportedProviderError(
                f"assigned model {provider_id}/{model_id} does not support IMAGE_GENERATION"
            )
        if readiness == READINESS_CREDENTIAL_MISSING or (
            role_config.get("credentialRequired") and not role_config.get("providerConnected")
        ):
            raise ImageGenerationConfigurationError(
                f"no stored credential for provider {provider_id!r}",
                code="image_generation_credential_missing",
            )
        if readiness not in _ACCEPTABLE_READINESS:
            raise ImageGenerationConfigurationError(
                f"IMAGE_GENERATION role is not ready ({readiness!r})"
            )

        if request.provider_id != provider_id or request.model_id != model_id:
            raise ImageGenerationConfigurationError(
                "request provider/model does not match the resolved IMAGE_GENERATION role"
            )
        if not (api_key or "").strip():
            raise ImageGenerationConfigurationError(
                f"no stored credential for provider {provider_id!r}",
                code="image_generation_credential_missing",
            )

        # the registry is authoritative for role + capability.
        try:
            _entry, model = require_model_supported(provider_id, model_id, ROLE_IMAGE_GENERATION)
        except ProviderRegistryError as exc:
            raise ImageGenerationUnsupportedProviderError(
                f"{provider_id}/{model_id}: {exc.code}"
            ) from exc

        refs = tuple(reference_bundle.references) if reference_bundle is not None else ()

        if refs:
            self._require_reference_capability(model, provider_id, model_id)
            inputs = reference_inputs_from_bundle(reference_bundle)  # type: ignore[arg-type]
            return generate_conditioned_image(
                prompt=request.prompt_text,
                model=model_id,
                api_key=api_key,
                base_url=base_url,
                references=inputs,
                size=request.size,
                quality=request.quality or "low",
                timeout_s=self._timeout_s,
                http_post=self._http_post,
            )

        return generate_text_to_image(
            prompt=request.prompt_text,
            model=model_id,
            api_key=api_key,
            base_url=base_url,
            size=request.size,
            quality=request.quality,
            timeout_s=self._timeout_s,
            http_post=self._http_post,
        )

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _require_reference_capability(model, provider_id: str, model_id: str) -> None:
        """Fail closed before transport when the registry says the model cannot
        take reference images. UNKNOWN (``None``) is only permitted when a
        capability flag (IMAGE_TO_IMAGE / CHARACTER_REFERENCE) is present -- it is
        never upgraded to TRUE, and an explicit ``False`` always rejects."""
        if model.supports_reference_image is False:
            raise ImageGenerationUnsupportedProviderError(
                f"model {provider_id}/{model_id} does not support reference images"
            )
        allowed = (
            model.supports_reference_image is True
            or model.supports_image_to_image is True
            or CAP_IMAGE_TO_IMAGE in model.capabilities
            or CAP_CHARACTER_REFERENCE in model.capabilities
        )
        if not allowed:
            raise ImageGenerationUnsupportedProviderError(
                f"model {provider_id}/{model_id} has no verified reference-image capability"
            )


def endpoint_kind_for(reference_bundle: Optional[ReferenceBundle]) -> str:
    """Which transport a request with this bundle will take."""
    refs = tuple(reference_bundle.references) if reference_bundle is not None else ()
    return ENDPOINT_CONDITIONED if refs else ENDPOINT_TEXT
