# SYSTEM.md
# Voyage Narrative Engine — System Architecture & Cold Start Guide
# Version: 3.0.0 | Last updated: 2025-01-20
# Purpose: Single source of truth for AI agents and developers

---

---

## 1. WHAT IS THIS REPOSITORY?

**Voyage Narrative Engine (VNE)** is a specification-driven framework for creating **interactive AI characters** and **branching narrative scenarios**.

- **Not a game engine** — no graphics, no runtime binary.
- **Not a chatbot** — characters have deep psychology, trauma, sexuality, and visual identity.
- **Specification-driven** — everything is defined in JSON/Markdown files, not code.
- **Modular** — characters and scenarios are built from reusable modules.
- **AI-native** — designed for LLM context windows (200K tokens).

**Core philosophy:** Every role (R1–R8 for personas, S1–S8 for scenarios) has a **Knowledge Base (KB)** — source of truth. KB → Generation → Audit → Compression → Next role.

---

## 2. REPOSITORY STRUCTURE

```
voyage-narrative-engine/
│
├── SYSTEM.md                    ← YOU ARE HERE (cold start guide)
├── README.md                    ← Human-readable overview
├── PRELOAD_PERSONAS_v2.2.md     ← Runtime context (3 layers)
│
├── personas/                    ← CHARACTER MODULES (10 personas)
│   ├── [id]/                    ← Modular structure (12 subfolders)
│   │   ├── INDEX.json           ← Manifest: modules, versions, dependencies
│   │   ├── ASSEMBLY.md          ← How to assemble this persona for runtime
│   │   ├── HANDOFF_R7.md        ← Migration notes (R7 → R8)
│   │   ├── AUDIT_REPORT_[id].md ← R8 validation report
│   │   ├── core/
│   │   │   └── IDENTITY.json    ← Name, age, archetype, anatomic_anchor
│   │   ├── levels/
│   │   │   └── U1-A.json … U7-B.json  ← 14 sublevels (speech, visuals, vscno, internal_state, ad)
│   │   ├── psychology/
│   │   │   ├── BASE.json        ← Core_conflict, trauma, secret_desire
│   │   │   ├── ATTACHMENT.json  ← Attachment style
│   │   │   ├── AROUSAL.json     ← Responsive desire, arousal specificity
│   │   │   ├── PLASTICITY.json  ← Erotic plasticity
│   │   │   └── TEC.json         ← TEC mechanics (8 types)
│   │   ├── sexology/
│   │   │   ├── RESPONSE_CYCLE.json
│   │   │   ├── EROTIC_SCRIPTS.json
│   │   │   ├── DYSPHORIA_AND_SHAME.json
│   │   │   └── FANTASY_VS_REALITY.json
│   │   ├── visual/
│   │   │   ├── PROMPT_BASE.json ← Visual prompt for AI image generation
│   │   │   ├── DYNAMIC_VISUALS.json ← Visuals by sublevel
│   │   │   └── GENERATION_HISTORY.json
│   │   ├── dynamics/
│   │   │   ├── REACTION_PATTERNS.json
│   │   │   ├── LEVEL_LOCK_MATRIX.json
│   │   │   ├── EMOTIONAL_INFLUENCE_MATRIX.json
│   │   │   ├── CONFLICT_RESOLUTION_MATRIX.json
│   │   │   └── CROSS_PERSONA_SYNC.json
│   │   ├── memory/
│   │   │   ├── TRUST.json
│   │   │   ├── ATTRACTION.json
│   │   │   ├── FLAGS.json
│   │   │   ├── HISTORY.json
│   │   │   └── EMOTIONAL_ANCHORS.json
│   │   ├── relationships/
│   │   │   └── MATRIX.json      ← Relations with other personas
│   │   ├── environment/
│   │   │   ├── STATE_TRIGGERS.json
│   │   │   └── SPATIAL_BEHAVIOR.json
│   │   ├── safety/
│   │   │   └── PROTOCOL.json    ← Stop words, hard limits, emergency
│   │   ├── autonomous/
│   │   │   ├── ACTIVITIES.json
│   │   │   └── TEMPLATES.json
│   │   └── meta/
│   │       └── META.json        ← Metadata, versions, changelog
│   │
│   └── [id]_MODULE_vN.json      ← LEGACY monoliths (kept for reference)
│
├── scenarios/                   ← SCENARIO MODULES (first modular: sauna_extended)
│   ├── sauna_extended/            ← 🆕 MODULAR SCENARIO v3.0.0
│   │   ├── core/
│   │   │   └── INDEX.json         ← Manifest: 6 participants, v3.0.0
│   │   ├── structure/
│   │   │   ├── phases.json        ← 8 phases (P1-P5 + P1b,P2b,P3b)
│   │   │   ├── timeline.json      ← Narrative timeline
│   │   │   └── locations.json     ← 2 floors, 8 rooms
│   │   ├── scenes/
│   │   │   ├── P1_entrance.json   ← Modular scene files (JSON + MD)
│   │   │   ├── P1b_andrey_plays.md
│   │   │   ├── P2_steam.json
│   │   │   ├── P2b_andrey_kira_duel.md
│   │   │   ├── P3_pool.json
│   │   │   ├── P3b_andrey_kira_pool.md
│   │   │   ├── P4_rest.json
│   │   │   └── P5_climax.json
│   │   ├── branches/
│   │   │   └── BRANCHES.json      ← 4 branching paths (B1-B4)
│   │   ├── characters/
│   │   │   └── ROLES.json         ← Roles, VSCNO targets, level locks
│   │   ├── dynamics/
│   │   │   └── CROSS_CHARACTER.json ← Cross-character interactions
│   │   ├── environment/
│   │   │   └── ATMOSPHERE.json    ← Visual prompts, sensory anchors
│   │   ├── safety/
│   │   │   └── SAFETY.json        ← Hard limits, safety checks, aftercare
│   │   ├── meta/
│   │   │   └── META.json          ← Version, changelog, author notes
│   │   └── scenario_validator.py  ← Scenario validation script
│   │
│   └── (legacy scenarios: SCENARIO_SAUNA_QUARTET.json, etc.)
│
├── knowledge_base/              ← KNOWLEDGE BASE (source of truth for all roles)
│   ├── R1/                      ← Portrait Writer
│   ├── R2/                      ← Psychologist (VSCNO, AD, audit, compression)
│   ├── R3/                      ← Sexologist (TEC)
│   ├── R4/                      ← Speech Specialist (FMDR)
│   ├── R5/                      ← Physiognomist (Visuals)
│   ├── R6/                      ← Modular Assembly Architect
│   ├── S1/                      ← Scenario Interviewer (3-level interview)
│   ├── S2/                      ← Scenario Analyst (interview analysis)
│   ├── S3/                      ← Scenario Architect (3-act matrix)
│   ├── S4/                      ← Scenario Writer (FMDR scenes)
│   ├── S5/                      ← Scenario Visualizer (shots, lighting)
│   ├── S6/                      ← Scenario Assembly Architect
│   ├── S7/                      ← Scenario Refactor (compression)
│   ├── S8/                      ← Scenario Auditor (validation)
│   └── narrative/               ← FMDR examples, Anchor system, Stop frame
│
├── roles/                       ← LLM PROMPTS (legacy + new)
│   ├── ROLE_1_PORTRAIT_WRITER_v1.0_PROMPT.md
│   ├── ROLE_2_PSYCHOLOGIST_v1.0_PROMPT.md
│   ├── ...
│   └── ROLE_8_AUDITOR_v1.0_PROMPT.md
│
├── scripts/python/              ← PYTHON UTILITIES
│   ├── runtime_loader.py        ← Load modular persona into runtime dict
│   ├── refactor_universal.py    ← R7: JSON → modular structure
│   ├── generate_vscno.py        ← R2: Generate VSCNO for all personas
│   ├── fix_missing_data.py      ← Fix data lost during migration
│   └── test_runtime_all.py      ← Test all personas
│
├── schemas/
│   └── persona_schema_v3_2_VOYAGE.json  ← JSON Schema for validation
│
├── state/                       ← RUNTIME STATE (session data)
│   ├── STATE_TEMPLATE_v2.json
│   └── STATE_ACTIVE.json
│
└── sessions/                    ← SESSION ARTIFACTS (auto-generated)
    ├── raw/                     ← Raw logs
    ├── state/                   ← State updates
    ├── memory/                  ← Memory updates
    ├── stories/                 ← Literary stories
    └── visuals/                 ← Image prompts
```

