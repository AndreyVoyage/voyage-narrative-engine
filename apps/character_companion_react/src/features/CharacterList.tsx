import type { CompanionCharacter } from "../client/types.js";
import { useLocale } from "../i18n/react.js";

interface Props {
  characters: CompanionCharacter[];
  selectedCharacterId: string | null;
  onSelect: (characterId: string) => void;
}

/** Region A -- character selection. Neutral functional list, no visual design. */
export function CharacterList({ characters, selectedCharacterId, onSelect }: Props) {
  const { t } = useLocale();
  return (
    <nav className="panel" aria-label={t("nav.characters")}>
      <h2 className="panel-title">{t("nav.characters")}</h2>
      {characters.length === 0 ? (
        <p className="empty">{t("characters.empty")}</p>
      ) : (
        <ul className="list">
          {characters.map((c) => (
            <li key={c.characterId}>
              <button
                type="button"
                className={c.characterId === selectedCharacterId ? "row row-selected" : "row"}
                onClick={() => onSelect(c.characterId)}
              >
                {c.displayName}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
