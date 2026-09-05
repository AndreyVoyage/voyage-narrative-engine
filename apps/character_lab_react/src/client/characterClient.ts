/**
 * CharacterClient -- the TypeScript client representation of the already
 * committed logical `CharacterService` Python contract
 * (`services/character_core/contract.py`). It covers only the capabilities
 * already present in CharacterService v1.
 *
 * Transport-neutral by construction: every method takes/returns plain DTOs
 * and Promises. No URL, fetch(), HTTP verb/status code, header, or REST path
 * concept appears anywhere in this interface. A concrete implementation may
 * be a mock (see `src/mocks`), a future direct/local adapter, an IPC bridge,
 * or an HTTP client -- this file must never assume which.
 *
 * Workspace ownership is explicit, not global mutable client state: resolve
 * or create a workspace FIRST (`listWorkspaces` / `getWorkspace` /
 * `createTestWorkspace`), then pass its id into `createSession`. A workspace
 * may host multiple sessions.
 *
 * Scope, matching the existing Character Lab semantics exactly:
 * - Memory is workspace-scoped (`getMemory(workspaceId)`);
 * - Runtime State is workspace-scoped (`getRuntimeState(workspaceId)`);
 * - Scene is session-scoped (`getScene` / `setScene` / `clearScene`).
 */

import type {
  CapabilitySet,
  ChatTurnResult,
  CharacterSession,
  CharacterSummary,
  CharacterVariantSummary,
  MemorySummary,
  RuntimeStateSummary,
  SceneSummary,
  SessionPurpose,
  SetSceneInput,
  WorkspaceSummary,
} from "./types.js";

export interface CharacterClient {
  // ------------------------------------------------------------- catalog
  listCharacters(): Promise<readonly CharacterSummary[]>;
  getCharacter(characterId: string): Promise<CharacterSummary>;
  listVariants(characterId: string): Promise<readonly CharacterVariantSummary[]>;
  capabilities(characterId: string): Promise<CapabilitySet>;

  // ----------------------------------------------------------- workspaces
  listWorkspaces(): Promise<readonly WorkspaceSummary[]>;
  getWorkspace(workspaceId: string): Promise<WorkspaceSummary>;
  createTestWorkspace(): Promise<WorkspaceSummary>;

  // ------------------------------------------------------------ sessions
  createSession(
    characterId: string,
    variantId: string,
    purpose: SessionPurpose,
    workspaceId: string
  ): Promise<CharacterSession>;
  getSession(sessionId: string): Promise<CharacterSession>;

  // ----------------------------------------------------------------- chat
  sendMessage(sessionId: string, text: string): Promise<ChatTurnResult>;

  // --------------------------------------------------------------- memory
  getMemory(workspaceId: string): Promise<MemorySummary>;

  // ---------------------------------------------------------- runtime state
  getRuntimeState(workspaceId: string): Promise<RuntimeStateSummary>;

  // -------------------------------------------------------------- scene
  getScene(sessionId: string): Promise<SceneSummary>;
  setScene(sessionId: string, input: SetSceneInput): Promise<SceneSummary>;
  clearScene(sessionId: string): Promise<SceneSummary>;
}
