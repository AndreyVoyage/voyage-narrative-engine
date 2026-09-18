# NARRATIVE / VNE Development Topology

GENERATED FROM: live Git/worktree facts (`git worktree list --porcelain`, `git merge-base --is-ancestor`) + `governance/BRANCH_WORKTREE_REGISTRY.json` metadata.

This file is NOT an independent source of truth. Regenerate with `py tools/voyage_branch_worktree_map.py` after any registry change; do not hand-edit.

Authoritative `main` @ `80dba618ee260979453cdde0e8a489ad1dfff54f`
(ref: `refs/remotes/origin/main`)

> Local refs/heads/main (checked out in worktree vne-n9-pac-merge) is STALE relative to this authoritative SHA by 2 commits (3ae0caa, 80dba61) -- it was never fetched/merged locally after those commits were pushed directly to origin/main. refs/remotes/origin/main is correct and current because `git push` updates the local remote-tracking ref automatically. Use refs/remotes/origin/main or this explicit sha for lineage checks; do not use refs/heads/main.

---

## Known / governed branches

### `feature/voyage-branch-worktree-registry-v1` <<< YOU ARE HERE

- worktree: `C:/DEV/Narrative/vne-voyage-framework-update-2026-09-v1`
- tip: `80dba618` (`80dba618ee260979453cdde0e8a489ad1dfff54f`)
- base: `main` @ `80dba618`
- return target: `main`
- depends on: `None`
- integration policy: `FF_ONLY`
- lifecycle: **ACTIVE**
- lineage: **CURRENT**
- cleanup candidate: **False**
- purpose: VOYAGE_BRANCH_WORKTREE_REGISTRY_V1 -- implement and populate the first operational branch/worktree registry and generated topology map.
- notes: Reused worktree; branched from feature/voyage-framework-update-2026-09-v1 at its exact published tip (80dba618) rather than creating a new worktree, per policy §1/§2.

### `feature/voyage-framework-update-2026-09-v1`

- worktree: `(none -- no worktree currently checked out)`
- tip: `80dba618` (`80dba618ee260979453cdde0e8a489ad1dfff54f`)
- base: `main` @ `3ae0caa3`
- return target: `main`
- depends on: `None`
- integration policy: `FF_ONLY`
- lifecycle: **INTEGRATED**
- lineage: **INTEGRATED**
- cleanup candidate: **True**
- purpose: Established OD-GOV-BRANCH-01 (Branch Lineage, Task Batching & Publication Freshness Policy v1) and registered it in governance/DECISION_REGISTER.md.
- notes: Published to origin/main as commit 80dba618. The worktree that held this branch (vne-voyage-framework-update-2026-09-v1) was reused for the current task and switched to feature/voyage-branch-worktree-registry-v1; this branch now has no worktree checked out but still exists as a local branch. Local branch deletion (git branch -d) is a cleanup candidate ONLY -- not performed in this task.

### `feature/kira-real-canon-visual-wiring-v1`

- worktree: `C:/DEV/Narrative/vne-kira-real-canon-visual-wiring-v1`
- tip: `3ae0caa3` (`3ae0caa32c887f726ac9938987c18baed8d539ad`)
- base: `main` @ `3d96d136`
- return target: `main`
- depends on: `None`
- integration policy: `FF_ONLY`
- lifecycle: **INTEGRATED**
- lineage: **INTEGRATED**
- cleanup candidate: **True**
- purpose: Wired the real, approved external Character Canon bridge (services.character_canon_bridge.read_character_canon) into the current character_visual_conditioning generation path via a new services/scene_image_production application service. Proven against the real KIRA canon.
- notes: Published to origin/main as commit 3ae0caa (verified ancestor of the current authoritative target 80dba618 -- see lineage_evidence in the generated map). Worktree and branch are both cleanup candidates once the owner confirms nothing further is needed from this exact worktree state.

### `feature/kira-package-v1-visual-binding-s1`

