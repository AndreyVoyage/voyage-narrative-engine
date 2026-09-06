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
  type CandidateDecisionStatus,
  type CapabilitySet,
  type ChatTurnResult,
  type CharacterSession,
  type CharacterSummary,
  type CharacterVariantSummary,
  type ConsolidatedMemoryRecordSummary,
  type ConsolidatedRelationKind,
  type MemoryEventInspection,
  type MemoryEventList,
  type MemoryEventSummary,
  type MemoryKind,
  type MemoryPromotionCandidateSummary,
  type MemoryRelationSummary,
  type MemorySummary,
  type PromotionDecision,
  type RuntimeStateDomain,
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
  private readonly candidatesByWorkspace = new Map<string, MemoryPromotionCandidateSummary[]>();
  private readonly recordsByWorkspace = new Map<string, ConsolidatedMemoryRecordSummary[]>();
  private readonly relationsByWorkspace = new Map<string, MemoryRelationSummary[]>();
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

  // ---------------------------------- consolidated memory (operator-driven)
  // The mock mirrors the backend's externally visible behavior (eligibility,
  // final decisions, dedupe, relation rules) so UI development needs no
  // backend; the Python backend remains the authority in "local" mode.

  private static assessEligibility(
    event: MemoryEventSummary
  ): { eligible: boolean; reason: string | null } {
    if (event.eventType !== "USER_MESSAGE") {
      return { eligible: false, reason: "not_a_user_message" };
    }
    if (event.provenance !== "USER_STATED") {
      return { eligible: false, reason: "not_user_stated" };
    }
    if (!event.meaning.trim()) {
      return { eligible: false, reason: "empty_content" };
    }
    return { eligible: true, reason: null };
  }

  async listMemoryEvents(workspaceId: string): Promise<MemoryEventList> {
    this.requireWorkspace(workspaceId);
    const events = (this.memoryByWorkspace.get(workspaceId) ?? []).map((e) => {
      const { eligible, reason } = MockCharacterClient.assessEligibility(e);
      const inspected: MemoryEventInspection = {
        ...e,
        subjectId: MOCK_CHARACTER_ID,
        eligibleForPromotion: eligible,
        ineligibilityReason: reason,
      };
      return inspected;
    });
    return { workspaceId, causalOrder: "seq", events };
  }

  async listMemoryPromotionCandidates(
    workspaceId: string
  ): Promise<readonly MemoryPromotionCandidateSummary[]> {
    this.requireWorkspace(workspaceId);
    return [...(this.candidatesByWorkspace.get(workspaceId) ?? [])];
  }

  async proposeMemoryPromotion(
    workspaceId: string,
    sourceEventId: string,
    memoryKind: MemoryKind
  ): Promise<MemoryPromotionCandidateSummary> {
    this.requireWorkspace(workspaceId);
    const event = (this.memoryByWorkspace.get(workspaceId) ?? []).find(
      (e) => e.eventId === sourceEventId
    );
    if (!event) {
      throw new Error(`source event '${sourceEventId}' not found in this workspace memory`);
    }
    const { eligible } = MockCharacterClient.assessEligibility(event);
    if (!eligible) {
      throw new Error(
        "ineligible: only USER_MESSAGE + USER_STATED events are promotable; a character utterance can never become consolidated memory"
      );
    }
    const candidate: MemoryPromotionCandidateSummary = {
      candidateId: nextId("memcand"),
      sourceEventId,
      memoryKind,
      epistemicKind: "USER_REPORT",
      meaning: event.meaning,
      provenance: event.provenance,
      seq: null,
      decisionStatus: "PENDING",
    };
    const list = this.candidatesByWorkspace.get(workspaceId) ?? [];
    list.push(candidate);
    this.candidatesByWorkspace.set(workspaceId, list);
    return candidate;
  }

  private setCandidateStatus(
    workspaceId: string,
    candidateId: string,
    status: CandidateDecisionStatus
  ): MemoryPromotionCandidateSummary {
    const list = this.candidatesByWorkspace.get(workspaceId) ?? [];
    const index = list.findIndex((c) => c.candidateId === candidateId);
    if (index < 0) throw new Error(`unknown candidate '${candidateId}'`);
    const updated = { ...list[index], decisionStatus: status };
    list[index] = updated;
    return updated;
  }

  async decideMemoryPromotion(
    workspaceId: string,
    candidateId: string,
    decision: PromotionDecision
  ): Promise<MemoryPromotionCandidateSummary> {
    this.requireWorkspace(workspaceId);
    const candidate = (this.candidatesByWorkspace.get(workspaceId) ?? []).find(
      (c) => c.candidateId === candidateId
    );
    if (!candidate) throw new Error(`unknown candidate '${candidateId}'`);
    if (candidate.decisionStatus !== "PENDING") {
      throw new Error(`candidate '${candidateId}' was already decided (decisions are final)`);
    }
    if (decision === "REJECT") {
      return this.setCandidateStatus(workspaceId, candidateId, "REJECTED");
    }
    // Matches the backend's normalize_meaning: strip + collapse whitespace,
    // case-fold (Python `" ".join(text.split())` -> JS needs the leading
    // `.trim()`, since `"  x".split(/\s+/)` keeps a leading "").
    const normalize = (t: string) => t.trim().split(/\s+/).join(" ").toLowerCase();
    const normalized = normalize(candidate.meaning);
    const records = this.recordsByWorkspace.get(workspaceId) ?? [];
    const duplicate = records.find(
      (r) =>
        r.status === "ACTIVE" &&
        r.epistemicKind === candidate.epistemicKind &&
        normalize(r.meaning) === normalized
    );
    if (duplicate) {
      throw new Error(
        `duplicate: an active consolidated record with the same normalized meaning already exists (record_id='${duplicate.recordId}')`
      );
    }
    const record: ConsolidatedMemoryRecordSummary = {
      recordId: nextId("memrec"),
      memoryKind: candidate.memoryKind,
      epistemicKind: candidate.epistemicKind,
      meaning: candidate.meaning,
      sourceEventId: candidate.sourceEventId,
      basisEventIds: [candidate.sourceEventId],
      provenance: candidate.provenance,
      status: "ACTIVE",
      supersededByRecordId: null,
      conflictRecordIds: [],
      seq: records.length + 1,
    };
    records.push(record);
    this.recordsByWorkspace.set(workspaceId, records);
    return this.setCandidateStatus(workspaceId, candidateId, "APPROVED");
  }

  async listConsolidatedMemory(
    workspaceId: string
  ): Promise<readonly ConsolidatedMemoryRecordSummary[]> {
    this.requireWorkspace(workspaceId);
    const records = this.recordsByWorkspace.get(workspaceId) ?? [];
    const relations = this.relationsByWorkspace.get(workspaceId) ?? [];
    const supersededBy = new Map<string, string>();
    for (const rel of relations) {
      if (rel.kind === "SUPERSEDES") supersededBy.set(rel.toRecordId, rel.fromRecordId);
    }
    const activeIds = new Set(
      records.filter((r) => !supersededBy.has(r.recordId)).map((r) => r.recordId)
    );
    const conflictPartners = new Map<string, Set<string>>();
    for (const rel of relations) {
      if (rel.kind !== "CONFLICTS_WITH") continue;
      if (activeIds.has(rel.fromRecordId) && activeIds.has(rel.toRecordId)) {
        if (!conflictPartners.has(rel.fromRecordId)) {
          conflictPartners.set(rel.fromRecordId, new Set());
        }
        conflictPartners.get(rel.fromRecordId)!.add(rel.toRecordId);
        if (!conflictPartners.has(rel.toRecordId)) {
          conflictPartners.set(rel.toRecordId, new Set());
        }
        conflictPartners.get(rel.toRecordId)!.add(rel.fromRecordId);
      }
    }
    return records.map((r) => {
      const superseder = supersededBy.get(r.recordId);
      return {
        ...r,
        status: superseder ? ("SUPERSEDED" as const) : ("ACTIVE" as const),
        supersededByRecordId: superseder ?? null,
        conflictRecordIds: [...(conflictPartners.get(r.recordId) ?? [])].sort(),
      };
    });
  }

  async createConsolidatedMemoryRelation(
    workspaceId: string,
    fromRecordId: string,
    toRecordId: string,
    relationType: ConsolidatedRelationKind
  ): Promise<MemoryRelationSummary> {
    this.requireWorkspace(workspaceId);
    if (fromRecordId === toRecordId) {
      throw new Error("a record cannot relate to itself");
    }
    const records = this.recordsByWorkspace.get(workspaceId) ?? [];
    const pairs: ReadonlyArray<readonly [string, string]> = [
      ["from_record", fromRecordId],
      ["to_record", toRecordId],
    ];
    for (const [name, id] of pairs) {
      if (!records.some((r) => r.recordId === id)) {
        throw new Error(`${name} '${id}' does not exist for this subject/workspace`);
      }
    }
    const relations = this.relationsByWorkspace.get(workspaceId) ?? [];
    if (
      relations.some(
        (rel) =>
          rel.kind === relationType &&
          rel.fromRecordId === fromRecordId &&
          rel.toRecordId === toRecordId
      )
    ) {
      throw new Error(
        `duplicate relation: ${relationType} from '${fromRecordId}' to '${toRecordId}' already exists`
      );
    }
    const relation: MemoryRelationSummary = {
      relationId: nextId("memrel"),
      kind: relationType,
      fromRecordId,
      toRecordId,
    };
    relations.push(relation);
    this.relationsByWorkspace.set(workspaceId, relations);
    return relation;
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

  async setRuntimeState(
    workspaceId: string,
    domain: RuntimeStateDomain,
    key: string,
    value: string,
    sourceRef?: string
  ): Promise<RuntimeStateEntrySummary> {
    this.requireWorkspace(workspaceId);
    const entries = this.stateByWorkspace.get(workspaceId) ?? [];
    const numeric = domain === "RELATIONSHIP" || domain === "PSYCHOLOGY";
    const parsed = numeric ? Number(value) : null;
    const entry: RuntimeStateEntrySummary = {
      domain,
      key,
      value,
      valueInt: numeric && Number.isInteger(parsed) ? parsed : null,
      sourceKind: "OPERATOR_CONFIRMED",
      sourceRef: sourceRef ?? null,
      seq: entries.length + 1,
    };
    const rest = entries.filter((e) => !(e.domain === domain && e.key === key));
    this.stateByWorkspace.set(workspaceId, [...rest, entry]);
    return entry;
  }

  async adjustRuntimeState(
    workspaceId: string,
    domain: RuntimeStateDomain,
    key: string,
    delta: number,
    sourceRef?: string
  ): Promise<RuntimeStateEntrySummary> {
    this.requireWorkspace(workspaceId);
    const entries = this.stateByWorkspace.get(workspaceId) ?? [];
    const current = entries.find((e) => e.domain === domain && e.key === key);
    if (!current || current.valueInt === null) {
      throw new Error(`${domain} key '${key}' is not initialized; SET an absolute value first`);
    }
    const next = current.valueInt + delta;
    if (next < -100 || next > 100) {
      throw new Error(`adjusted value ${next} out of range [-100, 100]; state unchanged`);
    }
    return this.setRuntimeState(workspaceId, domain, key, String(next), sourceRef);
  }

  async removeRuntimeState(
    workspaceId: string,
    domain: RuntimeStateDomain,
    key: string,
    _sourceRef?: string
  ): Promise<RuntimeStateEntrySummary> {
    this.requireWorkspace(workspaceId);
    const entries = this.stateByWorkspace.get(workspaceId) ?? [];
    const rest = entries.filter((e) => !(e.domain === domain && e.key === key));
    this.stateByWorkspace.set(workspaceId, rest);
    return {
      domain,
      key,
      value: "",
      valueInt: null,
      sourceKind: "OPERATOR_CONFIRMED",
      sourceRef: null,
      seq: null,
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
