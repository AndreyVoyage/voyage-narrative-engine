#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA_GROUNDED_V2 point-in-time epistemic integration (offline, NO provider).

Proves: information not epistemically available at ``at_seq`` is physically
ABSENT from the Grounded provider request; available information MAY be
present. Visibility is decided entirely by Character Core / the epistemic
bridge -- the policy/service only supply the material the pipeline already
selected and render what the selector reports visible. Working-context bounds
stay authoritative. Beta v1 is untouched.

Synthetic identities (``character-a`` / ``character-b``) for the policy-layer
tests so the integration code stays obviously generic; the accepted ``kira``
package is used only for the service-wiring / bound / Beta tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_core.epistemics import EpistemicEnvelope
from services.character_lab import (
    BetaV1CurrentPolicy,
    GroundedV2Policy,
    RuntimeService,
    TurnCapture,
)
from services.character_lab.epistemic_bridge import build_runtime_epistemic_context
from services.character_lab.runtime_policy import (
    GROUNDED_V2_RAW_MEMORY_MAX_EVENTS,
    _GROUNDED_V2_CONSMEM_LINE_PREFIX,
    _GROUNDED_V2_EPI_HEADER,
    _GROUNDED_V2_MEMORY_LINE_PREFIX,
)
from services.character_lab.scene import (
    SceneEpistemicClaim,
    new_scene,
    render_scene_block,
    with_epistemic_claims,
)
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import (
    ConsolidatedMemoryBackend,
    RuntimeEvent,
    RuntimeMemoryBackend,
)
from services.character_runtime.consolidated_memory import DECISION_APPROVE

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
_POLICY_SRC = _REPO_ROOT / "services" / "character_lab" / "runtime_policy.py"
_SERVICE_SRC = _REPO_ROOT / "services" / "character_lab" / "runtime_service.py"

A, B = "character-a", "character-b"
MARINA = "Марина уже уехала."
DOOR_LOCKED = "Дверь заперта."
DOOR_OPEN = "Дверь открыта."


# --------------------------------------------------------------------------
# policy-layer helpers (controlled snapshot / at_seq / perceiver)
# --------------------------------------------------------------------------


def _evt(eid, meaning, seq, *, subject=A, etype="USER_MESSAGE", prov="USER_STATED"):
    return RuntimeEvent(
        event_id=eid, subject_id=subject, session_id="s1", event_type=etype,
        meaning=meaning, created_at="2026-01-01T00:00:00+00:00", seq=seq,
        provenance=prov,
    )


def _causal(events):
    return [
        {"event_id": e.event_id, "session_id": e.session_id, "event_type": e.event_type,
         "meaning": e.meaning, "created_at": e.created_at, "seq": e.seq,
         "provenance": e.provenance}
        for e in events
    ]


def _bounded_bridge_events(events, consolidated_records):
    """Mirror exactly what ``RuntimeService.turn`` now feeds the bridge:
    the existing Grounded bounded raw selection + only the consolidated
    basis events -- NOT the whole historical log."""
    events = tuple(events)
    by_id = {e.event_id: e for e in events}
    rc_pre = {"subject_id": A, "causal_memory": _causal(events)}
    bounded_dicts = GroundedV2Policy().select_memory(rc_pre, "s")
    bounded_raw = [by_id[d["event_id"]] for d in bounded_dicts if d.get("event_id") in by_id]
    return RuntimeService._select_epistemic_runtime_inputs(
        bounded_raw, tuple(consolidated_records), by_id
    )


def _assemble(
    *, subject=A, perceiver=None, at_seq, events=(), explicit=(),
    consolidated_records=(), consolidated_dicts=(), user="Что нам делать?",
):
    perceiver = perceiver or subject
    snap = build_runtime_epistemic_context(
        subject_id=subject,
        runtime_events=_bounded_bridge_events(events, consolidated_records),
        consolidated_records=tuple(consolidated_records),
        explicit_envelopes=tuple(explicit), perceiver_id=perceiver, at_seq=at_seq,
    )
    rc = {
        "subject_id": subject,
        "causal_memory": _causal(events),
        "consolidated_memory": list(consolidated_dicts),
        "epistemic_snapshot": snap,
        "epistemic_at_seq": at_seq,
        "epistemic_perceiver_id": perceiver,
    }
    asm = GroundedV2Policy().assemble_context(
        runtime_context=rc, session_id="s", history=[], user_message=user, scene=None
    )
    sys_text = "\n".join(m["content"] for m in asm.messages if m["role"] == "system")
    return asm, sys_text, snap


