#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-release identity + manifest for the Windows KIRA Companion.

- `COMPANION_MODE` distinguishes `dev` (fake provider allowed) from `release`
  (a real DIALOGUE provider must be configured -- no silent FakeKIRA).
- `build_release_manifest` produces a small, machine-readable descriptor of the
  release candidate: app / Core / contract versions, the accepted KIRA package
  identity + hash, runtime prerequisites, and where non-secret provider config
  lives. It NEVER contains an API key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.character_core.release import (
    CONTRACT_VERSION as CORE_CONTRACT_VERSION,
    CORE_NAME,
    CORE_VERSION,
)

from .catalog import build_default_catalog

RELEASE_NAME = "KIRA Companion MVP RC1"
RELEASE_VERSION = "0.1.0-rc1"
RELEASE_CHANNEL = "release-candidate"

MODE_DEV = "dev"
MODE_RELEASE = "release"
COMPANION_MODES = (MODE_DEV, MODE_RELEASE)

#: Real KIRA Grounded request size observed in LOCAL_LLM_PROVIDER_V1 evidence
#: (qwen3:4b-instruct rejected ~10014 prompt tokens against a 4096 window).
#: Used only for a conservative UI hint -- not a precise token claim.
KIRA_GROUNDED_OBSERVED_PROMPT_TOKENS = 10014

_SECRET_KEYS = ("api_key", "apikey", "secret", "credential", "authorization", "token", "bearer")


class ReleaseManifestError(RuntimeError):
    pass


def normalize_mode(value: Optional[str]) -> str:
    m = (value or MODE_DEV).strip().lower()
    if m not in COMPANION_MODES:
        raise ReleaseManifestError(f"COMPANION_MODE must be one of {COMPANION_MODES}, got {value!r}")
    return m


def _assert_no_secret(obj) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in _SECRET_KEYS:
                raise ReleaseManifestError("release manifest must never contain a credential")
            _assert_no_secret(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_secret(v)


def build_release_manifest(
    *,
    acceptance_root,
    frontend_build_id: Optional[str] = None,
    provider_config_source: str = "companion_settings.json (+ OS credential vault)",
) -> dict:
    acceptance_root = Path(acceptance_root)
    catalog = build_default_catalog(acceptance_root)
    kira = catalog.get("kira")
    if kira is None or not kira.available:
        raise ReleaseManifestError("accepted KIRA package did not resolve; cannot assemble a release manifest")

    manifest = {
        "release": {
            "name": RELEASE_NAME,
            "version": RELEASE_VERSION,
            "channel": RELEASE_CHANNEL,
        },
        "characterCore": {
            "name": CORE_NAME,
            "version": CORE_VERSION,
            "contractVersion": CORE_CONTRACT_VERSION,
        },
        "acceptedCharacter": {
            "characterId": kira.character_id,
            "displayName": kira.display_name,
            "subjectId": kira.subject_id,
            "packageId": kira.package_id,
            "packageVersion": kira.package_version,
            "sourceHash": kira.source_hash,
        },
        "frontendBuildId": frontend_build_id,
        "runtimePrerequisites": [
            "Windows 10/11 (x64)",
            "Python 3.11+ on PATH (`py`)",
            "A built Companion frontend (apps/character_companion_react/dist)",
            "For a real character reply: a configured DIALOGUE provider "
            "(Local Ollama on 127.0.0.1, or a cloud key stored in the OS vault)",
        ],
        "providerConfigSource": provider_config_source,
        "localContext": {
            "kiraGroundedObservedPromptTokens": KIRA_GROUNDED_OBSERVED_PROMPT_TOKENS,
            "recommendedMinNumCtx": 16384,
            "note": "Наблюдённый размер запроса KIRA Grounded ~10k токенов; "
                    "рекомендуемый минимум num_ctx для локальной модели — 16384.",
        },
        "dataLocationNote": "Пользовательские данные (диалоги, память, состояние, "
                            "настройки, зашифрованный ключ) хранятся в стабильном каталоге "
                            "данных вне каталога сборки; пересборка фронтенда их не затрагивает.",
        "secrets": "none",
    }
    _assert_no_secret(manifest)
    return manifest
