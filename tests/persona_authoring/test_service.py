#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Service tests -- generation, provider, variants."""

from __future__ import annotations

import pytest
from services.persona_authoring import (
    PacApprovalError,
    PacFmdrError,
    PacProviderError,
    PacRequest,
)
from services.persona_authoring.contracts import (
    validate_fmdr,
)
from .conftest import make_mock_provider, valid_fmdr_text


class TestValidateFmdr:
    def test_valid_fmdr(self):
        text = valid_fmdr_text()
        valid, thoughts, actions, speech, error = validate_fmdr(text)
        assert valid is True
        assert error is None
        assert thoughts is not None
        assert actions is not None
        assert speech is not None

    def test_empty_text(self):
        valid, _, _, _, error = validate_fmdr("")
        assert valid is False
        assert "empty" in error

    def test_no_fmdr_markers(self):
        valid, _, _, _, error = validate_fmdr("just plain text without markers")
        assert valid is False
        assert "no ФМДР" in error

    def test_only_thoughts(self):
        text = "(Мысли: я один)"
        valid, thoughts, actions, speech, error = validate_fmdr(text)
        assert valid is True
        assert thoughts == "я один"
        assert actions is None
        assert speech is None

    def test_only_speech(self):
        text = "«Речь: привет»"
        valid, thoughts, actions, speech, error = validate_fmdr(text)
        assert valid is True
        assert speech == "привет"


class TestGeneration:
    def test_generate_two_variants(self, service, sample_request):
        sample_request = PacRequest(
            character_id="kira", level="U3-A",
            situation="test", author_instruction="test",
            provider="mock", model="test", variant_count=2,
        )
        gen = service.generate(sample_request)
        assert len(gen.variants) == 2
        assert gen.request.character_id == "kira"
        assert gen.run_id

    def test_generate_three_variants(self, service):
        req = PacRequest(
            character_id="kira", level="U3-A",
            situation="test", author_instruction="test",
            provider="mock", model="test", variant_count=3,
        )
        provider = make_mock_provider([
            "Вариант 1\n(Мысли: а)→*а*→«а»\nВариант 2\n(Мысли: б)→*б*→«б»\nВариант 3\n(Мысли: в)→*в*→«в»"
        ])
        svc = type(service)(gateway=service.gateway, provider_callable=provider, storage=service.storage)
        gen = svc.generate(req)
        assert len(gen.variants) == 3

    def test_reject_one_variant(self, service):
        req = PacRequest(
            character_id="kira", level="U3-A",
            situation="t", author_instruction="t",
            provider="mock", model="t", variant_count=1,
        )
        with pytest.raises(PacFmdrError, match="must be 2 or 3"):
            service.generate(req)

    def test_reject_four_variants(self, service):
        req = PacRequest(
            character_id="kira", level="U3-A",
            situation="t", author_instruction="t",
            provider="mock", model="t", variant_count=4,
        )
        with pytest.raises(PacFmdrError, match="must be 2 or 3"):
            service.generate(req)

    def test_raw_response_preserved(self, service, sample_request):
        gen = service.generate(sample_request)
        for v in gen.variants:
            assert v.raw_text
            assert isinstance(v.raw_text, str)

    def test_provenance_in_generation(self, service, sample_request):
        gen = service.generate(sample_request)
        assert "source_commit" in gen.canon_snapshot
        assert "modules" in gen.canon_snapshot
        assert len(gen.canon_snapshot["modules"]) > 0

    def test_invalid_variant_fmdr_detected(self, service):
        req = PacRequest(
            character_id="kira", level="U3-A",
            situation="t", author_instruction="t",
            provider="mock", model="t", variant_count=2,
        )
        provider = make_mock_provider([
            "Вариант 1\nnot valid\nВариант 2\nalso not valid"
        ])
        svc = type(service)(gateway=service.gateway, provider_callable=provider, storage=service.storage)
        gen = svc.generate(req)
        for v in gen.variants:
            assert v.fmdr_valid is False


class TestProvider:
    def test_mock_provider_deterministic(self):
        p = make_mock_provider()
        r1 = p(messages=[{"role":"user","content":"hi"}], provider="mock", model="t")
        p2 = make_mock_provider()
        r2 = p2(messages=[{"role":"user","content":"hi"}], provider="mock", model="t")
        assert r1 == r2  # deterministic for same input

    def test_unknown_provider_rejected(self, service):
        req = PacRequest(
            character_id="kira", level="U3-A",
            situation="t", author_instruction="t",
            provider="invalid_provider", model="t", variant_count=2,
        )
        with pytest.raises(PacProviderError):
            service.generate(req)

    def test_provider_model_in_generation(self, service, sample_request):
        gen = service.generate(sample_request)
        assert gen.request.provider == "mock"
        assert gen.request.model == "test-model"