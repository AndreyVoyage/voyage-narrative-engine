// Minimal ambient declarations for the two Node built-ins the structural
// checks use, so they compile with a bare global `tsc` (no @types/node).
declare module "node:fs" {
  export function readFileSync(path: string, encoding: string): string;
}
declare module "node:path" {
  export function join(...parts: string[]): string;
}
