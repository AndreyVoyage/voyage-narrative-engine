# Visual pipeline — vendoring provenance (V1)

Every source-derived module in the Companion visual pipeline records where its
code came from. This is provenance, not a licence claim: the source repo is an
internal sibling project.

- **Source repo:** `C:\DEV\Narrative\vne-n9-pac-merge`
- **Source commit:** `a445ab59f6104e1524b5249c4f11e659a042fde4` (branch `main`)
- **Integration map:** `VISUAL_PIPELINE_COMPANION_INTEGRATION_MAP_V1` (owner report)

Classifications:

- **VENDORED_NEAR_AS_IS** — the source function/class was copied with only
  cosmetic edits (module docstring/header, local relative imports). Logic
  unchanged.
- **ADAPTED** — real behavioural retargeting (paths, schema ids, dropped
  fields, credential handling). The core algorithm is preserved; the note says
  exactly what changed.
- **EXTRACTED** — only specific pure functions were lifted out of a larger
  file; the surrounding CLI / orchestrator / repo globals were left behind.

## Slice A — Character Local Snapshot + controlled Canon import

| Target path (`services/character_companion/character_import/`) | Source path (in the source repo) | Classification | Adaptation note |
|---|---|---|---|
| `canon_status.py` | `services/character_canon_bridge/status.py` | VENDORED_NEAR_AS_IS | Only the module header changed. `KNOWN_CANON_STATUSES`, `PRODUCTION_APPROVED_STATUSES = {"APPROVED_AS_CANON"}`, `is_known_canon_status`, `is_production_approved` are byte-equivalent. |
| `canon_model.py` | `services/character_canon_bridge/model.py` | VENDORED_NEAR_AS_IS | `CanonReference`, `Provenance`, `CharacterCanonSnapshot` copied verbatim (frozen dataclasses, `semantic_payload()`/`to_dict()`). The unused `_freeze`/`_to_plain` helpers were not carried over. |
| `canon_reader.py` | `services/character_canon_bridge/reader.py` | ADAPTED | Logic identical: NCC layout `AI_CHARACTERS/<ID>/10_notes/<ID>_REFERENCE_PRESETS.json`, exact `character` id check, `_is_safe_relative` path safety, `active_canon` + `scene:`-prefixed reference collection, `usage_context="production"` → requires `APPROVED_AS_CANON`, deterministic `content_hash`/`source_hash`, **zero writes to Canon**. Adaptation: imports the local `errors`/`canon_model`/`canon_status`/`hashing` modules. |
| `hashing.py` | `services/character_canon_bridge/hashing.py` **+** `services/reference_library/hashing.py` | VENDORED_NEAR_AS_IS (merged) | Two source files merged: `canonical_json`/`sha256_hex`/`compute_content_hash`/`compute_source_hash` from the bridge; `compute_sha256(bytes)`/`is_valid_sha256` from reference_library. No logic change. |
| `errors.py` | `services/character_canon_bridge/errors.py` **+** `services/reference_library/errors.py` | ADAPTED | Both taxonomies re-parented under one root `CharacterImportError` and renamed to a Companion prefix (`ReferenceLibrary*` → `Reference*`). Added the local-snapshot error family (`SnapshotError`/`SnapshotNotFoundError`/`SnapshotValidationError`/`SnapshotOperationError`). |
| `reference_model.py` | `services/reference_library/model.py` | ADAPTED | `ReferenceRecord` kept (frozen, sha256 + `file_type` PNG/JPEG/WEBP validation, `from_dict`/`to_dict`). Dropped fields: `collection`, `mime_type`, `notes` (schema minimization — roles live on `CharacterLocalSnapshot`). `relative_path` is snapshot-relative. |
| `reference_manifest.py` | `services/reference_library/manifest.py` | ADAPTED | Kept: `is_safe_relative_path` (absolute/drive/UNC/backslash/`..`/empty rejection), deterministic serialize/parse/load/`save_manifest` (atomic), `find_records_by_sha256`. Adaptation: the "asset root" is the snapshot-local `references/` dir (`is_under_references_dir`), schema id `companion_reference_manifest/0.1`; dropped the repo-manifest `validate_manifest`/`lookup_record` helpers not used by this slice. |
| `reference_importer.py` | `services/reference_library/importer.py` | ADAPTED | Kept: COPY-only (never move/delete source), `sniff_image_format` magic bytes, extension/signature mismatch rejection, source SHA-256, `_atomic_copy_verified` (staged write → SHA verify → `os.replace`), `asset_id` collision + duplicate-SHA + cross-character-duplicate policy (`NO_OP_DUPLICATE`/`NO_OP_EXISTING_ASSET`), rollback of only the destination created by the failing call. Adaptation: destination is `<snapshot_dir>/references/<asset_id>.<ext>`; dropped `collection`/`notes`; `repo_root`→`snapshot_dir`. |
| `physical.py` | `tools/build_physical_profiles.py` | EXTRACTED | `_normalize_height`, `_normalize_weight`, `_is_owner_approved_exact`, `_str_or`/`_opt_str`/`_str_list` and the record-shaping (`normalize_preset` → `physical_profile_from_preset`) are verbatim. Left behind: `argparse`, `_REPO_ROOT`, `DEFAULT_OUTPUT`, `discover_preset_paths`, `build_snapshot`, `serialize_snapshot`, `main`. Output keeps `source_preset_sha256` binding; drops `source_preset_path`. |
| `local_snapshot.py` | — | COMPANION-OWNED (new) | No source code copied. `CharacterLocalSnapshot` + `SnapshotStore` (versioned `snapshots/vN/`, `ACTIVE` pointer, fail-closed load validation). |
| `service.py` | — (composes the above; selection rule referenced) | COMPANION-OWNED (new) | `_active_canon_references` re-implements the `character_visual_conditioning/selection.py::_active_references` rule (drop `scene:` variants, dedupe by path, preserve `active_canon` order). Role mapping is from Canon **keys**, never filenames. |

## Not vendored in Slice A

`services/ass/**`, `services/scene_interpretation/**`, `services/mediaplan/**`,
`services/prompt_composer/**`, `services/scene_text_interpreter/**`,
`services/character_visual_conditioning/{bundle,provider,selection}.py`,
`services/image_provider_boundary/**`, `services/location_canon/**`,
`services/generated_image_review/**`,
`services/approved_generated_image_asset_gate/**`,
`tools/reference_selector.py`, `tools/scene_image_test_app.py`,
`tools/visual_asset_registry.py`. These belong to later slices (B: reference
selection + visual context + prompt assembly; C: provider adapter; D: product
binding) or are VNE/Ren'Py-specific.
