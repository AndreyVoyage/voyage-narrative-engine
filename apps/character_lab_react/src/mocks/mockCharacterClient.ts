/**
 * MockCharacterClient -- an in-memory, deterministic `CharacterClient`
 * implementation. Lets React UI be built and exercised before any transport
 * (direct/local adapter, IPC, HTTP) is chosen. No network, no Python, no
 * real Accepted Package data -- everything here is synthesized dev-only
 * fixture data (see `mockData.ts`).
 */

import type { CharacterClient } from "../client/characterClient.js";
import {
  SessionPurpose,
  SessionPurposeNotImplementedError,
  isSessionPurposeSupported,
  type CapabilitySet,
  type ChatTurnResult,
  type CharacterSession,
  type CharacterSummary,
  type CharacterVariantSummary,
  type MemoryEventSummary,
  type MemorySummary,
  type RuntimeStateEntrySummary,
  type RuntimeStateSummary,
  type SceneSummary,
  type SetSceneInput,
  type WorkspaceSummary,
} from "../client/types.js";
import {
  MOCK_CHARACTER_ID,
  MOCK_NORMAL_WORKSPACE_ID,
  makeMockCleanTestWorkspace,
  makeMockNormalWorkspace,
  mockCapabilities,
  mockCharacter,
  mockVariants,
} from "./mockData.js";

let idCounter = 0;
function nextId(prefix: string): string {
  idCounter += 1;
  return `${prefix}-mock-${idCounter.toString().padStart(4, "0")}`;
}

export class MockCharacterClient implements CharacterClient {
  private readonly workspaces = new Map<string, WorkspaceSummary>();
  private readonly sessions = new Map<string, CharacterSession>();
  private readonly memoryByWorkspace = new Map<string, MemoryEventSummary[]>();
  private readonly stateByWorkspace = new Map<string, RuntimeStateEntrySummary[]>();
  private readonly sceneBySession = new Map<string, SceneSummary>();
  private selectedVariantId = "KIRA_BETA_V1_CURRENT";
  private selectedWorkspaceId: string;

  constructor() {
    this.workspaces.set(MOCK_NORMAL_WORKSPACE_ID, makeMockNormalWorkspace(false));
    const firstWorkspaceId = nextId("test");
    this.workspaces.set(firstWorkspaceId, makeMockCleanTestWorkspace(firstWorkspaceId, true));
    this.selectedWorkspaceId = firstWorkspaceId;
  }

  // ------------------------------------------------------------- catalog

  async listCharacters(): Promise<readonly CharacterSummary[]> {
    return [mockCharacter];
  }

  async getCharacter(characterId: string): Promise<CharacterSummary> {
    this.requireKnownCharacter(characterId);
    return mockCharacter;
  }

  async listVariants(characterId: string): Promise<readonly CharacterVariantSummary[]> {
    this.requireKnownCharacter(characterId);
    return mockVariants.map((v) => ({ ...v, selected: v.variantId === this.selectedVariantId }));
  }

  async capabilities(characterId: string): Promise<CapabilitySet> {
    this.requireKnownCharacter(characterId);
    return mockCapabilities;
  }

  private requireKnownCharacter(characterId: string): void {
    if (characterId !== MOCK_CHARACTER_ID) {
      throw new Error(`unknown character '${characterId}'`);
    }
  }

  // ----------------------------------------------------------- workspaces

  async listWorkspaces(): Promise<readonly WorkspaceSummary[]> {
    return [...this.workspaces.values()].map((w) => ({
      ...w,
      selected: w.workspaceId === this.selectedWorkspaceId,
    }));
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
    const found = this.workspaces.get(workspaceId);
    if (!found) throw new Error(`unknown workspace '${workspaceId}'`);
    return { ...found, selected: workspaceId === this.selectedWorkspaceId };
  }

  async createTestWorkspace(): Promise<WorkspaceSummary> {
    const workspaceId = nextId("test");
    const workspace = makeMockCleanTestWorkspace(workspaceId, false);
    this.workspaces.set(workspaceId, workspace);
    return workspace;
  }

  private requireWorkspace(workspaceId: string): WorkspaceSummary {
    const found = this.workspaces.get(workspaceId);
    if (!found) throw new Error(`unknown workspace '${workspaceId}'`);
    return found;
  }

