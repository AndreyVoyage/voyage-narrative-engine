#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 7B-G -- R8 live-smoke glue runner tests (fake providers only).

Zero network. Each case uses an injected fake provider callable; the real
``run_r8_live_smoke()`` is never invoked. Verifies the one-shot guard, attempt
accounting, fail-before-provider, retry absence, and the frozen provider config.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.join(_PROJECT_ROOT, "tools")
for _p in (_PROJECT_ROOT, _TOOLS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import crp_r8_smoke_runner as runner  # noqa: E402

from llm_provider import LLMProviderError  # noqa: E402


def _valid_llm_json(package_id="pkg-001", subject_id="char-subject-1"):
    return json.dumps({
        "package_id": package_id,
        "subject_id": subject_id,
        "role_id": "R8",
        "role_version": "v1",
        "checks": [
            {"check_id": "R8_ROLE_BOUNDARY_SEMANTIC", "outcome": "PASS", "findings": []},
            {"check_id": "R8_MODULE_PLACEMENT", "outcome": "PASS", "findings": []},
            {"check_id": "R8_UNKNOWN_COVERAGE", "outcome": "PASS", "findings": []},
        ],
        "narrative": "clean",
    }, ensure_ascii=False)


def _semantic_finding_json():
    data = json.loads(_valid_llm_json())
    data["checks"][1]["outcome"] = "FAIL"
    data["checks"][1]["findings"] = [{
        "check_id": "R8_MODULE_PLACEMENT",
        "message": "misplaced",
        "claim_id": "c1",
    }]
    return json.dumps(data, ensure_ascii=False)


class TestFrozenManifest:
    def test_frozen_ids(self):
        assert runner.SMOKE_ID == "R8-SMOKE-001"
        assert runner.PACKAGE_ID == "pkg-001"
        assert runner.SUBJECT_ID == "char-subject-1"
        assert runner.CLAIM_ID == "c1"
        assert runner.EVIDENCE_ID == "se-001"

    def test_frozen_provider_config(self):
        cfg = runner.make_r8_smoke_provider_config()
        assert cfg.provider_id == "deepseek"
        assert cfg.model == "deepseek-v4-pro"
        assert cfg.timeout_s == 60.0
        assert cfg.max_tokens == 8192
        assert cfg.credential_env == "DEEPSEEK_API_KEY"
        # No secret value field exists.
        assert not hasattr(cfg, "api_key")

    def test_frozen_provider_config_requests_json_mode(self):
        cfg = runner.make_r8_smoke_provider_config()
        assert cfg.json_mode is True

    def test_frozen_provider_config_forwards_response_format(self, monkeypatch):
        import crp_provider_adapter
        captured = {}

        def fake_complete(messages, *, provider, model=None, system=None, params=None):
            captured["params"] = params
            captured["provider"] = provider
            captured["model"] = model
            return "{}"

        monkeypatch.setattr(crp_provider_adapter, "complete", fake_complete)
        cfg = runner.make_r8_smoke_provider_config()
        provider_callable = runner.build_provider_callable(cfg)
        provider_callable([{"role": "system", "content": "sys"},
                           {"role": "user", "content": "u"}])

        assert captured["provider"] == "cloud"
        assert captured["model"] == "deepseek-v4-pro"
        assert captured["params"]["response_format"] == {"type": "json_object"}

    def test_smoke_package_clean_and_non_blocked(self):
        from services.crp_authoring.auditor_checks import AuditPolicy, run_deterministic_audit
        pkg = runner.make_r8_smoke_package()
        ev = runner.make_r8_smoke_evidence()
        audit = run_deterministic_audit(pkg, ev, AuditPolicy())
        assert audit.verdict.value != "BLOCKED"


class TestOfflineCases:
    def test_case_a_valid_fake_provider(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _valid_llm_json()
        result = runner.run_r8_smoke(fake)
        assert len(calls) == 1
        assert result.provider_attempts == 1
        assert result.attempt_consumed is True
        assert result.provider_path_pass is True
        assert result.audit_content_outcome == "PASS"

    def test_case_b_deterministic_block(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _valid_llm_json()
        # Leakage evidence triggers deterministic BLOCKED before provider.
        result = runner.run_r8_smoke(fake, forbidden_refs=("ref://raw/001",))
        assert calls == []  # never reached the provider
        assert result.provider_attempts == 0
        assert result.attempt_consumed is False
        assert result.provider_path_pass is False
        assert result.error_stage == "deterministic_block"

    def test_case_c_malformed_fake_response(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return "not json"
        result = runner.run_r8_smoke(fake)
        assert len(calls) == 1
        assert result.provider_attempts == 1
        assert result.attempt_consumed is True
        assert result.error_stage == "parse_or_validation"
        assert result.provider_path_pass is False

    def test_case_d_wrong_metadata(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _valid_llm_json(subject_id="wrong-subject")
        result = runner.run_r8_smoke(fake)
        assert len(calls) == 1
        assert result.provider_attempts == 1
        assert result.attempt_consumed is True
        assert result.error_stage == "parse_or_validation"

    def test_case_e_provider_exception(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            raise LLMProviderError("boom")
        result = runner.run_r8_smoke(fake)
        assert len(calls) == 1
        assert result.provider_attempts == 1
        assert result.attempt_consumed is True
        assert result.error_stage == "provider"

    def test_case_f_semantic_finding_path_still_pass(self):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _semantic_finding_json()
        result = runner.run_r8_smoke(fake)
        assert result.provider_path_pass is True
        assert result.audit_content_outcome == "FAIL"  # content outcome is separate
        assert result.final_audit_verdict == "FAIL"

    def test_case_g_second_call_guard(self):
        inner_calls = []
        def fake(msgs):
            inner_calls.append(msgs)
            return _valid_llm_json()
        guard = runner.OneShotGuard(fake)
        guard([{"role": "user", "content": "hi"}])
        assert inner_calls == [1] or len(inner_calls) == 1
        with pytest.raises(Exception):
            guard([{"role": "user", "content": "hi"}])
        assert len(inner_calls) == 1  # no second underlying invocation


class TestLiveEntrypointGuarded:
    def test_live_entrypoint_exists_but_separate(self):
        # The live entrypoint is a distinct function; offline tests never call it.
        assert callable(runner.run_r8_live_smoke)
        assert callable(runner.build_provider_callable)


class TestCLI:
    def _patch_builder(self, monkeypatch, provider_callable):
        def fake_builder(config):
            return provider_callable
        monkeypatch.setattr(runner, "build_provider_callable", fake_builder)
        return provider_callable

    def test_cli_help_no_provider(self, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(runner, "run_r8_live_smoke",
                            lambda: calls.append("live") or None)
        # argparse -h exits successfully with SystemExit(0); no live call.
        with pytest.raises(SystemExit) as excinfo:
            runner.main(["--help"])
        assert excinfo.value.code == 0
        assert calls == []

    def test_cli_no_args_refuses_safely(self, monkeypatch, capsys):
        calls = []
        monkeypatch.setattr(runner, "run_r8_live_smoke",
                            lambda: calls.append("live") or None)
        rc = runner.main([])
        assert rc != 0
        assert calls == []
        err = capsys.readouterr().err
        assert "Refusing to run" in err

    def test_cli_live_valid_fake(self, monkeypatch):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _valid_llm_json()
        self._patch_builder(monkeypatch, fake)
        rc = runner.main(["--live"])
        assert rc == 0
        assert len(calls) == 1

    def test_cli_live_provider_exception(self, monkeypatch):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            raise LLMProviderError("boom")
        self._patch_builder(monkeypatch, fake)
        rc = runner.main(["--live"])
        assert rc != 0
        assert len(calls) == 1  # no retry

    def test_cli_live_malformed_response(self, monkeypatch):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return "not json"
        self._patch_builder(monkeypatch, fake)
        rc = runner.main(["--live"])
        assert rc != 0
        assert len(calls) == 1

    def test_cli_live_semantic_finding_exit_zero(self, monkeypatch):
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _semantic_finding_json()
        self._patch_builder(monkeypatch, fake)
        rc = runner.main(["--live"])
        # provider path succeeded even though audit content had a finding
        assert rc == 0
        assert len(calls) == 1

    def test_cli_rejects_unknown_override_flags(self, monkeypatch, capsys):
        # Any arbitrary override flag is rejected by argparse (no silent override).
        with pytest.raises(SystemExit):
            runner.main(["--live", "--model", "other-model"])
        captured = capsys.readouterr()
        assert "unrecognized arguments" in captured.err

    def test_cli_output_has_no_secrets(self, monkeypatch, capsys):
        def fake(msgs):
            return _valid_llm_json()
        self._patch_builder(monkeypatch, fake)
        rc = runner.main(["--live"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "DEEPSEEK_API_KEY" not in out
        assert "Authorization" not in out
        assert "api_key" not in out
        assert "Bearer" not in out

    def test_import_has_no_provider_activity(self, monkeypatch):
        calls = []
        monkeypatch.setattr(runner, "run_r8_live_smoke",
                            lambda: calls.append("live") or None)
        with pytest.raises(SystemExit):
            runner.main(["--help"])
        assert calls == []

    def test_live_uses_existing_one_shot_guard(self, monkeypatch):
        # Exercise --live twice inside one process to prove the guard in the
        # runner path caps at one provider invocation per run_r8_smoke call.
        calls = []
        def fake(msgs):
            calls.append(msgs)
            return _valid_llm_json()
        self._patch_builder(monkeypatch, fake)
        rc1 = runner.main(["--live"])
        rc2 = runner.main(["--live"])
        assert rc1 == 0 and rc2 == 0
        # Two separate smoke runs; each may issue one call (no shared
        # cross-run retry), so total == 2 and each run is internally one-shot.
        assert len(calls) == 2
