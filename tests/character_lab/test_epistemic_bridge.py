#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime -> Core epistemic bridge (projection + Core-delegated visibility).

Uses the REAL runtime memory / consolidated memory domain objects (no parallel
fakes). Synthetic character identities ("character-a" / "character-b") so the
production bridge stays obviously generic. Offline, no provider.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.character_core.epistemics import EpistemicEnvelope, EpistemicKind
from services.character_lab.epistemic_bridge import (
    EpistemicBridgeError,
    EpistemicContextSnapshot,
    build_runtime_epistemic_context,
    project_consolidated_user_report,
    project_runtime_user_report,
)
from services.character_runtime import RuntimeEvent, RuntimeMemoryBackend
from services.character_runtime.consolidated_memory import (
    DECISION_APPROVE,
    DECISION_REJECT,
    RECORD_STATUS_SUPERSEDED,
    RELATION_SUPERSEDES,
    ConsolidatedMemoryBackend,
)

SUBJ = "character-a"
OTHER = "character-b"
_BRIDGE_SRC = Path(__file__).resolve().parents[2] / "services" / "character_lab" / "epistemic_bridge.py"


def _mem(root, subject=SUBJ):
    return RuntimeMemoryBackend(root, subject)


def _add(mb, eid, etype, meaning, prov, subject=SUBJ, session="s1", ts="2026-01-01T00:00:00+00:00"):
    mb.record_event(
        RuntimeEvent(event_id=eid, subject_id=subject, session_id=session,
                     event_type=etype, meaning=meaning, created_at=ts),
        provenance=prov,
    )


@pytest.fixture()
def rt(tmp_path):
    """Real runtime history: 1 user report + 25 later neutral user events + 1
    character message. Returns (memory_backend, root, events_by_id)."""
    root = tmp_path / "ws"
    mb = _mem(root)
    _add(mb, "evt-src", "USER_MESSAGE", "Марина уехала.", "USER_STATED", ts="2026-01-01T00:00:00+00:00")
    for i in range(25):
        _add(mb, f"evt-f{i:02d}", "USER_MESSAGE", f"Нейтральное сообщение {i}.", "USER_STATED",
             ts=f"2026-01-02T00:{i:02d}:00+00:00")
    _add(mb, "evt-char", "CHARACTER_MESSAGE", "Марина всё ещё дома.", "CHARACTER_UTTERANCE",
         ts="2026-01-03T00:00:00+00:00")
    events = mb.load_events_causal(SUBJ)
    yield mb, root, {e.event_id: e for e in events}
    mb.close()


def _events(rt):
    mb, root, _ = rt
    return list(mb.load_events_causal(SUBJ))


# ---------------------------------------------------------- runtime projection


def test_1_2_3_4_user_stated_event_projects_to_user_report(rt):
    _, _, by_id = rt
    src = by_id["evt-src"]
    env = project_runtime_user_report(src, subject_id=SUBJ)
    assert env is not None
    assert env.epistemic_kind is EpistemicKind.USER_REPORT          # 1
    assert env.meaning == "Марина уехала."                          # 2 verbatim
    assert env.basis_event_ids == ("evt-src",)                      # 3
    assert env.valid_from_seq == src.seq and env.valid_to_seq is None  # 4
    assert env.provenance == "USER_STATED"
    assert env.perceiver_ids == (SUBJ,)
    assert env.confidence == 1.0  # receipt confidence, not truth


def test_8_character_message_is_not_projected_as_belief(rt):
    _, _, by_id = rt
    assert project_runtime_user_report(by_id["evt-char"], subject_id=SUBJ) is None
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=_events(rt), consolidated_records=[],
        perceiver_id=SUBJ, at_seq=10_000,
    )
    metas = {(e.epistemic_kind, e.meaning) for e in snap.candidate_envelopes}
    assert (EpistemicKind.CHARACTER_BELIEF, "Марина всё ещё дома.") not in metas
    assert (EpistemicKind.CHARACTER_INTERPRETATION, "Марина всё ещё дома.") not in metas
    assert not any(e.meaning == "Марина всё ещё дома." for e in snap.candidate_envelopes)


