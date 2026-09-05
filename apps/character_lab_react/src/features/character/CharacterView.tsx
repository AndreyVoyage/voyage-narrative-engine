import { useAppState } from "../../app/AppState";
import { CharacterIdentityCard } from "../../components/character";
import { EmptyState, Panel } from "../../components/primitives";

export function CharacterView() {
  const { state } = useAppState();
  const character = state.characters.find((c) => c.characterId === "kira");
  const variant = state.variants.find((v) => v.variantId === state.session?.variantId);

  if (!character) {
    return (
      <Panel>
        <EmptyState title="Персонаж не загружен">Каталог персонажей ещё загружается.</EmptyState>
      </Panel>
    );
  }

  return (
    <Panel>
      <CharacterIdentityCard
        character={character}
        variant={variant}
        capabilities={state.capabilities}
      />
    </Panel>
  );
}
