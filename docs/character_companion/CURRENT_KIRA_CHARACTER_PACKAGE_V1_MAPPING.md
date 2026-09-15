# Current Kira Character Package V1 — Source Mapping

**НОВАЯ / АКТУАЛЬНАЯ KIRA**

This package is sourced from the current, **HUMAN_APPROVED** CRP acceptance
record for Kira — rebuilt after the AI-role update, tested in Character Lab,
and presently the accepted Kira Companion.

It is **NOT** sourced from `legacy-compat-v1`
(`packageHash = c2194c215effbefff76a42362e1a9adef45076b8e794dd1fb76bcf3788047ac9`).
The materializer tool never reads that package, or any file under
`accepted/` or `character_packages/` other than the three exact files named
below, and refuses to proceed (`BLOCKED_OLD_KIRA_CONTAMINATION`) if the
acceptance record it loads ever resolves to that old package identity.

This document describes the mapping only. It is not a new governance
framework — Package V1 itself, and the existing CRP acceptance mechanism,
remain the authorities for their respective parts.

---

## 1. Exact source files (CANONICAL_EOL_SOURCE_LOCK)

Tool: `tools/materialize_current_kira_package_v1.py`
(`voyage_character_platform.materialize_legacy_compat_package`, imported
from the Voyage Character Platform — never reimplemented here).

Each file is locked to an exact expected SHA-256 of its **canonical**
bytes — not its raw working-tree bytes. Canonicalization
(`_canonicalize_source_lock_bytes`) does ONLY one thing: collapse physical
CRLF (`\r\n`) to LF (`\n`). It does **not** reorder JSON, reserialize,
strip/add whitespace or indentation, normalize Unicode, touch numbers,
change the final newline, or otherwise interpret content. A bare CR byte
not immediately followed by LF is **not** treated as an equivalent
newline — it fails closed. This makes the lock reproducible across a clean
LF checkout and a Windows CRLF checkout of the exact same committed
content, while staying exactly as sensitive as a raw-byte lock to every
other kind of change.

| Repo-relative path | Expected canonical SHA-256 |
|---|---|
| `accepted/kira/ACCEPTANCE.json` | `42ce4fa0838bee25477d0f6ba24552170014088c060b50a6dd7a29de5d9fcb34` |
| `accepted/kira/source_candidate.json` | `abffecab28b50d260f440c2bd6561bcae95e7c3d52f887d7d71569f1e842188d` |
| `character_packages/kira/extensions/dimension_semantics/v1.json` | `84463aeb31f32c4b2e41c8fa64a0824b2889abeb9c3eb32315ac016da2fdda20` |

These values are mechanically derived — `sha256(canonicalize(git show
HEAD:<path>))` at commit `9d8e2162dd505e19f7a1047738b9b948776e3634` — never
invented, and independently re-derived by
`test_canonical_head_hash_matches_committed_source`.

