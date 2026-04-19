---
title: "Phase 2: Simplify instruction-builder agent"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Simplify instruction-builder agent

## Phase Context

**Dependencies**: Phase 1 must be complete (instruction-render.py produces both files).

**Key files**:
- `tomo/.claude/agents/instruction-builder.md` (main target)

---

## Tasks

The instruction-builder currently assembles markdown by reading manifest.json +
parsed-suggestions.json and building instruction entries. After Phase 1, the script
handles all of this. The agent becomes a pure orchestrator.

- [ ] **T2.1 Rewrite instruction-builder as orchestrator** `[activity: agent-design]`

  1. Prime: Read current instruction-builder.md (Steps 1-6).
  2. Implement: Simplify to 4 steps:
     - Step 1: Resolve paths (unchanged — batch config load)
     - Step 2: Parse suggestions (unchanged — `suggestion-parser.py`)
     - Step 3: Render everything (one call to `instruction-render.py` which now
       produces rendered notes + `instructions.json` + `instructions.md`)
     - Step 4: Write to vault via kado-write:
       - Each rendered note file → `<inbox>/<filename>`
       - `instructions.json` → `<inbox>/<date>_instructions.json`
       - `instructions.md` → `<inbox>/<date>_instructions.md`
     - Step 5: Report to user
  3. Validate: Agent doc is shorter, clearer, no markdown assembly logic.

  **Remove entirely:**
  - Step 5 (Assemble instruction entries) — script does this now
  - All markdown templates (Move note, MOC link, Daily update, Delete source)
  - MOC reading via kado-read for callout detection — script handles this
  - Position value mapping — script handles this

  **Keep:**
  - Step 1 (config resolution)
  - Step 2 (suggestion parsing)
  - Step 4 (kado-write loop)
  - Format rules (wikilink conventions) — move to script, remove from agent

- [ ] **T2.2 Update model/effort** `[activity: agent-design]`

  1. Prime: Current: `model: opus`, `effort: xhigh`.
  2. Implement: The agent now just runs 3 scripts and writes files via Kado.
     No judgment needed. Downgrade to `model: sonnet`, `effort: medium`.
  3. Validate: Agent works with lower model. Cost savings per Pass 2 run.

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  - instruction-builder.md is shorter (target: ~60 lines, down from ~190)
  - Agent runs scripts and writes results — no markdown assembly
  - Pass 2 produces identical output (instructions.json + instructions.md)
  - Model downgrade doesn't affect quality (agent is mechanical now)
