import { useEffect, useState } from "react";
import type { CompanionClient } from "../client/types.js";
import type { CompanionSettingsView, ProviderCardView, ProviderTestResult } from "../client/types.js";
import {
  DIALOGUE_CONTEXT_BUDGET_PRESETS,
  MODEL_ROLE_ORDER,
  autoFallbackDefault,
  isValidDialogueContextBudget,
  localContextWarning,
  modelsForRole,
  providerActions,
  providersForRole,
  readinessLabelKey,
  roleIsConfiguredButNotImplemented,
  roleLabelKey,
  secretDraftAfterSubmit,
} from "../app/settingsState.js";
import type { LocalUserProfile } from "../app/userProfile.js";
import { useLocale } from "../i18n/react.js";
import { LOCALE_LABELS, UI_LOCALES, type UiLocale } from "../i18n/index.js";

interface Props {
  client: CompanionClient;
  profile: LocalUserProfile;
  onProfileChange: (profile: LocalUserProfile) => void;
  onClose: () => void;
}

/** Companion Settings — Profile · Providers · Model roles · Local model · Security.
 * No raw key is ever rendered. Attachment upload stays disabled; no file input. */
export function SettingsPanel({ client, profile, onProfileChange, onClose }: Props) {
  const { t, locale, setLocale } = useLocale();
  const [view, setView] = useState<CompanionSettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secretDrafts, setSecretDrafts] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<Record<string, ProviderTestResult>>({});
  const [nameDraft, setNameDraft] = useState(profile.displayName);
  const [budgetError, setBudgetError] = useState<string | null>(null);
  // Local-model technical settings (Base URL, num_ctx) start hidden behind a
  // collapsed disclosure so they never look like a second "context" control next
  // to the ordinary "Контекст диалога" budget. Not persisted; every mount starts
  // collapsed.
  const [localAdvancedOpen, setLocalAdvancedOpen] = useState(false);

  function load() {
    client.getSettings().then(setView).catch((e) => setError(String(e?.message ?? e)));
  }
  useEffect(load, []);

  function guard<T>(p: Promise<T>) {
    setError(null);
    return p.catch((e) => {
      setError(String(e?.message ?? e));
      throw e;
    });
  }

  function statusLabel(card: ProviderCardView): string {
    if (!card.credentialRequired) return t("settings.status.ready");
    return card.connected ? t("settings.status.connected") : t("settings.status.disconnected");
  }

  function commitName() {
    const next = { ...profile, displayName: nameDraft.trim().slice(0, 40) };
    onProfileChange(next);
  }

  function changeLanguage(next: UiLocale) {
    setLocale(next);
    onProfileChange({ ...profile, locale: next });
  }

  if (!view) {
    return (
      <section className="panel settings">
        <div className="settings-head"><h2 className="panel-title">{t("settings.title")}</h2>
          <button type="button" className="btn btn-sm" onClick={onClose}>{t("settings.close")}</button></div>
        {error ? <p className="error" role="alert">{error}</p> : <p className="empty">{t("app.loading")}</p>}
      </section>
    );
  }

  function saveSecret(card: ProviderCardView) {
    const secret = (secretDrafts[card.providerId] ?? "").trim();
    if (!secret) return;
    guard(client.storeCredential(card.providerId, secret)).then((v) => {
      setView(v);
      setSecretDrafts((d) => ({ ...d, [card.providerId]: secretDraftAfterSubmit() }));
    });
  }

  return (
    <section className="panel settings">
      <div className="settings-head">
        <h2 className="panel-title">{t("settings.title")}</h2>
        <button type="button" className="btn btn-sm" onClick={onClose}>{t("settings.close")}</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}

      {/* Profile — presentation-only Local User Profile */}
      <h3 className="settings-section">{t("profile.section")}</h3>
      <label className="field">
        <span>{t("profile.displayName")}</span>
        <input
          value={nameDraft}
          maxLength={40}
          placeholder={t("profile.defaultName")}
          onChange={(e) => setNameDraft(e.target.value)}
          onBlur={commitName}
        />
      </label>
      <p className="settings-hint">{t("profile.displayNameHint")}</p>
      <p className="settings-hint profile-avatar-status">{t("profile.avatarComingSoon")}</p>
      <label className="field">
        <span>{t("profile.language")}</span>
        <select value={locale} onChange={(e) => changeLanguage(e.target.value as UiLocale)}>
          {UI_LOCALES.map((l) => (
            <option key={l} value={l}>{LOCALE_LABELS[l]}</option>
          ))}
        </select>
      </label>

      <p className="settings-note">{view.dataRoutingNote}</p>

      {/* Providers */}
      <h3 className="settings-section">{t("settings.section.providers")}</h3>
      <div className="provider-cards">
        {view.providers.filter((p) => p.providerId !== "fake").map((card) => (
          <div className="provider-card" key={card.providerId}>
            <div className="provider-card-head">
              <strong>{card.displayName}</strong>
              <span className={card.connected || !card.credentialRequired ? "pill pill-ok" : "pill"}>
                {statusLabel(card)}
              </span>
            </div>
            <p className="provider-card-notes">{card.notes}</p>
            <p className="provider-card-model">{t("settings.providerModel", { model: card.configuredModel })}</p>
            <p className="provider-card-roles">{t("settings.providerRoles", { roles: card.supportedRoles.join(", ") })}</p>
            <div className="provider-card-caps">
              {card.capabilities.filter((c) => c !== "CLOUD" && c !== "LOCAL").map((c) => (
                <span key={c} className="cap-chip">{c}</span>
              ))}
            </div>
            {card.maskedTail && <p className="provider-card-tail">{t("settings.providerKey", { tail: card.maskedTail })}</p>}

            {card.credentialRequired && (
              <div className="provider-card-secret">
                <input
                  type="password"
                  placeholder={card.connected ? t("settings.keyReplacePlaceholder") : t("settings.keyPlaceholder")}
                  value={secretDrafts[card.providerId] ?? ""}
                  onChange={(e) => setSecretDrafts((d) => ({ ...d, [card.providerId]: e.target.value }))}
                />
                <button type="button" className="btn btn-sm" onClick={() => saveSecret(card)}>
                  {card.connected ? t("settings.replace") : t("settings.connect")}
                </button>
                {card.connected && (
                  <button type="button" className="btn btn-sm" onClick={() =>
                    guard(client.deleteCredential(card.providerId)).then(setView)}>
                    {t("settings.deleteKey")}
                  </button>
                )}
              </div>
            )}
            <div className="provider-card-actions">
              {providerActions(card).includes("Проверить") && (
                <button type="button" className="btn btn-sm" onClick={() =>
                  guard(client.testProvider(card.providerId)).then((r) =>
                    setTestResults((t2) => ({ ...t2, [card.providerId]: r })))}>
                  {t("settings.testConnection")}
                </button>
              )}
              {testResults[card.providerId] && (
                <span className={testResults[card.providerId].ok ? "pill pill-ok" : "pill pill-bad"}>
                  {testResults[card.providerId].ok ? "OK" : testResults[card.providerId].status}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Models by task — data-driven role -> provider -> model configuration */}
      <h3 className="settings-section">{t("settings.section.modelRoles")}</h3>
      <p className="settings-hint">{t("settings.rolesHint")}</p>
      <p className="settings-hint">{t("settings.modelRolesHint")}</p>
      <div className="role-rows">
        {MODEL_ROLE_ORDER.map((role) => {
          const entry = view.roleCatalog.find((r) => r.role === role);
          const roleProviders = providersForRole(view, role);
          const selectedProviderId = entry?.providerId ?? "";
          const providerCard = view.providers.find((p) => p.providerId === selectedProviderId);
          const roleModels = modelsForRole(providerCard, role);
          const readiness = entry?.readiness ?? "NOT_CONFIGURED";
          const runtimeWired = Boolean(entry?.runtimeWired);
          return (
            <div className="role-row" key={role}>
              <div className="role-row-head">
                <span className="role-row-name">{t(roleLabelKey(role))}</span>
                {runtimeWired
                  ? <span className="pill pill-ok">{t("settings.runtimeWiredBadge")}</span>
                  : <span className="pill">{t(readinessLabelKey(readiness))}</span>}
              </div>
              {roleProviders.length === 0 ? (
                <p className="settings-hint">{t("settings.roleNoProvider")}</p>
              ) : (
                <div className="role-row-selects">
                  <label className="field">
                    <span>{t("settings.roleProvider")}</span>
                    <select
                      value={selectedProviderId}
                      onChange={(e) => guard(client.setRole(role, e.target.value, "")).then(setView)}
                    >
                      {!selectedProviderId && <option value="" disabled>—</option>}
                      {roleProviders.map((p) => (
                        <option key={p.providerId} value={p.providerId}>{p.displayName}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>{t("settings.roleModel")}</span>
                    <select
                      value={entry?.modelId ?? ""}
                      disabled={!selectedProviderId}
                      onChange={(e) => guard(client.setRole(role, selectedProviderId, e.target.value)).then(setView)}
                    >
                      {!entry?.modelId && <option value="" disabled>—</option>}
                      {roleModels.map((m) => (
                        <option key={m.modelId} value={m.modelId}>
                          {m.displayName}{m.status === "unverified" ? ` · ${t("settings.modelUnverified")}` : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}
              {role === "DIALOGUE" && (
                <p className="settings-hint">{t("settings.textModelHint")}</p>
              )}
              {roleIsConfiguredButNotImplemented(readiness, runtimeWired) && (
                <p className="settings-hint role-row-future">{t("readiness.FUTURE_NOT_WIRED")}</p>
              )}
            </div>
          );
        })}
      </div>
      <p className="settings-hint settings-model-change-note">{t("settings.modelChangeNote")}</p>

      {/* Dialogue operational context budget -- separate from Local model num_ctx */}
      <h3 className="settings-section">{t("settings.section.dialogueContext")}</h3>
      <p className="settings-hint">{t("settings.dialogueContextBudgetHint")}</p>
      <div className="role-row-selects">
        {DIALOGUE_CONTEXT_BUDGET_PRESETS.map((p) => (
          <button
            key={p.value}
            type="button"
            className={
              view.dialogueContextBudget.estTokens === p.value ? "btn btn-sm btn-active" : "btn btn-sm"
            }
            onClick={() => {
              setBudgetError(null);
              guard(client.setDialogueContextBudget(p.value)).then(setView);
            }}
          >
            {p.label}
            {p.value === view.dialogueContextBudget.default
              ? ` (${t("settings.dialogueContextPresetDefault")})`
              : ""}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{t("settings.dialogueContextBudget")}</span>
        <input
          key={view.dialogueContextBudget.estTokens}
          type="number"
          name="dialogue_context_budget"
          min={view.dialogueContextBudget.min}
          max={view.dialogueContextBudget.max}
          defaultValue={view.dialogueContextBudget.estTokens}
          onBlur={(e) => {
            const raw = e.target.value.trim();
            const n = Number(raw);
            if (raw === "" || !isValidDialogueContextBudget(n, view)) {
              setBudgetError(t("settings.dialogueContextBudgetInvalid"));
              return;
            }
            setBudgetError(null);
            guard(client.setDialogueContextBudget(n)).then(setView);
          }}
        />
      </label>
      {budgetError && <p className="settings-warn" role="alert">{budgetError}</p>}

      {/* Local model -- technical Base URL + num_ctx live behind a collapsed
          advanced disclosure so they don't compete with "Контекст диалога". */}
      <h3 className="settings-section">{t("settings.section.local")}</h3>
      <button
        type="button"
        className="btn btn-sm"
        aria-expanded={localAdvancedOpen}
        onClick={() => setLocalAdvancedOpen((v) => !v)}
      >
        {localAdvancedOpen ? "▾" : "▸"} {t("settings.section.localAdvanced")}
      </button>
      {localAdvancedOpen && (
        <>
          <label className="field">
            <span>{t("settings.localBaseUrl")}</span>
            <input
              defaultValue={view.local.baseUrl}
              onBlur={(e) => guard(client.setLocalSettings({ baseUrl: e.target.value })).then(setView)}
            />
          </label>
          <label className="field">
            <span>{t("settings.localNumCtx")}</span>
            <input
              type="number"
              name="num_ctx"
              min={view.local.numCtxMin}
              max={view.local.numCtxMax}
              defaultValue={view.local.numCtx ?? ""}
              onBlur={(e) => {
                const raw = e.target.value.trim();
                const n = raw === "" ? null : Number(raw);
                guard(client.setLocalSettings({ numCtx: n })).then(setView);
              }}
            />
          </label>
          <p className="settings-hint">{t("settings.localNumCtxHint")}</p>
          {localContextWarning(view) && (
            <p className="settings-warn" role="alert">
              {t("settings.contextWarn", { hint: view.local.kiraSafeHint })}
            </p>
          )}
        </>
      )}

      {/* Security status */}
      <h3 className="settings-section">{t("settings.section.security")}</h3>
      <ul className="settings-security">
        <li>{t("settings.security.keys")}</li>
        <li>
          {t("settings.security.fallback")}{" "}
          <strong>{view.allowCloudFallback ? t("settings.security.fallbackOn") : t("settings.security.fallbackOff")}</strong>
          {" "}({autoFallbackDefault() ? "" : t("settings.security.fallbackDefault")}).
        </li>
        <li>{t("settings.security.upload")}</li>
      </ul>
    </section>
  );
}
