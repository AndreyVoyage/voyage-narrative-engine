# SCENARIO_EDITOR_SE12_LOCAL_PERSISTENCE_DESIGN_DRAFT_V1

**Status:** `TECHNICAL_DRAFT / IMPLEMENTATION_CANDIDATE`
**Date:** 2026-10-02
**Slice:** SE-1.2 — Local Card persistence and recovery
**Package:** `services/scenario_authoring/persistence.py` (storage schema id `scenario_authoring_storage/0.1`)
**Source authority:** `NARRATIVE_DECISIONS_v1.md` §19 (OD-SE-STORAGE-CONTRACT-01),
`SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1.md` §G/§H/§I/§J.

> This is a **technical implementation candidate for independent review**, not a
> ratified storage/package contract. It implements only the W1 local working
> directory; the portable P1 ZIP container (`.vscenario`) is explicitly out of
> scope (SE-1.4).

---

## Purpose and non-goals

SE-1.2 adds a minimal, UI-independent persistence API over the existing pure
SE-1.1 authoring model. The required user-visible behavior is: create a Project,
add connected Cards, Slides, a complete Utterance split into Display Portions,
save locally, discard in-memory state, reopen, and recover exactly the same
authored content.

Explicitly **out of scope**: PySide6 UI, Card visual editor, portable ZIP save,
Ren'Py publication, Card-to-OrderedASS projection (SE-1.3), Character Lab import,
AI-provider integration, media-file copying/deduplication, and generic
database/transaction/revision frameworks.

---

## A. W1 directory layout

```
<project_root>/
    project.json            # atomically-replaced Project INDEX
    cards/<card_id>.json    # one independent Card snapshot per stable card_id
    recovery/               # previous-good copies for explicit recovery
        project.json
        cards/<card_id>.json
```

- `project.json` is the authoritative **index**: ordered membership, `start_card_id`,
  characters, and a per-Card `content_hash`. It never embeds Card content.
- `cards/<card_id>.json` is one independent Card snapshot (raw `card.to_dict()`).
- `recovery/` holds the previous-good snapshot; restored only by explicit recovery.

The card file name is derived from the stable `card_id`, but identity is the
`card_id` field inside the file, verified against the index entry. Filesystem
paths are never entity identities.

---

## B. Serialized Project/Card boundaries

**Project index (`project.json`):**

```json
{
  "schema_version": "scenario_authoring_storage/0.1",
  "project_id": "proj_alpha",
  "authoring_schema_version": "scenario_authoring/0.1",
  "start_card_id": "card_a",
  "cards": [
    {"card_id": "card_a", "content_hash": "<sha256 hex>"},
    {"card_id": "card_b", "content_hash": "<sha256 hex>"}
  ],
  "characters": [ "... CharacterReference.to_dict() ..." ]
}
```

The `cards` array is ordered and preserves authoring order. `characters` is
omitted when empty.

**Card snapshot (`cards/<card_id>.json`):** the raw `card.to_dict()` payload:

```json
{
  "card_id": "card_a",
  "slides": [ "... Slide.to_dict() ..." ],
  "connections": [ "... CardConnection.to_dict() ..." ]
}
```

`content_hash` is the lowercase-hex SHA-256 of the canonical JSON
(`ensure_ascii=False, sort_keys=True`) of `card.to_dict()`, mirroring the
existing `services/ass/hashing.py` convention. Reopening reconstructs the
Project through the validated `project_from_dict` interface (plus
`validate_project`) — never by ad-hoc dict assembly.

---

## C. Supported operations

`ProjectStore(root: Path)` provides:

- `save(project)` — initial/full save. Cards are written first, then the index
  last, so the index never points at incomplete Card content. Validates
  consistency and lossless round-trip before any write.
- `save_card(card)` — persist one **already-existing** Card independently;
  rewrites only that Card's file plus the index entry, never an unrelated Card.
- `load()` — reopen and validate the stored Project (fail closed).
- `recover()` — explicit restore from `recovery/`.
- `exists()` / `has_recovery()` — predicates.

Failures raise `ScenarioAuthoringStorageError` and its subclasses
(`NotFoundError`, `CorruptionError`, `RecoveryError`), all under the existing
`ScenarioAuthoringError` root.

---

## D. Safe path rules

- A `card_id` must match the existing stable lowercase-slug
  `^[a-z][a-z0-9_]{2,63}$` (reused from the model). This makes any derived file
  name traversal-free and drive-letter-free by construction.
- Every derived path is additionally verified to stay under the resolved project
  root (`os.path.commonpath` check), as defense in depth.
- Parent-directory traversal (`..`), unsafe absolute references, and unexpected
  Windows drive paths are rejected; `relative_path` media references keep the
  existing SE-1.1 portable forward-slash rules unchanged.

---

## E. Atomic-write behavior

Each file is written via a same-directory temporary file
(`tempfile.mkstemp`) with `fsync`, then atomically published with `os.replace`.
Publication order is Cards first, then the authoritative index last. Because
multiple independent file replacements do **not** form one atomic transaction,
a previous-good snapshot is kept in `recovery/` for explicit recovery. A failed
save never destroys the previous-good snapshot: if the current main state is
already corrupt, the snapshot step refuses to overwrite good recovery data.

---

## F. Previous-good recovery

`_snapshot_previous_good()` copies the current valid main state into
`recovery/` at the start of a save. `recover()` validates the recovery snapshot
(so corrupt recovery data is never restored), restores it to the main location,
and returns the recovered Project. Recovery restores exactly the snapshot —
it never invents missing authored content.

---

## G. Detected corruption

The following are detected and rejected (fail closed, no silent repair):

- malformed / non-object / duplicate-key / non-finite-number JSON;
- wrong storage or authoring schema version;
- missing required index fields;
- unsafe or duplicate `card_id` in the index;
- missing referenced Card data;
- Card file whose `card_id` does not match the index entry (identity mismatch);
- Card file whose `content_hash` does not match the index entry (content
  mismatch / stale content);
- a stored project that fails `validate_project` cross-object consistency.

---

## H. Limitations

- W1 is a **local single-directory** layout with **one level** of previous-good
  (not a multi-generation history).
- Orphan card files (present under `cards/` but absent from the index) are not
  treated as corruption; `load()` reads only the indexed cards.
- The project index itself carries no self-hash; its integrity is enforced by
  strict parsing plus `project_from_dict`/`validate_project` on the assembled
  project.
- No media bytes are copied; `MediaReference` is preserved as plain data.

---

## I. Future P1 compatibility boundary

The portable P1 ZIP container (SE-1.4) is not implemented. The W1 index and
Card snapshot payloads are intentionally pure plain data (`project.to_dict()` /
`card.to_dict()`), so a future P1 manifest can reuse the same serialized
representation and add packaging/`content_hash` semantics without changing the
authoring model. Media-file copying, portable packaging, and deduplication
remain SE-1.4.
