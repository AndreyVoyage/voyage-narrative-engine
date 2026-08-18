# Visual Asset Registry + Safe Import v0 — Contract

DATE: 2026-08-18
STATUS: Implemented (v0, uncommitted)

This document ratifies the exact v0 contract implemented by
`tools/visual_asset_registry.py` and the registry at
`scenarios/visual_assets/ASSET_REGISTRY.json`. It is the durable reference
for the first slice of Visual Asset Registry + Safe Import.

## 1. Stock-first boundary

Everything is Python standard library (`pathlib`, `hashlib`, `json`,
`argparse`, `os`, `re`, `sys`, `tempfile`, `datetime`, `typing`). No Pillow, no custom
image decoder, no new dependency. Ren'Py remains responsible for actual
runtime image display in a later slice; this slice only establishes the
controlled import + metadata foundation.

## 2. Categories

Exactly three v0 categories: `background`, `character`, `cg`.

```
novel/game/images/story/backgrounds/<asset_id>.<ext>
novel/game/images/story/characters/<character_id>/<asset_id>.<ext>
novel/game/images/story/cg/<asset_id>.<ext>
```

- `character` requires a valid `character_id` and nests under
  `characters/<character_id>/`.
- `background` and `cg` are flat.

## 3. Registry location & schema

Location: `scenarios/visual_assets/ASSET_REGISTRY.json` (git-tracked).

Root shape: `{"assets": []}`. Each record carries these v0 fields:

| Field | Required | Notes |
|---|---|---|
| `asset_id` | yes | see §4 |
| `type` | yes | `background`/`character`/`cg` |
| `relative_path` | yes | repo-root-relative, forward-slash, under the story root only |
| `source_kind` | yes | `character_canon`/`manual`/`unknown` |
| `source_character_id` | conditional | required when `type=character` |
| `source_original_name` | optional | display basename only, never a path |
| `source_hash` | optional | SHA-256 of pre-copy source bytes (informational) |
| `imported_hash` | yes | SHA-256 of committed destination bytes (integrity field) |
| `format` | yes | canonical `png`/`webp`/`jpg` (derived from magic bytes) |
| `mime_type` | yes | derived, e.g. `image/png` |
| `created` | yes | ISO-8601 UTC timestamp |
| `notes` | optional | free text, default `""` |

`width`/`height` are **deferred** (would require a new dependency or
hand-rolled per-format header parsing).

## 4. asset_id rules

Regex: `^[a-z][a-z0-9_]{2,63}$`

Lowercase ASCII letters/digits/underscore only; must start with a letter;
`_` separator; 3–64 characters; globally unique across the registry. No
spaces, no filesystem path, no UUID-only IDs, no Windows path syntax.
Rejected deterministically at import time.

## 5. Supported formats

PNG, WEBP, JPG/JPEG. `jpg` and `jpeg` canonicalise to `.jpg`. Validation is
by magic-byte signature (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, WEBP
`RIFF????WEBP`), not extension alone — a renamed non-image must not pass.

Rejected/deferred for v0: GIF, SVG, AVIF, and any unlisted format.

## 6. COPY semantics

Import **COPIES** the source; it never moves, modifies, or deletes it.
External source changes after import have **no effect** on the game; a new
bytes version can only be introduced via an explicit `update` command.

## 7. SHA-256 integrity

Source bytes → SHA-256 → copy → destination bytes → SHA-256. Import aborts
if `source_sha256 != destination_sha256`. The destination hash is recorded
as `imported_hash`; the source hash as informational `source_hash`.

## 8. Provenance portability

Only portable provenance is stored: `source_kind`, `source_character_id`
(conditional), `source_original_name` (basename), `source_hash`. The
original absolute source filesystem path is **never** stored (it is
non-portable and non-reproducible).

## 9. Duplicate policy (five cases)

| Case | Behavior |
|---|---|
| A. new `asset_id` + new bytes | IMPORT |
| B. existing `asset_id` + identical bytes | NO-OP (idempotent success, no rewrite) |
| C. existing `asset_id` + different bytes | REJECT — use explicit `update` |
| D. different `asset_id` + identical bytes | IMPORT with non-blocking warning (aliasing) |
| E. destination exists but registry has no entry | REJECT (filesystem drift) |

No silent overwrite in any case.

## 10. Update / re-import policy

Explicit `update` (requires `--asset-id` that already exists + `--source`).
No automatic synchronization, no background watch, no polling, no source
repository scan. Format changes require a new `asset_id`.

Updates are **failure-safe via staged replacement + compensating rollback**,
not a single cross-file transaction (the asset and the registry are two
separate files; individual writes use atomic file replacement, but there is
no filesystem-atomic "both at once" guarantee).

Update sequence:
1. Validate the new source and prepare the intended registry state in
   memory (serialisation is exercised before any destination mutation).
2. Stage the validated new bytes to a temp file in the destination
   directory and verify its SHA-256.
3. Create a recovery backup copy of the **existing local VNE asset bytes**
   (never the external source).
4. Atomically replace the destination with the new bytes.
5. Atomically persist the registry.
6. On registry-persistence failure, restore the destination from the
   recovery backup and leave the on-disk registry unchanged; only
   operation-created temp files are cleaned up.
7. If restoration also fails, a distinct `CRITICAL` diagnostic is surfaced
   (including both the registry-write and rollback errors) and the recovery
   backup is retained so the only copy of the previous bytes is not lost.

New imports: if registry persistence fails after the asset copy, only the
destination file created by that import is removed; the registry stays
unchanged, pre-existing destinations, unrelated orphans, and the source are
never deleted.

## 11. Dry-run / validate

- `import --dry-run`: runs every validation step and classification, prints
  the planned destination/action, performs **zero** filesystem writes.
- `validate`: read-only; checks asset_id uniqueness/validity, category,
  relative-path safety (no absolute paths, no `..`, under story root, no
  duplicate physical paths), file existence, allowed extension, live hash
  match, `source_character_id` presence for characters, and **orphan
  detection** — any supported asset file under `novel/game/images/story/`
  that has no registry entry is reported as a validation failure. The
  validator never deletes, repairs, or registers orphan files.

## 12. CLI

```
py tools/visual_asset_registry.py import --source <path> --asset-id <id> --type {background,character,cg} [--character-id <id>] [--source-kind {character_canon,manual,unknown}] [--notes <text>] [--dry-run]
py tools/visual_asset_registry.py update --asset-id <id> --source <path> [--notes <text>] [--dry-run]
py tools/visual_asset_registry.py validate [--registry <path>]
```

Exit codes: `0` success (including case-B NO-OP), `1` validation/rejection
failure, `2` argparse usage error.

## 13. No direct Character Canon dependency

The tool never reads or writes any external character-canon repository. The
future workflow is: external source → explicit controlled import → local VNE
copy → game, with zero automatic coupling after the copy.

## 14. Deferred (not implemented in v0)

- scene JSON integration (`visual.stills`, background-per-scene field)
- Ren'Py exporter/runtime adapter changes
- actual runtime image display
- `width`/`height` dimensions
- Pillow or any new dependency
- visible delete controls / version history