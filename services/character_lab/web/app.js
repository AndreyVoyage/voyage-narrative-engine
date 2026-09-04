"use strict";

async function api(path, options) {
  const res = await fetch(path, options);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
  if (!res.ok) { throw new Error(data && data.message ? data.message : (res.status + " " + res.statusText)); }
  return data;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const state = {
  catalog: null, loaded: null, sessions: [], turns: [], mode: "chat",
  workspaces: null, memory: null, scene: null,
};

const PROVENANCE_LABELS = {
  USER_STATED: "Сообщил пользователь",
  CHARACTER_UTTERANCE: "Сказала Кира / модель",
  SCENE_SETUP: "Условие сцены",
  LEGACY_UNCLASSIFIED: "Старая запись — происхождение не классифицировано",
};

function provenanceLabel(code) { return PROVENANCE_LABELS[code] || code || "—"; }
function triState(v) { return v === true ? "✓" : v === false ? "—" : "UNKNOWN"; }

function $(id) { return document.getElementById(id); }

function shortHash(h) { return h ? h.slice(0, 12) + "…" : "—"; }

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  ["chat", "character", "memory", "scene", "turns"].forEach((m) => {
    $("view-" + m).classList.toggle("hidden", m !== mode);
  });
  if (mode === "character") loadCharacterInspector();
  if (mode === "turns") loadTurns();
  if (mode === "memory") loadMemory();
  if (mode === "scene") loadScene();
}

async function loadCatalog() {
  state.catalog = await api("/api/catalog");
  renderCharacters();
  renderVariants();
}

function renderCharacters() {
  const ul = $("characters");
  ul.innerHTML = "";
  (state.catalog.characters || []).forEach((c) => {
    const li = el("li", "active", c.display_name);
    li.appendChild(el("div", "sub", c.supported ? "поддерживается" : ""));
    li.addEventListener("click", () => refreshLoadedState());
    ul.appendChild(li);
  });
}

function variantDisplayName(id) {
  const v = ((state.catalog && state.catalog.variants) || []).find((x) => x.id === id);
  return v ? v.display_name : (id || "—");
}

function currentVariantId() {
  return (state.loaded && state.loaded.variant_id) ||
    (((state.catalog && state.catalog.variants) || []).find((v) => v.selected) || {}).id;
}

function renderVariants() {
  const ul = $("variants");
  ul.innerHTML = "";
  const current = currentVariantId();
  (state.catalog.variants || []).forEach((v) => {
    const isCurrent = v.id === current;
    const li = el("li", !v.implemented ? "disabled" : (isCurrent ? "active" : ""), v.display_name);
    li.appendChild(el("div", "sub",
      !v.implemented ? ((v.status || "disabled") + " / недоступно")
        : (isCurrent ? "выбран" : "доступен — нажмите, чтобы выбрать")));
    if (v.implemented) {
      li.addEventListener("click", () => selectVariant(v.id));
    } else {
      li.title = "Вариант отключён";
    }
    ul.appendChild(li);
  });
}

async function selectVariant(variantId) {
  try {
    const r = await api("/api/variant/select", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant_id: variantId }),
    });
    if (r && r.ok === false) {
      addSystemMessage("Вариант недоступен: " + (r.message || variantId));
      return;
    }
    addSystemMessage("Вариант переключён: " + variantId + " — действует со следующего хода.");
  } catch (e) {
    addSystemMessage("Ошибка переключения варианта: " + e.message);
    return;
  }
  await loadCatalog();
  await refreshLoadedState();
}

function updateChatHeader() {
  const h = $("chat-header");
  if (h) h.textContent = "KIRA · " + variantDisplayName(currentVariantId());
}

async function loadWorkspaces() {
  state.workspaces = await api("/api/workspaces");
  const sel = $("workspace-select");
  sel.innerHTML = "";
  (state.workspaces.workspaces || []).forEach((w) => {
    const opt = el("option", "", w.display_name + " (" + w.workspace_kind + ")");
    opt.value = w.workspace_id;
    if (w.selected) opt.selected = true;
    sel.appendChild(opt);
  });
  renderWorkspaceBanner();
}

