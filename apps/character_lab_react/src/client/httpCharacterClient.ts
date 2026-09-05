/**
 * HttpCharacterClient -- the local loopback HTTP/JSON transport adapter for
 * `CharacterClient`, talking to `tools/character_lab_react_server.py`'s
 * minimal API surface v1 (characters, workspaces, sessions, chat).
 *
 * `CharacterClient` itself remains transport-neutral (see
 * `characterClient.ts`) -- every HTTP-specific concept (relative paths,
 * `fetch`, JSON envelopes, status codes) lives ONLY inside this file. This is
 * an APPLICATION transport decision for React Character Lab specifically; it
 * is not documented anywhere as the canonical Character Core platform
 * transport (see `services/character_lab/react_transport.py`'s module
 * docstring for the equivalent note on the backend side).
 *
 * Calls relative `/api/...` paths (never an embedded absolute localhost URL)
 * so Vite's dev proxy (`vite.config.ts`) can forward them to the backend
 * server without any CORS configuration.
 *
 * Desktop Integration v1 does not transport Memory / Runtime State / Scene
 * yet (see `services/character_lab/react_transport.py`'s minimal API
 * surface) -- those methods deterministically reject with
 * `NotIntegratedInTransportError` rather than calling a nonexistent endpoint
 * or fabricating mock data under a live label.
 */

import type { CharacterClient } from "./characterClient.js";
import {
  ALL_SESSION_PURPOSES,
  NotIntegratedInTransportError,
  SessionPurpose,
  SessionPurposeNotImplementedError,
  type CapabilitySet,
  type ChatTurnResult,
  type CharacterSession,
  type CharacterSummary,
  type CharacterVariantSummary,
  type MemorySummary,
  type RuntimeStateSummary,
  type SceneSummary,
  type SetSceneInput,
  type WorkspaceSummary,
} from "./types.js";

interface TransportErrorBody {
  readonly error?: { readonly code?: string; readonly message?: string };
}

/** Raised for any backend error response this client does not translate
 * into a more specific typed error (see `SessionPurposeNotImplementedError`
 * for `unsupported_purpose`). Carries the same small error-code vocabulary
 * `services/character_lab/react_transport.py` defines. */
export class HttpTransportError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "HttpTransportError";
    this.status = status;
    this.code = code;
  }
}

async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const text = await response.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!response.ok) {
    const errorBody = (body ?? {}) as TransportErrorBody;
    const code = errorBody.error?.code ?? "internal_error";
    const message = errorBody.error?.message ?? `${response.status} ${response.statusText}`;
    if (code === "unsupported_purpose") {
      // Best-effort recovery of the purpose value from the message the
      // backend generates deterministically (see react_transport.py); if it
      // ever can't be parsed, fall through to the generic HttpTransportError
      // rather than guessing a purpose.
      const match = /SessionPurpose\.(\w+)/.exec(message);
      const purpose = match
        ? ALL_SESSION_PURPOSES.find((p) => p === match[1])
        : undefined;
      if (purpose) throw new SessionPurposeNotImplementedError(purpose);
    }
    throw new HttpTransportError(response.status, code, message);
  }
  return body;
}

function toCharacterSummary(json: any): CharacterSummary {
  return {
    characterId: json.characterId,
    displayName: json.displayName,
    supported: json.supported,
    packageRef: json.packageRef
      ? {
          characterId: json.packageRef.characterId,
          packageId: json.packageRef.packageId,
          packageVersion: json.packageRef.packageVersion,
          sourceHash: json.packageRef.sourceHash,
          acceptanceDecision: json.packageRef.acceptanceDecision,
          candidateStatus: json.packageRef.candidateStatus,
        }
      : undefined,
  };
}

function toVariantSummary(json: any): CharacterVariantSummary {
  return {
    variantId: json.variantId,
    displayName: json.displayName,
    implemented: json.implemented,
    status: json.status ?? undefined,
    selected: json.selected,
  };
}

