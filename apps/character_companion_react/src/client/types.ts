/**
 * Character Companion client contract (transport-neutral).
 *
 * Feature code NEVER calls fetch()/URLs directly — it depends only on
 * `CompanionClient`. `HttpCompanionClient` is the sole file with HTTP concepts;
 * `MockCompanionClient` is an in-memory deterministic implementation.
 *
 * Cinematic first-release surface: catalog, multi-chat sessions with additive
 * scene metadata, conversation, deterministic random scenario, and the async
 * image-generation job boundary. No debug / operator / provider-settings
 * surface here.
 */

export interface CompanionCharacter {
  characterId: string;
  displayName: string;
  packageId: string | null;
  packageVersion: number | null;
  sourceHash: string | null;
  // ---- public-profile card summary (lightweight; full profile on demand) ----
  shortDescription: string;
  hasDetailedProfile: boolean;
  profileIsFallback: boolean;
}

/**
 * Curated PUBLIC editorial content for a character. This is a presentation
 * layer a future Admin Studio edits — never Character Package / Runtime /
 * Memory / Canon truth. It carries no CRP data, hashes, prompts, or provider
 * config.
 */
export type ProfileMediaType = "image" | "video";

export interface ProfileMedia {
  mediaId: string;
  mediaType: ProfileMediaType;
  sourceRef: string;          // transport-safe: "characters/…" or "images/…"
  thumbnailRef: string | null;
  title: string | null;
}

export interface ProfileSection {
  sectionId: string;
  title: string;
  body: string;
}

export interface CharacterPublicProfile {
  schemaVersion: string;
  characterId: string;
  displayName: string;
  shortDescription: string;
  longDescription: string;
  isFallback: boolean;
  primaryMediaId: string | null;
  sections: ProfileSection[];
  media: ProfileMedia[];
}

export const SCENE_FIELDS = ["place", "time", "situation", "mood"] as const;
export type SceneField = (typeof SCENE_FIELDS)[number];

export interface CompanionScene {
  place: string;
  time: string;
  situation: string;
  mood: string;
  freeform: string;
}

export function emptyScene(): CompanionScene {
  return { place: "", time: "", situation: "", mood: "", freeform: "" };
}

export function sceneHasAny(scene: CompanionScene | null | undefined): boolean {
  if (!scene) return false;
  return Boolean(scene.place || scene.time || scene.situation || scene.mood || scene.freeform);
}

export interface CompanionSession {
  sessionId: string;
  characterId: string;
  purpose: string; // always "COMPANION"
  createdAt: string;
  updatedAt: string;
  label: string;
  title: string;
  scene: CompanionScene | null;
  sceneCoverRef: string | null;
  lastMessagePreview: string;
  lastActivity: string;
  // ---- durable presentation metadata (never affects Character Memory) ----
  titleOverride: string | null;
  hidden: boolean;
  hiddenMessageIds: number[];
}

export type CompanionRole = "user" | "character";

export interface CompanionMessage {
  seq: number | null;
  role: CompanionRole;
  text: string;
  createdAt: string;
}

export interface CompanionTurn {
  sessionId: string;
  response: string;
  scenePresent: boolean;
  messages: CompanionMessage[];
}

export type ImageJobKind = "custom" | "context";
export type ImageJobState = "QUEUED" | "GENERATING" | "READY" | "FAILED" | "CANCELLED";

export type ImageReadinessStatus =
  | "READY"
  | "ROLE_UNASSIGNED"
  | "PROVIDER_NOT_CONFIGURED"
  | "MODEL_UNSUPPORTED"
  | "CREDENTIAL_MISSING"
  | "REFERENCE_CONDITIONING_UNSUPPORTED"
  | "UNVERIFIED_CAPABILITY"
  | "ACTIVE_SNAPSHOT_MISSING";

/** Provider-call-free readiness verdict for IMAGE_GENERATION. Safe product
 *  fields only — no credential, no provider base URL, no filesystem path. */
export interface ImageGenerationReadiness {
  status: ImageReadinessStatus;
  ready: boolean;
  providerId: string | null;
  modelId: string | null;
  unverified: boolean;
  reasonCode: string | null;
  messageKey: string;
}

export interface ImageJob {
  jobId: string;
  sessionId: string;
  characterId: string;
  kind: ImageJobKind;
  state: ImageJobState;
  createdAt: string;
  updatedAt: string;
  prompt: string | null;
  resultRef: string | null;
  error: string | null;
}

export interface RandomScenarioResult {
  scenario?: Record<SceneField, string>;
  field?: SceneField;
  value?: string;
}

export interface NewDialogInput {
  title?: string;
  scene?: CompanionScene;
}

// ---- secure provider settings ----------------------------------------

/** Canonical model-role ids (DIALOGUE is the only runtime-wired one). */
export const MODEL_ROLES = [
  "DIALOGUE", "VISION", "IMAGE_GENERATION", "VIDEO_GENERATION",
  "STT", "TTS", "REALTIME", "WRITING_ASSISTANT", "LOCAL_ALTERNATIVE",
] as const;
export type ModelRole = (typeof MODEL_ROLES)[number];

/** Which co-author mode the backend derived from the draft. */
export type WritingAssistantMode = "COMPOSE" | "EXPAND";

/** Result of one composer co-author call. `mode` is derived by the backend
 *  ("" -> COMPOSE, non-empty -> EXPAND); the client never sends it. */
export interface WritingAssistantResult {
  suggestion: string;
  provider: string;
  model: string;
  mode?: WritingAssistantMode;
}

export type RoleReadiness =
  | "READY"
  | "CONFIGURED_CREDENTIAL_MISSING"
  | "NOT_CONFIGURED"
  | "UNSUPPORTED"
  | "FUTURE_NOT_WIRED";

