export interface CharacterLabMarkProps {
  readonly className?: string;
}

/**
 * Small original Character Lab product mark: a dialogue bubble (character /
 * conversation) containing a tiny connected-node graph (lab / analysis
 * signal). No embedded text, simple geometry, recognizable at 18-24px.
 * Pure inline SVG (no external image asset, no icon library) so it inherits
 * `currentColor` and works on both dark and light surfaces.
 */
export function CharacterLabMark({ className }: CharacterLabMarkProps) {
  return (
    <svg
      className={className}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      {/* dialogue bubble */}
      <rect x="3" y="4" width="18" height="12" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 16 L7 20 L11 16 Z" fill="currentColor" />
      {/* small connected-node / analysis signal inside the bubble */}
      <line x1="8" y1="10" x2="16" y2="8" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
      <line x1="8" y1="10" x2="16" y2="12" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
      <circle cx="8" cy="10" r="1.4" fill="currentColor" />
      <circle cx="16" cy="8" r="1.4" fill="currentColor" />
      <circle cx="16" cy="12" r="1.4" fill="currentColor" />
    </svg>
  );
}
