/**
 * Deterministic in-memory `CompanionClient` for structural checks and offline
 * dev. Mirrors backend rules: accepted characters only, additive scene
 * metadata, causal history, newest-activity-first sessions, deterministic
 * random scenario, and a step-driven fake image job (QUEUED→GENERATING→READY
 * advanced by `listImageJobs`, never by `sendMessage`).
 */

import {
  CompanionCharacter,
  CompanionClient,
  CompanionClientError,
  CompanionMessage,
  CompanionScene,
  CompanionSession,
  CompanionSettingsView,
  CompanionTurn,
  ImageJob,
  ImageJobKind,
  NewDialogInput,
  ProviderCardView,
  ProviderTestResult,
  RandomScenarioResult,
  ReleaseInfo,
  SCENE_FIELDS,
  SceneField,
  emptyScene,
  sceneHasAny,
} from "../client/types.js";

const KIRA: CompanionCharacter = {
  characterId: "kira",
  displayName: "Кира",
  packageId: "kira-mock-package",
  packageVersion: 0,
  sourceHash: "mock-source-hash",
};

const POOLS: Record<SceneField, string[]> = {
  place: ["Небольшая кухня", "Столик в кафе", "Крыша дома вечером"],
  time: ["Раннее утро", "Поздний вечер", "Полдень"],
  situation: ["Случайная встреча", "Разговор за чаем", "Пережидают дождь"],
  mood: ["Спокойное", "Лёгкое", "Задумчивое"],
};

interface Row {
  session: CompanionSession;
  messages: CompanionMessage[];
}

export class MockCompanionClient implements CompanionClient {
  private readonly characters: CompanionCharacter[];
  private readonly rows = new Map<string, Row>();
  private readonly jobs = new Map<string, ImageJob>();
  private seq = 0;
  private counter = 0;
  private activity = 0;
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

  private requireCharacter(id: string): CompanionCharacter {
    const c = this.characters.find((x) => x.characterId === id);
    if (!c) throw new CompanionClientError(404, "unknown_character", "Неизвестный персонаж.");
    return c;
  }

  private stamp(): string {
    this.counter += 1;
    return `2026-01-01T00:00:${String(this.counter).padStart(2, "0")}+00:00`;
  }

  async listSessions(characterId: string): Promise<CompanionSession[]> {
    this.requireCharacter(characterId);
    return [...this.rows.values()]
      .map((r) => r.session)
      .filter((s) => s.characterId === characterId)
      .sort((a, b) => (a.lastActivity < b.lastActivity ? 1 : a.lastActivity > b.lastActivity ? -1 : 0));
  }

  async getSession(sessionId: string): Promise<CompanionSession> {
    return { ...this.requireRow(sessionId).session };
  }

  async createSession(characterId: string, input?: NewDialogInput): Promise<CompanionSession> {
    this.requireCharacter(characterId);
    const at = this.stamp();
    this.activity += 1;
    const scene: CompanionScene | null =
      input?.scene && sceneHasAny(input.scene) ? { ...emptyScene(), ...input.scene } : null;
    const session: CompanionSession = {
      sessionId: `cmp-mock-${++this.counter}`,
      characterId,
      purpose: "COMPANION",
      createdAt: at,
      updatedAt: at,
      label: `Диалог от ${at.replace("T", " ").split("+")[0]}`,
      title: (input?.title ?? "").trim(),
      scene,
      sceneCoverRef: null,
      lastMessagePreview: "",
      lastActivity: `${String(this.activity).padStart(6, "0")}`,
    };
    this.rows.set(session.sessionId, { session, messages: [] });
    return { ...session };
  }

  private requireRow(sessionId: string): Row {
    const row = this.rows.get(sessionId);
    if (!row) throw new CompanionClientError(404, "unknown_session", "Неизвестный диалог.");
    return row;
  }

  async getMessages(sessionId: string): Promise<CompanionMessage[]> {
    return [...this.requireRow(sessionId).messages];
  }

  async sendMessage(sessionId: string, text: string): Promise<CompanionTurn> {
    const row = this.requireRow(sessionId);
    if (!text.trim()) throw new CompanionClientError(400, "empty_message", "Пустое сообщение.");
    if (this.armedFailure) {
      this.armedFailure = false;
      throw new CompanionClientError(502, "provider_failed", "Сбой провайдера.");
    }
    this.seq += 1;
    row.messages.push({ seq: this.seq, role: "user", text, createdAt: this.stamp() });
    this.seq += 1;
    row.messages.push({ seq: this.seq, role: "character", text: this.reply, createdAt: this.stamp() });
    this.activity += 1;
    row.session.lastActivity = `${String(this.activity).padStart(6, "0")}`;
    row.session.lastMessagePreview = this.reply;
    // NOTE: sendMessage never advances image jobs
    return { sessionId, response: this.reply, scenePresent: Boolean(row.session.scene), messages: [...row.messages] };
  }

