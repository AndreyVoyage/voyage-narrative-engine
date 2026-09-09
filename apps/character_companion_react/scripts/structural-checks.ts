/**
 * Minimum-sufficient structural checks for the Cinematic Companion client.
 * Compiles and runs with only a global TypeScript compiler and Node.js — no
 * npm install, no DOM, no React, no network.
 *
 *   tsc --project tsconfig.checks.json
 *   node dist-checks/scripts/structural-checks.js
 *
 * Two kinds of check:
 *  - headless logic:  the pure reducer / mock client / helpers are exercised;
 *  - source markers:  the .tsx feature files are grepped for the structural
 *    contract (they cannot be type-checked here without React types).
 */

import {
  CompanionClient,
  SCENE_FIELDS,
  emptyScene,
  sceneHasAny,
} from "../src/client/types.js";
import { MockCompanionClient } from "../src/mocks/mockCompanionClient.js";
import {
  anyImageJobActive,
  companionReducer,
  displaySessionTitle,
  filterSessions,
  hiddenMessageCount,
  hiddenSessions,
  initialCompanionState,
  isSendableMessage,
  visibleMessages,
  visibleSessions,
} from "../src/app/companionState.js";
import {
  beginRewrite,
  canRestoreOriginal,
  initialAssistantState,
  restoreOriginal,
  rewriteFailed,
  rewriteSucceeded,
  sourceDraftFor,
} from "../src/app/composerAssistant.js";
import {
  FOCUS_LAYOUTS,
  IMPLEMENTED_EXPERIENCES,
  isExperienceImplemented,
  nextFocusLayout,
} from "../src/app/appearance.js";
import { draftToInput, emptyDraft, setFreeform, setMode, setSceneField, setTitle } from "../src/app/newDialog.js";
import {
  DEFAULT_LOCALE,
  UI_LOCALES,
  errorText,
  normalizeLocale,
  translate,
  LOCALE_STORAGE_KEY,
} from "../src/i18n/index.js";
import { ru } from "../src/i18n/ru.js";
import { en } from "../src/i18n/en.js";
import { es } from "../src/i18n/es.js";
import { zhCN } from "../src/i18n/zhCN.js";
import { pt } from "../src/i18n/pt.js";
import {
  DEFAULT_USER_PROFILE,
  normalizeUserProfile,
  parseUserProfile,
  serializeUserProfile,
  userProfileInitials,
  resolveDisplayName,
  USER_PROFILE_STORAGE_KEY,
} from "../src/app/userProfile.js";
import { resolveFocusBackground } from "../src/app/focusBackground.js";
import { buildFocusGallery, clampGalleryIndex } from "../src/app/focusGallery.js";
import * as fs from "node:fs";
import * as nodePath from "node:path";

// Node globals — declared locally (no @types/node), matching the Lab checks.
// The structural checks are always run from `apps/character_companion_react/`.
declare const process: { exit(code: number): never; cwd(): string };

function assert(cond: unknown, message: string): asserts cond {
  if (!cond) throw new Error(message);
}
let passed = 0;
const ok = (label: string) => { passed += 1; console.log(`  ok  - ${label}`); };