**Corrected defect:** the first version of this lock hashed *raw* working-tree
bytes. `source_candidate.json`'s committed HEAD blob is LF-only, but a
Windows `core.autocrlf=true` checkout of that same commit can be CRLF —
Git blob content is identical either way, only the on-disk EOL
representation differs. Locking to raw bytes made the same committed Kira
source able to fail the lock purely from a clean-vs-CRLF checkout
difference. `abffecab28b50d260f440c2bd6561bcae95e7c3d52f887d7d71569f1e842188d`
(the canonical/LF-normalized value) replaces the old
`feae83e9ad70fcfc7c5e5b18ee7d384f301fcef29e3b7a228b2cfae0a0037cfc` (which was
that one checkout's raw-CRLF-bytes hash, not a portable lock). ACCEPTANCE.json
and the extension file's HEAD blobs are already LF-only, so their canonical
values are unchanged from a plain raw-byte hash.

No other file is ever read as content input. Paths are resolved against
**this repository's own root**, never a sibling worktree.

A canonical SHA-256 mismatch on any of the three files **fails closed**
(`SourceLockError`), independent of any hash found *inside* the file. A
semantic/content hash match alone is never trusted as a substitute for this
lock — see §7. The lock remains exactly as strict as before for every
non-EOL change: a changed claim, a changed acceptance reason, a changed
extension description, an added/removed JSON member, a changed `null`, a
reordered array, or an added/removed space all still change the canonical
hash and fail closed (see the *_rejected tests in
`tests/crp_authoring/test_current_kira_package_v1.py`). Only the physical
CRLF-vs-LF representation is ignored, and a bare CR (any newline
convention other than CRLF or LF) is refused rather than silently treated
as equivalent.

## 2. Acceptance identity (verified, not just read)

| Field | Expected value |
|---|---|
| `acceptance_record.acceptance_id` | `kira-accepted-package-001` |
| `acceptance_record.subject_id` | `kira` |
| `acceptance_record.package_hash` (accepted semantic hash) | `e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd` |
| `acceptance_record.decision` | `HUMAN_APPROVED` |

`source_candidate.json`'s own `package_id` must equal
`acceptance_record.package_id`, and `source_candidate.json` must pass
strict typed `CandidateCharacterPackage` rehydration
(`services.crp_authoring.candidate_rehydration.rehydrate_candidate_package`)
before anything is materialized.

## 3. Dimension-semantics extension binding

`character_packages/kira/extensions/dimension_semantics/v1.json`'s own
`target_accepted_source_hash` field must equal
`acceptance_record.package_hash` above. If it does not, materialization
fails closed — this is the "dimension extension binding" check.

## 4. Package identity

| Field | Value |
|---|---|
| `characterId` | `kira` |
| `releaseId` | `crp-import-v1` |
| `displayName` | Кира — актуальная CRP |
| `authorityClass` | `LEGACY_COMPAT` |
| `packageOrigin` | `LEGACY_IMPORT` |

**Why `LEGACY_COMPAT` / `LEGACY_IMPORT`:** this is a *technical* Package V1
authority label meaning "imported from the earlier CRP acceptance system
into the newer Package V1 mechanism." It does **not** mean "old Kira
personality" — the content is the new/actual, HUMAN_APPROVED Kira. No
Character Platform `ACCEPTED_RELEASE` acceptance is invented: the package
contains no `provenance/acceptance.json`, no `acceptedAggregateHash`, no
`acceptanceRecordHash`. The original HUMAN_APPROVED CRP acceptance record is
preserved, content-faithful, as source evidence (§5).

## 5. Supplemental source files (content-faithful canonical preservation)

Materialized via the Voyage Character Platform's optional, additive
`supplemental_json` mechanism (`SupplementalJsonFile`) — same canonical
JSON serializer, same manifest/hash/collision/path-safety rules as every
other Package V1 file; nothing new invented.

**Terminology note:** preservation here is **content-faithful canonical
preservation**, not raw byte-faithful preservation. Each source file is
parsed once, and the exact *parsed JSON value* — semantically/deeply equal
to the source, including every `null`, empty object/array, and array
ordering — is re-emitted through the Character Platform's deterministic
Package V1 canonical JSON serializer. The embedded file's raw bytes are
therefore not asserted to equal the original filesystem source's raw bytes
(formatting/line-endings differ); what is asserted and tested is that the
embedded *parsed content* is exactly, deeply equal to the source's parsed
content (`embedded == json.loads(original_source_bytes)`).

| Package path | Content |
|---|---|
| `provenance/source_candidate.json` | The complete, content-faithful `source_candidate.json` Candidate: every claim, contradiction, unknown, `null`, empty object/array, and array ordering preserved exactly (deep JSON equality), canonically re-serialized. `status` remains `DRAFT` (never rewritten to `HUMAN_APPROVED` — that is a separate, package-level acceptance concept). |
| `provenance/source_acceptance.json` | The complete, content-faithful `ACCEPTANCE.json` acceptance record (deep JSON equality; canonically re-serialized). |
| `extensions/dimension_semantics/v1.json` | The complete, content-faithful dimension-semantics extension (deep JSON equality; canonically re-serialized). |

## 6. Deterministic domain mapping

`domains/*.json` are a **projection**, not a rewrite: each required Package
V1 domain's `content.structured.crpV1` embeds the exact source JSON
sub-object(s), content-faithful (deep JSON equality, no re-derivation of
claim content).

| Package V1 domain | `structured.crpV1.*` source | `contentState` |
|---|---|---|
| `core_identity` | `identity_biography_candidate` | `POPULATED` |
| `psychology` | `psychology_candidate`, `behavior_candidate` | `POPULATED` |
| `speech` | `voice_candidate` | `POPULATED` |
| `relationships` | `relationships_candidate` | `POPULATED` |
| `interaction_boundaries` | `boundaries_candidate`, `intimacy_candidate` | `POPULATED` |
| `visual_identity` | *(none)* | `EXPLICITLY_EMPTY` |

`visual_identity: EXPLICITLY_EMPTY` does **not** mean Kira has no
appearance — it means this accepted CRP source does not contain a complete,
approved visual-identity contract. No production snapshot, portrait, React
image, Character Canon image, or legacy package image is imported.

Every claim and unknown in `source_candidate.json` carries its own
`target_module_or_layer` (e.g. `identity_biography.age`,
`boundaries.control`). Routing is a fixed, closed prefix table:

```
identity_biography -> core_identity
psychology, behavior -> psychology
voice -> speech
relationships -> relationships
boundaries, intimacy -> interaction_boundaries
```

Contradictions carry no `target_module_or_layer` of their own; they are
routed by resolving **every** referenced `claim_id` through the same table.
If a contradiction's claims resolve to more than one domain, or any
referenced `claim_id` cannot be found, materialization fails closed
(`AmbiguousRoutingError`) rather than guessing. For the current source, all
5 contradictions and 14 unknowns route unambiguously.

`provenance/provenance.json` carries one `ProvenanceRecord` per source
field (7 total: `identity_biography_candidate`, `psychology_candidate`,
`behavior_candidate`, `voice_candidate`, `relationships_candidate`,
`boundaries_candidate`, `intimacy_candidate`), each pointing at
`provenance/source_candidate.json` with the field's exact source SHA-256,
`authoringMethod = CRP` (the content *was* authored via the CRP pipeline;
this is independent of the package-level `LEGACY_COMPAT`/`LEGACY_IMPORT`
labels in §4, which describe only how it entered Package V1).

## 7. Why not `ACCEPTED_RELEASE`

Kira is HUMAN_APPROVED in CRP, but this tool does not invent a Character
Platform `ACCEPTED_RELEASE` acceptance — Package V1 authority here is
`LEGACY_COMPAT`/`LEGACY_IMPORT` (§4), and the CRP hash-algorithm
completeness gap is a separate, future task (not fixed here). This slice
compensates using: the exact source-file SHA locks (§1), the existing
accepted semantic hash + dimension-extension binding (§2–3), complete
package source preservation (§5), and full package-roundtrip proof (tests).

## 8. Memory boundary

Only **authored** content is ever read or packaged: biography, psychology,
relationship history, boundaries, `seed_memory_candidate`. The tool never
searches for or reads `runtime_memory.sqlite3`, `runtime_state.sqlite3`,
conversation/session history, consolidated runtime memory, promoted runtime
facts, relationship deltas, current trust/stress runtime state, user
profiles, provider settings, credentials, or image-job history.

## 9. Old-Kira non-source rule

The materializer never opens, globs, or scans `legacy-compat-v1` or any
file whose resolved acceptance `package_hash` equals
`c2194c215effbefff76a42362e1a9adef45076b8e794dd1fb76bcf3788047ac9`. If the
loaded acceptance record ever resolves to that identity, materialization
fails closed before any package content is built.

## 10. Roundtrip requirements

A materialized package must, read *only* from the package directory
(original source access blocked during recovery):

- rehydrate the exact same typed `CandidateCharacterPackage`
  (`rehydrate_candidate_package` on `provenance/source_candidate.json`);
- recover `provenance/source_acceptance.json` and
  `extensions/dimension_semantics/v1.json` deep-equal, as parsed JSON
  (content-faithful, not raw-byte-equal), to the originals;
- render an *exactly* equal Accepted Character grounding block
  (`services.character_lab.grounding.render_accepted_grounding`) to the
  one rendered directly from the live source — content equality, not just
  length;
- verify identically under both the Character Platform's own
  `verify_materialized_package` and the Companion side's independent
  `services.character_companion.character_import.verify_character_package_v1`;
- materialize byte-identically on repeated runs (twin materialization; no
  timestamps in package identity).

See `tests/crp_authoring/test_current_kira_package_v1.py` for the executable
proof of every item above.

## 11. Output safety

`materialize_current_kira_package_v1(destination, ...)` requires an
explicit `destination` with no default, and refuses to write under this
repository's own `accepted/`, `character_packages/`, or at the repository
root. Tests materialize only inside pytest `tmp_path`. This tool must not
be imported by Companion runtime, catalog, session, or memory code — it is
an authoring/build-time tool only.

## 12. Not authorized by this document

Producing this mapping, or a successful test run against it, does **not**
authorize:

- a persistent, real Kira Character Package V1 (none has been created by
  this work — all materialization stays inside auto-cleaned temp
  directories);
- installation, import, or runtime activation of any Kira package;
- any change to Companion runtime, catalog, session, or memory code;
- any change to the current owner-approved Candidate_07 / release-readiness
  criteria referenced elsewhere in this project.
