#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slice 4 tests for tools/cis_pilot/provider_boundary.py.

No LLM, no network. Covers: mock-only enforcement, deterministic output,
non-mock rejection, fail-closed, DI adapters, provenance metadata,
no network imports/calls.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cis_pilot.provider_boundary import (
    SUPPORTED_PROVIDER,
    MOCK_MODEL_ID,
    ProviderBoundaryError,
    ProviderConfig,
    PilotProviderBoundary,
    default_boundary,
    make_interpretation_proposal_fn,
    make_gist_proposal_fn,
    _mock_completion_digest,
)
from tools.cis_pilot.contracts import ContractValidationError
from tools.cis_pilot.memory_gate import (
    CharacterPerception,
    WorldEvent,
)

DUMMY_EVENT_ID = "evt-001"
DUMMY_SHA256 = "b" * 64  # 64-char lowercase hex


def _synthetic_event(event_id: str = DUMMY_EVENT_ID) -> WorldEvent:
    return WorldEvent(
        event_id=event_id,
        objective_text="test objective text",
        participants=("kira", "user"),
        scenario_repo_relative_path="scenarios/test.json",
        json_path="beats[0].action",
        source_sha256=DUMMY_SHA256,
    )


# ---------------------------------------------------------------------------
# ProviderConfig tests
# ---------------------------------------------------------------------------


class TestProviderConfig:
    def test_valid_mock_config(self) -> None:
        cfg = ProviderConfig(provider="mock", model=MOCK_MODEL_ID, params={})
        assert cfg.provider == "mock"
        assert cfg.model == MOCK_MODEL_ID
        assert isinstance(cfg.params, MappingProxyType)

    def test_trim_and_lower(self) -> None:
        cfg = ProviderConfig(provider="  MOCK  ", model=MOCK_MODEL_ID, params={})
        assert cfg.provider == "mock"

    def test_non_mock_rejected(self) -> None:
        for bad in ("openai", "anthropic", "deepseek", "kimi", "ollama", "local"):
            with pytest.raises(ProviderBoundaryError, match="not supported"):
                ProviderConfig(provider=bad, model="x", params={})

    def test_empty_provider_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            ProviderConfig(provider="", model=MOCK_MODEL_ID, params={})

    def test_empty_model_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            ProviderConfig(provider="mock", model="", params={})

    def test_params_must_be_mapping(self) -> None:
        with pytest.raises(ContractValidationError):
            ProviderConfig(provider="mock", model=MOCK_MODEL_ID, params=[])  # type: ignore[arg-type]

    def test_params_keys_must_be_strings(self) -> None:
        with pytest.raises(ContractValidationError):
            ProviderConfig(provider="mock", model=MOCK_MODEL_ID, params={1: "val"})  # type: ignore[arg-type]

    def test_provenance_metadata(self) -> None:
        cfg = ProviderConfig(provider="mock", model=MOCK_MODEL_ID, params={"temp": 0.5})
        meta = cfg.provenance_metadata()
        assert meta["provider"] == "mock"
        assert meta["model"] == MOCK_MODEL_ID
        assert meta["params"] == {"temp": 0.5}


# ---------------------------------------------------------------------------
# PilotProviderBoundary tests
# ---------------------------------------------------------------------------


class TestPilotProviderBoundary:
    def test_default_boundary_factory(self) -> None:
        b = default_boundary()
        assert isinstance(b, PilotProviderBoundary)
        assert b.config.provider == "mock"

    def test_complete_returns_string(self) -> None:
        b = default_boundary()
        result = b.complete([{"role": "user", "content": "hello"}])
        assert isinstance(result, str)
        assert result.startswith("[MOCK]")

    def test_complete_deterministic(self) -> None:
        b = default_boundary()
        messages = [{"role": "user", "content": "determinism test"}]
        a = b.complete(messages)
        c = b.complete(messages)
        assert a == c

    def test_complete_different_inputs_different_outputs(self) -> None:
        b = default_boundary()
        r1 = b.complete([{"role": "user", "content": "alpha"}])
        r2 = b.complete([{"role": "user", "content": "beta"}])
        assert r1 != r2

    def test_provenance_metadata(self) -> None:
        b = default_boundary()
        meta = b.provenance_metadata()
        assert meta["provider"] == "mock"
        assert meta["model"] == MOCK_MODEL_ID


# ---------------------------------------------------------------------------
# Mock completion digest parsing
# ---------------------------------------------------------------------------


