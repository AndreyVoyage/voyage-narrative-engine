import { useEffect } from "react";
import type { ReactNode } from "react";

export interface AppShellProps {
  readonly topbar: ReactNode;
  readonly sidebar: ReactNode;
  readonly main: ReactNode;
  readonly inspector?: ReactNode;
  /** Only meaningful below the narrow breakpoint (sidebar becomes a drawer). */
  readonly sidebarOpen?: boolean;
  /** Only meaningful below the medium breakpoint (inspector becomes a drawer). */
  readonly inspectorOpen?: boolean;
  readonly onRequestCloseSidebar?: () => void;
  readonly onRequestCloseInspector?: () => void;
}

/**
 * The desktop-first, responsive three-region shell: sidebar (navigation) +
 * main (active feature workspace) + inspector (context/loaded-state area).
 * ALL page-level sizing lives in `styles/layout.css`'s `.clab-app-shell*`
 * rules -- this component only assembles the regions and the responsive
 * drawer state; it defines no pixel dimensions itself.
 */
export function AppShell({
  topbar,
  sidebar,
  main,
  inspector,
  sidebarOpen = false,
  inspectorOpen = false,
  onRequestCloseSidebar,
  onRequestCloseInspector,
}: AppShellProps) {
  const showScrim = sidebarOpen || inspectorOpen;

  // Escape closes whichever narrow/medium drawer is currently open. Only
  // listens while at least one is open, so it costs nothing on desktop.
  useEffect(() => {
    if (!sidebarOpen && !inspectorOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onRequestCloseSidebar?.();
        onRequestCloseInspector?.();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen, inspectorOpen, onRequestCloseSidebar, onRequestCloseInspector]);

  return (
    <div className="clab-app-shell">
      <div className="clab-app-shell__topbar">{topbar}</div>
      <nav
        id="clab-app-sidebar"
        className="clab-app-shell__sidebar"
        data-open={sidebarOpen ? "true" : "false"}
      >
        {sidebar}
      </nav>
      <main className="clab-app-shell__main">{main}</main>
      {inspector !== undefined && (
        <aside
          id="clab-app-inspector"
          className="clab-app-shell__inspector"
          data-open={inspectorOpen ? "true" : "false"}
        >
          {inspector}
        </aside>
      )}
      {showScrim && (
        <div
          className="clab-scrim"
          onClick={() => {
            onRequestCloseSidebar?.();
            onRequestCloseInspector?.();
          }}
        />
      )}
    </div>
  );
}