- worktree: `C:/DEV/Narrative/vne-kira-package-v1-visual-binding-s1`
- tip: `46464d3a` (`46464d3a3ef759a7d0b73263129880683087a1c1`)
- base: `feature/crp-mvp-v1` @ `e0485ca6`
- return target: `feature/crp-mvp-v1`
- depends on: `None`
- integration policy: `None`
- lifecycle: **SUPERSEDED**
- lineage: **DIVERGED**
- cleanup candidate: **False**
- purpose: Implemented a Package V1 visual_identity binding (services/character_companion, services/character_runtime, services/crp_authoring) for KIRA, on top of the feature/crp-mvp-v1 architecture line.
- notes: Technically correct, tested, and independently reviewed, but its entire target subsystem (character_companion / character_runtime / crp_authoring) was removed and replaced on the authoritative line by character_visual_conditioning / reference_library / character_canon_bridge before this candidate could integrate. Confirmed by governance/BRANCH_LINEAGE_AND_TASK_BATCHING_POLICY_v1.md Case 2. NOT a cleanup candidate: retained intact as design/reference evidence per policy §7. Do not integrate, cherry-pick, or delete.

### `feature/crp-mvp-v1`

- worktree: `C:/DEV/Narrative/vne-crp-mvp-v1`
- tip: `e0485ca6` (`e0485ca610aac35d6c5773ded8df7723c981bf27`)
- base: `None` @ `n/a`
- return target: `None`
- depends on: `None`
- integration policy: `None`
- lifecycle: **SUPERSEDED**
- lineage: **DIVERGED**
- cleanup candidate: **False**
- purpose: The old Character Companion / Package V1 / CRP-authoring architecture line (S8A-S8C2, character_companion.package_runtime, crp_authoring). Superseded by the current character_visual_conditioning / reference_library / character_canon_bridge line on main.
- notes: PROPOSED SUPERSEDED, not final: this worktree also physically contains docs/workflows/VOYAGE_FRAMEWORK_UPDATE_BATCH_2026_09_BRANCH_AND_FAST_LANE_LESSONS_V1.md, an UNTRACKED historical source-evidence file whose accepted content has since been formalized into governance/BRANCH_LINEAGE_AND_TASK_BATCHING_POLICY_v1.md on the current line (see governance doc §0 and the generated map's preservation note). Its own AGENTS.md, docs/workflows/VOYAGE_REVERSIBLE_FAST_LANE_V1.md, VOYAGE_AI_QA_AND_EVIDENCE_POLICY_V1.md, and VOYAGE_FAST_LANE_JOURNAL_V1.md also exist only on this line and have not been individually reconciled item-by-item against current governance beyond what OD-GOV-BRANCH-01 already covers. This worktree also hosts several OTHER feature branches from the same architecture line (e.g. feature/s8b-character-selection-session-pinning-v1, feature/s8c1-pinned-text-runtime-wiring-v1, feature/kira-package-runtime-definition-v1) not individually classified here. Do not delete this worktree or its untracked source file until an owner-reviewed cleanup task confirms nothing further needs extracting from it.

---

## Other registered worktrees (owner review required)

The branches above are the only ones with recorded governance metadata (base/return target, lifecycle, purpose). Every other currently registered worktree is listed below with Git-derived facts only -- `lifecycle_status: null`, `classification_state: OWNER_REVIEW_REQUIRED` for all of them. `lineage` here is a bare topology fact (is the branch tip an ancestor of, or ahead of, the authoritative target?), not an architectural judgement -- per policy, topology distance alone must never be read as an architectural-divergence verdict.

| worktree | branch | tip | lineage (topology only) |
|---|---|---|---|
| `C:/DEV/Narrative/vne-adapter-v41-clean` | `adapter/v4.1-isolated` | `113076b7` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-aside-v2-slice1-closeout` | `docs/aside-v2-slice1-closeout` | `2af11fca` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-decisions` | `docs/aside-v2-slice2-owner-decisions` | `69a3cee2` | INTEGRATED |
| `C:/DEV/Narrative/vne-crp-mvp-spec-v1` | `docs/crp-mvp-spec-v1` | `c2ba68ac` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-crp-vnext-ratification` | `docs/crp-vnext-ratification` | `d025642a` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-n7-docs-reconciliation` | `docs/n7-canonical-status-reconciliation` | `a75c738c` | INTEGRATED |
| `C:/DEV/Narrative/vne-od-gov-fast-01-canonicalization` | `docs/od-gov-fast-01-canonicalization` | `6574ef01` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-persona-context-routing-decisions` | `docs/persona-context-routing-decisions` | `4cb1fb83` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-sva-mr1-manual-scene-reference-input-v0` | `docs/sva-mr1-manual-scene-reference-input-v0-ratification` | `cb437193` | INTEGRATED |
| `C:/DEV/Narrative/vne-sva-rl-reference-library-controlled-import-v0` | `docs/sva-rl-reference-library-controlled-import-ratification` | `5e7251b1` | INTEGRATED |
| `C:/DEV/Narrative/vne-approved-generated-image-asset-gate-v0` | `feature/approved-generated-image-asset-gate-v0` | `ad5fa2d6` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-context-return-recovery` | `feature/aside-v2-s2-context-return-recovery` | `54cae9a5` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-multiturn-persistence-fix` | `feature/aside-v2-s2-multiturn-persistence-fix` | `cf42f658` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-scene-context-correction` | `feature/aside-v2-scene-context-correction` | `9735d712` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-stage0-preflight` | `feature/aside-v2-slice1-memory-identity-safety` | `86bb5f7b` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-correction` | `feature/aside-v2-slice2-sqlite-correction` | `54cae9a5` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-fts5` | `feature/aside-v2-slice2-sqlite-fts5` | `4c5d21cd` | INTEGRATED |
| `C:/DEV/Narrative/vne-ass-ordered-flow-renpy-export-v1` | `feature/ass-ordered-flow-renpy-export-v1` | `a260c827` | INTEGRATED |
| `C:/DEV/Narrative/vne-ass-ordered-flow-renpy-export-v1-canonical-publish` | `feature/ass-ordered-flow-renpy-export-v1-canonical-publish` | `1d3efb74` | INTEGRATED |
| `C:/DEV/Narrative/vne-ass-ordered-flow-renpy-export-v1-project-integration` | `feature/ass-ordered-flow-renpy-export-v1-project-integration` | `a445ab59` | INTEGRATED |
| `C:/DEV/Narrative/vne-ass-v0-core` | `feature/ass-v0-core` | `653840a8` | INTEGRATED |
| `C:/DEV/Narrative/vne-authoring-media-real-e2e-pilot-v0` | `feature/authoring-media-real-e2e-pilot-v0` | `e0af9271` | INTEGRATED |
| `C:/DEV/Narrative/vne-b4-kira-sergey-generation-v1` | `feature/b4-kira-sergey-two-character-generation-v1` | `dab283d1` | INTEGRATED |
| `C:/DEV/Narrative/vne-b4-rc2-reference-bundle-v0` | `feature/b4-rc2-generic-reference-bundle-v0` | `c2d51bb0` | INTEGRATED |
| `C:/DEV/Narrative/vne-b4-rc3-conditioned-provider-v0` | `feature/b4-rc3-conditioned-provider-attachment-v0` | `17ea8c6b` | INTEGRATED |
| `C:/DEV/Narrative/vne-b4-rc4s-reference-selection-v0` | `feature/b4-rc4s-explicit-reference-selection-v0` | `75698dce` | INTEGRATED |
| `C:/DEV/Narrative/vne-b4-rc5-conditioned-live-retry-v2` | `feature/b4-rc5-conditioned-live-retry-v2` | `75698dce` | INTEGRATED |
| `C:/DEV/Narrative/vne-c4-status-eligibility-decoupling` | `feature/c4-status-eligibility-decoupling` | `028456fa` | INTEGRATED |
| `C:/DEV/Narrative/vne-canon-status-semantics-alignment-v0` | `feature/canon-status-semantics-alignment-v0` | `8bbd833e` | INTEGRATED |
| `C:/DEV/Narrative/vne-character-canon-read-bridge-v0` | `feature/character-canon-read-bridge-v0` | `e76ef381` | INTEGRATED |
| `C:/DEV/Narrative/vne-character-visual-reference-conditioning-v0` | `feature/character-visual-reference-conditioning-v0` | `62750647` | INTEGRATED |
| `C:/DEV/Narrative/vne-cis-kira-pilot` | `feature/cis-kira-pilot` | `5959048f` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-crp-anthropic-dialogue-v1-s1` | `feature/companion-anthropic-dialogue-v1-s1` | `bf2d0d94` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-companion-character-package-importer-v1` | `feature/companion-character-package-importer-v1` | `20225436` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-companion-character-package-management-v1` | `feature/companion-character-package-management-v1` | `9d8e2162` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-current-kira-package-v1` | `feature/current-kira-package-v1` | `87e730d7` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-editor-acceptance-workflow-v1` | `feature/editor-acceptance-workflow-v1` | `54fe7209` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-application-service-v1` | `feature/editor-application-service-v1` | `968b6d0e` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-draft-workspace-v1` | `feature/editor-draft-workspace-v1` | `68fe8669` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-m5-real-authoring-proof-v1` | `feature/editor-m5-real-authoring-proof-v1` | `3d96d136` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-start-new-revision-v1` | `feature/editor-start-new-revision-v1` | `7cd0efeb` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-ui-dependency-v1` | `feature/editor-ui-dependency-v1` | `9342d6d7` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-ui-shell-v1` | `feature/editor-ui-shell-v1` | `da3ba77f` | INTEGRATED |
| `C:/DEV/Narrative/vne-editor-validation-ux-v1` | `feature/editor-validation-ux-v1` | `22993da1` | INTEGRATED |
| `C:/DEV/Narrative/vne-c4-u-play-v0` | `feature/first-playable-visual-scene-v0` | `381bc68f` | INTEGRATED |
| `C:/DEV/Narrative/vne-c4-u-scene-consumption-v0` | `feature/first-production-scene-asset-consumption-v0` | `9929926f` | INTEGRATED |
| `C:/DEV/Narrative/vne-first-real-canonical-runtime-proof-v1` | `feature/first-real-canonical-runtime-proof-v1` | `1d6eef13` | INTEGRATED |
| `C:/DEV/Narrative/vne-first-real-orderedass-bootstrap-v1` | `feature/first-real-orderedass-bootstrap-v1` | `0441aa5c` | INTEGRATED |
| `C:/DEV/Narrative/vne-first-real-player-reachability-v1` | `feature/first-real-player-reachability-v1` | `da072d58` | INTEGRATED |
| `C:/DEV/Narrative/vne-c4-u-emit-v0` | `feature/first-renpy-visual-emission-v0` | `fe6abfa8` | INTEGRATED |
| `C:/DEV/Narrative/vne-generated-image-review-approval-v0` | `feature/generated-image-review-approval-v0` | `15037ed7` | INTEGRATED |
| `C:/DEV/Narrative/vne-gym-location-canon-v0` | `feature/gym-location-canon-v0` | `dab283d1` | INTEGRATED |
| `C:/DEV/Narrative/vne-image-provider-boundary-v0` | `feature/image-provider-boundary-v0` | `1b2d6e8e` | INTEGRATED |
| `C:/DEV/Narrative/vne-kira-existing-candidate-safe-import-registration` | `feature/kira-existing-candidate-safe-import-registration` | `246ab851` | INTEGRATED |
| `C:/DEV/Narrative/vne-kira-package-runtime-definition-v1` | `feature/kira-package-runtime-definition-v1` | `f4965cd0` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-location-canon-v0` | `feature/location-canon-v0` | `d568baf6` | INTEGRATED |
| `C:/DEV/Narrative/vne-mediaplan-v0` | `feature/mediaplan-v0` | `6907bfb1` | INTEGRATED |
| `C:/DEV/Narrative/vne-n3-story-runtime-renpy` | `feature/n3-story-runtime-renpy-adapter` | `015f5312` | INTEGRATED |
| `C:/DEV/Narrative/voyage-narrative-engine` | `feature/n9-pac-v0` | `653f52ff` | INTEGRATED |
| `C:/DEV/Narrative/vne-orderedass-canonical-store-v1` | `feature/orderedass-canonical-store-v1` | `9fb553f7` | INTEGRATED |
| `C:/DEV/Narrative/vne-orderedass-multibranch-control-flow-v1` | `feature/orderedass-multibranch-control-flow-v1` | `7dd5382c` | INTEGRATED |
| `C:/DEV/Narrative/vne-player-shell-splash-main-menu` | `feature/player-shell-splash-main-menu` | `41739249` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-c4-u-bind-runtime-resolver-v0` | `feature/production-media-asset-binding-runtime-resolver-v0` | `d42c8ad1` | INTEGRATED |
| `C:/DEV/Narrative/vne-project-accepted-orderedass-batch-v1` | `feature/project-accepted-orderedass-batch-v1` | `7407c3c5` | INTEGRATED |
| `C:/DEV/Narrative/vne-prompt-composer-v0` | `feature/prompt-composer-v0` | `2bec791f` | INTEGRATED |
| `C:/DEV/Narrative/vne-reference-bundle-prompt-alias-v0` | `feature/reference-bundle-prompt-alias-v0` | `4624790c` | INTEGRATED |
| `C:/DEV/Narrative/vne-reference-library-to-reference-bundle-adapter-v0` | `feature/reference-library-to-reference-bundle-adapter-v0` | `93bdadfe` | INTEGRATED |
| `C:/DEV/Narrative/vne-c4-u-name-v0` | `feature/renpy-8-5-auto-image-name-compat` | `2a2f7a2b` | INTEGRATED |
| `C:/DEV/Narrative/vne-rn-deepseek` | `feature/rn-aside-cloud-deepseek` | `6fadc23f` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-rn-aside-runtime-context` | `feature/rn-aside-runtime-context-correction-v1` | `9b00ede0` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-rn-aside-scene-context` | `feature/rn-aside-scene-context` | `161b41b4` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-rn-auto-01` | `feature/rn-auto-01-story-state-dev-overlay` | `41b794c2` | INTEGRATED |
| `C:/DEV/Narrative/vne-rn-auto-02` | `feature/rn-auto-02-aside-scroll-composer` | `c163eb68` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-s8b-character-selection-session-pinning-v1` | `feature/s8b-character-selection-session-pinning-v1` | `736e1b85` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-s8b2-character-definition-memory-state-namespace-v1` | `feature/s8b2-character-definition-memory-state-namespace-v1` | `71850c15` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-s8c1-pinned-text-runtime-wiring-v1` | `feature/s8c1-pinned-text-runtime-wiring-v1` | `48443aa4` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-s8c2-pinned-coauthor-context-enablement-v1` | `feature/s8c2-pinned-coauthor-context-enablement-v1` | `e0485ca6` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-scene-aware-reference-selection-v0` | `feature/scene-aware-reference-selection-v0` | `b375ecad` | INTEGRATED |
| `C:/DEV/Narrative/vne-scene-body-ordered-events-v1` | `feature/scene-body-ordered-events-v1` | `a85871b5` | INTEGRATED |
| `C:/DEV/Narrative/vne-scene-editor-domain-operations-v1` | `feature/scene-editor-domain-operations-v1` | `42b1443c` | INTEGRATED |
| `C:/DEV/Narrative/vne-scene-interpretation-artifact-v0` | `feature/scene-interpretation-artifact-v0` | `fd9c9e17` | INTEGRATED |
| `C:/DEV/Narrative/vne-scene-text-to-still-plan-v0` | `feature/scene-text-to-still-plan-v0` | `296e080e` | INTEGRATED |
| `C:/DEV/Narrative/vne-second-real-orderedass-scene-v1` | `feature/second-real-orderedass-scene-v1` | `14a3eb97` | INTEGRATED |
| `C:/DEV/Narrative/vne-sva-rl2-controlled-reference-import-v0` | `feature/sva-rl2-controlled-reference-import-v0` | `f708f21c` | INTEGRATED |
| `C:/DEV/Narrative/vne-third-real-multibranch-scene-v1` | `feature/third-real-multibranch-scene-v1` | `2abe76b4` | INTEGRATED |
| `C:/DEV/Narrative/vne-visual-asset-registry-v0` | `feature/visual-asset-registry-v0` | `732a00b5` | INTEGRATED |
| `C:/DEV/Narrative/vne-workspace-domain-foundation-v1` | `feature/workspace-domain-foundation-v1` | `f875ab0b` | INTEGRATED |
| `C:/DEV/Narrative/vne-authority-json-lf-fix` | `fix/authoring-authority-json-lf` | `4a96de79` | INTEGRATED |
| `C:/DEV/Narrative/vne-nika-fixture-fix` | `fix/nika-fixture-reproducibility` | `88baaede` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-pac-level-none-projection-fix` | `fix/pac-level-none-projection-contract` | `1ab481e0` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-real-user-trial` | `fix/pac-real-user-trial` | `321c30be` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice1-integration` | `integration/aside-v2-slice1-with-docs` | `0895b37d` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-controlled-merge` | `integration/aside-v2-slice2-controlled-merge` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-integration-trial` | `integration/aside-v2-slice2-trial` | `95426167` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-integration-trial-02` | `integration/aside-v2-slice2-trial-02` | `39472967` | INTEGRATED |
| `C:/DEV/Narrative/vne-crp-mvp-spec-main-integration` | `integration/crp-mvp-spec-v1-main` | `3988fb16` | INTEGRATED |
| `C:/DEV/Narrative/vne-crp-vnext-main-integration` | `integration/crp-vnext-ratification-main` | `cedbf0a6` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-level-none-merge-execution` | `integration/pac-level-none-projection-merge` | `39472967` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-merge-execution` | `integration/pac-real-user-trial-merge` | `95426167` | INTEGRATED |
| `C:/DEV/Narrative/vne-rn-aside-integration` | `integration/rn-aside-deepseek` | `0733f79d` | INTEGRATED |
| `C:/DEV/Narrative/vne-n9-pac-merge` | `main` | `3d96d136` | INTEGRATED |
| `C:/DEV/Narrative/vne-overnight-rn-workflow` | `overnight/rn-workflow-phase2` | `3f615c9d` | INTEGRATED |
| `C:/DEV/Narrative/vne-overnight-rn17-source` | `overnight/rn17-source` | `8c752c82` | INTEGRATED |
| `C:/DEV/Narrative/vne-auto-rn18-night` | `overnight/rn18-auto` | `03bb37e7` | INTEGRATED |
| `C:/DEV/Narrative/vne-auto-rn19-night` | `overnight/rn19-auto` | `12057ecf` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-level-none-merge-candidate` | `preflight/pac-level-none-fix-merge` | `95426167` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-merge-preflight` | `preflight/pac-real-user-trial-merge` | `69a3cee2` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-live-memory-api` | `qa/aside-v2-s2-live-memory-api` | `7f994f1b` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-real-kira-memory` | `qa/aside-v2-s2-real-kira-memory` | `54cae9a5` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-sqlite-fresh-checkout` | `qa/aside-v2-s2-sqlite-fresh-checkout` | `7f994f1b` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-s2-tls-ca-independent-qa` | `qa/aside-v2-s2-tls-ca-independent` | `7f994f1b` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-live-qa` | `qa/aside-v2-slice2-live-renpy` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-renpy-native-abi-probe` | `qa/aside-v2-slice2-renpy-native-abi-probe` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-renpy-sqlite-audit` | `qa/aside-v2-slice2-renpy-sqlite-audit` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-renpy-sqlite-packaging-preflight` | `qa/aside-v2-slice2-renpy-sqlite-packaging-preflight` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-renpy-sqlite-source-research` | `qa/aside-v2-slice2-renpy-sqlite-source-research` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-correction-qa` | `qa/aside-v2-slice2-sqlite-correction-independent` | `afa64d3a` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-final-qa` | `qa/aside-v2-slice2-sqlite-final` | `661c3b66` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-live-qa-r2` | `qa/aside-v2-slice2-sqlite-live-renpy-r2` | `661c3b66` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-live-qa-r3` | `qa/aside-v2-slice2-sqlite-live-renpy-r3` | `661c3b66` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-live-qa-r4` | `qa/aside-v2-slice2-sqlite-live-renpy-r4` | `661c3b66` | INTEGRATED |
| `C:/DEV/Narrative/vne-aside-v2-slice2-sqlite-live-qa-r5` | `qa/aside-v2-slice2-sqlite-live-renpy-r5` | `661c3b66` | INTEGRATED |
| `C:/DEV/Narrative/vne-pac-trial-02` | `trial/pac-kira-u2a-scene-02` | `bab7b5a1` | TOPOLOGY_UNCLASSIFIED |
| `C:/DEV/Narrative/vne-cis-kira-pilot-preflight` | *(detached)* | `afa64d3a` | n/a (detached) |
| `C:/DEV/Narrative/vne-pac-level-none-preflight-candidate` | *(detached)* | `1ab481e0` | n/a (detached) |
| `C:/DEV/Narrative/vne-pac-level-none-preflight-main` | *(detached)* | `95426167` | n/a (detached) |
| `C:/DEV/Narrative/vne-pac-main-baseline-qa` | *(detached)* | `69a3cee2` | n/a (detached) |
| `C:/DEV/Narrative/vne-persona-context-routing-audit` | *(detached)* | `afa64d3a` | n/a (detached) |
| `C:/DEV/Narrative/vne-rkr-role-audit` | *(detached)* | `afa64d3a` | n/a (detached) |

Total other worktrees: 129 (101 INTEGRATED, 22 TOPOLOGY_UNCLASSIFIED, 6 detached). All require owner review before any lifecycle/cleanup classification is assigned.

---

## Cleanup candidates (identification only -- nothing deleted)

- `feature/voyage-framework-update-2026-09-v1` (worktree: `none`) -- lifecycle INTEGRATED. Published to origin/main as commit 80dba618. The worktree that held this branch (vne-voyage-framework-update-2026-09-v1) was reused for the current task and switched to feature/voyage-branch-worktree-registry-v1; this branch now has no worktree checked out but still exists as a local branch. Local branch deletion (git branch -d) is a cleanup candidate ONLY -- not performed in this task.
- `feature/kira-real-canon-visual-wiring-v1` (worktree: `C:/DEV/Narrative/vne-kira-real-canon-visual-wiring-v1`) -- lifecycle INTEGRATED. Published to origin/main as commit 3ae0caa (verified ancestor of the current authoritative target 80dba618 -- see lineage_evidence in the generated map). Worktree and branch are both cleanup candidates once the owner confirms nothing further is needed from this exact worktree state.

No `git worktree remove`, `git worktree prune`, `git branch -d/-D`, `git reset`, or `git clean` was performed by this tool or the task that generated this map. Cleanup requires a separate, explicitly owner-reviewed task.
