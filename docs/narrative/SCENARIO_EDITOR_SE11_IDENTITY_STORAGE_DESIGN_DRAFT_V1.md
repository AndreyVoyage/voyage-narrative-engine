# SCENARIO_EDITOR_SE11_IDENTITY_STORAGE_DESIGN_DRAFT_V1

**Status:** `TECHNICAL_DRAFT / OWNER_REVIEW_REQUIRED`
**Date:** 2026-10-02
**Slice:** SE-1.1 — Identity, authoring model and storage contracts
**Package:** `services/scenario_authoring/` (working schema id `scenario_authoring/0.1`)
**Source authority:** `NARRATIVE_DECISIONS_v1.md` §18/§19, `NARRATIVE_ROADMAP.md` §14.10,
`SCENARIO_EDITOR_PRODUCT_DESIGN_DECISIONS_V1.md`, `SCENARIO_CHARACTER_LIBRARY_AND_MULTI_ASSISTANT_V1.md`

> This is a **technical draft for Owner review**, not a ratified storage/package
> contract. It does **not** claim that the portable `.vscenario` format is
> implemented, does not implement ZIP packaging, and does not implement
> Card-level filesystem persistence (that is SE-1.2 / SE-1.4).

---

## Purpose and non-goals

SE-1.1 delivers a **pure, UI-independent authoring foundation**: immutable
plain-data entities for the agreed model (`Project → Cards → Slides → Content
Items / Utterances → Display Portions`) plus explicit, testable validation.

Explicitly **out of scope** (later slices): project save/reopen, autosave,
portable ZIP export, Card-to-OrderedASS projection (SE-1.3), Ren'Py generation,
Character Lab `.vchar` import, AI-provider integration, Dialogue Workshop UI,
visual Card editor, media playback, and Start Page / Game Menu builders.

---

## A. Entity identities and reference rules

Every entity carries an explicit **stable ID** — never a filesystem path, a
visual position, or a current list index. Identity follows the existing
lowercase-slug convention (``tools.visual_asset_registry.ASSET_ID_RE`` /
``workspace_project.PROJECT_ID_RE``):

```
^[a-z][a-z0-9_]{2,63}$
```

Reference rules:

- **Move** (reorder slides/items/portions) preserves identity: the ID is bound
  to the entity, not to its position.
- **Copy** requires a fresh ID: the model never auto-generates IDs, so a copy
  must be constructed with new IDs and duplicate detection rejects reuse.
- **Speaker** references are stable character IDs (``speaker_ids``), distinct
  from the Character Library membership (see §L).
- **Media** references are either a stable ``asset_id`` or a portable
  ``relative_path`` (§G/H), never an absolute machine path.

---

## B. Card / Slide / Item / Utterance / Portion invariants

| Entity | Invariants enforced at construction |
|--------|-------------------------------------|
| Project | non-empty ordered Cards; unique card IDs; `start_card_id` resolves to an existing Card; schema version pinned |
| Card | unique slide IDs; unique connection IDs; identity independent of path/position/index |
| Slide | unique content-item IDs; optional background media reference |
| ContentItem | one of `TEXT` / `CHOICE` / `MEDIA` with exactly its matching payload |
| Utterance | complete authoritative `text`; unique speaker IDs; portions, when present, form an **explicit complete segmentation** (ordered, non-overlapping, exactly covering `[0, len(text))`); invalid/stale ranges rejected, never silently repaired |
| DisplayPortion | stable ID; `0 <= start < end`; optional per-speaker portrait/emotion overrides referencing declared speakers |

The AI dialogue context is always based on the **complete** Utterance, never on
isolated Display Portions (DW-01..DW-03). Per-portrait/emotion overrides inherit
the previous portion's value by default (DW-02); this is exposed as a pure
``resolve_effective_overrides`` helper.

---

## C. Card connection representation

A ``CardConnection`` is explicit authoring data: a stable ``connection_id``, a
``target_card_id``, an optional author ``label``, and an optional ``choice_id``
that references an authored CHOICE item inside the source Card.

Cross-object validation (`validate_project`) reports, without raising:

- a connection whose ``target_card_id`` does not resolve to an existing Card
  (dangling connection);
- a branch connection whose ``choice_id`` does not resolve to an authored CHOICE
  item in the source Card;
- a ChoiceOption whose ``target_connection_id`` does not resolve to a connection
  of the same Card.

Connections are **frozen** and carry no mutator: moving content, splitting or
merging a Card never silently re-targets an existing branch, and there is no
operation that invents a new destination for a branch. A Card is never
automatically equal to one SceneBody / OrderedASS / Ren'Py scene; multiple Cards
may correspond to one accepted scene.

