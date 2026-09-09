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

**Character-ID boundary (CANON_TO_COMPANION_CHARACTER_ID_MAPPING_V1):** the
Companion-local `character_id` (storage path, `manifest.characterId`,
`ReferenceRecord.character_id`, `SnapshotStore` lookup, catalog discovery) is
**distinct** from the exact Character Canon `source_character_id` (source folder
/ preset filename / `payload["character"]` production gate). `import_character`
takes both (`source_character_id` defaults to `character_id`, never
case-folded). The vendored `canon_reader` receives only `source_character_id`,
so its exact-identity semantics are unchanged; the vendored `reference_importer`
receives only `character_id`, so imported bytes are owned by the Companion id.
`sourceCanon.sourceCharacterId` records the Canon identity as provenance and is
part of the snapshot semantic hash.

## Slice B — reference selection + visual context + visual prompt (OFFLINE)

Deterministic chain, no provider / network / credentials / Character Canon:
active `CharacterLocalSnapshot` + `CompanionScene` + bounded linear
conversation (≤ 8 msgs) + optional explicit description (≤ 4000 chars) →
`VisualContext` → local reference selection → `ReferenceBundle` (bytes from the
snapshot dir only) → physical identity block → `VisualPromptPackage`. Output
stops at `VisualPromptPackage` + `ReferenceBundle` (Slice C = provider).

| Target path (`services/character_companion/visual/`) | Source path (in the source repo) | Classification | Adaptation note |
|---|---|---|---|
| `reference_selection.py` | `tools/reference_selector.py` | ADAPTED | Kept: the priority ladder (face/identity authority → body → face/expression support → motion support), bounded **2–4** per character, SHA + asset-identity de-dupe, deterministic ordering, fail-closed when no identity reference exists. Adaptation: the VNE version consumes a curated semantic **catalog**; Companion V1 drives the ladder directly off `CharacterLocalSnapshot.references[].roles` (a small hand-imported set) and relaxes "one body" to "all body views up to the cap". Roles come only from the snapshot manifest — never a filename, never Canon. Added an explicit-`asset_ids` override path (validate-against-snapshot, order-preserving, de-duped, no min/max clamp). |
| `reference_model.py` | `services/character_visual_conditioning/model.py` | ADAPTED | `ReferenceEntry` + a single-character `ReferenceBundle` shape kept (frozen dataclasses, `semantic_payload()` excludes machine paths + bytes, deterministic `compute_hash()`). Dropped: the multi-character `ReferenceCharacterGroup` nesting (Companion V1 conditions on exactly one active character). Schema id `companion_reference_bundle/0.1`. `relative_path` is OPERATIONAL only — never hashed, never rendered into prose. |
| `reference_bundle.py` | `services/character_visual_conditioning/bundle.py` (shape/idea only) | COMPANION-OWNED (new) | No source code copied. Fail-closed builder: snapshot-relative safe path that resolves under the snapshot dir, file exists, byte length matches the manifest, SHA-256 matches, magic-byte format matches the declared `fileType`, PNG/JPEG/WEBP only. Bytes come **only** from `<snapshot_dir>/references/`. No `canon_root` parameter anywhere. `validate_reference_bundle_integrity` re-hashes + re-checks every payload. |
| `physical.py` | `tools/scene_image_test_app.py` (lines ~548–690) | EXTRACTED | `_gender_label` → `gender_label`, `_format_weight` → `format_weight`, `_height_line` → `height_line`, `_render_relative_scale` → `render_relative_scale`, `_render_physical_block` → `render_physical_block` lifted verbatim in behaviour. Left behind: the `orchestrate` harness, fixtures, forbidden-token scanning, the physical-profiles file loader. Companion extension: also emits `face` / `hair` / `confirmed traits` lines (present in the imported snapshot; the VNE block omitted them). Still never emits `style_direction*`, `safety_rules`, paths, or SHAs; no scenario-specific forbidden-token logic. |
| `context.py` | — | COMPANION-OWNED (new) | No source code copied. `VisualContext` binds `character_id` + snapshot version; conversation bound mirrors `CompanionService._CONTEXT_EXCERPT_MAX` (8); custom request → explicit description required, recent messages dropped; context request → scene and/or bounded chat and/or description. Presentation-"hidden" state is a UI concern and never independently filters the raw history handed in here. Deterministic `content_hash` (no timestamps, no paths). |
| `prompt.py` | — | COMPANION-OWNED (new) | No source code copied. Fixed section order `[REQUEST]` / `[SCENE]` / `[RECENT CONTEXT]` / `[CHARACTER IDENTITY]` / `[REFERENCE GUIDANCE]`; reference guidance names asset ids + roles only (never a relative path, never an absolute path, never bytes); binds one identity + one snapshot version (rejects `character_id` / snapshot-version disagreement between the `VisualContext` and the `ReferenceBundle`). Deterministic `content_hash` over the semantic payload. Deliberately contains no SceneInterpretationArtifact / MediaPlan / VNE PromptPackage chain / branch or supersession awareness / Ren'Py concern. |
| `hashing.py` | — (re-export) | COMPANION-OWNED (new) | Re-exports `canonical_json` / `compute_sha256` / `is_valid_sha256` / `sha256_hex` from `character_import.hashing`; adds `content_hash(payload)` as a thin alias of `sha256_hex`. No new hashing convention. |
| `errors.py` | — | COMPANION-OWNED (new) | Single root `VisualPipelineError` with `VisualContextError` / `ReferenceSelectionError` / `ReferenceBundleError` / `VisualPromptError`. Messages carry stable logical identifiers only — never absolute machine paths, Canon paths, asset bytes, or credentials. |

**Hard rule (Slice B):** the visual chain must **not** require
`narrative-character-canon`. It operates solely from
`<data-root>/characters/<character_id>/snapshots/<ACTIVE>/`. Nothing in
`services/character_companion/visual/**` imports `canon_reader`, takes a
`canon_root`, or opens a Canon path. Not reintroduced: sent-message edit,
supersession, branches, ASS, SceneInterpretationArtifact, MediaPlan, the VNE
PromptPackage chain, Ren'Py.

## Not vendored in Slice A / B

`services/ass/**`, `services/scene_interpretation/**`, `services/mediaplan/**`,
`services/prompt_composer/**`, `services/scene_text_interpreter/**`,
`services/character_visual_conditioning/{provider}.py` and the multi-character
selection/grouping in `selection.py`,
`services/image_provider_boundary/**`, `services/location_canon/**`,
`services/generated_image_review/**`,
`services/approved_generated_image_asset_gate/**`,
`tools/visual_asset_registry.py`, and the `tools/scene_image_test_app.py`
orchestrator / provider call. These belong to later slices (C: provider
adapter; D: product binding) or are VNE/Ren'Py-specific.
