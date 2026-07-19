---
title: "Phase 5: Agent, Command, Wizard, Docs"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Agent, Command, Wizard, Docs

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — garden-auditor.md, /garden-audit]`
- `[ref: SDD/Runtime View — Primary Flow + Secondary Flow (wizard)]`
- `[ref: SDD/ADR-2, ADR-6]` `[ref: SDD/CON-2]`
- `tomo/dot_claude/commands/moc-propose.md`, `tomo/dot_claude/agents/moc-architect.md` (patterns to mirror)

**Key Decisions**: ADR-6 (mirror the moc-propose command/agent), ADR-2 (exclusion wizard + `--configure`, skill-managed, never via `/inbox`). Runtime files carry only imperatives; WHY lives in `docs/tomo/` (CON-2).

**Dependencies**: Phases 2-4 (the scripts the agent orchestrates).

---

## Tasks

Delivers the user-facing entry point, the interactive exclusion management, and the WHY-persistence docs.

- [ ] **T5.1 `garden-auditor.md` orchestration agent + exclusion wizard** `[activity: agent-authoring]`

  1. Prime: Read moc-architect (orchestration discipline: "MUST NOT analyse yourself"), and the wizard flow `[ref: SDD/Runtime View — Secondary Flow]`.
  2. Test (spec-conformance review, not unit): agent runs scan → render → transport via `kado-write-file` (never inline); first-run (no config) triggers the wizard (scan → surface clusters → ask permanent → ask temporary → write config → filtered report); `--configure` re-runs the wizard; exclusion writes go to the skill config, never through `/inbox`; emits a fixed output block.
  3. Implement: `tomo/dot_claude/agents/garden-auditor.md` (STRICT/MUST/NEVER where runtime deviation is a risk).
  4. Validate: run the agent-author audit; restart-after-sync note; dry-run the wizard against the test vault.
  - Success: on-demand whole-vault audit + skill-side exclusion management `[ref: PRD/Feature 5, Detailed Spec — wizard]`.

- [ ] **T5.2 `/garden-audit` command shim** `[activity: agent-authoring]` `[parallel: true]`

  1. Prime: Read moc-propose.md (impersonate-not-dispatch pattern).
  2. Test: the shim is a thin overview that impersonates `garden-auditor.md` (does NOT dispatch via Agent tool); passes `--configure` through.
  3. Implement: `tomo/dot_claude/commands/garden-audit.md`.
  4. Validate: agent-author/skill audit; `/tomo-help` surfaces it (container project skills are `/name`-invocable only).
  - Success: `/garden-audit` + `/garden-audit --configure` invoke the agent `[ref: SDD/ADR-6]`.

- [ ] **T5.3 docs/tomo WHY mirrors** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/CON-2]` and an existing `docs/tomo/scripts/*.md` mirror.
  2. Test: every new runtime file (`garden-audit.py`, `-render.py`, `-parser.py`, `lib/garden_exclusions.py`, `garden-auditor.md`, command) has a `docs/tomo/<mirror>.md` capturing the WHY (ADR refs, STRICT rationale, the example-driven Hashi posture).
  3. Implement: the mirror docs.
  4. Validate: gap-scan — every new runtime file has a mirror.
  - Success: WHY-persistence complete `[ref: SDD/CON-2]`.

- [ ] **T5.4 Phase Validation** `[activity: validate]`

  - Agent/skill audits pass; version headers set on managed files; `update-tomo` delivers agent + command + scripts (grep instance copy).
