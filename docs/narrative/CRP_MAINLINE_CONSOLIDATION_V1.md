# CRP vNext — MAINLINE CONSOLIDATION (v1)

> **Status:** IMPLEMENTATION EVIDENCE RECORD — not a new ratification, not a Canon promotion
> **Date:** 2026-09-21
> **Track:** CRP vNext (Character Reconstruction Pipeline)
> **Companion documents:** [`CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md`](CRP_VNEXT_ARCHITECTURE_RATIFICATION_v1.md),
> [`CRP_VNEXT_DECISION_REGISTER_v1.md`](CRP_VNEXT_DECISION_REGISTER_v1.md), [`CRP_MVP_SPEC_v1.md`](CRP_MVP_SPEC_v1.md),
> [`CRP_MVP_CONTRACTS_v1.md`](CRP_MVP_CONTRACTS_v1.md)
> **Source branch:** `feature/character-lab-crp-integration-v1`, based on `origin/main` @ `a3e47418a0a8003544f4524b2d899c334b8c9a54`

---

## 0. What this document is

The three documents above are marked `IMPLEMENTATION_NOT_AUTHORIZED`. Despite that, a real,
extensively tested CRP vNext implementation was built on `feature/crp-mvp-v1` and its descendant
branches, was exercised with a real provider against a real, owner-authored KIRA evidence set, passed
R8 audit, and was accepted by the owner (`HUMAN_APPROVED`) — none of which ever reached `origin/main`.
This document records that fact and the consolidation performed in task
`CRP_MAINLINE_CONSOLIDATION_AND_CHARACTER_LAB_ADAPTER_V1`. It does not authorize anything retroactively
and does not change the status of the specs above; it is evidence, filed alongside them.

## 1. What was ported

From `feature/crp-mvp-v1` (tip `e0485ca610aac35d6c5773ded8df7723c981bf27`) onto this branch, by exact
path (`git checkout <source> -- <path>`, content byte-identical to the source blobs):

- `services/crp_authoring/` — the full engine (contracts, role_task, executor, orchestrator, registry,
  compiler, validator, auditor_checks, r8_llm_judgment, reconstruction_audit, candidate_package,
  candidate_rehydration, dataset_freeze, acceptance_store, lifecycle, permissions, voice_rules,
  knowledge_profile, errors).
- `roles/vnext/` — `CRP_ROLE_REGISTRY_v1.yaml` and the R1/R2/R3/R4/R8 prompt files (R6/R7 are
  deterministic functions with no prompt).
- `tests/crp_authoring/` — 27 of 28 test files (`test_current_kira_package_v1.py` excluded; it imports
  the superseded `services.character_companion`/`services.character_lab` and a separate VCP worktree —
  out of scope per Part 23 of the consolidation task).
- `tests/fixtures/crp_authoring/` — the KIRA dataset-freeze fixture (`kira_dataset_freeze/v1/`) and the
  golden-negative fixtures.
- `tools/crp_kira_r4_runner.py`, `tools/crp_provider_adapter.py`.
- `accepted/kira/ACCEPTANCE.json`, `accepted/kira/source_candidate.json` — see §3.

None of `services/character_companion`, `character_core`, `character_runtime`, the old
`services/character_lab` (a live-chat web app, unrelated to and name-colliding with
`services/character_lab_application`), Studio, S8B/S8B2/S8C1/S8C2, or the Anthropic dialogue CLI were
ported — none is a proven CRP-generic dependency (Part 23).

Working-tree line endings were normalized from CRLF back to LF after checkout (a local
`core.autocrlf=true` artifact of this Windows checkout — the source Git blobs were already LF-only;
`git diff` against the source commit is empty). No semantic content was changed.

## 2. What was added (new, not ported)

- `services/crp_authoring/relevance.py` — the R3 relevance boundary (`evaluate_r3_relevance`,
  `R3RelevanceResult`, `R3RelevanceStatus`). Deterministic, explicit-signal-only; reads only documented
  `SourceEvidence.metadata` markers, never infers from appearance/gender/attractiveness/attachment-label
  alone (no such fields exist on `SourceEvidence` for it to read). Relevance is data only — it cannot
  construct or hold an `activation_authorization_ref`; the existing hard gate in
  `RoleTask.__post_init__` (`GATED_OPTIONAL_ROLES = {"R3"}`) is untouched and unweakened.
- `services/crp_authoring/application_adapter.py` — a Lab-independent facade
  (`evaluate_specialist_relevance`, `prepare_reconstruction`, `start_reconstruction`,
  `get_reconstruction_result`). Imports only from within `services.crp_authoring`; never imports
  `services.character_lab_application`, `ui.character_lab`, or any Companion/Studio module, so it is
  usable and testable before the Character Lab Foundation is published (see §4).
