---
title: "Phase 2: Agent Definitions"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Agent Definitions

## Phase Context

**Specification References**:
- `docs/XDD/reference/tier-3/inbox/inbox-analysis.md` — classification heuristics, InboxItemAnalysis
- `docs/XDD/reference/tier-3/inbox/suggestions-document.md` — Pass 1 document format
- `docs/XDD/reference/tier-3/inbox/instruction-set-generation.md` — Pass 2 action handlers
- `docs/XDD/reference/tier-3/inbox/instruction-set-cleanup.md` — cleanup logic
- `docs/XDD/reference/tier-2/workflows/inbox-processing.md` — overall flow

**Dependencies**: Phase 1 (scripts must exist so agents know what to call)

---

## Tasks

- [ ] **T2.1 Inbox Analyst Agent** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/inbox/inbox-analysis.md]` and `[ref: docs/XDD/reference/tier-2/workflows/inbox-processing.md]`
  2. Test: Agent classifies inbox items through 4-layer stack; detects 8+ note types (fleeting, coding_insight, system_action, external_source, quote, question, task, attachment, unknown); matches items to MOCs using discovery cache; detects tracker relevance; assesses atomic note worthiness; produces InboxItemAnalysis per item and batch summary
  3. Implement: Create `tomo/.claude/agents/inbox-analyst.md` with classification heuristics, MOC matching delegation (uses lyt-patterns skill), batch clustering logic
  4. Validate: Agent references correct scripts and skills; covers all classification types
  5. Success: Agent definition enables complete inbox analysis

- [ ] **T2.2 Suggestion Builder Agent** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/inbox/suggestions-document.md]`
  2. Test: Agent takes InboxItemAnalysis data, generates suggestions document with per-item sections (S01, S02...), checkboxes, alternatives, editable fields; writes to inbox folder via Kado; tags as proposed; handles batch limits (warn at 30+, split at 50+)
  3. Implement: Create `tomo/.claude/agents/suggestion-builder.md` with document format, per-item section template, alternative generation, cluster detection sections
  4. Validate: Agent produces correctly formatted suggestions document structure
  5. Success: Suggestions document matches spec format with all required fields

- [ ] **T2.3 Instruction Builder Agent** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/inbox/instruction-set-generation.md]`
  2. Test: Agent parses confirmed suggestions (delegates to suggestion-parser.py), generates instruction set with 5 action handlers (new atomic note, new MOC, MOC link, daily note update, note modification); renders templates via token-render.py; writes auxiliary files; groups actions by type; tags as instructions
  3. Implement: Create `tomo/.claude/agents/instruction-builder.md` with action handler definitions, token resolution delegation, auxiliary file generation, action ordering (new files → links → daily → modifications)
  4. Validate: Agent references correct scripts; covers all 5 action handlers
  5. Success: Instruction set matches spec format with actionable per-item instructions

- [ ] **T2.4 Vault Executor Agent** `[parallel: true]` `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/inbox/instruction-set-cleanup.md]` and `[ref: docs/XDD/reference/tier-3/inbox/state-tag-lifecycle.md]`
  2. Test: Agent handles cleanup phase; transitions fully-applied sources to active; archives suggestions/instructions; optional archive moves; optional auxiliary deletion; idempotent (safe to run twice); auto-detection of applied actions
  3. Implement: Create `tomo/.claude/agents/vault-executor.md` with cleanup workflow, state transitions, archive logic, auto-detection heuristics
  4. Validate: Agent handles all state transitions correctly; idempotent
  5. Success: Cleanup workflow matches spec with proper state machine enforcement

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - All 4 agent files exist with version comments. Each references correct scripts/skills. State machine transitions are consistent across agents.