function renderWorkspaceBanner() {
  const banner = $("workspace-banner");
  const current = (state.workspaces && state.workspaces.workspaces || []).find((w) => w.selected);
  const kind = current ? current.workspace_kind : (state.loaded && state.loaded.workspace_kind);
  banner.innerHTML = "";
  if (kind === "NORMAL") {
    banner.className = "workspace-banner longlived";
    banner.appendChild(el("strong", "", "LONG-LIVED MEMORY"));
    banner.appendChild(el("span", "", "Постоянная память персонажа активна."));
  } else {
    banner.className = "workspace-banner clean";
    banner.appendChild(el("strong", "", "CLEAN TEST"));
    banner.appendChild(el("span", "", "Изолированная тестовая память."));
  }
}

async function selectWorkspace(workspaceId) {
  const r = await api("/api/workspace/select", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
  if (r.notice) addSystemMessage(r.notice.title + " — " + r.notice.message);
  await loadWorkspaces();
  await loadSessions();
  await refreshLoadedState();
  clearChat();
}

async function newCleanTest() {
  const r = await api("/api/workspace/new-test", { method: "POST" });
  addSystemMessage("Новый Clean Test: " + r.workspace_id);
  await loadWorkspaces();
  await loadSessions();
  await refreshLoadedState();
  clearChat();
}

async function refreshLoadedState() {
  try {
    state.loaded = await api("/api/state");
  } catch (e) {
    state.loaded = { error: String(e) };
  }
  renderLoadedState();
  renderProviderState();
  renderDataRoot();
  renderWorkspaceBanner();
  if (state.catalog) renderVariants();
  updateChatHeader();
}

function renderProviderState() {
  const av = state.loaded && state.loaded.provider_availability;
  const node = $("provider-state");
  node.textContent = "Провайдер: " + (av || "—");
  if (av === "CONFIGURED") node.style.color = "#1f7a4d";
  else if (av === "NOT CONFIGURED") node.style.color = "#9a6a00";
  else node.style.color = "#6f6a83";
}

function renderDataRoot() {
  if (state.loaded && state.loaded.data_root) {
    $("data-root-label").textContent = "Данные: " + state.loaded.data_root;
  }
}

function renderLoadedState() {
  const s = state.loaded || {};
  const rows = [
    ["Персонаж", s.character_id, s.hash_match ? "ok" : "bad"],
    ["Acceptance", s.acceptance_decision, "ok"],
    ["Статус кандидата", s.package_status, ""],
    ["Accepted source", shortHash(s.accepted_source_hash), ""],
    ["Loaded hash", shortHash(s.runtime_loaded_package_hash), ""],
    ["Hash match", s.hash_match ? "YES" : "NO", s.hash_match ? "ok" : "bad"],
    ["Package ID", s.package_id || "—", ""],
    ["Package version", s.package_version !== undefined ? String(s.package_version) : "—", ""],
    ["Variant", variantDisplayName(s.variant_id) + " · " + (s.variant_id || "—"), ""],
    ["Workspace", (s.workspace_display_name || "—") + " · " + (s.workspace_kind || "—"),
      s.workspace_kind === "NORMAL" ? "warn" : "ok"],
    ["Scene", s.scene_active ? "активна" : "нет", ""],
    ["Session", s.session_id ? shortHash(s.session_id) : "—", ""],
    ["Provider", s.provider_id, ""],
    ["Requested model", s.model, ""],
    ["Provider state", s.provider_availability, s.provider_availability === "CONFIGURED" ? "ok" : "warn"],
    ["Context Capture", s.context_capture, s.context_capture === "ACTIVE" ? "ok" : "warn"],
    ["Package Write", s.package_write_access, "ok"],
  ];
  const box = $("loaded-state");
  box.innerHTML = "";
  rows.forEach(([k, v, cls]) => {
    const row = el("div", "row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v " + (cls || ""), String(v)));
    box.appendChild(row);
  });
}

