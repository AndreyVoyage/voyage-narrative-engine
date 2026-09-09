# KIRA Companion — MVP Release Candidate 1

Release identifier: **KIRA Companion MVP RC1** (`0.1.0-rc1`, channel `release-candidate`).

This is the bounded first-Windows release assembly of the Companion app. It is
**not** `1.0`, not a general-purpose character platform, not multi-character, not
mobile. It assembles what already exists (Character Core / Runtime, the accepted
KIRA package, the Companion service, Cinematic UX, multi-chat, Scene, Focus Mode,
the image-job boundary, the secure credential vault, the provider registry and
role settings, the Local Ollama provider, and the Attachment Security Gateway
foundation) into a runnable, distributable Windows form.

---

## What ships

| Area | State |
|---|---|
| Accepted KIRA identity | `kira-r4-canonical-run-1-package` v0, hash `e26f83da…3eebd` (unchanged; no CRP reconstruction) |
| Cinematic UX | multi-chat, Scene new-dialog, RightWing, Focus Mode, composer, image-job strip — unchanged |
| Provider selection | Settings → DIALOGUE role → provider registry → OS credential vault (cloud) → exactly one provider → `RuntimeService.turn`. No hidden fallback. |
| Local model | `num_ctx` field, validated, `[512, 131072]`; "context too small" warning below 16384 |
| Secure credentials | Windows DPAPI vault; key never in settings JSON / bundle / manifest / logs / UI |
| Release mode | `--mode release` — a real DIALOGUE provider must be configured; the app never answers as **FakeKIRA** |
| Windows launch | `tools/start_character_companion.ps1` (script-dir anchored, one process, serves built SPA + `/api`) |
| Release build | `tools/build_character_companion_release.ps1` → `dist/character-companion/` (`web/`, `backend/`, `RELEASE_MANIFEST.json`, `START.ps1`) |

## What does NOT ship in RC1 (owner-gated / deferred)

- **KIRA release portrait** — not bound. The canon repo has approved KIRA visual
  assets, but no single clean identity portrait suitable for the RightWing slot
  (the designated `primary_face_reference` is a multi-panel *contact sheet*; the
  one `_APPROVED`-suffixed single image is scene-flavoured "bar_romance").
  Selecting one is an owner asset decision — see `OWNER_ASSET_DECISION_REQUIRED`
  in the assembly report. Placeholder portrait remains.
- **Real image generation** — the only existing callable image pipeline
  (`vne-image-provider-boundary-v0` `generate_image`) is a paid OpenAI Images
  HTTPS call requiring `OPENAI_API_KEY`, in a sibling repo. Binding it needs a
  live cloud call + credential, both outside this slice's authorization. The
  `FakeImageGenerator` / `UnavailableImageGenerator` behaviour is unchanged.
- **Live provider acceptance** — no DeepSeek / OpenAI / Qwen call and no real
  local Ollama generation was run. Those are the explicit live-acceptance gates.
- Literary UI, third theme, phone/TTS/STT/voice/video, mobile, cloud sync,
  scheduler, autonomous initiative, book library, arbitrary attachment ingestion,
  non-Windows vaults — all remain out of scope.

---

## Prerequisites

- Windows 10/11 x64
- Python 3.11+ on PATH (`py`)
- A built frontend: run `tools/build_character_companion_release.ps1` once
  (uses the already-installed Vite toolchain; **no `npm install`** by this repo,
  no packaging framework, no downloads)
- For a real reply: either a local Ollama server on `127.0.0.1:11434` with a
  model that has a ≥ 16384 context window, **or** a cloud provider key entered
  once in Settings (stored only in the Windows credential vault)

## Run

```powershell
# one-time
powershell -ExecutionPolicy Bypass -File tools\build_character_companion_release.ps1
# every time
powershell -ExecutionPolicy Bypass -File tools\start_character_companion.ps1
```

The launcher starts a single loopback process that serves both the SPA and the
`/api/companion/*` endpoints, opens a browser, and stops on Ctrl+C.

## User data location

All durable user data lives under **`%LOCALAPPDATA%\KiraCompanion\data`** —
outside the disposable build output. Rebuilding or replacing the frontend does
not touch it:

- `companion_sessions.json` — session registry (titles, scene, cover ref)
- `characters/kira/memory/…` — Runtime Memory event log (conversation history)
- `characters/kira/state/…` — Runtime State
- `companion_image_jobs.json` + `images/` — image-job metadata & placeholder outputs
- `companion_settings.json` — provider/role/num_ctx settings (**no secrets**)
- `companion_credentials.dpapi.json` — DPAPI-encrypted key blob (opaque ciphertext only)

## Local context (`num_ctx`)

Real evidence from `LOCAL_LLM_PROVIDER_V1`: a full KIRA Grounded request was
~**10 014** prompt tokens and was rejected by a model running a 4096-token
window. RC1 therefore recommends a local model configured with
**`num_ctx` ≥ 16384** and surfaces a warning below that. This is a conservative
hint from one measured observation, not a precise per-turn token guarantee.

## Not a single EXE

RC1 is honestly: Python backend + browser-served React build, driven by a
PowerShell launcher. A true self-contained `.exe` would require a packaging
framework (PyInstaller / Electron / Tauri / NSIS) that is not installed —
`SELF_CONTAINED_EXE_DEFERRED`. This is not a release blocker for the bounded
launcher + folder distribution.
