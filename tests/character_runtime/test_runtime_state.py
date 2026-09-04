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
    SOURCE_OPERATOR_CONFIRMED,
    RuntimeStateBackend,
    RuntimeStateError,
)


def _open(tmp_path):
    return RuntimeStateBackend(tmp_path / "ws", "kira")


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
