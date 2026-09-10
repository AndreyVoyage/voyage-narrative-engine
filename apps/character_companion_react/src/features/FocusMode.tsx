import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CompanionMessage, ImageJob } from "../client/types.js";
import type { FocusLayout } from "../app/appearance.js";
import { FOCUS_LAYOUTS, nextFocusLayout } from "../app/appearance.js";
import { portraitFor } from "../assets/portrait.js";
import type { LocalUserProfile } from "../app/userProfile.js";
import { resolveDisplayName, userProfileInitials } from "../app/userProfile.js";
import {
  clearFocusBackgroundRef,
  getFocusBackgroundRef,
  resolveFocusBackground,
  setFocusBackgroundRef,
} from "../app/focusBackground.js";
import { buildFocusGallery, clampGalleryIndex } from "../app/focusGallery.js";
import { visibleMessages } from "../app/companionState.js";
import type { TFunction } from "../i18n/react.js";
import { Composer, type ComposerAssistant } from "./Composer.js";

interface Props {
  layout: FocusLayout;
  characterId: string | null;
  characterName: string;
  sessionId: string | null;
  messages: CompanionMessage[];
  hiddenMessageIds: number[];
  sending: boolean;
  assistant?: ComposerAssistant;
  /** Controlled current-session composer draft (owned by App, per session). */
  draft: string;
  onDraftChange: (next: string) => void;
  coverUrl: string | null;
  coverRef: string | null;
  readyImages: ImageJob[];
  imageUrl: (resultRef: string) => string;
  userProfile: LocalUserProfile;
  t: TFunction;
  onSetLayout: (layout: FocusLayout) => void;
  onSend: (text: string) => void;
  onCreateImage: () => void;
  onContextFrame: () => void;
  onExit: () => void;
  /** reuse of the existing explicit scene-cover backend action */
  onMakeCover: (resultRef: string) => void;
}

interface MessageGroup {
  role: "user" | "character";
  key: string;
  items: CompanionMessage[];
}

