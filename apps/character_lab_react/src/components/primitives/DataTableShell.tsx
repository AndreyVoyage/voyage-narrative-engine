import type { ReactNode } from "react";

export interface DataTableColumn<TRow> {
  readonly key: string;
  readonly header: ReactNode;
  readonly render: (row: TRow) => ReactNode;
  /** Long/variable-length content (e.g. free text) wraps instead of forcing
   * the whole table wider. */
  readonly wrap?: boolean;
}

export interface DataTableShellProps<TRow> {
  readonly columns: readonly DataTableColumn<TRow>[];
  readonly rows: readonly TRow[];
  readonly rowKey: (row: TRow, index: number) => string;
  readonly emptyMessage?: ReactNode;
}

/**
 * A reusable table shell: horizontal scroll only when content is wider than
 * its container; height always grows naturally with row count. This is the
 * structural fix for the vanilla Character Lab's earlier "current state
 * table collapses to a clipped sliver" bug -- no component built on this
 * shell can reproduce it, because vertical clipping is never introduced
 * here in the first place.
 */
export function DataTableShell<TRow>({
  columns,
  rows,
  rowKey,
  emptyMessage,
}: DataTableShellProps<TRow>) {
  return (
    <div className="clab-data-table-shell">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey(row, index)}>
              {columns.map((col) => (
                <td key={col.key} data-wrap={col.wrap ? "true" : undefined}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} data-wrap="true">
                {emptyMessage ?? "Нет данных."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
