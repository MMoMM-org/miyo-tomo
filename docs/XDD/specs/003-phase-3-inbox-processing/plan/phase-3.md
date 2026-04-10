---
title: "Phase 3: Command + Skills"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Command + Skills

## Phase Context

**Specification References**:
- `docs/specs/tier-2/workflows/inbox-processing.md` — workflow orchestration
- `docs/specs/tier-3/inbox/state-tag-lifecycle.md` — run-to-run discovery
- `docs/specs/tier-3/templates/token-vocabulary.md` — token system knowledge

**Dependencies**: Phase 2 (agent definitions determine what command orchestrates)

---

## Tasks

- [ ] **T3.1 Inbox Command** `[activity: build-feature]`

  1. Prime: Read existing `tomo/.claude/commands/inbox.md` and `[ref: docs/specs/tier-2/workflows/inbox-processing.md]`
  2. Test: Command implements run-to-run discovery (check applied→confirmed→captured); dispatches to correct agent per state; supports `--pass1` (force suggestions), `--pass2` (force instructions), `--cleanup` (force cleanup); clear user instructions
  3. Implement: Update `tomo/.claude/commands/inbox.md` with full orchestration logic
  4. Validate: Command references all 4 agents; implements priority discovery
  5. Success: `/inbox` correctly routes to the right agent based on current state

- [ ] **T3.2 PKM Workflows Skill** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/inbox/state-tag-lifecycle.md]` and `[ref: docs/specs/tier-3/inbox/inbox-analysis.md]`
  2. Test: Skill encodes state machine (7 states, transitions, ownership), classification heuristics (8 types with keywords/patterns), batch processing patterns, date extraction from filenames
  3. Implement: Create `tomo/.claude/skills/pkm-workflows.md` with state machine reference, classification patterns, workflow knowledge
  4. Validate: All 7 states documented; transitions match spec
  5. Success: Skill provides complete workflow knowledge for agents

- [ ] **T3.3 Template Render Skill** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/specs/tier-3/templates/token-vocabulary.md]` and `[ref: docs/specs/tier-2/components/template-system.md]`
  2. Test: Skill encodes token categories (5 types), resolution order, YAML list formatting, Templater coexistence rules, required vs optional handling, custom token declaration, fallback template
  3. Implement: Create `tomo/.claude/skills/template-render.md` with token reference, rendering pipeline, validation rules
  4. Validate: All token categories documented; resolution order correct
  5. Success: Skill provides complete template rendering knowledge

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Command and skills exist with version comments. Command references all agents. Skills cover all spec-defined patterns.
