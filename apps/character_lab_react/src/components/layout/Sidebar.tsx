import type { PropsWithChildren } from "react";
import { Stack } from "../primitives/Stack";

/** Content wrapper for the AppShell's `sidebar` slot: navigation,
 * character/variant/session lists. Its children do not self-pad, so this
 * wrapper carries the ONE content-padding layer for the sidebar region
 * (`.clab-sidebar-content` in styles/layout.css) -- never width (that
 * belongs to `.clab-app-shell__sidebar` in layout.css). */
export function Sidebar({ children }: PropsWithChildren<unknown>) {
  return (
    <Stack gap={4} className="clab-sidebar-content">
      {children}
    </Stack>
  );
}
