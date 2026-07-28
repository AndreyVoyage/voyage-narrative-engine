#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared fixtures for PAC v0 tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.persona_authoring import (
    GatewayAdapter,
    PacGeneration,
    PacRequest,
    PacService,
    PacStorage,
    PacVariant,
    validate_fmdr,
)
from services.persona_authoring.contracts import (
    PacApprovalLevel,
    generate_run_id,
    new_uuid,
    utc_now_iso,
)


# ------------------------------------------------------------------
# Mock provider
# ------------------------------------------------------------------


def make_mock_provider(responses: list[str] | None = None):
    """Return a callable that returns canned responses.

    Simulates the real ``tools.llm_provider.complete`` contract:
    accepts only ``"mock"``, ``"local"``, or ``"cloud"`` as provider values.
    Unknown providers raise ``LLMProviderError``-compatible error.
    """
    if responses is None:
        responses = []

    def _provider(messages=None, *, provider=None, model=None, system=None, params=None, **kwargs):
        # Validate provider like the real complete() does.
        provider_str = str(provider or "").strip().lower()
        if provider_str not in ("mock", "local", "cloud"):
            # Simulate LLMProviderError from tools.llm_provider
            raise RuntimeError(f"Unknown provider: {provider}")
        idx = _provider.call_count
        _provider.call_count += 1
        if idx < len(responses):
            return responses[idx]
        # Default: return 2 ФМДР variants.
        return (
            "Вариант 1\n"
            "(Мысли: тестовая мысль) → "
            "*Действия: тестовое действие* → "
            "«Речь: тестовая речь»\n"
            "\n"
            "Вариант 2\n"
            "(Мысли: вторая мысль) → "
            "*Действия: второе действие* → "
            "«Речь: вторая речь»"
        )

    _provider.call_count = 0
    return _provider


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def tmp_storage_dir():
    """Create a temporary directory for PAC storage."""
    with tempfile.TemporaryDirectory(prefix="pac_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def storage(tmp_storage_dir):
    """Return a PacStorage backed by a temporary directory."""
    return PacStorage(base_path=tmp_storage_dir / "pac")


@pytest.fixture
def mock_provider():
    """Return a mock provider that returns 2 ФМДР variants."""
    return make_mock_provider()


@pytest.fixture
def mock_gateway():
    """Return a MagicMock-wrapped GatewayAdapter."""
    gw = MagicMock(spec=GatewayAdapter)
    gw.list_characters.return_value = [{"id": "kira", "name": "Кира"}]
    gw.get_character_manifest.return_value = MagicMock(
        id="kira",
        name="Кира",
        version="1.0",
        schema_version="3.2",
        default_level="U3-A",
        default_ag_level=3,
        compatible_scenarios=(),
        modules=(),
    )
    gw.get_authoring_context.return_value = {
        "manifest": {"id": "kira", "name": "Кира"},
        "modules": {},
        "source_commit": "8c28521153eeed39f35840d7f82d0d571eddfb84",
    }
    gw.build_canon_snapshot.return_value = {
        "source_commit": "8c28521153eeed39f35840d7f82d0d571eddfb84",
        "modules": [
            {
                "module_id": "core/IDENTITY.json",
                "content_hash": "sha256:abc123",
                "provenance": "gateway-v1",
            }
        ],
    }
    return gw


@pytest.fixture
def service(mock_gateway, mock_provider, storage):
    """Return a fully wired PacService with mock deps."""
    return PacService(
        gateway=mock_gateway,
        provider_callable=mock_provider,
        storage=storage,
    )


@pytest.fixture
def sample_request():
    """Return a valid PacRequest for testing."""
    return PacRequest(
        character_id="kira",
        level="U3-A",
        situation="встреча после долгой разлуки",
        author_instruction="сдержанная радость",
        provider="mock",
        model="test-model",
        variant_count=2,
    )


@pytest.fixture
def sample_generation(service, sample_request):
    """Return a generated PacGeneration through the service."""
    return service.generate(sample_request)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def valid_fmdr_text() -> str:
    return (
        "(Мысли: он здесь) → "
        "*Кира застыла на месте* → "
        "«Сергей...»"
    )


def make_variant(index: int, valid: bool = True) -> PacVariant:
    if valid:
        return PacVariant(
            index=index,
            raw_text=valid_fmdr_text(),
            fmdr_valid=True,
            thoughts="он здесь",
            actions="Кира застыла на месте",
            speech="Сергей...",
        )
    return PacVariant(
        index=index,
        raw_text="not valid fmdr",
        fmdr_valid=False,
        fmdr_error="no ФМДР layer markers found",
    )