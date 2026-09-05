import type { CSSProperties, PropsWithChildren } from "react";

export interface InlineProps {
  readonly gap?: 1 | 2 | 3 | 4 | 6;
  readonly className?: string;
  readonly style?: CSSProperties;
}

/** Horizontal flex layout with a token-based gap, wraps by default. */
export function Inline({ gap = 2, className, style, children }: PropsWithChildren<InlineProps>) {
  const cls = ["clab-inline", `clab-gap-${gap}`, className].filter(Boolean).join(" ");
  return (
    <div className={cls} style={style}>
      {children}
    </div>
  );
}
