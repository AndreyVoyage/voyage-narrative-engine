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

from tools import llm_provider
from tools.cis_pilot.provider_boundary import (
    SUPPORTED_PROVIDER,
    MOCK_MODEL_ID,
    DEEPSEEK_REAL_PROVIDER,
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_TIMEOUT_S,
    ProviderBoundaryError,
    ProviderConfig,
    PilotProviderBoundary,
    default_boundary,
    make_interpretation_proposal_fn,
    make_gist_proposal_fn,
    make_real_interpretation_proposal_fn,
    make_real_gist_proposal_fn,
    parse_real_interpretation,
    parse_real_gist,
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
        """Verify production module imports no network/provider/SDK libs.

        TD-16 (approved DeepSeek real path) reuses the existing
        stdlib-only ``tools.llm_provider``; the module must not add any new
        network import or SDK dependency. The literal string ``deepseek`` is
        now a legitimate configuration identifier (model id / base URL), so
        that token is asserted at the import-statement level rather than as
        a raw substring anywhere in the source.
        """
        import re

        src = (Path(__file__).parents[2] / "tools" / "cis_pilot" /
               "provider_boundary.py").read_text(encoding="utf-8")
        forbidden = (
            "openai", "anthropic", "kimi", "ollama",
            "requests", "httpx", "urllib", "socket", "http.client",
            "aiohttp", "sqlite3", "sqlite", "renpy", "message_parts",
        )
        for token in forbidden:
            assert token not in src, f"forbidden token in source: {token}"

        import_lines = [
            ln.strip() for ln in src.splitlines()
            if ln.strip().startswith(("import ", "from "))
        ]
        prohibited_import_prefixes = (
            "import requests", "import httpx", "import urllib",
            "import socket", "import aiohttp", "import openai",
            "import anthropic", "import langgraph", "import sqlite",
            "from openai", "from anthropic", "from deepseek",
            "from langgraph", "from urllib", "from http", "from httpx",
        )
        for line in import_lines:
            assert not line.startswith(prohibited_import_prefixes), (
                f"prohibited import in source: {line}"
            )
        assert re.search(r"\bimport\s+re\b", src) is None

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


# ---------------------------------------------------------------------------
# TD-16: approved DeepSeek real path (offline; no network)
# ---------------------------------------------------------------------------


class TestApprovedDeepSeekRealPath:
    def test_approved_config_accepted(self) -> None:
        cfg = ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER,
                             model=DEEPSEEK_MODEL_ID, params={})
        assert cfg.provider == "cloud"
        assert cfg.model == DEEPSEEK_MODEL_ID
        # Endpoint is bound to the approved DeepSeek base URL automatically.
        assert dict(cfg.params)["base_url"] == DEEPSEEK_BASE_URL
        # TD-22A: the approved transport timeout is applied automatically.
        assert dict(cfg.params)["timeout_s"] == DEEPSEEK_TIMEOUT_S

    def test_other_real_models_rejected(self) -> None:
        for bad in ("deepseek-chat", "deepseek-reasoner", "gpt-4o-mini",
                    "gpt-4", "claude-3", "kimi-k2", "ollama/llama3",
                    "some-arbitrary-name"):
            with pytest.raises(ProviderBoundaryError, match="not authorized"):
                ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER, model=bad,
                               params={})

    def test_empty_model_on_real_path_rejected(self) -> None:
        with pytest.raises(ContractValidationError):
            ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER, model="",
                           params={})

    def test_other_base_url_rejected(self) -> None:
        for bad_url in ("https://api.openai.com",
                        "https://api.deepseek.com/v2",
                        "http://localhost:11434"):
            with pytest.raises(ProviderBoundaryError, match="base_url"):
                ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER,
                               model=DEEPSEEK_MODEL_ID,
                               params={"base_url": bad_url})

    def test_approved_base_url_accepted_verbatim(self) -> None:
        cfg = ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER,
                             model=DEEPSEEK_MODEL_ID,
                             params={"base_url": DEEPSEEK_BASE_URL})
        assert dict(cfg.params)["base_url"] == DEEPSEEK_BASE_URL

    def test_no_api_key_in_provenance(self) -> None:
        cfg = ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER,
                             model=DEEPSEEK_MODEL_ID, params={})
        meta = cfg.provenance_metadata()
        serialized = repr(meta)
        assert "api_key" not in serialized
        assert "OPENAI_API_KEY" not in serialized
        assert "secret" not in serialized

    def test_complete_forwards_approved_deepseek_params(self, monkeypatch) -> None:
        calls: list[dict] = []

        def fake_complete(messages, *, provider, model=None, system=None,
                          params=None, usage_sink=None):
            calls.append({
                "messages": messages,
                "provider": provider,
                "model": model,
                "params": params,
                "usage_sink": usage_sink,
            })
            return "real-response"

        monkeypatch.setattr(llm_provider, "complete", fake_complete)
        boundary = PilotProviderBoundary(provider=DEEPSEEK_REAL_PROVIDER,
                                         model=DEEPSEEK_MODEL_ID,
                                         params={})
        result = boundary.complete([{"role": "user", "content": "hello"}])
        assert result == "real-response"
        assert len(calls) == 1
        call = calls[0]
        assert call["provider"] == "cloud"
        assert call["model"] == DEEPSEEK_MODEL_ID
        assert call["params"]["base_url"] == DEEPSEEK_BASE_URL
        assert call["messages"] == [{"role": "user", "content": "hello"}]

    def test_helper_exception_propagates_no_mock_fallback(self, monkeypatch) -> None:
        def fake_complete(messages, *, provider, model=None, system=None,
                          params=None, usage_sink=None):
            raise llm_provider.LLMProviderError(
                "OPENAI_API_KEY is required for cloud provider"
            )

        monkeypatch.setattr(llm_provider, "complete", fake_complete)
        boundary = PilotProviderBoundary(provider=DEEPSEEK_REAL_PROVIDER,
                                         model=DEEPSEEK_MODEL_ID,
                                         params={})
        with pytest.raises(llm_provider.LLMProviderError):
            boundary.complete([{"role": "user", "content": "hello"}])

    def test_runner_facing_return_type_is_str(self, monkeypatch) -> None:
        def fake_complete(messages, *, provider, model=None, system=None,
                          params=None, usage_sink=None):
            return "mock-free completion text"

        monkeypatch.setattr(llm_provider, "complete", fake_complete)
        boundary = PilotProviderBoundary(provider=DEEPSEEK_REAL_PROVIDER,
                                         model=DEEPSEEK_MODEL_ID,
                                         params={})
        assert isinstance(boundary.complete([{"role": "user", "content": "x"}]),
                          str)


