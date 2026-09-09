import { useEffect, useState } from "react";
import type { CompanionClient } from "../client/types.js";
import type { CompanionSettingsView, ProviderCardView, ProviderTestResult } from "../client/types.js";
import {
  autoFallbackDefault,
  localContextWarning,
  providerActions,
  providerStatusLabel,
  secretDraftAfterSubmit,
} from "../app/settingsState.js";

interface Props {
  client: CompanionClient;
  onClose: () => void;
}

/** Companion Settings — A. Providers  B. Model roles  C. Local model  D. Security.
 * No raw key is ever rendered. Attachment upload stays disabled elsewhere. */
export function SettingsPanel({ client, onClose }: Props) {
  const [view, setView] = useState<CompanionSettingsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secretDrafts, setSecretDrafts] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<Record<string, ProviderTestResult>>({});

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

  if (!view) {
    return (
      <section className="panel settings">
        <div className="settings-head"><h2 className="panel-title">Настройки</h2>
          <button type="button" className="btn btn-sm" onClick={onClose}>Закрыть</button></div>
        {error ? <p className="error" role="alert">{error}</p> : <p className="empty">Загрузка…</p>}
      </section>
    );
  }

  const dialogue = view.roles.DIALOGUE;

  function saveSecret(card: ProviderCardView) {
    const secret = (secretDrafts[card.providerId] ?? "").trim();
    if (!secret) return;
    guard(client.storeCredential(card.providerId, secret)).then((v) => {
      setView(v);
      // single-use: clear the input, never keep the raw value
      setSecretDrafts((d) => ({ ...d, [card.providerId]: secretDraftAfterSubmit() }));
    });
  }

  return (
    <section className="panel settings">
      <div className="settings-head">
        <h2 className="panel-title">Настройки</h2>
        <button type="button" className="btn btn-sm" onClick={onClose}>Закрыть</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}

      <p className="settings-note">{view.dataRoutingNote}</p>

      {/* A. Providers */}
      <h3 className="settings-section">Провайдеры</h3>
      <div className="provider-cards">
        {view.providers.filter((p) => p.providerId !== "fake").map((card) => (
          <div className="provider-card" key={card.providerId}>
            <div className="provider-card-head">
              <strong>{card.displayName}</strong>
              <span className={card.connected || !card.credentialRequired ? "pill pill-ok" : "pill"}>
                {providerStatusLabel(card)}
              </span>
            </div>
            <p className="provider-card-notes">{card.notes}</p>
            <p className="provider-card-model">Модель: {card.configuredModel}</p>
            <p className="provider-card-roles">Роли: {card.supportedRoles.join(", ")}</p>
            {card.maskedTail && <p className="provider-card-tail">Ключ: {card.maskedTail}</p>}

            {card.credentialRequired && (
              <div className="provider-card-secret">
                <input
                  type="password"
                  placeholder={card.connected ? "Заменить ключ API" : "Ключ API"}
                  value={secretDrafts[card.providerId] ?? ""}
                  onChange={(e) => setSecretDrafts((d) => ({ ...d, [card.providerId]: e.target.value }))}
                />
                <button type="button" className="btn btn-sm" onClick={() => saveSecret(card)}>
                  {card.connected ? "Заменить" : "Подключить"}
                </button>
                {card.connected && (
                  <button type="button" className="btn btn-sm" onClick={() =>
                    guard(client.deleteCredential(card.providerId)).then(setView)}>
                    Удалить ключ
                  </button>
                )}
              </div>
            )}
            <div className="provider-card-actions">
              {providerActions(card).includes("Проверить") && (
                <button type="button" className="btn btn-sm" onClick={() =>
                  guard(client.testProvider(card.providerId)).then((r) =>
                    setTestResults((t) => ({ ...t, [card.providerId]: r })))}>
                  Проверить соединение
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

      {/* B. Model roles */}
      <h3 className="settings-section">Роли моделей</h3>
      <p className="settings-hint">
        В этом релизе используется роль <strong>DIALOGUE</strong>. Остальные роли — задел на будущее.
      </p>
      <label className="field">
        <span>DIALOGUE — провайдер</span>
        <select
          value={dialogue.providerId}
          onChange={(e) => {
            const pid = e.target.value;
            const p = view.providers.find((x) => x.providerId === pid);
            guard(client.setRole("DIALOGUE", pid, p?.defaultModel ?? "")).then(setView);
          }}
        >
          {view.providers.filter((p) => p.supportedRoles.includes("DIALOGUE")).map((p) => (
            <option key={p.providerId} value={p.providerId}>{p.displayName}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>DIALOGUE — модель</span>
        <select
          value={dialogue.modelId}
          onChange={(e) => guard(client.setRole("DIALOGUE", dialogue.providerId, e.target.value)).then(setView)}
        >
          {(view.providers.find((p) => p.providerId === dialogue.providerId)?.modelCatalog ?? [dialogue.modelId])
            .map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>

      {/* C. Local model */}
      <h3 className="settings-section">Локальная модель</h3>
      <label className="field">
        <span>Базовый URL</span>
        <input
          defaultValue={view.local.baseUrl}
          onBlur={(e) => guard(client.setLocalSettings({ baseUrl: e.target.value })).then(setView)}
        />
      </label>
      <label className="field">
        <span>Размер контекста (num_ctx)</span>
        <input
          type="number"
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
      {localContextWarning(view) && <p className="settings-warn" role="alert">{localContextWarning(view)}</p>}

      {/* D. Security status */}
      <h3 className="settings-section">Безопасность</h3>
      <ul className="settings-security">
        <li>Ключи API хранятся в защищённом хранилище ОС и не попадают в интерфейс, историю или логи.</li>
        <li>
          Автоматический переход на облачного провайдера при сбое:{" "}
          <strong>{view.allowCloudFallback ? "включён" : "выключен"}</strong>
          {" "}({autoFallbackDefault() ? "" : "по умолчанию выключен"}).
        </li>
        <li>Загрузка произвольных файлов недоступна: модуль безопасной обработки вложений ещё не подключён.</li>
      </ul>
    </section>
  );
}
