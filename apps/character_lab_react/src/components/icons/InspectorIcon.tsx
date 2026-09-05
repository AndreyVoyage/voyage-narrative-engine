export interface InspectorIconProps {
  readonly className?: string;
}

/**
 * Right sidebar / inspector / details-panel glyph: an outer panel with a
 * divider near the right edge, representing the toggleable inspector pane.
 * Pure inline SVG (no icon library, no external asset) so it can inherit
 * `currentColor` like any other text/icon in the app.
 */
export function InspectorIcon({ className }: InspectorIconProps) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
      <line x1="15" y1="4.5" x2="15" y2="19.5" />
    </svg>
  );
}