class TestMockCompletionDigest:
    def test_valid_digest(self) -> None:
        result = _mock_completion_digest("[MOCK] (user) test prompt :: abcdef1234")
        assert result == "abcdef1234"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            _mock_completion_digest("")
        with pytest.raises(ProviderBoundaryError):
            _mock_completion_digest("   ")

    def test_missing_separator_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            _mock_completion_digest("[MOCK] no separator here")

    def test_non_mock_prefix_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            _mock_completion_digest("[REAL] (user) test :: abcdef1234")

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            _mock_completion_digest(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DI adapter: make_interpretation_proposal_fn
# ---------------------------------------------------------------------------


class TestInterpretationProposalAdapter:
    def test_produces_interpretation(self) -> None:
        boundary = default_boundary()
        fn = make_interpretation_proposal_fn(boundary)
        event = _synthetic_event()
        perception = CharacterPerception(
            character_id="kira",
            world_event_id=event.event_id,
            noticed="test noticed",
            missed=("background detail",),
        )
        interp = fn(event, perception)
        assert interp.character_id == "kira"
        assert interp.world_event_id == event.event_id
        assert interp.meaning.startswith("mock-interpretation:")
        assert interp.emotional_coloring.startswith("mock-coloring:")

    def test_deterministic_same_input_same_output(self) -> None:
        boundary = default_boundary()
        fn = make_interpretation_proposal_fn(boundary)
        event = _synthetic_event()
        perception = CharacterPerception(
            character_id="kira",
            world_event_id=event.event_id,
            noticed="test",
        )
        a = fn(event, perception)
        b = fn(event, perception)
        assert a == b

    def test_rejects_bad_boundary(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            make_interpretation_proposal_fn(None)  # type: ignore[arg-type]

    def test_rejects_bad_inputs(self) -> None:
        boundary = default_boundary()
        fn = make_interpretation_proposal_fn(boundary)
        event = _synthetic_event()
        good_perception = CharacterPerception(
            character_id="kira", world_event_id=event.event_id, noticed="x"
        )
        with pytest.raises(ProviderBoundaryError):
            fn(None, good_perception)  # type: ignore[arg-type]
        with pytest.raises(ProviderBoundaryError):
            fn(event, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DI adapter: make_gist_proposal_fn
# ---------------------------------------------------------------------------


class TestGistProposalAdapter:
    def test_produces_gist_string(self) -> None:
        boundary = default_boundary()
        fn = make_gist_proposal_fn(boundary)
        event = _synthetic_event()
        perception = CharacterPerception(
            character_id="kira", world_event_id=event.event_id, noticed="x"
        )
        interp_fn = make_interpretation_proposal_fn(boundary)
        interp = interp_fn(event, perception)
        gist = fn(event, perception, interp)
        assert isinstance(gist, str)
        assert gist.startswith("mock-gist:")

    def test_deterministic(self) -> None:
        boundary = default_boundary()
        interp_fn = make_interpretation_proposal_fn(boundary)
        gist_fn = make_gist_proposal_fn(boundary)
        event = _synthetic_event()
        perception = CharacterPerception(
            character_id="kira", world_event_id=event.event_id, noticed="x"
        )
        interp = interp_fn(event, perception)
        a = gist_fn(event, perception, interp)
        b = gist_fn(event, perception, interp)
        assert a == b

    def test_rejects_bad_boundary(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            make_gist_proposal_fn(None)  # type: ignore[arg-type]

    def test_rejects_bad_interpretation(self) -> None:
        boundary = default_boundary()
        fn = make_gist_proposal_fn(boundary)
        event = _synthetic_event()
        perception = CharacterPerception(
            character_id="kira", world_event_id=event.event_id, noticed="x"
        )
        with pytest.raises(ProviderBoundaryError):
            fn(event, perception, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Static dependency audit
# ---------------------------------------------------------------------------


class TestNoNetworkOrRealProvider:
    def test_no_network_imports(self) -> None:
        """Verify production module imports no network/provider/SDK libs."""
        src = (Path(__file__).parents[2] / "tools" / "cis_pilot" /
               "provider_boundary.py").read_text(encoding="utf-8")
        forbidden = (
            "openai", "anthropic", "deepseek", "kimi", "ollama",
            "requests", "httpx", "urllib", "socket", "http.client",
            "sqlite3", "sqlite", "renpy", "message_parts",
        )
        for token in forbidden:
            assert token not in src, f"forbidden token in source: {token}"

    def test_no_network_in_complete_path(self) -> None:
        """Confirm the complete() method only calls llm_provider.complete."""
        from tools.cis_pilot.provider_boundary import PilotProviderBoundary
        import inspect
        source = inspect.getsource(PilotProviderBoundary.complete)
        assert "requests" not in source
        assert "urllib" not in source
        assert "socket" not in source
        assert "api_key" not in source


# ---------------------------------------------------------------------------
# Mock-only hard gate
# ---------------------------------------------------------------------------


class TestMockOnlyHardGate:
    def test_non_mock_provider_names_fail(self) -> None:
        bad_names = ("openai", "anthropic", "deepseek", "kimi", "ollama",
                     "local", "real", "production")
        for name in bad_names:
            with pytest.raises(ProviderBoundaryError):
                ProviderConfig(provider=name, model="x", params={})

    def test_cannot_construct_with_unsupported_provider(self) -> None:
        for name in ("openai", "anthropic", "kimi"):
            with pytest.raises(ProviderBoundaryError):
                PilotProviderBoundary(provider=name)