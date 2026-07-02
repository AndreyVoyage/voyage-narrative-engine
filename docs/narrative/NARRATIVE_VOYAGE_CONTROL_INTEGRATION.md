# Narrative Voyage Control Integration

## Status

- Track: V0 / Infrastructure
- Type: dev-control only
- Product runtime impact: none
- Current state: planning / conventions
- Activation: not automatic

V0 is a Narrative-side infrastructure track for development control. It is separate from the product roadmap phases N1-N6 and does not change the story runtime, RenPy runtime, scenario schema, scenes, personas, or player experience.

## Purpose

This document defines how Voyage Control should support the Narrative project as development infrastructure.

V0 exists to:

- reduce manual handoff friction between Claude Code and ChatGPT;
- make implementation and audit reports consistent;
- preserve decisions and task boundaries across chats;
- make Claude Code to ChatGPT audit easier;
- prepare for the added coordination complexity of N4-N6;
- keep development control visible without turning it into product runtime.

The goal is not to build infrastructure for its own sake. V0 should stay incremental, explicit, and anti-overengineering.

## Boundary

### Narrative Engine

Narrative Engine is the product/runtime. It owns:

- scenes;
- scenario schema;
- story runtime;
- RenPy preview/export;
- player experience;
- editor and developer inspector features;
- LLM Director later, after product-side contracts are ready.

Narrative source and runtime decisions remain governed by the Narrative docs and product roadmap.

### Voyage Framework

Voyage Framework is development process infrastructure. It owns:

- task control;
- report validation;
- handoff checks;
- audit trail;
- workflow memory;
- development gates.

Voyage may control the development workflow around Narrative, but it must not enter the product runtime path.

## What V0 Is

V0 is a small development-control layer for Narrative conventions.

It may define:

- report and handoff conventions;
- task template conventions;
- project profile intent;
- validation report expectations;
- cross-chat coordination rules.

V0 should help tasks become easier to audit, safer to merge, and less dependent on manual copy/paste.

## What V0 Is Not

V0 is not:

- story runtime;
- RenPy runtime;
- character logic;
- scene execution;
- game save system;
- LLM Director;
- an automatic agent system;
- a reason to modify product files.

Voyage must not become:

- story runtime;
- scene executor;
- character engine;
- RenPy runtime;
- LLM Director runtime;
- gameplay dependency.

## Timing

The main product foundation N0-N3 is complete:

- N0 docs complete;
- N1 schema/validator complete;
- N2 story runtime foundation complete;
- N3 preview/export foundation complete.

V0 is appropriate before N4 planning because N4-N6 will increase coordination pressure. That said, V0 should remain small. N4 must not be blocked by large infrastructure work.

Initial V0 should be docs/conventions first. Future V0 work can add templates or schemas only after the boundary is accepted.

## Cross-chat Boundary

Narrative chat owns:

- Narrative-side conventions;
- Narrative report expectations;
- Narrative task templates;
- Narrative handoff structure;
- product roadmap notes.

Framework chat owns:

- Framework validate-report implementation;
- generic schema engine;
- Framework CLI;
- dashboards;
- Framework CI/pre-commit;
- core Voyage behavior.

No task should edit both repos at once. If a Narrative-side task discovers a required Framework change, it should stop and hand that requirement to a separate Framework task.

## Minimal First Implementation

This document is the first V0 implementation.

Future candidates:

- report schema draft;
- handoff report template;
- task prompt template;
- project profile draft.

Each future candidate must be separate, explicit, and small. A future V0 step may add:

- `report_schemas/`;
- `task_templates/`;
- `handoffs/`;
- `project_profile`;
- validate-report integration.

Future V0 must not activate `.voyage/tasks.db` without explicit approval.

## Guardrails

- Do not modify `.voyage/**` casually.
- Do not create `.voyage/tasks.db` without explicit approval.
- Do not activate the task database without explicit approval.
- Do not touch the Framework repo from Narrative tasks.
- Do not touch runtime, RenPy, scenes, schemas, personas, or exporters as part of V0.
- Do not merge infrastructure and product work in one commit.
- Do not create `SC_028` as part of V0.
- Do not mass migrate scenarios as part of V0.
- Do not turn report validation into story execution.
- Do not make Narrative depend on Framework at gameplay time.

## Current Baseline

Current completed foundation:

- N0 docs complete;
- N1 schema/validator complete;
- N2 story runtime foundation complete;
- N3 preview/export foundation complete.

Current `main` baseline:

```text
67b3a6628bccf02bc9678d92593706b8a9bc7ee6
```

## Next Step

After this document:

- audit and merge this docs-only change;
- then either:
  - proceed to N4 planning;
  - or run one small V0 report/handoff template preflight.

This document does not prescribe implementation beyond that. Any next step must have its own prompt, branch, allowed files, forbidden files, validation gates, audit, and merge decision.
