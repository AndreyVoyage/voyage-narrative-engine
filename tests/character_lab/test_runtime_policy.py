#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA_BETA_V1_CURRENT frozen-baseline regression tests (offline).

Proves the new policy reproduces the current committed tools/kira_chat_cli.py
provider-context behavior EXACTLY, without injecting full package claim content
or changing legacy memory ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone

from kira_chat_cli import KiraChatCLI
from services.character_lab import (
    BETA_V1_VARIANT_VERSION,
    BetaV1CurrentPolicy,
    KIRA_BETA_V1_CURRENT,
)
from services.character_runtime import RuntimeEvent
from services.crp_authoring import (
    AcceptanceRecord,
    CandidateCharacterPackage,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import write_acceptance_record


def _make_package(subject_id="kira", package_id="pkg-test", package_version=0):
    return CandidateCharacterPackage(
        package_id=package_id,
        subject_id=subject_id,
        package_version=package_version,
        source_snapshot_id="snapshot-test",
        role_result_refs=(),
        claims=(),
        contradictions=(),
        unknowns=(),
        psychology_candidate={},
        voice_candidate={},
        validation_results={},
        audit_result=None,
        provenance_manifest={},
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        status=PackageStatus.DRAFT,
    )


def _accept(acceptance_root, package, subject_id="kira", acceptance_id="acc-test"):
    record = AcceptanceRecord(
        acceptance_id=acceptance_id,
        package_id=package.package_id,
        package_version=package.package_version,
        subject_id=subject_id,
        package_hash=compute_package_hash(package),
        audit_id=None,
        decision=PackageStatus.HUMAN_APPROVED,
        decided_by="owner",
        decided_at="2026-08-29T00:00:00+00:00",
        reason=None,
    )
    write_acceptance_record(record, acceptance_root)
    return record


class FakeProvider:
    def __init__(self, response="[KIRA] fake response"):
        self.response = response
        self.calls = []

    def __call__(self, messages):
        self.calls.append(list(messages))
        return self.response


def _make_cli(tmp_path, provider=None):
    package = _make_package()
    acceptance_root = tmp_path / "accepted"
    _accept(acceptance_root, package)
    cli = KiraChatCLI(
        acceptance_root=acceptance_root,
        source_loader=lambda sid: package,
        memory_root=tmp_path / "memory",
        provider=provider or FakeProvider(),
        subject_id="kira",
    )
    return cli, package


class TestVariantIdentity:
    def test_identity_and_version(self):
        policy = BetaV1CurrentPolicy()
        assert policy.variant_id == KIRA_BETA_V1_CURRENT
        assert policy.variant_version == BETA_V1_VARIANT_VERSION


class TestBetaV1Regression:
    def test_system_prompt_exact_match_no_memory(self, tmp_path):
        cli, _ = _make_cli(tmp_path)
        cli.start()
        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        expected = cli._build_system_prompt()
        assembly = policy.assemble_context(
            runtime_context=ctx,
            session_id=cli.session.session_id,
            history=[],
            user_message="Привет.",
        )
        assert assembly.messages[0]["content"] == expected

    def test_system_prompt_exact_match_with_prior_memory(self, tmp_path):
        cli, _ = _make_cli(tmp_path)
        cli.start()
        cli.session._memory.record_event(RuntimeEvent(
            event_id="evt-prior-1",
            subject_id="kira",
            session_id="session-prior",
            event_type="USER_MESSAGE",
            meaning="Я люблю зелёный чай.",
            created_at="2026-08-29T00:00:00+00:00",
        ))
        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        expected = cli._build_system_prompt()
        assembly = policy.assemble_context(
            runtime_context=ctx,
            session_id=cli.session.session_id,
            history=[],
            user_message="Привет.",
        )
        assert assembly.messages[0]["content"] == expected

    def test_message_sequence_exact_match(self, tmp_path):
        provider = FakeProvider()
        cli, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_user_message("Первый вопрос.")
        cli.handle_user_message("Второй вопрос.")
        cli_messages = provider.calls[1]

        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        history = [
            {"role": "user", "content": "Первый вопрос."},
            {"role": "assistant", "content": provider.response},
        ]
        assembly = policy.assemble_context(
            runtime_context=ctx,
            session_id=cli.session.session_id,
            history=history,
            user_message="Второй вопрос.",
        )
        assert list(assembly.messages) == cli_messages

    def test_no_full_character_claims_added(self, tmp_path):
        cli, _ = _make_cli(tmp_path)
        cli.start()
        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        assembly = policy.assemble_context(
            runtime_context=ctx,
            session_id=cli.session.session_id,
            history=[],
            user_message="Привет.",
        )
        system = assembly.messages[0]["content"]
        assert "psychology_candidate" not in system
        assert "identity_biography_candidate" not in system
        assert "boundaries_candidate" not in system
        assert "voice_candidate" not in system
