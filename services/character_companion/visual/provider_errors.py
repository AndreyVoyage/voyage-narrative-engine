#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded backend errors for the IMAGE_GENERATION provider boundary (Slice C).

Adapted from ``services/image_provider_boundary/errors.py`` in the VNE repo
(single root, config-before-network / transport / result split). Renamed to a
Companion ``ImageGeneration*`` prefix and given one extra member
(``ImageGenerationUnsupportedProviderError``) for the registry capability gate.

Error strings may carry logical provider / model / job identifiers. They MUST
NEVER carry a credential, an ``Authorization`` header, reference bytes, an
absolute local path, or a Character Canon path.
"""

from __future__ import annotations

import re
from dataclasses import InitVar, dataclass


_WITHHELD_MESSAGE = "Provider error details withheld."
_MAX_MESSAGE_LENGTH = 400
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_SENSITIVE_TEXT = re.compile(
    r"authorization|bearer|api[ _-]?key|credential|secret|password|"
    r"\bsk-[A-Za-z0-9_-]+|multipart|content-disposition|base64|b64_json|"
    r"\b(?:prompt|request[ _-]?body|image\[\])\s*[:=]|"
    r"[/\\<>]|[A-Za-z0-9+_=\-]{32,}|[A-Za-z0-9+_\-]{8,}={1,2}|iVBORw0KGgo|UklGR",
    re.IGNORECASE,
)


def _safe_error_text(
    value: object, *, secrets: tuple[str, ...] = (), identifier: bool = False,
) -> str | None:
    """Консервативный allowlist: сомнительное поле целиком скрывается.

    Проверка идёт до усечения, чтобы не сохранить начало секрета/пути.
    Неизвестные объекты никогда не преобразуются через str/repr.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    if any(secret and secret in value for secret in secrets):
        return None if identifier else _WITHHELD_MESSAGE
    if identifier:
        # invalid_api_key — безопасный код, а не значение credential.
        if _IDENTIFIER.fullmatch(value) and not re.search(r"sk-|[A-Za-z0-9_-]{32,}", value, re.I):
            return value
        return None
    if _SENSITIVE_TEXT.search(value):
        return _WITHHELD_MESSAGE
    if any(not char.isprintable() and not char.isspace() for char in value):
        return _WITHHELD_MESSAGE
    return " ".join(value.split())[:_MAX_MESSAGE_LENGTH]


@dataclass(frozen=True)
class ImageHTTPFailureDiagnostic:
    """Только безопасные поля HTTP-ошибки; сырой ответ и секреты не хранятся."""

    http_status: int
    provider_error_code: str | None = None
    provider_error_type: str | None = None
    provider_message: str | None = None
    provider: str | None = None
    model: str | None = None
    secrets: InitVar[tuple[str, ...]] = ()

    def __post_init__(self, secrets: tuple[str, ...]) -> None:
        if type(self.http_status) is not int or not 100 <= self.http_status <= 599:
            raise ValueError("invalid provider HTTP status")
        for field in ("provider_error_code", "provider_error_type", "provider", "model"):
            object.__setattr__(self, field, _safe_error_text(getattr(self, field), secrets=secrets, identifier=True))
        object.__setattr__(self, "provider_message", _safe_error_text(self.provider_message, secrets=secrets))

    def to_dict(self) -> dict:
        fields = {
            "provider": self.provider,
            "model": self.model,
            "httpStatus": self.http_status,
            "providerErrorCode": self.provider_error_code,
            "providerErrorType": self.provider_error_type,
            "providerMessage": self.provider_message,
        }
        return {key: value for key, value in fields.items() if value is not None}


class ImageGenerationError(RuntimeError):
    """Root of the Companion image-generation backend exception hierarchy.

    Carries a short, stable ``code`` for the job-failure record.
    """

    code = "image_generation_failed"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ImageGenerationConfigurationError(ImageGenerationError):
    """A required input is missing / invalid BEFORE any network access:
    role unassigned, credential absent, no active local snapshot, bad size."""

    code = "image_generation_not_configured"


class ImageGenerationUnsupportedProviderError(ImageGenerationConfigurationError):
    """The resolved provider/model cannot serve this request per the Companion
    registry (model lacks IMAGE_GENERATION, or a conditioned request was made
    to a model whose reference-image capability is explicitly unsupported)."""

    code = "image_generation_unsupported_provider"


class ImageGenerationTransportError(ImageGenerationError):
    """HTTP / connection / JSON transport failure. Terminal: the adapter never
    retries and never issues a second generation."""

    code = "image_generation_transport_failed"

    def __init__(
        self, message: str, *, code: str | None = None,
        diagnostic: ImageHTTPFailureDiagnostic | None = None,
    ) -> None:
        super().__init__(_safe_error_text(message) or "image provider transport failed", code=code)
        self.diagnostic = diagnostic


class ImageGenerationResultError(ImageGenerationError):
    """The provider response carried no single decodable in-band image
    (zero / many results, a URL-only result, malformed base64, empty bytes,
    or an unrecognised image format)."""

    code = "image_generation_result_invalid"
