#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline KIRA Runtime/CIS persistent-memory smoke (provider-free).

Proves the accepted KIRA package loads through the acceptance gate, a runtime
event persists across backend re-instantiation, the recovered memory reaches
runtime context assembly, and the Accepted Package + AcceptanceRecord remain
unchanged. No provider, no network, no reconstruction, no R1/R2/R3/R4/R8.

Run:  py tools/kira_runtime_memory_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.character_runtime import (  # noqa: E402
    CharacterRuntimeError,
    load_accepted_character,
    start_session,
)
from services.crp_authoring.auditor_checks import compute_package_hash  # noqa: E402
from services.crp_authoring.candidate_rehydration import (  # noqa: E402
    rehydrate_candidate_package,
)

ACCEPTANCE_ROOT = _REPO_ROOT / "accepted"
SUBJECT = "kira"
_DEFAULT_RUN015 = Path("C:/DEV/Narrative/LOCAL_STORAGE/crp_r4_live_runs/RUN_015.stdout.json")


def _resolve_run015() -> Path:
    return Path(os.environ.get("KIRA_RUN_015_STDOUT", str(_DEFAULT_RUN015)))


def _make_source_loader(run015: Path):
    def _loader(subject_id: str):
        data = json.loads(run015.read_text(encoding="utf-8"))
        package = rehydrate_candidate_package(data["candidate_package"])
        if package.subject_id != subject_id:
            raise CharacterRuntimeError(
                f"source subject {package.subject_id!r} != requested {subject_id!r}"
            )
        return package

    return _loader


def run_smoke() -> dict:
    run015 = _resolve_run015()
    if not run015.exists():
        raise CharacterRuntimeError(f"RUN_015 source artifact not found: {run015}")

    source_loader = _make_source_loader(run015)
    acceptance_path = ACCEPTANCE_ROOT / SUBJECT / "ACCEPTANCE.json"
    acceptance_before = acceptance_path.read_bytes()

    with tempfile.TemporaryDirectory(prefix="kira_runtime_memory_") as tmp:
        memory_root = Path(tmp)

        # 1) load accepted KIRA through the gate
        accepted = load_accepted_character(
            SUBJECT,
            acceptance_root=ACCEPTANCE_ROOT,
            source_loader=source_loader,
        )
        package_hash_before = compute_package_hash(accepted.package)

        # 2) session #1
        session_1 = start_session(
            SUBJECT,
            acceptance_root=ACCEPTANCE_ROOT,
            source_loader=source_loader,
            memory_root=memory_root,
            session_id="session-1",
        )

        # 3) persist one synthetic, character-independent runtime event
        event = session_1.record_runtime_event(
            "USER_STATED_PREFERENCE",
            "The user prefers tea without sugar.",
            event_id="evt-1",
            created_at="2026-08-29T00:00:00+00:00",
        )

        # 4) close session/backend #1
        session_1.close()

        # 5-6) completely new runtime/backend instance starts session #2
        session_2 = start_session(
            SUBJECT,
            acceptance_root=ACCEPTANCE_ROOT,
            source_loader=source_loader,
            memory_root=memory_root,
            session_id="session-2",
        )

        # 7-8) recover persisted memory into runtime context
        context = session_2.build_runtime_context()
        recovered = {
            e["event_id"]: e["meaning"] for e in context["runtime_memory"]
        }
        memory_available = recovered.get("evt-1") == "The user prefers tea without sugar."

        # 9) accepted package + acceptance record unchanged
        package_hash_after = compute_package_hash(accepted.package)
        acceptance_after = acceptance_path.read_bytes()
        package_unchanged = package_hash_before == package_hash_after
        acceptance_unchanged = acceptance_before == acceptance_after

        session_2.close()

        return {
            "ACCEPTED_KIRA_LOADED": True,
            "SESSION_1_STARTED": True,
            "RUNTIME_EVENT_PERSISTED": True,
            "SESSION_1_CLOSED": True,
            "RUNTIME_RESTARTED": True,
            "SESSION_2_STARTED": True,
            "RUNTIME_MEMORY_RECOVERED": "evt-1" in recovered,
            "MEMORY_AVAILABLE_IN_CONTEXT": memory_available,
            "ACCEPTED_PACKAGE_UNCHANGED": package_unchanged,
            "SMOKE_PASS": (
                memory_available and package_unchanged and acceptance_unchanged
            ),
            "subject_id": SUBJECT,
            "source_candidate_hash": accepted.source_candidate_hash,
            "package_hash_before": package_hash_before,
            "package_hash_after": package_hash_after,
            "acceptance_record_unchanged": acceptance_unchanged,
            "temporary_memory_root": str(memory_root),
            "recovered_event_count": len(context["runtime_memory"]),
        }


def main(argv=None) -> int:
    try:
        result = run_smoke()
    except CharacterRuntimeError as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
