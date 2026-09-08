/**
 * Deterministic in-memory `CompanionClient` for structural checks and offline
 * dev. Mirrors the backend's rules: only accepted characters are listable,
 * sessions persist for the life of the instance, history is causal-ordered,
 * empty messages are rejected, unknown ids fail with bounded errors.
 *
 * `failSendOnce()` arms a single simulated provider failure for the error-path
 * checks -- prior history must survive it.
 */

import {
  CompanionCharacter,
  CompanionClient,
  CompanionClientError,
  CompanionMessage,
  CompanionSession,
  CompanionTurn,
} from "../client/types.js";

const KIRA: CompanionCharacter = {
  characterId: "kira",
  displayName: "Кира",
  packageId: "kira-mock-package",
  packageVersion: 0,
  sourceHash: "mock-source-hash",
};

export class MockCompanionClient implements CompanionClient {
  private readonly characters: CompanionCharacter[];
  private readonly sessions = new Map<string, CompanionSession>();
  private readonly messages = new Map<string, CompanionMessage[]>();
  private seq = 0;
  private counter = 0;
  private armedFailure = false;
  reply = "Детерминированный ответ.";

  constructor(characters: CompanionCharacter[] = [KIRA]) {
    this.characters = characters;
  }

  failSendOnce(): void {
    this.armedFailure = true;
  }

  async listCharacters(): Promise<CompanionCharacter[]> {
    return [...this.characters];
  }

  private requireCharacter(characterId: string): CompanionCharacter {
    const found = this.characters.find((c) => c.characterId === characterId);
    if (!found) {
      throw new CompanionClientError(404, "unknown_character", "Неизвестный персонаж.");
    }
    return found;
  }

  async listSessions(characterId: string): Promise<CompanionSession[]> {
    this.requireCharacter(characterId);
    return [...this.sessions.values()]
      .filter((s) => s.characterId === characterId)
      .sort((a, b) => (a.createdAt < b.createdAt ? -1 : a.createdAt > b.createdAt ? 1 : 0));
  }

  async createSession(characterId: string): Promise<CompanionSession> {
    this.requireCharacter(characterId);
    this.counter += 1;
    const stamp = `2026-01-01T00:00:${String(this.counter).padStart(2, "0")}+00:00`;
    const session: CompanionSession = {
      sessionId: `cmp-mock-${this.counter}`,
      characterId,
      purpose: "COMPANION",
      createdAt: stamp,
      updatedAt: stamp,
      label: `Диалог от ${stamp.replace("T", " ").split("+")[0]}`,
    };
    this.sessions.set(session.sessionId, session);
    this.messages.set(session.sessionId, []);
    return session;
  }

  private requireSession(sessionId: string): CompanionMessage[] {
    const history = this.messages.get(sessionId);
    if (!history) {
      throw new CompanionClientError(404, "unknown_session", "Неизвестный диалог.");
    }
    return history;
  }

  async getMessages(sessionId: string): Promise<CompanionMessage[]> {
    return [...this.requireSession(sessionId)];
  }

  async sendMessage(sessionId: string, text: string): Promise<CompanionTurn> {
    const history = this.requireSession(sessionId);
    if (!text.trim()) {
      throw new CompanionClientError(400, "empty_message", "Пустое сообщение.");
    }
    if (this.armedFailure) {
      this.armedFailure = false;
      throw new CompanionClientError(502, "provider_failed", "Сбой провайдера.");
    }
    this.seq += 1;
    history.push({ seq: this.seq, role: "user", text, createdAt: "2026-01-01T00:00:00+00:00" });
    this.seq += 1;
    history.push({ seq: this.seq, role: "character", text: this.reply, createdAt: "2026-01-01T00:00:00+00:00" });
    return { sessionId, response: this.reply, messages: [...history] };
  }
}
