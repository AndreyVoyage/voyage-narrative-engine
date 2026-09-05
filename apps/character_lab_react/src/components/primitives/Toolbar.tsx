import type { PropsWithChildren } from "react";

export interface ToolbarProps {
  readonly className?: string;
}

/** A horizontal row of actions/status, wrapping instead of overflowing. */
export function Toolbar({ className, children }: PropsWithChildren<ToolbarProps>) {
  const cls = className ? `clab-toolbar ${className}` : "clab-toolbar";
  return <div className={cls}>{children}</div>;
}