  async randomScenario(opts?: { field?: SceneField; seed?: number }): Promise<RandomScenarioResult> {
    const seed = opts?.seed ?? 1;
    const pick = (field: SceneField) => POOLS[field][seed % POOLS[field].length];
    if (opts?.field) return { field: opts.field, value: pick(opts.field) };
    const scenario = {} as Record<SceneField, string>;
    for (const f of SCENE_FIELDS) scenario[f] = pick(f);
    return { scenario };
  }

  async createImageJob(sessionId: string, kind: ImageJobKind, prompt?: string): Promise<ImageJob> {
    const row = this.requireRow(sessionId);
    if (kind === "custom" && !(prompt ?? "").trim()) {
      throw new CompanionClientError(400, "invalid_request", "Нужно описание изображения.");
    }
    const job: ImageJob = {
      jobId: `img-mock-${++this.counter}`,
      sessionId,
      characterId: row.session.characterId,
      kind,
      state: "QUEUED",
      createdAt: this.stamp(),
      updatedAt: this.stamp(),
      prompt: prompt?.trim() ?? null,
      resultRef: null,
      error: null,
    };
    this.jobs.set(job.jobId, job);
    return { ...job };
  }

  async listImageJobs(sessionId: string): Promise<ImageJob[]> {
    this.requireRow(sessionId);
    // step the fake generator forward by one, exactly like polling a real async service
    for (const job of this.jobs.values()) {
      if (job.sessionId !== sessionId) continue;
      if (job.state === "QUEUED") {
        job.state = "GENERATING";
      } else if (job.state === "GENERATING") {
        job.state = "READY";
        job.resultRef = `images/${job.jobId}.svg`;
      }
    }
    return [...this.jobs.values()]
      .filter((j) => j.sessionId === sessionId)
      .sort((a, b) => (a.createdAt < b.createdAt ? -1 : 1));
  }

  async setSceneCover(sessionId: string, resultRef: string): Promise<CompanionSession> {
    const row = this.requireRow(sessionId);
    const ready = [...this.jobs.values()].some(
      (j) => j.sessionId === sessionId && j.state === "READY" && j.resultRef === resultRef,
    );
    if (!ready) {
      throw new CompanionClientError(400, "invalid_request", "Обложкой можно сделать только готовое изображение диалога.");
    }
    row.session.sceneCoverRef = resultRef;
    return { ...row.session };
  }

  // -------- secure provider settings (in-memory; secrets never re-exposed) --
  private readonly secrets = new Map<string, string>(); // provider -> raw (never returned)
  private readonly roles: Record<string, { providerId: string; modelId: string }> = {
    DIALOGUE: { providerId: "fake", modelId: "fake" },
  };
  private localNumCtx: number | null = null;
  private localBaseUrl = "http://127.0.0.1:11434";

  private providerCatalog(): ProviderCardView[] {
    const base: Omit<ProviderCardView, "connected" | "configuredModel" | "maskedTail" | "lastTestStatus">[] = [
      { providerId: "deepseek", displayName: "DeepSeek", kind: "cloud", transport: "openai_compat", credentialRequired: true, defaultBaseUrl: "https://api.deepseek.com", supportedRoles: ["DIALOGUE"], runtimeWiredRoles: ["DIALOGUE"], modelCatalog: ["deepseek-chat", "deepseek-reasoner"], defaultModel: "deepseek-chat", notes: "Сильная работа с диалогом." },
      { providerId: "openai", displayName: "OpenAI", kind: "cloud", transport: "openai_compat", credentialRequired: true, defaultBaseUrl: "https://api.openai.com", supportedRoles: ["DIALOGUE", "VISION", "IMAGE_GENERATION", "STT", "TTS", "REALTIME"], runtimeWiredRoles: ["DIALOGUE"], modelCatalog: ["gpt-4o-mini", "gpt-4o"], defaultModel: "gpt-4o-mini", notes: "Широкий мультимодальный набор (метаданные)." },
      { providerId: "qwen", displayName: "Qwen", kind: "cloud", transport: "openai_compat", credentialRequired: true, defaultBaseUrl: "https://dashscope.aliyuncs.com/compatible-mode", supportedRoles: ["DIALOGUE", "VISION"], runtimeWiredRoles: ["DIALOGUE"], modelCatalog: ["qwen-plus", "qwen-max"], defaultModel: "qwen-plus", notes: "Совместимый OpenAI-протокол." },
      { providerId: "local", displayName: "Local (Ollama)", kind: "local", transport: "ollama_native", credentialRequired: false, defaultBaseUrl: "http://127.0.0.1:11434", supportedRoles: ["DIALOGUE", "LOCAL_ALTERNATIVE"], runtimeWiredRoles: ["DIALOGUE"], modelCatalog: ["llama3", "llama3.1", "qwen2.5"], defaultModel: "llama3", notes: "Приватность / без оплаты за токены." },
      { providerId: "fake", displayName: "Fake (dev)", kind: "local", transport: "fake", credentialRequired: false, defaultBaseUrl: "", supportedRoles: ["DIALOGUE"], runtimeWiredRoles: ["DIALOGUE"], modelCatalog: ["fake"], defaultModel: "fake", notes: "Детерминированная заглушка. Никогда не автоматический fallback." },
    ];
    return base.map((p) => {
      const connected = p.credentialRequired ? this.secrets.has(p.providerId) : true;
      const raw = this.secrets.get(p.providerId);
      return {
        ...p,
        connected,
        configuredModel: this.roles.DIALOGUE.providerId === p.providerId ? this.roles.DIALOGUE.modelId : p.defaultModel,
        maskedTail: raw ? "…" + raw.slice(-4) : null,
        lastTestStatus: null,
      };
    });
  }

