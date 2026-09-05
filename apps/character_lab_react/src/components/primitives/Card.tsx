import type { PropsWithChildren } from "react";

export interface CardProps {
  readonly raised?: boolean;
  readonly className?: string;
}

export function Card({ raised, className, children }: PropsWithChildren<CardProps>) {
  const cls = ["clab-card", raised && "clab-card--raised", className].filter(Boolean).join(" ");
  return <div className={cls}>{children}</div>;
}
