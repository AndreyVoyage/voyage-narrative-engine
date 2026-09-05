/**
 * Character Core Contract v1 -- TypeScript-side DTO mirror.
 *
 * This is the frontend representation of the ALREADY-COMMITTED Python
 * boundary in `services/character_core/contract.py`. It is not a second
 * backend contract, and it must stay transport-neutral: no URLs, fetch(),
 * HTTP status codes, headers, or REST paths belong in this file. Field
 * names are camelCase; shapes otherwise mirror the Python dataclasses
 * one-to-one so a future transport adapter is a pure mapping exercise.
 *
 * Framework-free: no React import here. Safe to typecheck/execute without
 * any UI dependency installed.
 */

// ---------------------------------------------------------------------------
// Session purpose
// ---------------------------------------------------------------------------

/**
 * Recognized architectural session purposes. Recognizing a purpose here is
 * NOT the same as a concrete client/backend implementing its behavioral
 * policy today -- see {@link SUPPORTED_SESSION_PURPOSES}.
 */
export enum SessionPurpose {
  TESTING = "TESTING",
  AUTHORING = "AUTHORING",
  GAME_RUNTIME = "GAME_RUNTIME",
  COMPANION = "COMPANION",
}

/** The full recognized vocabulary, in a stable, iterable order. */
export const ALL_SESSION_PURPOSES: readonly SessionPurpose[] = [
  SessionPurpose.TESTING,
  SessionPurpose.AUTHORING,
  SessionPurpose.GAME_RUNTIME,
  SessionPurpose.COMPANION,
];

/**
 * Purposes the CURRENT client/backend combination actually implements.
 * Contract v1 / the local mock and the Python local adapter both implement
 * only TESTING -- the other three are reserved vocabulary with deferred
 * semantics, never silently mapped onto TESTING.
 */
export const SUPPORTED_SESSION_PURPOSES: readonly SessionPurpose[] = [
  SessionPurpose.TESTING,
];

export function isSessionPurposeSupported(purpose: SessionPurpose): boolean {
  return SUPPORTED_SESSION_PURPOSES.includes(purpose);
}

/**
 * Thrown by a {@link CharacterClient} implementation (mock or real) when
 * asked to create a session for a recognized-but-unimplemented purpose.
 * Never a silent fallback to TESTING.
 */
export class SessionPurposeNotImplementedError extends Error {
  readonly purpose: SessionPurpose;
  constructor(purpose: SessionPurpose) {
    super(
      `SessionPurpose.${purpose} is a recognized architectural purpose but ` +
        "is not implemented by this client/backend"
    );
    this.name = "SessionPurposeNotImplementedError";
    this.purpose = purpose;
  }
}

/**
 * Thrown by a {@link CharacterClient} implementation when a capability the
 * interface declares is not wired up by the CURRENT transport (e.g. Memory /
 * Runtime State / Scene in `HttpCharacterClient`'s Desktop Integration v1).
 * A deterministic, typed signal -- never a silent mock-data substitution
 * presented as if it came from Core, and never a raw transport-level error
 * (a failed `fetch`, a 404) that would be ambiguous with a genuine backend
 * failure.
 */
export class NotIntegratedInTransportError extends Error {
  readonly capability: string;
  constructor(capability: string) {
    super(
      `'${capability}' is not integrated in this transport yet -- ` +
        "see the transport's own documentation for what it currently covers"
    );
    this.name = "NotIntegratedInTransportError";
    this.capability = capability;
  }
}

// ---------------------------------------------------------------------------
// Capabilities
// ---------------------------------------------------------------------------

/** The full vocabulary of capability names a backend MAY resolve as present. */
export const KNOWN_CAPABILITIES = [
  "chat",
  "memory",
  "runtime_state",
  "relationship_state",
  "psychology_state",
  "scene",
  "turn_debugger",
  "provider_configured",
] as const;

export type CapabilityName = (typeof KNOWN_CAPABILITIES)[number];

export interface CapabilitySet {
  readonly capabilities: readonly CapabilityName[];
}

export function hasCapability(set: CapabilitySet, name: CapabilityName): boolean {
  return set.capabilities.includes(name);
}

// ---------------------------------------------------------------------------
// Character / package / variant / workspace DTOs
// ---------------------------------------------------------------------------

/**
 * Identifies an Accepted Character Package independently from Core. A
 * REFERENCE only -- identity + acceptance status, never the package's
 * claims/content (Character Core and Character Package have independent
 * versions per OD-CHAR-CORE-RELEASE-01).
 */
export interface CharacterPackageRef {
  readonly characterId: string;
  readonly packageId: string;
  readonly packageVersion: number;
  readonly sourceHash: string;
  readonly acceptanceDecision: string;
  readonly candidateStatus: string;
}

export interface CharacterVariantSummary {
  readonly variantId: string;
  readonly displayName: string;
  readonly implemented: boolean;
  readonly status?: string;
  readonly selected: boolean;
}