---

## 3. HOW TO BUILD A PERSONA (from modules)

### 3.1 Discovery
```python
from scripts.python.runtime_loader import load_modular_persona

persona = load_modular_persona("andrey_senior")
# Returns: dict with all fields (like old monolith)
```

### 3.2 Manual Assembly (understanding the structure)
1. Read `personas/[id]/INDEX.json` → get module list
2. Read `personas/[id]/ASSEMBLY.md` → understand loading order
3. Load required modules:
   - `core/IDENTITY.json` (always)
   - `psychology/BASE.json` (always)
   - `safety/PROTOCOL.json` (always)
   - `levels/{current_level}.json` (by current level)
   - `visual/PROMPT_BASE.json` (for image generation)
   - `memory/TRUST.json`, `memory/FLAGS.json` (runtime state)

### 3.3 Validation
```python
from scripts.python.runtime_loader import validate_modular_persona

results = validate_modular_persona(persona)
# Returns: {check: (PASS/FAIL/WARNING, comment)}
```

---

## 4. RUNTIME CONTEXT (3 Layers)

When running a session, the AI receives **3 layers** of context:

### Layer 1: BASE (System)
- VSCNO rules (4 axes, sum=10, [0,4])
- AD codes (10 codes: ФС, ЛС, СП, СЛ, КН, ПД, ДР, ПУ, ПР, ВС)
- FMDR format (Thought / Action / Speech)
- Safety protocols (stop words, emergency phrases)
- ~20 KB, always in context

