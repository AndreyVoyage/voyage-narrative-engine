import { EmptyState } from "./EmptyState";

export interface NotIntegratedNoticeProps {
  readonly capability: string;
}

/**
 * Honest placeholder for a `CharacterClient` capability the CURRENT
 * transport does not wire up yet (Memory / Runtime State / Scene / Turn
 * Debugger in Desktop Integration v1's `HttpCharacterClient`). Shown instead
 * of attempting a doomed request or, worse, silently continuing to display
 * mock data as if it came from a live backend.
 */
export function NotIntegratedNotice({ capability }: NotIntegratedNoticeProps) {
  return (
    <EmptyState title="Не подключено к Desktop Integration v1">
      «{capability}» ещё не переведено на текущий транспорт в этой сборке.
    </EmptyState>
  );
}
