import type { PropsWithChildren, ReactNode } from "react";

export interface FormGridProps {
  readonly className?: string;
}

/** A responsive auto-fit field grid -- fields wrap onto new rows rather than
 * squeezing or overflowing the panel. */
export function FormGrid({ className, children }: PropsWithChildren<FormGridProps>) {
  const cls = className ? `clab-form-grid ${className}` : "clab-form-grid";
  return <div className={cls}>{children}</div>;
}

export interface FormFieldProps {
  readonly label: ReactNode;
  readonly htmlFor?: string;
}

export function FormField({ label, htmlFor, children }: PropsWithChildren<FormFieldProps>) {
  return (
    <label className="clab-form-field" htmlFor={htmlFor}>
      <span className="clab-form-field__label">{label}</span>
      {children}
    </label>
  );
}