function groupMessages(messages: CompanionMessage[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  messages.forEach((m, i) => {
    const last = groups[groups.length - 1];
    if (last && last.role === m.role) {
      last.items.push(m);
    } else {
      groups.push({ role: m.role, key: `${m.seq ?? i}-${m.role}`, items: [m] });
    }
  });
  return groups;
}

const NEAR_BOTTOM_PX = 120;

/**
 * Focus Mode V2 — three production-quality layouts (BACKGROUND / SIDE_GALLERY /
 * CHAT_ONLY) around one centered conversation canvas. Participant identity is
 * shown per speaker group (not per message). Esc exits.
 */
export function FocusMode(props: Props) {
  const {
    layout, characterId, characterName, sessionId, messages, hiddenMessageIds, sending, assistant,
    draft, onDraftChange,
    coverUrl, coverRef, readyImages, imageUrl, userProfile, t, onSetLayout, onExit, onMakeCover,
  } = props;
  // hidden messages are omitted from every focus layout's transcript; the
  // underlying history and Runtime context are never filtered.
  const shownMessages = useMemo(
    () => visibleMessages(messages, hiddenMessageIds, false),
    [messages, hiddenMessageIds],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onExit();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onExit]);

  const readyRefs = useMemo(
    () => readyImages.filter((j) => j.state === "READY" && j.resultRef).map((j) => j.resultRef as string),
    [readyImages],
  );

  // -- BACKGROUND source: local selection → cover → identity portrait ----
  const [selectedBgRef, setSelectedBgRef] = useState<string | null>(() => getFocusBackgroundRef(sessionId));
  useEffect(() => {
    setSelectedBgRef(getFocusBackgroundRef(sessionId));
  }, [sessionId]);

  const background = resolveFocusBackground({
    selectedRef: selectedBgRef,
    readyRefs,
    coverUrl,
    imageUrl,
    characterId,
  });

  function chooseBackground(ref: string) {
    if (!sessionId) return;
    setFocusBackgroundRef(sessionId, ref);
    setSelectedBgRef(ref);
  }
  function resetBackground() {
    if (!sessionId) return;
    clearFocusBackgroundRef(sessionId);
    setSelectedBgRef(null);
  }

  // -- SIDE_GALLERY contents (portrait + distinct cover + READY images) --
  const gallery = useMemo(
    () => buildFocusGallery({ portraitUrl: portraitFor(characterId), coverRef, readyRefs, imageUrl }),
    [characterId, coverRef, readyRefs, imageUrl],
  );
  const [galleryIndex, setGalleryIndex] = useState(0);
  useEffect(() => {
    setGalleryIndex((i) => clampGalleryIndex(i, gallery.length));
  }, [gallery.length]);
  const galleryItem = gallery[clampGalleryIndex(galleryIndex, gallery.length)] ?? gallery[0];
  const galleryStep = (delta: number) => setGalleryIndex((i) => clampGalleryIndex(i + delta, gallery.length));

  // -- polished scroll behaviour --------------------------------------
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const nearBottomRef = useRef(true);
  const [showNewMessages, setShowNewMessages] = useState(false);
  const prevCountRef = useRef(shownMessages.length);

  function recomputeNearBottom() {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    nearBottomRef.current = distance <= NEAR_BOTTOM_PX;
    if (nearBottomRef.current) setShowNewMessages(false);
  }

  function scrollToBottom(behavior: ScrollBehavior = "smooth") {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    nearBottomRef.current = true;
    setShowNewMessages(false);
  }

  // history load / layout change: jump to the latest without animation
  useLayoutEffect(() => {
    scrollToBottom("auto");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, layout]);

  // new message: only auto-follow if the reader is already near the bottom;
  // otherwise surface a compact affordance and keep their scroll position.
  useEffect(() => {
    const grew = shownMessages.length > prevCountRef.current;
    prevCountRef.current = shownMessages.length;
    if (!grew) return;
    if (nearBottomRef.current) scrollToBottom("smooth");
    else setShowNewMessages(true);
  }, [shownMessages.length]);

  const groups = useMemo(() => groupMessages(shownMessages), [shownMessages]);
  const userName = resolveDisplayName(userProfile, t("profile.defaultName"));
  const userInitials = userProfileInitials(userProfile, t("profile.defaultName"));
  const isBackground = layout === "background";
  const isGallery = layout === "side_gallery";

  return (
    <div className={`focus focus-${layout}${isBackground ? " focus-background" : ""}`}>
      {isBackground && (
        <>
          <div
            className="focus-bg-layer"
            style={{ backgroundImage: `url(${background.url})` }}
            data-bg-kind={background.kind}
            aria-hidden="true"
          />
          <div className="focus-bg-scrim" aria-hidden="true" />
        </>
      )}

      <header className="focus-bar">
        <div className="focus-identity">
          <img className="focus-avatar focus-avatar-ring" src={portraitFor(characterId)} alt="" />
          <span className="focus-identity-name">{characterName || "Кира"}</span>
        </div>
        <div className="focus-layouts" role="tablist" aria-label={t("focus.layoutGroup")}>
          {FOCUS_LAYOUTS.map((l) => (
            <button
              key={l}
              type="button"
              role="tab"
              aria-selected={l === layout}
              className={l === layout ? "btn btn-sm btn-active" : "btn btn-sm"}
              onClick={() => onSetLayout(l)}
            >
              {t(`focus.layout.${l}` as const)}
            </button>
          ))}
          <button type="button" className="btn btn-sm" onClick={() => onSetLayout(nextFocusLayout(layout))}>
            {t("focus.cycle")}
          </button>
        </div>
        <button type="button" className="btn btn-sm focus-exit" onClick={onExit}>{t("focus.exit")}</button>
      </header>

      <div className="focus-body">
        {isGallery && (
          <aside className="focus-rail focus-gallery" aria-label={t("focus.gallery.portrait")}>
            <div className="focus-rail-stage">
              {galleryItem && <img src={galleryItem.src} alt={t("focus.gallery.frame")} />}
            </div>
            <div className="focus-rail-controls">
              <button
                type="button"
                className="btn btn-sm focus-rail-prev"
                onClick={() => galleryStep(-1)}
                disabled={gallery.length < 2}
                aria-label={t("focus.gallery.prev")}
              >
                ←
              </button>
              <span className="focus-rail-counter">
                {t("focus.gallery.counter", {
                  index: clampGalleryIndex(galleryIndex, gallery.length) + 1,
                  total: gallery.length,
                })}
              </span>
              <button
                type="button"
                className="btn btn-sm focus-rail-next"
                onClick={() => galleryStep(1)}
                disabled={gallery.length < 2}
                aria-label={t("focus.gallery.next")}
              >
                →
              </button>
            </div>
            {galleryItem?.kind === "generated" && galleryItem.resultRef && (
              <div className="focus-rail-actions">
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => onMakeCover(galleryItem.resultRef as string)}
                >
                  {t("focus.gallery.makeCover")}
                </button>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => chooseBackground(galleryItem.resultRef as string)}
                >
                  {t("focus.gallery.makeBackground")}
                </button>
              </div>
            )}
            {selectedBgRef && (
              <button type="button" className="btn btn-sm focus-rail-reset" onClick={resetBackground}>
                {t("focus.gallery.clearBackground")}
              </button>
            )}
            <ul className="focus-rail-strip">
              {gallery.map((it, i) => (
                <li key={it.key}>
                  <button
                    type="button"
                    className={i === clampGalleryIndex(galleryIndex, gallery.length) ? "thumb thumb-cover" : "thumb"}
                    onClick={() => setGalleryIndex(i)}
                  >
                    <img src={it.src} alt="" />
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        )}

        <div className="focus-chat">
          <div className="focus-canvas">
            <div className="focus-scroll" ref={scrollRef} onScroll={recomputeNearBottom}>
              <ol className="focus-transcript">
                {groups.map((g) => {
                  const isUser = g.role === "user";
                  return (
                    <li key={g.key} className={isUser ? "focus-group focus-group-user" : "focus-group focus-group-character"}>
                      <div className="focus-group-head">
                        {isUser ? (
                          <span className="focus-avatar focus-avatar-user" aria-hidden="true">{userInitials}</span>
                        ) : (
                          <img className="focus-avatar" src={portraitFor(characterId)} alt="" />
                        )}
                        <span className="focus-group-name">{isUser ? userName : (characterName || "Кира")}</span>
                      </div>
                      {g.items.map((m, i) => (
                        <p key={m.seq ?? `${g.key}-${i}`} className="focus-msg">
                          <span className="msg-text">{m.text}</span>
                        </p>
                      ))}
                    </li>
                  );
                })}
                {shownMessages.length === 0 && <li className="empty">{t("conversation.empty")}</li>}
              </ol>
            </div>

            {showNewMessages && (
              <button type="button" className="btn btn-sm focus-new-messages" onClick={() => scrollToBottom("smooth")}>
                {t("focus.newMessages")}
              </button>
            )}

            <div className="focus-composer">
              <Composer
                sending={sending}
                t={t}
                assistant={assistant}
                sessionId={sessionId}
                draft={draft}
                onDraftChange={onDraftChange}
                onSend={props.onSend}
                onCreateImage={props.onCreateImage}
                onContextFrame={props.onContextFrame}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
