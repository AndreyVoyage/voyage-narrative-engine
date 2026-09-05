import type { MemoryEventSummary } from "../../client/types";
import { DataTableShell, type DataTableColumn } from "../primitives/DataTableShell";

export interface MemoryTableProps {
  readonly events: readonly MemoryEventSummary[];
}

const PROVENANCE_LABELS: Record<string, string> = {
  USER_STATED: "Сообщил пользователь",
  CHARACTER_UTTERANCE: "Сказал персонаж / модель",
  SCENE_SETUP: "Условие сцены",
  LEGACY_UNCLASSIFIED: "Старая запись — не классифицировано",
};

/**
 * Developer/debug observability: causal-order runtime memory. Built on
 * `DataTableShell` specifically so it CANNOT reproduce the vanilla Character
 * Lab's earlier vertical-collapse bug -- height always grows with row count,
 * only width scrolls.
 */
export function MemoryTable({ events }: MemoryTableProps) {
  const columns: readonly DataTableColumn<MemoryEventSummary>[] = [
    { key: "seq", header: "seq", render: (e) => e.seq ?? "—" },
    {
      key: "provenance",
      header: "источник / provenance",
      render: (e) => PROVENANCE_LABELS[e.provenance] ?? e.provenance,
    },
    { key: "content", header: "содержание", render: (e) => e.meaning, wrap: true },
  ];

  return (
    <DataTableShell
      columns={columns}
      rows={events}
      rowKey={(e) => e.eventId}
      emptyMessage="Память пуста."
    />
  );
}