def test_non_user_stated_and_unsequenced_events_skip(tmp_path):
    root = tmp_path / "w"
    mb = _mem(root)
    _add(mb, "e-legacy", "USER_MESSAGE", "старое", None)  # provenance None
    events = mb.load_events_causal(SUBJ)
    assert project_runtime_user_report(events[0], subject_id=SUBJ) is None
    mb.close()
    # unsequenced RuntimeEvent (seq=None) also skips
    bare = RuntimeEvent(event_id="e-x", subject_id=SUBJ, session_id="s",
                        event_type="USER_MESSAGE", meaning="hi",
                        created_at="2026-01-01T00:00:00+00:00")
    assert bare.seq is None
    assert project_runtime_user_report(bare, subject_id=SUBJ) is None


# ------------------------------------------ visibility is delegated to Core


def test_5_6_7_perceiver_and_pit_delegated_to_core(rt):
    _, _, by_id = rt
    src = by_id["evt-src"]
    events = _events(rt)
    # correct perceiver at the boundary seq -> visible
    at_boundary = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=events, consolidated_records=[],
        perceiver_id=SUBJ, at_seq=src.seq,
    )
    assert any(e.meaning == "Марина уехала." for e in at_boundary.visible_envelopes)  # 5
    # same perceiver one seq earlier -> not visible
    before = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=events, consolidated_records=[],
        perceiver_id=SUBJ, at_seq=src.seq - 1,
    )
    assert not any(e.meaning == "Марина уехала." for e in before.visible_envelopes)  # 6
    # another character, never a listed perceiver -> not visible
    other = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=events, consolidated_records=[],
        perceiver_id=OTHER, at_seq=10_000,
    )
    assert other.visible_envelopes == ()  # 7


# --------------------------------------------- consolidated projection


def _approve(cm, mb, event_id):
    cand = cm.propose(memory_backend=mb, source_event_id=event_id, memory_kind="SEMANTIC")
    dec = cm.decide(candidate_id=cand.candidate_id, decision=DECISION_APPROVE, decided_by="op")
    return dec.record_id


def test_9_10_active_consolidated_user_report_projects_from_source_seq(rt):
    mb, root, by_id = rt
    src = by_id["evt-src"]
    assert src.seq == 1  # oldest runtime event
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        # approve two OTHER records first so the evt-src record's approval-
        # ledger seq (>= 3) is clearly distinct from the source event seq (1).
        _approve(cm, mb, "evt-f00")
        _approve(cm, mb, "evt-f01")
        rid = _approve(cm, mb, "evt-src")
        record = next(r for r in cm.load_active_records(SUBJ) if r.record_id == rid)
    finally:
        cm.close()
    assert record.seq is not None and record.seq >= 3 and record.seq != src.seq
    env = project_consolidated_user_report(
        record, subject_id=SUBJ, runtime_events_by_id=by_id
    )
    assert env is not None
    assert env.epistemic_kind is EpistemicKind.USER_REPORT           # 9
    assert env.meaning == "Марина уехала." and env.basis_event_ids == ("evt-src",)
    assert env.valid_from_seq == src.seq == 1                         # 10: source seq
    assert env.valid_from_seq != record.seq                           # 10: NOT approval seq


def test_11_missing_consolidated_basis_event_fails_closed(rt):
    mb, root, by_id = rt
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        rid = _approve(cm, mb, "evt-src")
        record = next(r for r in cm.load_active_records(SUBJ) if r.record_id == rid)
    finally:
        cm.close()
    # runtime history WITHOUT the source event
    with pytest.raises(EpistemicBridgeError) as ei:
        project_consolidated_user_report(record, subject_id=SUBJ, runtime_events_by_id={})
    assert ei.value.code == "missing_basis_event"
    with pytest.raises(EpistemicBridgeError) as ei2:
        build_runtime_epistemic_context(
            subject_id=SUBJ, runtime_events=[], consolidated_records=[record],
            perceiver_id=SUBJ, at_seq=10_000,
        )
    assert ei2.value.code == "missing_basis_event"