function toWorkspaceSummary(json: any): WorkspaceSummary {
  return {
    workspaceId: json.workspaceId,
    workspaceKind: json.workspaceKind,
    displayName: json.displayName,
    selected: json.selected,
  };
}

function toSession(json: any): CharacterSession {
  return {
    sessionId: json.sessionId,
    characterId: json.characterId,
    variantId: json.variantId,
    purpose: json.purpose as SessionPurpose,
    workspace: toWorkspaceSummary(json.workspace),
    createdAt: json.createdAt ?? undefined,
  };
}

function toChatTurnResult(json: any): ChatTurnResult {
  return {
    turnId: json.turnId,
    sessionId: json.sessionId,
    characterId: json.characterId,
    variantId: json.variantId,
    response: json.response,
    requestHash: json.requestHash ?? undefined,
    scenePresent: json.scenePresent,
  };
}

export class HttpCharacterClient implements CharacterClient {
  // ------------------------------------------------------------- catalog

  async listCharacters(): Promise<readonly CharacterSummary[]> {
    const data = (await requestJson("/api/characters")) as { characters: any[] };
    return data.characters.map(toCharacterSummary);
  }

  async getCharacter(characterId: string): Promise<CharacterSummary> {
    const data = await requestJson(`/api/characters/${encodeURIComponent(characterId)}`);
    return toCharacterSummary(data);
  }

  async listVariants(characterId: string): Promise<readonly CharacterVariantSummary[]> {
    const data = (await requestJson(
      `/api/characters/${encodeURIComponent(characterId)}/variants`
    )) as { variants: any[] };
    return data.variants.map(toVariantSummary);
  }

  async capabilities(characterId: string): Promise<CapabilitySet> {
    const data = (await requestJson(
      `/api/characters/${encodeURIComponent(characterId)}/capabilities`
    )) as { capabilities: string[] };
    return { capabilities: data.capabilities as CapabilitySet["capabilities"] };
  }

  // ----------------------------------------------------------- workspaces

  async listWorkspaces(): Promise<readonly WorkspaceSummary[]> {
    const data = (await requestJson("/api/workspaces")) as { workspaces: any[] };
    return data.workspaces.map(toWorkspaceSummary);
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceSummary> {
    const data = await requestJson(`/api/workspaces/${encodeURIComponent(workspaceId)}`);
    return toWorkspaceSummary(data);
  }

  async createTestWorkspace(): Promise<WorkspaceSummary> {
    const data = await requestJson("/api/workspaces", { method: "POST", body: JSON.stringify({}) });
    return toWorkspaceSummary(data);
  }

  // ------------------------------------------------------------ sessions

  async createSession(
    characterId: string,
    variantId: string,
    purpose: SessionPurpose,
    workspaceId: string
  ): Promise<CharacterSession> {
    const data = await requestJson("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ characterId, variantId, purpose, workspaceId }),
    });
    return toSession(data);
  }

  async getSession(sessionId: string): Promise<CharacterSession> {
    const data = await requestJson(`/api/sessions/${encodeURIComponent(sessionId)}`);
    return toSession(data);
  }

  // ----------------------------------------------------------------- chat

  async sendMessage(sessionId: string, text: string): Promise<ChatTurnResult> {
    const data = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({ sessionId, text }),
    });
    return toChatTurnResult(data);
  }

  // ------------------------------------------- not integrated in v1 (honest)

  async getMemory(_workspaceId: string): Promise<MemorySummary> {
    throw new NotIntegratedInTransportError("memory");
  }

  async getRuntimeState(_workspaceId: string): Promise<RuntimeStateSummary> {
    throw new NotIntegratedInTransportError("runtime_state");
  }

  async getScene(_sessionId: string): Promise<SceneSummary> {
    throw new NotIntegratedInTransportError("scene");
  }

  async setScene(_sessionId: string, _input: SetSceneInput): Promise<SceneSummary> {
    throw new NotIntegratedInTransportError("scene");
  }

  async clearScene(_sessionId: string): Promise<SceneSummary> {
    throw new NotIntegratedInTransportError("scene");
  }
}