class TestMockPreservedAfterTD16:
    """The deterministic mock path must remain byte-for-byte unchanged."""

    def test_default_boundary_still_mock(self) -> None:
        b = default_boundary()
        assert b.config.provider == "mock"
        assert b.config.model == MOCK_MODEL_ID
        assert b.config.params == {}

    def test_mock_deterministic_after_td16(self) -> None:
        b = default_boundary()
        messages = [{"role": "user", "content": "determinism-after-td16"}]
        assert b.complete(messages) == b.complete(messages)
        assert b.complete(messages).startswith("[MOCK]")

    def test_mock_never_receives_base_url(self, monkeypatch) -> None:
        calls: list[dict] = []

        def fake_complete(messages, *, provider, model=None, system=None,
                          params=None, usage_sink=None):
            calls.append(params or {})
            return "[MOCK] (user) x :: abcdef1234"

        monkeypatch.setattr(llm_provider, "complete", fake_complete)
        b = default_boundary()
        b.complete([{"role": "user", "content": "x"}])
        assert calls == [{}]


# ---------------------------------------------------------------------------
# TD-22A: shared cloud transport timeout surface
# ---------------------------------------------------------------------------


class TestTd22aCloudTimeout:
    """Transport-only cloud timeout; CIS DeepSeek real path uses 120s.

    Offline: the cloud HTTP layer is stubbed at ``_post_json`` / ``complete``,
    so no network, no credential value, and no real provider is ever reached.
    """

    def test_cloud_default_timeout_30(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        captured: list[dict] = []

        def fake_post(url, payload, *, headers, timeout_s=30.0):
            captured.append({"payload": payload, "timeout_s": timeout_s})
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr(llm_provider, "_post_json", fake_post)
        llm_provider.complete([{"role": "user", "content": "hi"}],
                              provider="cloud", model="gpt-4o-mini")
        assert captured[0]["timeout_s"] == 30.0
        assert "timeout_s" not in captured[0]["payload"]
        assert "base_url" not in captured[0]["payload"]

    def test_cloud_explicit_timeout_120_transport_only(self, monkeypatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        captured: list[dict] = []

        def fake_post(url, payload, *, headers, timeout_s=30.0):
            captured.append({"payload": payload, "timeout_s": timeout_s})
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr(llm_provider, "_post_json", fake_post)
        llm_provider.complete([{"role": "user", "content": "hi"}],
                              provider="cloud", model="gpt-4o-mini",
                              params={"timeout_s": 120})
        # 120 reaches the transport timeout, never the request body.
        assert captured[0]["timeout_s"] == 120.0
        assert "timeout_s" not in captured[0]["payload"]

    def test_cis_deepseek_forwards_timeout_120(self, monkeypatch) -> None:
        calls: list[dict] = []

        def fake_complete(messages, *, provider, model=None, system=None,
                          params=None, usage_sink=None):
            calls.append({"params": params, "usage_sink": usage_sink})
            return "real-response"

        monkeypatch.setattr(llm_provider, "complete", fake_complete)
        boundary = PilotProviderBoundary(provider=DEEPSEEK_REAL_PROVIDER,
                                         model=DEEPSEEK_MODEL_ID, params={})
        boundary.complete([{"role": "user", "content": "hi"}])
        assert calls[0]["params"]["timeout_s"] == DEEPSEEK_TIMEOUT_S
        assert calls[0]["params"]["base_url"] == DEEPSEEK_BASE_URL

    def test_cis_deepseek_rejects_wrong_timeout(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="timeout_s"):
            ProviderConfig(provider=DEEPSEEK_REAL_PROVIDER,
                           model=DEEPSEEK_MODEL_ID,
                           params={"timeout_s": 30})

    def test_provider_failure_exactly_one_attempt_no_retry(self, monkeypatch) -> None:
        attempt_count = [0]

        def failing_complete(messages, *, provider, model=None, system=None,
                             params=None, usage_sink=None):
            attempt_count[0] += 1
            raise llm_provider.LLMProviderError("boom")

        monkeypatch.setattr(llm_provider, "complete", failing_complete)
        boundary = PilotProviderBoundary(provider=DEEPSEEK_REAL_PROVIDER,
                                         model=DEEPSEEK_MODEL_ID, params={})
        with pytest.raises(llm_provider.LLMProviderError):
            boundary.complete([{"role": "user", "content": "hi"}])
        assert attempt_count[0] == 1


# ---------------------------------------------------------------------------
# TD-26A: real-provider (PB-MEM) strict interpretation + gist parsing
# ---------------------------------------------------------------------------


class TestTd26aRealParsers:
    """Real interpretation = strict 2-field JSON; real gist = plain text."""

    def test_mock_interpretation_parser_unchanged(self) -> None:
        res = _mock_completion_digest("[MOCK] (user) hello :: abcdef1234")
        assert res == "abcdef1234"

    def test_mock_gist_parser_unchanged(self) -> None:
        fn = make_gist_proposal_fn(default_boundary())
        assert callable(fn)

    def test_valid_real_interpretation_accepted(self) -> None:
        meaning, coloring = parse_real_interpretation(
            '{"meaning": "она доверилась", "emotional_coloring": "ранимость"}'
        )
        assert meaning == "она доверилась"
        assert coloring == "ранимость"

    def test_real_interpretation_strips_surrounding_whitespace(self) -> None:
        meaning, coloring = parse_real_interpretation(
            '  {"meaning": "a", "emotional_coloring": "b"}  '
        )
        assert (meaning, coloring) == ("a", "b")

    def test_empty_interpretation_rejected(self) -> None:
        for bad in ("", "   ", "\n"):
            with pytest.raises(ProviderBoundaryError):
                parse_real_interpretation(bad)

    def test_malformed_json_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="not valid JSON"):
            parse_real_interpretation("not-json at all")

    def test_missing_key_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="exactly"):
            parse_real_interpretation('{"meaning": "a"}')

    def test_extra_key_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="exactly"):
            parse_real_interpretation(
                '{"meaning": "a", "emotional_coloring": "b", "character_id": "kira"}'
            )

    def test_wrong_type_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            parse_real_interpretation('{"meaning": 1, "emotional_coloring": "b"}')
        with pytest.raises(ProviderBoundaryError):
            parse_real_interpretation('{"meaning": "a", "emotional_coloring": null}')

    def test_empty_string_value_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            parse_real_interpretation('{"meaning": "  ", "emotional_coloring": "b"}')

    def test_code_fenced_json_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="not valid JSON"):
            parse_real_interpretation('```json\n{"meaning":"a","emotional_coloring":"b"}\n```')

    def test_real_gist_valid_text_accepted(self) -> None:
        assert parse_real_gist("  она доверилась  ", "Падает ему на грудь.") == \
            "она доверилась"

    def test_real_gist_empty_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError):
            parse_real_gist("   ", "Падает ему на грудь.")

    def test_real_gist_objective_event_equal_rejected(self) -> None:
        with pytest.raises(ProviderBoundaryError, match="objective event"):
            parse_real_gist("Падает ему на грудь.", "Падает ему на грудь.")

    def test_no_mock_fallback_on_real_parse_failure(self) -> None:
        # _mock_completion_digest is never invoked by the real parser; the real
        # parser raises directly and does not attempt the mock digest path.
        with pytest.raises(ProviderBoundaryError):
            parse_real_interpretation("[MOCK] (user) x :: abcdef1234")
