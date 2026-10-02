# SCENARIO EDITOR — PROGRESS JOURNAL V1

**Document status:** ACTIVE / PROJECT_CONTINUITY
**Date:** 2026-10-02

> This journal records development evidence and milestone chronology for the
> Voyage Scenario Editor (SE). It does **not** replace the canonical roadmap,
> Owner decisions, or technical contracts. **Git is the source of truth for
> current branch and worktree positions** — a future reader must re-verify the
> real Git state before acting, and must never treat the dated snapshot below as
> live truth.

---

## A. CURRENT HANDOFF

| Field | Value |
|---|---|
| Product name | Voyage Scenario Editor |
| Development purpose | Standalone Windows visual multimedia editor for a writer to compose narrative scenes as connected Cards / Slides / Content Items / Utterances / Display Portions, then validate and publish them. |
| Permanent product branch | `Voyage-Scenario-Editor` |
| Permanent product worktree | `C:\DEV\Narrative\vne-voyage-scenario-editor` |
| Last verified **local** product HEAD | `df2fae21971878b1205599ffbbf41e7e680e620a` |
| Last verified **remote** product HEAD | NOT VERIFIED (no fetch/pull/network performed) |
| Active feature branch | `feature/voyage-scenario-editor-se11-foundation-v1` |
| Active feature worktree | `C:\DEV\Narrative\vne-scenario-se11-foundation-v1` |
| Exact feature commit SHA | `cdbc10ea068cc0359c28140157656cf3f1866b9e` |
| Current SE milestone | SE-1.1 — Identity & Storage Contract Foundation |
| Implementation status | IMPLEMENTED (7 files, locally committed) |
| Review status | A. PASS (final independent correction review; 0 blocker / 0 major / 0 minor) |
| Publication status | **LOCAL_COMMITTED** — NOT yet integrated into the product branch, NOT published |
| Current Owner authorization boundary | SE-1.1 local commit only. SE-1.2 is **NOT** authorized and must not be started automatically. |
| Next required action | Independent read-only continuity documentation review of this journal, then Owner-controlled authorization for SE-1.2. |
| Known blockers / open gates | See section D (exact W1 layout, P1 manifest, immutable Display Portion pinning, start_card compatibility, cross-scene targets, Character Library separation, no mandatory Story Runtime Semantics V1, plus the cosmetic EOF whitespace note). |

> **State precision.** `cdbc10ea068cc0359c28140157656cf3f1866b9e` is the SE-1.1
> **local** commit on the feature branch. It is **NOT** the product branch HEAD
> and **NOT** a published/integrated position. The permanent product branch
> `Voyage-Scenario-Editor` remains at `df2fae21971878b1205599ffbbf41e7e680e620a`
> (locally verified). Do not describe the feature commit as already published.

---

## B. DEVELOPMENT CHRONOLOGY

Append-only chronological milestone records. Full SHAs are recorded once known;
`NOT VERIFIED` marks evidence not independently confirmed.

### B.1 — Canonical Product Design Sync V1 (SE-0)
- **Purpose:** ratify the standalone Scenario Editor roadmap and Owner product
  concept (Card/Slide/Utterance/Portion model, Dialogue Workshop, Start Page/Menu
  Editors, hybrid storage).