### Layer 2: STATE (Current)
- Active personas and their current levels
- Active scenario and current act
- Session history (last 10 turns)
- Memory updates (trust, flags, emotional anchors)
- ~5 KB, updated each turn

### Layer 3: LIVE (Active Personas)
- For each active persona: core + current level + memory
- Usually 2–3 personas per session
- ~50 KB for 3 personas (fits in 200K limit)

**Total context:** ~75 KB for typical session (well within 200K limit).

**Full modular structure:** ~409 KB (10 personas) — only used for development, not runtime.

---

## 5. HOW TO BUILD A SCENARIO (modular structure — implemented)

```
scenarios/
└── [scenario_id]/
    ├── core/
    │   └── INDEX.json               ← Manifest: id, name, version, participants, synopsis
    ├── structure/
    │   ├── phases.json              ← Phase definitions with character states, triggers, flags
    │   ├── timeline.json            ← Narrative timeline (ordered phases)
    │   └── locations.json           ← Setting descriptions, atmosphere, sensory anchors
    ├── scenes/
    │   ├── P1_*.json / P1_*.md      ← Modular scene files (one per phase)
    │   ├── P2_*.json / P2_*.md
    │   └── ...
    ├── branches/
    │   └── BRANCHES.json            ← Branching logic: conditions, results, FMDR
    ├── characters/
    │   └── ROLES.json               ← Which personas participate + their roles
    ├── dynamics/
    │   └── CROSS_CHARACTER.json     ← Cross-character interactions, psychology
    ├── environment/
    │   └── ATMOSPHERE.json          ← Visual prompts, sensory details
    ├── safety/
    │   └── SAFETY.json              ← Hard limits, safety checks, emergency protocols
    ├── meta/
    │   └── META.json                ← Changelog, author notes
    └── scenario_validator.py        ← Validation script (checks all files, phases, sync)
```

### Scenario Assembly (for runtime)
1. Read `scenarios/[id]/core/INDEX.json`
2. Load `structure/phases.json` + `structure/timeline.json` + `structure/locations.json`
3. Load `characters/ROLES.json` → discover which personas needed
4. Load each persona's modules (via runtime_loader)
5. Assemble scenes in order: `scenes/P1_*.json` → `scenes/P2_*.md` → ...
6. Apply branches based on user choices: `branches/BRANCHES.json`
7. Output: `SCENARIO_[id]_RUNTIME.md` (single file for LLM)

### Validation
```bash
python scenarios/[id]/scenario_validator.py [id]
# Checks: directory structure, required files, JSON validity,
#          phases/timeline sync, characters/roles sync,
#          safety checks, scene coverage, branch definitions
```

### First Modular Scenario: `sauna_extended` (v3.0.0)
- 8 phases (P1–P5 + P1b, P2b, P3b with Andrey Senior)
- 4 branches (B1–B4): user_kira, user_andrey_kira, user_marina, group
- 6 characters: user, kira, marina, sergey, maksim, andrey_senior
- Andrey Senior stays through P1–P3, interacts with Kira, creates tension triangle
- ~120 minutes narrative time, AG1–AG4

