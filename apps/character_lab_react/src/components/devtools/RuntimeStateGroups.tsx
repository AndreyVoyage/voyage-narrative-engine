import type { RuntimeStateDomain, RuntimeStateEntrySummary } from "../../client/types";
import { DataTableShell, type DataTableColumn } from "../primitives/DataTableShell";
import { EmptyState } from "../primitives/EmptyState";
import { Section } from "../primitives/Section";
import { Stack } from "../primitives/Stack";

export interface RuntimeStateGroupsProps {
  readonly current: readonly RuntimeStateEntrySummary[];
}

const DOMAIN_LABELS: Record<RuntimeStateDomain, string> = {
  FACT: "Факты",
  RELATIONSHIP: "Отношения",
  PSYCHOLOGY: "Психология",
};

const DOMAIN_ORDER: readonly RuntimeStateDomain[] = ["FACT", "RELATIONSHIP", "PSYCHOLOGY"];

const columns: readonly DataTableColumn<RuntimeStateEntrySummary>[] = [
  { key: "key", header: "ключ", render: (e) => e.key },
  { key: "value", header: "значение", render: (e) => e.value, wrap: true },
  { key: "source", header: "источник", render: (e) => e.sourceKind },
  { key: "seq", header: "seq", render: (e) => e.seq ?? "—" },
];

/**
 * Developer/debug observability: Runtime State (explicitly operator-
 * confirmed only -- never automatically promoted from memory, model output,
 * or Scene). FACT / RELATIONSHIP / PSYCHOLOGY are always shown as separate
 * visible groups, never merged into one undifferentiated table.
 */
export function RuntimeStateGroups({ current }: RuntimeStateGroupsProps) {
  return (
    <Stack gap={6}>
      {DOMAIN_ORDER.map((domain) => {
        const rows = current.filter((e) => e.domain === domain);
        return (
          <Section key={domain} title={DOMAIN_LABELS[domain]}>
            {rows.length === 0 ? (
              <EmptyState title="Не инициализировано">
                Для этого домена ещё нет подтверждённых значений.
              </EmptyState>
            ) : (
              <DataTableShell columns={columns} rows={rows} rowKey={(e) => `${e.domain}.${e.key}`} />
            )}
          </Section>
        );
      })}
    </Stack>
  );
}