export interface CharacterSummary {
  readonly characterId: string;
  readonly displayName: string;
  readonly supported: boolean;
  readonly packageRef?: CharacterPackageRef;
}

/**
 * Minimal, path-free workspace identity: no filesystem path, no SQLite
 * filename, no turn-capture directory -- only an opaque id, its kind
 * (`CLEAN_TEST` / `NORMAL`), and a display name. A workspace MAY host
 * multiple sessions (see {@link CharacterClient.createSession}).
 */
export interface WorkspaceSummary {
  readonly workspaceId: string;
  readonly workspaceKind: "CLEAN_TEST" | "NORMAL";
  readonly displayName: string;
  readonly selected: boolean;
}

/** A live session bound to one character + variant + purpose, hosted in
 * exactly one EXPLICIT workspace (never silently created). */
export interface CharacterSession {
  readonly sessionId: string;
  readonly characterId: string;
  readonly variantId: string;
  readonly purpose: SessionPurpose;
  readonly workspace: WorkspaceSummary;
  readonly createdAt?: string;
}

export interface ChatTurnResult {
  readonly turnId: string;
  readonly sessionId: string;
  readonly characterId: string;
  readonly variantId: string;
  readonly response: string;
  readonly requestHash?: string;
  readonly scenePresent: boolean;
}

// ---------------------------------------------------------------------------
// Runtime State / Memory / Scene DTOs
// ---------------------------------------------------------------------------

export type RuntimeStateDomain = "FACT" | "RELATIONSHIP" | "PSYCHOLOGY";

/** One current Runtime State fact -- explicitly operator-confirmed only;
 * never automatically promoted from memory, model output, or Scene. */
export interface RuntimeStateEntrySummary {
  readonly domain: RuntimeStateDomain;
  readonly key: string;
  readonly value: string;
  readonly valueInt: number | null;
  readonly sourceKind: string;
  readonly sourceRef: string | null;
  readonly seq: number | null;
}

/** Current Runtime State for one workspace (workspace-scoped). */
export interface RuntimeStateSummary {
  readonly workspaceId: string;
  readonly domainsActive: readonly RuntimeStateDomain[];
  readonly current: readonly RuntimeStateEntrySummary[];
  readonly currentCount: number;
}

/** One causal runtime-memory event, with its honest provenance label. */
export interface MemoryEventSummary {
  readonly seq: number | null;
  readonly eventId: string;
  readonly sessionId: string;
  readonly eventType: string;
  readonly provenance: string;
  readonly meaning: string;
}

/** Causal-order runtime memory for one workspace (workspace-scoped). */
export interface MemorySummary {
  readonly workspaceId: string;
  readonly causalOrder: string;
  readonly eventCount: number;
  readonly events: readonly MemoryEventSummary[];
}

/** Session-scoped situational Scene setup -- never Accepted Package data,
 * never durable memory. */
export interface SceneSummary {
  readonly sessionId: string | null;
  readonly workspaceId: string | null;
  readonly active: boolean;
  readonly title?: string;
  readonly location?: string;
  readonly sceneHash?: string;
}

export interface SetSceneInput {
  readonly title?: string;
  readonly location?: string;
  readonly participants?: readonly string[];
  readonly priorEvents?: readonly string[];
  readonly currentSituation?: string;
}

// ---------------------------------------------------------------------------
// Debug / observability DTOs
// ---------------------------------------------------------------------------

/** One captured turn, listing-level detail only. */
export interface TurnSummary {
  readonly turnId: string;
  readonly sessionId: string | null;
  readonly variantId: string | null;
  readonly requestHash: string | null;
  readonly responsePreview: string | null;
  readonly scenePresent: boolean;
  readonly hasError: boolean;
  readonly createdAt: string | null;
}

/** One assembly-manifest item: request text mapped back to its source, with
 * SELECTED (always true for a captured item) / DELIVERED proven only from
 * the exact captured provider request bytes. */
export interface ManifestItemSummary {
  readonly kind: string;
  readonly text: string;
  readonly selected: boolean;
  readonly delivered: boolean;
}

/** The deterministic assembly manifest for one turn. */
export interface ContextManifestSummary {
  readonly turnId: string;
  readonly variantId: string | null;
  readonly assemblyHash: string | null;
  readonly items: readonly ManifestItemSummary[];
}

/** The exact captured transport request for one turn (source of truth for
 * DELIVERED) -- never provider reasoning/chain-of-thought, which this
 * contract does not expose at all. */
export interface RequestCaptureSummary {
  readonly turnId: string;
  readonly requestHash: string | null;
  readonly rawRequestJson: string | null;
}

/** One turn's full developer-observability bundle. */
export interface TurnDebugBundle {
  readonly turn: TurnSummary;
  readonly manifest: ContextManifestSummary;
  readonly request: RequestCaptureSummary;
}