def _kinds(asm, prefix):
    return [i for i in asm.manifest.items if i.kind == prefix]


# --------------------------------------------------------------------------
# Acceptance A -- primary point-in-time proof
# --------------------------------------------------------------------------


class TestAcceptanceA_PointInTime:
    def test_seq20_report_absent_at_seq19_present_at_seq20(self):
        evt = _evt("evt-r", MARINA, 20)
        _, before, snap_before = _assemble(at_seq=19, events=[evt])
        assert MARINA not in before                       # not yet available
        assert snap_before.visible_envelopes == ()

        _, after, snap_after = _assemble(at_seq=20, events=[evt])
        assert MARINA in after                            # boundary is inclusive
        assert f"{_GROUNDED_V2_MEMORY_LINE_PREFIX}{MARINA}" in after

    def test_no_future_knowledge_leak(self):
        evt = _evt("evt-r", MARINA, 20)
        for seq in (0, 1, 10, 19):
            _, txt, _ = _assemble(at_seq=seq, events=[evt])
            assert MARINA not in txt, seq


# --------------------------------------------------------------------------
# Acceptance B -- perceiver isolation
# --------------------------------------------------------------------------


class TestAcceptanceB_Perceiver:
    def test_wrong_perceiver_cannot_receive_report(self):
        evt = _evt("evt-r", MARINA, 20)  # projected perceiver = subject "character-a"
        _, txt, _ = _assemble(subject=A, perceiver=B, at_seq=20, events=[evt])
        assert MARINA not in txt

    def test_report_present_only_when_perceiver_explicitly_included(self):
        evt = _evt("evt-r", MARINA, 20)
        explicit = (
            EpistemicEnvelope(
                meaning=MARINA, epistemic_kind="USER_REPORT", provenance="authored",
                basis_event_ids=("evt-r",), confidence=1.0, perceiver_ids=(B,),
                valid_from_seq=20,
            ),
        )
        _, txt, _ = _assemble(subject=A, perceiver=B, at_seq=20, events=[evt], explicit=explicit)
        assert MARINA in txt


# --------------------------------------------------------------------------
# Acceptance C -- WORLD_FACT vs private CHARACTER_BELIEF, contradictions
# --------------------------------------------------------------------------


class TestAcceptanceC_FactBeliefContradiction:
    def _fact(self, meaning, perceivers=()):
        return EpistemicEnvelope(
            meaning=meaning, epistemic_kind="WORLD_FACT", provenance="authored",
            basis_event_ids=("authored-f",), confidence=1.0, perceiver_ids=perceivers,
        )

    def _belief(self, meaning, holder=A):
        return EpistemicEnvelope(
            meaning=meaning, epistemic_kind="CHARACTER_BELIEF", provenance="authored",
            basis_event_ids=("authored-b",), confidence=0.6, holder_id=holder,
        )

    def test_private_belief_delivered_inaccessible_fact_absent(self):
        asm, txt, _ = _assemble(
            at_seq=100,
            explicit=(self._fact(DOOR_LOCKED, perceivers=()), self._belief(DOOR_OPEN)),
        )
        assert _GROUNDED_V2_EPI_HEADER in txt
        assert f"[CHARACTER_BELIEF] {DOOR_OPEN}" in txt   # holder sees own belief
        assert DOOR_LOCKED not in txt                     # no perceiver -> hidden
        assert not _kinds(asm, "system.consolidated_memory")

    def test_perceived_fact_and_contradictory_belief_coexist(self):
        asm, txt, _ = _assemble(
            at_seq=100,
            explicit=(self._fact(DOOR_LOCKED, perceivers=(A,)), self._belief(DOOR_OPEN)),
        )
        assert f"[WORLD_FACT] {DOOR_LOCKED}" in txt
        assert f"[CHARACTER_BELIEF] {DOOR_OPEN}" in txt   # both, unreconciled
        # nothing in the segment tells the model to reconcile / replace
        seg = txt.split(_GROUNDED_V2_EPI_HEADER, 1)[1]
        assert "разреш" in seg and "не заменяет" in seg
        assert "замени" not in seg.replace("не заменяет", "")

    def test_belief_not_visible_to_other_character(self):
        _, txt, _ = _assemble(subject=A, perceiver=B, at_seq=100, explicit=(self._belief(DOOR_OPEN),))
        assert DOOR_OPEN not in txt

    def test_user_report_and_interpretation_keep_their_labels(self):
        rep = EpistemicEnvelope(
            meaning="Собеседник сказал X.", epistemic_kind="USER_REPORT",
            provenance="authored", basis_event_ids=("authored-r",), confidence=1.0,
            perceiver_ids=(A,),
        )
        interp = EpistemicEnvelope(
            meaning="Возможно, он раздражён.", epistemic_kind="CHARACTER_INTERPRETATION",
            provenance="authored", basis_event_ids=("authored-i",), confidence=0.4,
            holder_id=A,
        )
        _, txt, _ = _assemble(at_seq=100, explicit=(rep, interp))
        assert "[USER_REPORT] Собеседник сказал X." in txt          # not relabelled WORLD_FACT
        assert "[WORLD_FACT] Собеседник сказал X." not in txt
        assert "[CHARACTER_INTERPRETATION] Возможно, он раздражён." in txt  # not a fact
        assert "[WORLD_FACT] Возможно, он раздражён." not in txt


