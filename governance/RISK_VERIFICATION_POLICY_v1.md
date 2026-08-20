# Risk & Verification Policy v1

> **Decision ID:** OD-GOV-RISK-01
> **Status:** OWNER-RATIFIED
> **Date:** 2026-08-20
> **Scope:** All NARRATIVE / VNE engineering and authoring-development tasks.
> **Canonical.** This is the authoritative source of truth for risk
> classification and verification depth. The agent entrypoint (`AGENTS.md`)
> references this document rather than duplicating it. Registered once in
> `governance/DECISION_REGISTER.md`.

---

## 1. Core rule

**RISK ASSESSMENT IS MANDATORY.**

**INDEPENDENT AUDIT IS RISK-TRIGGERED.**

Every bounded task must receive an R0–R4 classification **before**
implementation. Verification depth follows the assigned risk — nothing more,
nothing less, unless a documented escalation trigger fires.

---

## 2. Risk classes and minimum assurance model

| Class | Meaning | Minimum sufficient verification |
|---|---|---|
| **R0** | MINIMAL | scope + diff hygiene |
| **R1** | LOW | scope + targeted verification where relevant |
| **R2** | MEDIUM | targeted/integration verification |
| **R3** | HIGH | preflight + targeted/full QA + focused risk review |
| **R4** | CRITICAL | explicit owner authorization + dry-run/preflight + audit + rollback/post-verification |

These are **minimum** sufficient requirements. Do not automatically add
heavier gates without a documented escalation trigger.

---

## 3. Mandatory escalation rule

**STOP_ON_RISK_ESCALATION**

If actual implementation discovers a higher-risk surface than the assigned
class, the agent must STOP and return to the owner.

Escalation triggers include (non-exhaustive):

- runtime becomes affected
- persistence / migration becomes affected
- provider / network side effects become necessary
- a destructive operation becomes necessary
- canon / schema boundary expands
- security / secrets become involved

---

## 4. No gate creep

**NO GATE CREEP**

If actual risk does not increase during execution, agents must NOT
automatically add:

- forensic audits
- extra independent reviews
- full suites
- repeated preflights
- repeated owner gates

merely "for safety". Any extra verification must identify the concrete new
risk that triggered it.

---

## 5. Required prompt block

Every future implementation prompt MUST contain the following block:

```
RISK CLASS:
...

WHY:
...

REQUIRED VERIFICATION:
...

NOT REQUIRED:
...

RISK ESCALATION TRIGGERS:
...

IF TRIGGERED:
STOP_AND_RETURN_TO_OWNER
```

---

## 6. Risk calculator

No automated risk score/calculator exists in v1.

Initial classification is human/LLM judgment under this policy.

Revisit automation only after approximately 20–30 real classified tasks
provide enough evidence to calibrate one.