/** One entry in a provider's data-driven model catalog. */
export interface ModelView {
  modelId: string;
  displayName: string;
  capabilities: string[];
  roles: string[];
  status: "available" | "unverified" | "deprecated" | string;
  notes: string;
  contentPolicyProfile: string;
  supportsReferenceImage: boolean | null;
  supportsImageToImage: boolean | null;
  supportsCharacterReference: boolean | null;
  supportsVideo: boolean | null;
  maxDurationSeconds: number | null;
}

export interface ProviderCardView {
  providerId: string;
  displayName: string;
  kind: "cloud" | "local";
  transport: string;
  credentialRequired: boolean;
  defaultBaseUrl: string;
  supportedRoles: string[];
  runtimeWiredRoles: string[];
  capabilities: string[];
  modelCatalog: string[];          // backward-compatible id list
  models: ModelView[];
  defaultModel: string;
  notes: string;
  connected: boolean;
  configuredModel: string;
  maskedTail: string | null;
  lastTestStatus: string | null;
}

/** Provider-call-free resolution metadata for one model role. */
export interface RoleResolution {
  role: string;
  runtimeWired: boolean;
  providerId: string | null;
  modelId: string | null;
  providerConnected: boolean;
  credentialRequired: boolean;
  maskedTail: string | null;
  capabilities: string[];
  contentPolicyProfile: string;
  modelStatus: string | null;
  readiness: RoleReadiness;
}

export interface RoleCatalogEntry extends RoleResolution {
  providerIds: string[];           // providers whose catalog can serve this role
}

export interface LocalSettingsView {
  numCtx: number | null;
  baseUrl: string;
  model: string;
  numCtxMin: number;
  numCtxMax: number;
  kiraSafeHint: number;
  numCtxWarning: boolean;
}

/**
 * Provider-independent DIALOGUE operational context budget (V1C backend).
 * `estTokens` is an ESTIMATED sizing value — not an exact provider token count,
 * not the provider context window, not the Ollama local `num_ctx`.
 */
export interface DialogueContextBudgetView {
  estTokens: number;
  min: number;
  default: number;
  max: number;
}

export interface CompanionSettingsView {
  providers: ProviderCardView[];
  roles: Record<string, { providerId: string; modelId: string }>;
  roleCatalog: RoleCatalogEntry[];
  allRoles: string[];
  roleDisplayOrder: string[];
  runtimeWiredRoles: string[];
  local: LocalSettingsView;
  dialogueContextBudget: DialogueContextBudgetView;
  allowCloudFallback: boolean;
  dataRoutingNote: string;
}

export interface ProviderTestResult {
  providerId: string;
  ok: boolean;
  status: string;
  message?: string;
}

export interface ReleaseInfo {
  release: { name: string; version: string; channel: string };
  mode: "dev" | "release";
  dialogueProvider: string;
  acceptedCharacter: { characterId: string; packageId: string; sourceHash: string };
  localContext: { recommendedMinNumCtx: number; kiraGroundedObservedPromptTokens: number };
}

export class CompanionClientError extends Error {
  readonly code: string;
  readonly status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "CompanionClientError";
    this.code = code;
    this.status = status;
  }
}

export interface CompanionClient {
  listCharacters(): Promise<CompanionCharacter[]>;
  getCharacterProfile(characterId: string): Promise<CharacterPublicProfile>;
  listSessions(characterId: string): Promise<CompanionSession[]>;
  getSession(sessionId: string): Promise<CompanionSession>;
  createSession(characterId: string, input?: NewDialogInput): Promise<CompanionSession>;
  renameSession(sessionId: string, title: string): Promise<CompanionSession>;
  setSessionHidden(sessionId: string, hidden: boolean): Promise<CompanionSession>;
  setMessageHidden(sessionId: string, messageId: number, hidden: boolean): Promise<CompanionSession>;
  getMessages(sessionId: string): Promise<CompanionMessage[]>;
  sendMessage(sessionId: string, text: string): Promise<CompanionTurn>;
  /** V2 contextual co-author. `draft` MAY be empty (COMPOSE); non-empty is
   *  EXPAND. The backend derives the mode — never pass one. */
  suggestDraft(
    draft: string,
    opts?: { localeHint?: string | null; sessionId?: string | null },
  ): Promise<WritingAssistantResult>;
  /** Legacy composer rewrite — non-empty draft only, EXPAND semantics. */
  rewriteDraft(draft: string, opts?: { localeHint?: string }): Promise<WritingAssistantResult>;
  randomScenario(opts?: { field?: SceneField; seed?: number }): Promise<RandomScenarioResult>;
  imageGenerationReadiness(characterId: string): Promise<ImageGenerationReadiness>;
  createImageJob(sessionId: string, kind: ImageJobKind, prompt?: string): Promise<ImageJob>;
  listImageJobs(sessionId: string): Promise<ImageJob[]>;
  setSceneCover(sessionId: string, resultRef: string): Promise<CompanionSession>;
  getSettings(): Promise<CompanionSettingsView>;
  setRole(role: string, providerId: string, modelId: string): Promise<CompanionSettingsView>;
  setLocalSettings(input: { numCtx?: number | null; baseUrl?: string | null }): Promise<CompanionSettingsView>;
  setDialogueContextBudget(value: number): Promise<CompanionSettingsView>;
  storeCredential(providerId: string, secret: string): Promise<CompanionSettingsView>;
  deleteCredential(providerId: string): Promise<CompanionSettingsView>;
  testProvider(providerId: string, modelId?: string): Promise<ProviderTestResult>;
  resolveRole(role: string): Promise<RoleResolution>;
  getReleaseInfo(): Promise<ReleaseInfo>;
}