# --------------------------------------------------------------------------
# Acceptance D -- consolidated causal seq (source, not approval)
# --------------------------------------------------------------------------


class TestAcceptanceD_ConsolidatedCausality:
    def _seed(self, tmp_path):
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, A)
        for i in range(9):  # events seq 1..9
            mb.record_event(RuntimeEvent(event_id=f"e-{i}", subject_id=A, session_id="s",
                            event_type="USER_MESSAGE", meaning=f"шум {i}",
                            created_at=f"2026-01-01T00:0{i}:00+00:00"), provenance="USER_STATED")
        mb.record_event(RuntimeEvent(event_id="e-src", subject_id=A, session_id="s",
                        event_type="USER_MESSAGE", meaning=MARINA,
                        created_at="2026-01-01T00:09:30+00:00"), provenance="USER_STATED")  # seq 10
        cm = ConsolidatedMemoryBackend(mem, A)
        cand = cm.propose(memory_backend=mb, source_event_id="e-src", memory_kind="SEMANTIC")
        cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="op")
        rec = next(r for r in cm.load_active_records(A) if r.source_event_id == "e-src")
        events = list(mb.load_events_causal(A))
        cm.close(); mb.close()
        return events, rec

    def _cons_dict(self, rec):
        return {"record_id": rec.record_id, "source_event_id": rec.source_event_id,
                "basis_event_ids": list(rec.basis_event_ids), "memory_kind": rec.memory_kind,
                "epistemic_kind": rec.epistemic_kind, "provenance": rec.provenance,
                "holder_id": rec.holder_id, "meaning": rec.meaning, "seq": rec.seq,
                "in_conflict": False}

    def test_available_by_source_seq_10_not_approval_seq(self, tmp_path):
        events, rec = self._seed(tmp_path)
        src_seq = next(e.seq for e in events if e.event_id == "e-src")
        assert src_seq == 10 and rec.seq is not None and rec.seq < 10  # approval ledger seq is small

        # at_seq 9  -> source seq 10 not reached -> absent (would be WRONG-present
        # if approval seq were used, since approval seq < 9)
        _, before, _ = _assemble(at_seq=9, events=events,
                                 consolidated_records=[rec], consolidated_dicts=[self._cons_dict(rec)])
        assert MARINA not in before

        # at_seq 20 -> source seq 10 reached -> deliverable
        _, after, _ = _assemble(at_seq=20, events=events,
                                consolidated_records=[rec], consolidated_dicts=[self._cons_dict(rec)])
        assert MARINA in after
        assert f"{_GROUNDED_V2_CONSMEM_LINE_PREFIX}{MARINA}" in after


# --------------------------------------------------------------------------
# Acceptance E -- exact-source prompt de-duplication
# --------------------------------------------------------------------------


