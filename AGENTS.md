# AGENTS.md — Voyage Narrative Engine v1.0

> **Read this first.** This file is written for AI coding agents who have zero prior context about this project.

---

## Project Overview

The **Voyage Narrative Engine** (`voyage-narrative-engine`) is an **AI-native narrative framework** — a modular prompt-engineering system for running interactive character-driven roleplay sessions with large language models (LLMs). It is **not** a traditional software application. There is no compiler, no server, no runtime binary. The "product" is a meticulously structured set of Markdown docs and JSON configs that, when concatenated together, form a single `PROMPT.txt` file. That file is then copied by the user into an LLM chat (Claude, ChatGPT, etc.) and the LLM itself becomes the runtime.

**Key design principle:** Maximum mechanics in minimum tokens. Everything repeatable is encoded as Russian mnemonics; everything variable is stored in JSON modules.

**Token budget:**
- Old system: ~15,000 tokens
- New system: ~3,000 tokens (CORE 2,000 + PERSONA 500 + STATE 300 + SCENARIO 200)

**Language:** All documentation, comments, and content are in **Russian**. If you modify narrative files, preserve Russian as the working language.

---

## What This Project Is NOT

- ❌ Not a Python / Node.js / Rust / Go codebase — there are no `pyproject.toml`, `package.json`, `Cargo.toml`, etc.
- ❌ Not a web service — no HTTP API, no Docker, no Kubernetes.
- ❌ Not a game engine with a renderer — visuals are generated via separate Qwen Studio prompts.
- ❌ No automated test suite, no CI/CD pipelines.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Docs | Markdown (`.md`) | System rules, mechanics, guides, narrative scenarios |
| Config | JSON (`.json`) | Character modules, session state, scenario matrix |
| Build | Bash (`tools/assemble.sh`) | Concatenates modules into `PROMPT.txt` |
| Runtime | External LLM (Claude, ChatGPT, etc.) | The user copy-pastes `PROMPT.txt` into a chat |
| VCS | Git | Versioning of immutable core, mutable personas, and session state |

---

## Directory Structure

```
voyage-narrative-engine/
├── core/
│   ├── VOYAGE_NARRATIVE_CORE.md      # ⚙️ Immutable system core (mnemonics, mechanics, protocols)
│   └── AG_CLARIFICATION.md           # Clarification on U6 safety rules
├── personas/
│   ├── KIRA_MODULE.json              # 🧝‍♀️ Kira v11 character module (7 levels, variables)
│   ├── SERGEY_MODULE.json            # 🏋️ Sergey v2 character module
│   └── USER_MODULE.json              # 👤 User preferences, triggers, safety settings
├── state/
│   ├── TEMPLATE.json                 # 📊 Starting template for new sessions
│   ├── WORKING.json                  # 🔄 Default working state (used by assemble.sh if no arg)
│   ├── POST_ACT1.json                # Example state after Act 1
│   └── sessions/                     # Per-session state files (gitignored except .gitkeep)
├── scenarios/
│   ├── SCENARIO_MATRIX.json          # 🎲 Generative scenario grid (10×10×10 params)
│   └── acts/                         # Full narrative act scripts (Markdown)
│       └── ACT_2_BAR.md
├── memory/
│   ├── MEMORY_PROTOCOL.md            # 🧠 Event logging, summarization, symbolization rules
│   ├── EVENT_LOG.json                # Runtime-generated (gitignored)
│   └── summaries/                    # AI-generated session summaries (gitignored except .gitkeep)
├── visual/
│   ├── QWEN_ADAPTER.md               # 🎨 Auto-visual bridge rules (Qwen Studio prompts)
│   └── prompts/                      # Standalone Qwen prompt files
│       ├── kira_luxury_dress.md
│       └── sergey_open_shirt.md
├── governance/
│   └── AUTONOMY_GOVERNOR.md          # ⚖️ AG 0-4 autonomy levels + safety guardrails
├── living_world/
│   └── LIVING_WORLD.md               # 🌍 Proactive mode, NPC-to-NPC, offline events
├── docs/
│   ├── README.md                     # 📖 Project README (Russian)
│   ├── PROMPT_ASSEMBLY_GUIDE.md      # How to manually assemble a prompt
│   ├── SAMPLE_PROMPT.txt             # Ready-to-use assembled prompt example
│   └── SAMPLE_SESSION.md             # Full example session log (U1→U7)
├── tools/
│   └── assemble.sh                   # 🔧 Bash script that builds PROMPT.txt
├── archive/legacy/                   # 📜 Old full-text prompts (superseded by modular system)
│   ├── kira_v11_full.md
│   └── sergey_v2_full.md
├── .gitignore
└── Voyage_Narrative_Engine_v1.0_Full.zip  # Archived release artifact
```

