import type { PropsWithChildren } from "react";

export interface PanelProps {
  readonly className?: string;
}

/** A generic scrollable content panel. Owns no width/height of its own --
 * it fills whatever layout region (AppShell region, drawer, etc.) contains
 * it. Feature components should reach for this instead of inventing their
 * own top-level container sizing. */
export function Panel({ className, children }: PropsWithChildren<PanelProps>) {
  const cls = className ? `clab-panel ${className}` : "clab-panel";
  return <div className={cls}>{children}</div>;
}