class TestAcceptanceE_ExactSourceDedup:
    def test_same_source_delivered_once_consolidated_wins(self, tmp_path):
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, A)
        mb.record_event(RuntimeEvent(event_id="e-src", subject_id=A, session_id="s",
                        event_type="USER_MESSAGE", meaning=MARINA,
                        created_at="2026-01-01T00:00:00+00:00"), provenance="USER_STATED")
        cm = ConsolidatedMemoryBackend(mem, A)
        cand = cm.propose(memory_backend=mb, source_event_id="e-src", memory_kind="SEMANTIC")
        cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="op")
        rec = next(r for r in cm.load_active_records(A) if r.source_event_id == "e-src")
        events = list(mb.load_events_causal(A))
        cm.close(); mb.close()
        cons_dict = {"record_id": rec.record_id, "source_event_id": "e-src",
                     "basis_event_ids": ["e-src"], "memory_kind": rec.memory_kind,
                     "epistemic_kind": rec.epistemic_kind, "provenance": rec.provenance,
                     "holder_id": None, "meaning": MARINA, "seq": rec.seq, "in_conflict": False}
        asm, txt, _ = _assemble(at_seq=50, events=events,
                                consolidated_records=[rec], consolidated_dicts=[cons_dict])
        # the claim appears exactly once across the memory/epistemic delivery
        assert txt.count(MARINA) == 1
        # and it is the consolidated representation that survived
        assert f"{_GROUNDED_V2_CONSMEM_LINE_PREFIX}{MARINA}" in txt
        assert f"{_GROUNDED_V2_MEMORY_LINE_PREFIX}{MARINA}" not in txt
        mem_lines = _kinds(asm, "system.memory_line")
        assert not any(MARINA in i.text for i in mem_lines)
        cons_lines = _kinds(asm, "system.consolidated_memory_line")
        assert sum(MARINA in i.text for i in cons_lines) == 1

    def test_no_fuzzy_or_semantic_dedupe(self):
        # near-identical but NOT exact -> both survive (exact identity only)
        e1 = _evt("e-1", "Марина уехала.", 5)
        e2 = _evt("e-2", "Марина уже уехала.", 6)  # different string
        _, txt, _ = _assemble(at_seq=10, events=[e1, e2])
        assert "Марина уехала." in txt and "Марина уже уехала." in txt


# --------------------------------------------------------------------------
# Acceptance F -- bounds preserved (no historical-log resurrection)
# --------------------------------------------------------------------------


class TestAcceptanceF_Bounds:
    def test_raw_working_bound_preserved_and_no_resurrection(self):
        events = [_evt("e-old", "Старое сообщение.", 1)] + [
            _evt(f"e-{i:02d}", f"Сообщение {i}.", i + 2) for i in range(25)
        ]  # 26 total, seqs 1..27
        at_seq = max(e.seq for e in events) + 1
        asm, txt, snap = _assemble(at_seq=at_seq, events=events)
        raw = [l for l in txt.splitlines() if l.startswith(_GROUNDED_V2_MEMORY_LINE_PREFIX)]
        assert len(raw) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS       # still exactly 20
        assert "Старое сообщение." not in txt                     # oldest 6 not resurrected
        # CANDIDATE INPUT BOUND: only the bounded-raw 20 became epistemic
        # candidates -- the 6 unselected historical events never entered.
        assert len(snap.candidate_envelopes) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS
        assert len(snap.visible_envelopes) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS
        cand_basis = {b for env in snap.candidate_envelopes for b in env.basis_event_ids}
        assert "e-old" not in cand_basis
        assert not any(f"e-{i:02d}" in cand_basis for i in range(5))  # e-00..e-04 excluded
        assert not _kinds(asm, "system.epistemic_context")

    def test_18_segment_absent_when_nothing_additional(self):
        asm, txt, _ = _assemble(at_seq=10, events=[_evt("e-1", "обычное сообщение", 5)])
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert not _kinds(asm, "system.epistemic_context")
        assert not _kinds(asm, "system.epistemic_context_line")


# --------------------------------------------------------------------------
# BOUNDED INPUT CORRECTION -- the epistemic bridge must NOT receive the whole
# historical runtime event log; only bounded raw + consolidated bases.
# --------------------------------------------------------------------------


