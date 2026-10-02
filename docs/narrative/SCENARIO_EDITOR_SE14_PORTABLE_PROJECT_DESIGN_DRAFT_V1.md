# SCENARIO_EDITOR_SE14_PORTABLE_PROJECT_DESIGN_DRAFT_V1

**Status:** `TECHNICAL_DRAFT / IMPLEMENTATION_CANDIDATE`
**Date:** 2026-10-02
**Slice:** SE-1.4 — Portable Project container (`.vscenario`)
**Package:** `services/scenario_authoring/portable.py`
**Format identity:** `voyage.scenario_editor.scenario_project` v1 (manifest schema `scenario_project_portable/0.1`)
**Source authority:** `NARRATIVE_DECISIONS_v1.md` §19 (`OD-SE-STORAGE-CONTRACT-01`),
`SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md` §G/§H,
`SCENARIO_EDITOR_SE12_LOCAL_PERSISTENCE_DESIGN_DRAFT_V1.md` §I.

> This is a **technical implementation candidate for independent review**, not a
> ratified acceptance schema. It implements the P1 portable container only; it
> does **not** ratify `DisplayPortionManifest` acceptance linkage, does not modify
> the authoring model, and does not implement Ren'Py export (SE-1.5).
>
> **Correction record:** the independent SE-1.4 review returned
> `C. REWORK_REQUIRED` (MAJOR 1 — `export_project` silently replaced an existing
> destination). Corrected to a CREATE-ONLY default (`overwrite=False`) with
> explicit `overwrite=True` authorization via no-clobber atomic publication. The
> other review findings remain open limitations (see §10), not corrected.

---

## 1. Purpose and non-goals

SE-1.4 provides a UI-independent portable-project API that captures one validated
current logical Project snapshot into a standard ZIP container (working extension
`.vscenario`), transfers it, and reopens it in a fresh destination through the
existing W1 `ProjectStore`.

Explicitly **out of scope**: PySide6 UI, Ren'Py export (SE-1.5), Character Lab
`.vchar` import, AI-provider integration, media playback, recovery-snapshot
packaging, and any change to `model.py` / `validation.py` / `persistence.py` /
`projection.py`.

---

## 2. Container layout

```
manifest.json              # versioned P1 manifest (itself NOT a listed entry)
project.json               # the authoritative W1 Project INDEX (on-disk bytes)
cards/<card_id>.json       # one independent W1 Card snapshot per card
media/<relative_path>      # authored local media bytes (one entry per path)
```

- The package reuses the **exact W1 serialized bytes** (`project.json` and
  `cards/<card_id>.json`) read from disk after a successful `ProjectStore.load()`,
  so the container is a faithful snapshot of the W1 layout and reuses W1 as its
  authority. No redesign of `Project`, `Card` or `MediaReference`.
- `media/` is a **reserved top-level directory** that holds authored local media.
  The package path for an authored `relative_path` is `media/<relative_path>`; the
  authored `relative_path` itself is preserved verbatim in `media_mapping`.
- Recovery snapshots are **not** included: the portable file represents one
  validated current logical snapshot.

---

## 3. Manifest contract

`manifest.json` is deterministic canonical JSON (`sort_keys`, UTF-8, no NaN):

```json
{
  "format_namespace": "voyage.scenario_editor.scenario_project",
  "format_version": 1,
  "manifest_schema_version": "scenario_project_portable/0.1",
  "project_id": "proj_alpha",
  "project_schema_version": "scenario_authoring/0.1",
  "storage_schema_version": "scenario_authoring_storage/0.1",
  "start_card_id": "card_a",
  "project_hash": "<sha256 of canonical project.to_dict()>",
  "entries": [
    {"path": "project.json", "size": 123, "sha256": "<hex>"},
    {"path": "cards/card_a.json", "size": 456, "sha256": "<hex>"},
    {"path": "media/media/bg_a.png", "size": 789, "sha256": "<hex>"}
  ],
  "media_mapping": [
    {"relative_path": "media/bg_a.png", "package_path": "media/media/bg_a.png"}
  ]
}
```

- `entries` lists every content member with canonical relative path, byte size and
  SHA-256. `project.json` is first, then `cards/*` in authored order, then
  `media/*` in sorted order (deterministic).
- `media_mapping` records the authored `relative_path` -> package path association
  (one entry per distinct authored local media path). It is validated to be
  1:1 with the `media/*` entries.
- `project_hash` is the SHA-256 of canonical `project.to_dict()`, giving a strong
  whole-project integrity anchor on top of the per-card W1 `content_hash`.

---

