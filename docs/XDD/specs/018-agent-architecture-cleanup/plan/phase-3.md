---
title: "Phase 3: Skills & WHY Docs (Layer C + AC-14)"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Skills & WHY Docs (Layer C + AC-14)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Directory Map; lines: 296-326]`
- `[ref: SDD/Building Block View — Components; lines: 255-294]`
- `[ref: PRD/F-7; lines: 168-171]`
- `[ref: PRD/AC-9; lines: 298-305]`
- `[ref: PRD/AC-10; lines: 307-311]`
- `[ref: PRD/AC-13; lines: 336-349]`
- `[ref: PRD/AC-14; lines: 351-363]`

**Key Decisions**:
- ADR-2: Skills at `tomo/dot_claude/skills/` (not `tomo/skills/`)
- Skills contain how-to invocations, not prose rationale (per `[[feedback_tell_how_not_what]]`)
- SKILL.md directory format required (per `[[feedback_skill_format_distinction]]`)
- AC-14: WHY docs MUST be written BEFORE any runtime content is stripped
- Version comments: number only, no parenthetical (per `[[feedback_version_comments_number_only]]`)

**Dependencies**:
- Phase 1 (T1.1 routing-plan.schema.json) — routing-plan-consumer skill references the schema
- Phase 2 is NOT a dependency — skills describe patterns, not runtime outputs

---

## Tasks

Creates the 6 lazy-loaded skills that conductors reference, and harvests rationale from legacy agent files into `docs/tomo/` WHY-docs before legacy content is stripped.

- [ ] **T3.1 WHY docs harvest from legacy agents** `[activity: documentation]`

  1. Prime: Read legacy agents being replaced: `tomo/dot_claude/agents/inbox-orchestrator.md` (760 lines) `[ref: tomo/dot_claude/agents/inbox-orchestrator.md]` and `tomo/dot_claude/agents/instruction-builder.md` (380 lines) `[ref: tomo/dot_claude/agents/instruction-builder.md]`; read `/inbox` command `[ref: tomo/dot_claude/commands/inbox.md]`; read AC-14 requirements `[ref: PRD/AC-14; lines: 351-363]`
  2. Test: Each docs/tomo entry captures: decision context, alternatives considered, platform constraints. WHY-shaped phrasing used (not spec-ref or date-stamped). Every non-trivial rationale from the legacy files has a corresponding docs/tomo entry
  3. Implement: Create `docs/tomo/dot_claude/agents/inbox-orchestrator.md` — harvest WHY content (dispatch decisions, Phase sequencing rationale, transcription stop-gate reason, discovery logic motivation). Create `docs/tomo/dot_claude/agents/instruction-builder.md` — harvest WHY content (FAN sub-flow rationale, MOC merge logic, Step ordering). Create `docs/tomo/dot_claude/commands/inbox.md` — harvest WHY content (auto-discovery rationale, pass flags, recover mode)
  4. Validate: Manually verify every section of legacy agents that contains rationale has a corresponding WHY entry in docs/tomo
  5. Success: AC-14 satisfied — all rationale preserved before any runtime strip `[ref: PRD/AC-14]`

- [ ] **T3.2 Core skills (always-loaded by conductors)** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read SDD skill list `[ref: SDD/Building Block View — Components; lines: 255-294]`; read existing skill format in `tomo/dot_claude/skills/` for conventions; read routing-plan schema `[ref: tomo/schemas/routing-plan.schema.json]`
  2. Test: Each skill has valid `SKILL.md` in directory format; contains only invocations and branching logic (no prose rationale); no spec refs, dates, or historical wording (AC-13); passes `/skill-author` audit
  3. Implement: Create 3 skills:
     - `tomo/dot_claude/skills/routing-plan-consumer/SKILL.md` — how to read routing-plan.json, branch on action, access typed buckets
     - `tomo/dot_claude/skills/suggestions-doc-format/SKILL.md` — doc layout conventions, approval-checkbox patterns, output shape for suggestions/fan docs
     - `tomo/dot_claude/skills/instructions-coverage/SKILL.md` — sources field semantics, coverage computation logic, drift indicator handling
  4. Validate: `/skill-author` audit on each; verify AC-13 compliance (no spec refs, dates, rationale in runtime content)
  5. Success:
     - [ ] 3 core skills exist in `tomo/dot_claude/skills/` `[ref: PRD/F-7]`
     - [ ] Runtime hygiene: no inline documentation `[ref: PRD/AC-13]`
     - [ ] Pass `/skill-author` audit `[ref: SDD/Quality Requirements — SKILL-QA]`

- [ ] **T3.3 Conditional skills (loaded on-demand)** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read SDD skill list `[ref: SDD/Building Block View — Components; lines: 255-294]`; read existing force-atomic handling in instruction-builder.md Step 2.5 `[ref: tomo/dot_claude/agents/instruction-builder.md]`; read tomo_lifecycle.py for STATE_MACHINE `[ref: tomo/scripts/lib/tomo_lifecycle.py]`
  2. Test: Each skill has valid `SKILL.md` in directory format; contains only invocations and branching logic; force-atomic-handling extracted cleanly from instruction-builder; tomo-lifecycle-states references actual STATE_MACHINE; kado-discovery-patterns uses proven kado_client invocations
  3. Implement: Create 3 skills:
     - `tomo/dot_claude/skills/force-atomic-handling/SKILL.md` — FAN sub-flow: when to dispatch inbox-analyst with force_atomic=true, how to read force_atomic_items from routing-plan, how to produce fan companion doc
     - `tomo/dot_claude/skills/tomo-lifecycle-states/SKILL.md` — STATE_MACHINE reference, transition rules, state-promoter invocation patterns
     - `tomo/dot_claude/skills/kado-discovery-patterns/SKILL.md` — listDir + byFrontmatter recipes, kado-read caching patterns, error handling
  4. Validate: `/skill-author` audit on each; verify force-atomic-handling covers AC-10 (FAN via skill, not inline)
  5. Success:
     - [ ] 3 conditional skills exist in `tomo/dot_claude/skills/` `[ref: PRD/F-7]`
     - [ ] Force-atomic logic in skill, not conductor `[ref: PRD/AC-10]`
     - [ ] Runtime hygiene: no inline documentation `[ref: PRD/AC-13]`
     - [ ] Pass `/skill-author` audit `[ref: SDD/Quality Requirements — SKILL-QA]`

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  Verify all 6 skills exist with correct directory structure. Run `/skill-author` audit on each. Verify docs/tomo files capture all legacy WHY content. Cross-check: every skill referenced in SDD Component diagram (lines 255-294) has a corresponding SKILL.md. AC-13 spot-check: grep runtime files for spec refs, dates, historical wording — expect zero hits.