class TestBoundedBridgeInput:
    E01_MEANING = "первичное уникальное утверждение X7"

    def _seed_26_with_e01_consolidated(self, tmp_path):
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, "kira")
        for i in range(1, 27):  # e-01..e-26, seqs 1..26
            meaning = self.E01_MEANING if i == 1 else f"историческое сообщение {i}"
            mb.record_event(
                RuntimeEvent(event_id=f"e-{i:02d}", subject_id="kira", session_id="s",
                             event_type="USER_MESSAGE", meaning=meaning,
                             created_at=f"2026-01-01T00:{i:02d}:00+00:00"),
                provenance="USER_STATED",
            )
        cm = ConsolidatedMemoryBackend(mem, "kira")
        cand = cm.propose(memory_backend=mb, source_event_id="e-01", memory_kind="SEMANTIC")
        cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="op")
        rec = next(r for r in cm.load_active_records("kira") if r.source_event_id == "e-01")
        prior_events = list(mb.load_events_causal("kira"))
        cm.close(); mb.close()
        return mem, prior_events, rec

    def test_candidate_input_bound_not_only_delivered_bound(self, tmp_path):
        _, prior_events, rec = self._seed_26_with_e01_consolidated(tmp_path)
        by_id = {e.event_id: e for e in prior_events}

        # exactly the inputs RuntimeService.turn now composes
        rc_pre = {
            "subject_id": "kira",
            "causal_memory": [
                {"event_id": e.event_id, "session_id": e.session_id, "event_type": e.event_type,
                 "meaning": e.meaning, "created_at": e.created_at, "seq": e.seq,
                 "provenance": e.provenance}
                for e in prior_events
            ],
        }
        bounded_dicts = GroundedV2Policy().select_memory(rc_pre, "s")
        bounded_ids = [d["event_id"] for d in bounded_dicts]
        assert bounded_ids == [f"e-{i:02d}" for i in range(7, 27)]  # newest 20: e-07..e-26

        bounded_raw = [by_id[i] for i in bounded_ids]
        bridge_events = RuntimeService._select_epistemic_runtime_inputs(
            bounded_raw, (rec,), by_id
        )
        bridge_ids = [e.event_id for e in bridge_events]
        # bounded raw 20 + the ONE consolidated basis (e-01); NOTHING else
        assert bridge_ids == [f"e-{i:02d}" for i in range(7, 27)] + ["e-01"]
        assert not any(f"e-{i:02d}" in bridge_ids for i in range(2, 7))  # e-02..e-06 never admitted

        snap = build_runtime_epistemic_context(
            subject_id="kira", runtime_events=bridge_events, consolidated_records=(rec,),
            explicit_envelopes=(), perceiver_id="kira", at_seq=100,
        )
        cand_basis = {b for env in snap.candidate_envelopes for b in env.basis_event_ids}
        assert cand_basis == {"e-01"} | {f"e-{i:02d}" for i in range(7, 27)}
        assert not any(f"e-{i:02d}" in cand_basis for i in range(2, 7))
        # e-01 is delivered via its consolidated projection, not a raw one
        assert snap.suppressed_exact_source_count == 1

    def test_end_to_end_turn_delivers_bounded_raw_plus_consolidated_source(self, tmp_path):
        mem, _, _ = self._seed_26_with_e01_consolidated(tmp_path)
        txt, manifest = _turn_request(tmp_path, mem_root=mem, policy=GroundedV2Policy(),
                                      turn_id="bounded", at_seq=100)
        raw = [l for l in txt.splitlines() if l.startswith(_GROUNDED_V2_MEMORY_LINE_PREFIX)]
        assert len(raw) == GROUNDED_V2_RAW_MEMORY_MAX_EVENTS       # still exactly 20
        # e-01's claim is delivered once, via consolidated memory
        assert txt.count(self.E01_MEANING) == 1
        assert f"{_GROUNDED_V2_CONSMEM_LINE_PREFIX}{self.E01_MEANING}" in txt
        assert f"{_GROUNDED_V2_MEMORY_LINE_PREFIX}{self.E01_MEANING}" not in txt
        # unrelated bounded-out events (e-02..e-06) deliver no line at all
        lines = txt.splitlines()
        for i in range(2, 7):
            exact = f"{_GROUNDED_V2_MEMORY_LINE_PREFIX}историческое сообщение {i}"
            assert exact not in lines
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])


# --------------------------------------------------------------------------
# service wiring / at_seq / Beta / regression  (accepted kira package)
# --------------------------------------------------------------------------


