#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secure desktop credential vault for Character Companion.

A user-supplied provider API key is stored ONLY here, encrypted at rest, and is
resolved in-process solely to build a provider request. It is never written to
the Companion settings JSON, the conversation DB, logs, error text, debug
manifests, and is never returned to the frontend after being saved.

Platform-neutral interface: :class:`CredentialVault` (Protocol). Windows
implementation: :class:`WindowsDpapiCredentialVault` -- per-user DPAPI
(``CryptProtectData`` / ``CryptUnprotectData`` via ``ctypes``, no third-party
dependency). Future adapters (macOS Keychain, Android Keystore, iOS Keychain)
implement the same interface. Tests use :class:`InMemoryCredentialVault`.

There is NO plaintext-file fallback: if secure storage is unavailable the
factory raises rather than degrading.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Protocol

__all__ = [
    "CredentialError",
    "CredentialMetadata",
    "CredentialVault",
    "InMemoryCredentialVault",
    "WindowsDpapiCredentialVault",
    "build_default_credential_vault",
    "mask_tail",
]

_VAULT_FILENAME = "companion_credentials.dpapi.json"
_MIN_SECRET_LEN = 8
_MAX_SECRET_LEN = 8192


class CredentialError(RuntimeError):
    """Deterministic, secret-free credential-vault error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CredentialMetadata:
    """Everything the frontend is ever allowed to see about a stored key."""

    provider_id: str
    connected: bool
    masked_tail: Optional[str] = None
    last_test_status: Optional[str] = None


def mask_tail(secret: str) -> str:
    """A safe, non-reversible hint: the last 4 characters only."""
    s = secret.strip()
    return ("…" + s[-4:]) if len(s) >= 8 else "…"


def _validate_secret(secret: str) -> str:
    if not isinstance(secret, str):
        raise CredentialError("invalid_secret", "secret must be a string")
    s = secret.strip()
    if not (_MIN_SECRET_LEN <= len(s) <= _MAX_SECRET_LEN):
        raise CredentialError("invalid_secret", "secret length is outside the accepted range")
    return s


def _validate_provider_id(provider_id: str) -> str:
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise CredentialError("invalid_request", "provider_id must be a non-empty string")
    pid = provider_id.strip().lower()
    if not pid.replace("-", "").replace("_", "").isalnum():
        raise CredentialError("invalid_request", f"unsafe provider_id {provider_id!r}")
    return pid


class CredentialVault(Protocol):
    def store(self, provider_id: str, secret: str) -> CredentialMetadata: ...
    def has(self, provider_id: str) -> bool: ...
    def delete(self, provider_id: str) -> bool: ...
    def resolve(self, provider_id: str) -> str: ...
    def metadata(self, provider_id: str) -> CredentialMetadata: ...
    def list_metadata(self) -> Dict[str, CredentialMetadata]: ...


# --------------------------------------------------------------- in-memory
class InMemoryCredentialVault:
    """Test/dev vault. Secrets live only in this process's memory; never
    written to disk. Not for production (``build_default_credential_vault``
    never returns this)."""

    def __init__(self) -> None:
        self._secrets: Dict[str, str] = {}
        self._status: Dict[str, str] = {}

    def store(self, provider_id: str, secret: str) -> CredentialMetadata:
        pid = _validate_provider_id(provider_id)
        self._secrets[pid] = _validate_secret(secret)
        return self.metadata(pid)

    def has(self, provider_id: str) -> bool:
        return _validate_provider_id(provider_id) in self._secrets

    def delete(self, provider_id: str) -> bool:
        pid = _validate_provider_id(provider_id)
        existed = self._secrets.pop(pid, None) is not None
        self._status.pop(pid, None)
        return existed

    def resolve(self, provider_id: str) -> str:
        pid = _validate_provider_id(provider_id)
        if pid not in self._secrets:
            raise CredentialError("missing_credential", f"no stored credential for {pid!r}")
        return self._secrets[pid]

    def set_test_status(self, provider_id: str, status: str) -> None:
        self._status[_validate_provider_id(provider_id)] = status

    def metadata(self, provider_id: str) -> CredentialMetadata:
        pid = _validate_provider_id(provider_id)
        connected = pid in self._secrets
        return CredentialMetadata(
            provider_id=pid,
            connected=connected,
            masked_tail=mask_tail(self._secrets[pid]) if connected else None,
            last_test_status=self._status.get(pid),
        )

    def list_metadata(self) -> Dict[str, CredentialMetadata]:
        return {pid: self.metadata(pid) for pid in self._secrets}


# --------------------------------------------------------------- Windows DPAPI
def _dpapi_available() -> bool:
    return sys.platform == "win32" and hasattr(__import__("ctypes"), "windll")


def _dpapi_protect(plaintext: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data: bytes) -> _BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    src = _blob(plaintext)
    out = _BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x1  -- never show UI
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(src), "companion-credential", None, None, None, 0x1, ctypes.byref(out)
    ):
        raise CredentialError("vault_unavailable", "DPAPI CryptProtectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(ciphertext, len(ciphertext))
    src = _BLOB(len(ciphertext), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out)
    ):
        raise CredentialError("vault_unavailable", "DPAPI CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


class WindowsDpapiCredentialVault:
    """Per-user DPAPI-encrypted key store. The on-disk file holds only opaque
    DPAPI ciphertext (base64) keyed by provider_id -- never a plaintext key."""

    def __init__(self, data_root: Path) -> None:
        if not _dpapi_available():  # pragma: no cover - platform guard
            raise CredentialError(
                "vault_unavailable",
                "Windows DPAPI is not available on this platform; secure storage required",
            )
        self._path = Path(data_root) / _VAULT_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._status_path = self._path.with_suffix(".status.json")

    # ---- file io ----
    def _load_blobs(self) -> Dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}

    def _save_blobs(self, blobs: Dict[str, str]) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(blobs, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def _load_status(self) -> Dict[str, str]:
        if not self._status_path.exists():
            return {}
        try:
            data = json.loads(self._status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}

    def _save_status(self, status: Dict[str, str]) -> None:
        tmp = self._status_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._status_path)

    # ---- interface ----
    def store(self, provider_id: str, secret: str) -> CredentialMetadata:
        pid = _validate_provider_id(provider_id)
        s = _validate_secret(secret)
        blobs = self._load_blobs()
        blobs[pid] = base64.b64encode(_dpapi_protect(s.encode("utf-8"))).decode("ascii")
        self._save_blobs(blobs)
        return self.metadata(pid)

    def has(self, provider_id: str) -> bool:
        return _validate_provider_id(provider_id) in self._load_blobs()

    def delete(self, provider_id: str) -> bool:
        pid = _validate_provider_id(provider_id)
        blobs = self._load_blobs()
        existed = blobs.pop(pid, None) is not None
        if existed:
            self._save_blobs(blobs)
        status = self._load_status()
        if status.pop(pid, None) is not None:
            self._save_status(status)
        return existed

    def resolve(self, provider_id: str) -> str:
        pid = _validate_provider_id(provider_id)
        blobs = self._load_blobs()
        if pid not in blobs:
            raise CredentialError("missing_credential", f"no stored credential for {pid!r}")
        return _dpapi_unprotect(base64.b64decode(blobs[pid])).decode("utf-8")

    def set_test_status(self, provider_id: str, status: str) -> None:
        pid = _validate_provider_id(provider_id)
        st = self._load_status()
        st[pid] = str(status)[:32]
        self._save_status(st)

    def metadata(self, provider_id: str) -> CredentialMetadata:
        pid = _validate_provider_id(provider_id)
        connected = self.has(pid)
        tail = None
        if connected:
            try:
                tail = mask_tail(self.resolve(pid))
            except CredentialError:
                tail = None
        return CredentialMetadata(
            provider_id=pid, connected=connected, masked_tail=tail,
            last_test_status=self._load_status().get(pid),
        )

    def list_metadata(self) -> Dict[str, CredentialMetadata]:
        return {pid: self.metadata(pid) for pid in self._load_blobs()}


def build_default_credential_vault(data_root) -> CredentialVault:
    """The production vault. Windows DPAPI only; never a plaintext fallback."""
    if _dpapi_available():
        return WindowsDpapiCredentialVault(Path(data_root))
    raise CredentialError(  # pragma: no cover - platform guard
        "vault_unavailable",
        "no secure OS credential store available on this platform",
    )