  // ------------------------------------------------------------ sessions

  async createSession(
    characterId: string,
    variantId: string,
    purpose: SessionPurpose,
    workspaceId: string
  ): Promise<CharacterSession> {
    this.requireKnownCharacter(characterId);
    if (!isSessionPurposeSupported(purpose)) {
      throw new SessionPurposeNotImplementedError(purpose);
    }
    const workspace = this.requireWorkspace(workspaceId); // must already exist
    const variant = mockVariants.find((v) => v.variantId === variantId);
    if (!variant || !variant.implemented) {
      throw new Error(`variant unavailable: '${variantId}'`);
    }
    this.selectedVariantId = variantId;
    this.selectedWorkspaceId = workspaceId;

    const session: CharacterSession = {
      sessionId: nextId("session"),
      characterId,
      variantId,
      purpose,
      workspace: { ...workspace, selected: true },
    };
    this.sessions.set(session.sessionId, session);
    return session;
  }

  async getSession(sessionId: string): Promise<CharacterSession> {
    const found = this.sessions.get(sessionId);
    if (!found) throw new Error(`unknown session '${sessionId}'`);
    return found;
  }

  // ----------------------------------------------------------------- chat

  async sendMessage(sessionId: string, text: string): Promise<ChatTurnResult> {
    const session = await this.getSession(sessionId);
    const workspaceId = session.workspace.workspaceId;
    const events = this.memoryByWorkspace.get(workspaceId) ?? [];

    const response = `(демо-ответ) ${text}`.trim();
    const nextSeq = events.length + 1;
    events.push({
      seq: nextSeq,
      eventId: nextId("evt"),
      sessionId,
      eventType: "USER_MESSAGE",
      provenance: "USER_STATED",
      meaning: text,
    });
    events.push({
      seq: nextSeq + 1,
      eventId: nextId("evt"),
      sessionId,
      eventType: "CHARACTER_MESSAGE",
      provenance: "CHARACTER_UTTERANCE",
      meaning: response,
    });
    this.memoryByWorkspace.set(workspaceId, events);

    return {
      turnId: nextId("turn"),
      sessionId,
      characterId: session.characterId,
      variantId: session.variantId,
      response,
      requestHash: nextId("hash"),
      scenePresent: this.sceneBySession.get(sessionId)?.active ?? false,
    };
  }

  // --------------------------------------------------------------- memory

  async getMemory(workspaceId: string): Promise<MemorySummary> {
    this.requireWorkspace(workspaceId);
    const events = this.memoryByWorkspace.get(workspaceId) ?? [];
    return {
      workspaceId,
      causalOrder: "seq",
      eventCount: events.length,
      events: [...events],
    };
  }

  // ---------------------------------------------------------- runtime state

  async getRuntimeState(workspaceId: string): Promise<RuntimeStateSummary> {
    this.requireWorkspace(workspaceId);
    const current = this.stateByWorkspace.get(workspaceId) ?? [];
    return {
      workspaceId,
      domainsActive: ["FACT", "RELATIONSHIP", "PSYCHOLOGY"],
      current: [...current],
      currentCount: current.length,
    };
  }

  // -------------------------------------------------------------- scene

  async getScene(sessionId: string): Promise<SceneSummary> {
    const session = await this.getSession(sessionId);
    return (
      this.sceneBySession.get(sessionId) ?? {
        sessionId,
        workspaceId: session.workspace.workspaceId,
        active: false,
      }
    );
  }

  async setScene(sessionId: string, input: SetSceneInput): Promise<SceneSummary> {
    const session = await this.getSession(sessionId);
    const scene: SceneSummary = {
      sessionId,
      workspaceId: session.workspace.workspaceId,
      active: true,
      title: input.title ?? "",
      location: input.location ?? "",
      sceneHash: nextId("scenehash"),
    };
    this.sceneBySession.set(sessionId, scene);
    return scene;
  }

  async clearScene(sessionId: string): Promise<SceneSummary> {
    const session = await this.getSession(sessionId);
    this.sceneBySession.delete(sessionId);
    return { sessionId, workspaceId: session.workspace.workspaceId, active: false };
  }
}
