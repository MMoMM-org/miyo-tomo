---
title: "Phase 3: Paid green runs and findings"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Paid green runs and findings

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Error Handling]`: what a red result means, and the rule never to loosen a grader to get green.
- `[ref: SDD/Known Technical Issues]`: the conductor's `mcp__kado__kado-write` constraint contradicts the skill, and the HHMM source is unspecified.
- `[ref: PRD/Risks]`: a grader that is red on the current prose is a finding.
- `[ref: README Decisions Log 2026-10-30]`: a red WARN-before-dispatch result is fixed in the prose.

**Key Decisions**:
- Paid runs are started by the owner from a terminal (`!` prefix or a plain terminal), never while an agent is writing files.
- A red result on the current prose is fixed in the runtime prose.
  - The WHY goes to `docs/tomo/<mirrored-path>.md` first.
  - The edit goes through `tcs-helper:skill-author` / `agent-author`.
  - `# version:` is bumped.
- Fixing a case or a stub instead of the prose is allowed only when the trace shows that the stand-in, not the model, deviated from production.

**Dependencies**:
- Phase 2 complete, all pytest green, tree clean (committed).

---

## Tasks

This phase gets the new cases green on real model runs and turns every red result into a fix or a recorded decision.

- [ ] **T3.1 Smoke run and triage** `[activity: validate]`

  1. Prime: the Phase 2 hand-off command, and how to read kept traces (`evals/README.md`, Reading a failure).
  2. Test (owner): `scripts/run-evals.sh --case 'pass1-*' --runs 1 --keep-temp`. Expected cost is about $0.50.
  3. Implement: read every red grader in the kept traces and classify the cause:
     - (a) a prose finding;
     - (b) stand-in fidelity;
     - (c) a pattern defect.
     Record the classification and the evidence (trace line) in `docs/XDD/specs/043-pass1-conductor-eval-gate/findings.md`. The expected (a) finding is relay 02 (WARN before the first dispatch).
  4. Validate: every red grader has a classification backed by a trace line. Unknowns are not allowed.
  5. Success: the finding list is complete `[ref: PRD/Risks]`

- [ ] **T3.2 Fix findings** `[activity: runtime-prose]`

  1. Prime: `findings.md`; CLAUDE.md runtime-file rules; `docs/tomo/dot_claude/skills/suggest-handling.md` and `docs/tomo/dot_claude/agents/suggestion-conductor.md`.
  2. Test: the offline harness (T2.1) still passes. For (b) and (c), add a fixture that reproduces the defect before fixing it.
  3. Implement, per finding:
     - (a) The WHY goes into the docs/tomo counterpart, then the imperative edit, then the version bump. Example: make the WARN relay a visible message before the batch-count step. If the `mcp__kado__kado-write` constraint is implicated, align the conductor with the skill.
     - (b) and (c): fix the stub or the pattern with its fixture.
  4. Validate:
     - pytest is green.
     - The owner re-runs the smoke (`--case 'pass1-*' --runs 1`) until it is green.
     - A prose edit touches a gated file, so it is covered by the T3.3 full suite.
  5. Success: the smoke is green `[ref: PRD/F1, F2]`; every finding is closed or recorded with an owner decision.

- [ ] **T3.3 Full-suite green** `[activity: validate]`

  1. Prime: the merge rule in `evals/README.md`.
  2. Test (owner): `scripts/run-evals.sh` (7 cases × 3 runs; expected about $2.50–3.10).
  3. Implement: if the Pass 2 report-only grader is red in any run, treat it as a finding as in T3.1 and T3.2. The deviation is the one #205 already saw, so the fix belongs in `synthesis-conductor.md`'s report step.
  4. Validate: GREEN, with the cost and duration recorded in `findings.md`.
  5. Success: one full-suite GREEN on the current prose `[ref: PRD/F6-AC3 (first of three)]`

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Confirm that `findings.md` is complete and that every runtime-prose edit has its docs/tomo counterpart and a version bump.
  - Run pytest and shellcheck.
  - Update the instance only if the owner asks for it (`update-tomo.sh --instance tomo-instance --yolo`, never tomo-privat).
