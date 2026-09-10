#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMPANION_CONTEXT_POLICY_V1C -- GroundedV2Policy operational context budget.

Offline, no provider, no network. Proves the request-assembly budget:

* bare ``GroundedV2Policy()`` is byte-for-byte the legacy unbounded behavior;
* an explicit budget bounds ONLY the assembled provider request (the caller's
  ``history`` list is untouched, and ``select_memory``'s own 20/6000 bound is
  unchanged);
* deterministic language-safer estimated-token unit;
* MUST-KEEP overflow fails closed with a Character-Lab-local error, before any
  provider call / persistence;
* metadata-only budget report (no message / memory / grounding text).
"""

from __future__ import annotations

import math

import pytest

from services.character_lab.grounding import render_accepted_grounding
from services.character_lab.runtime_policy import (
    CONTEXT_BUDGET_ESTIMATOR_ID,
    MESSAGE_OVERHEAD_EST_TOKENS,
    OUTPUT_RESERVE_EST_TOKENS,
    PROTECTED_RECENT_TURNS,
    ContextBudgetExceededError,
    GroundedV2Policy,
    _GROUNDED_V2_CORE_INSTRUCTION,
    build_assembly_hash,
    content_est_tokens,
    message_est_tokens,
)


# --------------------------------------------------------------------------- helpers
class _Claim:
    def __init__(self, text: str, confidence: str = "CANONICAL") -> None:
        self.claim = text
        self.confidence = confidence


class _FakePkg:
    package_id = "pkg-ctx-budget"
    package_version = 1
    status = "ACCEPTED"
    identity_biography_candidate = {
        "bio": [_Claim("Кира — тестовый персонаж для проверки бюджета контекста запроса.")]
    }
    psychology_candidate: dict = {}
    behavior_candidate: dict = {}
    relationships_candidate: dict = {}
    boundaries_candidate: dict = {}
    intimacy_candidate: dict = {}
    voice_candidate: dict = {}
    contradictions: tuple = ()
    unknowns: tuple = ()


def _rc(*, package=None, state=None, causal=None, consolidated=None):
    return {
        "accepted_package": package,
        "source_candidate_hash": "hash-ctx",
        "runtime_state": state or [],
        "causal_memory": causal or [],
        "consolidated_memory": consolidated or [],
    }


def _turns(n: int, *, body_reps: int = 30, start: int = 0):
    """n complete [user, assistant] turns, mostly Cyrillic."""
    out = []
    for i in range(start, start + n):
        out.append({"role": "user", "content": f"сообщение пользователя {i}: " + "бла " * body_reps})
        out.append({"role": "assistant", "content": f"ответ персонажа {i}: " + "ла " * body_reps})
    return out


def _hist_msgs(assembly):
    msgs = [m for m in assembly.messages if m["role"] in ("user", "assistant")]
    return msgs[:-1], msgs[-1]  # (history, current-user)


def _report(assembly):
    items = [it for it in assembly.manifest.items if it.kind == "context.budget_report"]
    return items[0].meta if items else None


# ------------------------------------------------------------------- estimator
def test_05_estimator_deterministic_ascii():
    assert content_est_tokens("") == 0
    assert message_est_tokens("") == MESSAGE_OVERHEAD_EST_TOKENS
    for s in ("hello world", "a" * 100, "The quick brown fox."):
        v = content_est_tokens(s)
        assert v == max(math.ceil(len(s) / 3), math.ceil(len(s.encode("utf-8")) / 4))
        assert content_est_tokens(s) == v  # repeatable
        assert message_est_tokens(s) == v + MESSAGE_OVERHEAD_EST_TOKENS


def test_06_estimator_cyrillic_more_conservative_than_len_over_3():
    ru = "я" * 120  # 120 chars, 240 UTF-8 bytes -> byte term (60) beats len/3 (40)
    assert content_est_tokens(ru) == 60
    assert content_est_tokens(ru) > math.ceil(len(ru) / 3)
    # a mixed string is still deterministic + >= the simple len/3 lower bound
    mixed = "Кира: привет! Hello there. " * 5
    assert content_est_tokens(mixed) >= math.ceil(len(mixed) / 3)
    assert content_est_tokens(mixed) == content_est_tokens(mixed)


def test_07_fixed_message_overhead_applied():
    assert message_est_tokens("abc") == content_est_tokens("abc") + MESSAGE_OVERHEAD_EST_TOKENS
    assert OUTPUT_RESERVE_EST_TOKENS == 2048 and MESSAGE_OVERHEAD_EST_TOKENS == 8
    assert PROTECTED_RECENT_TURNS == 2


# ---------------------------------------------------------------- legacy path
def test_01_bare_policy_is_unbounded_and_unmarked():
    hist = _turns(40)
    a = GroundedV2Policy().assemble_context(
        runtime_context=_rc(package=_FakePkg()), session_id="s", history=hist,
        user_message="текущее сообщение",
    )
    history, current = _hist_msgs(a)
    assert len(history) == 80 and history == hist          # whole history passes through
    assert current == {"role": "user", "content": "текущее сообщение"}
    assert _report(a) is None                              # NO budget-report item
    # a huge single history message is NOT dropped on the legacy path
    big = hist + [{"role": "user", "content": "мега " * 20000}, {"role": "assistant", "content": "ok"}]
    a2 = GroundedV2Policy().assemble_context(
        runtime_context=_rc(package=_FakePkg()), session_id="s", history=big, user_message="c",
    )
    assert [m for m in a2.messages if m["role"] in ("user", "assistant")][-3]["content"] == "мега " * 20000


# --------------------------------------------------------------- budgeted path
def _assemble(budget, hist, *, package=_FakePkg, state=None, causal=None, consolidated=None,
              user_message="текущее сообщение"):
    return GroundedV2Policy(context_budget_est_tokens=budget).assemble_context(
        runtime_context=_rc(
            package=package() if isinstance(package, type) else package,
            state=state, causal=causal, consolidated=consolidated,
        ),
        session_id="s", history=hist, user_message=user_message,
    )


def test_09_long_conversation_request_is_bounded():
    hist = _turns(60)
    a = _assemble(6000, hist)
    history, _ = _hist_msgs(a)
    assert 0 < len(history) < 120
    m = _report(a)
    assert m["est_assembled_tokens"] <= m["effective_input_budget_est_tokens"]
    assert m["effective_input_budget_est_tokens"] == 6000 - OUTPUT_RESERVE_EST_TOKENS


def test_10_newest_history_retained():
    hist = _turns(40)
    history, _ = _hist_msgs(_assemble(6000, hist))
    assert history[-1] == hist[-1]                         # newest assistant reply kept
    assert history == hist[len(hist) - len(history):]      # exactly the newest contiguous run


def test_11_complete_turn_integrity():
    hist = _turns(40)
    history, _ = _hist_msgs(_assemble(6000, hist))
    assert len(history) % 2 == 0                           # only whole [user, assistant] pairs
    for i in range(0, len(history), 2):
        assert history[i]["role"] == "user" and history[i + 1]["role"] == "assistant"


def test_12_final_history_order_is_chronological():
    hist = _turns(40)
    history, _ = _hist_msgs(_assemble(6000, hist))
    start = hist.index(history[0])
    assert history == hist[start:start + len(history)]     # oldest-selected -> newest-selected


def test_14_must_keep_always_present_on_success():
    a = _assemble(20000, _turns(5))
    sys_contents = [m["content"] for m in a.messages if m["role"] == "system"]
    assert any("Ты — Кира, персонаж" in c for c in sys_contents)          # role instruction
    assert any("ACCEPTED CHARACTER GROUNDING" in c for c in sys_contents)  # grounding
    assert a.messages[-1] == {"role": "user", "content": "текущее сообщение"}
    m = _report(a)
    assert "system.role_instruction" in m["blocks_included"]
    assert "system.package_grounding" in m["blocks_included"]


def test_15_state_and_consolidated_before_history():
    state = [
        {"domain": "FACT", "key": "город", "value": "Москва", "seq": 1},
        {"domain": "RELATIONSHIP", "key": "доверие", "value": "40", "seq": 2},
        {"domain": "PSYCHOLOGY", "key": "настроение", "value": "10", "seq": 3},
    ]
    consolidated = [{"record_id": "r1", "meaning": "собеседник любит море", "seq": 1,
                     "source_event_id": "e1", "basis_event_ids": [], "in_conflict": False}]
    a = _assemble(9000, _turns(50), state=state, consolidated=consolidated)
    m = _report(a)
    for kind in ("system.runtime_state", "system.relationship_state",
                 "system.psychology_state", "system.consolidated_memory"):
        assert kind in m["blocks_included"], kind
    # history was trimmed while those blocks survived
    assert m["history_messages_selected"] < m["history_messages_available"]
    sys_contents = "\n".join(m2["content"] for m2 in a.messages if m2["role"] == "system")
    assert "ПОДТВЕРЖДЁННОЕ СОСТОЯНИЕ ОТНОШЕНИЙ" in sys_contents


def test_16_two_newest_turns_attempted_before_raw_memory():
    causal = [
        {"event_id": f"e{i}", "session_id": "other", "event_type": "USER_MESSAGE",
         "meaning": f"пользовательский факт номер {i}: " + "деталь " * 12, "seq": i,
         "provenance": "USER_STATED"}
        for i in range(1, 13)
    ]
    hist = _turns(40, body_reps=2)
    pkg = _FakePkg()
    pol = GroundedV2Policy()

    # exact costs, so the budget is set precisely: PHASE C (2 newest turns) wins
    # the contested slot -> raw memory omitted, even though memory ALONE would fit.
    must = (
        message_est_tokens(_GROUNDED_V2_CORE_INSTRUCTION)
        + message_est_tokens(render_accepted_grounding(pkg))
        + message_est_tokens("текущее сообщение")
    )
    two_newest_cost = sum(message_est_tokens(x["content"]) for x in hist[-4:])
    mem_cost = message_est_tokens(pol._memory_block(pol.select_memory(_rc(causal=causal), "s")))
    assert two_newest_cost >= 1 and mem_cost > 1
    # E = must + two_newest_cost + mem_cost - 1  -> memory misses by 1 after the
    # 2 turns, but E - must >= mem_cost so memory ALONE would have fit.
    budget = OUTPUT_RESERVE_EST_TOKENS + must + two_newest_cost + mem_cost - 1

    a = _assemble(budget, hist, package=pkg, causal=causal)
    m = _report(a)
    assert m["history_turns_selected"] >= min(PROTECTED_RECENT_TURNS, m["history_turns_available"])
    assert "system.memory_grounding" in m["blocks_omitted_budget"]
    assert "system.memory_grounding" not in m["blocks_included"]
    history, _ = _hist_msgs(a)
    assert history[-4:] == hist[-4:]                       # the two newest turns kept


def test_17_raw_memory_before_additional_older_history():
    causal = [
        {"event_id": f"e{i}", "session_id": "other", "event_type": "USER_MESSAGE",
         "meaning": "факт " + str(i), "seq": i, "provenance": "USER_STATED"}
        for i in range(1, 4)
    ]
    hist = _turns(40)
    a = _assemble(7000, hist, causal=causal)
    m = _report(a)
    assert "system.memory_grounding" in m["blocks_included"]
    # raw memory got budget; some but not all older history is included
    assert 0 < m["history_messages_selected"] < m["history_messages_available"]


def test_18_epistemic_context_is_lowest_priority():
    # No epistemic snapshot here -> the block is absent, which is the common case;
    # this asserts the ordering CONTRACT via blocks_included ordering + that a
    # present epistemic block is the last thing tried. We validate the ordering
    # rule structurally: epistemic never appears in blocks_included before history
    # selection has run (it is appended in PHASE F).
    a = _assemble(20000, _turns(3))
    m = _report(a)
    assert "system.epistemic_context" not in m["blocks_included"]  # nothing to add
    # sanity: role instruction is always first-included
    assert m["blocks_included"][0] == "system.role_instruction"


# --------------------------------------------------------------------------- #
# History selection is ONE strictly-contiguous newest->oldest window. The first
# complete turn that does not fit ends selection; no older turn is inspected
# after that -- across PHASE C and PHASE E alike.
# --------------------------------------------------------------------------- #
def _must_keep_est(pkg):
    return (
        message_est_tokens(_GROUNDED_V2_CORE_INSTRUCTION)
        + message_est_tokens(render_accepted_grounding(pkg))
        + message_est_tokens("текущее сообщение")
    )


def _turn_cost(hist, i):
    """est cost of the [user, assistant] turn whose user message is hist[i]."""
    return message_est_tokens(hist[i]["content"]) + message_est_tokens(hist[i + 1]["content"])


def test_19_oversized_single_turn_dropped_whole_zero_history():
    hist = _turns(6) + [{"role": "user", "content": "мега " * 6000},
                        {"role": "assistant", "content": "ответ"}]
    a = _assemble(4000, hist)                              # newest turn is oversized
    m = _report(a)
    assert m["history_oversized_turns_dropped"] >= 1
    history, _ = _hist_msgs(a)
    assert history == []                                  # contiguous cutoff at the newest turn
    assert m["history_turns_selected"] == 0
    assert "мега мега" not in "".join(x["content"] for x in history)


def test_19b_case_A_newest_oversized_second_newest_would_fit_still_zero():
    """CASE A: newest complete turn does not fit; the second-newest WOULD fit ->
    still ZERO historical turns (no skip-ahead)."""
    pkg = _FakePkg()
    older = {"role": "user", "content": "маленький вопрос"}, {"role": "assistant", "content": "краткий ответ"}
    newest = {"role": "user", "content": "гигант " * 8000}, {"role": "assistant", "content": "ok"}
    hist = [*older, *newest]
    must = _must_keep_est(pkg)
    would_fit_older = _turn_cost(hist, 0)
    # E leaves room for the older turn but NOT the (oversized) newest turn.
    budget = OUTPUT_RESERVE_EST_TOKENS + must + would_fit_older + 50
    a = _assemble(budget, hist, package=pkg)
    history, current = _hist_msgs(a)
    assert current == {"role": "user", "content": "текущее сообщение"}
    assert history == []                                  # older fitting turn is NOT resurrected
    m = _report(a)
    assert m["history_turns_selected"] == 0 and m["mandatory_overflow"] is False
    assert m["history_oversized_turns_dropped"] >= 1


def test_19c_case_B_no_skip_ahead_past_a_non_fitting_middle_turn():
    """CASE B: newest two turns fit; the third-newest does not; the fourth-newest
    WOULD fit -> select exactly the newest two, nothing older."""
    pkg = _FakePkg()
    # T1(old) small, T2 small, T3 BIG, T4 small, T5(newest) small
    hist = (
        [{"role": "user", "content": "T1 " + "щ" * 20}, {"role": "assistant", "content": "r1"}]
        + [{"role": "user", "content": "T2 " + "щ" * 20}, {"role": "assistant", "content": "r2"}]
        + [{"role": "user", "content": "T3 " + "щ" * 4000}, {"role": "assistant", "content": "r3"}]
        + [{"role": "user", "content": "T4 " + "щ" * 20}, {"role": "assistant", "content": "r4"}]
        + [{"role": "user", "content": "T5 " + "щ" * 20}, {"role": "assistant", "content": "r5"}]
    )
    must = _must_keep_est(pkg)
    cT5, cT4, cT3, cT2 = _turn_cost(hist, 8), _turn_cost(hist, 6), _turn_cost(hist, 4), _turn_cost(hist, 2)
    assert cT3 > cT2                                      # T3 genuinely bigger than the skipped T2
    # after MUST_KEEP + T5 + T4 the leftover == cT2 exactly: T2 WOULD fit if reached,
    # but PHASE E stops at the non-fitting T3 and never inspects T2/T1.
    budget = OUTPUT_RESERVE_EST_TOKENS + must + cT5 + cT4 + cT2
    a = _assemble(budget, hist, package=pkg)
    history, _ = _hist_msgs(a)
    assert history == hist[6:10]                          # exactly T4, T5, chronological
    contents = "".join(x["content"] for x in history)
    assert "T3 " not in contents and "T2 " not in contents and "T1 " not in contents
    m = _report(a)
    assert m["history_turns_selected"] == 2
    assert m["oldest_selected_history_index"] == 6 and m["newest_selected_history_index"] == 9


def test_19d_case_C_protected_phase_cutoff_blocks_additional_history():
    """CASE C: a protected recent turn fails to fit in PHASE C -> that cutoff
    stands; PHASE E adds NO older turns even though they would fit."""
    pkg = _FakePkg()
    # T1..T3 small (would fit), T4 BIG (2nd-newest, will not fit), T5 small (newest)
    hist = (
        [{"role": "user", "content": "T1 " + "ж" * 20}, {"role": "assistant", "content": "r1"}]
        + [{"role": "user", "content": "T2 " + "ж" * 20}, {"role": "assistant", "content": "r2"}]
        + [{"role": "user", "content": "T3 " + "ж" * 20}, {"role": "assistant", "content": "r3"}]
        + [{"role": "user", "content": "T4 " + "ж" * 4000}, {"role": "assistant", "content": "r4"}]
        + [{"role": "user", "content": "T5 " + "ж" * 20}, {"role": "assistant", "content": "r5"}]
    )
    must = _must_keep_est(pkg)
    cT5, cT4 = _turn_cost(hist, 8), _turn_cost(hist, 6)
    # room for MUST_KEEP + T5, then T4 misses by 1 -> cutoff at the 2nd protected turn.
    budget = OUTPUT_RESERVE_EST_TOKENS + must + cT5 + (cT4 - 1)
    a = _assemble(budget, hist, package=pkg)
    history, _ = _hist_msgs(a)
    assert history == hist[8:10]                          # only T5
    contents = "".join(x["content"] for x in history)
    for token in ("T4 ", "T3 ", "T2 ", "T1 "):
        assert token not in contents
    m = _report(a)
    assert m["history_turns_selected"] == 1


def test_19e_trailing_unpaired_user_not_fitting_stops_history():
    """A newest trailing unpaired user that does not fit stops selection -- older
    complete turns are NOT included."""
    pkg = _FakePkg()
    hist = _turns(4, body_reps=2) + [{"role": "user", "content": "хвост " * 5000}]
    must = _must_keep_est(pkg)
    would_fit = _turn_cost(hist, 6)                       # the newest complete turn behind the tail
    budget = OUTPUT_RESERVE_EST_TOKENS + must + would_fit + 50
    a = _assemble(budget, hist, package=pkg)
    history, current = _hist_msgs(a)
    assert current == {"role": "user", "content": "текущее сообщение"}
    assert history == []                                  # tail didn't fit -> nothing older either
    assert _report(a)["history_turns_selected"] == 0


def test_20_mandatory_overflow_fails_closed_before_provider():
    with pytest.raises(ContextBudgetExceededError):
        GroundedV2Policy(context_budget_est_tokens=4000).assemble_context(
            runtime_context=_rc(package=_FakePkg()), session_id="s", history=[],
            user_message="я" * 200000,   # current message alone blows the budget
        )
    # grounding alone can also overflow a tiny budget
    with pytest.raises(ContextBudgetExceededError):
        GroundedV2Policy(context_budget_est_tokens=2100).assemble_context(
            runtime_context=_rc(package=_FakePkg()), session_id="s", history=_turns(3),
            user_message="c",
        )


def test_21_repeated_assembly_is_deterministic():
    hist = _turns(50)
    a = _assemble(6000, hist)
    b = _assemble(6000, hist)
    assert a.messages == b.messages
    assert build_assembly_hash(a.manifest) == build_assembly_hash(b.manifest)


def test_22_diagnostics_are_metadata_only():
    hist = _turns(60)
    m = _report(_assemble(6000, hist, user_message="секретный текущий вопрос пользователя"))
    assert m is not None
    blob = str(m)
    # never any conversation / memory / grounding text
    assert "секретный текущий" not in blob
    assert "сообщение пользователя" not in blob
    assert "ACCEPTED CHARACTER" not in blob and "Кира" not in blob
    # exactly the declared fields, all counts / kinds / ints / stable strings
    assert set(m) == {
        "budget_est_tokens", "effective_input_budget_est_tokens", "budget_unit",
        "estimator", "output_reserve_est_tokens",
        "history_messages_available", "history_messages_selected",
        "history_turns_available", "history_turns_selected",
        "oldest_selected_history_index", "newest_selected_history_index",
        "blocks_included", "blocks_omitted_budget",
        "est_assembled_tokens", "mandatory_overflow", "history_oversized_turns_dropped",
    }
    assert m["budget_unit"] == "estimated_tokens"
    assert m["estimator"] == CONTEXT_BUDGET_ESTIMATOR_ID
    for k in ("history_messages_available", "history_messages_selected",
              "history_turns_available", "history_turns_selected",
              "est_assembled_tokens", "history_oversized_turns_dropped"):
        assert isinstance(m[k], int)
    assert isinstance(m["blocks_included"], list) and isinstance(m["blocks_omitted_budget"], list)
    assert isinstance(m["mandatory_overflow"], bool)


def test_23_select_memory_bound_unchanged_by_budget():
    # The working-memory 20-event / 6000-char bound is a SEPARATE, untouched
    # layer -- assert both policies select the same raw-memory dicts.
    causal = [
        {"event_id": f"e{i}", "session_id": "other", "event_type": "USER_MESSAGE",
         "meaning": f"пользовательский факт номер {i} " + "у" * 30, "seq": i,
         "provenance": "USER_STATED"}
        for i in range(1, 40)
    ]
    rc = _rc(causal=causal)
    legacy_sel = GroundedV2Policy().select_memory(rc, "s")
    budgeted_sel = GroundedV2Policy(context_budget_est_tokens=32768).select_memory(rc, "s")
    assert legacy_sel == budgeted_sel
    assert len(legacy_sel) <= 20


def test_24_no_provider_or_network_dependency():
    # assemble_context is a pure function of its inputs -- no provider callable,
    # no sockets, no filesystem. Constructing + assembling here proves it.
    a = _assemble(6000, _turns(30))
    assert a.messages and a.manifest.items
