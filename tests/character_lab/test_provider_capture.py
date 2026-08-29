#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider capture-seam tests (offline, monkeypatched transport)."""

from __future__ import annotations

import json
import urllib.error

import pytest

import llm_provider
from services.character_lab import (
    AssemblyItem,
    AssemblyManifest,
    TurnCapture,
    build_assembly_hash,
)


class _FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_response(content="ok"):
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


class TestNoRecorderBehavior:
    def test_no_recorder_behavior_unchanged(self, monkeypatch):
        calls = {}

        def fake_post(url, payload, *, headers, timeout_s=30.0, recorder=None):
            calls["recorder"] = recorder
            return _ok_response("unchanged")

        monkeypatch.setattr(llm_provider, "_post_json", fake_post)
        out = llm_provider.complete(
            [{"role": "user", "content": "hi"}],
            provider="cloud",
            model="m",
            params={"api_key": "k", "base_url": "https://fake.invalid"},
        )
        assert out == "unchanged"
        assert calls["recorder"] is None


class TestRecorderSeam:
    def test_recorder_observes_exact_body_before_transport(self, monkeypatch):
        events = []
        order = []

        def fake_urlopen(request, timeout=None, context=None):
            order.append("urlopen")
            return _FakeResponse(_ok_response("the-answer"))

        monkeypatch.setattr(llm_provider.urllib.request, "urlopen", fake_urlopen)

        def recorder(event):
            order.append("recorder:" + event["event"])
            events.append(event)

        out = llm_provider.complete(
            [{"role": "user", "content": "hi"}],
            provider="cloud",
            model="m",
            params={"api_key": "k", "base_url": "https://fake.invalid"},
            recorder=recorder,
        )
        assert out == "the-answer"
        assert order[0] == "recorder:request"
        assert order.index("urlopen") > order.index("recorder:request")

        req = events[0]
        assert req["event"] == "request"
        body = req["body"]
        assert body == json.dumps(req["payload"], ensure_ascii=False).encode("utf-8")
        assert b"Bearer" not in body
        assert b"Authorization" not in body
        assert any(e["event"] == "response" for e in events)

    def test_recorder_does_not_receive_authorization(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            llm_provider.urllib.request, "urlopen",
            lambda *a, **k: _FakeResponse(_ok_response("ok")),
        )

        def recorder(event):
            events.append(event)

        llm_provider.complete(
            [{"role": "user", "content": "hi"}],
            provider="cloud",
            model="m",
            params={"api_key": "SUPER_SECRET_VALUE", "base_url": "https://fake.invalid"},
            recorder=recorder,
        )
        for event in events:
            dumped = json.dumps(event, default=str)
            assert "SUPER_SECRET_VALUE" not in dumped
            assert "Bearer" not in dumped
            assert "Authorization" not in dumped

    def test_success_response_captured_without_changing_return(self, monkeypatch):
        events = []
        monkeypatch.setattr(
            llm_provider.urllib.request, "urlopen",
            lambda *a, **k: _FakeResponse(_ok_response("the-answer")),
        )

        def recorder(event):
            events.append(event)

        out = llm_provider.complete(
            [{"role": "user", "content": "hi"}],
            provider="cloud",
            model="m",
            params={"api_key": "k", "base_url": "https://fake.invalid"},
            recorder=recorder,
        )
        assert out == "the-answer"
        responses = [e for e in events if e["event"] == "response"]
        assert responses and responses[0]["data"]["choices"][0]["message"]["content"] == "the-answer"


class TestFailureWriteAhead:
    def test_failure_leaves_request_artifact(self, monkeypatch, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = AssemblyManifest(
            variant_id="KIRA_BETA_V1_CURRENT",
            variant_version=1,
            items=(AssemblyItem("system.role_instruction", "role", {}),),
        )
        assembly_hash = build_assembly_hash(manifest)
        rec = cap.recorder(
            turn_id="turn-1",
            manifest=manifest,
            assembly_hash=assembly_hash,
            attribution={"provider_id": "deepseek"},
        )

        def fail_urlopen(*a, **k):
            raise urllib.error.URLError("boom")

        monkeypatch.setattr(llm_provider.urllib.request, "urlopen", fail_urlopen)

        with pytest.raises(llm_provider.LLMProviderError):
            llm_provider.complete(
                [{"role": "user", "content": "hi"}],
                provider="cloud",
                model="m",
                params={"api_key": "k", "base_url": "https://fake.invalid"},
                recorder=rec,
            )

        assert (cap.turn_dir("turn-1") / "request.json").exists()
        assert (cap.turn_dir("turn-1") / "manifest.json").exists()
        assert (cap.turn_dir("turn-1") / "error.json").exists()
        assert cap.read_request_hash("turn-1") is not None