def _fake_factory(response="[FAKE] ok"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {"id": "f", "model": "fake",
                          "choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
            return response
        return provider
    return factory


def _service():
    return RuntimeService(acceptance_root=_ACCEPTED_ROOT,
                          source_loader=build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT))


def _turn_request(tmp_path, *, mem_root, policy, turn_id, explicit=(), at_seq=None, state_root=None,
                  scene=None):
    cap = TurnCapture(tmp_path / f"cap-{turn_id}")
    _service().turn(
        "kira", policy=policy, history=[], user_message="Что происходит?",
        provider=None, provider_factory=_fake_factory(), memory_root=mem_root,
        state_root=state_root, capture=cap, turn_id=turn_id,
        provider_info={"provider_id": "p", "model": "m"},
        explicit_epistemic_envelopes=explicit, epistemic_at_seq=at_seq,
        scene=scene,
    )
    req = (cap.turn_dir(turn_id) / "request.json").read_text("utf-8")
    data = json.loads(req)
    sys_text = "\n".join(m["content"] for m in data["messages"] if m["role"] == "system")
    return sys_text, cap.read_manifest(turn_id)


class TestServiceWiringAndRegression:
    def test_1_2_grounded_turn_builds_snapshot_with_explicit_at_seq(self, tmp_path):
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, "kira")
        for i in range(3):
            mb.record_event(RuntimeEvent(event_id=f"k-{i}", subject_id="kira", session_id="s",
                            event_type="USER_MESSAGE", meaning=f"реплика {i}",
                            created_at=f"2026-01-01T00:0{i}:00+00:00"), provenance="USER_STATED")
        mb.close()
        # a hidden explicit WORLD_FACT (no perceiver) + a visible one for kira
        hidden = EpistemicEnvelope(meaning="Скрытый факт про мир.", epistemic_kind="WORLD_FACT",
                                   provenance="authored", basis_event_ids=("a-1",), confidence=1.0)
        shown = EpistemicEnvelope(meaning="Открытый факт про мир.", epistemic_kind="WORLD_FACT",
                                  provenance="authored", basis_event_ids=("a-2",), confidence=1.0,
                                  perceiver_ids=("kira",))
        txt, manifest = _turn_request(tmp_path, mem_root=mem, policy=GroundedV2Policy(),
                                      turn_id="wired", explicit=(hidden, shown), at_seq=99)
        assert "Открытый факт про мир." in txt         # 17: visible explicit envelope present
        assert "Скрытый факт про мир." not in txt      # 16: hidden explicit envelope absent
        epi = [i for i in manifest["items"] if i["kind"] == "system.epistemic_context"]
        assert len(epi) == 1
        assert epi[0]["meta"]["at_seq"] == 99          # 2: explicit at_seq threaded through
        assert epi[0]["meta"]["visibility_source"] == "CHARACTER_CORE_SELECTOR"
        assert epi[0]["meta"]["kinds"] == ["WORLD_FACT"]
        lines = [i for i in manifest["items"] if i["kind"] == "system.epistemic_context_line"]
        assert [l["text"] for l in lines] == ["[WORLD_FACT] Открытый факт про мир."]

    def test_production_at_seq_is_max_prior_seq_plus_one(self, tmp_path):
        def fresh(name):
            mem = tmp_path / name
            mb = RuntimeMemoryBackend(mem, "kira")
            for i in range(5):
                mb.record_event(RuntimeEvent(event_id=f"k-{i}", subject_id="kira", session_id="s",
                                event_type="USER_MESSAGE", meaning=f"реплика {i}",
                                created_at=f"2026-01-01T00:0{i}:00+00:00"), provenance="USER_STATED")
            mb.close()
            return mem

        shown = EpistemicEnvelope(meaning="Факт.", epistemic_kind="WORLD_FACT", provenance="authored",
                                  basis_event_ids=("a-1",), confidence=1.0, perceiver_ids=("kira",),
                                  valid_from_seq=6)  # exactly max_prior(5) + 1
        txt, manifest = _turn_request(tmp_path, mem_root=fresh("wsA"), policy=GroundedV2Policy(),
                                      turn_id="autoseq", explicit=(shown,))  # no at_seq override
        epi = [i for i in manifest["items"] if i["kind"] == "system.epistemic_context"]
        assert epi and epi[0]["meta"]["at_seq"] == 6   # derived, not wall-clock/index/approval
        assert "Факт." in txt
        # a fact valid only from seq 7 would NOT be visible at auto at_seq 6
        future = EpistemicEnvelope(meaning="Будущее.", epistemic_kind="WORLD_FACT", provenance="authored",
                                   basis_event_ids=("a-2",), confidence=1.0, perceiver_ids=("kira",),
                                   valid_from_seq=7)
        txt2, _ = _turn_request(tmp_path, mem_root=fresh("wsB"), policy=GroundedV2Policy(),
                                turn_id="autoseq2", explicit=(future,))
        assert "Будущее." not in txt2

    def test_19_beta_v1_has_no_epistemic_segment(self, tmp_path):
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, "kira")
        mb.record_event(RuntimeEvent(event_id="k-0", subject_id="kira", session_id="s",
                        event_type="USER_MESSAGE", meaning="реплика",
                        created_at="2026-01-01T00:00:00+00:00"), provenance="USER_STATED")
        mb.close()
        shown = EpistemicEnvelope(meaning="Факт для беты.", epistemic_kind="WORLD_FACT",
                                  provenance="authored", basis_event_ids=("a-1",), confidence=1.0,
                                  perceiver_ids=("kira",))
        txt, manifest = _turn_request(tmp_path, mem_root=mem, policy=BetaV1CurrentPolicy(),
                                      turn_id="beta", explicit=(shown,), at_seq=99)
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert "Факт для беты." not in txt
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])

    def test_21_existing_runtime_state_and_grounding_unchanged(self, tmp_path):
        # a plain grounded turn with no explicit envelopes and auto at_seq must
        # still carry package grounding and behave normally.
        mem = tmp_path / "ws"
        mb = RuntimeMemoryBackend(mem, "kira")
        mb.record_event(RuntimeEvent(event_id="k-0", subject_id="kira", session_id="s",
                        event_type="USER_MESSAGE", meaning="реплика",
                        created_at="2026-01-01T00:00:00+00:00"), provenance="USER_STATED")
        mb.close()
        txt, manifest = _turn_request(tmp_path, mem_root=mem, policy=GroundedV2Policy(), turn_id="plain")
        assert "ACCEPTED CHARACTER GROUNDING" in txt
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])


