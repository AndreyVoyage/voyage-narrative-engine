#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the real DeepSeek scene-text adapter.

The transport (``tools.llm_provider.complete``) is mocked in every test -- no
network, no real key. Proves: provider-neutral protocol conformance, exactly
one transport call, strict single parse (no repair), fail-closed on malformed
/ schema-invalid / hallucinated output, sanitized transport errors, and that
the adapter never reads the API key itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools import llm_provider, scene_text_llm_adapter  # noqa: E402
from tools.scene_text_llm_adapter import DeepSeekSceneTextProposer  # noqa: E402
from services.scene_text_interpreter import (  # noqa: E402
    GroundingError,
    HallucinationError,
    ProposalSchemaError,
    SceneTextProposer,
    build_interpreter_input,
    interpret_scene_text,
)

FIRST_PROOF_TEXT = (
    "Марина лежит на коврике в спортзале и делает растяжку.\n"
    "Максим находится рядом и наблюдает за её техникой.\n"
    "Марина поворачивает голову и смотрит на него."
)
_PROPOSAL_FIXTURE = (
    _REPO_ROOT / "tests/fixtures/scene_text_interpreter/first_proof_proposal.json"
)


def _good_proposal_json() -> str:
    data = json.loads(_PROPOSAL_FIXTURE.read_text(encoding="utf-8"))
    return json.dumps(data["proposal"], ensure_ascii=False)


def _install_fake_transport(monkeypatch, response=None, *, raises=None):
    calls: list[dict] = []

    def fake_complete(messages, *, provider, model, system=None, params=None):
        calls.append(
            {"messages": messages, "provider": provider, "model": model,
             "system": system, "params": params}
        )
        if raises is not None:
            raise raises
        return response

    monkeypatch.setattr(llm_provider, "complete", fake_complete)
    return calls


def test_adapter_satisfies_scenetextproposer_protocol():
    proposer = DeepSeekSceneTextProposer()
    assert isinstance(proposer, SceneTextProposer)
    assert proposer.provider == "deepseek"
    assert proposer.model == "deepseek-v4-flash"
    assert proposer.mock is False


def test_one_transport_call_with_deepseek_convention(monkeypatch):
    calls = _install_fake_transport(monkeypatch, response=_good_proposal_json())
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    proposer.propose(inp)
    assert len(calls) == 1
    c = calls[0]
    assert c["provider"] == "cloud"
    assert c["model"] == "deepseek-v4-flash"
    assert c["params"]["base_url"] == "https://api.deepseek.com"
    assert c["params"]["api_key_env"] == "DEEPSEEK_API_KEY"
    assert c["params"]["thinking"] == {"type": "disabled"}
    # no literal secret anywhere in the outgoing params
    assert "api_key" not in c["params"]
    blob = json.dumps(c["params"], ensure_ascii=False) + json.dumps(c["messages"], ensure_ascii=False)
    assert "DEEPSEEK_API_KEY" in blob  # only as the env-var NAME
    assert "Bearer" not in blob


def test_raw_response_sha_recorded(monkeypatch):
    _install_fake_transport(monkeypatch, response=_good_proposal_json())
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    proposer.propose(inp)
    assert isinstance(proposer.raw_response_sha256, str)
    assert len(proposer.raw_response_sha256) == 64


def test_malformed_json_fails_closed_no_repair(monkeypatch):
    calls = _install_fake_transport(monkeypatch, response="not json {{{")
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    with pytest.raises(ProposalSchemaError):
        proposer.propose(inp)
    assert len(calls) == 1  # no retry


def test_markdown_fenced_json_is_rejected(monkeypatch):
    fenced = "```json\n" + _good_proposal_json() + "\n```"
    _install_fake_transport(monkeypatch, response=fenced)
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    with pytest.raises(ProposalSchemaError):
        proposer.propose(inp)


def test_schema_invalid_response_fails(monkeypatch):
    data = json.loads(_good_proposal_json())
    del data["beats"]
    _install_fake_transport(monkeypatch, response=json.dumps(data, ensure_ascii=False))
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    with pytest.raises(ProposalSchemaError):
        proposer.propose(inp)


def test_transport_exception_propagates_sanitized(monkeypatch):
    calls = _install_fake_transport(
        monkeypatch, raises=llm_provider.LLMProviderError("HTTP 500: upstream boom")
    )
    proposer = DeepSeekSceneTextProposer()
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    with pytest.raises(llm_provider.LLMProviderError) as excinfo:
        proposer.propose(inp)
    assert len(calls) == 1  # no retry / no fallback
    assert "boom" in str(excinfo.value)


def test_adapter_module_does_not_read_the_key_itself():
    src = Path(scene_text_llm_adapter.__file__).read_text(encoding="utf-8")
    for forbidden in (
        'os.environ.get("DEEPSEEK_API_KEY")',
        "os.environ['DEEPSEEK_API_KEY']",
        'os.getenv("DEEPSEEK_API_KEY")',
        "os.environ.get('DEEPSEEK_API_KEY')",
    ):
        assert forbidden not in src


def test_end_to_end_with_mocked_transport_builds_valid_plan(monkeypatch):
    _install_fake_transport(monkeypatch, response=_good_proposal_json())
    proposer = DeepSeekSceneTextProposer()
    plan = interpret_scene_text(
        FIRST_PROOF_TEXT, repo_root=_REPO_ROOT, proposer=proposer
    )
    assert plan.characters_in_frame == ("MARINA", "MAKSIM")
    assert plan.location_id == "gym"
    assert plan.scene_tags == ("stretching", "training", "neutral")
    assert plan.interpreter["provider"] == "deepseek"
    assert plan.interpreter["mock"] is False
    assert plan.interpreter["raw_response_sha256"] == proposer.raw_response_sha256


def test_end_to_end_hallucination_still_fails_closed(monkeypatch):
    data = json.loads(_good_proposal_json())
    data["characters"].append({"character_id": "OLGA", "source_spans": ["Ольга"]})
    _install_fake_transport(monkeypatch, response=json.dumps(data, ensure_ascii=False))
    proposer = DeepSeekSceneTextProposer()
    with pytest.raises((HallucinationError, GroundingError)):
        interpret_scene_text(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT, proposer=proposer)
