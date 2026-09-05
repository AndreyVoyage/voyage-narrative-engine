import type { PropsWithChildren } from "react";
import { Stack } from "../primitives/Stack";

/** Content wrapper for the AppShell's `inspector` slot: loaded-state /
 * context summary. Its children do not self-pad, so this wrapper carries
 * the ONE content-padding layer for the inspector region
 * (`.clab-inspector-content` in styles/layout.css) -- never width. */
export function InspectorPanel({ children }: PropsWithChildren<unknown>) {
  return (
    <Stack gap={4} className="clab-inspector-content">
      {children}
    </Stack>
  );
}
