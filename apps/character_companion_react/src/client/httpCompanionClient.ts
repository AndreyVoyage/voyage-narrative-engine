/**
 * The ONLY file in the Companion app with HTTP concepts. Everything else
 * depends on the transport-neutral `CompanionClient` interface.
 *
 * Talks to `tools/character_companion_server.py` (loopback, fake provider) via
 * relative `/api/companion/...` paths -- Vite proxies them in dev, so there is
 * no CORS and no hardcoded host in feature code.
 */

import {
  CompanionCharacter,
  CompanionClient,
  CompanionClientError,
  CompanionMessage,
  CompanionSession,
  CompanionTurn,
} from "./types.js";

const BASE = "/api/companion";

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new CompanionClientError(0, "backend_unavailable", "Нет подключения к серверу.");
  }
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    if (response.ok) {
      throw new CompanionClientError(response.status, "malformed_response", "Некорректный ответ сервера.");
    }
  }
  if (!response.ok) {
    const err = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new CompanionClientError(
      response.status,
      err?.code ?? "request_failed",
      err?.message ?? "Запрос завершился ошибкой.",
    );
  }
  return data as T;
}

export class HttpCompanionClient implements CompanionClient {
  async listCharacters(): Promise<CompanionCharacter[]> {
    const data = await call<{ characters: CompanionCharacter[] }>("GET", "/characters");
    return data.characters ?? [];
  }

  async listSessions(characterId: string): Promise<CompanionSession[]> {
    const data = await call<{ sessions: CompanionSession[] }>(
      "GET",
      `/characters/${encodeURIComponent(characterId)}/sessions`,
    );
    return data.sessions ?? [];
  }

  async createSession(characterId: string): Promise<CompanionSession> {
    return call<CompanionSession>("POST", "/sessions", { characterId });
  }

  async getMessages(sessionId: string): Promise<CompanionMessage[]> {
    const data = await call<{ messages: CompanionMessage[] }>(
      "GET",
      `/sessions/${encodeURIComponent(sessionId)}/messages`,
    );
    return data.messages ?? [];
  }

  async sendMessage(sessionId: string, text: string): Promise<CompanionTurn> {
    return call<CompanionTurn>("POST", "/messages", { sessionId, text });
  }
}
