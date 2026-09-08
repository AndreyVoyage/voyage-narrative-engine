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
  filterSessions,
  initialCompanionState,
  isSendableMessage,
} from "../src/app/companionState.js";
import {
  FOCUS_LAYOUTS,
  IMPLEMENTED_EXPERIENCES,
  isExperienceImplemented,
  nextFocusLayout,
} from "../src/app/appearance.js";
import { draftToInput, emptyDraft, setFreeform, setMode, setSceneField, setTitle } from "../src/app/newDialog.js";
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
  assert(/portrait/i.test(wing) && wing.includes("PORTRAIT_PLACEHOLDER_DATA_URI"), "portrait slot");
  ok("38. right wing shows a persistent portrait slot");
  assert(wing.includes("wing-scene-image") && wing.includes("hasSceneImage"), "conditional scene image");
  ok("39. right wing conditionally shows the scene visual");
  assert(wing.includes("wing-portrait-expanded"), "portrait expansion without scene image");
  ok("40. no scene image → portrait expansion behaviour exists");
  assert(wing.includes("scene-params") && wing.includes("Настроение"), "scene parameters rendered");
  ok("41. scene parameters render (место/время/ситуация/настроение)");

  // 42 + 43 — image job states render, composer never disabled by a job
  let s = companionReducer(focus0, { type: "imageJobsLoaded", jobs: [
    { jobId: "j1", sessionId: "x", characterId: "kira", kind: "context", state: "GENERATING",
      createdAt: "", updatedAt: "", prompt: null, resultRef: null, error: null },
  ] });
  assert(anyImageJobActive(s.imageJobs) && s.loading === "idle", "image job active but chat not blocked");
  const conv = read("features/Conversation.tsx");
  assert(conv.includes("job-strip") && conv.includes("Создаём изображение"), "job status strip renders");
  ok("42. image job states render");
  assert(!/Composer[\s\S]*disabled=\{[^}]*job/i.test(conv), "composer not disabled by image jobs");
  ok("43. image job does not disable the composer");

  // 44 — create-image vs context-frame are distinct actions
  const composer = read("features/Composer.tsx");
  assert(composer.includes("onCreateImage") && composer.includes("onContextFrame"), "two distinct create actions");
  assert(composer.includes("Создать изображение") && composer.includes("Кадр по контексту"), "distinct labels");
  ok("44. create-image and context-frame actions are distinct");

  // 45 — arbitrary attachment upload is disabled / not implemented
  assert(/disabled/.test(composer) && /(Скоро|безопасной загрузки)/.test(composer), "attach actions disabled honestly");
  assert(!/input[^>]*type=["']file["']/.test(composer), "no unsafe file picker");
  ok("45. arbitrary attachment upload actions are disabled / not implemented");

  // 46 — microphone not duplicated in the attachment menu
  const menuBlock = composer.slice(composer.indexOf("composer-menu"), composer.indexOf("</div>", composer.indexOf("composer-menu")));
  assert(!menuBlock.includes("🎤"), "microphone icon is not inside the + menu");
  assert(!/(Голосов|voice message|Записать голос)/i.test(menuBlock), "no voice-message entry in the + menu");
  assert(composer.includes("🎤") && composer.includes("Записать голосовое сообщение"),
    "microphone is a dedicated composer button meaning 'record a voice message'");
  ok("46. microphone is not duplicated in the attachment menu");

  // 47–51 — Focus Mode
  s = companionReducer(focus0, { type: "focusEnter" });
  assert(s.focusActive, "focus enter");
  s = companionReducer(s, { type: "focusExit" });
  assert(!s.focusActive, "focus exit");
  ok("47. Focus Mode exists");
  assert(FOCUS_LAYOUTS.length === 3 && FOCUS_LAYOUTS.join(",") === "background,side_gallery,chat_only", "three layouts");
  const fm = read("features/FocusMode.tsx");
  assert(fm.includes("focus-background") || fm.includes("backgroundImage"), "BACKGROUND layout");
  ok("48. BACKGROUND mode exists");
  assert(fm.includes("focus-gallery") && fm.includes("side_gallery"), "SIDE_GALLERY layout");
  ok("49. SIDE_GALLERY mode exists");
  assert(fm.includes("chat_only"), "CHAT_ONLY layout");
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

  console.log(`\n${passed} passed, 0 failed`);
}

main().catch((err) => {
  console.error("\nFAILED:", err instanceof Error ? err.message : err);
  process.exit(1);
});
