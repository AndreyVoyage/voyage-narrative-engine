import type { PropsWithChildren, ReactNode } from "react";

export interface EmptyStateProps {
  readonly title: ReactNode;
  readonly action?: ReactNode;
}

export function EmptyState({ title, action, children }: PropsWithChildren<EmptyStateProps>) {
  return (
    <div className="clab-empty-state">
      <strong>{title}</strong>
      {children}
      {action}
    </div>
  );
}
