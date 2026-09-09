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
  ModelView,
  ProviderCardView,
  ProviderTestResult,
  RandomScenarioResult,
  ReleaseInfo,
  RoleCatalogEntry,
  RoleResolution,
  SCENE_FIELDS,
  SceneField,
  WritingAssistantResult,
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

// ---- media model-role catalog (compact mirror of the backend registry) ----
const MOCK_ROLE_ORDER = [
  "DIALOGUE", "VISION", "IMAGE_GENERATION", "VIDEO_GENERATION",
  "STT", "TTS", "REALTIME", "WRITING_ASSISTANT", "LOCAL_ALTERNATIVE",
];
const CAP_TO_ROLE: Record<string, string> = {
  DIALOGUE: "DIALOGUE", VISION: "VISION", IMAGE_GENERATION: "IMAGE_GENERATION",
  VIDEO_GENERATION: "VIDEO_GENERATION", STT: "STT", TTS: "TTS", REALTIME: "REALTIME",
};

function mv(
  modelId: string, displayName: string, capabilities: string[],
  status: ModelView["status"], contentPolicyProfile: string,
  media: Partial<Pick<ModelView, "supportsReferenceImage" | "supportsImageToImage" | "supportsCharacterReference" | "supportsVideo" | "maxDurationSeconds">> = {},
): ModelView {
  const roles = [...new Set(capabilities.map((c) => CAP_TO_ROLE[c]).filter(Boolean))];
  return {
    modelId, displayName, capabilities, roles, status, notes: "",
    contentPolicyProfile,
    supportsReferenceImage: media.supportsReferenceImage ?? null,
    supportsImageToImage: media.supportsImageToImage ?? null,
    supportsCharacterReference: media.supportsCharacterReference ?? null,
    supportsVideo: media.supportsVideo ?? null,
    maxDurationSeconds: media.maxDurationSeconds ?? null,
  };
}

interface MockProviderDef {
  displayName: string;
  kind: "cloud" | "local";
  transport: string;
  credentialRequired: boolean;
  baseUrl: string;
  models: ModelView[];
}

