/**
 * MockCharacterDebugClient -- a deterministic `CharacterDebugClient`
 * implementation over static fixture data. Deliberately separate from
 * `MockCharacterClient` (no shared base class, no shared instance) -- the
 * same separation the real contract enforces between `CharacterService` and
 * `CharacterDebugService`.
 */

import type { CharacterDebugClient } from "../client/characterDebugClient.js";
import type {
  ContextManifestSummary,
  RequestCaptureSummary,
  TurnDebugBundle,
  TurnSummary,
} from "../client/types.js";
import { mockContextManifest, mockRequestCapture, mockTurns } from "./mockData.js";

export class MockCharacterDebugClient implements CharacterDebugClient {
  async listTurns(sessionId?: string): Promise<readonly TurnSummary[]> {
    if (sessionId === undefined) return mockTurns;
    return mockTurns.filter((t) => t.sessionId === sessionId);
  }

  async getTurnDebug(turnId: string): Promise<TurnDebugBundle> {
    const turn = mockTurns.find((t) => t.turnId === turnId);
    if (!turn) throw new Error(`unknown turn '${turnId}'`);
    return {
      turn,
      manifest: { ...mockContextManifest, turnId },
      request: { ...mockRequestCapture, turnId },
    };
  }

  async getRequestCapture(turnId: string): Promise<RequestCaptureSummary> {
    return { ...mockRequestCapture, turnId };
  }

  async getContextManifest(turnId: string): Promise<ContextManifestSummary> {
    return { ...mockContextManifest, turnId };
  }
}
