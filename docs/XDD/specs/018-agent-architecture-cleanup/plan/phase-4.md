---
title: "Phase 4: Conductors & Router (Layer B)"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Conductors & Router (Layer B)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View — Primary Flow: Suggest (Pass 1); lines: 715-749]`
- `[ref: SDD/Runtime View — Primary Flow: FAN Resolve (Pass 1b); lines: 751-782]`
- `[ref: SDD/Runtime View — Primary Flow: Synthesize (Pass 2); lines: 788-815]`
- `[ref: SDD/Runtime View — Primary Flow: Idle; lines: 817-824]`
- `[ref: SDD/Runtime View — Primary Flow: Transcribe (stop-gate); lines: 826-837]`
- `[ref: SDD/Interface Specifications — Conductor → Leaf Agent Dispatch Interface; lines: 606-624]`
- `[ref: PRD/F-2; lines: 137-141]`
- `[ref: PRD/F-3; lines: 143-148]`
- `[ref: PRD/F-4; lines: 149-153]`

**Key Decisions**:
- Conductors are IMPERSONATED (run in main session) — they need Agent tool for leaf dispatch (CON-2)
- Leaf agents (inbox-analyst, voice-transcriber) are DISPATCHED via Agent tool
- ADR-4: Opus-level reasoning via leaf dispatch with `model: opus` in Agent tool call
- ADR-7: FAN resolve is a suggestion-conductor mode (analysis work)
- Runtime hygiene: conductors have invocations only, domain knowledge in skills (AC-9, AC-13)
- Transcribe action bypasses conductors entirely — /inbox dispatches voice-transcriber directly

**Dependencies**:
- Phase 2 (T2.1, T2.2 inbox-triage.py) — conductors consume routing-plan.json
- Phase 3 (T3.2, T3.3 skills) — conductors load skills for domain knowledge

---

## Tasks

Builds the two thin conductor agents and rewrites /inbox as a routing-plan consumer. Conductors contain only orchestration logic; all domain knowledge comes from Phase 3 skills.

- [ ] **T4.1 suggestion-conductor agent** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read SDD suggest flow `[ref: SDD/Runtime View — Primary Flow: Suggest (Pass 1); lines: 715-749]`; read FAN resolve flow `[ref: SDD/Runtime View — Primary Flow: FAN Resolve (Pass 1b); lines: 751-782]`; read dispatch interface `[ref: SDD/Interface Specifications — Conductor → Leaf Agent Dispatch Interface; lines: 606-624]`; read legacy inbox-orchestrator.md for code paths to replicate `[ref: tomo/dot_claude/agents/inbox-orchestrator.md]`
  2. Test: Agent file has valid frontmatter (model, tools, skills); loads routing-plan-consumer + suggestions-doc-format always; loads force-atomic-handling only when action=fan-resolve; dispatches voice-transcriber for audio (stop-gate on transcribe > 0); dispatches inbox-analyst per fresh_source item; calls pipeline scripts (run-id.py, shared-ctx-builder.py, suggestions-reducer.py, suggestions-render.py); calls mark-captured.py for state tagging; contains NO inline domain knowledge or rationale; passes `/agent-author` audit
  3. Implement: Create `tomo/dot_claude/agents/suggestion-conductor.md`. Two modes: (a) `suggest` — fresh classify flow (Phase A→B→C→D equivalent), (b) `fan-resolve` — FAN sub-flow (today's Step 2.5). Agent reads routing-plan.json for mode and data. Dispatches leaf agents via Agent tool. Calls scripts via Bash. Create `docs/tomo/dot_claude/agents/suggestion-conductor.md` WHY doc
  4. Validate: `/agent-author` audit; verify no spec refs, dates, or rationale in runtime file (AC-13); verify all script calls use actual `python3 scripts/...` invocations (per `[[feedback_tell_how_not_what]]`)
  5. Success:
     - [ ] Agent handles suggest + fan-resolve modes `[ref: PRD/F-3]` `[ref: SDD/ADR-7]`
     - [ ] Contains only orchestration logic `[ref: PRD/AC-9]`
     - [ ] Runtime hygiene clean `[ref: PRD/AC-13]`
     - [ ] Passes `/agent-author` audit `[ref: SDD/Quality Requirements — AGENT-QA]`

- [ ] **T4.2 synthesis-conductor agent** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read SDD synthesize flow `[ref: SDD/Runtime View — Primary Flow: Synthesize (Pass 2); lines: 788-815]`; read dispatch interface `[ref: SDD/Interface Specifications — Conductor → Leaf Agent Dispatch Interface; lines: 606-624]`; read legacy instruction-builder.md for code paths to replicate `[ref: tomo/dot_claude/agents/instruction-builder.md]`
  2. Test: Agent file has valid frontmatter; loads routing-plan-consumer + instructions-coverage always; reads cached docs from inbox-cache/ (not via kado-read — AC-5); calls suggestion-parser.py (from cache paths); calls instruction-render.py (populates sources[]); calls upload-rendered.py; calls state-promoter.py; calls instructions-diff.py; contains NO inline domain knowledge or rationale; passes `/agent-author` audit
  3. Implement: Create `tomo/dot_claude/agents/synthesis-conductor.md`. Single mode: synthesize. Reads approved docs + moc-proposals from routing-plan and inbox-cache. Calls pipeline scripts in sequence. No analysis branches (those are in suggestion-conductor). Create `docs/tomo/dot_claude/agents/synthesis-conductor.md` WHY doc
  4. Validate: `/agent-author` audit; verify reads from cache (not kado-read); verify no spec refs, dates, or rationale in runtime file (AC-13)
  5. Success:
     - [ ] Agent handles synthesize mode `[ref: PRD/F-4]`
     - [ ] Reads from inbox-cache, not Kado `[ref: PRD/AC-5]`
     - [ ] Handles approved suggestions + moc-proposals in single invocation `[ref: PRD/AC-2]`
     - [ ] Contains only orchestration logic `[ref: PRD/AC-9]`
     - [ ] Passes `/agent-author` audit `[ref: SDD/Quality Requirements — AGENT-QA]`

- [ ] **T4.3 /inbox command rewrite** `[activity: backend-implementation]`

  1. Prime: Read current /inbox command `[ref: tomo/dot_claude/commands/inbox.md]`; read SDD idle flow `[ref: SDD/Runtime View — Primary Flow: Idle; lines: 817-824]`; read SDD transcribe flow `[ref: SDD/Runtime View — Primary Flow: Transcribe (stop-gate); lines: 826-837]`; read PRD F-2 `[ref: PRD/F-2; lines: 137-141]`
  2. Test: Command calls `python3 scripts/inbox-triage.py` exactly once before any dispatch (AC-4); reads routing-plan.json for action; impersonates suggestion-conductor for action=suggest or fan-resolve; impersonates synthesis-conductor for action=synthesize; dispatches voice-transcriber directly for action=transcribe (no conductor); surfaces idle_reasons + pending_approval for action=idle (AC-6); preserves --pass1/--pass2/--recover flag passthrough to triage; contains NO in-command markdown auto-discovery logic (current lines 90-101 deleted)
  3. Implement: Rewrite `tomo/dot_claude/commands/inbox.md` as thin router. One Bash call to triage, one JSON read, one branch to impersonate/dispatch/idle. Create `docs/tomo/dot_claude/commands/inbox.md` WHY doc for the router design
  4. Validate: Verify no inline routing logic remains; verify triage is the only routing computation (AC-4); `/agent-author` audit on command file
  5. Success:
     - [ ] Exactly one triage call before any agent dispatch `[ref: PRD/AC-4]`
     - [ ] No in-command auto-discovery logic `[ref: PRD/F-2]`
     - [ ] Idle surfaces reasons to user `[ref: PRD/AC-6]`
     - [ ] Transcribe stop-gate works without conductor `[ref: SDD/Runtime View — Transcribe]`
     - [ ] All 5 actions routed correctly `[ref: SDD/Complex Logic: Action Determination]`

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  `/agent-author` audit on both conductors and /inbox command. AC-9 spot-check: verify conductors contain ONLY orchestration (routing, dispatch, branching). AC-13 spot-check: grep all new runtime files for spec refs (`F-\d+`, `ADR-\d+`, `XDD-\d+`), dates (`\d{4}-\d{2}-\d{2}`), historical wording — expect zero hits. Verify all docs/tomo WHY files created for new runtime files. Run `python3 -m ruff check tomo/scripts/` to catch any script changes.
