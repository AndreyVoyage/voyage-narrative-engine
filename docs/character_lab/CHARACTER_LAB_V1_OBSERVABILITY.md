# Character Lab V1 Observability Contract

Status: DOCUMENTATION BASELINE (read-only). This document is the evidence
contract for Character Lab: what can be proven, and how. CURRENT describes the
repository as it exists today; TARGET/PLANNED describe accepted direction only.

---

## 1. Core principle

Character Lab must display what the runtime can prove.

It must NOT convert:

- stored state;
- intended context;
- model self-report;
- UI labels;

into unsupported claims about what the model actually received or used.

---

## 2. STORED / LOADED / SELECTED / DELIVERED

Records OD-CL-04 (ACCEPTED).

These states are NOT interchangeable:

- `STORED` — information exists in a source/store.
- `LOADED` — runtime loaded/resolved it.
- `SELECTED` — context assembly selected it for this exact turn.
- `DELIVERED` — it is mechanically proven to exist in the actual captured
  provider request.

Core invariant:

```
STORED ≠ LOADED ≠ SELECTED ≠ DELIVERED
```

`DELIVERED` may only be claimed from the captured provider request artifact.
Never infer `DELIVERED` from package load success, memory existence, UI state,
or context-selection intent.

Examples:

Psychology claims:

- STORED = YES
- LOADED = YES
- SELECTED = NO
- DELIVERED = NO

Runtime memory `event_018`:

- STORED = YES
- LOADED = YES
- SELECTED = YES
- DELIVERED = YES

`DELIVERED` requires captured-request evidence.

---

## 3. Current provider boundary

Verified current path (CURRENT):

```
tools/kira_chat_cli.py
    ->
tools/crp_provider_adapter.py
    ->
tools/llm_provider.complete()
    ->
_complete_cloud()
    ->
_post_json()
    ->
urllib.request.urlopen()
```

Current exact request payload:

- The `payload` dict is built in `_complete_cloud`
  (`tools/llm_provider.py`): `{ "model": ..., "messages": ..., ...extra }`.
- The exact transport body is `json.dumps(payload, ensure_ascii=False).encode("utf-8")`
  in `_post_json`, immediately before `urlopen`.

Because the current transport is hand-written `urllib` and `request.data` is the
same body bytes, V1 can target byte-for-byte request-body capture.

---

## 4. Exact Context Snapshot

Target invariant:

```
request_hash = SHA-256(exact transport body bytes)
```

The captured request artifact is source-of-truth. The UI must project from this
artifact, not from a separate UI-side context reconstruction.

Possible target artifact:

```
turns/<turn_id>/request.json
```

It must represent the actual request bytes/body used by transport.

Credentials / `Authorization` header must never be captured.

---

## 5. Assembly Manifest

Because the provider request may contain flattened prompt text, V1 may maintain
a parallel deterministic assembly manifest.

The manifest must be created by the SAME context assembly operation and must be
cryptographically/logically bound to the captured request hash.

Possible entries:

- `system.role_instruction`
- `system.package_identity`
- `system.memory_line`
- `system.scene`
- `history.user`
- `history.assistant`
- `user.current`

Each entry may carry source metadata such as:

- `event_id`
- `session_id`
- `provenance`
- `sequence`
- `scene_id`
- `accepted_source_hash`

The manifest is NOT evidence by itself that delivery occurred. `DELIVERED`
requires verification against the captured request.

---

## 6. Turn artifacts

Target minimal append-only artifact set:

```
turns/<turn_id>/
    request.json
    manifest.json
    response.json
```

or, on failure:

```
turns/<turn_id>/error.json
```

A turn index may reference artifacts by `turn_id`.

Artifacts should survive:

- provider error;
- timeout;
- parsing failure;
- runtime persistence failure;
- session close.

Request capture must occur before provider transport completes.

---

## 7. Provider/model attribution

Capture from actual provider configuration/request:

- `provider_id`
- requested model
- `base_url`
- `timeout`
- `max_tokens`
- `json_mode` / response format
- thinking/reasoning config if present
- attempt count
- retry/fallback behavior

From response, where available:

- `finish_reason`
- usage
- response/request id
- provider-reported model

UI terminology: `REQUESTED MODEL` and `PROVIDER-REPORTED MODEL` must remain
distinct where applicable.

Never expose:

- API key;
- Authorization header;
- environment values.

The credential env variable NAME may be shown if useful.

---

## 8. Memory ordering

Current defect (verified against `services/character_runtime/memory.py`):