## 4. Portable API

Re-exported from `services/scenario_authoring`:

```python
export_project(source_root, destination_path, *, media_source_root=None, overwrite=False) -> ExportReport
validate_package(package_path) -> PackageSummary
import_project(package_path, destination_root) -> Project
```

Errors (under the existing `ScenarioAuthoringError` root):
`PortableProjectError`, `PortableProjectExportError`,
`PortableProjectValidationError`, `PortableProjectImportError`.

### Export
1. Load the complete validated Project via W1 `ProjectStore.load()`.
2. Snapshot the on-disk `project.json` + `cards/*` bytes.
3. Resolve every authored `relative_path` media against `media_source_root`
   (default `source_root`); reject missing/inaccessible/reserved/symlink sources.
4. Build the deterministic inventory + hashes.
5. Write the archive to a temporary sibling and `validate_package` it. Publication
   is CREATE-ONLY by default (`overwrite=False`): an atomic no-clobber hard-link
   rejects an already-existing destination (including one that appears after
   validation), preserving it byte-for-byte. `overwrite=True` explicitly
   authorizes atomic replacement via `os.replace`.

### Import
1. `validate_package`-equivalent checks in a single streaming pass.
2. Reject a non-fresh destination (nonexistent or empty) before writing anything.
3. Extract safely to an isolated temporary directory.
4. Reconstruct + verify the Project via W1 `ProjectStore` and `project_hash`.
5. Publish (cards, then media, then the index last) with per-file atomic writes;
   on any failure remove only the files created (no partial project remains).
6. Reopen through `ProjectStore` and verify `to_dict()` equality.

---

## 5. Media portability

- `MediaReference.relative_path` is a portable project-relative path. Its bytes
  are packaged and written back to the same authored relative path under the fresh
  destination; the authored data (`Project.to_dict()`) is never mutated.
- `MediaReference.asset_id` is a stable external Visual Asset Registry reference,
  not a local file. It is preserved verbatim as authored metadata and is **not**
  copied (no local bytes exist). Resolving it to bytes is a later-slice concern.
- Reserved media paths (`project.json`, `manifest.json`, `cards/*`) are rejected at
  export and validation time.
- No network access, no substitute media, no Character Lab `.vchar` integration.

---

## 6. Integrity guarantees

- Round-trip invariant: `import_project(...).to_dict() == source.to_dict()` and
  packaged `relative_path` media bytes equal the originals.
- Every declared member's size and SHA-256 are verified against the manifest.
- The manifest `project_hash` is re-verified against the reconstructed Project.
- The source W1 project is never mutated by export.

---

## 7. Archive security

Imported `.vscenario` is treated as untrusted input. Rejected: absolute paths,
drive-qualified paths, UNC paths, `..` traversal, backslash paths, symlink
members, duplicate (case-insensitive) members, unexpected members, malformed
JSON, unsupported versions, and missing/hash-mismatched members. Finite limits:

| Limit | Value |
|---|---|
| member count | 1024 |
| per-member uncompressed size | 64 MiB |
| total uncompressed size | 256 MiB |
| compression ratio | 1000 |

Extraction is streaming (no `extractall`); nothing is written outside the
intended destination; no network access is introduced.

---

## 8. Compatibility with W1

The package reuses W1's exact serialized representation and reconstruction path
(`ProjectStore.load()`), so an imported Project reopens exactly through existing
persistence. No accepted ASS/StorySequence data is modified; the authoring model
and its stable IDs/ordering are preserved.

---

## 9. Supported and unsupported cases

**Supported:** TEXT/CHOICE/MEDIA content items, multiple Cards/Slides, complete
Utterance text with Display Portions and speaker overrides, Card connections and
`start_card_id`, characters, `relative_path` media bytes, `asset_id` reference
preservation.

**Unsupported / deferred:** `asset_id` media byte resolution (external registry),
recovery-snapshot packaging, media deduplication, Ren'Py export (SE-1.5).

---

## 10. Unresolved P1 Owner decisions

1. Ratify or revise the `media/<relative_path>` package-path convention (the
   double-`media/` prefix appears when an authored path already starts with
   `media/`).
2. Ratify the exact security limits (member count / sizes / ratio).
3. Whether recovery snapshots must ever be portable.
4. Whether `asset_id` media should later embed a registry snapshot or remain an
   external stable reference.

---

## 11. SE-1.5 boundary

Ren'Py export of accepted portions and authored connections is SE-1.5 and is not
implemented here. `DisplayPortionManifest` remains an SE-1.3 technical candidate;
its acceptance linkage is not ratified by this slice.