---

## D. Future deterministic Card-to-OrderedASS projection boundary

Projection of Cards into OrderedASS is **SE-1.3** and is **not implemented
here**. The boundary reserves only: a deterministic projection into existing
accepted-scene / Ren'Py structures, with no custom gameplay runtime. Cross-scene
targets must obey existing supported target semantics; ``start_card_id`` does
not make an arbitrary middle-of-scene entry a valid start position. Accepted
Display Portion metadata must eventually be immutable and hash-pinned. This
slice does **not** select any change to ``ass/0.2`` and does **not** introduce
``ass/0.3``.

## E. W1 working storage direction (local directory)

Direction (not implemented in SE-1.1): a **W1** local project directory with
fast, independent **Card-level persistence**. Each Card saves independently so
an author's per-card edit is cheap; the directory layout is defined in SE-1.2.
No W1 write path exists yet.

## F. P1 portable package direction (ZIP container)

Direction (not implemented): a **P1** portable ZIP package carrying a versioned
**manifest**. The package must be openable on another Windows PC, must not
depend on absolute source-machine paths, and must include a manifest with
integrity verification. `.vscenario` remains only a working extension name until
the exact package contract is ratified. **No ZIP packaging is implemented here.**

## G. Stable asset references and media deduplication

Media is referenced through a ``MediaReference`` (stable ``asset_id`` or
portable ``relative_path``). A future storage layer should deduplicate identical
bytes (content-addressed) while preserving the logical reference and the
original media bytes. The authoring model never reads or normalizes media
bytes; it only validates that the reference is stable and portable.

## H. Safe relative paths and cross-PC portability

``relative_path`` must be forward-slash, traversal-free, and non-absolute
(no `C:`, no leading `/` or `\`, no `..`/`.`/empty segments). This keeps a
project openable on a different Windows PC without rewriting references.

## I. Atomic save and previous-good backup

A future W1/P1 writer must write via a temporary file + atomic rename, and keep
a **previous-good** copy for recovery. Not implemented in SE-1.1.

## J. Corruption detection and hash verification

A future manifest must carry a deterministic content hash (mirroring the
existing ``content_hash`` convention in `services/ass`) so corruption and stale
packages are detected rather than silently repaired. Not implemented here.

## K. Secrets exclusion (without filtering prose)

Provider credentials and application secrets must be **excluded** from portable
project files. This applies to credential/configuration **fields** only — an
ordinary fictional text that happens to contain words such as "password" or
"token" is not rejected on that basis (OD-SE-STORAGE-CONTRACT-01).

## L. Character Library provenance and future `.vchar` inclusion

The model reserves a minimal ``CharacterReference`` (`character_id` +
`provenance`: `MANUAL` or `CHARACTER_LAB_VCHAR`) only. Three concepts stay
distinct: **Character**, **Character Media Library**, **optional Character AI
Assistant**. Importing a Character must **not** automatically cast it into the
work, create dialogue, activate a provider, or create a Writing Assistant.
SE-1.1 does **not** implement `.vchar` import and does **not** create a
replacement package format; the future project package will include the
necessary character data/media via the existing VCP readers.

## M. Versioning and backward compatibility

Semantic versioning. The in-memory model pins its own schema id
(`scenario_authoring/0.1`); future ratified storage/package contracts get their
own version and must be backward-compatible with already-published data.
Changing a persona/module/core table bumps its version (repo convention).

---

## Acceptance boundaries (unchanged)

- `scene_body/1.0` unchanged.
- `ass/0.2` unchanged.
- `vne_story_sequence/0.1` unchanged.
- A technical scene may correspond to multiple Cards.
- Card connections are authoring data, not a competing gameplay runtime.
- Cross-scene targets obey existing supported target semantics.
- `start_card_id` does not make an arbitrary middle-of-scene entry a valid start.
- Accepted Display Portion metadata must eventually be immutable and hash-pinned.
- No decision to modify `ass/0.2` or introduce `ass/0.3` is authorized here.
- No Card-to-OrderedASS projection (SE-1.3).

## Open technical decisions (require separate Owner approval)

1. Exact W1 directory layout and per-card file granularity.
2. Exact P1 manifest schema, package-version semantics, and `.vscenario` format.
3. Named emotion catalog (currently unconfirmed; kept as an opaque string).
4. Exact Display Portion pinning/hash mechanism.
5. Fallback policy for a missing default portrait.

