import { useCallback, useEffect, useRef, useState } from "react";
import type { CharacterClient } from "../../client/characterClient";
import type { EvolutionCandidate, EvolutionProposal } from "../../client/types";
import { FormField, FormGrid, Inline, Section } from "../../components/primitives";

interface Props {
  readonly client: CharacterClient;
  readonly workspaceId: string;
  readonly onChanged: () => Promise<void>;
}

export function EvolutionPanel({ client, workspaceId, onChanged }: Props) {
  const [candidates, setCandidates] = useState<readonly EvolutionCandidate[]>([]);
  const [filter, setFilter] = useState("PENDING");
  const [operator, setOperator] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const mounted = useRef(false);
  const pending = useRef(false);
  const generation = useRef(0);
  const [domain, setDomain] = useState<EvolutionProposal["domain"]>("PSYCHOLOGY");
  const [operation, setOperation] = useState<EvolutionProposal["operation"]>("ADJUST");
  const [timescale, setTimescale] = useState<EvolutionProposal["timescale"]>("MEDIUM");
  const [stateKey, setStateKey] = useState("");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [basis, setBasis] = useState("");
  const [confidence, setConfidence] = useState("");

  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const rows = await client.listEvolutionCandidates(workspaceId);
      if (mounted.current && current === generation.current) setCandidates(rows);
    } finally {
      if (mounted.current && current === generation.current) setLoading(false);
    }
  }, [client, workspaceId]);

  useEffect(() => {
    mounted.current = true;
    void reload().catch(err => {
      if (mounted.current) setError(String(err));
    });
    return () => { mounted.current = false; generation.current += 1; };
  }, [reload]);

  async function run(action: () => Promise<unknown>, success: string) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await action();
      if (mounted.current) setNotice(success);
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : String(err));
    } finally {
      // Reconcile even after an uncertain response or another operator's decision.
      if (mounted.current) {
        try { await Promise.all([reload(), onChanged()]); }
        catch (err) { if (mounted.current) setError(`Не удалось обновить данные: ${String(err)}`); }
        if (mounted.current) setBusy(false);
      }
      pending.current = false;
    }
  }

  const visible = candidates.filter(c => filter === "ALL" || c.status === filter);
  const validNumber = /^-?\d+$/.test(value.trim()) && Number.isSafeInteger(Number(value));
  const validConfidence = confidence.trim() !== "" && Number.isFinite(Number(confidence)) && Number(confidence) >= 0 && Number(confidence) <= 1;

  return (
    <Section title="Предложения изменений">
      <p>Состояние меняется только после одобрения оператором. Уверенность — оценка предложения.</p>
      <Inline>
        <FormField label="Показать">
          <select aria-label="Показать" className="clab-select" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="PENDING">Ожидают решения</option>
            <option value="APPROVED">Одобрены</option>
            <option value="REJECTED">Отклонены</option>
            <option value="ALL">Все</option>
          </select>
        </FormField>
        <button className="clab-btn" disabled={busy || loading} onClick={() => {
          setError(null);
          void reload().catch(err => { if (mounted.current) setError(String(err)); });
        }}>Обновить предложения</button>
      </Inline>
      <FormGrid>
        <FormField label="Оператор (обязательно для решения)">
          <input className="clab-input" value={operator} onChange={e => setOperator(e.target.value)} />
        </FormField>
        <FormField label="Комментарий к решению">
          <input className="clab-input" value={decisionReason} onChange={e => setDecisionReason(e.target.value)} />
        </FormField>
      </FormGrid>
      {error && <p role="alert" className="clab-state-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {loading && <p role="status">Загрузка предложений…</p>}
      {!loading && visible.length === 0 && <p>Предложений в этой категории нет.</p>}
      {visible.map(c => (
        <article key={c.candidate_id} className="clab-evolution-candidate">
          <strong>{c.domain} · {c.key} · {c.status}</strong>
          <p>{c.operation === "SET" ? `Установить: ${c.proposed_value}` : `Изменить на: ${c.proposed_delta} (от значения на момент одобрения)`}</p>
          <p>Причина: {c.reason}</p>
          <p>Основания: {c.basis_event_ids.join(", ")}</p>
          <p>Уверенность: {c.confidence} · Темп: {c.timescale}</p>
          <small>{c.candidate_id} · {c.created_at}</small>
          {c.timescale === "AUTHOR_ONLY" && <p>Только для рассмотрения: одобрение недоступно.</p>}
          {c.decision ? (
            <p>Решение: {c.decision.decision} · {c.decision.decided_by} · {c.decision.decided_at}
              {c.decision.reason && ` · ${c.decision.reason}`}
              {c.state_event_id && ` · Событие: ${c.state_event_id}`}</p>
          ) : (
            <Inline>
              <button className="clab-btn" disabled={busy || loading || !operator.trim() || c.timescale === "AUTHOR_ONLY"}
                onClick={() => void run(() => client.decideEvolutionCandidate(workspaceId, c.candidate_id, "APPROVE", operator.trim(), decisionReason.trim() || undefined), "Предложение одобрено.")}>Одобрить</button>
              <button className="clab-btn" disabled={busy || loading || !operator.trim()}
                onClick={() => void run(() => client.decideEvolutionCandidate(workspaceId, c.candidate_id, "REJECT", operator.trim(), decisionReason.trim() || undefined), "Предложение отклонено.")}>Отклонить</button>
            </Inline>
          )}
        </article>
      ))}
      <details>
        <summary>Добавить предложение вручную</summary>
        <form onSubmit={e => {
          e.preventDefault();
          if (!validNumber || !validConfidence) return;
          void run(() => client.createEvolutionCandidate(workspaceId, {
            domain, operation, timescale, key: stateKey.trim(), reason: reason.trim(),
            basisEventIds: basis.split(/\r?\n/).map(s => s.trim()).filter(Boolean),
            confidence: Number(confidence),
            ...(operation === "SET" ? { proposedValue: Number(value) } : { proposedDelta: Number(value) }),
          }), "Предложение сохранено и ожидает решения.");
        }}>
          <FormGrid>
            <FormField label="Область"><select aria-label="Область" className="clab-select" value={domain} onChange={e => setDomain(e.target.value as EvolutionProposal["domain"])}><option>PSYCHOLOGY</option><option>RELATIONSHIP</option></select></FormField>
            <FormField label="Ключ"><input className="clab-input" required value={stateKey} onChange={e => setStateKey(e.target.value)} placeholder={domain === "PSYCHOLOGY" ? "stress" : "andrey.trust"} /></FormField>
            <FormField label="Операция"><select aria-label="Операция" className="clab-select" value={operation} onChange={e => setOperation(e.target.value as EvolutionProposal["operation"])}><option>ADJUST</option><option>SET</option></select></FormField>
            <FormField label={operation === "SET" ? "Новое значение (−100…100)" : "Изменение (целое число)"}><input className="clab-input" required value={value} onChange={e => setValue(e.target.value)} /></FormField>
            <FormField label="Причина"><textarea aria-label="Причина" className="clab-textarea" required value={reason} onChange={e => setReason(e.target.value)} /></FormField>
            <FormField label="ID событий-оснований (по одному на строку)"><textarea aria-label="ID событий-оснований (по одному на строку)" className="clab-textarea" required value={basis} onChange={e => setBasis(e.target.value)} /></FormField>
            <FormField label="Уверенность (0…1)"><input className="clab-input" required type="number" min="0" max="1" step="any" value={confidence} onChange={e => setConfidence(e.target.value)} /></FormField>
            <FormField label="Темп"><select aria-label="Темп" className="clab-select" value={timescale} onChange={e => setTimescale(e.target.value as EvolutionProposal["timescale"])}><option>FAST</option><option>MEDIUM</option><option>SLOW</option><option>AUTHOR_ONLY</option></select></FormField>
          </FormGrid>
          <button className="clab-btn" disabled={busy || !validNumber || !validConfidence || !stateKey.trim() || !reason.trim() || !basis.trim()}>Сохранить предложение</button>
        </form>
      </details>
    </Section>
  );
}
