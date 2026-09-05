/**
 * Character Lab feature navigation.
 *
 * `tier` is the structural line between "character UI" (Chat / Character /
 * Scene -- concepts a future consumer Character App could plausibly reuse)
 * and "developer/debug UI" (Memory Inspector / Runtime State / Turn
 * Debugger -- backend observability a normal consumer app never needs).
 * The tier drives which component layer (`components/character` vs
 * `components/devtools`) a feature view is built from, and gives the nav a
 * visibly distinct debug accent (see `styles/components.css`).
 */

export type FeatureKey = "chat" | "character" | "memory" | "state" | "scene" | "turnDebugger";
export type FeatureTier = "character" | "debug";

export interface NavItem {
  readonly key: FeatureKey;
  readonly label: string;
  readonly tier: FeatureTier;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { key: "chat", label: "Чат", tier: "character" },
  { key: "character", label: "Персонаж", tier: "character" },
  { key: "memory", label: "Память", tier: "debug" },
  { key: "state", label: "Состояние", tier: "debug" },
  { key: "scene", label: "Сцена", tier: "character" },
  { key: "turnDebugger", label: "Turn Debugger", tier: "debug" },
];

export const DEFAULT_FEATURE: FeatureKey = "chat";
