#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Lab runtime-service tests (offline)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.character_lab import (
    BetaV1CurrentPolicy,
    LoadedState,
    RuntimeService,
    TurnCapture,
    TurnResult,
)
from services.crp_authoring import (
    AcceptanceRecord,
    CandidateCharacterPackage,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import write_acceptance_record

_REPO_ROOT = Path(__file__).resolve().parents[2]


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


def _accept(root, package, subject_id="kira", acceptance_id="acc-test"):
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
    write_acceptance_record(record, root)
    return record


def _service(tmp_path, package=None):
    package = package or _make_package()
    acceptance_root = tmp_path / "accepted"
    _accept(acceptance_root, package)
    service = RuntimeService(acceptance_root=acceptance_root, source_loader=lambda sid: package)
    return service, package


class TestResolve:
    def test_resolve_produces_loaded_state(self, tmp_path):
        service, package = _service(tmp_path)
        state = service.resolve(
            "kira",
            policy=BetaV1CurrentPolicy(),
            provider_id="deepseek",
            model="deepseek-v4-pro",
        )
        assert isinstance(state, LoadedState)
        assert state.character_id == "kira"
        assert state.acceptance_decision == "HUMAN_APPROVED"
        assert state.accepted_source_hash == compute_package_hash(package)
        assert state.runtime_loaded_package_hash == compute_package_hash(package)
        assert state.hash_match is True
        assert state.package_status == "DRAFT"
        assert state.variant_id == "KIRA_BETA_V1_CURRENT"
        assert state.provider_id == "deepseek"
        assert state.model == "deepseek-v4-pro"


class TestTurn:
    def test_turn_returns_turn_result(self, tmp_path):
        service, package = _service(tmp_path)

        def provider(messages):
            return "[KIRA] ответ"

        result = service.turn(
            "kira",
            policy=BetaV1CurrentPolicy(),
            history=[],
            user_message="Привет.",
            provider=provider,
            memory_root=tmp_path / "mem",
        )
        assert isinstance(result, TurnResult)
        assert result.response == "[KIRA] ответ"
        assert result.package_hash_unchanged is True
        assert result.variant_id == "KIRA_BETA_V1_CURRENT"
        assert len(result.persisted_event_ids) == 2

    def test_turn_with_capture(self, tmp_path):
        service, package = _service(tmp_path)
        cap = TurnCapture(tmp_path / "capture")

        def provider_factory(recorder):
            def provider(messages):
                body = json.dumps(
                    {"model": "m", "messages": messages}, ensure_ascii=False
                ).encode("utf-8")
                if recorder:
                    recorder({"event": "request", "payload": {"model": "m", "messages": messages}, "body": body})
                response = "[KIRA] ответ"
                if recorder:
                    recorder({"event": "response", "data": {
                        "id": "cmpl-1",
                        "model": "m",
                        "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                        "usage": {"total_tokens": 3},
                    }})
                return response
            return provider

        result = service.turn(
            "kira",
            policy=BetaV1CurrentPolicy(),
            history=[],
            user_message="Привет.",
            provider=None,
            provider_factory=provider_factory,
            memory_root=tmp_path / "mem",
            provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
            capture=cap,
            turn_id="turn-1",
        )
        assert result.request_hash is not None
        assert result.response_metadata.get("finish_reason") == "stop"
        assert result.response_metadata.get("response_id") == "cmpl-1"
        assert (cap.turn_dir("turn-1") / "request.json").exists()
        assert (cap.turn_dir("turn-1") / "manifest.json").exists()
        assert (cap.turn_dir("turn-1") / "response.json").exists()


class TestImmutability:
    def test_package_immutable(self, tmp_path):
        service, package = _service(tmp_path)
        with pytest.raises(FrozenInstanceError):
            package.package_id = "mutated"
        with pytest.raises(TypeError):
            package.psychology_candidate["x"] = ()

    def test_package_hash_unchanged_after_turn(self, tmp_path):
        service, package = _service(tmp_path)
        before = compute_package_hash(package)
        result = service.turn(
            "kira",
            policy=BetaV1CurrentPolicy(),
            history=[],
            user_message="Привет.",
            provider=lambda m: "ok",
            memory_root=tmp_path / "mem",
        )
        assert result.package_hash_after == before
        assert compute_package_hash(package) == before


class TestNoAcceptanceWriteImport:
    def test_character_lab_does_not_import_acceptance_writers(self):
        forbidden = ("write_acceptance_record", "materialize_acceptance", "accept_candidate")
        pkg_dir = _REPO_ROOT / "services" / "character_lab"
        sources = list(pkg_dir.rglob("*.py"))
        assert sources
        for path in sources:
            src = path.read_text(encoding="utf-8")
            for token in forbidden:
                assert token not in src, (
                    f"{path.name} references forbidden acceptance writer {token!r}"
                )