def test_12_13_pending_or_rejected_candidate_not_accepted(rt):
    mb, root, _ = rt
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        pending = cm.propose(memory_backend=mb, source_event_id="evt-src", memory_kind="SEMANTIC")
        rej_cand = cm.propose(memory_backend=mb, source_event_id="evt-f00", memory_kind="SEMANTIC")
        cm.decide(candidate_id=rej_cand.candidate_id, decision=DECISION_REJECT, decided_by="op")
        rejected = next(c for c in cm.load_candidates(SUBJ) if c.candidate_id == rej_cand.candidate_id)
    finally:
        cm.close()
    for cand in (pending, rejected):
        with pytest.raises(EpistemicBridgeError) as ei:
            build_runtime_epistemic_context(
                subject_id=SUBJ, runtime_events=_events(rt), consolidated_records=[cand],
                perceiver_id=SUBJ, at_seq=10_000,
            )
        assert ei.value.code == "unsupported_consolidated_input"


def test_14_superseded_record_excluded_from_active_context(rt):
    mb, root, by_id = rt
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        old_id = _approve(cm, mb, "evt-src")
        new_id = _approve(cm, mb, "evt-f00")
        cm.declare_relation(from_record_id=new_id, to_record_id=old_id, kind=RELATION_SUPERSEDES)
        all_recs = cm.load_all_records(SUBJ)
    finally:
        cm.close()
    old = next(r for r in all_recs if r.record_id == old_id)
    assert old.status == RECORD_STATUS_SUPERSEDED
    assert project_consolidated_user_report(old, subject_id=SUBJ, runtime_events_by_id=by_id) is None
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=_events(rt), consolidated_records=list(all_recs),
        perceiver_id=SUBJ, at_seq=10_000,
    )
    # the superseded "Марина уехала." is not a consolidated candidate; the
    # still-active "Нейтральное сообщение 0." record is.
    cons_meanings = [e.meaning for e in snap.candidate_envelopes
                     if e.basis_event_ids in (("evt-src",), ("evt-f00",))]
    assert "Нейтральное сообщение 0." in " ".join(cons_meanings)
    assert snap.projected_consolidated_count == 1


# ------------------------------------------ exact-source suppression


def test_15_raw_and_consolidated_same_source_yield_one_envelope(rt):
    mb, root, by_id = rt
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        rid = _approve(cm, mb, "evt-src")
        record = next(r for r in cm.load_active_records(SUBJ) if r.record_id == rid)
    finally:
        cm.close()
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=_events(rt), consolidated_records=[record],
        perceiver_id=SUBJ, at_seq=10_000,
    )
    from_src = [e for e in snap.candidate_envelopes if e.basis_event_ids == ("evt-src",)]
    assert len(from_src) == 1                       # exactly one, not two
    assert snap.suppressed_exact_source_count == 1  # the raw projection was dropped
    # consolidated projections come before runtime projections -> the survivor
    # occupies the first (consolidated) slot; the raw fillers follow.
    assert snap.candidate_envelopes[0].basis_event_ids == ("evt-src",)
    assert snap.projected_consolidated_count == 1
    # 25 fillers remain (source suppressed), character message never projects
    assert snap.projected_runtime_count == 25


# ------------------------------------------ explicit envelopes + contradictions


def _world(meaning, perceivers=()):
    return EpistemicEnvelope(
        meaning=meaning, epistemic_kind="WORLD_FACT", provenance="authored",
        basis_event_ids=("authored-1",), confidence=1.0, perceiver_ids=perceivers,
    )


def test_16_contradictory_envelopes_both_survive():
    world = EpistemicEnvelope(
        meaning="Марина уехала.", epistemic_kind="WORLD_FACT", provenance="authored",
        basis_event_ids=("authored-w",), confidence=1.0, perceiver_ids=(SUBJ,),
    )
    belief = EpistemicEnvelope(
        meaning="Марина всё ещё дома.", epistemic_kind="CHARACTER_BELIEF",
        provenance="authored", basis_event_ids=("authored-b",), confidence=0.6,
        holder_id=SUBJ,
    )
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=[], consolidated_records=[],
        explicit_envelopes=[world, belief], perceiver_id=SUBJ, at_seq=100,
    )
    assert snap.candidate_envelopes == (world, belief)  # unchanged, both kept
    assert set(e.meaning for e in snap.visible_envelopes) == {
        "Марина уехала.", "Марина всё ещё дома."
    }
    assert snap.suppressed_exact_source_count == 0


def test_17_world_fact_without_perceiver_invisible():
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=[], consolidated_records=[],
        explicit_envelopes=[_world("Марина действительно уехала.", perceivers=())],
        perceiver_id=SUBJ, at_seq=100,
    )
    assert len(snap.candidate_envelopes) == 1
    assert snap.visible_envelopes == ()