async function loadSessions() {
  state.sessions = await api("/api/sessions");
  renderSessions();
}

function renderSessions() {
  const ul = $("sessions");
  ul.innerHTML = "";
  (state.sessions || []).forEach((s) => {
    const li = el("li", s.selected ? "active" : "", s.session_id.slice(0, 24) + "…");
    const sub = (s.preview ? s.preview.slice(0, 36) : "новая сессия") + (s.scene_active ? " · сцена" : "");
    li.appendChild(el("div", "sub", sub));
    li.addEventListener("click", () => selectSession(s.session_id));
    ul.appendChild(li);
  });
}

async function newSession() {
  await api("/api/session/new", { method: "POST" });
  await loadSessions();
  await refreshLoadedState();
  clearChat();
}

async function selectSession(sessionId) {
  await api("/api/session/select", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId }) });
  await loadSessions();
  await refreshLoadedState();
  if (state.mode === "scene") loadScene();
}

function clearChat() {
  $("messages").innerHTML = "";
  addSystemMessage("Новая сессия начата.");
}

function addMessage(role, content, turnId) {
  const msg = el("div", "msg " + (role === "user" ? "user" : "kira"), content);
  if (turnId) { msg.dataset.turnId = turnId; msg.addEventListener("click", () => { setMode("turns"); openTurnDetail(turnId); }); }
  $("messages").appendChild(msg);
  $("messages").scrollTop = $("messages").scrollHeight;
}

function addSystemMessage(content) {
  const msg = el("div", "msg system", content);
  $("messages").appendChild(msg);
  $("messages").scrollTop = $("messages").scrollHeight;
}

async function sendMessage() {
  const input = $("message-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMessage("user", text);
  try {
    const r = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: text }) });
    addMessage("kira", r.response, r.turn_id);
  } catch (e) {
    addSystemMessage("Ошибка: " + e.message);
  }
  await loadSessions();
  await refreshLoadedState();
  if (state.mode === "memory") loadMemory();
}

async function loadCharacterInspector() {
  const box = $("character-inspector");
  box.innerHTML = "";
  try {
    const data = await api("/api/character");
    box.appendChild(el("h1", "", "Персонаж: KIRA"));
    box.appendChild(el("div", "hash", "Accepted source: " + (data.accepted_source_hash || "—")));
    box.appendChild(el("div", "fields", "Package ID: " + data.package_id + " · v" + data.package_version + " · status: " + data.package_status));
    box.appendChild(el("div", "fields", "Claims: " + data.claim_count + " · Contradictions: " + data.contradiction_count + " · Unknowns: " + data.unknown_count));
    (data.groups || []).forEach((g) => {
      const group = el("div", "group");
      group.appendChild(el("h3", "", g.display_name));
      const obs = el("div", "obs");
      ["stored", "loaded", "selected", "delivered"].forEach((k) => {
        const val = g.observability && g.observability[k];
        obs.appendChild(el("span", "st " + (val ? "yes" : "no"), k.toUpperCase() + " " + (val ? "✓" : "—")));
      });
      group.appendChild(obs);
      (g.sections || []).forEach((section) => {
        (section.claims || []).forEach((c) => {
          const claim = el("div", "claim");
          claim.appendChild(el("div", "text", c.claim));
          claim.appendChild(el("div", "fields", "status=" + c.status + " · confidence=" + c.confidence + " · " + (c.target_module_or_layer || "")));
          group.appendChild(claim);
        });
      });
      box.appendChild(group);
    });
  } catch (e) {
    box.appendChild(el("div", "note", "Ошибка: " + e.message));
  }
}

