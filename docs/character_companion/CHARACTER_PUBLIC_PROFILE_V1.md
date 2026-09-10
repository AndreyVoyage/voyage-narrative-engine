# Character Public Profile (V1)

`CharacterPublicProfile` is the **editable, editorial, user-facing presentation
layer** for a companion character. It answers one question: *what does the
product choose to show a user about this character?*

## Boundary — this is NOT runtime truth

| Layer | Owns | Mutated by a profile edit? |
|---|---|---|
| Accepted Character Package | who the character is for the runtime (personality, voice, boundaries, CRP claims) | **never** |
| `CharacterLocalSnapshot` | the visual identity / reference authority | **never** |
| Runtime state / relationship / psychology / Memory | the live conversation | **never** |
| **`CharacterPublicProfile`** | display name, short & long description, ordered sections, ordered public media, section/media visibility | this is the only thing an edit changes |

Editing `short_description`, `long_description`, a profile section, or public
media ordering changes only `<data_root>/character_profiles/<character_id>.json`.
It performs no Accepted Package, runtime, snapshot, or Memory write. A public
profile is curated editorial content and must never carry CRP R1–R8 data, claim
ids, evidence, prompts, package/snapshot hashes, provider config, numeric
relationship/psychology state, Memory, conversation history, credentials, or
filesystem paths — the model has no such fields.

## Ownership

* **Admin Studio (future)** → edits and publishes a `CharacterPublicProfile`
  through `CharacterPublicProfileStore.save(...)` (or the future
  `CompanionService.save_public_profile`). No Admin HTTP write route exists
  yet.
* **Companion** → reads and presents it: `CompanionService.get_public_profile`
  → `CompanionTransport.get_character_profile` →
  `GET /api/companion/characters/<id>/profile`.

## Precedence

1. A profile **persisted** through the store (Admin Studio) — returned with
   `is_fallback = False`.
2. Otherwise a **restrained built-in default** — `is_fallback = True`, a single
   short line, no long description, no sections, no media. A malformed persisted
   file fails closed to this default (a broken edit never removes the character
   from the UI).

There is exactly one source of truth per character (the store); the default is
only used when the store has nothing.

## Public profile media ≠ session / gallery media

* **Public profile media** = images/videos an author/admin explicitly curated
  for the character's presentation. Source refs are transport-safe only
  (`characters/…` static assets, or `images/…` served generated files); absolute
  paths, `..`, backslashes, and URL schemes are rejected.
* **Chat / gallery media** = images generated during sessions / `ImageJob`
  results. These are **never** auto-promoted into the public profile. A future
  Admin Studio may explicitly promote one; V1 does not.

## Card vs detail

* The character list ships a **lightweight card summary** per entry
  (`shortDescription`, `hasDetailedProfile`, `profileIsFallback`) — never the
  long copy, sections, or media.
* `"Подробнее"` fetches the **full profile** on demand and opens a right-side
  detail drawer. Opening/closing the drawer never changes the selected
  character, the session, chat messages, Memory, or any image job, and never
  calls a provider.

## Current KIRA

No owner-approved detailed editorial copy exists yet (the Accepted Package holds
only internal CRP data, which is not public copy). KIRA therefore shows the
restrained fallback short line and an empty detail body until Admin Studio
publishes a profile. **`OWNER_PUBLIC_COPY_REQUIRED`.**
