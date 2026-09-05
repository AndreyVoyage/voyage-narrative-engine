import type { ManifestItemSummary, TurnDebugBundle } from "../../client/types";
import { DataTableShell, type DataTableColumn } from "../primitives/DataTableShell";
import { EmptyState } from "../primitives/EmptyState";
import { Section } from "../primitives/Section";
import { Stack } from "../primitives/Stack";

export interface TurnDebuggerPanelProps {
  readonly bundle: TurnDebugBundle | null;
}

/**
 * Developer/debug observability for one turn: the deterministic assembly
 * manifest (SELECTED / DELIVERED, proven only from the captured request
 * bytes) and the exact captured transport request. Never provider
 * reasoning/chain-of-thought -- `CharacterDebugClient` does not expose that,
 * so there is nothing here to accidentally surface.
 */
export function TurnDebuggerPanel({ bundle }: TurnDebuggerPanelProps) {
  if (!bundle) {
    return (
      <EmptyState title="Ход не выбран">
        Отправьте сообщение в Чате, затем выберите ход для отладки.
      </EmptyState>
    );
  }

  const manifestColumns: readonly DataTableColumn<ManifestItemSummary>[] = [
    { key: "kind", header: "kind", render: (i) => i.kind },
    { key: "text", header: "текст", render: (i) => i.text, wrap: true },
    { key: "selected", header: "SELECTED", render: (i) => (i.selected ? "✓" : "—") },
    { key: "delivered", header: "DELIVERED", render: (i) => (i.delivered ? "✓" : "—") },
  ];

  return (
    <Stack gap={6}>
      <Section title="Ход">
        <div>turn_id: {bundle.turn.turnId}</div>
        <div>variant_id: {bundle.turn.variantId ?? "—"}</div>
      </Section>

      <Section title="Context Manifest">
        <DataTableShell
          columns={manifestColumns}
          rows={bundle.manifest.items}
          rowKey={(item, index) => `${item.kind}-${index}`}
        />
      </Section>

      <Section title="Request Capture">
        <div className="clab-hash">SHA-256: {bundle.request.requestHash ?? "—"}</div>
        <pre
          className="clab-card"
          style={{ overflowX: "auto", fontFamily: "var(--clab-font-mono)", fontSize: "var(--clab-text-xs)" }}
        >
          {bundle.request.rawRequestJson ?? "(нет данных)"}
        </pre>
      </Section>
    </Stack>
  );
}
