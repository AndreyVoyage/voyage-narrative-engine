/**
 * Static mock fixtures for MockCharacterClient / MockCharacterDebugClient.
 *
 * DEV-ONLY, CLEARLY FAKE DATA. None of this is imported from or derived
 * from the Accepted KIRA package (`accepted/kira/source_candidate.json`) --
 * no real claims, no real package hash, no real acceptance id. It exists
 * only so React UI can be built and eyeballed before a transport is chosen.
 */

import type {
  CapabilitySet,
  CharacterPackageRef,
  CharacterSummary,
  CharacterVariantSummary,
  ContextManifestSummary,
  MemoryEventSummary,
  RequestCaptureSummary,
  RuntimeStateEntrySummary,
  TurnSummary,
  WorkspaceSummary,
} from "../client/types.js";

export const MOCK_CHARACTER_ID = "kira";

// Deliberately fake -- never a real accepted-package hash/id.
export const mockPackageRef: CharacterPackageRef = {
  characterId: MOCK_CHARACTER_ID,
  packageId: "mock-package-id-dev-only",
  packageVersion: 0,
  sourceHash: "0000000000000000000000000000000000000000000000000000000000mock",
  acceptanceDecision: "HUMAN_APPROVED",
  candidateStatus: "DRAFT",
};

export const mockCharacter: CharacterSummary = {
  characterId: MOCK_CHARACTER_ID,
  displayName: "KIRA",
  supported: true,
  packageRef: mockPackageRef,
};

export const mockVariants: readonly CharacterVariantSummary[] = [
  {
    variantId: "KIRA_BETA_V1_CURRENT",
    displayName: "Beta v1 — Current",
    implemented: true,
    selected: true,
  },
  {
    variantId: "KIRA_GROUNDED_V2",
    displayName: "Grounded v2",
    implemented: true,
    selected: false,
  },
  {
    variantId: "EXPERIMENTAL",
    displayName: "Experimental",
    implemented: false,
    status: "disabled",
    selected: false,
  },
];

export const mockCapabilities: CapabilitySet = {
  capabilities: [
    "chat",
    "memory",
    "runtime_state",
    "relationship_state",
    "psychology_state",
    "scene",
    "turn_debugger",
    "provider_configured",
  ],
};

export const MOCK_NORMAL_WORKSPACE_ID = "normal";

export function makeMockNormalWorkspace(selected: boolean): WorkspaceSummary {
  return {
    workspaceId: MOCK_NORMAL_WORKSPACE_ID,
    workspaceKind: "NORMAL",
    displayName: "Normal / long-lived",
    selected,
  };
}

export function makeMockCleanTestWorkspace(
  workspaceId: string,
  selected: boolean
): WorkspaceSummary {
  return {
    workspaceId,
    workspaceKind: "CLEAN_TEST",
    displayName: `Clean Test ${workspaceId.slice(-8)}`,
    selected,
  };
}

export const mockMemoryEvents: readonly MemoryEventSummary[] = [
  {
    seq: 1,
    eventId: "mock-evt-1",
    sessionId: "mock-session-dev",
    eventType: "USER_MESSAGE",
    provenance: "USER_STATED",
    meaning: "(демо) Привет.",
  },
  {
    seq: 2,
    eventId: "mock-evt-2",
    sessionId: "mock-session-dev",
    eventType: "CHARACTER_MESSAGE",
    provenance: "CHARACTER_UTTERANCE",
    meaning: "(демо) Привет! Рада тебя видеть.",
  },
];

export const mockRuntimeStateEntries: readonly RuntimeStateEntrySummary[] = [
  {
    domain: "FACT",
    key: "demo.example_key",
    value: "demo-value",
    valueInt: null,
    sourceKind: "OPERATOR_CONFIRMED",
    sourceRef: null,
    seq: 1,
  },
  {
    domain: "RELATIONSHIP",
    key: "andrey.trust",
    value: "20",
    valueInt: 20,
    sourceKind: "OPERATOR_CONFIRMED",
    sourceRef: null,
    seq: 2,
  },
  {
    domain: "PSYCHOLOGY",
    key: "stress",
    value: "-10",
    valueInt: -10,
    sourceKind: "OPERATOR_CONFIRMED",
    sourceRef: "manual test",
    seq: 3,
  },
];

export const mockTurns: readonly TurnSummary[] = [
  {
    turnId: "mock-turn-1",
    sessionId: "mock-session-dev",
    variantId: "KIRA_BETA_V1_CURRENT",
    requestHash: "mockrequesthash0000000000000000000000000000000000000000000001",
    responsePreview: "(демо) Привет! Рада тебя видеть.",
    scenePresent: false,
    hasError: false,
    createdAt: "2026-01-01T00:00:00+00:00",
  },
];

export const mockContextManifest: ContextManifestSummary = {
  turnId: "mock-turn-1",
  variantId: "KIRA_BETA_V1_CURRENT",
  assemblyHash: "mockassemblyhash00000000000000000000000000000000000000000001",
  items: [
    { kind: "system.role_instruction", text: "(демо) системная инструкция", selected: true, delivered: true },
    { kind: "system.memory_line", text: "(демо) строка памяти", selected: true, delivered: true },
    { kind: "user.current", text: "(демо) текущее сообщение", selected: true, delivered: true },
  ],
};

export const mockRequestCapture: RequestCaptureSummary = {
  turnId: "mock-turn-1",
  requestHash: mockContextManifest.assemblyHash,
  rawRequestJson: JSON.stringify(
    { model: "mock-model", messages: [{ role: "system", content: "(демо)" }] },
    null,
    2
  ),
};