async function loadMemory(turnId) {
  const box = $("memory-table");
  box.innerHTML = "";
  try {
    const q = turnId ? ("?turn_id=" + encodeURIComponent(turnId)) : "";
    const data = await api("/api/memory" + q);
    state.memory = data;
    box.appendChild(el("div", "sub", "Рабочая область: " + data.workspace_id + " · порядок: " + data.causal_order + " · событий: " + data.event_count));
    const head = el("div", "mem-row head");
    ["seq", "время", "сессия", "тип", "происхождение", "STORED", "LOADED", "SELECTED", "DELIVERED", "содержание"].forEach((h) => head.appendChild(el("span", "", h)));
    box.appendChild(head);
    (data.events || []).forEach((e) => {
      const row = el("div", "mem-row");
      row.appendChild(el("span", "", e.seq !== null && e.seq !== undefined ? String(e.seq) : "—"));
      row.appendChild(el("span", "", (e.created_at || "").replace("T", " ").replace("+00:00", "")));
      row.appendChild(el("span", "", shortHash(e.session_id)));
      row.appendChild(el("span", "", e.event_type));
      const prov = el("span", "prov", provenanceLabel(e.provenance));
      if (e.provenance_display_hint) prov.title = "подсказка по типу: " + provenanceLabel(e.provenance_display_hint);
      row.appendChild(prov);
      row.appendChild(el("span", "", triState(e.stored)));
      row.appendChild(el("span", "", triState(e.loaded)));
      row.appendChild(el("span", "", triState(e.selected)));
      row.appendChild(el("span", "", triState(e.delivered)));
      row.appendChild(el("span", "mem-text", e.meaning));
      box.appendChild(row);
    });
  } catch (e) {
    box.appendChild(el("div", "note", "Ошибка: " + e.message));
  }
}

async function loadScene() {
  try {
    const data = await api("/api/scene");
    state.scene = data;
    const s = data.scene || {};
    $("scene-title").value = s.title || "";
    $("scene-location").value = s.location || "";
    $("scene-participants").value = (s.participants || []).join("\n");
    $("scene-prior").value = (s.prior_events || []).join("\n");
    $("scene-current").value = s.current_situation || "";
    $("scene-preview").textContent = data.preview_block || "(сцена не активна)";
  } catch (e) {
    $("scene-preview").textContent = "Ошибка: " + e.message;
  }
}

async function saveScene() {
  const body = {
    title: $("scene-title").value,
    location: $("scene-location").value,
    participants: $("scene-participants").value,
    prior_events: $("scene-prior").value,
    current_situation: $("scene-current").value,
  };
  try {
    const r = await api("/api/scene", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.ok) {
      $("scene-preview").textContent = r.preview_block;
      addSystemMessage("Сцена применена (" + shortHash(r.scene_hash) + ").");
    } else {
      $("scene-preview").textContent = "Отклонено: " + r.message;
    }
  } catch (e) {
    $("scene-preview").textContent = "Ошибка: " + e.message;
  }
  await refreshLoadedState();
  await loadSessions();
}

async function clearScene() {
  await api("/api/scene", { method: "DELETE" });
  await loadScene();
  await refreshLoadedState();
  await loadSessions();
  addSystemMessage("Сцена очищена.");
}

async function loadTurns() {
  state.turns = await api("/api/turns");
  const list = $("turns-list");
  list.innerHTML = "";
  (state.turns || []).forEach((t) => {
    const item = el("div", "turn-item", shortHash(t.turn_id));
    item.appendChild(el("div", "sub", (t.scene_present ? "[сцена] " : "") + (t.response_preview || "—")));
    item.addEventListener("click", () => openTurnDetail(t.turn_id));
    list.appendChild(item);
  });
}

