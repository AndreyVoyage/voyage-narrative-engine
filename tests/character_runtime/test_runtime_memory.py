#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA Runtime/CIS persistent-memory tests (offline, provider-free).

Proves the accepted KIRA package loads through the acceptance gate, runtime
events persist across backend re-instantiation, recovered memory reaches runtime
context assembly, and the Accepted Package + AcceptanceRecord remain unchanged.

No provider, no network, no reconstruction, no R1/R2/R3/R4/R8, no Hidden-B read.
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.character_runtime import (
    AcceptedCharacter,
    CharacterRuntimeError,
    RuntimeEvent,
    RuntimeMemoryBackend,
    load_accepted_character,
    start_session,
)
from services.crp_authoring import (
    AcceptanceRecord,
    CandidateCharacterPackage,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import (
    load_acceptance_record,
    write_acceptance_record,
)
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_ROOT = REPO_ROOT / "accepted"
ACCEPTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
RUN015_DEFAULT = Path("C:/DEV/Narrative/LOCAL_STORAGE/crp_r4_live_runs/RUN_015.stdout.json")


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


def _source_loader(package):
    return lambda subject_id: package


def _run015_loader():
    path = Path(os.environ.get("KIRA_RUN_015_STDOUT", str(RUN015_DEFAULT)))
    if not path.exists():
        pytest.skip("RUN_015.stdout.json not available")

    def _loader(subject_id):
        data = json.loads(path.read_text(encoding="utf-8"))
        package = rehydrate_candidate_package(data["candidate_package"])
        assert package.subject_id == subject_id
        return package

    return _loader

# ---------------------------------------------------------------------------
# T1-T4 -- accepted-package loading gate
# ---------------------------------------------------------------------------

class TestAcceptedPackageGate:
    def test_t1_real_accepted_kira_resolves(self):
        accepted = load_accepted_character(
            "kira",
            acceptance_root=ACCEPTANCE_ROOT,
            source_loader=_run015_loader(),
        )
        assert isinstance(accepted, AcceptedCharacter)
        assert accepted.subject_id == "kira"
        assert accepted.source_candidate_hash == ACCEPTED_HASH

    def test_t1_hermetic_resolves(self, tmp_path):
        package = _make_package()
        acceptance_root = tmp_path / "accepted"
        _accept(acceptance_root, package)
        accepted = load_accepted_character(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=_source_loader(package),
        )
        assert accepted.subject_id == "kira"
        assert accepted.source_candidate_hash == compute_package_hash(package)

    def test_t2_non_accepted_subject_fails_closed(self, tmp_path):
        package = _make_package(subject_id="draft-only")
        with pytest.raises(CharacterRuntimeError):
            load_accepted_character(
                "draft-only",
                acceptance_root=tmp_path / "accepted",
                source_loader=_source_loader(package),
            )

    def test_t3_resolved_hash_equals_exact_hash(self, tmp_path):
        package = _make_package()
        acceptance_root = tmp_path / "accepted"
        _accept(acceptance_root, package)
        accepted = load_accepted_character(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=_source_loader(package),
        )
        assert accepted.source_candidate_hash == compute_package_hash(package)

    def test_t4_typed_immutable_package_loaded(self, tmp_path):
        package = _make_package()
        acceptance_root = tmp_path / "accepted"
        _accept(acceptance_root, package)
        accepted = load_accepted_character(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=_source_loader(package),
        )
        assert isinstance(accepted.package, CandidateCharacterPackage)
        assert is_dataclass(accepted.package)
        with pytest.raises(Exception):
            accepted.package.status = PackageStatus.HUMAN_APPROVED  # type: ignore[misc]

# ---------------------------------------------------------------------------
# T5-T10 -- persistent-memory session flow
# ---------------------------------------------------------------------------

def _run_two_session_flow(tmp_path):
    package = _make_package()
    acceptance_root = tmp_path / "accepted"
    memory_root = tmp_path / "memory"
    _accept(acceptance_root, package)
    loader = _source_loader(package)

    s1 = start_session(
        "kira",
        acceptance_root=acceptance_root,
        source_loader=loader,
        memory_root=memory_root,
        session_id="session-1",
    )
    event = s1.record_runtime_event(
        "USER_STATED_PREFERENCE",
        "The user prefers tea without sugar.",
        event_id="evt-1",
        created_at="2026-08-29T00:00:00+00:00",
    )
    s1.close()

    s2 = start_session(
        "kira",
        acceptance_root=acceptance_root,
        source_loader=loader,
        memory_root=memory_root,
        session_id="session-2",
    )
    return {
        "package": package,
        "event": event,
        "s1": s1,
        "s2": s2,
        "acceptance_root": acceptance_root,
        "memory_root": memory_root,
    }


class TestPersistentMemoryFlow:
    def test_t5_session_1_starts(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        assert flow["s1"].session_id == "session-1"

    def test_t6_event_persisted(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        backend = RuntimeMemoryBackend(flow["memory_root"], "kira")
        try:
            events = backend.load_events("kira")
        finally:
            backend.close()
        assert flow["event"].event_id in {e.event_id for e in events}

    def test_t7_session_1_closed(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        with pytest.raises(CharacterRuntimeError):
            flow["s1"].record_runtime_event("X", "Y")

    def test_t8_new_instance_starts_session_2(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        assert flow["s2"].session_id == "session-2"
        assert flow["s2"] is not flow["s1"]

    def test_t9_session_2_recovers_event(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        ctx = flow["s2"].build_runtime_context()
        recovered_ids = {e["event_id"] for e in ctx["runtime_memory"]}
        assert "evt-1" in recovered_ids

    def test_t10_recovered_event_in_context(self, tmp_path):
        flow = _run_two_session_flow(tmp_path)
        ctx = flow["s2"].build_runtime_context()
        recovered = {e["event_id"]: e for e in ctx["runtime_memory"]}
        assert recovered["evt-1"]["meaning"] == "The user prefers tea without sugar."
        assert recovered["evt-1"]["event_type"] == "USER_STATED_PREFERENCE"
        assert ctx["subject_id"] == "kira"
        assert ctx["source_candidate_hash"] == compute_package_hash(flow["package"])

# ---------------------------------------------------------------------------
# T11-T15 -- immutability, fail-closed hash, provider-freedom
# ---------------------------------------------------------------------------

class TestImmutabilityAndBoundaries:
    def _flow_with_package(self, tmp_path):
        package = _make_package()
        acceptance_root = tmp_path / "accepted"
        memory_root = tmp_path / "memory"
        _accept(acceptance_root, package)
        loader = _source_loader(package)
        s1 = start_session(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=loader,
            memory_root=memory_root,
            session_id="session-1",
        )
        s1.record_runtime_event(
            "USER_STATED_PREFERENCE",
            "The user prefers tea without sugar.",
            event_id="evt-1",
            created_at="2026-08-29T00:00:00+00:00",
        )
        s1.close()
        s2 = start_session(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=loader,
            memory_root=memory_root,
            session_id="session-2",
        )
        return package, acceptance_root, s2

    def test_t11_package_hash_before_equals_after(self, tmp_path):
        package = _make_package()
        before = compute_package_hash(package)
        acceptance_root = tmp_path / "accepted"
        _accept(acceptance_root, package)
        loader = _source_loader(package)
        s1 = start_session(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=loader,
            memory_root=tmp_path / "memory",
            session_id="session-1",
        )
        s1.record_runtime_event("USER_STATED_PREFERENCE", "The user prefers tea without sugar.")
        s1.close()
        s2 = start_session(
            "kira",
            acceptance_root=acceptance_root,
            source_loader=loader,
            memory_root=tmp_path / "memory",
            session_id="session-2",
        )
        s2.build_runtime_context()
        s2.close()
        assert compute_package_hash(package) == before

    def test_t12_acceptance_record_before_equals_after(self, tmp_path):
        package, acceptance_root, s2 = self._flow_with_package(tmp_path)
        before = load_acceptance_record(acceptance_root, "kira")
        s2.build_runtime_context()
        s2.close()
        after = load_acceptance_record(acceptance_root, "kira")
        assert before == after

    def test_t13_runtime_memory_not_in_package(self, tmp_path):
        package, acceptance_root, s2 = self._flow_with_package(tmp_path)
        ctx = s2.build_runtime_context()
        s2.close()
        # Memory lives only in runtime context, never in package seed data.
        assert any(
            e["meaning"] == "The user prefers tea without sugar."
            for e in ctx["runtime_memory"]
        )
        assert tuple(package.claims) == ()
        assert tuple(package.unknowns) == ()
        assert dict(package.psychology_candidate) == {}
        assert dict(package.voice_candidate) == {}

    def test_t14_wrong_accepted_hash_fails_closed(self, tmp_path):
        package_a = _make_package(package_id="pkg-a")
        package_b = _make_package(package_id="pkg-b")
        acceptance_root = tmp_path / "accepted"
        _accept(acceptance_root, package_a)  # binds package_a's hash
        with pytest.raises(CharacterRuntimeError):
            load_accepted_character(
                "kira",
                acceptance_root=acceptance_root,
                source_loader=_source_loader(package_b),  # different hash
            )

    def test_t15_no_provider_required(self):
        prod_root = REPO_ROOT / "services" / "character_runtime"
        forbidden = (
            "llm_provider", "openai", "anthropic", "requests", "httpx",
            "urllib", "socket", "http.client", "aiohttp",
        )
        for py_file in sorted(prod_root.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            modules = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    modules.append(node.module or "")
            for m in modules:
                assert not any(m.startswith(f) for f in forbidden), (
                    f"{py_file}: provider/network import {m}"
                )
