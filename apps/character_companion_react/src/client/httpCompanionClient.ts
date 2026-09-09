/**
 * The ONLY file in the Companion app with HTTP concepts. Everything else
 * depends on the transport-neutral `CompanionClient` interface.
 *
 * Talks to `tools/character_companion_server.py` (loopback, fake provider,
 * fake image generator in dev) via relative `/api/companion/...` paths — Vite
 * proxies them in dev, so no CORS and no hardcoded host in feature code.
 */

import {
  CompanionCharacter,
  CompanionClient,
  CompanionClientError,
  CompanionMessage,
  CompanionSession,
  CompanionSettingsView,
  CompanionTurn,
  ImageJob,
  ImageJobKind,
  NewDialogInput,
  ProviderTestResult,
  RandomScenarioResult,
  ReleaseInfo,
  RoleResolution,
  SceneField,
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
    return (await call<{ characters: CompanionCharacter[] }>("GET", "/characters")).characters ?? [];
  }

  async listSessions(characterId: string): Promise<CompanionSession[]> {
    return (
      await call<{ sessions: CompanionSession[] }>(
        "GET",
        `/characters/${encodeURIComponent(characterId)}/sessions`,
      )
    ).sessions ?? [];
  }

  async getSession(sessionId: string): Promise<CompanionSession> {
    return call<CompanionSession>("GET", `/sessions/${encodeURIComponent(sessionId)}`);
  }

  async createSession(characterId: string, input?: NewDialogInput): Promise<CompanionSession> {
    return call<CompanionSession>("POST", "/sessions", {
      characterId,
      title: input?.title,
      scene: input?.scene,
    });
  }

  async getMessages(sessionId: string): Promise<CompanionMessage[]> {
    return (
      await call<{ messages: CompanionMessage[] }>(
        "GET",
        `/sessions/${encodeURIComponent(sessionId)}/messages`,
      )
    ).messages ?? [];
  }

  async sendMessage(sessionId: string, text: string): Promise<CompanionTurn> {
    return call<CompanionTurn>("POST", "/messages", { sessionId, text });
  }

  async randomScenario(opts?: { field?: SceneField; seed?: number }): Promise<RandomScenarioResult> {
    return call<RandomScenarioResult>("POST", "/scenario", {
      field: opts?.field,
      seed: opts?.seed ?? null,
    });
  }

  async createImageJob(sessionId: string, kind: ImageJobKind, prompt?: string): Promise<ImageJob> {
    return call<ImageJob>("POST", "/images", { sessionId, kind, prompt: prompt ?? null });
  }

  async listImageJobs(sessionId: string): Promise<ImageJob[]> {
    return (
      await call<{ jobs: ImageJob[] }>("GET", `/sessions/${encodeURIComponent(sessionId)}/images`)
    ).jobs ?? [];
  }

  async setSceneCover(sessionId: string, resultRef: string): Promise<CompanionSession> {
    return call<CompanionSession>("POST", "/sessions/cover", { sessionId, resultRef });
  }

  async getSettings(): Promise<CompanionSettingsView> {
    return call<CompanionSettingsView>("GET", "/settings");
  }

  async setRole(role: string, providerId: string, modelId: string): Promise<CompanionSettingsView> {
    return call<CompanionSettingsView>("POST", "/settings/roles", { role, providerId, modelId });
  }

  async setLocalSettings(input: { numCtx?: number | null; baseUrl?: string | null }): Promise<CompanionSettingsView> {
    return call<CompanionSettingsView>("POST", "/settings/local", input);
  }

  async storeCredential(providerId: string, secret: string): Promise<CompanionSettingsView> {
    // the secret is sent once and never requested back
    return call<CompanionSettingsView>("POST", "/settings/credentials", { providerId, secret });
  }

  async deleteCredential(providerId: string): Promise<CompanionSettingsView> {
    return call<CompanionSettingsView>("DELETE", `/settings/credentials/${encodeURIComponent(providerId)}`);
  }

  async testProvider(providerId: string, modelId?: string): Promise<ProviderTestResult> {
    return call<ProviderTestResult>("POST", "/settings/test", { providerId, modelId });
  }

  async resolveRole(role: string): Promise<RoleResolution> {
    return call<RoleResolution>("GET", `/settings/resolve/${encodeURIComponent(role)}`);
  }

  async getReleaseInfo(): Promise<ReleaseInfo> {
    return call<ReleaseInfo>("GET", "/release");
  }
}