- **Branch:** `Voyage-Scenario-Editor` (permanent product integration line).
- **Full SHA:** `5883d50238d317a386432eacabb8cff0a49eb32c` ("docs(scenario): sync
  product design and character library decisions"). Preceded by
  `5f8f07a975b612aa75995df3914b1409afa0fd48` ("docs(scenario): ratify roadmap to
  standalone editor 1.0").
- **Scope:** documentation only (`SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md`,
  `SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md`, roadmap §14).
- **Tests:** N/A (docs-only).
- **Review:** NOT VERIFIED.
- **Owner gate:** `CLOSED_AND_PUBLISHED` (roadmap §14.10).
- **Lifecycle state:** CLOSED_AND_PUBLISHED (documentation).
- **Next dependency:** SE-1 architectural closure.

### B.2 — SE-1 architectural design and contract closure
- **Purpose:** agree the authoring model direction and hybrid storage direction
  that seed SE-1 implementation slices.
- **Branch:** `Voyage-Scenario-Editor`.
- **Full SHA:** `df2fae21971878b1205599ffbbf41e7e680e620a` ("docs(scenario):
  ratify SE1 authoring and storage decisions").
- **Scope:** documentation only (`NARRATIVE_DECISIONS_v1.md` §18/§19,
  `NARRATIVE_ROADMAP.md` §14.10).
- **Tests:** N/A (docs-only).
- **Review:** NOT VERIFIED.
- **Owner gate:** OWNER_DIRECTION_AGREED (principles); technical schemas deferred
  to SE-1.1.
- **Lifecycle state:** SE-1 `ACTIVE` (roadmap §14.10); documentation baseline.
- **Next dependency:** SE-1.1 implementation.

### B.3 — OD-SE-AUTHORING-MODEL-01
- **Purpose:** authoring model `Project → connected Cards → Slides → Content
  Items / Utterances → Display Portions`; Card ≠ one SceneBody/OrderedASS;
  deterministic projection; no custom gameplay runtime.
- **Branch:** N/A (recorded in `NARRATIVE_DECISIONS_v1.md` §18).
- **Full SHA:** NOT VERIFIED as an isolated commit (part of docs commits B.1/B.2).
- **Scope:** Owner direction record, `OWNER_DIRECTION_AGREED /
  DOCUMENTED_AWAITING_INDEPENDENT_REVIEW` (2026-10-01).
- **Lifecycle state:** DOCUMENTED, deferred-to-SE-1.1.

### B.4 — OD-SE-STORAGE-CONTRACT-01
- **Purpose:** hybrid storage — W1 local JSON/media directory + P1 portable ZIP
  package; atomic save, previous-good recovery, no absolute paths, no secrets.
- **Branch:** N/A (recorded in `NARRATIVE_DECISIONS_v1.md` §19).
- **Full SHA:** NOT VERIFIED as an isolated commit (part of docs commits B.1/B.2).
- **Scope:** Owner direction record (2026-10-01).
- **Lifecycle state:** DOCUMENTED, deferred-to-SE-1.1.

### B.5 — Published SE-1 documentation baseline
- **Full SHA:** `df2fae21971878b1205599ffbbf41e7e680e620a`.
- **Note:** this is the tip of the permanent product branch `Voyage-Scenario-Editor`
  (verified locally). Remote publication state NOT VERIFIED (no network access).

### B.6 — SE-1.1 implementation (authoring identity foundation)
- **Purpose:** introduce the pure, UI-independent authoring model + validation.
- **Branch:** `feature/voyage-scenario-editor-se11-foundation-v1`.
- **Full SHA:** committed as `cdbc10ea068cc0359c28140157656cf3f1866b9e` (B.9);
  authored as untracked files before that commit.
- **Scope:** `services/scenario_authoring/` (`__init__.py`, `errors.py`,
  `model.py`, `validation.py`), `tests/unit/test_scenario_authoring_model.py`,
  `tests/unit/test_scenario_authoring_validation.py`,
  `docs/narrative/SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md`.
- **Tests:** 31 focused tests + 233 regression tests (recorded in B.8).
- **Lifecycle state:** IMPLEMENTED (locally committed).

### B.7 — Initial independent review and targeted correction
- **Review identifier:** `VOYAGE_SCENARIO_EDITOR_SE11_CORRECTION_INDEPENDENT_REVIEW_V1`.
- **Initial verdict:** C. REWORK_REQUIRED.
- **Correction report:** A. CORRECTION_READY_FOR_INDEPENDENT_REVIEW.
- **Full SHA:** NOT VERIFIED (correction was uncommitted file edits, no commit).
- **Scope:** model duplicate `choice_id` rejection, `_required`/`*_from_dict`
  consistency, string validation; write scope limited to the 3 reviewable files
  plus the 7-file SE-1.1 set.
- **Lifecycle state:** corrected, then re-reviewed (B.8).

### B.8 — Final independent review: A. PASS
- **Review identifier:** `VOYAGE_SCENARIO_EDITOR_SE11_CORRECTION_INDEPENDENT_REVIEW`.
- **Verdict:** A. PASS — 0 blocker, 0 major, 0 minor, no required corrections.
- **Evidence:** 31 focused tests passed; 233 SceneBody/ASS/StorySequence
  regression tests passed.
- **Lifecycle state:** independently verified.

### B.9 — SE-1.1 detailed local commit
- **Full SHA:** `cdbc10ea068cc0359c28140157656cf3f1866b9e`.
- **Commit task identifier:** `VOYAGE_SCENARIO_EDITOR_SE11_DETAILED_LOCAL_COMMIT_V1`.
- **Parent:** `df2fae21971878b1205599ffbbf41e7e680e620a`.
- **Scope:** exactly the 7 SE-1.1 files (1727 insertions), detailed multi-section
  commit message.
- **Review:** A. PASS (B.8).
- **Owner gate:** Owner-authorized local commit only — no merge, no push.
- **Lifecycle state:** **LOCAL_COMMITTED** — NOT integrated, NOT published.
- **Next dependency:** Owner-controlled SE-1.2 authorization (not automatic).

---

## C. IMPLEMENTED VS PLANNED

### Implemented in SE-1.1 (locally committed)

- `Project` — non-empty ordered Cards, unique card IDs, `start_card_id` resolves,
  pinned schema version.
- `Card` — unique slide IDs, unique connection IDs, identity independent of
  path/position/index; duplicate authored `choice_id` values across all Slides of
  the same Card are rejected at construction.
- `Slide` — unique content-item IDs, optional background media reference.
- `ContentItem` — exactly one of `TEXT` / `CHOICE` / `MEDIA` with its matching
  payload.
- `Utterance` — complete authoritative `text` (whitespace and line breaks
  preserved), unique speaker IDs, explicit complete Display Portion segmentation.
- `DisplayPortion` — stable ID, ordered non-overlapping `[0, len(text))` coverage,
  optional per-speaker portrait/emotion overrides; `resolve_effective_overrides`
  helper.
- Supporting model objects and validation — `MediaReference`, `SpeakerOverride`,
  `AuthoredChoice`, `ChoiceOption`, `CardConnection`, `CharacterReference`;
  construction validation in `model.py` and cross-object integrity in
  `validation.py` (`validate_project`, `is_project_consistent`); deterministic
  `project_from_dict` serialization interface.

**Evidence:** 31 focused tests passed; 233 regression tests passed; final
independent review A. PASS.

### NOT implemented (deferred — do not present as ratified contracts)

- W1 local persistence (project save/reopen).
- Autosave and unfinished-draft recovery.
- Portable ZIP package (P1 / `.vscenario`).
- Card-to-OrderedASS projection (SE-1.3).
- Ren'Py portion emission (SE-1.5).
- Character Lab `.vchar` import.
- AI-provider integration.
- Desktop Card/Slide interface and multimedia playback.

SE-1.1 technical design draft status remains:
**TECHNICAL_DRAFT / OWNER_REVIEW_REQUIRED**.

---

## D. KNOWN LIMITATIONS AND OPEN GATES

1. **Exact W1 directory layout** and per-Card file granularity — required before
   SE-1.2.
2. **P1 manifest and package specification** — manifest schema, package-version
   semantics, and `.vscenario` format are deferred.
3. **Immutable Display Portion acceptance pinning** — exact hash/pinning mechanism
   not yet defined; accepted publication metadata must eventually be immutable and
   hash-pinned.
4. **start_card / accepted-scene compatibility** — `start_card_id` alone does not
   make an arbitrary middle-of-scene Card a valid start entry.
5. **Supported cross-scene target boundaries** — unsupported cross-scene entry
   targets are not allowed; exact validation deferred.
6. **Character Library and optional Assistant separation** — Character, Character
   Media Library, and optional Character AI Assistant remain distinct; importing
   `.vchar` must not auto-activate a provider.
7. **No mandatory Story Runtime Semantics V1** — `STORY_RUNTIME_SEMANTICS_V1`
   remains `NOT REQUIRED FOR 1.0`; `OD-SE-RUNTIME-01` `NOT RATIFIED`.
8. **Cosmetic commit-quality note (blank-line-at-EOF).** The SE-1.1 staged
   whitespace check (`git diff --cached --check`) reported three `new blank line
   at EOF` warnings:

   - `docs/narrative/SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md`
   - `services/scenario_authoring/model.py`
   - `tests/unit/test_scenario_authoring_model.py`

   These warnings were **not corrected after independent review** and were
   **included in the local commit**. The staged whitespace check was **not**
   clean. This content is not altered during this documentation task.

---

## E. DOCUMENTATION NAVIGATION

All paths are relative to this file (`docs/narrative/`).

### Canonical documents (same directory)

- [`00_DOCUMENT_INDEX.md`](00_DOCUMENT_INDEX.md) — document map; read this for orientation.
- [`NARRATIVE_ROADMAP.md`](NARRATIVE_ROADMAP.md) — current roadmap; §14 (and §14.10) cover the Scenario Editor track.
- [`NARRATIVE_DECISIONS_v1.md`](NARRATIVE_DECISIONS_v1.md) — Owner decisions; §18 = OD-SE-AUTHORING-MODEL-01, §19 = OD-SE-STORAGE-CONTRACT-01.
- [`SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md`](SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md) — Owner product design concept (Card/Slide/Utterance/Portion).
- [`SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md`](SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md) — Owner addendum: Character Library / Media Library / optional AI Assistant separation.
- [`SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md`](SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md) — SE-1.1 technical design draft (`TECHNICAL_DRAFT / OWNER_REVIEW_REQUIRED`).

### Authoring source and test paths (repo root)

- [`../../services/scenario_authoring/__init__.py`](../../services/scenario_authoring/__init__.py)
- [`../../services/scenario_authoring/errors.py`](../../services/scenario_authoring/errors.py)
- [`../../services/scenario_authoring/model.py`](../../services/scenario_authoring/model.py)
- [`../../services/scenario_authoring/validation.py`](../../services/scenario_authoring/validation.py)
- [`../../tests/unit/test_scenario_authoring_model.py`](../../tests/unit/test_scenario_authoring_model.py)
- [`../../tests/unit/test_scenario_authoring_validation.py`](../../tests/unit/test_scenario_authoring_validation.py)

### Generated discovery aid (do not hand-edit)

- [`../../governance/BRANCH_WORKTREE_MAP.md`](../../governance/BRANCH_WORKTREE_MAP.md) — generated branch/worktree topology (a discovery aid, **not** a manually maintained milestone history).
- [`../../governance/BRANCH_WORKTREE_REGISTRY.json`](../../governance/BRANCH_WORKTREE_REGISTRY.json) — generated registry source; never hand-edited.

> External audit/review reports supplied only in chat are referenced here by their
> exact identifiers and verdicts (e.g. `VOYAGE_SCENARIO_EDITOR_SE11_CORRECTION_INDEPENDENT_REVIEW` → A. PASS),
> not by an invented repository file path.

---

## F. NEXT CHAT RECOVERY PROTOCOL

Copy the following into a new ChatGPT conversation to restore context without the
previous conversation history:

```text
You are resuming the Voyage Scenario Editor (SE) project. Reconstruct state from
the repository, not from memory.

1. Read docs/narrative/SCENARIO_EDITOR_PROGRESS_JOURNAL_v1.md first.
2. Follow its Documentation Navigation links to the canonical documents
   (00_DOCUMENT_INDEX.md, NARRATIVE_ROADMAP.md, NARRATIVE_DECISIONS_v1.md,
   SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md,
   SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md,
   SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md).
3. Inspect real Git state: branch, worktrees, and HEAD SHAs
   (git status, git rev-parse HEAD, git log --oneline).
   - Permanent product branch: Voyage-Scenario-Editor (worktree C:/DEV/Narrative/vne-voyage-scenario-editor).
   - Feature branch: feature/voyage-scenario-editor-se11-foundation-v1 (worktree C:/DEV/Narrative/vne-scenario-se11-foundation-v1).
4. Compare the actual Git state with the dated snapshot in section A of this journal.
5. Reconstruct the completed milestone chain from section B (SE-0 → SE-1.1 local commit).
6. Distinguish implemented (section C) from planned/deferred capabilities.
7. Preserve Owner decisions and authorization gates (OD-SE-AUTHORING-MODEL-01,
   OD-SE-STORAGE-CONTRACT-01, and the SE-1.1 technical draft status).
8. Confirm the next bounded slice before editing anything.
9. Never assume an unintegrated feature commit is already published. SE-1.1 commit
   cdbc10ea068cc0359c28140157656cf3f1866b9e is LOCAL_COMMITTED only.
10. Never automatically commit, merge, push, or change shared main.
```

---

## G. JOURNAL MAINTENANCE RULE

For every significant future milestone:

- use a small and bounded code scope;
- create a detailed Git commit message (multi-section, context-preserving);
- append verified milestone evidence to section B of this journal (append-only);
- refresh section A (CURRENT HANDOFF) with the new state;
- record exact SHAs once they are known (do not guess);
- update `00_DOCUMENT_INDEX.md` references when necessary;
- update `NARRATIVE_ROADMAP.md` only when milestone status or approved
  development direction actually changes.

**Self-referential SHA rule:** a commit cannot contain its own final SHA in its
pre-existing file content. Record a completed implementation commit in a
**subsequent** documentation update, never attempt to embed a SHA that does not
exist yet.
