#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared offline fixtures for Companion tests. No provider, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTED_ROOT = _REPO_ROOT / "accepted"

FAKE_REPLY = "Тестовый ответ Киры."
FAKE_PROVIDER_INFO = {"provider_id": "fake", "model": "fake-companion-mvp-v1"}


def make_fake_factory(reply: str = FAKE_REPLY):
    """A deterministic fake provider factory that records every call so tests
    can prove the existing provider abstraction is exercised, not bypassed."""
    calls: list = []

    def factory(recorder):
        def provider(messages):
            calls.append([dict(m) for m in messages])
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake-companion", "model": "fake",
                    "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                }})
            return reply
        return provider

    factory.calls = calls  # type: ignore[attr-defined]
    return factory


def make_failing_factory():
    def factory(recorder):
        def provider(messages):
            raise RuntimeError("simulated provider failure")
        return provider
    return factory


@pytest.fixture
def accepted_root() -> Path:
    return ACCEPTED_ROOT