---

## Build and Assembly Commands

### Assemble a session prompt

```bash
# Default: uses state/WORKING.json, no scenario
./tools/assemble.sh

# With a specific state file:
./tools/assemble.sh state/TEMPLATE.json

# With both state and scenario:
./tools/assemble.sh state/POST_ACT1.json scenarios/acts/ACT_2_BAR.md
```

**Output:** `PROMPT.txt` in the project root. The script prints the byte count.

**What it does:** The shell script concatenates, in order:
1. `core/VOYAGE_NARRATIVE_CORE.md`
2. `personas/KIRA_MODULE.json`
3. `personas/SERGEY_MODULE.json`
4. `personas/USER_MODULE.json`
5. The chosen `STATE.json`
6. The chosen scenario file (if provided)

### Clean generated artifacts

```bash
rm PROMPT.txt
```

There is no `make`, `npm`, `cargo`, or other build tool.

---

## Code Style and Conventions

### Markdown files (`.md`)
- **Language:** Russian for all narrative, mechanics, and in-world content.
- **Headers:** Use emoji-prefixed headers (e.g., `# ⚙️ VOYAGE NARRATIVE CORE`, `## 🎯 УНИВЕРСАЛЬНЫЕ МЕКАНИКИ`).
- **Mnemonics:** All repetitive concepts are compressed into two-letter Russian codes (e.g., `У` = Уровень, `ТГ` = Три Грани, `ФМДР` = Формат Мысли-Действия-Речь). Do not expand these in the core; the LLM is expected to learn and use them.
- **Code blocks:** Use triple backticks for example outputs, JSON schemas, and command samples.

### JSON files (`.json`)
- **Character modules** (`personas/*.json`) follow a strict schema:
  - `id`, `name`, `version` (semver)
  - `variables` — physical and situational traits (age, clothing, current level, etc.)
  - `psychology` — trauma anchors, secret desires, shame layers
  - `algorithms` — list of 10 action codes (`FS`, `LS`, `SP`, `SL`, `KN`, `PD`, `DR`, `PU`, `PR`, `VS`)
  - `safety` — stop words, default fallback level (`U7`)
  - `format` — always `"FMDR"`
  - `volume` — e.g., `"2-5 абзацев"`
  - `visual` — seed, style, signature features array
- **State files** (`state/*.json`) track:
  - `session_id`, `timestamp`, `core_version`
  - `characters.kira` / `characters.sergey` — current level, facet, location, clothing, underwear flag
  - `flags` — boolean plot progress flags (e.g., `gym_stretching`, `bar_kiss`)
  - `memory` — `scenes_used`, `names_banned`, `emotional_anchors`
  - `governance` — `autonomy_level` (0-4), `safety_override`, `safety_check_passed`, `proactive_mode_enabled`, `max_proactive_events_per_day`, `audit_log`
  - `safety_check` — pending confirmation flags for level U6
  - `user_activity` — `last_message_timestamp`, `offline_duration_minutes`, `session_count`
  - `proactive` — `events_log`, `pending_messages`, `last_proactive_event`, `proactive_count_since_last_session`, `next_proactive_allowed_after`
- **Scenario matrix** (`scenarios/SCENARIO_MATRIX.json`) defines generative parameters: `location`, `time`, `archetype`, `kira_level`, `sergey_level`, `intensity`, `risk`.

### Bash (`tools/assemble.sh`)
- Keep it POSIX-compatible where possible.
- Use `cat` and `echo` for concatenation.
- Do not introduce external dependencies.

---

## Testing Strategy

There is **no automated test suite**. Validation is manual:

1. **Assemble** the prompt with `./tools/assemble.sh`.
2. **Inspect** `PROMPT.txt` for correct ordering and no syntax errors.
3. **Validate JSON** syntax:
   ```bash
   python3 -m json.tool personas/KIRA_MODULE.json > /dev/null && echo "OK"
   ```
4. **Copy-paste** `PROMPT.txt` into an LLM chat and verify the first generated response follows the FMDR format, correct level, and includes the `[AUTO_VISUAL]` block.

