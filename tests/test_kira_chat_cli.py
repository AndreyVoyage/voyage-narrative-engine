#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive terminal chat CLI tests (offline, deterministic fake provider).

Proves the Accepted KIRA gate, session lifecycle, dialogue persistence/recovery,
command handling, and package immutability — all without a real provider/network.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.crp_authoring import (  # noqa: E402
    AcceptanceRecord,
    CandidateCharacterPackage,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import (  # noqa: E402
    load_acceptance_record,
    write_acceptance_record,
)
from services.character_runtime import CharacterRuntimeError  # noqa: E402
from kira_chat_cli import KiraChatCLI  # noqa: E402


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
    """Deterministic provider double that records every call."""

    def __init__(self, response="[KIRA] fake response"):
        self.response = response
        self.calls = []

    def __call__(self, messages):
        self.calls.append(list(messages))
        return self.response


def _make_cli(tmp_path, provider=None, subject_id="kira", memory_root=None):
    package = _make_package(subject_id=subject_id)
    acceptance_root = tmp_path / "accepted"
    _accept(acceptance_root, package, subject_id=subject_id)
    cli = KiraChatCLI(
        acceptance_root=acceptance_root,
        source_loader=lambda sid: package,
        memory_root=memory_root or (tmp_path / "memory"),
        provider=provider or FakeProvider(),
        subject_id=subject_id,
    )
    return cli, package, acceptance_root

class TestGateAndSession:
    def test_t1_accepted_kira_loads(self, tmp_path):
        cli, package, _ = _make_cli(tmp_path)
        cli.start()
        assert cli.accepted.subject_id == "kira"
        assert cli.accepted.source_candidate_hash == compute_package_hash(package)

    def test_t2_unaccepted_subject_fails_closed(self, tmp_path):
        # A DRAFT-only source with no acceptance record must be refused.
        package = _make_package(subject_id="draft-only")
        acceptance_root = tmp_path / "accepted"
        cli = KiraChatCLI(
            acceptance_root=acceptance_root,
            source_loader=lambda sid: package,
            memory_root=tmp_path / "memory",
            provider=FakeProvider(),
            subject_id="draft-only",
        )
        with pytest.raises(CharacterRuntimeError):
            cli.start()

    def test_t3_cli_creates_runtime_session(self, tmp_path):
        cli, _, _ = _make_cli(tmp_path)
        cli.start()
        assert cli.session is not None
        assert cli.session.session_id

    def test_t4_provider_receives_accepted_package_context(self, tmp_path):
        provider = FakeProvider()
        cli, package, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_user_message("Привет.")
        system = provider.calls[0][0]["content"]
        assert "subject_id=kira" in system
        assert "package_id=pkg-test" in system
        assert compute_package_hash(package) in system

class TestDialogueAndPersistence:
    def test_t5_provider_receives_session_history(self, tmp_path):
        provider = FakeProvider()
        cli, _, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_user_message("Первый вопрос.")
        cli.handle_user_message("Второй вопрос.")
        # Second call must include the first user turn AND the first character reply.
        second_messages = provider.calls[1]
        contents = [m["content"] for m in second_messages if m["role"] != "system"]
        assert "Первый вопрос." in contents
        assert provider.response in contents
        assert "Второй вопрос." in contents

    def test_t6_one_user_turn_invokes_provider_once(self, tmp_path):
        provider = FakeProvider()
        cli, _, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_user_message("Привет.")
        assert len(provider.calls) == 1

    def test_t7_user_and_character_turns_persisted(self, tmp_path):
        cli, _, _ = _make_cli(tmp_path)
        cli.start()
        cli.handle_user_message("Привет, Кира.")
        ctx = cli.session.build_runtime_context()
        types = [e["event_type"] for e in ctx["runtime_memory"]]
        assert "USER_MESSAGE" in types
        assert "CHARACTER_MESSAGE" in types

    def test_t8_new_instance_recovers_prior_memory(self, tmp_path):
        memory_root = tmp_path / "memory"
        cli1, _, _ = _make_cli(tmp_path, memory_root=memory_root)
        cli1.start()
        cli1.handle_user_message("Запомни: я люблю зелёный чай.")
        cli1.close()

        provider2 = FakeProvider()
        cli2, _, _ = _make_cli(tmp_path, provider=provider2, memory_root=memory_root)
        cli2.start()
        view = cli2.memory_view()
        assert "я люблю зелёный чай" in view
        cli2.close()

class TestCommandsAndImmutability:
    def test_t9_memory_view_without_provider_call(self, tmp_path):
        provider = FakeProvider()
        cli, _, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_user_message("Привет.")
        calls_before = len(provider.calls)
        view = cli.handle_command("/memory")
        assert len(provider.calls) == calls_before
        assert "Привет." in view

    def test_t10_new_starts_session_preserving_memory(self, tmp_path):
        cli, _, _ = _make_cli(tmp_path)
        cli.start()
        cli.handle_user_message("Привет.")
        old_session_id = cli.session.session_id
        cli.handle_command("/new")
        assert cli.session.session_id != old_session_id
        view = cli.memory_view()
        assert "Привет." in view

    def test_t11_exit_closes_backend_cleanly(self, tmp_path):
        cli, _, _ = _make_cli(tmp_path)
        cli.start()
        cli.handle_command("/exit")
        assert cli.should_exit is True
        cli.close()  # idempotent; must not raise
        assert cli.session is None

    def test_t12_unknown_slash_command_no_provider(self, tmp_path):
        provider = FakeProvider()
        cli, _, _ = _make_cli(tmp_path, provider=provider)
        cli.start()
        cli.handle_command("/bogus")
        assert len(provider.calls) == 0

    def test_t13_package_hash_unchanged(self, tmp_path):
        cli, package, _ = _make_cli(tmp_path)
        before = compute_package_hash(package)
        cli.start()
        cli.handle_user_message("Привет.")
        cli.handle_user_message("Как дела?")
        assert compute_package_hash(package) == before

    def test_t14_acceptance_record_unchanged(self, tmp_path):
        cli, _, acceptance_root = _make_cli(tmp_path)
        before = load_acceptance_record(acceptance_root, "kira")
        cli.start()
        cli.handle_user_message("Привет.")
        after = load_acceptance_record(acceptance_root, "kira")
        assert before == after

    def test_t15_runtime_dialogue_not_in_package(self, tmp_path):
        cli, package, _ = _make_cli(tmp_path)
        cli.start()
        cli.handle_user_message("Привет, Кира.")
        assert tuple(package.claims) == ()
        assert tuple(package.unknowns) == ()
        assert dict(package.psychology_candidate) == {}
        assert dict(package.voice_candidate) == {}

    def test_t16_no_real_provider_required(self, tmp_path):
        provider = FakeProvider()
        cli, _, _ = _make_cli(tmp_path, provider=provider)
        assert cli._provider is provider
        cli.start()
        cli.handle_user_message("Привет.")
        assert len(provider.calls) == 1