def test_18_world_fact_explicitly_perceived_visible():
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=[], consolidated_records=[],
        explicit_envelopes=[_world("Марина действительно уехала.", perceivers=(SUBJ,))],
        perceiver_id=SUBJ, at_seq=100,
    )
    assert len(snap.visible_envelopes) == 1


def test_19_character_belief_visible_to_holder_via_core():
    belief = EpistemicEnvelope(
        meaning="Марина всё ещё дома.", epistemic_kind="CHARACTER_BELIEF",
        provenance="authored", basis_event_ids=("authored-b",), confidence=0.7,
        holder_id=SUBJ,
    )
    snap = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=[], consolidated_records=[],
        explicit_envelopes=[belief], perceiver_id=SUBJ, at_seq=100,
    )
    assert snap.visible_envelopes == (belief,)
    # and NOT visible to a different perceiver
    snap2 = build_runtime_epistemic_context(
        subject_id=SUBJ, runtime_events=[], consolidated_records=[],
        explicit_envelopes=[belief], perceiver_id=OTHER, at_seq=100,
    )
    assert snap2.visible_envelopes == ()


def test_23_freeform_text_is_not_auto_mapped_to_world_fact():
    with pytest.raises(EpistemicBridgeError) as ei:
        build_runtime_epistemic_context(
            subject_id=SUBJ, runtime_events=[], consolidated_records=[],
            explicit_envelopes=["The door is locked."],  # plain scene-like text
            perceiver_id=SUBJ, at_seq=1,
        )
    assert ei.value.code == "unsupported_explicit_input"
    src = _BRIDGE_SRC.read_text(encoding="utf-8")
    assert "EpistemicKind.WORLD_FACT" not in src           # bridge never builds one
    assert "import" in src and ".scene" not in src         # no scene import


# ------------------------------------------ isolation + determinism


def test_21_subject_mismatch_fails_closed(rt):
    events = _events(rt)  # subject "character-a"
    with pytest.raises(EpistemicBridgeError) as ei:
        build_runtime_epistemic_context(
            subject_id=OTHER, runtime_events=events, consolidated_records=[],
            perceiver_id=OTHER, at_seq=10,
        )
    assert ei.value.code == "subject_mismatch"

    mb, root, by_id = rt
    cm = ConsolidatedMemoryBackend(root, SUBJ)
    try:
        rid = _approve(cm, mb, "evt-src")
        record = next(r for r in cm.load_active_records(SUBJ) if r.record_id == rid)
    finally:
        cm.close()
    with pytest.raises(EpistemicBridgeError) as ei2:
        project_consolidated_user_report(record, subject_id=OTHER, runtime_events_by_id=by_id)
    assert ei2.value.code == "subject_mismatch"


def test_22_deterministic_order_and_output(rt):
    world = _world("явный факт", perceivers=(SUBJ,))
    events = _events(rt)
    kw = dict(subject_id=SUBJ, runtime_events=events, consolidated_records=[],
              explicit_envelopes=[world], perceiver_id=SUBJ, at_seq=10_000)
    a = build_runtime_epistemic_context(**kw)
    b = build_runtime_epistemic_context(**kw)
    assert a == b                                   # fully deterministic
    assert isinstance(a, EpistemicContextSnapshot)
    # order: explicit first, then (no consolidated), then runtime projections
    assert a.candidate_envelopes[0] is world
    assert a.candidate_envelopes[1].epistemic_kind is EpistemicKind.USER_REPORT
    assert a.explicit_count == 1 and a.projected_runtime_count == 26  # src + 25 fillers


def test_20_and_24_bridge_delegates_visibility_and_has_no_character_rules():
    src = _BRIDGE_SRC.read_text(encoding="utf-8")
    low = src.lower()
    # delegates to Core -- does not reimplement the comparisons
    assert "select_visible_epistemic_context" in src
    for forbidden in ("at_seq <", "at_seq >", "< valid_from", "> valid_to",
                      "valid_from_seq <", "valid_to_seq >", "holder_id ==",
                      "perceiver_id in "):
        assert forbidden not in src, forbidden
    # no character-specific identity anywhere in production code
    for name in ("kira", "andrey", "nika", "marina", "sergey", "deepseek"):
        assert name not in low, name