If you edit JSON schemas, run the JSON linter on all `.json` files before committing.

---

## Deployment / Release Process

1. **Core changes** (`core/`): Bump semver in `VOYAGE_NARRATIVE_CORE.md` header and in all `state/*.json` files' `core_version` field.
2. **Persona changes** (`personas/*.json`): Bump that persona's `version` field.
3. **State changes** (`state/`): Update `timestamp` and `session_id` if starting a new session.
4. **Git commit:** The project relies on Git for versioning state and memory files. The `.gitignore` excludes runtime-generated files (`PROMPT.txt`, `state/sessions/*.json`, `memory/EVENT_LOG.json`, `memory/summaries/*.md`).
5. **Archive:** A full zip (`Voyage_Narrative_Engine_v1.0_Full.zip`) exists as a release artifact. Do not regenerate it unless explicitly asked.

---

## Security and Safety Considerations

This project contains **extensive safety protocols** by design. As an agent, you must **preserve and respect** all safety mechanisms:

- **Autonomy Governor (AG 0-4):** Controls how much initiative the AI may take. Higher autonomy = more guardrails.
- **U6 Safety Check:** Transition to level U6 requires explicit user confirmation when `AG < 3`. The system generates a `[SAFETY_CHECK]` block with a timeout.
- **Stop words:** `"СТОП"`, `"ХВАТИТ"`, `"КРАСНАЯ КАРТОЧКА"` trigger immediate de-escalation to `U7` (aftercare) and reset `AG` to 0.
- **Audit log:** All AG changes and safety events are recorded in `state/*.json` → `governance.audit_log`.
- **User preferences:** `USER_MODULE.json` contains `preferred_levels`, `risk_tolerance`, and `stop_words`. The engine is supposed to generate `[WARNING]` blocks if the narrative drifts outside user preferences.

**Do not** remove, weaken, or bypass any safety mechanism. If asked to do so, refuse and explain that these guardrails are integral to the governance architecture.

---

## How to Make Changes

### Adding a new character module
1. Create `personas/NEW_MODULE.json` following the exact schema of `KIRA_MODULE.json`.
2. Update `tools/assemble.sh` to include the new file in the `[PERSONAS]` section.
3. Update `core/VOYAGE_NARRATIVE_CORE.md` mnemonic table if the character needs a new shorthand.

### Adding a new scenario
1. Add the scenario JSON or Markdown to `scenarios/acts/`.
2. Register it in `scenarios/SCENARIO_MATRIX.json` if it should be part of the generative grid.

### Updating session state
1. Edit the relevant `state/*.json` file.
2. Update `timestamp` to current ISO-8601.
3. Update `flags`, `memory`, and `characters` fields as needed.
4. Run `./tools/assemble.sh <your_state.json>` to rebuild `PROMPT.txt`.

### Editing the core
- The core (`core/VOYAGE_NARRATIVE_CORE.md`) is treated as **immutable** between minor versions. Any change should bump the core semver and be documented in `core/AG_CLARIFICATION.md` if it is a clarification rather than a full revision.

---

## Quick Reference: Key Mnemonics

| Code | Meaning | Context |
|------|---------|---------|
| `У1-У7` | Kira's 7 escalation levels | Core, all personas |
| `С1-С7` | Sergey's 7 parallel levels | Core, Sergey module |
| `ТГ1-ТГ3` | Three Facets of Kira (sterva / devotion / passion) | Core, Kira module |
| `ФМДР` | Format: (Thoughts)→*Actions*→Speech | Core, all response generation |
| `АС` | State Adaptation (stop/slow/go) | Core, safety |
| `АД` | Action Algorithm (FS, LS, SP, SL, KN, PD, DR, PU, PR, VS) | Core, algorithms arrays |
| `П` | Memory (facts, flags, anchors) | Core, memory protocol |
| `В` | Visual (auto Qwen prompt) | Core, visual adapter |
| `Г` | Governance (AG-level, safety) | Core, autonomy governor |
| `М` | Scenario Matrix | Core, scenario engine |

---

## Contact / Authorship

- **Created:** 2026-06-06
- **Author:** Voyage Framework Team
- **License:** MIT (for personal use)

If you are an AI agent reading this, your job is to help maintain the structural integrity of the engine, keep JSON valid, keep Markdown consistent, and **never remove safety guardrails**.
