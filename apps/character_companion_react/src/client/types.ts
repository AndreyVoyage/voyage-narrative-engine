/**
 * Character Companion client contract (transport-neutral).
 *
 * Feature code NEVER calls fetch()/URLs directly -- it depends only on
 * `CompanionClient`. `HttpCompanionClient` is the sole file with HTTP concepts;
 * `MockCompanionClient` is an in-memory deterministic implementation for
 * structural checks and offline dev.
 *
 * This client exposes ONLY the five end-user Companion operations. There is no
 * debug / operator / workspace / memory-editor / evolution surface here.
 */

export interface CompanionCharacter {
  characterId: string;
  displayName: string;
  packageId: string | null;
  packageVersion: number | null;
  sourceHash: string | null;
}

export interface CompanionSession {
  sessionId: string;
  characterId: string;
  purpose: string; // always "COMPANION"
  createdAt: string;
  updatedAt: string;
  label: string;
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
  messages: CompanionMessage[];
}

/** A bounded, client-safe error. `code` is a small fixed vocabulary. */
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
  createSession(characterId: string): Promise<CompanionSession>;
  getMessages(sessionId: string): Promise<CompanionMessage[]>;
  sendMessage(sessionId: string, text: string): Promise<CompanionTurn>;
}
