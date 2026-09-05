/**
 * CharacterDebugClient -- developer-observability contract, explicitly
 * SEPARATE from {@link CharacterClient} (see `characterClient.ts`).
 *
 * A normal chat client never needs this; it is for a Turn Debugger /
 * Character Inspector style consumer only. Structurally, no
 * `CharacterClient` implementation exposes these methods, and no
 * `CharacterDebugClient` implementation exposes `sendMessage` /
 * `createSession` -- keeping the two interfaces separate is itself the
 * mechanism that stops developer/debug UI from leaking into reusable
 * consumer-facing "character UI" components.
 *
 * Mirrors `services/character_core/contract.py::CharacterDebugService`.
 * Never exposes hidden reasoning / chain-of-thought -- only the
 * deterministic assembly manifest and the exact captured transport request
 * (the same evidence the existing TurnCapture already produces).
 */

import type {
  ContextManifestSummary,
  RequestCaptureSummary,
  TurnDebugBundle,
  TurnSummary,
} from "./types.js";

export interface CharacterDebugClient {
  listTurns(sessionId?: string): Promise<readonly TurnSummary[]>;
  getTurnDebug(turnId: string): Promise<TurnDebugBundle>;
  getRequestCapture(turnId: string): Promise<RequestCaptureSummary>;
  getContextManifest(turnId: string): Promise<ContextManifestSummary>;
}
