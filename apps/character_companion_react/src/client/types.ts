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
  listSessions(characterId: string): Promise<CompanionSession[]>;
  getSession(sessionId: string): Promise<CompanionSession>;
  createSession(characterId: string, input?: NewDialogInput): Promise<CompanionSession>;
  getMessages(sessionId: string): Promise<CompanionMessage[]>;
  sendMessage(sessionId: string, text: string): Promise<CompanionTurn>;
  randomScenario(opts?: { field?: SceneField; seed?: number }): Promise<RandomScenarioResult>;
  createImageJob(sessionId: string, kind: ImageJobKind, prompt?: string): Promise<ImageJob>;
  listImageJobs(sessionId: string): Promise<ImageJob[]>;
  setSceneCover(sessionId: string, resultRef: string): Promise<CompanionSession>;
}
