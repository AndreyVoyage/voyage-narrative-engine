import type { CSSProperties, PropsWithChildren } from "react";

export interface StackProps {
  readonly gap?: 1 | 2 | 3 | 4 | 6;
  readonly className?: string;
  readonly style?: CSSProperties;
}

/** Vertical flex layout with a token-based gap -- never a raw pixel value. */
export function Stack({ gap = 3, className, style, children }: PropsWithChildren<StackProps>) {
  const cls = ["clab-stack", `clab-gap-${gap}`, className].filter(Boolean).join(" ");
  return (
    <div className={cls} style={style}>
      {children}
    </div>
  );
}