async function main(): Promise<void> {
  console.log("Character Companion — Cinematic structural checks\n");

  const SRC = nodePath.join(process.cwd(), "src");
  const read = (rel: string): string => fs.readFileSync(nodePath.join(SRC, rel), "utf8");

  const mock = new MockCompanionClient();
  const focus0 = initialCompanionState("background");

  // 33 — multi-chat list: many chats per character, newest-activity-first
  const c1 = await mock.createSession("kira", { title: "Первый" });
  const c2 = await mock.createSession("kira", { title: "Второй" });
  await mock.sendMessage(c1.sessionId, "hi");
  const listed = await mock.listSessions("kira");
  assert(listed.length === 2 && listed[0].sessionId === c1.sessionId, "newest activity first");
  ok("33. multi-chat list exists (per character, newest first)");

  // 34 + 35 — new-dialog flow: ordinary vs scene
  let draft = emptyDraft();
  assert(draft.mode === "ordinary", "default ordinary");
  assert(Object.keys(draftToInput(draft)).length === 0, "ordinary dialog carries no scene/title");
  draft = setTitle(setMode(draft, "scene"), "Вечер");
  ok("34. new-dialog draft flow exists");
  ok("35. ordinary vs scene choice exists");

  // 36 — location / time / situation / mood fields
  for (const f of SCENE_FIELDS) draft = setSceneField(draft, f, `v-${f}`);
  draft = setFreeform(draft, "свободный текст");
  const input = draftToInput(draft);
  assert(input.scene && SCENE_FIELDS.every((f) => input.scene![f] === `v-${f}`), "structured fields stored");
  assert(input.scene!.freeform === "свободный текст", "free-form stored alongside structured");
  ok("36. location/time/situation/mood + free-form fields exist");

  // 37 — random scenario action (deterministic, editable)
  const whole = await mock.randomScenario({ seed: 2 });
  assert(whole.scenario && SCENE_FIELDS.every((f) => typeof whole.scenario![f] === "string"), "random scenario fields");
  const one = await mock.randomScenario({ field: "mood", seed: 2 });
  assert(one.field === "mood" && typeof one.value === "string", "single-field dice");
  ok("37. random scenario action exists (whole + per-field)");

  // 38–41 — right wing markers
  const wing = read("features/RightWing.tsx");
  assert(/portrait/i.test(wing) && wing.includes("portraitFor("), "portrait slot resolves via portraitFor()");
  ok("38. right wing shows a persistent portrait slot");

  // KIRA identity portrait binding (owner-approved release asset)
  const portraitMod = await import("../src/assets/portrait.js");
  const kiraPortrait = portraitMod.portraitFor("kira");
  assert(kiraPortrait === "/characters/kira/KIRA_release_portrait_v1_APPROVED.png",
    "KIRA resolves to the approved release portrait");
  assert(portraitMod.hasReleasePortrait("kira") === true, "KIRA has a bound release portrait");
  const fallback = portraitMod.portraitFor("some-future-character");
  assert(fallback.startsWith("data:image/svg+xml") && portraitMod.hasReleasePortrait("x") === false,
    "unknown / future character falls back to the neutral placeholder");
  const wingSrc = read("features/RightWing.tsx");
  assert(wingSrc.includes('t("focus.portraitAlt"') && wingSrc.includes("wing-scene-image"),
    "identity portrait (localized alt) and Scene image are separate slots");
  // the portrait <img> src is always portraitFor(...), never a Scene resultRef
  assert(wingSrc.includes("<img src={portraitFor(characterId)}"), "portrait src is portraitFor(characterId)");
  const portraitImgLine = wingSrc.split("\n").find((l) => l.includes("portraitFor(characterId)")) ?? "";
  assert(!portraitImgLine.includes("imageUrl("), "portrait line does not use imageUrl()");
  ok("KIRA identity portrait bound; distinct from Scene image; fallback preserved");
  assert(wing.includes("wing-scene-image") && wing.includes("hasSceneImage"), "conditional scene image");
  ok("39. right wing conditionally shows the scene visual");
  assert(wing.includes("wing-portrait-expanded"), "portrait expansion without scene image");
  ok("40. no scene image → portrait expansion behaviour exists");
  assert(wing.includes("scene-params") && wing.includes('t("scene.mood")'), "scene parameters rendered");
  assert(ru["scene.mood"] === "Настроение" && ru["scene.place"] === "Место", "scene-field labels come from the RU dictionary unchanged");
  ok("41. scene parameters render (место/время/ситуация/настроение)");

  // 42 + 43 — image job states render, composer never disabled by a job
  let s = companionReducer(focus0, { type: "imageJobsLoaded", jobs: [
    { jobId: "j1", sessionId: "x", characterId: "kira", kind: "context", state: "GENERATING",
      createdAt: "", updatedAt: "", prompt: null, resultRef: null, error: null },
  ] });
  assert(anyImageJobActive(s.imageJobs) && s.loading === "idle", "image job active but chat not blocked");
  const conv = read("features/Conversation.tsx");
  assert(conv.includes("job-strip") && conv.includes('t("job.generating")'), "job status strip renders");
  assert(ru["job.generating"] === "Создаём изображение…", "job status text preserved in RU dictionary");
  ok("42. image job states render");
  assert(!/Composer[\s\S]*disabled=\{[^}]*job/i.test(conv), "composer not disabled by image jobs");
  ok("43. image job does not disable the composer");

  // 44 — create-image vs context-frame are distinct actions
  const composer = read("features/Composer.tsx");
  assert(composer.includes("onCreateImage") && composer.includes("onContextFrame"), "two distinct create actions");
  assert(composer.includes('t("composer.createImage")') && composer.includes('t("composer.contextFrame")'), "distinct labels");
  assert(ru["composer.createImage"] === "Создать изображение…" && ru["composer.contextFrame"] === "Кадр по контексту",
    "composer create labels preserved in RU dictionary");
  ok("44. create-image and context-frame actions are distinct");

  // 45 — arbitrary attachment upload is disabled / not implemented
  assert(/disabled/.test(composer) && composer.includes('t("composer.attachSoonTitle")'), "attach actions disabled honestly");
  assert(!/input[^>]*type=["']file["']/.test(composer), "no unsafe file picker");
  ok("45. arbitrary attachment upload actions are disabled / not implemented");

  // 46 — microphone not duplicated in the attachment menu
  const menuBlock = composer.slice(composer.indexOf("composer-menu"), composer.indexOf("</div>", composer.indexOf("composer-menu")));
  assert(!menuBlock.includes("🎤"), "microphone icon is not inside the + menu");
  assert(!/(Голосов|voice message|Записать голос|recordVoice)/i.test(menuBlock), "no voice-message entry in the + menu");
  assert(composer.includes("🎤") && composer.includes('t("composer.recordVoice")'),
    "microphone is a dedicated composer button meaning 'record a voice message'");
  assert(/Записать голосовое сообщение/.test(ru["composer.recordVoice"]), "voice-record label preserved in RU dictionary");
  ok("46. microphone is not duplicated in the attachment menu");

  // 47–51 — Focus Mode
  s = companionReducer(focus0, { type: "focusEnter" });
  assert(s.focusActive, "focus enter");
  s = companionReducer(s, { type: "focusExit" });
  assert(!s.focusActive, "focus exit");
  ok("47. Focus Mode exists");
  assert(FOCUS_LAYOUTS.length === 3 && FOCUS_LAYOUTS.join(",") === "background,side_gallery,chat_only", "three layouts (unchanged)");
  const fm = read("features/FocusMode.tsx");
  const focusCss = read("styles.css");
  assert(fm.includes("focus-background") && fm.includes("backgroundImage"), "BACKGROUND layout");
  ok("48. BACKGROUND mode exists");
  assert(fm.includes("focus-gallery") && fm.includes('layout === "side_gallery"'), "SIDE_GALLERY layout");
  ok("49. SIDE_GALLERY mode exists");
  assert(focusCss.includes(".focus-chat_only") && (FOCUS_LAYOUTS as readonly string[]).includes("chat_only"), "CHAT_ONLY layout");
  ok("50. CHAT_ONLY exists");
  assert(fm.includes('e.key === "Escape"') && fm.includes("onExit"), "Esc exits focus mode");
  ok("51. Esc exits Focus Mode");
  assert(nextFocusLayout("background") === "side_gallery" && nextFocusLayout("chat_only") === "background", "layout cycle");

  // 52 — search / filter over title + preview
  const sample = [
    { ...c1, title: "Дождливый вечер", lastMessagePreview: "про зонт" },
    { ...c2, title: "Утро", lastMessagePreview: "кофе" },
  ];
  assert(filterSessions(sample, "зонт").length === 1, "filter by preview");
  assert(filterSessions(sample, "утро").length === 1, "filter by title (case-insensitive)");
  assert(filterSessions(sample, "").length === 2, "empty query keeps all");
  ok("52. search/filter over chat title + preview exists");

  // 53 — Literary is not a broken selectable mode
  assert(IMPLEMENTED_EXPERIENCES.join(",") === "cinematic", "only cinematic implemented");
  assert(!isExperienceImplemented("literary"), "literary not implemented");
  const appSrc = read("App.tsx");
  assert(!/literary/i.test(appSrc), "App never renders a literary mode");
  ok("53. future Literary is not exposed as a broken selectable mode");

  // 54 — no Character Lab debug components imported
  for (const rel of ["App.tsx", "features/RightWing.tsx", "features/ChatList.tsx",
                     "features/NewDialog.tsx", "features/Conversation.tsx",
                     "features/Composer.tsx", "features/FocusMode.tsx",
                     "client/httpCompanionClient.ts", "mocks/mockCompanionClient.ts"]) {
    const src = read(rel).toLowerCase();
    for (const banned of ["character_lab", "characterlab", "characterdebugclient", "manifest",
                          "evolutionpanel", "runtime_state", "turndebug", "operator"]) {
      assert(!src.includes(banned), `${rel} free of '${banned}'`);
    }
  }
  ok("54. no Character Lab debug components imported");

  // extras
  const client: CompanionClient = mock;
  assert(typeof client.sendMessage === "function" && typeof client.createImageJob === "function", "client surface");
  assert(!isSendableMessage("  ") && isSendableMessage("hi"), "blank messages not sendable");
  assert(!sceneHasAny(emptyScene()) && sceneHasAny({ ...emptyScene(), place: "x" }), "sceneHasAny");
  // sendMessage must NOT advance an image job
  const sc = await mock.createSession("kira", { scene: { ...emptyScene(), place: "Кухня" } });
  const job = await mock.createImageJob(sc.sessionId, "context");
  await mock.sendMessage(sc.sessionId, "hi");
  assert((await mock.getMessages(sc.sessionId)).length === 2, "chat works with a pending job");
  const jobsAfterChat = [...(await mock.listImageJobs(sc.sessionId))];
  assert(job.state === "QUEUED", "job object captured while queued");
  assert(jobsAfterChat[0].state !== "QUEUED", "listImageJobs (poll) is what advances the job");
  ok("send never advances image jobs; polling does");

  // ---- SECURE COMPANION DESKTOP FOUNDATIONS (Settings) ----
  const settings = read("features/SettingsPanel.tsx");
  const appSrc2 = read("App.tsx");
  const stMod = await import("../src/app/settingsState.js");

  assert(appSrc2.includes("SettingsPanel") && appSrc2.includes('t("app.settings")'), "App exposes a Settings entry");
  assert(ru["app.settings"] === "Настройки", "Settings label preserved in RU dictionary");
  ok("Settings entry exists in the app");

  for (const p of ["DeepSeek", "OpenAI", "Qwen", "Local"]) {
    assert(settings.includes("provider-card"), "provider cards");
  }
  const settingsMock = new MockCompanionClient();
  const view = await settingsMock.getSettings();
  const cardIds = view.providers.map((p) => p.providerId);
  for (const id of ["deepseek", "openai", "qwen", "local"]) assert(cardIds.includes(id), `provider ${id} present`);
  ok("provider cards exist for DeepSeek / OpenAI / Qwen / Local");

  assert(/type="password"/.test(settings), "credential input is a password field");
  assert(settings.includes("secretDraftAfterSubmit"), "secret input cleared after submit");
  assert(stMod.secretDraftAfterSubmit() === "", "post-submit secret draft is empty");
  ok("secret input clears after submit");

  // no raw secret is ever rendered — the view only carries a masked tail
  const saved = await settingsMock.storeCredential("deepseek", "sk-secret-RAWVALUE-0001");
  const dsCard = saved.providers.find((p) => p.providerId === "deepseek")!;
  assert(dsCard.connected === true && !("secret" in (dsCard as unknown as Record<string, unknown>)), "no secret field on card");
  assert((dsCard.maskedTail ?? "").indexOf("RAWVALUE") === -1, "masked tail is not the raw key");
  assert(!/\{card\.(secret|apiKey|rawKey)\}/.test(settings), "panel never renders a raw key");
  ok("raw secret is not rendered after save");
  ok("connected state visible on the provider card");

  // role selector — data-driven, DIALOGUE configurable; others are foundation only
  assert(settings.includes("MODEL_ROLE_ORDER") && settings.includes("client.setRole(role,"), "data-driven role selector");
  assert(view.runtimeWiredRoles.length === 1 && view.runtimeWiredRoles[0] === "DIALOGUE", "only DIALOGUE is runtime-wired");
  const afterRole = await settingsMock.setRole("DIALOGUE", "local", "llama3.1");
  assert(afterRole.roles.DIALOGUE.providerId === "local", "role assignment applied");
  let unsupported = false;
  try { await settingsMock.setRole("STT", "deepseek", "x"); } catch { unsupported = true; }
  assert(unsupported, "unsupported role rejected");
  ok("role selector exists; DIALOGUE configurable; unsupported role rejected");

  // local model config + num_ctx
  assert(/num_ctx/i.test(settings) && /baseUrl/.test(settings), "local base URL + num_ctx fields");
  const lc = await settingsMock.setLocalSettings({ numCtx: 4096 });
  assert(lc.local.numCtx === 4096 && lc.local.numCtxWarning === true, "num_ctx set + KIRA-safe warning");
  assert(stMod.localContextWarning(lc) !== null, "context warning surfaces");
  let badCtx = false;
  try { await settingsMock.setLocalSettings({ numCtx: -1 }); } catch { badCtx = true; }
  assert(badCtx, "invalid num_ctx rejected");
  ok("Local model config + num_ctx field exist");

  // no auto-fallback by default; data-routing explanation present
  assert(stMod.autoFallbackDefault() === false && view.allowCloudFallback === false, "auto fallback off by default");
  assert(settings.includes('t("settings.security.fallbackOff")') && ru["settings.security.fallbackOff"] === "выключен",
    "settings state that fallback is off");
  assert(view.dataRoutingNote.includes("выбранному провайдеру"), "data-routing explanation present");
  assert(/дублирования/i.test(settings) || /Дублирования/.test(view.dataRoutingNote), "no-duplication statement");
  ok("no auto-fallback toggle enabled by default; data-routing explanation exists");

  // upload actions still disabled (unchanged Composer) + Cinematic preserved
  assert(/disabled/.test(composer) && !/input[^>]*type=["']file["']/.test(composer), "upload still disabled");
  assert(!/type="file"/.test(settings), "Settings adds no file input");
  const appHasCinematic = read("App.tsx");
  for (const f of ["ChatList", "RightWing", "FocusMode", "Conversation", "NewDialog"]) {
    assert(appHasCinematic.includes(f), `Cinematic component ${f} still wired`);
  }
  ok("arbitrary attachment upload still disabled; Cinematic layout preserved");

  // no Character Lab debug surface leaked into Settings
  const sLow = settings.toLowerCase();
  for (const banned of ["character_lab", "manifest", "evolutionpanel", "turndebug", "operator"]) {
    assert(!sLow.includes(banned), `SettingsPanel free of '${banned}'`);
  }
  ok("Settings panel free of Character Lab debug surface");

  // ---- KIRA COMPANION RELEASE ASSEMBLY (RC1) ----
  assert(typeof settingsMock.getReleaseInfo === "function", "client exposes getReleaseInfo");
  const rel = await settingsMock.getReleaseInfo();
  assert(rel.release.name === "KIRA Companion MVP RC1" && rel.release.version === "0.1.0-rc1", "RC1 identity");
  assert(rel.acceptedCharacter.characterId === "kira", "release info names accepted KIRA");
  assert(rel.localContext.recommendedMinNumCtx === 16384, "release info carries the num_ctx hint");
  const appSrc3 = read("App.tsx");
  assert(appSrc3.includes("getReleaseInfo") && appSrc3.includes("release.release.name"), "App shows the release name");
  assert(/mode === "release"[\s\S]*dialogueProvider === "fake"/.test(appSrc3), "App has a release-mode 'provider not configured' guard");
  // release must not hardcode a raw key anywhere in the client bundle sources
  for (const rf of ["App.tsx", "client/httpCompanionClient.ts", "mocks/mockCompanionClient.ts"]) {
    assert(!/sk-[A-Za-z0-9]{6,}/.test(read(rf)), `${rf} has no hardcoded API key`);
  }
  ok("release identity (RC1) surfaced; release-mode provider guard present; no hardcoded key");

  // ================================================================
  // FOCUS MODE V2 · USER IDENTITY · i18n
  // ================================================================
  const fmv2 = read("features/FocusMode.tsx");
  const css = read("styles.css");
  const i18nIndex = read("i18n/index.ts");
  const i18nReact = read("i18n/react.tsx");
  const profileSrc = read("app/userProfile.ts");
  const bgSrc = read("app/focusBackground.ts");
  const mainSrc = read("main.tsx");
  const settingsV2 = read("features/SettingsPanel.tsx");
  const appV2 = read("App.tsx");
  const iu = (r: string) => "/img/" + r;

  // 1 — centered / max-width bounded conversation canvas
  assert(fmv2.includes("focus-canvas") && css.includes(".focus-canvas"), "focus canvas present");
  assert(/\.focus-canvas\s*\{[^}]*max-width:\s*var\(--focus-canvas-max\)/.test(css) && /\.focus-canvas\s*\{[^}]*margin:\s*0 auto/.test(css),
    "focus canvas is centered with a bounded max-width");
  ok("V2.1 Focus chat canvas is centered / max-width bounded");

  // 2 — BACKGROUND source priority: selected → cover → portrait
  const bgSel = resolveFocusBackground({ selectedRef: "g1", readyRefs: ["g1", "g2"], coverUrl: "/c.png", imageUrl: iu, characterId: "kira" });
  const bgCover = resolveFocusBackground({ selectedRef: "gone", readyRefs: ["g2"], coverUrl: "/c.png", imageUrl: iu, characterId: "kira" });
  const bgPortrait = resolveFocusBackground({ selectedRef: null, readyRefs: [], coverUrl: null, imageUrl: iu, characterId: "kira" });
  assert(bgSel.kind === "selected" && bgSel.url === "/img/g1", "selected focus image wins when still READY");
  assert(bgCover.kind === "cover" && bgCover.url === "/c.png", "falls back to the conversation cover");
  assert(bgPortrait.kind === "portrait" && bgPortrait.url === "/characters/kira/KIRA_release_portrait_v1_APPROVED.png",
    "falls back to the identity portrait");
  assert(fmv2.includes("resolveFocusBackground("), "FocusMode uses the background priority resolver");
  ok("V2.2 BACKGROUND uses selected/cover/portrait priority");

  // 3 — BACKGROUND readability overlay
  assert(fmv2.includes("focus-bg-scrim") && css.includes(".focus-bg-scrim"), "readability scrim element + style");
  assert(/\.focus-bg-scrim\s*\{[^}]*linear-gradient/.test(css), "scrim darkens the image behind the text");
  ok("V2.3 BACKGROUND has a readability overlay");

  // 4 — SIDE_GALLERY contains portrait + READY images
  const gal = buildFocusGallery({
    portraitUrl: "/p.png", coverRef: "cov", readyRefs: ["g1", "g2"], imageUrl: iu,
  });
  assert(gal[0].kind === "portrait" && gal[0].src === "/p.png", "portrait is always first in the rail");
  assert(gal.some((i) => i.kind === "generated" && i.resultRef === "g1") && gal.some((i) => i.resultRef === "g2"),
    "all READY generated images are in the rail");
  const galDedup = buildFocusGallery({ portraitUrl: "/p.png", coverRef: "g1", readyRefs: ["g1"], imageUrl: iu });
  assert(galDedup.filter((i) => i.resultRef === "g1").length === 1, "cover that is also a READY image is not duplicated");
  assert(fmv2.includes("buildFocusGallery(") && fmv2.includes("portraitFor(characterId)") && fmv2.includes("readyImages"),
    "FocusMode builds the rail from portrait + ready images");
  ok("V2.4 SIDE_GALLERY contains portrait + READY images");

  // 5 + 6 — gallery previous/next + index counter
  assert(fmv2.includes("focus-rail-prev") && fmv2.includes("focus-rail-next"), "gallery has previous / next controls");
  ok("V2.5 gallery previous / next exists");
  assert(fmv2.includes("focus-rail-counter") && fmv2.includes('t("focus.gallery.counter"'), "gallery shows an index counter");
  assert(ru["focus.gallery.counter"].includes("{index}") && ru["focus.gallery.counter"].includes("{total}"), "counter is a parameterized label");
  assert(clampGalleryIndex(5, 3) === 2 && clampGalleryIndex(-1, 3) === 2 && clampGalleryIndex(0, 0) === 0, "gallery index wraps and tolerates empty");
  ok("V2.6 gallery index counter exists");

  // 7 — cover action reuses the explicit existing scene-cover action
  assert(fmv2.includes("onMakeCover(") && fmv2.includes('t("focus.gallery.makeCover")'), "gallery 'set as cover' calls onMakeCover");
  assert(/onMakeCover=\{makeCover\}/.test(appV2) && /function makeCover\b[\s\S]*?\.setSceneCover\(/.test(appV2),
    "onMakeCover is wired to the existing client.setSceneCover action");
  ok("V2.7 cover action still uses the explicit existing action");

  // 8 — choosing a focus background does NOT write Scene / Memory / Runtime
  assert(bgSrc.includes("localStorage"), "focus background preference is local-storage only");
  for (const banned of ["setSceneCover", "client.", "fetch(", "/api/", "import.meta"]) {
    assert(!bgSrc.includes(banned), `focusBackground.ts free of '${banned}' (no backend / Scene write)`);
  }
  assert(fmv2.includes("setFocusBackgroundRef(") && fmv2.includes("chooseBackground("), "background selection goes through the local preference");
  ok("V2.8 background selection does not write Scene / Memory");

  // 9 — CHAT_ONLY has no gallery rail
  assert(fmv2.includes('layout === "side_gallery"') && fmv2.includes("isGallery"), "rail renders only for side_gallery");
  assert(/\.focus-chat_only\s+\.focus-rail[^{]*\{[^}]*display:\s*none/.test(css), "CHAT_ONLY hides the rail");
  ok("V2.9 CHAT_ONLY has no gallery");

  // 10 + 11 — participant identity (character + local user)
  assert(fmv2.includes("focus-avatar") && fmv2.includes("focus-identity-name") && fmv2.includes("characterName"),
    "character avatar + name render");
  ok("V2.10 character avatar / name renders");
  assert(fmv2.includes("userProfileInitials(") && fmv2.includes("resolveDisplayName(") && fmv2.includes("focus-avatar-user"),
    "local user avatar + name render");
  assert(fmv2.includes("groupMessages(") && fmv2.includes("g.items.map(") && fmv2.includes("focus-group-head"),
    "messages are rendered in per-speaker groups");
  assert(fmv2.indexOf("focus-group-head") < fmv2.indexOf("g.items.map("),
    "identity chrome renders once per group, before the per-message bubbles");
  ok("V2.11 user avatar / name renders (grouped, not per-message)");

  // 12 — local user profile persists locally
  assert(DEFAULT_USER_PROFILE.displayName === "" && DEFAULT_USER_PROFILE.avatarKind === "placeholder", "sane profile default");
  const customProfile = normalizeUserProfile({ displayName: "  Мария Иванова  ", avatarKind: "image", avatarRef: "x", locale: "en" });
  assert(customProfile.displayName === "Мария Иванова" && customProfile.avatarRef === null && customProfile.locale === "en",
    "profile is normalized; image avatar ref is never hydrated yet");
  const round = parseUserProfile(serializeUserProfile(customProfile));
  assert(round.displayName === customProfile.displayName && round.locale === "en" && round.avatarKind === "image",
    "profile round-trips through serialize/parse");
  assert(profileSrc.includes("localStorage") && profileSrc.includes(USER_PROFILE_STORAGE_KEY.slice(0, 8)),
    "profile is stored in localStorage under a stable key");
  assert(resolveDisplayName({ ...DEFAULT_USER_PROFILE }, "Пользователь") === "Пользователь", "empty name falls back to the localized default");
  assert(userProfileInitials({ ...DEFAULT_USER_PROFILE, displayName: "Мария Иванова" }, "П") === "МИ", "initials from two words");
  ok("V2.12 user profile persists locally");

  // 13 — no profile file picker
  for (const rel of ["features/SettingsPanel.tsx", "features/FocusMode.tsx", "App.tsx"]) {
    assert(!/type=["']file["']/.test(read(rel)) && !/<input[^>]*\bfile\b/i.test(read(rel)), `${rel} has no file input`);
  }
  assert(settingsV2.includes('t("profile.avatarComingSoon")'), "avatar shown as a 'coming soon' status, not an upload");
  ok("V2.13 no profile file picker exists");

  // 14 — composer aligned with the centered canvas
  assert(fmv2.includes("focus-composer") && fmv2.indexOf("focus-canvas") < fmv2.indexOf("focus-composer"),
    "composer sits inside the centered focus canvas");
  assert(css.includes(".focus-composer"), "focus composer has an alignment style");
  ok("V2.14 composer aligned with centered canvas");

  // 15 + 16 — custom scrollbar CSS exists and stays visible
  assert(css.includes("::-webkit-scrollbar") && css.includes("scrollbar-color") && css.includes("scrollbar-width"),
    "custom scrollbar CSS (WebKit + standards) present");
  assert(css.includes("::-webkit-scrollbar-thumb:hover"), "scrollbar has a hover treatment");
  assert(!/::-webkit-scrollbar\s*\{[^}]*display:\s*none/.test(css) && !/::-webkit-scrollbar\s*\{[^}]*width:\s*0(px)?;/.test(css),
    "scrollbar is never fully hidden");
  ok("V2.15 custom scrollbar CSS exists");
  ok("V2.16 scrollbar remains visible");

  // 17 + 18 — polished scroll behaviour
  assert(fmv2.includes("recomputeNearBottom") && fmv2.includes("nearBottomRef") && fmv2.includes("scrollToBottom("),
    "near-bottom tracking + programmatic scroll-to-bottom");
  assert(/if \(nearBottomRef\.current\) scrollToBottom/.test(fmv2), "only auto-follows when the reader is near the bottom");
  assert(fmv2.includes("showNewMessages") && fmv2.includes('t("focus.newMessages")'), "a compact 'new messages' affordance exists");
  ok("V2.17 near-bottom autoscroll behaviour exists");
  ok("V2.18 reading older messages is not forcibly autoscrolled");

  // 19–24 — locale selector + five languages
  assert(settingsV2.includes("UI_LOCALES") && settingsV2.includes("setLocale(") && settingsV2.includes('t("profile.language")'),
    "Settings has an interface-language selector");
  ok("V2.19 locale selector exists");
  assert(JSON.stringify([...UI_LOCALES]) === JSON.stringify(["ru", "en", "es", "zh-CN", "pt"]), "five UI locales");
  for (const [name, dict] of [["en", en], ["es", es], ["zh-CN", zhCN], ["pt", pt]] as const) {
    assert(Object.keys(dict).length === Object.keys(ru).length, `${name} dictionary has the full key set`);
    assert(typeof dict["app.settings"] === "string" && dict["app.settings"].length > 0, `${name} has a real translation`);
  }
  ok("V2.20 ru available");
  ok("V2.21 en available");
  ok("V2.22 es available");
  ok("V2.23 zh-CN available");
  ok("V2.24 pt available");

  // 25 + 26 — locale persists; switches without backend restart
  assert(i18nIndex.includes(LOCALE_STORAGE_KEY.slice(0, 8)) && i18nIndex.includes("localStorage.setItem"),
    "selected locale is persisted to localStorage");
  ok("V2.25 selected locale persists");
  assert(mainSrc.includes("LocaleProvider") && i18nReact.includes("useState") && i18nReact.includes("createContext"),
    "locale lives in React state at the top of the tree");
  assert(!/location\.reload|window\.location/.test(i18nReact) && !/location\.reload/.test(settingsV2),
    "changing language never reloads the page or restarts the backend");
  assert(translate("en", "app.settings") === "Settings" && translate("ru", "app.settings") === "Настройки", "translate resolves per locale");
  assert(translate("en", "focus.gallery.counter", { index: 2, total: 5 }) === "2 / 5", "translate interpolates params");
  assert(normalizeLocale("zh") === "zh-CN" && normalizeLocale("en-US") === "en" && normalizeLocale("de") === DEFAULT_LOCALE,
    "locale normalization is robust");
  ok("V2.26 UI changes locale without backend restart");

  // 27 + 28 — conversation content is NEVER machine-translated
  for (const rel of ["features/FocusMode.tsx", "features/Conversation.tsx"]) {
    const src = read(rel);
    assert(src.includes("{m.text}"), `${rel} renders the raw message text`);
    assert(!/t\(\s*m\.text/.test(src) && !/translate\([^)]*m\.text/.test(src), `${rel} never translates message text`);
  }
  assert(!i18nIndex.includes("CompanionMessage") && !i18nIndex.includes("reply"), "i18n core has no coupling to conversation content");
  ok("V2.27 conversation content is not passed through translator");
  ok("V2.28 character replies are untouched");

  // 29 + 30 — backend error codes map through i18n; unknown → localized generic
  for (const code of ["provider_not_configured", "missing_credential", "provider_failed", "provider_unavailable", "generator_unavailable"]) {
    assert(errorText("ru", code) !== code && errorText("ru", code) !== errorText("ru", "totally_unknown_zzz"),
      `error code '${code}' maps to dedicated localized text`);
    assert(errorText("es", code) !== errorText("ru", code), `error code '${code}' is localized per locale`);
  }
  ok("V2.29 backend error codes map through i18n");
  assert(errorText("en", "totally_unknown_zzz") === translate("en", "error.unknown") && errorText("en", "totally_unknown_zzz") !== "totally_unknown_zzz",
    "unknown error code falls back to a localized generic message");
  ok("V2.30 unknown error fallback localized");

  // 31 + 32 — no Character Runtime import; no unsafe file input introduced
  for (const rel of ["i18n/index.ts", "i18n/ru.ts", "app/userProfile.ts", "app/focusBackground.ts",
                     "app/focusGallery.ts", "features/FocusMode.tsx", "features/SettingsPanel.tsx"]) {
    const low = read(rel).toLowerCase();
    for (const banned of ["character_runtime", "character_core", "runtime_service", "runtimeservice", "runtimestate", "characterpackage"]) {
      assert(!low.includes(banned), `${rel} free of '${banned}'`);
    }
  }
  ok("V2.31 no Character Runtime import introduced");
  for (const rel of ["App.tsx", "features/SettingsPanel.tsx", "features/FocusMode.tsx", "features/Composer.tsx"]) {
    assert(!/type=["']file["']/.test(read(rel)), `${rel} introduces no file input`);
  }
  ok("V2.32 no unsafe file input introduced");

  // ================================================================
  // MEDIA PROVIDERS AND MODEL ROLES V1
  // ================================================================
  const mediaSettings = read("features/SettingsPanel.tsx");
  const ru2 = ru as Record<string, string>;
  const stMod2 = await import("../src/app/settingsState.js");
  const roleView = await new MockCompanionClient().getSettings();

  // 1 — a dedicated "models by task" section exists
  assert(mediaSettings.includes('t("settings.section.modelRoles")') && mediaSettings.includes("MODEL_ROLE_ORDER"),
    "SettingsPanel has a models-by-task section");
  assert(stMod2.MODEL_ROLE_ORDER.join(",") === "DIALOGUE,VISION,IMAGE_GENERATION,VIDEO_GENERATION,STT,TTS,REALTIME,WRITING_ASSISTANT,LOCAL_ALTERNATIVE",
    "canonical role order incl. VIDEO_GENERATION + WRITING_ASSISTANT");
  ok("MPR.1 model-role configuration section exists");

  // 2 — every canonical role is visible in the catalog + has a localized label
  for (const role of ["DIALOGUE", "VISION", "IMAGE_GENERATION", "VIDEO_GENERATION", "STT", "TTS", "REALTIME"]) {
    assert(roleView.roleCatalog.some((r) => r.role === role), `roleCatalog has ${role}`);
    assert(typeof ru2[`role.${role}`] === "string" && ru2[`role.${role}`].length > 0, `role.${role} localized`);
  }
  ok("MPR.2 DIALOGUE + VISION + IMAGE_GENERATION + VIDEO_GENERATION + STT + TTS + REALTIME visible");

  // 3 — provider dropdown is data-driven (no hardcoded provider===... in components)
  assert(mediaSettings.includes("providersForRole(view, role)") && !/provider(Id)?\s*===\s*["']openai["']/.test(mediaSettings),
    "provider options come from the catalog, not a hardcoded check");
  const imgProviders = stMod2.providersForRole(roleView, "IMAGE_GENERATION").map((p) => p.providerId);
  assert(imgProviders.includes("openai") && !imgProviders.includes("deepseek"),
    "IMAGE_GENERATION providers are catalog-filtered");
  ok("MPR.3 provider dropdown data-driven");

  // 4 — model dropdown is filtered by the model's own capabilities
  const openaiCard = roleView.providers.find((p) => p.providerId === "openai")!;
  const visionModels = stMod2.modelsForRole(openaiCard, "VISION").map((m) => m.modelId);
  const imageModels = stMod2.modelsForRole(openaiCard, "IMAGE_GENERATION").map((m) => m.modelId);
  assert(visionModels.includes("gpt-4o-mini") && !visionModels.includes("gpt-image-1"), "VISION models filtered by capability");
  assert(imageModels.includes("gpt-image-1") && !imageModels.includes("gpt-4o-mini"), "IMAGE_GENERATION models filtered by capability");
  assert(mediaSettings.includes("modelsForRole(providerCard, role)"), "SettingsPanel filters the model dropdown by role");
  ok("MPR.4 model dropdown filtered by capability");

  // 5 — readiness / future status is visible
  assert(mediaSettings.includes("readinessLabelKey(readiness)") && mediaSettings.includes('t("settings.runtimeWiredBadge")'),
    "role rows show a readiness / runtime-wired status");
  for (const k of ["READY", "CONFIGURED_CREDENTIAL_MISSING", "NOT_CONFIGURED", "UNSUPPORTED", "FUTURE_NOT_WIRED"]) {
    assert(typeof ru2[`readiness.${k}`] === "string", `readiness.${k} localized`);
  }
  ok("MPR.5 readiness / future status visible");

  // 6 — "configured" is explicitly not "implemented"
  const settingsMockB = new MockCompanionClient();
  await settingsMockB.setRole("IMAGE_GENERATION", "openai", "gpt-image-1");
  await settingsMockB.storeCredential("openai", "sk-media-check-RAW-0001");
  const imgRes = await settingsMockB.resolveRole("IMAGE_GENERATION");
  assert(imgRes.runtimeWired === false && imgRes.readiness === "FUTURE_NOT_WIRED",
    "configured image role resolves but is not runtime-wired");
  assert(stMod2.roleIsConfiguredButNotImplemented(imgRes.readiness, imgRes.runtimeWired),
    "helper flags configured-but-not-implemented");
  assert(mediaSettings.includes("roleIsConfiguredButNotImplemented("), "UI surfaces the configured != implemented distinction");
  ok("MPR.6 configured vs implemented distinction visible");

  // 7 — no automatic fallback: resolver returns ONLY the selected provider
  const stt = await (async () => { const c = new MockCompanionClient(); await c.setRole("STT", "openai", "whisper-1"); return c.resolveRole("STT"); })();
  assert(stt.providerId === "openai" && JSON.stringify(stt).indexOf("qwen") === -1 && JSON.stringify(stt).indexOf("deepseek") === -1,
    "role resolver names only the selected provider");
  ok("MPR.7 no automatic cross-provider fallback");

  // 8 — provider connection state visible; no raw key ever rendered
  assert(/provider-card-caps|cap-chip/.test(mediaSettings), "provider cards show a capability summary");
  assert(!/\{card\.(secret|apiKey|rawKey)\}/.test(mediaSettings) && !/sk-[A-Za-z0-9]{6,}/.test(mediaSettings),
    "no raw API key rendered in the settings panel");
  const savedView = await settingsMockB.getSettings();
  assert(JSON.stringify(savedView).indexOf("sk-media-check-RAW-0001") === -1, "stored key never re-exposed in the settings view");
  const oc = savedView.providers.find((p) => p.providerId === "openai")!;
  assert(oc.connected === true && (oc.maskedTail ?? "").indexOf("RAW") === -1, "connection state shown via masked tail only");
  ok("MPR.8 provider connection state visible; no raw key");

  // 9 — one provider credential serves several roles
  const multi = new MockCompanionClient();
  for (const [r, m] of [["VISION", "gpt-4o-mini"], ["IMAGE_GENERATION", "gpt-image-1"], ["TTS", "gpt-4o-mini-tts"]] as const) {
    await multi.setRole(r, "openai", m);
  }
  await multi.storeCredential("openai", "sk-one-key-many-roles-0002");
  for (const r of ["VISION", "IMAGE_GENERATION", "TTS"]) {
    const res = await multi.resolveRole(r);
    assert(res.providerId === "openai" && res.providerConnected === true, `${r} reuses the one openai credential`);
  }
  ok("MPR.9 one provider credential reused across roles");

  // 10 — model-change warning + all new strings go through i18n
  assert(mediaSettings.includes('t("settings.modelChangeNote")') && ru2["settings.modelChangeNote"].length > 0,
    "a localized 'model availability can change' note exists");
  for (const loc of [en, es, zhCN, pt]) {
    assert(typeof (loc as Record<string, string>)["settings.section.modelRoles"] === "string"
      && typeof (loc as Record<string, string>)["role.VIDEO_GENERATION"] === "string"
      && typeof (loc as Record<string, string>)["readiness.FUTURE_NOT_WIRED"] === "string",
      "every locale has the media-role strings");
  }
  assert(!/["']Модели по задачам["']|["']Models by task["']/.test(mediaSettings), "no hardcoded role-section string in the component");
  ok("MPR.10 model-change warning + i18n for all new strings");

  // 11 — Focus Mode V2 + Local Profile UX preserved
  const appMedia = read("App.tsx");
  for (const f of ["FocusMode", "SettingsPanel"]) assert(appMedia.includes(f), `${f} still wired`);
  assert(read("features/FocusMode.tsx").includes("focus-canvas") && read("features/SettingsPanel.tsx").includes('t("profile.section")'),
    "Focus Mode centered canvas and the Local Profile section are untouched");
  ok("MPR.11 Focus Mode V2 / Local Profile UX preserved");

  // ================================================================
  // CHAT CONTROL AND COMPOSER ASSISTANT V1
  // ================================================================
  const composerSrc = read("features/Composer.tsx");
  const convSrc = read("features/Conversation.tsx");
  const focusSrc = read("features/FocusMode.tsx");
  const chatSrc = read("features/ChatList.tsx");
  const msgActSrc = read("features/MessageActions.tsx");
  const appSrcCC = read("App.tsx");
  const ccRu = ru as Record<string, string>;
  const ccMock = new MockCompanionClient();

  // 1 — WRITING_ASSISTANT role is additive, in the settings section, not runtime-wired
  const ccView = await ccMock.getSettings();
  assert(ccView.roleCatalog.some((r) => r.role === "WRITING_ASSISTANT"), "roleCatalog has WRITING_ASSISTANT");
  assert(stMod2.MODEL_ROLE_ORDER.includes("WRITING_ASSISTANT" as (typeof stMod2.MODEL_ROLE_ORDER)[number]), "role order includes it");
  assert(ccView.runtimeWiredRoles.length === 1 && ccView.runtimeWiredRoles[0] === "DIALOGUE", "still only DIALOGUE runtime-wired");
  for (const loc of [ru, en, es, zhCN, pt]) {
    assert(typeof (loc as Record<string, string>)["role.WRITING_ASSISTANT"] === "string", "role.WRITING_ASSISTANT localized");
  }
  ok("CCA.1 WRITING_ASSISTANT role added additively, localized, not runtime-wired");

  // 2 — ✨ exists in the composer and never sends automatically
  assert(composerSrc.includes("✨") && composerSrc.includes("runAssistant") && composerSrc.includes("composer-assist"),
    "composer has a ✨ assistant control");
  assert(/setDraft\(suggestion\)/.test(composerSrc), "suggestion replaces the composer value in place");
  const submitBody = composerSrc.slice(composerSrc.indexOf("function submit"), composerSrc.indexOf("function editDraft"));
  assert(!submitBody.includes("assistant") && !/runAssistant[\s\S]{0,200}onSend/.test(composerSrc),
    "the assistant path never calls onSend");
  ok("CCA.2 ✨ exists; suggestion replaces composer text; never auto-sends");

  // 3 — no modal / dialog for the suggestion
  assert(!/role=["']dialog["']/.test(composerSrc) && !/class(Name)?=["'][^"']*modal/.test(composerSrc),
    "no modal suggestion UI");
  ok("CCA.3 no modal suggestion window");

  // 4 — disabled with a blank draft or an unconfigured assistant
  assert(/canAssist\s*=\s*assistantReady\s*&&\s*isSendableMessage\(draft\)/.test(composerSrc)
    && composerSrc.includes("disabled={!canAssist}"), "✨ disabled unless a non-blank draft + configured assistant");
  ok("CCA.4 ✨ disabled for blank draft / unconfigured role");

  // 5 — original draft preserved + regenerate from the ORIGINAL source
  let a0 = initialAssistantState();
  assert(a0.originalDraft === null, "fresh assistant state has no original draft");
  a0 = beginRewrite(a0, "прив я устал");
  assert(a0.originalDraft === "прив я устал" && a0.running === true, "beginRewrite captures the original + marks running");
  a0 = rewriteSucceeded(a0);
  a0 = beginRewrite(a0, "Привет, я устал.");             // user then pressed ✨ again on the suggestion
  assert(sourceDraftFor(a0, "Привет, я устал.") === "прив я устал", "regenerate uses the ORIGINAL draft, not the suggestion");
  assert(canRestoreOriginal(a0, "Привет, я устал.") === true, "restore affordance is offered");
  const undo = restoreOriginal(a0);
  assert(undo.draft === "прив я устал" && undo.state.originalDraft === null, "undo restores the exact original draft");
  ok("CCA.5 original draft preserved; regenerate from original; undo works");

  // 6 — draft is kept on assistant failure
  let a1 = rewriteFailed(beginRewrite(initialAssistantState(), "черновик"), "assistant_failed");
  assert(a1.running === false && a1.error === "assistant_failed" && a1.originalDraft === "черновик",
    "failure keeps the draft and records a bounded code");
  assert(composerSrc.includes("rewriteFailed") && !/catch[\s\S]{0,120}setDraft\(""\)/.test(composerSrc),
    "composer never clears the draft on failure");
  ok("CCA.6 draft remains after assistant failure");

  // 7 — assistant resolves only the configured provider/model; unconfigured -> bounded
  let unconfigured = false;
  try { await new MockCompanionClient().rewriteDraft("привет"); } catch (e) {
    unconfigured = (e as { code?: string }).code === "assistant_not_configured";
  }
  assert(unconfigured, "rewrite without a configured role fails with assistant_not_configured");
  const cc2 = new MockCompanionClient();
  await cc2.setRole("WRITING_ASSISTANT", "fake", "fake");
  const sug = await cc2.rewriteDraft("прив я сегодня устал давай просто поговорим");
  assert(sug.suggestion && sug.provider === "fake" && sug.model === "fake", "configured fake assistant returns a suggestion");
  ok("CCA.7 assistant resolves only the configured role; no fallback");

  // 8 — error codes localized in all five locales
  for (const code of ["assistant_not_configured", "assistant_failed"]) {
    assert(errorText("ru", code) !== code && errorText("en", code) !== errorText("ru", code),
      `error '${code}' mapped + localized`);
  }
  ok("CCA.8 assistant error codes map through i18n");

  // 9 — message ⋯ menu: copy + hide, NO functional sent-message edit
  assert(msgActSrc.includes("msg-actions") && msgActSrc.includes('t("message.copy")') && msgActSrc.includes('t("message.hide")'),
    "MessageActions exposes copy + hide");
  {
    const menuOnly = msgActSrc.slice(msgActSrc.indexOf('className="msg-actions-menu"'));
    assert(!/message\.edit/.test(msgActSrc) && !/(Редактировать|Editar|编辑)/.test(menuOnly) && !/>\s*Edit\s*</.test(menuOnly),
      "no functional sent-message edit command in the menu");
  }
  assert(convSrc.includes("MessageActions") && convSrc.includes("navigator.clipboard.writeText"),
    "Conversation wires the menu + real clipboard copy");
  ok("CCA.9 message ⋯ menu: copy + hide only; edit deferred");

  // 10 — hidden messages are omitted in EVERY transcript presentation mode
  const sampleMsgs = [
    { seq: 1, role: "user" as const, text: "a", createdAt: "" },
    { seq: 2, role: "character" as const, text: "b", createdAt: "" },
    { seq: 3, role: "user" as const, text: "c", createdAt: "" },
  ];
  assert(visibleMessages(sampleMsgs, [2]).length === 2 && !visibleMessages(sampleMsgs, [2]).some((m) => m.seq === 2),
    "visibleMessages drops hidden ids");
  assert(visibleMessages(sampleMsgs, [2], true).length === 3, "show-hidden override restores them");
  assert(hiddenMessageCount(sampleMsgs, [2, 3]) === 2, "hiddenMessageCount counts present hidden seqs");
  assert(convSrc.includes("visibleMessages(messages") && focusSrc.includes("visibleMessages(messages"),
    "both Conversation and FocusMode filter through visibleMessages");
  assert(focusSrc.includes("groupMessages(shownMessages)"), "FocusMode groups the FILTERED messages (all 3 layouts)");
  ok("CCA.10 hidden messages omitted in normal + all Focus layouts");

  // 11 — hidden conversations omitted from the normal list; recovery path exists
  const sampleSessions = [
    { ...(await ccMock.createSession("kira", { title: "A" })) },
    { ...(await ccMock.createSession("kira", { title: "B" })) },
  ];
  sampleSessions[1].hidden = true;
  assert(visibleSessions(sampleSessions).length === 1 && hiddenSessions(sampleSessions).length === 1,
    "visibleSessions / hiddenSessions split on the hidden flag");
  assert(chatSrc.includes("visibleSessions(sessions)") && chatSrc.includes("hiddenSessions(sessions)")
    && chatSrc.includes('t("chat.restore")'), "ChatList hides hidden chats and offers Restore");
  ok("CCA.11 hidden conversations omitted from normal list; recovery exists");

  // 12 — rename: titleOverride wins; empty falls back; no AI
  const renamed = await ccMock.renameSession(sampleSessions[0].sessionId, "  Мой вечер  ");
  assert(renamed.titleOverride === "Мой вечер", "rename trims + stores an override");
  assert(displaySessionTitle({ ...renamed }) === "Мой вечер", "override wins in the list");
  const cleared = await ccMock.renameSession(sampleSessions[0].sessionId, "   ");
  assert(cleared.titleOverride === null && displaySessionTitle({ ...cleared, title: "", label: "L" }) === "L",
    "empty rename falls back to the automatic label");
  assert(chatSrc.includes('t("chat.rename")') && !/rewriteDraft|assistant/.test(chatSrc), "rename UI has no AI");
  ok("CCA.12 rename persists; empty falls back; no AI");

  // 13 — hide is presentation privacy, not erasure (honest wording)
  for (const loc of [ru, en, es, zhCN, pt]) {
    const L = loc as Record<string, string>;
    for (const k of ["message.hide", "chat.hide", "chat.restore", "message.showHidden"]) {
      assert(typeof L[k] === "string" && L[k].length > 0, `${k} localized`);
    }
    assert(!/Безвозвратно|securely delet|permanently eras/i.test(L["chat.hide"] + L["message.hide"]),
      "hide labels never promise secure erasure");
  }
  ok("CCA.13 hide wording is presentation-privacy, not deletion");

  // 14 — client surface + no unsafe file input introduced
  const cc: CompanionClient = ccMock;
  assert(typeof cc.rewriteDraft === "function" && typeof cc.renameSession === "function"
    && typeof cc.setSessionHidden === "function" && typeof cc.setMessageHidden === "function", "client surface extended");
  for (const rel of ["features/Composer.tsx", "features/MessageActions.tsx", "features/ChatList.tsx", "App.tsx"]) {
    assert(!/type=["']file["']/.test(read(rel)), `${rel} introduces no file input`);
  }
  ok("CCA.14 client surface extended; no unsafe file input");

  // 15 — Focus V2 + custom scrolling preserved
  assert(focusSrc.includes("focus-canvas") && focusSrc.includes("recomputeNearBottom") && css.includes("::-webkit-scrollbar"),
    "Focus Mode V2 canvas + polished scrolling still present");
  ok("CCA.15 Focus V2 and custom scrolling preserved");

  console.log(`\n${passed} passed, 0 failed`);
}

main().catch((err) => {
  console.error("\nFAILED:", err instanceof Error ? err.message : err);
  process.exit(1);
});