const MOCK_CATALOG: Record<string, MockProviderDef> = {
  deepseek: { displayName: "DeepSeek", kind: "cloud", transport: "openai_compat", credentialRequired: true, baseUrl: "https://api.deepseek.com", models: [
    mv("deepseek-chat", "DeepSeek Chat", ["DIALOGUE", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
    mv("deepseek-reasoner", "DeepSeek Reasoner", ["DIALOGUE", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
  ] },
  openai: { displayName: "OpenAI", kind: "cloud", transport: "openai_compat", credentialRequired: true, baseUrl: "https://api.openai.com", models: [
    mv("gpt-4o-mini", "GPT-4o mini", ["DIALOGUE", "VISION", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
    mv("gpt-4o", "GPT-4o", ["DIALOGUE", "VISION", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
    mv("gpt-image-1", "GPT Image 1", ["IMAGE_GENERATION", "IMAGE_TO_IMAGE", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT", { supportsImageToImage: true, supportsReferenceImage: true }),
    mv("sora-2", "Sora 2", ["VIDEO_GENERATION", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT", { supportsVideo: true }),
    mv("whisper-1", "Whisper", ["STT", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT"),
    mv("gpt-4o-mini-tts", "GPT-4o mini TTS", ["TTS", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT"),
    mv("gpt-4o-realtime-preview", "GPT-4o Realtime", ["REALTIME", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT"),
  ] },
  qwen: { displayName: "Qwen", kind: "cloud", transport: "openai_compat", credentialRequired: true, baseUrl: "https://dashscope.aliyuncs.com/compatible-mode", models: [
    mv("qwen-plus", "Qwen Plus", ["DIALOGUE", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
    mv("qwen-max", "Qwen Max", ["DIALOGUE", "CLOUD"], "available", "PROVIDER_POLICY_DEPENDENT"),
    mv("qwen-vl-plus", "Qwen-VL Plus", ["VISION", "CLOUD"], "unverified", "PROVIDER_POLICY_DEPENDENT"),
  ] },
  local: { displayName: "Local (Ollama)", kind: "local", transport: "ollama_native", credentialRequired: false, baseUrl: "http://127.0.0.1:11434", models: [
    mv("llama3", "Llama 3", ["DIALOGUE", "LOCAL"], "available", "LOCAL_MODEL_POLICY"),
    mv("llama3.1", "Llama 3.1", ["DIALOGUE", "LOCAL"], "available", "LOCAL_MODEL_POLICY"),
    mv("qwen2.5", "Qwen 2.5", ["DIALOGUE", "LOCAL"], "available", "LOCAL_MODEL_POLICY"),
    mv("llava", "LLaVA", ["VISION", "LOCAL"], "unverified", "LOCAL_MODEL_POLICY"),
  ] },
  fake: { displayName: "Fake (dev)", kind: "local", transport: "fake", credentialRequired: false, baseUrl: "", models: [
    mv("fake", "Fake", ["DIALOGUE", "LOCAL"], "available", "STANDARD_ONLY"),
  ] },
};

function mockModelSupportsRole(m: ModelView, role: string): boolean {
  if (role === "LOCAL_ALTERNATIVE") return m.capabilities.includes("DIALOGUE") && m.capabilities.includes("LOCAL");
  if (role === "WRITING_ASSISTANT") return m.capabilities.includes("DIALOGUE");
  return m.roles.includes(role);
}

function mockProviderSupportedRoles(providerId: string): string[] {
  const c = MOCK_CATALOG[providerId];
  if (!c) return [];
  const set = new Set<string>();
  for (const m of c.models) for (const r of m.roles) set.add(r);
  if (c.kind === "local" && set.has("DIALOGUE")) set.add("LOCAL_ALTERNATIVE");
  if (set.has("DIALOGUE")) set.add("WRITING_ASSISTANT");
  return MOCK_ROLE_ORDER.filter((r) => set.has(r));
}

/** Deterministic offline "polish": trim, collapse spaces, capitalize, end with
 * punctuation. Good enough for structural checks; the real assistant is a model. */
function mockPolish(draft: string): string {
  let s = draft.trim().replace(/\s+/g, " ");
  if (!s) return s;
  s = s[0].toUpperCase() + s.slice(1);
  if (!/[.!?…]$/.test(s)) s += ".";
  return s;
}

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
      titleOverride: null,
      hidden: false,
      hiddenMessageIds: [],
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
    // NOTE: the transcript read is NEVER filtered by hidden ids -- presentation
    // filtering is the UI's job; the underlying history is returned in full.
    return [...this.requireRow(sessionId).messages];
  }

  async renameSession(sessionId: string, title: string): Promise<CompanionSession> {
    const row = this.requireRow(sessionId);
    const clean = (title ?? "").trim().slice(0, 120);
    row.session = { ...row.session, titleOverride: clean || null };
    return { ...row.session };
  }

  async setSessionHidden(sessionId: string, hidden: boolean): Promise<CompanionSession> {
    const row = this.requireRow(sessionId);
    row.session = { ...row.session, hidden: Boolean(hidden) };
    return { ...row.session };
  }

  async setMessageHidden(sessionId: string, messageId: number, hidden: boolean): Promise<CompanionSession> {
    const row = this.requireRow(sessionId);
    if (hidden && !row.messages.some((m) => m.seq === messageId)) {
      throw new CompanionClientError(404, "unknown_message", "Сообщение не найдено.");
    }
    const set = new Set(row.session.hiddenMessageIds);
    if (hidden) set.add(messageId); else set.delete(messageId);
    row.session = { ...row.session, hiddenMessageIds: [...set].sort((a, b) => a - b) };
    return { ...row.session };
  }

  async rewriteDraft(draft: string, _opts?: { localeHint?: string }): Promise<WritingAssistantResult> {
    if (typeof draft !== "string" || !draft.trim()) {
      throw new CompanionClientError(400, "invalid_draft", "Пустой черновик.");
    }
    const a = this.roles.WRITING_ASSISTANT;
    if (!a) {
      throw new CompanionClientError(409, "assistant_not_configured", "Помощник написания не настроен.");
    }
    const c = MOCK_CATALOG[a.providerId];
    if (c?.credentialRequired && !this.secrets.has(a.providerId)) {
      throw new CompanionClientError(409, "missing_credential", "Нет ключа для выбранного провайдера.");
    }
    return { suggestion: mockPolish(draft), provider: a.providerId, model: a.modelId };
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

  // -------- secure provider settings + media model roles (in-memory) -------
  private readonly secrets = new Map<string, string>(); // provider -> raw (never returned)
  private readonly roles: Record<string, { providerId: string; modelId: string }> = {
    DIALOGUE: { providerId: "fake", modelId: "fake" },
  };
  private localNumCtx: number | null = null;
  private localBaseUrl = "http://127.0.0.1:11434";

  private providerCatalog(): ProviderCardView[] {
    return Object.entries(MOCK_CATALOG).map(([providerId, c]) => {
      const connected = c.credentialRequired ? this.secrets.has(providerId) : true;
      const raw = this.secrets.get(providerId);
      const supportedRoles = mockProviderSupportedRoles(providerId);
      const capabilities = [...new Set([c.kind === "local" ? "LOCAL" : "CLOUD", ...c.models.flatMap((m) => m.capabilities)])];
      const assigned = Object.values(this.roles).find((a) => a.providerId === providerId);
      return {
        providerId,
        displayName: c.displayName,
        kind: c.kind,
        transport: c.transport,
        credentialRequired: c.credentialRequired,
        defaultBaseUrl: c.baseUrl,
        supportedRoles,
        runtimeWiredRoles: supportedRoles.filter((r) => r === "DIALOGUE"),
        capabilities,
        modelCatalog: c.models.map((m) => m.modelId),
        models: c.models,
        defaultModel: c.models[0]?.modelId ?? "",
        notes: "",
        connected,
        configuredModel: assigned ? assigned.modelId : (c.models[0]?.modelId ?? ""),
        maskedTail: raw ? "…" + raw.slice(-4) : null,
        lastTestStatus: null,
      };
    });
  }

  private providersForRole(role: string): string[] {
    return Object.keys(MOCK_CATALOG).filter((pid) => mockProviderSupportedRoles(pid).includes(role));
  }

  private resolveRoleConfig(role: string): RoleResolution {
    const runtimeWired = role === "DIALOGUE";
    const a = this.roles[role];
    const base: RoleResolution = {
      role, runtimeWired, providerId: null, modelId: null, providerConnected: false,
      credentialRequired: false, maskedTail: null, capabilities: [],
      contentPolicyProfile: "UNKNOWN", modelStatus: null, readiness: "NOT_CONFIGURED",
    };
    if (!a) return base;
    base.providerId = a.providerId;
    base.modelId = a.modelId;
    const c = MOCK_CATALOG[a.providerId];
    const m = c?.models.find((x) => x.modelId === a.modelId);
    if (!c || !m || !mockModelSupportsRole(m, role)) {
      base.readiness = "UNSUPPORTED";
      return base;
    }
    const raw = this.secrets.get(a.providerId);
    const connected = c.credentialRequired ? this.secrets.has(a.providerId) : true;
    base.credentialRequired = c.credentialRequired;
    base.providerConnected = connected;
    base.maskedTail = raw ? "…" + raw.slice(-4) : null;
    base.capabilities = m.capabilities;
    base.contentPolicyProfile = m.contentPolicyProfile;
    base.modelStatus = m.status;
    base.readiness = c.credentialRequired && !connected
      ? "CONFIGURED_CREDENTIAL_MISSING"
      : runtimeWired ? "READY" : "FUTURE_NOT_WIRED";
    return base;
  }

  async getSettings(): Promise<CompanionSettingsView> {
    const roleCatalog: RoleCatalogEntry[] = MOCK_ROLE_ORDER.map((role) => ({
      ...this.resolveRoleConfig(role),
      providerIds: this.providersForRole(role),
    }));
    return {
      providers: this.providerCatalog(),
      roles: { ...this.roles },
      roleCatalog,
      allRoles: [...MOCK_ROLE_ORDER],
      roleDisplayOrder: [...MOCK_ROLE_ORDER],
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
    const c = MOCK_CATALOG[providerId];
    if (!c) throw new CompanionClientError(404, "unknown_provider", "Неизвестный провайдер.");
    if (!mockProviderSupportedRoles(providerId).includes(role)) {
      throw new CompanionClientError(400, "unsupported_role", "Провайдер не поддерживает эту роль.");
    }
    const wanted = (modelId || "").trim() || (c.models.find((m) => mockModelSupportsRole(m, role))?.modelId ?? "");
    const model = c.models.find((m) => m.modelId === wanted);
    if (!model) throw new CompanionClientError(400, "unknown_model", "Модель не найдена в каталоге провайдера.");
    if (!mockModelSupportsRole(model, role)) {
      throw new CompanionClientError(400, "unsupported_model_role", "Модель не поддерживает эту задачу.");
    }
    this.roles[role] = { providerId, modelId: wanted };
    return this.getSettings();
  }

  async resolveRole(role: string): Promise<RoleResolution> {
    if (!MOCK_ROLE_ORDER.includes(role)) {
      throw new CompanionClientError(400, "unknown_role", "Неизвестная роль модели.");
    }
    return this.resolveRoleConfig(role);
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
