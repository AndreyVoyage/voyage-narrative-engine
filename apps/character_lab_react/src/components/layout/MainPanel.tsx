import type { PropsWithChildren } from "react";
import { Stack } from "../primitives/Stack";

/** Content wrapper for the AppShell's `main` slot: the active feature
 * workspace. Owns NO padding of its own -- every feature view already
 * supplies exactly one padding layer via `Panel`, so padding here would
 * double it. Only structural sizing (`min-width`/`min-height`) lives in
 * `.clab-main-content` (styles/layout.css). */
export function MainPanel({ children }: PropsWithChildren<unknown>) {
  return (
    <Stack gap={4} className="clab-main-content">
      {children}
    </Stack>
  );
}
