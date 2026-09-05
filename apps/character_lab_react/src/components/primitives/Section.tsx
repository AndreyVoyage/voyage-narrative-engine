import type { PropsWithChildren, ReactNode } from "react";

export interface SectionProps {
  readonly title?: ReactNode;
  readonly className?: string;
}

/** A labeled vertical grouping within a Panel/Card. */
export function Section({ title, className, children }: PropsWithChildren<SectionProps>) {
  const cls = className ? `clab-section ${className}` : "clab-section";
  return (
    <div className={cls}>
      {title !== undefined && <div className="clab-section__title">{title}</div>}
      {children}
    </div>
  );
}