# --------------------------------------------------------------------------
# SCENE EPISTEMIC CLAIMS V1 -- author-defined scene claims through Grounded v2
# --------------------------------------------------------------------------


def _scene_claim(claim_id, meaning, *, perceivers=("kira",), valid_from=None, valid_to=None):
    return SceneEpistemicClaim(
        claim_id=claim_id, meaning=meaning, epistemic_kind="WORLD_FACT",
        provenance="scene_authored", perceiver_ids=perceivers,
        valid_from_seq=valid_from, valid_to_seq=valid_to, confidence=1.0,
    )


def _claimed_scene(claims):
    base = new_scene(
        title="Терраса", location="крыша", participants=["Кира"],
        prior_events=["Все поднялись наверх."], current_situation="Ночь, тихо.",
        scene_id="sc-t", created_at="2026-01-01T00:00:00+00:00",
    )
    return with_epistemic_claims(base, claims)


class TestSceneClaimsGroundedIntegration:
    SCENE_FACT = "За дверью террасы включён свет."

    def test_11_visible_scene_claim_appears_in_epistemic_segment(self, tmp_path):
        scene = _claimed_scene([_scene_claim("sc-claim-1", self.SCENE_FACT, valid_from=1)])
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=GroundedV2Policy(), turn_id="sc-vis",
                                      scene=scene, at_seq=99)
        assert _GROUNDED_V2_EPI_HEADER in txt
        assert f"[WORLD_FACT] {self.SCENE_FACT}" in txt
        lines = [i for i in manifest["items"] if i["kind"] == "system.epistemic_context_line"]
        assert [l["text"] for l in lines] == [f"[WORLD_FACT] {self.SCENE_FACT}"]
        assert lines[0]["meta"]["basis_event_ids"] == ["sc-claim-1"]
        assert lines[0]["meta"]["provenance"] == "scene_authored"
        assert lines[0]["meta"]["valid_from_seq"] == 1

    def test_12_hidden_claim_wrong_perceiver_absent(self, tmp_path):
        scene = _claimed_scene([
            _scene_claim("sc-claim-1", self.SCENE_FACT, perceivers=("someone-else",)),
        ])
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=GroundedV2Policy(), turn_id="sc-hid",
                                      scene=scene, at_seq=99)
        assert self.SCENE_FACT not in txt
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])

    def test_13_future_valid_from_absent(self, tmp_path):
        scene = _claimed_scene([_scene_claim("sc-claim-1", self.SCENE_FACT, valid_from=50)])
        txt, _ = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                               policy=GroundedV2Policy(), turn_id="sc-fut",
                               scene=scene, at_seq=10)
        assert self.SCENE_FACT not in txt

    def test_14_inclusive_boundary_at_valid_from(self, tmp_path):
        scene = _claimed_scene([_scene_claim("sc-claim-1", self.SCENE_FACT, valid_from=10)])
        txt, _ = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                               policy=GroundedV2Policy(), turn_id="sc-bnd",
                               scene=scene, at_seq=10)
        assert f"[WORLD_FACT] {self.SCENE_FACT}" in txt

    def test_15_expired_valid_to_absent_after_cutoff(self, tmp_path):
        scene = _claimed_scene([
            _scene_claim("sc-claim-1", self.SCENE_FACT, valid_from=1, valid_to=5),
        ])
        txt_at, _ = _turn_request(tmp_path, mem_root=tmp_path / "wsA",
                                  policy=GroundedV2Policy(), turn_id="sc-exp5",
                                  scene=scene, at_seq=5)
        assert self.SCENE_FACT in txt_at                    # inclusive upper boundary
        txt_after, _ = _turn_request(tmp_path, mem_root=tmp_path / "wsB",
                                     policy=GroundedV2Policy(), turn_id="sc-exp9",
                                     scene=scene, at_seq=9)
        assert self.SCENE_FACT not in txt_after             # expired

    def test_16_contradictory_visible_claims_both_appear(self, tmp_path):
        scene = _claimed_scene([
            _scene_claim("sc-lock", "Дверь заперта."),
            _scene_claim("sc-open", "Дверь открыта."),
        ])
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=GroundedV2Policy(), turn_id="sc-contra",
                                      scene=scene, at_seq=99)
        assert "[WORLD_FACT] Дверь заперта." in txt
        assert "[WORLD_FACT] Дверь открыта." in txt         # both, unreconciled
        lines = [i["text"] for i in manifest["items"] if i["kind"] == "system.epistemic_context_line"]
        assert lines == ["[WORLD_FACT] Дверь заперта.", "[WORLD_FACT] Дверь открыта."]

    def test_17_free_form_scene_block_present_and_unchanged(self, tmp_path):
        scene = _claimed_scene([_scene_claim("sc-claim-1", self.SCENE_FACT)])
        plain = new_scene(
            title="Терраса", location="крыша", participants=["Кира"],
            prior_events=["Все поднялись наверх."], current_situation="Ночь, тихо.",
            scene_id="sc-t", created_at="2026-01-01T00:00:00+00:00",
        )
        # the claim layer does not alter the free-form block at all
        assert render_scene_block(scene) == render_scene_block(plain)
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=GroundedV2Policy(), turn_id="sc-ff",
                                      scene=scene, at_seq=99)
        assert render_scene_block(plain) in txt             # block delivered verbatim
        scene_items = [i for i in manifest["items"] if i["kind"] == "system.scene"]
        assert len(scene_items) == 1
        assert scene_items[0]["text"] == render_scene_block(plain)
        # free-form scene text does NOT leak into the epistemic segment
        lines = [i["text"] for i in manifest["items"] if i["kind"] == "system.epistemic_context_line"]
        assert lines == [f"[WORLD_FACT] {self.SCENE_FACT}"]

    def test_18_beta_v1_unchanged_even_with_scene_claims(self, tmp_path):
        scene = _claimed_scene([_scene_claim("sc-claim-1", self.SCENE_FACT)])
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=BetaV1CurrentPolicy(), turn_id="sc-beta",
                                      scene=scene, at_seq=99)
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert self.SCENE_FACT not in txt                   # claims never surface in Beta v1
        assert render_scene_block(scene) in txt             # free-form scene still delivered
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])

    def test_19_scene_without_claims_preserves_prior_behavior(self, tmp_path):
        plain = new_scene(
            title="Терраса", location="крыша", participants=["Кира"],
            prior_events=[], current_situation="Ночь, тихо.",
            scene_id="sc-t", created_at="2026-01-01T00:00:00+00:00",
        )
        txt, manifest = _turn_request(tmp_path, mem_root=tmp_path / "ws",
                                      policy=GroundedV2Policy(), turn_id="sc-none",
                                      scene=plain, at_seq=99)
        assert _GROUNDED_V2_EPI_HEADER not in txt
        assert render_scene_block(plain) in txt
        assert not any(i["kind"].startswith("system.epistemic_context") for i in manifest["items"])


