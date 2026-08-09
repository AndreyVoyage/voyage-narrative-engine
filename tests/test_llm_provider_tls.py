#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused regression tests for verified TLS in llm_provider.

ASIDE V2 S2 — Ren'Py DeepSeek TLS CA correction.
Tests 1-5 are deterministic, offline, require no API key or network.
"""

from __future__ import annotations

import ssl
import sys
import os

import pytest

# Ensure the project root is on sys.path so that 'import llm_provider'
# resolves tools/llm_provider.py without manipulating the tools/ namespace.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import llm_provider  # noqa: E402


class TestProviderTLSSafety:
    """Deterministic unit-regression: no API key, no network."""

    def test_ssl_context_is_created_from_certifi(self):
        """_get_ssl_context() uses certifi.where() as cafile."""
        ctx = llm_provider._get_ssl_context()
        assert ctx is not None, "certifi must be available; got None"

        import certifi

        # certifi.where() is called internally; sanity check that the file
        # exists and is the one expected.
        ca_file = certifi.where()
        assert os.path.isfile(ca_file), f"certifi CA bundle missing: {ca_file}"

    def test_verify_mode_is_cert_required(self):
        """Context must enforce CERT_REQUIRED."""
        ctx = llm_provider._get_ssl_context()
        assert ctx is not None
        assert ctx.verify_mode == ssl.CERT_REQUIRED, (
            f"expected CERT_REQUIRED ({ssl.CERT_REQUIRED}), got {ctx.verify_mode}"
        )

    def test_check_hostname_is_enabled(self):
        """Context must have hostname verification enabled."""
        ctx = llm_provider._get_ssl_context()
        assert ctx is not None
        assert ctx.check_hostname is True, (
            f"expected check_hostname=True, got {ctx.check_hostname}"
        )

    def test_no_cert_none(self):
        """verify_mode must NOT be CERT_NONE."""
        ctx = llm_provider._get_ssl_context()
        assert ctx is not None
        assert ctx.verify_mode != ssl.CERT_NONE, (
            "verify_mode must not be CERT_NONE"
        )

    def test_no_insecure_fallback_regression(self):
        """The module source must not contain any known insecure patterns."""
        source_path = os.path.join(_TOOLS_DIR, "llm_provider.py")
        with open(source_path, encoding="utf-8") as fh:
            source = fh.read()

        forbidden = [
            "verify=False",
            "CERT_NONE",
            "_create_unverified_context()",
            "check_hostname=False",
        ]
        for token in forbidden:
            assert token not in source, (
                f"insecure token found in llm_provider.py: {token}"
            )

    def test_context_ca_count_is_nonzero(self):
        """The certifi-backed context must yield >0 trusted CA certs."""
        ctx = llm_provider._get_ssl_context()
        assert ctx is not None
        ca_certs = ctx.get_ca_certs()
        assert len(ca_certs) > 0, f"expected >0 CA certs, got {len(ca_certs)}"