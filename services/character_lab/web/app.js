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

const state = { catalog: null, loaded: null, sessions: [], turns: [], mode: "chat" };

function $(id) { return document.getElementById(id); }

function shortHash(h) { return h ? h.slice(0, 12) + "…" : "—"; }

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  $("view-chat").classList.toggle("hidden", mode !== "chat");
  $("view-character").classList.toggle("hidden", mode !== "character");
  $("view-turns").classList.toggle("hidden", mode !== "turns");
  if (mode === "character") loadCharacterInspector();
  if (mode === "turns") loadTurns();
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

function renderVariants() {
  const ul = $("variants");
  ul.innerHTML = "";
  (state.catalog.variants || []).forEach((v) => {
    const li = el("li", v.implemented ? "active" : "disabled", v.display_name);
    li.appendChild(el("div", "sub", v.implemented ? "active" : (v.status || "planned") + " / недоступно"));
    if (v.implemented) {
      li.addEventListener("click", () => refreshLoadedState());
    } else {
      li.title = "Вариант запланирован и недоступен";
    }
    ul.appendChild(li);
  });
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
    ["Variant", "Beta v1 — Current", ""],
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
    li.appendChild(el("div", "sub", s.preview ? s.preview.slice(0, 40) : "новая сессия"));
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

async function loadTurns() {
  state.turns = await api("/api/turns");
  const list = $("turns-list");
  list.innerHTML = "";
  (state.turns || []).forEach((t) => {
    const item = el("div", "turn-item", shortHash(t.turn_id));
    item.appendChild(el("div", "sub", t.response_preview || "—"));
    item.addEventListener("click", () => openTurnDetail(t.turn_id));
    list.appendChild(item);
  });
}

async function openTurnDetail(turnId) {
  const detail = await api("/api/turn/" + encodeURIComponent(turnId));
  const box = $("turn-detail");
  box.innerHTML = "";
  box.appendChild(el("h1", "", "Ход: " + shortHash(detail.turn_id)));

  const metaRows = [
    ["Character", detail.character_id],
    ["Variant", detail.variant_id],
    ["Session", detail.session_id ? shortHash(detail.session_id) : "—"],
    ["Accepted source", shortHash(detail.accepted_source_hash)],
  ];
  metaRows.forEach(([k, v]) => {
    const row = el("div", "row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v hash", String(v)));
    box.appendChild(row);
  });

  box.appendChild(el("div", "section-title", "REQUEST"));
  box.appendChild(el("div", "proven", "Captured transport request"));
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
  const eventIds = (detail.persistence && detail.persistence.event_ids) || [];
  box.appendChild(el("div", "", "runtime event IDs: " + eventIds.map(shortHash).join(", ")));

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

  await loadCatalog();
  await refreshLoadedState();
  await loadSessions();
  clearChat();
}

init().catch((e) => { addSystemMessage("Не удалось инициализировать: " + e.message); });
