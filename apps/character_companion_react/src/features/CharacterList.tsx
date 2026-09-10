import type { CompanionCharacter } from "../client/types.js";
import { portraitFor } from "../assets/portrait.js";
import { useLocale } from "../i18n/react.js";

interface Props {
  characters: CompanionCharacter[];
  selectedCharacterId: string | null;
  onSelect: (characterId: string) => void;
  onOpenProfile: (characterId: string) => void;
}

/**
 * Region A — character selection. Compact premium cards: avatar, display name,
 * a ~2-line short description, and a "Подробнее" action that opens the public
 * profile drawer. Selecting a card keeps its existing behaviour (loads that
 * character's dialogues); opening the profile never changes selection.
 */
export function CharacterList({ characters, selectedCharacterId, onSelect, onOpenProfile }: Props) {
  const { t } = useLocale();
  return (
    <nav className="panel" aria-label={t("nav.characters")}>
      <h2 className="panel-title">{t("nav.characters")}</h2>
      {characters.length === 0 ? (
        <p className="empty">{t("characters.empty")}</p>
      ) : (
        <ul className="list char-card-list">
          {characters.map((c) => (
            <li key={c.characterId}>
              <div
                className={
                  c.characterId === selectedCharacterId
                    ? "char-card char-card-selected"
                    : "char-card"
                }
              >
                <button
                  type="button"
                  className="char-card-main"
                  aria-pressed={c.characterId === selectedCharacterId}
                  onClick={() => onSelect(c.characterId)}
                >
                  <img
                    className="char-card-avatar"
                    src={portraitFor(c.characterId)}
                    alt=""
                    aria-hidden="true"
                  />
                  <span className="char-card-text">
                    <span className="char-card-name">{c.displayName}</span>
                    {c.shortDescription && (
                      <span className="char-card-desc">{c.shortDescription}</span>
                    )}
                  </span>
                </button>
                <button
                  type="button"
                  className="char-card-details"
                  onClick={() => onOpenProfile(c.characterId)}
                >
                  {t("profile.details")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
