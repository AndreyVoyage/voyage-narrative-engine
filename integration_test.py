#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Integration Test Runner (ITR) v2.1
Тестирует session_finalize.py с модульной архитектурой персон.
"""

import json
import sys
from pathlib import Path

# Добавляем корень репозитория в путь
REPO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_DIR))

import session_finalize as sf

# =============================================================================
# FIXTURES
# =============================================================================

def load_test_personas():
    personas = {}
    for char in ["kira", "sergey", "marina", "maksim"]:
        p = sf.load_persona(char)
        if p:
            personas[char] = p
    return personas


# =============================================================================
# TEST CASES
# =============================================================================

def test_level_escalation_kira():
    """TC-001: Kira level escalation U1 -> U7 via signature keywords."""
    personas = load_test_personas()
    engine = sf.SessionEngine(scenario_id="test_escalation", personas=personas)

    # U1-A (neutral)
    engine.add_turn("kira", "Кира: Не знаю, может быть, я не уверена. Всё спокойно.")
    state = engine.get_state()
    lvl = state["characters"]["kira"]["current_level"]
    assert lvl in ("U1-A", "unknown"), f"Expected U1-A, got {lvl}"

    # U2-A (provocation)
    engine.add_turn("kira", "Кира: Ты меня провоцируешь. Но я не такая простая, понял?")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U2-A", \
        f"Expected U2-A, got {state['characters']['kira']['current_level']}"

    # U3-A (tremor, blush)
    engine.add_turn("kira", "Кира: Почему ты смотришь так... *покраснела* *дрожь* Не должна так думать.")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U3-A", \
        f"Expected U3-A, got {state['characters']['kira']['current_level']}"

    # U4-A (passive submission)
    engine.add_turn("kira", "Кира: Не могу... только не остановись... *тремор* пассивное подчинение.")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U4-A", \
        f"Expected U4-A, got {state['characters']['kira']['current_level']}"

    # U5-A (provocations)
    engine.add_turn("kira", "Кира: Ты ещё не видел настоящую меня. Стервозная провокация.")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U5-A", \
        f"Expected U5-A, got {state['characters']['kira']['current_level']}"

    # U6-A (dominance)
    engine.add_turn("kira", "Кира: Ползи. Ты заслужил. Докажи, повелительница.")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U6-A", \
        f"Expected U6-A, got {state['characters']['kira']['current_level']}"

    # U7-A (regret)
    engine.add_turn("kira", "Кира: Испортила всё... ты всё ещё хочешь? *плачет* раскаяние.")
    state = engine.get_state()
    assert state["characters"]["kira"]["current_level"] == "U7-A", \
        f"Expected U7-A, got {state['characters']['kira']['current_level']}"

    print("✅ TC-001 LEVEL_ESCALATION_KIRA passed")


def test_fmdr_extraction():
    """TC-002: FMDR block extraction."""
    text = "Кира: (Мысли: он смотрит... Действие: *отводит взгляд* Речь: Не смотри так.)"
    fmdr = sf.extract_fmdr(text)
    assert "thoughts" in fmdr or "actions" in fmdr or "speech" in fmdr, \
        f"FMDR not extracted properly: {fmdr}"
    print("✅ TC-002 FMDR_EXTRACTION passed")


def test_flag_detection():
    """TC-003: Flags detection from text."""
    personas = load_test_personas()
    engine = sf.SessionEngine(scenario_id="test_flags", personas=personas)
    engine.add_turn("kira", "Кира: Это был наш первый поцелуй... *краснеет*")
    engine.add_turn("user", "Пользователь: Вот мой номер телефона.")
    state = engine.get_state()
    flags = state["characters"]["kira"]["flags"]
    assert "first_kiss" in flags, f"first_kiss not in flags: {flags}"
    print("✅ TC-003 FLAG_DETECTION passed")


def test_emergency_stop():
    """TC-004: Emergency stop processing."""
    personas = load_test_personas()
    engine = sf.SessionEngine(scenario_id="test_stop", personas=personas)
    engine.add_turn("kira", "Кира: Привет.")
    engine.add_turn("user", "Пользователь: [СТОП] Хватит.")
    state = engine.get_state()
    assert state["stop_turn"] is not None, "stop_turn should be set"
    assert state["characters"]["kira"]["emergency_stop"] is True, \
        "emergency_stop should be True"
    print("✅ TC-004 EMERGENCY_STOP passed")


def test_vscno_integrity():
    """TC-005: VSCNO sum == 10 invariant."""
    personas = load_test_personas()
    engine = sf.SessionEngine(scenario_id="test_vscno", personas=personas)
    engine.add_turn("kira", "Кира: *улыбается* ВЛ+1 СТ-1")
    state = engine.get_state()
    vscno = state["characters"]["kira"]["vscno"]
    total = sum(vscno.values())
    assert total == 10, f"VSCNO sum {total} != 10 (values: {vscno})"
    print("✅ TC-005 VSCNO_INTEGRITY passed")


def test_audit_log_level_transition():
    """TC-006: Audit log records level transitions."""
    personas = load_test_personas()
    engine = sf.SessionEngine(scenario_id="test_audit", personas=personas)
    engine.add_turn("kira", "Кира: Не знаю, может быть.")   # U1
    engine.add_turn("kira", "Кира: Ты меня провоцируешь.")  # U2
    state = engine.get_state()
    transitions = [e for e in state["audit_log"] if e.get("event") == "LEVEL_TRANSITION"]
    assert len(transitions) >= 1, \
        f"Expected level transitions in audit_log, got {state['audit_log']}"
    print("✅ TC-006 AUDIT_LOG_TRANSITIONS passed")


def test_process_step_isolation():
    """TC-007: process_step works as standalone module call."""
    result = sf.process_step(None, "kira", "Кира: Ты меня провоцируешь. Не такая простая.")
    assert "characters" in result, "process_step should return state dict with characters"
    assert result["characters"]["kira"]["current_level"] == "U2-A", \
        f"Expected U2-A from process_step, got {result['characters']['kira']['current_level']}"
    print("✅ TC-007 PROCESS_STEP_ISOLATION passed")


# =============================================================================
# RUNNER
# =============================================================================

def run_all():
    tests = [
        test_level_escalation_kira,
        test_fmdr_extraction,
        test_flag_detection,
        test_emergency_stop,
        test_vscno_integrity,
        test_audit_log_level_transition,
        test_process_step_isolation,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"❌ {t.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"💥 {t.__name__} ERROR: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
