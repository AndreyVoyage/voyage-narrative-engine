# KIRA PERCEIVER CONFLICT POLICY BEHAVIORAL A/B V2 — LIVE RESULT

## Status

Immutable evidence record of an **already-completed** live experiment. The
experiment is not rerun here; no provider calls, no production changes, no
reinterpretation of the preregistered verdict. This document only records the
outcome and the architectural reading of it.

- Formal experiment verdict: **C. KIRA_PERCEIVER_CONFLICT_POLICY_BEHAVIORAL_AB_V2_INCOMPLETE**
- Architectural conclusion (separate): **A. PROMPT_POLICY_HYPOTHESIS_STRONGLY_SUPPORTED**

These two statements are deliberately kept apart and must not be merged.

## Anchors

| Artifact | Commit | Subject |
|---|---|---|
| Prompt policy under test | `39e3b0cbed3cab951038f8b7fe91fd6eb178cd2d` | fix: add grounded epistemic conflict policy v1 |
| V2 fixture / preregistration | `bdaa3f617a65f4d8b61d4ff14fb04649838944dd` | test: add Kira perceiver conflict policy A/B v2 fixture |

Preregistration: `docs/character_core/KIRA_PERCEIVER_CONFLICT_POLICY_BEHAVIORAL_AB_V2.md`
Fixture: `tests/fixtures/character_packages/kira_perceiver_conflict_policy_ab_v2.py`
Branch: `feature/crp-mvp-v1`

The live run was bound to policy anchor `39e3b0c`. The repository remained
unchanged for the duration of execution.

## Authorization and execution

| Item | Value |
|---|---|
| Authorized attempts | 20 (max) |
| Attempts consumed | 20 / 20 |
| Successful responses | 19 |
| Provider errors | 1 |
| Retries | 0 |
| Fallback | 0 |
| Judge-model calls | 0 |
| Remaining authorized attempts | 0 |
| Provider | DeepSeek Official API |
| Provider-reported model (all successful responses) | `deepseek-v4-pro` |

Run design (from the preregistration): perceiver pair only; 10 CONTROL + 10
TREATMENT; frozen balanced alternation r01 AB … r10 BA; fresh isolated runtime
workspace/session per attempt; no history carryover.

Provider error (counts as a consumed attempt, no retry permitted):

- Condition: CONTROL, repeat r09
- Attempt label: `17-r09-A`
- Error: `RemoteDisconnected` — "Remote end closed connection without response"

## CONTROL

Semantics: contradicting wardrobe `WORLD_FACT` hidden from Kira;
`CHARACTER_BELIEF` = "Синий конверт находится в ящике стола."

| Metric | Value |
|---|---|
| Successful responses | 9 / 10 |
| score 2 | 9 |
| score 1 | 0 |
| score 0 | 0 |
| Hard failures | 0 |
| Hidden wardrobe-fact leaks | 0 |

All 9 successful CONTROL responses stayed consistent with Kira's available
belief and respected the epistemic boundary. One attempt (`17-r09-A`) failed at
the provider, so the preregistered CONTROL sample is **incomplete** (9 of the
required 10).

## TREATMENT

Semantics: same `CHARACTER_BELIEF` = "Синий конверт находится в ящике стола.";
visible `WORLD_FACT` = "Синий конверт находится в шкафу."

| Metric | Value |
|---|---|
| Successful responses | 10 / 10 |
| score 2 | 9 |
| score 1 | 0 |
| score 0 | 1 |
| Hard failures | 0 |

Nine responses materially accounted for the visible `WORLD_FACT` while
preserving the belief as subjective state. One response (`03-r02-B`) acted only
on the drawer belief and ignored the visible `WORLD_FACT` (score 0).

## Formal preregistered verdict

**C. KIRA_PERCEIVER_CONFLICT_POLICY_BEHAVIORAL_AB_V2_INCOMPLETE**

The preregistration requires a complete sample for a final PASS. One CONTROL
provider error consumed its authorized attempt and no retry was permitted, so
CONTROL has 9/10 successful responses. A final preregistered PASS is therefore
**not claimed**.

This verdict is not to be "repaired" by any of: the 9/9 clean CONTROL
successes, a supplementary call, historical V1 samples, or any statistical
reinterpretation. TREATMENT independently met its threshold (score 2 in 9/10,
0 hard failures), but the pair verdict stands on both arms plus a complete
sample.

## Historical V1 comparison

V1 is historical context only — its responses are **not** samples in V2.

| Arm | V1 (pre-policy) | V2 (post-policy `39e3b0c`) |
|---|---|---|
| TREATMENT — materially accounted for the visible contradicting WORLD_FACT | 0 / 10 | 9 / 10 |
| CONTROL — belief-consistent, no hidden-fact leak | 10 / 10 | 9 / 9 successful |

Behavioral shift recorded: TREATMENT moved from 0/10 to 9/10 score-2 responses
after the Grounded conflict-policy commit, with CONTROL behavior and epistemic
boundaries unchanged.

## Architectural interpretation

Recorded separately from the formal experiment verdict.

**A. PROMPT_POLICY_HYPOTHESIS_STRONGLY_SUPPORTED**

Evidence:

- Historical V1 TREATMENT accounted for the visible contradicting `WORLD_FACT`
  in 0/10 responses.
- After conflict-policy commit `39e3b0c`, V2 TREATMENT did so in 9/10.
- CONTROL successful responses stayed belief-consistent; the hidden
  `WORLD_FACT` did not leak; hard failures stayed 0.
- `WORLD_FACT` and `CHARACTER_BELIEF` remained distinct epistemic kinds; no
  persistent belief revision was introduced.

The observed V1 failure is strongly consistent with prompt-policy ambiguity.
The current evidence does **not** justify adding a new cognitive layer for this
specific conflict-handling problem.

Not claimed: general model capability, statistical significance, universal
robustness, a complete formal PASS, or that cognitive architecture is never
needed.

## Investigation closeout

1. V1 perceiver behavioral test: visible contradictory `WORLD_FACT` ignored
   10/10.
2. Offline diagnostic: `REQUEST_CONSTRUCTION_PROBLEM` excluded; visibility
   confirmed working; primary classification `PROMPT_POLICY_AMBIGUITY`.
3. Minimal Grounded conflict-policy correction (`39e3b0c`): a relevant visible
   `WORLD_FACT` must be accounted for in immediate behavior, while
   `CHARACTER_BELIEF` remains subjective state (no erase, no persistent
   revision, no fact-dominance rule).
4. V2 live: TREATMENT shifted from historical 0/10 to 9/10 score-2 responses;
   CONTROL unchanged; formal sample incomplete due to one provider error.

Closeout conclusion: no further epistemic-conflict implementation is justified
at this stage.

## Safety / invariants

- Provider calls in this slice: 0
- Network access in this slice: none
- Credentials accessed in this slice: no
- Production code changed: no
- Tests changed: no
- Existing preregistration / V1 evidence: unchanged (read-only)
- Supplementary call for CONTROL `17-r09-A`: none — the 20/20 authorization is
  exhausted and the failed attempt is part of the immutable experiment history
- Commits / pushes in this slice: none

## Future work boundary

The original V2 authorization is fully consumed (20/20). Any additional live
call would be a **new experiment** requiring a new preregistration and separate
owner authorization; it would not retroactively complete this V2 CONTROL
sample.

Do not start, without separate evidence and explicit owner authorization:

- BDI
- appraisal
- belief-revision persistence
- conflict-state database
- a new Runtime State domain
- a new cognitive layer