- `created_at` is second precision (`datetime.now(...).replace(microsecond=0)`);
- `event_id` is a random UUID;
- `ORDER BY created_at, event_id` does not guarantee causal ordering.

`USER_MESSAGE` and `CHARACTER_MESSAGE` written within the same second can tie on
`created_at`, and UUID tie-breaking is not causal — explaining observed cases
where `CHARACTER_MESSAGE` appears before its causal `USER_MESSAGE`.

Target V1 observability: add a stable monotonic causal sequence. Inspector order
uses the sequence as authority.

OD-CL-02 (ACCEPTED): `KIRA_BETA_V1_CURRENT` prompt assembly still preserves
legacy ordering. Do not confuse Inspector order with baseline provider-context
order.

---

## 9. Provenance model

Advisor-recommended minimal V1 taxonomy:

- `PACKAGE_FACT`
- `USER_STATED`
- `CHARACTER_UTTERANCE`
- `SCENE_SETUP`
- `LEGACY_UNCLASSIFIED`

Definitions:

`PACKAGE_FACT`

- Source content from the accepted package.
- Primarily manifest/inspection provenance.
- Not a runtime memory fact created by dialogue.

`USER_STATED`

- User utterance.
- Proves only that the user said it.
- Does not automatically prove world truth.

`CHARACTER_UTTERANCE`

- Model-generated KIRA utterance.
- Proves only that KIRA/model said it.
- Must NEVER automatically become established truth.

`SCENE_SETUP`

- Owner-authored scene truth scoped to the active scene/session.
- Not package truth.
- Not automatically permanent memory.

`LEGACY_UNCLASSIFIED`

- Pre-provenance runtime rows.
- Leave unchanged.
- Do not fabricate a historical provenance backfill.

Explicitly defer (Grounded v2 / later):

- `MODEL_HYPOTHESIS`
- `CONFIRMED_RUNTIME_FACT`
- automatic promotion rules.

---

## 10. Beta v1 observational compatibility

Core rule: provenance and sequence metadata may be stored for observation if
they are NOT rendered into `KIRA_BETA_V1_CURRENT` provider context.

For Beta v1:

- existing `event_type` + `meaning` prompt representation must remain
  behaviorally unchanged;
- new provenance labels must not leak into request text.

Captured request bytes provide the future regression proof.

---

## 11. Turn Debugger contract

MECHANICALLY PROVEN may include:

- request bytes/artifact;
- request hash;
- character ID;
- variant ID;
- accepted source hash;
- workspace;
- session;
- manifest source items verified present in request;
- exact user message;
- requested provider/model/config;
- response;
- `finish_reason` if captured;
- new runtime event IDs;
- event sequence/provenance;
- persisted status;
- accepted package unchanged invariant.

POST-HOC / NON-AUTHORITATIVE:

- future analyses such as unsupported-claim detection.

NOT CLAIMABLE:

- "the model relied on event X";
- "the model ignored rule Y";
- attention/salience claims;
- hidden reasoning;
- numeric hallucination-risk percentage;
- model utterance automatically became truth.

---

## 12. Unsupported assertion detection

V1 decision: DEFER automated hallucination/unsupported-assertion detector.

Reason: current package claims are not sufficiently typed for a narrow
deterministic general detector, and an LLM post-hoc analyzer would create false
certainty.

V1 provides raw evidence for manual diagnosis. A future analyzer must be labeled
`NON-AUTHORITATIVE ANALYSIS` and must not emit fake precision.

---

## 13. Reproducibility contract

Minimum per-turn/run identity should include:

- `character_id`
- `acceptance_id`
- `accepted_source_hash`
- `package_id`
- `package_version`
- `source_artifact_hash`
- `variant_id`
- `variant_version`
- runtime code Git SHA
- `workspace_id`
- starting memory identity/hash
- scene identity/content
- `session_id`
- `provider_id`
- requested model
- effective provider config
- request artifact
- `request_hash`
- assembly manifest
- `assembly_hash`
- response/error artifact
- `response_hash` if applicable
- new runtime event IDs
- event seq/provenance
- session-close package hash invariant

---

## 14. Canonical source dependency

CURRENT:

- runtime KIRA source bytes depend on external RUN_015 artifact
  (`C:\DEV\Narrative\LOCAL_STORAGE\crp_r4_live_runs\RUN_015.stdout.json`).

RATIFIED TARGET via OD-CL-01:

- materialize immutable exact source Candidate alongside acceptance.

Do not implement here.
