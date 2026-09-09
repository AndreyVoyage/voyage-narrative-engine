#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-secret Companion settings, persisted to ``companion_settings.json``.

Holds provider selection + model id per role, base-URL overrides, local
``num_ctx``, and UI preferences. It NEVER holds an API key -- keys live only in
the :mod:`credentials` vault. Atomic write; a missing or malformed file loads
as safe defaults; unknown keys are dropped.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .provider_registry import (
    ALL_ROLES,
    ROLE_DIALOGUE,
    get_provider,
    is_known_provider,
    is_known_role,
)

_SETTINGS_FILENAME = "companion_settings.json"

# Local context bounds -- deliberately modest; no giant default.
NUM_CTX_MIN = 512
NUM_CTX_MAX = 131072
#: Below this the KIRA Grounded request is likely to be truncated.
NUM_CTX_KIRA_SAFE_HINT = 16384

_FORBIDDEN_KEYS = frozenset({"api_key", "apikey", "secret", "credential", "authorization", "token"})


class SettingsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RoleAssignment:
    provider_id: str
    model_id: str


@dataclass
class CompanionSettings:
    # role -> assignment (only DIALOGUE is runtime-wired this release)
    roles: Dict[str, RoleAssignment] = field(default_factory=dict)
    # provider_id -> base URL override
    base_urls: Dict[str, str] = field(default_factory=dict)
    local_num_ctx: Optional[int] = None
    # explicit; NEVER auto-enabled. Foundation only.
    allow_cloud_fallback: bool = False
    ui: Dict[str, str] = field(default_factory=dict)

    # ---------------------------------------------------------- defaults
    @classmethod
    def defaults(cls) -> "CompanionSettings":
        return cls(roles={ROLE_DIALOGUE: RoleAssignment("fake", "fake")})

    def dialogue(self) -> RoleAssignment:
        return self.roles.get(ROLE_DIALOGUE, RoleAssignment("fake", "fake"))

    # ---------------------------------------------------------- (de)serialize
    def to_row(self) -> dict:
        return {
            "version": 1,
            "roles": {r: {"providerId": a.provider_id, "modelId": a.model_id} for r, a in self.roles.items()},
            "baseUrls": dict(self.base_urls),
            "localNumCtx": self.local_num_ctx,
            "allowCloudFallback": bool(self.allow_cloud_fallback),
            "ui": dict(self.ui),
        }

    @classmethod
    def from_row(cls, data) -> "CompanionSettings":
        if not isinstance(data, dict):
            return cls.defaults()
        base = cls.defaults()
        roles: Dict[str, RoleAssignment] = dict(base.roles)
        raw_roles = data.get("roles")
        if isinstance(raw_roles, dict):
            for role, a in raw_roles.items():
                if not is_known_role(role) or not isinstance(a, dict):
                    continue
                pid = str(a.get("providerId") or "").strip().lower()
                mid = str(a.get("modelId") or "").strip()
                if is_known_provider(pid) and mid:
                    roles[role] = RoleAssignment(pid, mid)
        base_urls: Dict[str, str] = {}
        raw_urls = data.get("baseUrls")
        if isinstance(raw_urls, dict):
            for pid, url in raw_urls.items():
                if is_known_provider(pid) and isinstance(url, str) and url.strip():
                    base_urls[str(pid).strip().lower()] = url.strip()
        num_ctx = data.get("localNumCtx")
        if not (isinstance(num_ctx, int) and not isinstance(num_ctx, bool) and NUM_CTX_MIN <= num_ctx <= NUM_CTX_MAX):
            num_ctx = None
        ui = {str(k): str(v) for k, v in (data.get("ui") or {}).items()
              if isinstance(k, str) and str(k).lower() not in _FORBIDDEN_KEYS}
        return cls(
            roles=roles,
            base_urls=base_urls,
            local_num_ctx=num_ctx,
            allow_cloud_fallback=bool(data.get("allowCloudFallback", False)),
            ui=ui,
        )


def _assert_no_secret(row: dict) -> None:
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if str(k).lower() in _FORBIDDEN_KEYS:
                    raise SettingsError("secret_in_settings", "settings must never contain a credential")
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(row)


class SettingsStore:
    def __init__(self, data_root: Path) -> None:
        self._path = Path(data_root) / _SETTINGS_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> CompanionSettings:
        if not self._path.exists():
            return CompanionSettings.defaults()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return CompanionSettings.defaults()   # malformed -> safe defaults
        return CompanionSettings.from_row(data)

    def save(self, settings: CompanionSettings) -> CompanionSettings:
        row = settings.to_row()
        _assert_no_secret(row)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
        return self.load()

    def set_role(self, role: str, provider_id: str, model_id: str) -> CompanionSettings:
        if not is_known_role(role):
            raise SettingsError("unknown_role", f"unknown model role {role!r}")
        if not is_known_provider(provider_id):
            raise SettingsError("unknown_provider", f"unknown provider {provider_id!r}")
        entry = get_provider(provider_id)
        if role not in entry.supported_roles:
            raise SettingsError("unsupported_role", f"provider {entry.provider_id!r} does not support {role!r}")
        model_id = (model_id or entry.default_model).strip()
        settings = self.load()
        settings.roles[role] = RoleAssignment(entry.provider_id, model_id)
        return self.save(settings)

    def set_local_num_ctx(self, num_ctx: Optional[int]) -> CompanionSettings:
        if num_ctx is not None:
            if isinstance(num_ctx, bool) or not isinstance(num_ctx, int) or num_ctx <= 0:
                raise SettingsError("invalid_num_ctx", "num_ctx must be a positive integer")
            if not (NUM_CTX_MIN <= num_ctx <= NUM_CTX_MAX):
                raise SettingsError("invalid_num_ctx", f"num_ctx must be within [{NUM_CTX_MIN}, {NUM_CTX_MAX}]")
        settings = self.load()
        settings.local_num_ctx = num_ctx
        return self.save(settings)

    def set_base_url(self, provider_id: str, base_url: Optional[str]) -> CompanionSettings:
        if not is_known_provider(provider_id):
            raise SettingsError("unknown_provider", f"unknown provider {provider_id!r}")
        settings = self.load()
        pid = provider_id.strip().lower()
        if base_url and base_url.strip():
            settings.base_urls[pid] = base_url.strip()
        else:
            settings.base_urls.pop(pid, None)
        return self.save(settings)
