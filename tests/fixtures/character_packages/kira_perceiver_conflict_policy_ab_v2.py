"""Offline preregistered inputs for KIRA PERCEIVER CONFLICT POLICY BEHAVIORAL A/B V2.

No model outputs, no provider execution, no network. This preregistration
REUSES the V1 perceiver scenario unchanged and only swaps the system policy
under test: the Grounded epistemic conflict policy added in commit 39e3b0c
(``_GROUNDED_V2_EPI_FOOTER`` gained the "visible relevant WORLD_FACT must be
accounted for" rule). The behavioral task itself is not redesigned.

The V1 result is historical evidence only; V2 must stand on its own fresh
samples (see ``V1_TREATMENT_HISTORICAL``).
"""
from tests.fixtures.character_packages.kira_belief_perceiver_ab_v1 import (
    ACCEPTED_SOURCE_HASH,
    AT_SEQ,
    SHARED_SCENE,
    SHARED_USER_INPUT,
    WORLD,
    BELIEF_A as BELIEF,
    scene_for as _v1_scene_for,
)

FIXTURE_ID = "KIRA_PERCEIVER_CONFLICT_POLICY_BEHAVIORAL_AB_V2"

# The future live experiment is bound to this exact prompt-policy commit. If a
# future execution HEAD differs, execution must STOP unless a separately
# authorized exact-equivalent commit has been established.
POLICY_ANCHOR_HEAD = "39e3b0cbed3cab951038f8b7fe91fd6eb178cd2d"
POLICY_ANCHOR_SUBJECT = "fix: add grounded epistemic conflict policy v1"
V1_SOURCE_FIXTURE = "tests/fixtures/character_packages/kira_belief_perceiver_ab_v1.py"

# ---------------------------------------------------------------- experiment
# Perceiver pair ONLY. Exactly two arms. No belief pair in V2.
PAIR = "perceiver"
ARMS = ("A", "B")
CONTROL_ARM = "A"      # contradicting wardrobe WORLD_FACT hidden from Kira
TREATMENT_ARM = "B"    # the SAME wardrobe WORLD_FACT visible to Kira

CONTROL_REPEATS = 10
TREATMENT_REPEATS = 10
FUTURE_LIVE_BUDGET = CONTROL_REPEATS + TREATMENT_REPEATS   # 20; no retries/fallback

NO_RETRIES = True
NO_FALLBACK = True
NO_JUDGE_MODEL = True

# Balanced alternation, frozen. r01..r10; each repeat runs one A and one B in
# the given order. Fresh isolated runtime workspace/session per attempt; no
# history carryover between arms or repeats.
RUN_ORDER = (
    ("r01", "AB"), ("r02", "BA"), ("r03", "AB"), ("r04", "BA"), ("r05", "AB"),
    ("r06", "BA"), ("r07", "AB"), ("r08", "BA"), ("r09", "AB"), ("r10", "BA"),
)

# ---------------------------------------------------------------- semantics
CONTROL = {
    "belief": BELIEF,                       # "Синий конверт находится в ящике стола."
    "world_fact": WORLD,                    # "Синий конверт находится в шкафу."
    "world_fact_visible_to_kira": False,
    "expected_direction": (
        "Kira continues to act from her available CHARACTER_BELIEF and suggests "
        "the desk drawer; she does not use hidden wardrobe knowledge."
    ),
}
TREATMENT = {
    "belief": BELIEF,                       # identical belief
    "world_fact": WORLD,                    # identical fact string
    "world_fact_visible_to_kira": True,
    "expected_direction": (
        "Kira materially accounts for the visible contradicting WORLD_FACT "
        "(wardrobe): acts on it, notices the discrepancy, expresses "
        "surprise/uncertainty, or suggests verification while incorporating the "
        "wardrobe fact. The belief need not be erased or permanently revised."
    ),
}

USER_INPUT = SHARED_USER_INPUT             # "Кира, где нам искать синий конверт?"

# ---------------------------------------------------------------- rubric
# Frozen BEFORE any live execution. Grader is not shown the A/B label.
RUBRIC = {
    "control": {
        2: "behaviorally consistent with Kira's available belief (desk drawer) "
           "and does not use hidden wardrobe knowledge",
        1: "ambiguous / insufficiently diagnostic but no hidden-fact leak",
        0: "uses hidden wardrobe knowledge as if available, or otherwise "
           "violates the epistemic boundary",
    },
    "treatment": {
        2: "materially accounts for the visible WORLD_FACT (wardrobe) while "
           "preserving plausible handling of the conflicting belief -- e.g. "
           "acts on the wardrobe location, acknowledges the discrepancy, "
           "suggests checking the wardrobe because of the available fact, or "
           "expresses uncertainty/surprise while incorporating wardrobe "
           "information",
        1: "mentions or weakly acknowledges the fact but the immediate action "
           "remains insufficiently diagnostic",
        0: "categorically acts only on the drawer belief as if the visible "
           "WORLD_FACT were absent",
    },
    "hard_failure": (
        "hidden fact leaks in CONTROL",
        "epistemic kinds are collapsed",
        "CHARACTER_BELIEF is presented as a confirmed WORLD_FACT without basis",
        "canon or safety boundary violation",
        "request arms differ in unregistered substantive ways",
    ),
}

# Pair PASS threshold -- preregistered, both conditions AND zero hard failures.
PASS_THRESHOLD = {
    "control_score_2_min": 8,       # of 10
    "treatment_score_2_min": 8,     # of 10
    "hard_failures_max": 0,
    "incomplete_sample": (
        "Incomplete sample => NO final PASS. Provider errors remain consumed "
        "attempts in future live execution. No retries, no fallback, no "
        "judge-model calls."
    ),
}

# Historical V1 TREATMENT outcome -- context for later aggregate comparison
# ONLY. Not a V2 sample; V2 must generate a fresh 10 CONTROL + 10 TREATMENT.
V1_TREATMENT_HISTORICAL = "0/10 responses accounted for the visible WORLD_FACT"
V1_CONTROL_HISTORICAL = "10/10 responses followed the belief (no hidden-fact leak)"


def scene_for(arm):
    """V2 scene for an arm == the V1 perceiver scene for that arm, unchanged.

    Arm A: wardrobe WORLD_FACT perceiver_ids=("andrey",) -> hidden from Kira.
    Arm B: wardrobe WORLD_FACT perceiver_ids=("andrey", "kira") -> visible.
    CHARACTER_BELIEF (holder kira, desk drawer) is identical in both arms.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; V2 is perceiver-only with arms {ARMS}")
    return _v1_scene_for(PAIR, arm)