  async getSettings(): Promise<CompanionSettingsView> {
    return {
      providers: this.providerCatalog(),
      roles: { ...this.roles },
      allRoles: ["DIALOGUE", "VISION", "IMAGE_GENERATION", "STT", "TTS", "REALTIME", "LOCAL_ALTERNATIVE"],
      runtimeWiredRoles: ["DIALOGUE"],
      local: {
        numCtx: this.localNumCtx,
        baseUrl: this.localBaseUrl,
        model: this.roles.DIALOGUE.providerId === "local" ? this.roles.DIALOGUE.modelId : "llama3",
        numCtxMin: 512,
        numCtxMax: 131072,
        kiraSafeHint: 16384,
        numCtxWarning: this.localNumCtx !== null && this.localNumCtx < 16384,
      },
      allowCloudFallback: false,
      dataRoutingNote: "Сообщения для этой роли отправляются выбранному провайдеру. Дублирования между провайдерами нет.",
    };
  }

  async setRole(role: string, providerId: string, modelId: string): Promise<CompanionSettingsView> {
    const p = this.providerCatalog().find((x) => x.providerId === providerId);
    if (!p) throw new CompanionClientError(404, "unknown_provider", "Неизвестный провайдер.");
    if (!p.supportedRoles.includes(role)) {
      throw new CompanionClientError(400, "unsupported_role", "Провайдер не поддерживает эту роль.");
    }
    this.roles[role] = { providerId, modelId: modelId || p.defaultModel };
    return this.getSettings();
  }

  async setLocalSettings(input: { numCtx?: number | null; baseUrl?: string | null }): Promise<CompanionSettingsView> {
    if ("numCtx" in input) {
      const n = input.numCtx;
      if (n !== null && n !== undefined && (!Number.isInteger(n) || n <= 0)) {
        throw new CompanionClientError(400, "invalid_num_ctx", "Размер контекста должен быть положительным целым.");
      }
      this.localNumCtx = n ?? null;
    }
    if ("baseUrl" in input && typeof input.baseUrl === "string" && input.baseUrl) this.localBaseUrl = input.baseUrl;
    return this.getSettings();
  }

  async storeCredential(providerId: string, secret: string): Promise<CompanionSettingsView> {
    const p = this.providerCatalog().find((x) => x.providerId === providerId);
    if (!p) throw new CompanionClientError(404, "unknown_provider", "Неизвестный провайдер.");
    if (!p.credentialRequired) throw new CompanionClientError(409, "no_credential_needed", "Ключ не требуется.");
    if (!secret.trim()) throw new CompanionClientError(400, "invalid_secret", "Пустой ключ.");
    this.secrets.set(providerId, secret.trim()); // stored; never returned raw
    return this.getSettings();
  }

  async deleteCredential(providerId: string): Promise<CompanionSettingsView> {
    this.secrets.delete(providerId);
    return this.getSettings();
  }

  async testProvider(providerId: string, _modelId?: string): Promise<ProviderTestResult> {
    const p = this.providerCatalog().find((x) => x.providerId === providerId);
    if (!p) return { providerId, ok: false, status: "unknown_provider" };
    if (p.credentialRequired && !this.secrets.has(providerId)) {
      return { providerId, ok: false, status: "missing_credential" }; // credential NOT erased
    }
    return { providerId, ok: true, status: "ok" };
  }

  async getReleaseInfo(): Promise<ReleaseInfo> {
    return {
      release: { name: "KIRA Companion MVP RC1", version: "0.1.0-rc1", channel: "release-candidate" },
      mode: "dev",
      dialogueProvider: this.roles.DIALOGUE.providerId,
      acceptedCharacter: {
        characterId: "kira",
        packageId: "kira-mock-package",
        sourceHash: "mock-source-hash",
      },
      localContext: { recommendedMinNumCtx: 16384, kiraGroundedObservedPromptTokens: 10014 },
    };
  }
}
