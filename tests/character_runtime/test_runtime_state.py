#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime State backend -- append-only ledger + deterministic current-state.

Focused R3 proofs: no destructive writes, monotonic causal seq, reopen
durability, SET supersedes by seq, REMOVE hides without deleting history.
"""

from __future__ import annotations

import pytest

from services.character_runtime.state import (
    ACTION_REMOVE,
    ACTION_SET,
    DOMAIN_FACT,
    DOMAIN_PSYCHOLOGY,
    DOMAIN_RELATIONSHIP,
    SOURCE_OPERATOR_CONFIRMED,
    RuntimeStateBackend,
    RuntimeStateError,
)


def _open(tmp_path):
    return RuntimeStateBackend(tmp_path / "ws", "kira")


def _current(backend, domain, key):
    for e in backend.load_current_state("kira"):
        if e.domain == domain and e.key == key:
            return e.value
    return None


class TestNumericDomains:
    def test_fact_behavior_unchanged(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="living.city", value="Prague")   # arbitrary text ok
            b.record_set(key="mood note", value="слегка устал")  # spaces ok for FACT
            assert _current(b, DOMAIN_FACT, "living.city") == "Prague"
        finally:
            b.close()

    def test_relationship_and_psychology_accepted(self, tmp_path):
        b = _open(tmp_path)
        try:
            r = b.record_set(key="andrey.trust", value="20", domain=DOMAIN_RELATIONSHIP)
            p = b.record_set(key="stress", value="40", domain=DOMAIN_PSYCHOLOGY)
            assert r.domain == DOMAIN_RELATIONSHIP and r.value == "20"
            assert p.domain == DOMAIN_PSYCHOLOGY and p.value == "40"
        finally:
            b.close()

    def test_unsupported_domain_rejected(self, tmp_path):
        b = _open(tmp_path)
        try:
            with pytest.raises(RuntimeStateError):
                b.record_set(key="x", value="1", domain="MOOD")
        finally:
            b.close()

    def test_numeric_set_accepts_boundaries(self, tmp_path):
        b = _open(tmp_path)
        try:
            for v in ("-100", "0", "100"):
                b.record_set(key=f"a.d{v.strip('-')}", value=v, domain=DOMAIN_RELATIONSHIP)
            b.record_set(key="p_min", value="-100", domain=DOMAIN_PSYCHOLOGY)
            b.record_set(key="p_max", value="100", domain=DOMAIN_PSYCHOLOGY)
        finally:
            b.close()

    def test_numeric_set_rejects_out_of_range(self, tmp_path):
        b = _open(tmp_path)
        try:
            with pytest.raises(RuntimeStateError):
                b.record_set(key="a.b", value="101", domain=DOMAIN_RELATIONSHIP)
            with pytest.raises(RuntimeStateError):
                b.record_set(key="a.b", value="-101", domain=DOMAIN_RELATIONSHIP)
            assert b.load_current_state("kira") == ()
        finally:
            b.close()

    def test_non_integer_numeric_value_rejected(self, tmp_path):
        b = _open(tmp_path)
        try:
            for bad in ("60%", "high", "very close", "1.5", "  ", "+"):
                with pytest.raises(RuntimeStateError):
                    b.record_set(key="a.b", value=bad, domain=DOMAIN_RELATIONSHIP)
        finally:
            b.close()

    def test_relationship_key_format_validated(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="andrey.trust", value="10", domain=DOMAIN_RELATIONSHIP)
            for bad in ("andrey", "Andrey.Trust", "andrey.trust.extra", "andrey trust", "andrey."):
                with pytest.raises(RuntimeStateError):
                    b.record_set(key=bad, value="10", domain=DOMAIN_RELATIONSHIP)
        finally:
            b.close()

    def test_psychology_key_format_validated(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="self_control", value="10", domain=DOMAIN_PSYCHOLOGY)
            for bad in ("self.control", "Self_Control", "self control", "stress!"):
                with pytest.raises(RuntimeStateError):
                    b.record_set(key=bad, value="10", domain=DOMAIN_PSYCHOLOGY)
        finally:
            b.close()


class TestTransitions:
    def test_initialize_then_adjust_appends_new_set(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="andrey.trust", value="20", domain=DOMAIN_RELATIONSHIP)
            ev = b.record_adjust(key="andrey.trust", delta=10, domain=DOMAIN_RELATIONSHIP)
            assert ev.action == ACTION_SET and ev.value == "30"
            hist = b.load_events("kira")
            assert [h.value for h in hist] == ["20", "30"]   # old event kept
            assert _current(b, DOMAIN_RELATIONSHIP, "andrey.trust") == "30"
        finally:
            b.close()

    def test_initialize_psychology_and_adjust(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="stress", value="50", domain=DOMAIN_PSYCHOLOGY)
            b.record_adjust(key="stress", delta=-15, domain=DOMAIN_PSYCHOLOGY)
            assert _current(b, DOMAIN_PSYCHOLOGY, "stress") == "35"
        finally:
            b.close()

    def test_out_of_range_delta_rejected_state_unchanged(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="andrey.trust", value="90", domain=DOMAIN_RELATIONSHIP)
            with pytest.raises(RuntimeStateError):
                b.record_adjust(key="andrey.trust", delta=20, domain=DOMAIN_RELATIONSHIP)
            assert _current(b, DOMAIN_RELATIONSHIP, "andrey.trust") == "90"
            assert len(b.load_events("kira")) == 1
        finally:
            b.close()

    def test_delta_on_uninitialized_key_rejected(self, tmp_path):
        b = _open(tmp_path)
        try:
            with pytest.raises(RuntimeStateError):
                b.record_adjust(key="sergey.tension", delta=5, domain=DOMAIN_RELATIONSHIP)
            assert b.load_events("kira") == ()
        finally:
            b.close()

    def test_non_integer_delta_rejected(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="stress", value="10", domain=DOMAIN_PSYCHOLOGY)
            for bad in ("1.5", "up", "+", None):
                with pytest.raises(RuntimeStateError):
                    b.record_adjust(key="stress", delta=bad, domain=DOMAIN_PSYCHOLOGY)
        finally:
            b.close()

    def test_adjust_rejected_for_fact_domain(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="living.city", value="Prague")
            with pytest.raises(RuntimeStateError):
                b.record_adjust(key="living.city", delta=1, domain=DOMAIN_FACT)
        finally:
            b.close()

    def test_remove_makes_numeric_unknown_then_adjust_rejected(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="andrey.trust", value="30", domain=DOMAIN_RELATIONSHIP)
            b.record_remove(key="andrey.trust", domain=DOMAIN_RELATIONSHIP)
            assert _current(b, DOMAIN_RELATIONSHIP, "andrey.trust") is None
            assert b.current_numeric(DOMAIN_RELATIONSHIP, "andrey.trust") is None
            with pytest.raises(RuntimeStateError):
                b.record_adjust(key="andrey.trust", delta=5, domain=DOMAIN_RELATIONSHIP)
            # history still proves the earlier life of the key
            assert [h.action for h in b.load_events("kira")] == [ACTION_SET, ACTION_REMOVE]
            # re-initialize and adjust again
            b.record_set(key="andrey.trust", value="0", domain=DOMAIN_RELATIONSHIP)
            b.record_adjust(key="andrey.trust", delta=5, domain=DOMAIN_RELATIONSHIP)
            assert _current(b, DOMAIN_RELATIONSHIP, "andrey.trust") == "5"
        finally:
            b.close()

    def test_reopen_preserves_numeric_evolution(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="andrey.trust", value="20", domain=DOMAIN_RELATIONSHIP)
            b.record_adjust(key="andrey.trust", delta=10, domain=DOMAIN_RELATIONSHIP)
        finally:
            b.close()
        b2 = RuntimeStateBackend(tmp_path / "ws", "kira")
        try:
            assert _current(b2, DOMAIN_RELATIONSHIP, "andrey.trust") == "30"
            assert len(b2.load_events("kira")) == 2
        finally:
            b2.close()


class TestBackend:
    def test_new_db_initializes_empty(self, tmp_path):
        b = _open(tmp_path)
        try:
            assert b.load_events("kira") == ()
            assert b.load_current_state("kira") == ()
            assert b.db_path.name == "runtime_state.sqlite3"
        finally:
            b.close()

    def test_set_creates_current_fact(self, tmp_path):
        b = _open(tmp_path)
        try:
            ev = b.record_set(key="living.city", value="Prague")
            assert ev.action == ACTION_SET
            assert ev.domain == DOMAIN_FACT
            assert ev.source_kind == SOURCE_OPERATOR_CONFIRMED
            cur = b.load_current_state("kira")
            assert len(cur) == 1
            assert (cur[0].key, cur[0].value) == ("living.city", "Prague")
        finally:
            b.close()

    def test_second_set_supersedes_by_seq_without_deleting_history(self, tmp_path):
        b = _open(tmp_path)
        try:
            e1 = b.record_set(key="living.city", value="Prague")
            e2 = b.record_set(key="living.city", value="Berlin")
            cur = b.load_current_state("kira")
            assert len(cur) == 1
            assert cur[0].value == "Berlin"
            assert cur[0].seq == e2.seq
            hist = b.load_events("kira")
            assert [h.value for h in hist] == ["Prague", "Berlin"]
            assert e1.seq < e2.seq
        finally:
            b.close()

    def test_remove_makes_fact_absent_history_intact(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="employment.status", value="searching")
            rem = b.record_remove(key="employment.status")
            assert rem.action == ACTION_REMOVE
            assert rem.value is None
            assert b.load_current_state("kira") == ()
            hist = b.load_events("kira")
            assert [h.action for h in hist] == [ACTION_SET, ACTION_REMOVE]
            assert hist[0].value == "searching"  # SET row untouched
        finally:
            b.close()

    def test_set_after_remove_reestablishes(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="k", value="v1")
            b.record_remove(key="k")
            b.record_set(key="k", value="v2")
            cur = b.load_current_state("kira")
            assert len(cur) == 1 and cur[0].value == "v2"
            assert len(b.load_events("kira")) == 3
        finally:
            b.close()

    def test_seq_is_monotonic(self, tmp_path):
        b = _open(tmp_path)
        try:
            for i in range(6):
                b.record_set(key=f"k{i}", value=str(i))
            seqs = [e.seq for e in b.load_events("kira")]
            assert seqs == sorted(seqs)
            assert len(set(seqs)) == len(seqs)
            assert all(isinstance(s, int) for s in seqs)
        finally:
            b.close()

    def test_reopen_preserves_state_and_history(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="current.project", value="alpha")
            b.record_set(key="current.project", value="beta")
            b.record_remove(key="gone")
        finally:
            b.close()
        b2 = RuntimeStateBackend(tmp_path / "ws", "kira")
        try:
            cur = b2.load_current_state("kira")
            assert len(cur) == 1 and cur[0].value == "beta"
            assert len(b2.load_events("kira")) == 3
        finally:
            b2.close()

    def test_no_destructive_update_rowcount_only_grows(self, tmp_path):
        b = _open(tmp_path)
        try:
            b.record_set(key="k", value="a")
            b.record_set(key="k", value="b")
            b.record_remove(key="k")
            b.record_set(key="k", value="c")
            # append-only: one ledger row per action, nothing overwritten
            assert len(b.load_events("kira")) == 4
        finally:
            b.close()

    def test_source_ref_is_stored_but_not_required(self, tmp_path):
        b = _open(tmp_path)
        try:
            ev = b.record_set(key="k", value="v", source_ref="turn-123")
            assert ev.source_ref == "turn-123"
            cur = b.load_current_state("kira")
            assert cur[0].source_ref == "turn-123"
        finally:
            b.close()

    def test_rejects_inactive_domain_and_bad_input(self, tmp_path):
        b = _open(tmp_path)
        try:
            with pytest.raises(RuntimeStateError):
                b.record_set(key="k", value="v", domain="RELATIONSHIP")
            with pytest.raises(RuntimeStateError):
                b.record_set(key="k", value="v", domain="PSYCHOLOGY")
            with pytest.raises(RuntimeStateError):
                b.record_set(key="", value="v")
            with pytest.raises(RuntimeStateError):
                b.record_set(key="k", value="")
            with pytest.raises(RuntimeStateError):
                b.record_set(key="k", value="v", source_kind="MODEL_HYPOTHESIS")
        finally:
            b.close()
