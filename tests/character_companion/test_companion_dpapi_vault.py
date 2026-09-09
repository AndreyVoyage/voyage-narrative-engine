#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows DPAPI credential vault -- round-trip, on-disk ciphertext, delete.

Windows-only (the production vault). No network, no external process. Writes an
encrypted blob file under a temp dir only."""

from __future__ import annotations

import json
import sys

import pytest

from services.character_companion import (
    CredentialError,
    WindowsDpapiCredentialVault,
    build_default_credential_vault,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")

SECRET = "sk-dpapi-test-VALUE-9f8e7d6c5b4a-secret"


def test_dpapi_round_trip_and_no_plaintext_on_disk(tmp_path):
    v = WindowsDpapiCredentialVault(tmp_path)
    assert not v.has("deepseek")
    meta = v.store("deepseek", SECRET)
    assert meta.connected and meta.masked_tail and SECRET not in (meta.masked_tail or "")
    assert v.resolve("deepseek") == SECRET

    # the on-disk file holds only opaque base64 DPAPI ciphertext, never the key
    raw = (tmp_path / "companion_credentials.dpapi.json").read_text("utf-8")
    assert SECRET not in raw
    blobs = json.loads(raw)
    assert "deepseek" in blobs and SECRET not in blobs["deepseek"]

    assert v.delete("deepseek") is True and not v.has("deepseek")
    with pytest.raises(CredentialError):
        v.resolve("deepseek")


def test_dpapi_survives_new_instance(tmp_path):
    WindowsDpapiCredentialVault(tmp_path).store("openai", SECRET)
    assert WindowsDpapiCredentialVault(tmp_path).resolve("openai") == SECRET


def test_build_default_vault_is_dpapi_on_windows(tmp_path):
    v = build_default_credential_vault(tmp_path)
    assert isinstance(v, WindowsDpapiCredentialVault)


def test_dpapi_rejects_unsafe_provider_id(tmp_path):
    v = WindowsDpapiCredentialVault(tmp_path)
    with pytest.raises(CredentialError):
        v.store("../evil", SECRET)
    with pytest.raises(CredentialError):
        v.store("deepseek", "short")           # below min length
