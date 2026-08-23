# CRP Slice 10 — Kira Dataset Freeze (v1)

> STATUS: **OWNER_RATIFIED_FROZEN**
> KIRA_DATASET_FREEZE v1 is owner-byte-ratified and frozen.

## 1. Partition model

| Partition | Meaning | Reconstruction visibility |
|-----------|---------|----------------------------|
| A | Owner-authored reconstruction evidence | **YES** |
| B | Hidden evaluation (scenarios + owner reference answers) | NO |
| C | Legacy Kira benchmark metadata only | NO |
| root manifest | Control plane only | NO |

- **A** is the only source that may become `SourceEvidence` for CRP
  reconstruction.
- **B** is NEVER copied, paraphrased, summarized, or embedded into A; it must
  never become `SourceEvidence`.
- **C** holds only pinned Git locators + independent SHA-256 of legacy bytes;
  it contains no copied substantive legacy content.
- The root manifest is integrity/control metadata only, never evidence.

## 2. A — owner reconstruction evidence

- `A_AUTHORING/OWNER_AUTHORED_KIRA.md` — readable owner-ratified frozen
  compilation.
- `A_AUTHORING/OWNER_AUTHORED_KIRA.normalized.json` — deterministic normalized
  payload (sections of atomic owner facts) that drives snapshot generation.
- `A_AUTHORING/SOURCE_EVIDENCE_SNAPSHOT.json` — the generated A-only
  `SourceEvidence` snapshot (see helper `write_freeze_artifacts`).

Evidence granularity: one `kira-a-NNNN` record per normalized section, with a
deterministic `content_hash` (canonical JSON hash of that section's facts list)
and a `content_ref` pinned inside `A_AUTHORING`.

## 3. B — hidden evaluation

Stable IDs `kira-b-001 … kira-b-008`.

- `B_HIDDEN_EVALUATION/SCENARIOS.json` — scenario prompts only.
- `B_HIDDEN_EVALUATION/OWNER_REFERENCE_ANSWERS.json` — reference answers only.

**CRITICAL:** no `SourceEvidence` object may be derived from B. The freeze
verifier never materializes B into the returned authoring projection.

## 4. C — legacy benchmark metadata

- `C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json` — pinned Git tree/blob SHA-1
  locators, known size, and independent SHA-256 of canonical (LF) blob/tree
  content. No substantive legacy content is copied.

## 5. Deterministic hashes

- Canonical JSON: UTF-8, `ensure_ascii=False`, sorted keys, compact separators
  `(",", ":")`, non-finite float rejection.
- File artifacts: SHA-256 over exact bytes (with byte size).
- `a_snapshot_sha256` covers the normalized-payload file hash + ordered record
  identity/content hashes.
- `root_sha256` is the canonical hash of the manifest with `root_sha256` omitted
  (non-recursive self-hash; the manifest never lists itself as an artifact).

## 6. Frozen status

`KIRA_DATASET_FREEZE.manifest.json` carries
`status = "OWNER_RATIFIED_FROZEN"`.

KIRA_DATASET_FREEZE v1 is owner-byte-ratified and immutable.

## 7. A-only projection

`load_a_projection(fixture_root, manifest_rel)` verifies the manifest (artifact
hashes, root hash, A snapshot hash) and returns only A evidence + payloads. B,
C, and the root manifest data are structurally excluded.

## 8. Knowledge policy

The manifest's `knowledge_policy` stipulates:

- `allowed_kb_refs = []`
- `forbidden_refs` includes B/C/root-manifest fixture paths, `personas/kira/**`,
  and `personas/KIRA_MODULE_v15.json`.

`validate_freeze_knowledge_policy(manifest)` enforces this structurally. The
generic `KnowledgeProfile` implementation is unchanged.

## 9. No provider wiring (yet)

This slice is offline and provides no wiring into `executor` / `orchestrator` /
provider. A future R4 authorization is a required precondition for any live
reconstruction using this A-only projection.

## 10. Threat model

- Structural trust is derived solely from pinned hashes + closed manifest
  fields; no filesystem mtime/size-only trust.
- Path traversal, absolute paths, drive-qualified paths, and symlink escapes are
  refused fail-closed.
- B/C escape into A is prevented structurally (only A sections materialize).

## 11. Contamination rule

**The implementation session that has seen B answers must never be reused as
the live Kira reconstruction context.** A future, clean session must be used for
the real reconstruction.