---

## 6. ROLE PIPELINES (KB → Generation → Audit → Compression)

### Persona Pipeline (R1–R8)
```
R1 Portrait Writer    → PORTRAIT (identity, soft skills, narrative techniques)
R2 Psychologist      → PSYCHOLOGY (VSCNO, AD, trauma, defenses)
R3 Sexologist        → SEXOLOGY (TEC, sexual scenarios)
R4 Speech Specialist → SPEECH (FMDR, speech patterns, slang)
R5 Physiognomist     → VISUAL (anatomic anchor, dynamic visuals, lighting)
R6 Assembly Architect → PERSONA MODULE (aggregation into 12 folders)
R7 Refactor          → COMPACT (compression for runtime)
R8 Auditor           → AUDIT REPORT (validation against KB + schema)
```

### Scenario Pipeline (S1–S8)
```
S1 Scenario Interviewer → INTERVIEW (3-level user immersion)
S2 Scenario Analyst     → ANALYSIS (extract structure from interview)
S3 Scenario Architect   → SCENARIO MATRIX (3 acts, branches, arcs)
S4 Scenario Writer      → SCENES (FMDR, dialogue, action)
S5 Scenario Visualizer  → VISUALIZATION (shots, lighting, mise-en-scène)
S6 Assembly Architect   → SCENARIO MODULE (aggregation)
S7 Refactor            → COMPACT (compression)
S8 Auditor             → AUDIT REPORT (validation)
```

---

## 7. QUICK START FOR AI AGENTS

### If you are a new AI agent reading this:

**Step 1:** Read `SYSTEM.md` (this file) — understand the architecture.

**Step 2:** Check `README.md` for human-readable overview.

**Step 3:** To work with a persona:
```bash
# Load persona into Python dict
python scripts/python/runtime_loader.py andrey_senior

# Test all personas
python scripts/python/test_runtime_all.py
```

**Step 4:** To understand a specific role, read its KB:
```
knowledge_base/R2/KB_R2_VSCNO_RULES.md     ← VSCNO canonical rules
knowledge_base/R4/KB_R4_SPEECH_MATRIX.md   ← Speech patterns
knowledge_base/R5/KB_R5_DYNAMIC_VISUALS.md ← Dynamic visual parameters
```

**Step 5:** To create a new persona, follow the pipeline:
1. Read `knowledge_base/R1/` → create portrait
2. Read `knowledge_base/R2/` → create psychology
3. ... (continue through R8)

**Step 6:** To create a new scenario, follow the S-pipeline:
1. Read `knowledge_base/S1/` (TODO) → interview user
2. Read `knowledge_base/S2/` (TODO) → analyze
3. ... (continue through S8)

---

## 8. KNOWN ISSUES & CONSTRAINTS

| Issue | Description | Workaround |
|-------|-------------|------------|
| **Context limit** | 200K tokens per session | Use 3-layer runtime (BASE+STATE+LIVE) |
| **Folder names** | Some have `_module_vN` suffix | Use `runtime_loader.py` — it handles discovery |
| **Empty modules** | Some personas have empty psychology/sexology | They are user proxies (intentional) |
| **VSCNO missing** | Some monoliths had no VSCNO data | Generated by `generate_vscno.py` using R2 rules |
| **No Python** | Python may not be in PATH | Use full path: `C:/Users/.../cpython-3.12/python.exe` |

---

## 9. COMMANDS CHEATSHEET

```bash
# Load persona
python scripts/python/runtime_loader.py [id]

# Test all personas
python scripts/python/test_runtime_all.py

# Generate VSCNO for all
python scripts/python/generate_vscno.py

# Fix missing data
python scripts/python/fix_missing_data.py

# Validate scenario
python scenarios/[id]/scenario_validator.py [id]

# Check sizes
python scripts/python/analyze_sizes.py

# Git operations
git add personas/[id]/
git commit -m "persona: update [id]"
git push origin main
```

---

## 10. CONTACT & VERSIONING

- **Repository:** https://github.com/AndreyVoyage/voyage-narrative-engine
- **Version:** 3.0.0 (semantic: MAJOR.MINOR.PATCH)
- **Schema version:** 1.0.0
- **Last major update:** 2025-01-20 (First modular scenario: sauna_extended with Andrey Senior)

---

*SYSTEM.md | Voyage Narrative Engine | 2025-01-20*
