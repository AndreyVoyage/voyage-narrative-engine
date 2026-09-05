/**
 * Shared input normalization for Runtime State numeric deltas.
 *
 * The previous Character Lab defect was that the UI invited "+10" while the
 * backend's canonical integer parsing rejected the leading "+". This helper
 * normalizes a redundant leading "+" ("+10" -> "10") BEFORE transport, in ONE
 * place, so both RELATIONSHIP and PSYCHOLOGY share the same behavior.
 *
 * It does NOT weaken backend canonical numeric validation: it only fixes the
 * leading-+ representation and refuses anything that is not a canonical
 * integer.
 */

/** Normalize a user-entered delta and parse it to an integer, or return null
 * when the input is empty or not a canonical integer (after stripping a
 * redundant leading "+"). */
export function parseDeltaInput(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const canonical = trimmed.startsWith("+") ? trimmed.slice(1) : trimmed;
  if (!/^-?\d+$/.test(canonical)) return null;
  const value = Number(canonical);
  return Number.isSafeInteger(value) ? value : null;
}

/** Normalize a redundant leading "+" to a canonical integer string:
 * "+10" -> "10". Leaves any other string unchanged (callers validate it). */
export function normalizeDeltaString(raw: string): string {
  const trimmed = raw.trim();
  return trimmed.startsWith("+") ? trimmed.slice(1) : trimmed;
}