# --------------------------------------------------------------------------
# 20 + 24 -- no reimplemented visibility / no character-specific branching
# --------------------------------------------------------------------------


def test_20_integration_delegates_visibility_to_core():
    # the service builds the snapshot via the bridge (which calls the Core
    # selector); the policy only consumes snapshot.visible_envelopes.
    assert "build_runtime_epistemic_context" in _SERVICE_SRC.read_text(encoding="utf-8")
    pol = _POLICY_SRC.read_text(encoding="utf-8")
    assert "visible_envelopes" in pol and "epistemic_snapshot" in pol
    # the epistemic integration region must not re-derive visibility itself
    region = pol.split("point-in-time epistemics", 1)[1].split("policy registry", 1)[0]
    for forbidden in ("at_seq <", "at_seq >", "< valid_from", "> valid_to",
                      "valid_from_seq <", "valid_to_seq >", ".temporal_state(",
                      "assess_epistemic_visibility", "select_visible_epistemic_context"):
        assert forbidden not in region, forbidden


def test_24_no_character_specific_epistemic_branching():
    for src_path in (_POLICY_SRC, _SERVICE_SRC):
        low = src_path.read_text(encoding="utf-8").lower()
        for name in ("marina", "andrey", "nika", "sergey"):
            assert name not in low, name
    pol = _POLICY_SRC.read_text(encoding="utf-8")
    region = pol.split("point-in-time epistemics", 1)[1].split("policy registry", 1)[0]
    assert '== "kira"' not in region and 'subject_id ==' not in region
    assert 'perceiver_id ==' not in region and 'holder_id ==' not in region
