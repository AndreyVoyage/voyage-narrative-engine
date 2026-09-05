import { useState } from "react";
import type { CharacterClient } from "../../client/characterClient";
import type { RuntimeStateDomain, RuntimeStateEntrySummary } from "../../client/types";
import { FormField, FormGrid, Inline, Section, Stack } from "../../components/primitives";
import { parseDeltaInput } from "./stateInput";

export interface StateEditorProps {
  readonly client: CharacterClient;
  readonly workspaceId: string;
  readonly current: readonly RuntimeStateEntrySummary[];
  readonly onChanged: () => void;
}

function currentValue(
  current: readonly RuntimeStateEntrySummary[],
  domain: RuntimeStateDomain,
  key: string
): string {
  const entry = current.find((e) => e.domain === domain && e.key === key);
  if (!entry) return "—";
  return entry.valueInt !== null ? String(entry.valueInt) : entry.value;
}

/** Minimal shared mutation wrapper: request -> await -> reload -> show a short
 * Russian error on failure. Never optimistically fakes the new value. */
function useMutation(onChanged: () => void) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return { error, busy, run };
}

function ErrorText({ error }: { readonly error: string | null }) {
  if (!error) return null;
  return <div className="clab-state-error">Ошибка: {error}</div>;
}

function FactEditor({ client, workspaceId, onChanged }: StateEditorProps) {
  const { error, busy, run } = useMutation(onChanged);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  return (
    <Section title="Факты">
      <FormGrid>
        <FormField label="ключ">
          <input value={key} onChange={(e) => setKey(e.target.value)} placeholder="current.test_status" />
        </FormField>
        <FormField label="значение">
          <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="произвольный текст" />
        </FormField>
      </FormGrid>
      <Inline gap={2}>
        <button
          disabled={busy || !key.trim() || !value.trim()}
          onClick={() => run(() => client.setRuntimeState(workspaceId, "FACT", key.trim(), value.trim()))}
        >
          Установить
        </button>
        <button
          disabled={busy || !key.trim()}
          onClick={() => run(() => client.removeRuntimeState(workspaceId, "FACT", key.trim()))}
        >
          Удалить
        </button>
      </Inline>
      <ErrorText error={error} />
    </Section>
  );
}

function NumericEditor({
  client,
  workspaceId,
  current,
  onChanged,
  domain,
  stateKey,
}: StateEditorProps & { readonly domain: RuntimeStateDomain; readonly stateKey: string }) {
  const { error, busy, run } = useMutation(onChanged);
  const [absolute, setAbsolute] = useState("");
  const [delta, setDelta] = useState("");

  return (
    <Section title={domain === "RELATIONSHIP" ? "Отношения" : "Психология"}>
      <FormGrid>
        <FormField label="текущее значение">
          <span>{currentValue(current, domain, stateKey)}</span>
        </FormField>
        <FormField label="новое абсолютное значение">
          <input value={absolute} onChange={(e) => setAbsolute(e.target.value)} placeholder="30" />
        </FormField>
        <FormField label="изменение Δ">
          <input value={delta} onChange={(e) => setDelta(e.target.value)} placeholder="+10" />
        </FormField>
      </FormGrid>
      <Inline gap={2}>
        <button
          disabled={busy || !absolute.trim()}
          onClick={() => run(() => client.setRuntimeState(workspaceId, domain, stateKey, absolute.trim()))}
        >
          Установить
        </button>
        <button
          disabled={busy || parseDeltaInput(delta) === null}
          onClick={() => {
            const d = parseDeltaInput(delta);
            if (d !== null) run(() => client.adjustRuntimeState(workspaceId, domain, stateKey, d));
          }}
        >
          Изменить на Δ
        </button>
        <button disabled={busy} onClick={() => run(() => client.removeRuntimeState(workspaceId, domain, stateKey))}>
          Удалить
        </button>
      </Inline>
      <ErrorText error={error} />
    </Section>
  );
}

/**
 * Runtime State editing for the three domains, through the CharacterClient
 * boundary only (SET / ADJUST / REMOVE). No state logic lives here -- every
 * mutation delegates to the client, and the view reloads current state after
 * each successful mutation.
 */
export function StateEditor(props: StateEditorProps) {
  const { client, workspaceId, current, onChanged } = props;
  const [relationshipSubject, setRelationshipSubject] = useState("");
  const [relationshipDimension, setRelationshipDimension] = useState("");
  const [psychologyDimension, setPsychologyDimension] = useState("");

  const relationshipKey = relationshipSubject.trim() && relationshipDimension.trim()
    ? `${relationshipSubject.trim()}.${relationshipDimension.trim()}`
    : "";

  return (
    <div className="clab-state-editor">
      <Stack gap={6}>
        <FactEditor {...props} />

      <Section title="Отношения">
        <FormGrid>
          <FormField label="subject">
            <input value={relationshipSubject} onChange={(e) => setRelationshipSubject(e.target.value)} placeholder="andrey" />
          </FormField>
          <FormField label="dimension">
            <input value={relationshipDimension} onChange={(e) => setRelationshipDimension(e.target.value)} placeholder="trust" />
          </FormField>
        </FormGrid>
        <div className="clab-state-key">
          ключ: <code>{relationshipKey || "subject.dimension"}</code>
        </div>
        {relationshipKey && (
          <NumericEditor
            key={relationshipKey}
            client={client}
            workspaceId={workspaceId}
            current={current}
            onChanged={onChanged}
            domain="RELATIONSHIP"
            stateKey={relationshipKey}
          />
        )}
      </Section>

      <Section title="Психология">
        <FormGrid>
          <FormField label="dimension">
            <input value={psychologyDimension} onChange={(e) => setPsychologyDimension(e.target.value)} placeholder="stress" />
          </FormField>
        </FormGrid>
        <div className="clab-state-key">
          ключ: <code>{psychologyDimension.trim() || "dimension"}</code>
        </div>
        {psychologyDimension.trim() && (
          <NumericEditor
            key={psychologyDimension.trim()}
            client={client}
            workspaceId={workspaceId}
            current={current}
            onChanged={onChanged}
            domain="PSYCHOLOGY"
            stateKey={psychologyDimension.trim()}
          />
        )}
      </Section>
      </Stack>
      </div>
  );
}