async function openTurnDetail(turnId) {
  const detail = await api("/api/turn/" + encodeURIComponent(turnId));
  const box = $("turn-detail");
  box.innerHTML = "";
  box.appendChild(el("h1", "", "Ход: " + shortHash(detail.turn_id)));

  const ws = detail.workspace || {};
  const sc = detail.scene || {};
  const metaRows = [
    ["Character", detail.character_id],
    ["Variant", detail.variant_id],
    ["Workspace", (ws.workspace_id || "—") + " · " + (ws.workspace_kind || "—")],
    ["Session", detail.session_id ? shortHash(detail.session_id) : "—"],
    ["Scene", sc.present ? (shortHash(sc.scene_id) + " · " + shortHash(sc.scene_hash)) : "нет"],
    ["Accepted source", shortHash(detail.accepted_source_hash)],
  ];
  metaRows.forEach(([k, v]) => {
    const row = el("div", "row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v hash", String(v)));
    box.appendChild(row);
  });

  box.appendChild(el("div", "section-title", "REQUEST"));
  box.appendChild(el("div", "proven", "Captured transport request (источник истины для DELIVERED)"));
  box.appendChild(el("div", "hash", "SHA-256: " + (detail.request.request_hash || "—")));
  box.appendChild(el("pre", "", prettyJson(detail.request.raw)));

  box.appendChild(el("div", "section-title", "MANIFEST"));
  (detail.manifest.items || []).forEach((item) => {
    const row = el("div", "row");
    row.appendChild(el("span", "k", item.kind));
    row.appendChild(el("span", "v", "SELECTED ✓ · DELIVERED " + (item.delivered ? "✓" : "—")));
    box.appendChild(row);
  });

  box.appendChild(el("div", "section-title", "PROVIDER"));
  const prov = detail.provider || {};
  [
    ["provider_id", prov.provider_id],
    ["model", prov.model],
    ["max_tokens", prov.max_tokens],
    ["timeout_s", prov.timeout_s],
    ["attempt_count", prov.attempt_count],
    ["retry", prov.retry],
    ["fallback", prov.fallback],
  ].forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const row = el("div", "row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v", String(v)));
    box.appendChild(row);
  });

  box.appendChild(el("div", "section-title", "OUTPUT"));
  const meta = detail.response_metadata || {};
  box.appendChild(el("div", "", "finish_reason: " + (meta.finish_reason || "—")));
  if (meta.provider_reported_model) box.appendChild(el("div", "", "provider-reported model: " + meta.provider_reported_model));
  box.appendChild(el("pre", "", extractResponseText(detail.response) || "(нет содержимого)"));

  box.appendChild(el("div", "section-title", "PERSISTENCE"));
  const events = (detail.persistence && detail.persistence.events) || [];
  if (events.length) {
    events.forEach((ev) => {
      box.appendChild(el("div", "", "seq " + (ev.seq !== null ? ev.seq : "—") + " · " + ev.event_type + " · " + provenanceLabel(ev.provenance) + " · " + shortHash(ev.event_id)));
    });
  } else {
    const ids = (detail.persistence && detail.persistence.event_ids) || [];
    box.appendChild(el("div", "", "runtime event IDs: " + ids.map(shortHash).join(", ")));
  }

  box.appendChild(el("div", "section-title", "PACKAGE"));
  box.appendChild(el("div", "hash", "accepted source: " + shortHash(detail.package.accepted_source_hash)));
  if (detail.package.unchanged !== undefined) box.appendChild(el("div", "proven", "unchanged: " + (detail.package.unchanged ? "YES" : "NO")));
}

function prettyJson(raw) {
  if (!raw) return "(нет данных)";
  try { return JSON.stringify(JSON.parse(raw), null, 2); } catch (e) { return raw; }
}

function extractResponseText(data) {
  if (data && data.choices && data.choices[0] && data.choices[0].message) {
    return data.choices[0].message.content;
  }
  return null;
}

async function init() {
  document.querySelectorAll(".mode").forEach((b) => {
    if (!b.disabled) b.addEventListener("click", () => setMode(b.dataset.mode));
  });
  $("new-session").addEventListener("click", newSession);
  $("send").addEventListener("click", sendMessage);
  $("message-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });
  $("workspace-select").addEventListener("change", (e) => selectWorkspace(e.target.value));
  $("new-clean-test").addEventListener("click", newCleanTest);
  $("memory-refresh").addEventListener("click", () => loadMemory());
  $("scene-save").addEventListener("click", saveScene);
  $("scene-clear").addEventListener("click", clearScene);

  await loadCatalog();
  await loadWorkspaces();
  await refreshLoadedState();
  await loadSessions();
  clearChat();
}

init().catch((e) => { addSystemMessage("Не удалось инициализировать: " + e.message); });