- One new test-architecture-boundary check
  (`test_no_character_lab_or_companion_imports` in the ported `test_architecture_boundary.py`) plus
  three new test files: `test_relevance.py`, `test_application_adapter.py`,
  `test_kira_reference_fixture_integrity.py`.
- Two index/doc entries: this document, and one new row in `00_DOCUMENT_INDEX.md`.

## 3. The KIRA reference fixture

`accepted/kira/{ACCEPTANCE.json,source_candidate.json}` is a **regression/reference fixture**, ported
unmodified from commit `7e976bf0` ("CRP Kira: materialize accepted package", 2026-08-29) on
`feature/crp-mvp-v1`. It records:

- a real live-provider run (`deepseek-v4-pro`, evidence external to Git at
  `LOCAL_STORAGE/crp_r4_live_runs/RUN_015.stdout.json` — not copied into Git, per Part 17);
- roles R1+R2+R3+R4 executed, R8 independent audit `PASS`
  (`RUN_015_R8_V2_DIRECT_REVALIDATION.stdout.json`, `LOCAL_STORAGE`, candidate hash matches exactly);
- package hash `e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd`, recomputable from the
  ported `source_candidate.json` via `services.crp_authoring.auditor_checks.compute_package_hash` (proven
  in `test_kira_reference_fixture_integrity.py`);
- decision `HUMAN_APPROVED`, `decided_by: "owner"`, 2026-08-29.

**This fixture MUST NOT be treated as `narrative-character-canon` current state, a published Character
Canon, or a current game character release.** No Canon write or promotion is authorized by this task or
by the fixture's presence here.

## 4. Character Lab integration status

`services/character_lab_application/`, `ui/character_lab/` and their tests are **not present on
`origin/main`** — they exist only as uncommitted work in a different worktree
(`vne-character-lab-foundation-v1`). Per the consolidation task's Case B: that uncommitted candidate was
not copied, that worktree was not touched, and no `services/character_lab_application`/`ui/character_lab`
paths were created here. `services/crp_authoring/application_adapter.py` is the Lab-independent
groundwork a future `character_lab_application` layer can import once the Foundation is published; actual
UI/application-service wiring is deferred (`LAB_ADAPTER_DEFERRED_FOUNDATION_NOT_PUBLISHED`).

## 5. `CRP_VNEXT_DECISION_REGISTER_v1.md` divergence — NOT reconciled here

`origin/main`'s `CRP_VNEXT_DECISION_REGISTER_v1.md` (this branch's copy is unmodified) does not contain
the decision below, which exists only on `feature/crp-mvp-v1` and descendants (introduced by commit
`c1471793`, 2026-08-26):

> **CRP-OD-R4-KIRA-R3-01** — R3 mandatory for first canonical Kira reconstruction. Status:
> OWNER_RATIFIED, 2026-08-23. For the FIRST canonical Kira reconstruction, R3 is REQUIRED
> (R1+R2+R3+R4, then R8), overriding the default MVP subset (R1+R2+R4+R6+R8, CRP-OD-5) for that run
> only. Registry `ACTIVE` does not auto-insert R3 into any run; role selection stays caller-owned.

Classification: **SUPPORTED_BY_KIRA_ACCEPTED_RESULT** — the KIRA fixture in `accepted/kira/` (§3) is
direct proof this decision was acted on and produced an accepted result. It is not `STALE` or
`CONFLICTING` — it does not contradict anything on `origin/main`, it simply postdates and extends the
main-line register.

This document does **not** edit `CRP_VNEXT_DECISION_REGISTER_v1.md`. Per Part 15 of the consolidation
task, that remains an owner reconciliation action. Proposed patch (not applied): append the
`CRP-OD-R4-KIRA-R3-01` entry above, verbatim, to `origin/main`'s register in its own future commit.

## 6. Historical worktrees

`vne-crp-mvp-v1` and its descendants (`vne-current-kira-package-v1`,
`vne-companion-character-package-importer-v1`, `-management-v1`,
`vne-kira-package-runtime-definition-v1`, `vne-kira-package-v1-visual-binding-s1`, `vne-s8b*/-s8c*`,
`vne-crp-anthropic-dialogue-v1-s1`) were read from, not written to, by this task, and remain unchanged.
No future CRP work on this line should need to check them out again — the consolidated, tested engine
now lives on `feature/character-lab-crp-integration-v1`.
