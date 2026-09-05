# KIRA Dimension Semantics Extension v1

A **separate, versioned** artifact that gives the Accepted KIRA package
character-specific meaning for two numeric runtime-state dimensions
(`RELATIONSHIP/trust`, `PSYCHOLOGY/stress`) **without modifying `accepted/**`**.

## Artifact

`character_packages/kira/extensions/dimension_semantics/v1.json`

| Field | Value |
|---|---|
| `character_id` | `kira` |
| `extension_type` | `dimension_semantics` |
| `extension_version` | `1` |
| `target_accepted_source_hash` | `e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd` |
| `core_contract_version` | `0.1.0-dev` (recorded, not enforced) |
| `dimensions` | `RELATIONSHIP/trust`, `PSYCHOLOGY/stress` — each with all five band meanings |

It is intentionally **not** a broad dimension catalogue — only what the first
behavioral validation needs.

## Responsibility split

| Layer | Owns |
|---|---|
| **Character Core** (`services/character_core/dimensions.py`) | `DimensionDefinition` schema, validation, the generic bands (`VERY_LOW..VERY_HIGH`), number→band mapping, the renderer. **No** character-specific meaning. |
| **This extension** | KIRA-specific behavioral band meanings for `trust` / `stress`. |
| **Loader** (`services/character_lab/package_extensions.py`) | file resolution, identity validation, fail-closed hash binding. |
| **`RuntimeService.turn`** | injects the validated `DimensionSet` into `runtime_context["dimension_definitions"]` **for `KIRA_GROUNDED_V2` only**. |
| **`GroundedV2Policy`** | consumes the existing Foundation hook and renders `value + band + meaning`. Unchanged by this slice. |

Dependency direction: extension → Character Core validation → runtime context →
Grounded v2 rendering. Nothing KIRA-specific lives in Core or in
`runtime_policy.py`.

## Binding / fallback rules

- **Hash mismatch** (`target_accepted_source_hash` ≠ current accepted source
  hash): **fail closed** — `PackageExtensionError`, no semantics attached. This
  protects reproducibility: semantics are never silently bound to a different
  package version.
- **Bad identity** (`character_id` / `extension_type` / `extension_version`
  wrong): fail closed.
- **No extension file** for a character: return `None` → Character Core's
  raw numeric rendering (`- key: value`), exactly as before this slice.
- **Partial coverage** (a numeric key with no matching definition, e.g.
  `andrey.tension`): that line stays raw; defined dimensions still render
  enriched.

## Rendered result (with `andrey.trust = 70`, `stress = 70`)

```
- andrey.trust: 70 (band: VERY_HIGH) — Deep trust: open with this subject and willing to rely on them, with suspicion largely set aside — still within her boundaries, safety, canon, and established facts; not romance or attraction.
- stress: 70 (band: VERY_HIGH) — Severe current stress: strong tension and low tolerance for friction, replies more compressed or fragmented, while identity, boundaries, and canon still hold; not panic unless separately established.
```

Beta v1 (`KIRA_BETA_V1_CURRENT`) never receives this key and is unaffected.

## Not in this slice

No live provider call. No automatic evolution of the numbers. No DB/schema
change. The behavioral A/B validation is prepared as a spec only
(`tests/fixtures/character_packages/kira_behavioral_ab_v1.py`).
